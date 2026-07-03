"""Molden viewer chooser: embedded VibeMol or external Jmol."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from asbuilder import config as cfg
from asbuilder.gui.widgets.webview_panel import WebViewPanel
from asbuilder.viewers import jmol


class _JmolInstallWorker(QThread):
    line = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def run(self) -> None:
        try:
            jar = jmol.install_jmol(progress=self.line.emit)
        except Exception as exc:  # noqa: BLE001
            self.done.emit(False, f"{type(exc).__name__}: {exc}")
            return
        self.done.emit(True, str(jar))


class MoldenViewerPanel(QWidget):
    """Viewer panel that lets users choose VibeMol or desktop Jmol."""

    molden_loaded = pyqtSignal(bool)

    def __init__(self, vibemol_root: str | Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self._current_molden: Path | None = None
        self._install_worker: _JmolInstallWorker | None = None
        self._launch_after_install = False

        self._viewer_selector = QComboBox()
        self._viewer_selector.addItem("VibeMol", "vibemol")
        self._viewer_selector.addItem("Jmol", "jmol")
        active = cfg.viewer_backend()
        self._viewer_selector.setCurrentIndex(1 if active == "jmol" else 0)
        self._viewer_selector.currentIndexChanged.connect(self._on_backend_changed)

        self._install_btn = QPushButton("Install Jmol")
        self._install_btn.clicked.connect(self._on_install_jmol)
        self._open_jmol_btn = QPushButton("Open in Jmol")
        self._open_jmol_btn.clicked.connect(lambda: self._open_in_jmol(auto=False))

        self._status = QLabel("")
        self._status.setWordWrap(True)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Viewer:"))
        toolbar.addWidget(self._viewer_selector)
        toolbar.addWidget(self._install_btn)
        toolbar.addWidget(self._open_jmol_btn)
        toolbar.addStretch(1)

        self._webview = WebViewPanel(vibemol_root=vibemol_root)
        self._webview.molden_loaded.connect(self.molden_loaded.emit)

        self._jmol_placeholder = QLabel(
            "Jmol opens as a desktop Java window. Install it once, then open the "
            "selected Molden file in Jmol from this panel."
        )
        self._jmol_placeholder.setWordWrap(True)
        self._jmol_placeholder.setStyleSheet("padding: 24px; color: #666;")

        self._stack = QStackedWidget()
        self._stack.addWidget(self._webview)
        self._stack.addWidget(self._jmol_placeholder)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(toolbar)
        layout.addWidget(self._stack, stretch=1)
        layout.addWidget(self._status)
        self.setLayout(layout)
        self.setMinimumSize(0, 0)

        self._refresh_backend_ui(launch=False)

    @property
    def available(self) -> bool:
        backend = self._backend()
        if backend == "vibemol":
            return self._webview.available
        return jmol.is_jmol_installed()

    def load_molden(self, molden_path: str | Path) -> None:
        self._current_molden = Path(molden_path)
        if self._backend() == "vibemol":
            self._webview.load_molden(self._current_molden)
        else:
            self._open_in_jmol(auto=True)

    def reload(self) -> None:
        if self._backend() == "vibemol":
            self._webview.reload()

    def _backend(self) -> str:
        return str(self._viewer_selector.currentData())

    def _on_backend_changed(self) -> None:
        backend = self._backend()
        cfg.set_value("viewer_backend", backend)
        self._refresh_backend_ui(launch=True)

    def _refresh_backend_ui(self, launch: bool) -> None:
        backend = self._backend()
        using_jmol = backend == "jmol"
        self._stack.setCurrentIndex(1 if using_jmol else 0)
        self._install_btn.setVisible(using_jmol and not jmol.is_jmol_installed())
        self._open_jmol_btn.setVisible(using_jmol)
        self._open_jmol_btn.setEnabled(using_jmol and jmol.is_jmol_installed())
        if using_jmol:
            if jmol.is_jmol_installed():
                self._status.setText(f"Jmol installed: {jmol.jmol_jar_path()}")
                if launch:
                    self._open_in_jmol(auto=True)
            else:
                self._status.setText(f"Jmol is not installed for {jmol.desktop_label()}.")
        else:
            self._status.setText("Using embedded VibeMol.")
            if self._current_molden is not None:
                self._webview.load_molden(self._current_molden)

    def _on_install_jmol(self) -> None:
        if self._install_worker is not None and self._install_worker.isRunning():
            return
        self._launch_after_install = self._current_molden is not None
        self._install_btn.setEnabled(False)
        self._open_jmol_btn.setEnabled(False)
        self._status.setText("Installing Jmol...")
        worker = _JmolInstallWorker(self)
        worker.line.connect(self._on_install_line)
        worker.done.connect(self._on_install_done)
        self._install_worker = worker
        worker.start()

    def _on_install_line(self, line: str) -> None:
        self._status.setText(line)

    def _on_install_done(self, ok: bool, message: str) -> None:
        self._install_btn.setEnabled(True)
        self._install_worker = None
        if ok:
            self._status.setText(f"Jmol installed: {message}")
            self._refresh_backend_ui(launch=self._launch_after_install)
        else:
            self._status.setText(f"Jmol install failed: {message}")
        self._launch_after_install = False

    def _open_in_jmol(self, auto: bool) -> None:
        if self._current_molden is None:
            if not auto:
                self._status.setText("No Molden file is selected yet.")
            return
        if not jmol.is_jmol_installed():
            self._status.setText("Jmol is not installed yet. Click Install Jmol.")
            self.molden_loaded.emit(False)
            return
        try:
            jmol.launch_jmol(self._current_molden)
        except Exception as exc:  # noqa: BLE001
            self._status.setText(f"Could not launch Jmol: {exc}")
            self.molden_loaded.emit(False)
            return
        self._status.setText(f"Opened in Jmol: {self._current_molden.name}")
        self.molden_loaded.emit(True)
