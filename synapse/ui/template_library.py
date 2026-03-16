import os
import json
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QMessageBox, QSplitter, QFrame, QScrollArea, QDialog
)
from PyQt5.QtCore import Qt, pyqtSignal

from ..utils.constants import TEMPLATE_DIR

log = logging.getLogger(__name__)

class TemplateLibrary(QWidget):
    template_applied = pyqtSignal(str) # Emits the template content

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("Prompt Templates")
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        layout.addWidget(title)

        self.splitter = QSplitter(Qt.Vertical)
        
        # Top: List
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.splitter.addWidget(self.list_widget)
        
        # Bottom: Preview/Edit
        self.preview_frame = QFrame()
        self.preview_frame.setStyleSheet("background: #161b22; border: 1px solid #30363d; border-radius: 6px;")
        preview_layout = QVBoxLayout(self.preview_frame)
        
        self.template_name = QLineEdit()
        self.template_name.setPlaceholderText("Template Name")
        self.template_name.setStyleSheet("background: #0d1117; border: 1px solid #30363d; color: #e6edf3;")
        preview_layout.addWidget(self.template_name)
        
        self.template_content = QTextEdit()
        self.template_content.setPlaceholderText("Template Content...")
        self.template_content.setStyleSheet("background: #0d1117; border: 1px solid #30363d; color: #e6edf3; font-family: 'JetBrains Mono', monospace;")
        preview_layout.addWidget(self.template_content)
        
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_template)
        btn_row.addWidget(self.save_btn)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setStyleSheet("color: #f85149;")
        self.delete_btn.clicked.connect(self._delete_template)
        btn_row.addWidget(self.delete_btn)
        
        btn_row.addStretch()
        
        self.apply_btn = QPushButton("Apply to Chat")
        self.apply_btn.setStyleSheet("background-color: #238636; color: white; border: none; padding: 5px 15px;")
        self.apply_btn.clicked.connect(self._apply_template)
        btn_row.addWidget(self.apply_btn)
        
        preview_layout.addLayout(btn_row)
        self.splitter.addWidget(self.preview_frame)
        
        layout.addWidget(self.splitter)

    def refresh(self):
        self.list_widget.clear()
        if not TEMPLATE_DIR.exists():
            return
            
        # Default templates if empty
        if not list(TEMPLATE_DIR.glob("*.json")):
            self._create_defaults()

        for f in TEMPLATE_DIR.glob("*.json"):
            name = f.stem.replace("_", " ").title()
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, str(f))
            self.list_widget.addItem(item)

    def _create_defaults(self):
        defaults = {
            "Code_Review": "Please review the following code for potential bugs, security issues, and performance improvements:\n\n```\nPASTE_CODE_HERE\n```",
            "Refactor": "Refactor the following code to be more readable and efficient while maintaining the same functionality:\n\n```\nPASTE_CODE_HERE\n```",
            "Unit_Test": "Write comprehensive unit tests for the following function/class using pytest:\n\n```\nPASTE_CODE_HERE\n```",
            "Explain_Complex_Logic": "Explain the following logic in simple terms, breaking down how it works step-by-step:\n\n```\nPASTE_CODE_HERE\n```"
        }
        for name, content in defaults.items():
            path = TEMPLATE_DIR / f"{name}.json"
            with open(path, 'w') as f:
                json.dump({"name": name, "content": content}, f, indent=4)

    def _on_item_clicked(self, item):
        path = item.data(Qt.UserRole)
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                self.template_name.setText(data.get("name", "").replace("_", " ").title())
                self.template_content.setText(data.get("content", ""))
        except Exception as e:
            log.error(f"Failed to load template: {e}")

    def _save_template(self):
        name = self.template_name.text().strip().replace(" ", "_")
        content = self.template_content.toPlainText().strip()
        if not name or not content:
            return
            
        path = TEMPLATE_DIR / f"{name}.json"
        try:
            with open(path, 'w') as f:
                json.dump({"name": name, "content": content}, f, indent=4)
            self.refresh()
            self.template_name.clear()
            self.template_content.clear()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save template: {e}")

    def _delete_template(self):
        item = self.list_widget.currentItem()
        if not item: return
        
        path = item.data(Qt.UserRole)
        if QMessageBox.question(self, "Delete", f"Delete template '{item.text()}'?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            try:
                os.remove(path)
                self.refresh()
                self.template_name.clear()
                self.template_content.clear()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def _apply_template(self):
        content = self.template_content.toPlainText().strip()
        if content:
            self.template_applied.emit(content)

    def apply_theme(self, theme):
        fg = theme.get("fg", "#e6edf3")
        input_bg = theme.get("input_bg", "#0d1117")
        border = theme.get("border", "#30363d")
        sidebar_bg = theme.get("sidebar_bg", "#1e1e1e")
        self.preview_frame.setStyleSheet(f"background: {sidebar_bg}; border: 1px solid {border}; border-radius: 6px;")
        self.template_name.setStyleSheet(f"background: {input_bg}; border: 1px solid {border}; color: {fg};")
        self.template_content.setStyleSheet(f"background: {input_bg}; border: 1px solid {border}; color: {fg}; font-family: 'JetBrains Mono', monospace;")
        self.list_widget.setStyleSheet(f"""
            QListWidget {{ background: {input_bg}; border: 1px solid {border}; color: {fg}; }}
            QListWidget::item {{ padding: 6px; }}
            QListWidget::item:selected {{ background: {sidebar_bg}; }}
        """)
