from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QLineEdit, QHeaderView, QPushButton
)
from PyQt5.QtCore import Qt


SHORTCUT_DESCRIPTIONS = {
    "new_chat": "New Chat",
    "toggle_sidebar": "Toggle Sidebar",
    "save_file": "Save File",
    "rollback": "Undo Last Edit",
    "command_palette": "Command Palette",
    "focus_input": "Focus Input",
    "close_tab": "Close Tab",
    "next_tab": "Next Tab",
    "prev_tab": "Previous Tab",
    "new_window": "New Window",
    "global_search": "Global Search",
    "settings": "Settings",
    "import_conv": "Import Conversation",
    "zoom_in": "Zoom In",
    "zoom_out": "Zoom Out",
    "zoom_reset": "Zoom Reset",
    "paste_image": "Paste Image",
    "toggle_terminal": "Toggle Terminal",
    "search_replace": "Search & Replace",
    "screenshot": "Take Screenshot",
    "zen_mode": "Zen Mode",
    "global_summon": "Summon Synapse (Global)",
}


class ShortcutsDialog(QDialog):
    def __init__(self, shortcuts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(500, 550)
        self._shortcuts = shortcuts

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search shortcuts...")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        layout.addWidget(self.search)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Action", "Shortcut"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self._populate()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def _populate(self, filter_text=""):
        self.table.setRowCount(0)
        ft = filter_text.lower()
        for action_id, key in self._shortcuts.items():
            if not key:
                continue
            desc = SHORTCUT_DESCRIPTIONS.get(action_id, action_id.replace("_", " ").title())
            if ft and ft not in desc.lower() and ft not in key.lower():
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(desc))
            key_item = QTableWidgetItem(key)
            key_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, key_item)

    def _filter(self, text):
        self._populate(text)

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        input_bg = theme.get("input_bg", "#0d1117")
        fg = theme.get("fg", "#e6edf3")
        border = theme.get("border", "#30363d")
        self.setStyleSheet(f"""
            QDialog {{ background: {bg}; color: {fg}; }}
            QTableWidget {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; gridline-color: {border}; }}
            QTableWidget::item {{ padding: 4px; }}
            QHeaderView::section {{ background: {bg}; color: {fg}; border: 1px solid {border}; padding: 4px; }}
            QLineEdit {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; border-radius: 4px; padding: 6px; }}
            QPushButton {{ background: {border}; color: {fg}; border: none; padding: 6px 16px; border-radius: 4px; }}
            QPushButton:hover {{ background: {input_bg}; }}
            QLabel {{ color: {fg}; }}
        """)
