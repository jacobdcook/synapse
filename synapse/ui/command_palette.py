import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence

log = logging.getLogger(__name__)


class CommandPalette(QDialog):
    command_selected = pyqtSignal(str)

    def __init__(self, commands, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Popup)
        self.setMinimumWidth(500)
        self.setMaximumHeight(400)
        self.commands = commands

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Type a command...")
        self.search.setStyleSheet(
            "padding: 8px; font-size: 14px; background: #1e1e1e; "
            "color: #e6edf3; border: 1px solid #30363d; border-radius: 6px;"
        )
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget { background: #161b22; border: 1px solid #30363d; "
            "color: #e6edf3; font-size: 13px; }"
            "QListWidget::item { padding: 6px 10px; }"
            "QListWidget::item:selected { background: #2f81f7; color: white; }"
        )
        self.list_widget.itemActivated.connect(self._on_activated)
        layout.addWidget(self.list_widget)

        self._populate(commands)
        self.search.setFocus()

    def _populate(self, commands):
        self.list_widget.clear()
        for cmd in commands:
            label = cmd.get("label", "")
            shortcut = cmd.get("shortcut", "")
            display = f"{label}    {shortcut}" if shortcut else label
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, cmd.get("id", ""))
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _filter(self, text):
        text = text.lower()
        filtered = [c for c in self.commands if text in c.get("label", "").lower()]
        self._populate(filtered)

    def _on_activated(self, item):
        cmd_id = item.data(Qt.UserRole)
        if cmd_id:
            self.command_selected.emit(cmd_id)
            self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.reject()
        elif event.key() in (Qt.Key_Down, Qt.Key_Up):
            self.list_widget.setFocus()
            self.list_widget.keyPressEvent(event)
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            current = self.list_widget.currentItem()
            if current:
                self._on_activated(current)
        else:
            super().keyPressEvent(event)

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        fg = theme.get("fg", "#e6edf3")
        input_bg = theme.get("input_bg", "#0d1117")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#58a6ff")
        header_bg = theme.get("header_bg", "#161b22")

        self.search.setStyleSheet(
            f"padding: 8px; font-size: 14px; background: {input_bg}; "
            f"color: {fg}; border: 1px solid {border}; border-radius: 6px;"
        )
        self.list_widget.setStyleSheet(
            f"QListWidget {{ background: {header_bg}; border: 1px solid {border}; "
            f"color: {fg}; font-size: 13px; }}"
            f"QListWidget::item {{ padding: 6px 10px; }}"
            f"QListWidget::item:selected {{ background: {accent}; color: white; }}"
        )
