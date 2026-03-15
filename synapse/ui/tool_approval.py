from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextEdit
from PyQt5.QtCore import Qt

class ToolApprovalDialog(QDialog):
    def __init__(self, parent, tool_name, arguments):
        super().__init__(parent)
        self.setWindowTitle("Tool Execution Request")
        self.setMinimumWidth(500)
        
        layout = QVBoxLayout(self)
        
        self.label = QLabel(f"The assistant wants to run the following tool:")
        self.label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.label)
        
        self.tool_info = QLabel(f"Tool: <b>{tool_name}</b>")
        layout.addWidget(self.tool_info)

        # Show MCP source if applicable
        if tool_name.startswith("mcp__"):
            parts = tool_name.split("__")
            if len(parts) >= 2:
                server_name = parts[1]
                source_label = QLabel(f"Source: MCP Server \"{server_name}\"")
                source_label.setStyleSheet("color: #58a6ff; font-size: 11px; background: rgba(88,166,255,0.08); padding: 4px 8px; border-radius: 4px;")
                layout.addWidget(source_label)

        layout.addWidget(QLabel("Arguments:"))
        self.args_view = QTextEdit()
        import json
        self.args_view.setPlainText(json.dumps(arguments, indent=2))
        self.args_view.setReadOnly(True)
        layout.addWidget(self.args_view)
        
        warning = QLabel("Warning: Execution can modify files or run terminal commands.")
        warning.setStyleSheet("color: #ff9800; font-size: 11px;")
        layout.addWidget(warning)
        
        buttons = QHBoxLayout()
        self.reject_btn = QPushButton("Reject")
        self.reject_btn.clicked.connect(self.reject)
        buttons.addWidget(self.reject_btn)
        
        buttons.addStretch()
        
        self.approve_btn = QPushButton("Approve")
        self.approve_btn.setStyleSheet("background-color: #2ea043; color: white; font-weight: bold;")
        self.approve_btn.clicked.connect(self.accept)
        buttons.addWidget(self.approve_btn)
        
        layout.addLayout(buttons)
