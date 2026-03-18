import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QTabWidget, QScrollArea, QFrame, QLineEdit,
    QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal

log = logging.getLogger(__name__)

MARKETPLACE_EXTENSIONS = [
    {"id": "theme_pack", "name": "Modern Theme Pack", "description": "10+ premium themes including Nord, Dracula, and Catppuccin.", "author": "Synapse Team", "category": "Themes"},
    {"id": "rust_analyzer", "name": "Rust Support", "description": "Full Rust language support via rust-analyzer.", "author": "Ferrous Systems", "category": "Languages"},
    {"id": "git_lens", "name": "GitLens Mini", "description": "Visual git commit history and blame annotations in the editor.", "author": "Synapse Community", "category": "Git"},
    {"id": "python_ext", "name": "Python Tools", "description": "Black formatter, isort, mypy type checker integration.", "author": "Synapse Team", "category": "Languages"},
    {"id": "go_support", "name": "Go Support", "description": "gopls integration with auto-imports and test runner.", "author": "Synapse Community", "category": "Languages"},
    {"id": "cpp_support", "name": "C/C++ Support", "description": "clangd integration for completions, diagnostics, and formatting.", "author": "Synapse Community", "category": "Languages"},
    {"id": "java_support", "name": "Java Support", "description": "Eclipse JDT language server for Java projects.", "author": "Synapse Community", "category": "Languages"},
    {"id": "docker_compose", "name": "Docker Compose Helper", "description": "Autocomplete and validation for docker-compose.yml files.", "author": "Synapse Community", "category": "DevOps"},
    {"id": "kubernetes", "name": "Kubernetes Tools", "description": "kubectl integration, manifest validation, and cluster explorer.", "author": "Synapse Community", "category": "DevOps"},
    {"id": "terraform", "name": "Terraform Support", "description": "HCL syntax highlighting, plan preview, and state explorer.", "author": "Synapse Community", "category": "DevOps"},
    {"id": "prettier", "name": "Prettier Formatter", "description": "Auto-format JS, TS, CSS, HTML, JSON, and Markdown on save.", "author": "Synapse Community", "category": "Formatters"},
    {"id": "eslint_ext", "name": "ESLint Integration", "description": "Real-time JavaScript/TypeScript linting in the editor.", "author": "Synapse Community", "category": "Linters"},
    {"id": "ruff_ext", "name": "Ruff Linter", "description": "Ultra-fast Python linter and formatter (replaces flake8 + black).", "author": "Synapse Community", "category": "Linters"},
    {"id": "markdown_preview", "name": "Markdown Preview Enhanced", "description": "Live preview with Mermaid, KaTeX, and PlantUML support.", "author": "Synapse Team", "category": "Editors"},
    {"id": "csv_editor", "name": "CSV/TSV Editor", "description": "Spreadsheet-style editor for CSV and TSV files.", "author": "Synapse Community", "category": "Editors"},
    {"id": "svg_preview", "name": "SVG Preview", "description": "Live SVG rendering and editing with zoom controls.", "author": "Synapse Community", "category": "Editors"},
    {"id": "rest_client", "name": "REST Client", "description": "Send HTTP requests and view responses directly in Synapse.", "author": "Synapse Community", "category": "Tools"},
    {"id": "db_explorer", "name": "Database Explorer", "description": "Browse SQLite, PostgreSQL, and MySQL databases with query editor.", "author": "Synapse Community", "category": "Tools"},
    {"id": "ssh_remote", "name": "SSH Remote", "description": "Edit files on remote servers over SSH.", "author": "Synapse Community", "category": "Tools"},
    {"id": "copilot_bridge", "name": "AI Copilot Bridge", "description": "Use GitHub Copilot alongside Synapse's built-in AI.", "author": "Synapse Community", "category": "AI"},
    {"id": "ollama_models", "name": "Ollama Model Browser", "description": "Browse, pull, and manage Ollama models from the sidebar.", "author": "Synapse Team", "category": "AI"},
    {"id": "code_snippets", "name": "Code Snippets Manager", "description": "Save, organize, and insert code snippets with variables.", "author": "Synapse Community", "category": "Productivity"},
    {"id": "todo_highlight", "name": "TODO Highlighter", "description": "Highlight TODO, FIXME, HACK comments across your codebase.", "author": "Synapse Community", "category": "Productivity"},
    {"id": "color_picker", "name": "Color Picker", "description": "Inline color preview and picker for CSS/HTML color values.", "author": "Synapse Community", "category": "Editors"},
    {"id": "diff_folders", "name": "Folder Diff", "description": "Compare two directories side by side with merge support.", "author": "Synapse Community", "category": "Tools"},
    {"id": "vim_mode", "name": "Vim Keybindings", "description": "Full Vim emulation for the code editor.", "author": "Synapse Community", "category": "Editors"},
    {"id": "emmet_ext", "name": "Emmet Support", "description": "Expand Emmet abbreviations in HTML and CSS files.", "author": "Synapse Community", "category": "Editors"},
    {"id": "tailwind_ext", "name": "Tailwind CSS IntelliSense", "description": "Autocomplete, linting, and hover preview for Tailwind classes.", "author": "Synapse Community", "category": "Languages"},
]


class PluginItemWidget(QWidget):
    status_changed = pyqtSignal(str, bool)
    uninstall_requested = pyqtSignal(str)

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
        self.desc_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.desc_label)

        footer = QHBoxLayout()
        self.uninstall_btn = QPushButton("Uninstall")
        self.uninstall_btn.setStyleSheet(
            "QPushButton { background: transparent; font-size: 10px; border: none; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self.uninstall_btn.clicked.connect(lambda: self.uninstall_requested.emit(self.plugin_id))
        footer.addStretch()
        footer.addWidget(self.uninstall_btn)
        layout.addLayout(footer)

        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(self.separator)

    def _on_toggled(self, checked):
        self.status_changed.emit(self.plugin_id, checked)


class PluginSidebar(QWidget):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self._all_marketplace = MARKETPLACE_EXTENSIONS

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("EXTENSIONS")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 11px; margin: 10px;")
        layout.addWidget(self.title_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search extensions...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit)

        self.tabs = QTabWidget()

        self.installed_list = QListWidget()
        self.installed_list.setStyleSheet("background: transparent; border: none;")
        self.tabs.addTab(self.installed_list, "Installed")

        self.marketplace_list = QListWidget()
        self.marketplace_list.setStyleSheet("background: transparent; border: none;")
        self.tabs.addTab(self.marketplace_list, "Marketplace")

        layout.addWidget(self.tabs)

        self.banner_label = QLabel("Community extensions coming soon. Stay tuned!")
        self.banner_label.setAlignment(Qt.AlignCenter)
        self.banner_label.setWordWrap(True)
        self.banner_label.setStyleSheet("font-size: 10px; padding: 6px;")
        layout.addWidget(self.banner_label)

        self._refresh_installed()
        self._load_marketplace()

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

    def _load_marketplace(self, filter_text=""):
        self.marketplace_list.clear()
        query = filter_text.lower().strip()
        for p in self._all_marketplace:
            if query and query not in p["name"].lower() and query not in p.get("description", "").lower() and query not in p.get("category", "").lower():
                continue
            item = QListWidgetItem(self.marketplace_list)
            widget = QWidget()
            w_layout = QVBoxLayout(widget)
            w_layout.setContentsMargins(10, 5, 10, 5)
            name_lbl = QLabel(f"<b>{p['name']}</b>")
            w_layout.addWidget(name_lbl)
            cat_lbl = QLabel(p.get("category", ""))
            cat_lbl.setStyleSheet("font-size: 10px;")
            w_layout.addWidget(cat_lbl)
            desc_lbl = QLabel(p["description"])
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("font-size: 11px;")
            w_layout.addWidget(desc_lbl)
            install_btn = QPushButton("Install")
            install_btn.setFixedWidth(80)
            w_layout.addWidget(install_btn)
            item.setSizeHint(widget.sizeHint())
            self.marketplace_list.setItemWidget(item, widget)

    def _on_search_changed(self, text):
        if self.tabs.currentIndex() == 1:
            self._load_marketplace(text)

    def _on_plugin_status_changed(self, plugin_id, enabled):
        if enabled:
            self.plugin_manager.enable_plugin(plugin_id)
        else:
            self.plugin_manager.disable_plugin(plugin_id)
        log.info(f"Plugin {plugin_id} {'enabled' if enabled else 'disabled'}")

    def _on_uninstall_requested(self, plugin_id):
        self.plugin_manager.uninstall_plugin(plugin_id)
        self._refresh_installed()

    def apply_theme(self, theme):
        bg = theme.get("sidebar_bg", "#1e1e1e")
        fg = theme.get("fg", "#e6edf3")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#58a6ff")
        input_bg = theme.get("input_bg", "#1e1e1e")
        muted = theme.get("fg", "#8b949e")
        self.setStyleSheet(f"background-color: {bg};")
        self.title_label.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {muted}; margin: 10px;")
        self.search_edit.setStyleSheet(
            f"QLineEdit {{ background: {input_bg}; border: 1px solid {border}; border-radius: 4px; padding: 5px; margin: 0 10px 10px 10px; color: {fg}; }}"
        )
        self.tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: {bg}; }}"
            f"QTabBar::tab {{ background: transparent; color: {muted}; padding: 10px; min-width: 80px; }}"
            f"QTabBar::tab:selected {{ color: {accent}; border-bottom: 2px solid {accent}; }}"
        )
        self.installed_list.setStyleSheet(f"background: transparent; border: none; color: {fg};")
        self.marketplace_list.setStyleSheet(f"background: transparent; border: none; color: {fg};")
        self.banner_label.setStyleSheet(f"font-size: 10px; padding: 6px; color: {muted};")
