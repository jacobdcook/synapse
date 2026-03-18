import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QLabel, QSplitter, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt

log = logging.getLogger(__name__)

class PRReviewView(QDialog):
    def __init__(self, pr_data, parent=None):
        super().__init__(parent)
        self.pr_data = pr_data
        self.setWindowTitle(f"Review PR #{pr_data.get('number')}: {pr_data.get('title')}")
        self.resize(1000, 700)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info Header
        header = QLabel(f"<b>PR #{self.pr_data.get('number')}</b> by {self.pr_data.get('author')}")
        header.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        
        # File List (Left)
        self.file_list = QListWidget()
        self.file_list.setMaximumWidth(250)
        self.file_list.itemClicked.connect(self._on_file_selected)
        splitter.addWidget(self.file_list)

        # Diff View (Right)
        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setStyleSheet("font-family: 'Courier New'; background: #0d1117; color: #e6edf3;")
        splitter.addWidget(self.diff_view)

        layout.addWidget(splitter)

        # Actions
        buttons = QHBoxLayout()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        # Placeholder data
        self.file_list.addItem("README.md")
        self.file_list.addItem("main.py")
        self.file_list.addItem("core/git.py")

    def _on_file_selected(self, item):
        filename = item.text()
        # Mock diff for now
        self.diff_view.setPlainText(f"--- a/{filename}\n+++ b/{filename}\n@@ -1,5 +1,6 @@\n+ # Added by PR context\n  import os\n- import sys\n+ import subprocess\n")

    def apply_theme(self, theme):
        bg = theme.get("bg", "#0d1117")
        fg = theme.get("fg", "#e6edf3")
        self.setStyleSheet(f"background: {bg}; color: {fg};")
        self.diff_view.setStyleSheet(f"font-family: 'Courier New'; background: {bg}; color: {fg};")
