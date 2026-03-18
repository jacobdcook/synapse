from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QListWidgetItem, QMessageBox, QDialog,
    QLineEdit, QTextEdit, QComboBox, QFormLayout, QCheckBox,
    QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from ..core.agent_manager import AgentManager, AgentDefinition

class AgentEditorDialog(QDialog):
    def __init__(self, parent=None, agent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Agent" if agent else "Create Agent")
        self.setMinimumWidth(500)
        self.agent = agent
        self.result_agent = None
        
        self._setup_ui()
        if agent:
            self._load_agent(agent)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Bug Bounty Hunter")
        form.addRow("Name:", self.name_edit)
        
        self.icon_combo = QComboBox()
        self.icon_combo.addItems(["robot", "code", "edit", "shield", "search", "terminal"])
        form.addRow("Icon Icon:", self.icon_combo)
        
        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setPlaceholderText("Define the agent's personality and goals...")
        self.system_prompt_edit.setMinimumHeight(200)
        form.addRow("System Prompt:", self.system_prompt_edit)
        
        layout.addLayout(form)
        
        # Tools Selection (Simple for now)
        layout.addWidget(QLabel("<b>Tools Policy</b>"))
        self.allow_all_tools = QCheckBox("Allow all available tools")
        self.allow_all_tools.setChecked(True)
        layout.addWidget(self.allow_all_tools)
        
        buttons = QHBoxLayout()
        save_btn = QPushButton("Save Agent")
        save_btn.clicked.connect(self.accept)
        save_btn.setStyleSheet("background-color: #007acc; color: white;")
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addStretch()
        buttons.addWidget(cancel_btn)
        buttons.addWidget(save_btn)
        layout.addLayout(buttons)

    def _load_agent(self, agent):
        self.name_edit.setText(agent.name)
        self.icon_combo.setCurrentText(agent.icon)
        self.system_prompt_edit.setText(agent.system_prompt)

    def get_agent_data(self):
        return {
            "name": self.name_edit.text(),
            "system_prompt": self.system_prompt_edit.toPlainText(),
            "icon": self.icon_combo.currentText(),
            "tools": [] if self.allow_all_tools.isChecked() else [] # Logic to be expanded
        }

class AgentForgeSidebar(QWidget):
    agent_selected = pyqtSignal(str) # agent_id
    
    def __init__(self, agent_manager, parent=None):
        super().__init__(parent)
        self.manager = agent_manager
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        
        header = QHBoxLayout()
        title = QLabel("AGENT FORGE")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #858585;")
        header.addWidget(title)
        
        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setToolTip("Create New Agent")
        add_btn.clicked.connect(self._on_add_agent)
        header.addWidget(add_btn)
        layout.addLayout(header)
        
        self.agent_list = QListWidget()
        self.agent_list.setSpacing(4)
        self.agent_list.setStyleSheet("""
            QListWidget { background: transparent; border: none; }
            QListWidget::item { background: #2d2d2d; border-radius: 4px; padding: 8px; margin-bottom: 2px; }
            QListWidget::item:selected { background: #37373d; border: 1px solid #007acc; }
        """)
        self.agent_list.itemClicked.connect(self._on_item_clicked)
        self.agent_list.itemDoubleClicked.connect(self._on_edit_agent)
        layout.addWidget(self.agent_list)
        
        info = QLabel("Click to hire. Double-click to edit.")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info)

    def _on_item_clicked(self, item):
        agent_id = item.data(Qt.UserRole)
        self.agent_selected.emit(agent_id)

    def refresh(self):
        self.agent_list.clear()
        for agent in self.manager.list_agents():
            item = QListWidgetItem(f"{agent.name}")
            item.setData(Qt.UserRole, agent.id)
            item.setToolTip(agent.system_prompt[:100] + "...")
            self.agent_list.addItem(item)

    def _on_add_agent(self):
        dialog = AgentEditorDialog(self)
        if dialog.exec_():
            data = dialog.get_agent_data()
            if not data["name"]:
                return
            new_agent = AgentDefinition.from_dict(data)
            self.manager.add_agent(new_agent)
            self.refresh()

    def _on_edit_agent(self, item):
        agent_id = item.data(Qt.UserRole)
        agent = self.manager.get_agent(agent_id)
        if agent:
            dialog = AgentEditorDialog(self, agent)
            if dialog.exec_():
                data = dialog.get_agent_data()
                updated = AgentDefinition.from_dict(data)
                self.manager.add_agent(updated)
                self.refresh()

    def apply_theme(self, theme):
        bg = theme.get("sidebar_bg", "#21252b")
        fg = theme.get("fg", "#abb2bf")
        accent = theme.get("accent", "#61afef")
        border = theme.get("border", "#181a1f")
        input_bg = theme.get("input_bg", "#21252b")
        self.setStyleSheet(f"background-color: {bg};")
        for lbl in self.findChildren(QLabel):
            lbl.setStyleSheet(f"color: {fg};")
        self.agent_list.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none; color: {fg}; }}
            QListWidget::item {{ background: {input_bg}; border-radius: 4px; padding: 8px; margin-bottom: 2px; color: {fg}; }}
            QListWidget::item:selected {{ background: {bg}; border: 1px solid {accent}; color: {fg}; }}
        """)
