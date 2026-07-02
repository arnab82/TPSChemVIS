"""A scrolling, read-only log pane used by every "runs something in the
background" screen (molden generation, active-space build, CMF, export)."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit


class LogPane(QPlainTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(10000)  # cap memory use on very chatty Julia runs
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = self.font()
        font.setFamily("monospace")
        self.setFont(font)

    @pyqtSlot(str)
    def append_line(self, text: str) -> None:
        self.appendPlainText(text)
        self.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self) -> None:
        self.clear()
