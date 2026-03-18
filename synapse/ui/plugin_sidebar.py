import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QTabWidget, QScrollArea, QFrame, QLineEdit,
    QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal

log = logging.getLogger(__name__)

class PluginItemWidget(QWidget):
    """Custom widget for a plugin entry in the list."""
    status_changed = pyqtSignal(str, bool) # id, enabled
    uninstall_requested = pyqtSignal(str) # id

    def __init__(self, plugin_info, parent=None):
        super().__init__(parent)
        self.plugin_id = plugin_info["id"]
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        header = QHBoxLayout()
        self.name_label = QLabel(plugin_info["name"])
        self.name_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(self.name_label)
        header.addStretch()
        
        self.enable_check = QCheckBox()
        self.enable_check.setChecked(plugin_info.get("enabled", True))
        self.enable_check.toggled.connect(self._on_toggled)
        header.addWidget(self.enable_check)
        layout.addLayout(header)
        
        self.desc_label = QLabel(plugin_info.get("description", ""))
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self.desc_label)
        
        footer = QHBoxLayout()
        self.uninstall_btn = QPushButton("Uninstall")
        self.uninstall_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #f85149; font-size: 10px; border: none; }
            QPushButton:hover { text-decoration: underline; }
        """)
        self.uninstall_btn.clicked.connect(lambda: self.uninstall_requested.emit(self.plugin_id))
        footer.addStretch()
        footer.addWidget(self.uninstall_btn)
        layout.addLayout(footer)
        
        # Add separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #30363d;")
        layout.addWidget(line)

    def _on_toggled(self, checked):
        self.status_changed.emit(self.plugin_id, checked)

class PluginSidebar(QWidget):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = QLabel("EXTENSIONS")
        title.setStyleSheet("font-weight: bold; font-size: 11px; color: #8b949e; margin: 10px;")
        layout.addWidget(title)
        
        # Search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search extensions...")
        self.search_edit.setStyleSheet("""
            QLineEdit { background: #0d1117; border: 1px solid #30363d; border-radius: 4px; padding: 5px; margin: 0 10px 10px 10px; color: #e6edf3; }
        """)
        layout.addWidget(self.search_edit)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: none; }
            QTabBar::tab { background: transparent; color: #8b949e; padding: 10px; min-width: 80px; }
            QTabBar::tab:selected { color: #58a6ff; border-bottom: 2px solid #58a6ff; }
        """)
        
        self.installed_list = QListWidget()
        self.installed_list.setStyleSheet("background: transparent; border: none;")
        self.tabs.addTab(self.installed_list, "Installed")
        
        self.marketplace_list = QListWidget()
        self.marketplace_list.setStyleSheet("background: transparent; border: none;")
        self.tabs.addTab(self.marketplace_list, "Marketplace")
        
        layout.addWidget(self.tabs)
        
        self._refresh_installed()
        self._load_mock_marketplace()

    def _refresh_installed(self):
        self.installed_list.clear()
        plugins = self.plugin_manager.get_available_plugins()
        for p in plugins:
            item = QListWidgetItem(self.installed_list)
            widget = PluginItemWidget(p)
            widget.status_changed.connect(self._on_plugin_status_changed)
            widget.uninstall_requested.connect(self._on_uninstall_requested)
            item.setSizeHint(widget.sizeHint())
            self.installed_list.setItemWidget(item, widget)

    def _load_mock_marketplace(self):
        self.marketplace_list.clear()
        mock_plugins = [
            {"id": "theme_pack", "name": "Modern Theme Pack", "description": "10+ premium themes for Synapse.", "author": "Synapse Team"},
            {"id": "rust_analyzer", "name": "Rust Support", "description": "Full Rust language support via rust-analyzer.", "author": "Ferrous Systems"},
            {"id": "git_lens", "name": "GitLens Mini", "description": "Visual git commit history in the editor.", "author": "Synapse Commits"}
        ]
        
        for p in mock_plugins:
            item = QListWidgetItem(self.marketplace_list)
            widget = QWidget()
            w_layout = QVBoxLayout(widget)
            w_layout.addWidget(QLabel(f"<b>{p['name']}</b>"))
            w_layout.addWidget(QLabel(p['description']))
            install_btn = QPushButton("Install")
            install_btn.setStyleSheet("background: #238636; color: white; border-radius: 3px; padding: 3px;")
            w_layout.addWidget(install_btn)
            item.setSizeHint(widget.sizeHint())
            self.marketplace_list.setItemWidget(item, widget)

    def _on_plugin_status_changed(self, plugin_id, enabled):
        if enabled:
            self.plugin_manager.enable_plugin(plugin_id)
        else:
            self.plugin_manager.disable_plugin(plugin_id)
        log.info(f"Plugin {plugin_id} {'enabled' if enabled else 'disabled'}")

    def _on_uninstall_requested(self, plugin_id):
        self.plugin_manager.uninstall_plugin(plugin_id)
        self._refresh_installed()
