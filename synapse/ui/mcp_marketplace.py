import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QScrollArea, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from ..core.mcp_registry import MCP_REGISTRY

log = logging.getLogger(__name__)

class MCPServerCard(QFrame):
    """A card representing an MCP server in the marketplace."""
    install_clicked = pyqtSignal(dict) # server_info
    
    def __init__(self, info, is_installed=False, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.info = info
        self.is_installed = is_installed
        
        self.setStyleSheet("""
            MCPServerCard {
                background: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 12px;
                margin-bottom: 8px;
            }
            MCPServerCard:hover {
                border-color: #555;
                background: #252525;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Header: Icon + Name
        header = QHBoxLayout()
        icon_label = QLabel(self._get_icon(info.get("icon", "package")))
        icon_label.setStyleSheet("font-size: 20px; color: #58a6ff;")
        header.addWidget(icon_label)
        
        name_label = QLabel(info.get("name", "Unknown"))
        name_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #e6edf3;")
        header.addWidget(name_label)
        header.addStretch()
        
        id_label = QLabel(f"v{info.get('id', '')}")
        id_label.setStyleSheet("color: #666; font-size: 10px;")
        header.addWidget(id_label)
        
        layout.addLayout(header)
        
        # Description
        desc = QLabel(info.get("description", ""))
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 11px; margin-top: 4px; border: none;")
        layout.addWidget(desc)
        
        # Actions
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 8, 0, 0)
        
        if info.get("env_required"):
            env_hint = QLabel(f"Requires: {', '.join(info['env_required'])}")
            env_hint.setStyleSheet("color: #d19a66; font-size: 9px; font-style: italic;")
            actions.addWidget(env_hint)
        
        actions.addStretch()
        
        self.btn = QPushButton("Installed" if is_installed else "Install")
        self.btn.setEnabled(not is_installed)
        self.btn.setCursor(Qt.PointingHandCursor)
        if not is_installed:
            self.btn.setStyleSheet("""
                QPushButton {
                    background: #2ea043; color: white; border: none; 
                    padding: 4px 12px; border-radius: 4px; font-size: 11px; font-weight: bold;
                }
                QPushButton:hover { background: #3fb950; }
            """)
        else:
            self.btn.setStyleSheet("""
                QPushButton {
                    background: #30363d; color: #8b949e; border: 1px solid #444; 
                    padding: 4px 12px; border-radius: 4px; font-size: 11px;
                }
            """)
        
        self.btn.clicked.connect(lambda: self.install_clicked.emit(self.info))
        actions.addWidget(self.btn)
        
        layout.addLayout(actions)

    def _get_icon(self, icon_name):
        icons = {
            "github": "",
            "database": "",
            "message": "",
            "folder": "",
            "globe": "",
            "file-directory": "",
            "brain": "🧠",
            "git-branch": "",
            "search": "",
            "star": "",
            "package": ""
        }
        return icons.get(icon_name, "")

class MCPMarketplacePanel(QWidget):
    """The main marketplace UI panel."""
    
    def __init__(self, mcp_manager, settings_data, parent=None):
        super().__init__(parent)
        self.mcp_manager = mcp_manager
        self.settings_data = settings_data
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setStyleSheet("background: #161b22; border-bottom: 1px solid #30363d;")
        h_layout = QVBoxLayout(header)
        h_layout.setContentsMargins(12, 12, 12, 12)
        
        title = QLabel("MCP Marketplace")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #e6edf3;")
        h_layout.addWidget(title)
        
        subtitle = QLabel("Extend Synapse with community servers")
        subtitle.setStyleSheet("color: #8b949e; font-size: 11px;")
        h_layout.addWidget(subtitle)
        
        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search servers...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background: #0d1117; border: 1px solid #30363d; 
                border-radius: 4px; padding: 6px 10px; color: #e6edf3;
                margin-top: 8px;
            }
            QLineEdit:focus { border-color: #58a6ff; }
        """)
        self.search_input.textChanged.connect(self.refresh)
        h_layout.addWidget(self.search_input)
        
        self.layout.addWidget(header)
        
        # Scroll Area for Cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setAlignment(Qt.AlignTop)
        self.container_layout.setContentsMargins(8, 8, 8, 8)
        
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll)
        
        self.refresh()
        
    def refresh(self):
        """Clear and rebuild the list of cards."""
        # Clear container
        for i in reversed(range(self.container_layout.count())):
            self.container_layout.itemAt(i).widget().setParent(None)
            
        search_text = self.search_input.text().lower()
        installed_names = {s["name"] for s in self.settings_data.get("mcp_servers", [])}
        
        for info in MCP_REGISTRY:
            if search_text and search_text not in info["name"].lower() and search_text not in info["description"].lower():
                continue
                
            is_installed = info["name"] in installed_names
            card = MCPServerCard(info, is_installed)
            card.install_clicked.connect(self._on_install_clicked)
            self.container_layout.addWidget(card)

    def _on_install_clicked(self, info):
        """Handle install button click."""
        # Check if environment variables are needed
        required = info.get("env_required", [])
        env = {}
        
        if required:
            msg = f"This server requires the following environment variables:\n\n"
            msg += "\n".join([f"- {r}" for r in required])
            msg += "\n\nWould you like to add them now? (You can also add them later in Settings > Providers)"
            
            reply = QMessageBox.question(self, "Environment Setup", msg, QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                # For now, we point them to settings since we don't have a multi-input prompt here
                QMessageBox.information(self, "Manual Setup", "Please go to 'Settings > MCP' to configure this server with its required environment variables.")
                return

        # Add to settings
        mcp_servers = list(self.settings_data.get("mcp_servers", []))
        
        # Check if already exists (shouldn't happen with button state but just in case)
        if any(s["name"] == info["name"] for s in mcp_servers):
            return

        new_server = {
            "name": info["name"],
            "command": info["command"],
            "args": info["args"],
            "transport": "stdio",
            "enabled": True,
            "env": env
        }
        
        mcp_servers.append(new_server)
        self.settings_data["mcp_servers"] = mcp_servers
        
        # Notify manager
        self.mcp_manager.load_from_settings(self.settings_data)
        
        # Force save settings
        from ..utils.constants import save_settings
        save_settings(self.settings_data)
        
        QMessageBox.information(self, "Installed", f"Successfully installed {info['name']} MCP server.")
        self.refresh()
