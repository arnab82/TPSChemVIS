"""
Screen 3: the main orbital viewer / clustering screen.

Two modes toggled by a tab widget at the top:

  Manual mode  -- user clicks MOs in the orbital table and assigns them to
                  clusters (Tier A click-to-assign). fspace is derived from
                  mo_occ automatically when the active space is built.

  SPADE mode   -- user assigns *atoms* to clusters from the atom table, and
                  optionally filters which AO types (s/p/d/f) contribute to
                  the SPADE projector per cluster. Useful for bimetallic /
                  fragment systems (Fe₂S₂, dimer, etc.).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from asbuilder.cluster.state import ClusterSet
from asbuilder.gui.widgets.atom_table import AtomTable
from asbuilder.gui.widgets.cluster_manager import ClusterManager
from asbuilder.gui.widgets.orbital_table import OrbitalTable
from asbuilder.gui.widgets.webview_panel import WebViewPanel
from asbuilder.io.chk_to_molden import ChkContents


class ViewerScreen(QWidget):
    build_requested = pyqtSignal(object, object)  # (ChkContents, ClusterSet)

    def __init__(self, vibemol_root: str | Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self._chk: ChkContents | None = None
        self.cluster_set = ClusterSet()

        # --- orbital table (manual mode) ---
        self._orbital_table = OrbitalTable()
        self._orbital_table.orbital_clicked.connect(self._on_orbital_clicked)

        # --- atom table (SPADE mode) ---
        self._atom_table = AtomTable()
        self._atom_table.atom_clicked.connect(self._on_atom_clicked)

        # --- webview (center) ---
        self._webview = WebViewPanel(vibemol_root=vibemol_root)

        # --- cluster manager (right) ---
        self._cluster_manager = ClusterManager(self.cluster_set)
        self._cluster_manager.clusters_changed.connect(self._on_clusters_changed)

        # --- mode tabs ---
        self._tabs = QTabWidget()
        self._tabs.addTab(self._orbital_table, "Manual — assign MOs")
        self._tabs.addTab(self._atom_table,    "SPADE  — assign atoms")
        self._tabs.currentChanged.connect(self._on_mode_changed)

        self._mode_label = QLabel(
            "<b>Manual mode</b>: click an MO row to assign it to the active cluster."
        )
        self._mode_label.setWordWrap(True)

        self._status = QLabel("")
        self._build_btn = QPushButton("Build Active Space")
        self._build_btn.setEnabled(False)
        self._build_btn.clicked.connect(self._on_build_clicked)

        splitter = QSplitter()
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self._mode_label)
        left_layout.addWidget(self._tabs)
        splitter.addWidget(left)
        splitter.addWidget(self._webview)
        splitter.addWidget(self._cluster_manager)
        # orbital table : VibeMol (1/4 of total) : cluster manager
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(self._status)
        bottom.addStretch(1)
        bottom.addWidget(self._build_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)
        layout.addLayout(bottom)
        self.setLayout(layout)

    # ------------------------------------------------------------------

    def load(self, chk: ChkContents, molden_path: str) -> None:
        self._chk = chk
        self._orbital_table.set_orbitals(chk.orbital_table())
        self._orbital_table.refresh_cluster_assignments(self.cluster_set)
        self._atom_table.set_molecule(chk.mol, self.cluster_set)
        self._webview.load_molden(molden_path)
        self._update_status()

    # ------------------------------------------------------------------

    def _is_spade_mode(self) -> bool:
        return self._tabs.currentIndex() == 1

    def _on_mode_changed(self, index: int) -> None:
        spade = (index == 1)
        self._cluster_manager.set_spade_mode(spade)
        if spade:
            self._mode_label.setText(
                "<b>SPADE mode</b>: click an atom row to assign it to the active cluster. "
                "Select AO types (s/p/d/f) per cluster in the panel on the right — "
                "leave all unchecked to include all AO types."
            )
        else:
            self._mode_label.setText(
                "<b>Manual mode</b>: click an MO row to assign it to the active cluster."
            )
        self._update_status()

    def _on_orbital_clicked(self, orbital_index: int) -> None:
        active_id = self._cluster_manager.active_cluster_id()
        if active_id is None:
            self._status.setText("Add/select a cluster first.")
            return
        self.cluster_set.assign_orbital(active_id, orbital_index)
        self._orbital_table.refresh_cluster_assignments(self.cluster_set)
        self._cluster_manager.refresh()
        self._update_status()

    def _on_atom_clicked(self, atom_index: int) -> None:
        active_id = self._cluster_manager.active_cluster_id()
        if active_id is None:
            self._status.setText("Add/select a cluster first.")
            return
        # Toggle: if already assigned to this cluster, unassign
        c = self.cluster_set.get(active_id)
        if c.atom_indices and atom_index in c.atom_indices:
            self.cluster_set.unassign_atom(atom_index)
        else:
            self.cluster_set.assign_atom(active_id, atom_index)
        self._atom_table.refresh_cluster_assignments(self.cluster_set)
        self._cluster_manager.refresh()
        self._update_status()

    def _on_clusters_changed(self) -> None:
        if self._is_spade_mode():
            self._atom_table.refresh_cluster_assignments(self.cluster_set)
        else:
            self._orbital_table.refresh_cluster_assignments(self.cluster_set)
        self._update_status()

    def _update_status(self) -> None:
        problems = self.cluster_set.validate()
        if problems:
            self._status.setText("; ".join(problems))
            self._build_btn.setEnabled(False)
        else:
            self._status.setText("Clusters look valid — ready to build.")
            self._build_btn.setEnabled(self._chk is not None)

    def _on_build_clicked(self) -> None:
        if self._chk is not None:
            self.build_requested.emit(self._chk, self.cluster_set)
