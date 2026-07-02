"""
Orbital table: index / energy / occupation / assigned cluster.

This is the Tier A cluster-assignment mechanism from the design doc --
clicking a row assigns that orbital to whichever cluster is currently
"active" in the cluster manager dock. It also reflects assignments made
via a future Tier B click-on-isosurface bridge, so the two mechanisms
stay in sync regardless of which one the user actually uses.

Deliberately a QTableWidget, not a custom QAbstractTableModel -- simpler
to read for a scaffold this size. Worth revisiting if orbital counts get
into the many hundreds and repainting the whole table on every assignment
becomes visibly slow.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem

from asbuilder.cluster.state import ClusterSet
from asbuilder.io.chk_to_molden import OrbitalInfo

_COLUMNS = ["#", "Energy (Ha)", "Occ.", "Cluster"]


class OrbitalTable(QTableWidget):
    orbital_clicked = pyqtSignal(int)  # 1-based orbital index

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(_COLUMNS), parent)
        self.setHorizontalHeaderLabels(_COLUMNS)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.cellClicked.connect(self._on_cell_clicked)

        self._orbitals: list[OrbitalInfo] = []

    def set_orbitals(self, orbitals: list[OrbitalInfo]) -> None:
        self._orbitals = orbitals
        self.setRowCount(len(orbitals))
        for row, o in enumerate(orbitals):
            self.setItem(row, 0, QTableWidgetItem(str(o.index)))
            self.setItem(row, 1, QTableWidgetItem(f"{o.energy:.6f}"))
            self.setItem(row, 2, QTableWidgetItem(f"{o.occupation:.2f}"))
            self.setItem(row, 3, QTableWidgetItem(""))
        self.resizeColumnsToContents()

    def refresh_cluster_assignments(self, clusters: ClusterSet) -> None:
        """Recolor/relabel the Cluster column from the current ClusterSet.
        Call this after any assignment change (click, undo, SPADE auto-fill,
        etc.) so the table stays the single source of truth for display."""
        orbital_to_cluster = {}
        for c in clusters.clusters:
            for o in c.orbitals:
                orbital_to_cluster[o] = c

        for row, orb in enumerate(self._orbitals):
            item = self.item(row, 3)
            cluster = orbital_to_cluster.get(orb.index)
            if cluster is not None:
                item.setText(cluster.name)
                item.setBackground(QColor(cluster.color))
                item.setForeground(QColor("#000000"))
            else:
                item.setText("(unassigned)")
                item.setBackground(QColor("#ffffff"))
                item.setForeground(QColor("#999999"))

    def select_orbital(self, index: int) -> None:
        """Programmatically select the row for `index` -- used by the Tier B
        click-on-isosurface bridge to keep the table selection in sync with
        a click that originated in the VibeMol pane instead of the table."""
        for row, o in enumerate(self._orbitals):
            if o.index == index:
                self.selectRow(row)
                self.scrollToItem(self.item(row, 0))
                return

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        if 0 <= row < len(self._orbitals):
            self.orbital_clicked.emit(self._orbitals[row].index)
