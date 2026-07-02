"""
"New Calculation" dialog: collects xyz / basis / method / charge / spin and
runs asbuilder.io.run_scf.run_scf in a background thread (ScfWorker), so
the GUI doesn't need its own copy of the SCF-setup logic -- it calls the
exact same function the notebook does (once run_scf.py is filled in with
the real notebook logic; currently a generic RHF/UHF/ROHF placeholder,
see io/run_scf.py's module docstring).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from asbuilder.gui.widgets.log_pane import LogPane
from asbuilder.gui.workers import ScfWorker


class NewCalculationDialog(QDialog):
    def __init__(self, default_chk_path: str | Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Calculation")
        self.resize(520, 480)

        self.result_chk_path: Path | None = None
        self._worker: ScfWorker | None = None

        self._xyz = QPlainTextEdit()
        self._xyz.setPlaceholderText("Cr 0.0 0.0 0.0\nCr 0.0 0.0 2.5\n...")
        self._xyz.setFixedHeight(120)

        self._basis = QLineEdit("sto-3g")
        self._method = QComboBox()
        self._method.addItems(["RHF", "UHF", "ROHF"])
        self._charge = QSpinBox()
        self._charge.setRange(-10, 10)
        self._spin = QSpinBox()
        self._spin.setRange(0, 20)
        self._spin.setToolTip("PySCF convention: 2S = n_alpha - n_beta")

        form = QFormLayout()
        form.addRow("XYZ (atom lines)", self._xyz)
        form.addRow("Basis set", self._basis)
        form.addRow("Method", self._method)
        form.addRow("Charge", self._charge)
        form.addRow("Spin (2S)", self._spin)

        self._status = QLabel("")
        self._log = LogPane()
        self._log.setFixedHeight(140)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._run_btn = self._buttons.addButton("Run SCF", QDialogButtonBox.ButtonRole.ActionRole)
        self._run_btn.clicked.connect(self._on_run)
        self._buttons.rejected.connect(self.reject)

        self._default_chk_path = Path(default_chk_path)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._status)
        layout.addWidget(self._log)
        layout.addWidget(self._buttons)
        self.setLayout(layout)

    def _on_run(self) -> None:
        xyz = self._xyz.toPlainText().strip()
        if not xyz:
            self._status.setText("Enter atom coordinates first.")
            return

        self._run_btn.setEnabled(False)
        self._status.setText("Running SCF...")
        self._log.append_line(f"[new_calc] basis={self._basis.text()} method={self._method.currentText()}")

        self._worker = ScfWorker(
            xyz=xyz,
            basis=self._basis.text(),
            method=self._method.currentText(),
            charge=self._charge.value(),
            spin=self._spin.value(),
            chk_path=self._default_chk_path,
            parent=self,
        )
        self._worker.finished_ok.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_finished(self, result) -> None:
        self._log.append_line(f"[new_calc] converged={result.converged} E_tot={result.e_tot:.10f}")
        self._status.setText("Done.")
        self.result_chk_path = result.chk_path
        self.accept()

    def _on_failed(self, message: str) -> None:
        self._log.append_line(f"[new_calc] FAILED: {message}")
        self._status.setText("SCF failed -- see log.")
        self._run_btn.setEnabled(True)
