"""
Atom table for SPADE mode.

Shows all atoms in the molecule with columns:
    Idx | Element | x | y | z | Cluster

Clicking a row assigns that atom to whichever cluster is active in the
ClusterManager.  A second click on the same atom removes the assignment
(sends it back to "unassigned").

Used by ViewerScreen when the user selects "SPADE by atoms" mode.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from asbuilder.cluster.state import ClusterSet

_COLS = ["Idx", "Element", "x (Å)", "y (Å)", "z (Å)", "Cluster"]
_BOHR = 0.529177


class AtomTable(QWidget):
    atom_clicked = pyqtSignal(int)   # emits 0-based atom index

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cluster_set: ClusterSet | None = None
        self._n_atoms: int = 0

        self._table = QTableWidget(0, len(_COLS))
        self._table.setHorizontalHeaderLabels(_COLS)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.cellClicked.connect(self._on_cell_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Click an atom row to assign it to the active cluster:"))
        layout.addWidget(self._table)

    def set_molecule(self, mol, cluster_set: ClusterSet) -> None:
        """Populate from a pyscf.gto.Mole object."""
        import numpy as np
        self._cluster_set = cluster_set
        self._n_atoms = mol.natm
        coords_bohr = mol.atom_coords()   # (natm, 3) in Bohr
        self._table.setRowCount(mol.natm)
        for i in range(mol.natm):
            sym = mol.atom_symbol(i)
            x, y, z = coords_bohr[i] * _BOHR
            self._table.setItem(i, 0, QTableWidgetItem(str(i)))
            self._table.setItem(i, 1, QTableWidgetItem(sym))
            self._table.setItem(i, 2, QTableWidgetItem(f"{x:.4f}"))
            self._table.setItem(i, 3, QTableWidgetItem(f"{y:.4f}"))
            self._table.setItem(i, 4, QTableWidgetItem(f"{z:.4f}"))
            self._table.setItem(i, 5, QTableWidgetItem("—"))
        self.refresh_cluster_assignments(cluster_set)

    def refresh_cluster_assignments(self, cluster_set: ClusterSet) -> None:
        self._cluster_set = cluster_set
        # Build reverse map: atom_idx -> cluster
        atom_to_cluster: dict[int, tuple[str, str]] = {}
        for c in cluster_set.clusters:
            if c.atom_indices:
                for a in c.atom_indices:
                    atom_to_cluster[a] = (c.name, c.color)

        for row in range(self._table.rowCount()):
            if row in atom_to_cluster:
                name, color = atom_to_cluster[row]
                item = QTableWidgetItem(name)
                item.setBackground(QColor(color))
            else:
                item = QTableWidgetItem("—")
            self._table.setItem(row, 5, item)

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        self.atom_clicked.emit(row)
