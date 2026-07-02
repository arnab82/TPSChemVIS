from __future__ import annotations

from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """A titled section that collapses to its header when clicked.

    Usage::
        sec = CollapsibleSection("My section")
        body = QFormLayout()
        body.addRow(...)
        sec.set_body_layout(body)
    """

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self._title = title

        self._btn = QPushButton(f"▼  {title}")
        self._btn.setCheckable(True)
        self._btn.setChecked(True)
        self._btn.setFlat(True)
        self._btn.setStyleSheet(
            "QPushButton { text-align:left; font-weight:bold; padding:4px 8px; "
            "background:palette(button); border:1px solid palette(mid); border-radius:3px; }"
            "QPushButton:hover { background:palette(midlight); }"
        )
        self._btn.toggled.connect(self._on_toggled)

        self._body = QWidget()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addWidget(self._btn)
        layout.addWidget(self._body)

    def set_body_layout(self, body_layout) -> None:
        self._body.setLayout(body_layout)

    def _on_toggled(self, expanded: bool) -> None:
        self._body.setVisible(expanded)
        arrow = "▼" if expanded else "▶"
        self._btn.setText(f"{arrow}  {self._title}")
        if expanded:
            self.setMaximumHeight(16777215)
        else:
            self.setMaximumHeight(self._btn.sizeHint().height() + 6)
