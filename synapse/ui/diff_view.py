import difflib
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLabel,
    QFrame, QSplitter, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QTextCharFormat, QFont

class DiffViewDialog(QDialog):
    def __init__(self, parent, filename, old_content, new_content):
        super().__init__(parent)
        self.setWindowTitle(f"Propose Change: {filename}")
        self.setMinimumSize(1000, 700)
        self.accepted_change = False
        
        layout = QVBoxLayout(self)
        
        header = QLabel(f"Review changes for <b>{filename}</b>")
        header.setStyleSheet("font-size: 14px; margin-bottom: 8px;")
        layout.addWidget(header)
        
        self.splitter = QSplitter(Qt.Horizontal)
        
        old_container = QWidget()
        old_layout = QVBoxLayout(old_container)
        old_layout.addWidget(QLabel("CURRENT VERSION"))
        self.old_editor = QTextEdit()
        self.old_editor.setReadOnly(True)
        self.old_editor.setFont(QFont("JetBrains Mono", 10))
        self.old_editor.setStyleSheet("background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d;")
        old_layout.addWidget(self.old_editor)
        
        new_container = QWidget()
        new_layout = QVBoxLayout(new_container)
        new_layout.addWidget(QLabel("PROPOSED CHANGES"))
        self.new_editor = QTextEdit()
        self.new_editor.setReadOnly(True)
        self.new_editor.setFont(QFont("JetBrains Mono", 10))
        self.new_editor.setStyleSheet("background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d;")
        new_layout.addWidget(self.new_editor)
        
        self.splitter.addWidget(old_container)
        self.splitter.addWidget(new_container)
        layout.addWidget(self.splitter)
        
        self._generate_diff(old_content, new_content)
        
        buttons = QHBoxLayout()
        self.cancel_btn = QPushButton("Reject")
        self.cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_btn)
        
        buttons.addStretch()
        
        self.apply_btn = QPushButton("Accept and Apply")
        self.apply_btn.setStyleSheet("background-color: #2ea043; color: white; padding: 8px 20px; font-weight: bold;")
        self.apply_btn.clicked.connect(self._accept_and_apply)
        buttons.addWidget(self.apply_btn)
        
        layout.addLayout(buttons)

    def _generate_diff(self, old_text, new_text):
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        
        # Simple side-by-side highlighter logic
        # For a professional look, we should use a more advanced diff renderer,
        # but for now, we'll use difflib and basic highlighting.
        
        d = difflib.Differ()
        diff = list(d.compare(old_lines, new_lines))
        
        old_fmt = QTextCharFormat()
        new_fmt = QTextCharFormat()
        
        added_color = QColor("#1e3a1e") # Deep Forest Green
        removed_color = QColor("#3a1e1e") # Deep Maroon
        
        for line in diff:
            if line.startswith('  '): # Unchanged
                self.old_editor.append(line[2:])
                self.new_editor.append(line[2:])
            elif line.startswith('- '): # Removed
                cursor = self.old_editor.textCursor()
                fmt = QTextCharFormat()
                fmt.setBackground(removed_color)
                cursor.insertText(line[2:] + "\n", fmt)
            elif line.startswith('+ '): # Added
                cursor = self.new_editor.textCursor()
                fmt = QTextCharFormat()
                fmt.setBackground(added_color)
                cursor.insertText(line[2:] + "\n", fmt)
            elif line.startswith('? '): # Intraline info (skip for now)
                continue

    def _accept_and_apply(self):
        self.accepted_change = True
        self.accept()

    def apply_theme(self, theme):
        input_bg = theme.get("input_bg", "#0d1117")
        fg = theme.get("fg", "#c9d1d9")
        border = theme.get("border", "#30363d")
        self.old_editor.setStyleSheet(f"background-color: {input_bg}; color: {fg}; border: 1px solid {border};")
        self.new_editor.setStyleSheet(f"background-color: {input_bg}; color: {fg}; border: 1px solid {border};")
