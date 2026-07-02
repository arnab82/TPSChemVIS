"""
First-launch setup dialog.

Shown once when no valid TPSChem.jl project is configured.  The user can
either point to an existing clone or let the app clone and build it.
"""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

import asbuilder.config as cfg


class _CloneWorker(QThread):
    line = pyqtSignal(str)
    done = pyqtSignal(bool, str)   # success, message

    def __init__(self, dest: Path, julia_bin: str, parent=None):
        super().__init__(parent)
        self._dest = dest
        self._julia_bin = julia_bin

    def run(self):
        try:
            # --- 1. git clone ---
            self.line.emit(f"Cloning {cfg.TPSCHEM_REPO} → {self._dest} …")
            result = subprocess.run(
                ["git", "clone", cfg.TPSCHEM_REPO, str(self._dest)],
                capture_output=True, text=True,
            )
            for l in (result.stdout + result.stderr).splitlines():
                self.line.emit(l)
            if result.returncode != 0:
                self.done.emit(False, "git clone failed")
                return

            # --- 2. Pkg.instantiate ---
            self.line.emit("Running Pkg.instantiate …")
            script = (
                f'import Pkg; Pkg.activate(raw"{self._dest}"); '
                'Pkg.instantiate(); println("[setup] instantiate done")'
            )
            result = subprocess.run(
                [self._julia_bin, "-e", script],
                capture_output=True, text=True, timeout=600,
            )
            for l in (result.stdout + result.stderr).splitlines():
                self.line.emit(l)
            if result.returncode != 0:
                self.done.emit(False, "Pkg.instantiate failed")
                return

            # --- 3. Pkg.build("PyCall") ---
            self.line.emit("Building PyCall (links Julia to current Python) …")
            script = (
                f'import Pkg; Pkg.activate(raw"{self._dest}"); '
                'Pkg.build("PyCall"); println("[setup] PyCall build done")'
            )
            result = subprocess.run(
                [self._julia_bin, "-e", script],
                capture_output=True, text=True, timeout=300,
            )
            for l in (result.stdout + result.stderr).splitlines():
                self.line.emit(l)
            if result.returncode != 0:
                self.done.emit(False, "Pkg.build(PyCall) failed")
                return

            self.done.emit(True, str(self._dest))
        except Exception as exc:
            self.done.emit(False, str(exc))


class SetupDialog(QDialog):
    """Modal dialog shown on first launch (or when TPSChem.jl is not found)."""

    def __init__(self, julia_bin: str = "julia", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Active Space Builder — First-launch setup")
        self.setMinimumWidth(620)
        self.resize(680, 520)
        self._julia_bin = julia_bin
        self._worker: _CloneWorker | None = None
        self.chosen_path: Path | None = None   # set on success

        info = QLabel(
            "<b>TPSChem.jl is required to run CMF and TPSCI calculations.</b><br>"
            "Either point to an existing clone, or let the app download and build it now."
        )
        info.setWordWrap(True)

        # --- Option A: existing clone ---
        self._existing_edit = QLineEdit()
        self._existing_edit.setPlaceholderText("e.g. /Users/you/workspace/TPSChem.jl")
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse)
        use_existing_btn = QPushButton("Use this folder")
        use_existing_btn.clicked.connect(self._use_existing)
        row_a = QHBoxLayout()
        row_a.addWidget(self._existing_edit)
        row_a.addWidget(browse_btn)
        existing_group = QGroupBox("Use existing TPSChem.jl clone")
        existing_layout = QVBoxLayout(existing_group)
        existing_layout.addLayout(row_a)
        existing_layout.addWidget(use_existing_btn)

        # --- Option B: auto-install ---
        self._install_dir_edit = QLineEdit(str(cfg.DEFAULT_INSTALL_DIR))
        browse_install_btn = QPushButton("Browse…")
        browse_install_btn.setFixedWidth(80)
        browse_install_btn.clicked.connect(self._browse_install_dir)
        dir_row = QHBoxLayout()
        dir_row.addWidget(self._install_dir_edit)
        dir_row.addWidget(browse_install_btn)

        self._install_btn = QPushButton(f"Clone from GitHub and build  ({cfg.TPSCHEM_REPO})")
        self._install_btn.clicked.connect(self._start_install)

        install_group = QGroupBox("Download and build automatically")
        install_layout = QVBoxLayout(install_group)
        install_layout.addWidget(QLabel("Install to:"))
        install_layout.addLayout(dir_row)
        install_layout.addWidget(self._install_btn)

        # --- log ---
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        f = self._log.font(); f.setFamily("monospace"); self._log.setFont(f)
        self._log.setMaximumHeight(180)

        # --- status + buttons ---
        self._status = QLabel("")
        self._btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._btns.rejected.connect(self.reject)
        self._ok_btn = self._btns.addButton("Continue →", QDialogButtonBox.ButtonRole.AcceptRole)
        self._ok_btn.setEnabled(False)
        self._ok_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(existing_group)
        layout.addWidget(install_group)
        layout.addWidget(QLabel("Output:"))
        layout.addWidget(self._log)
        layout.addWidget(self._status)
        layout.addWidget(self._btns)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Select TPSChem.jl directory")
        if d:
            self._existing_edit.setText(d)

    def _browse_install_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Install TPSChem.jl into…")
        if d:
            self._install_dir_edit.setText(str(Path(d) / "TPSChem.jl"))

    def _use_existing(self):
        p = Path(self._existing_edit.text().strip())
        if not (p / "Project.toml").exists():
            self._status.setText(f"No Project.toml found in {p}")
            return
        cfg.set_value("julia_project", str(p))
        self.chosen_path = p
        self._status.setText(f"Saved: {p}")
        self._ok_btn.setEnabled(True)

    def _start_install(self):
        dest = Path(self._install_dir_edit.text().strip())
        if dest.exists() and (dest / "Project.toml").exists():
            self._log.appendPlainText(f"{dest} already exists — using it.")
            cfg.set_value("julia_project", str(dest))
            self.chosen_path = dest
            self._ok_btn.setEnabled(True)
            return
        self._install_btn.setEnabled(False)
        self._worker = _CloneWorker(dest, self._julia_bin, parent=self)
        self._worker.line.connect(self._log.appendPlainText)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, success: bool, message: str):
        self._install_btn.setEnabled(True)
        if success:
            p = Path(message)
            cfg.set_value("julia_project", str(p))
            self.chosen_path = p
            self._status.setText(f"Installed and configured: {p}")
            self._ok_btn.setEnabled(True)
        else:
            self._status.setText(f"Failed: {message}")
