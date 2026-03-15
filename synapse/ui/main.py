import sys
import os
import json
import time
import logging
import re
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Tuple

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStackedWidget, QComboBox, QLabel, QProgressBar,
    QMessageBox, QFileDialog, QInputDialog, QPlainTextEdit, QShortcut,
    QSystemTrayIcon, QMenu, QAction, QDialog, QTabWidget, QPushButton
)
from PyQt5.QtCore import Qt, QTimer, QSettings, pyqtSignal
from PyQt5.QtGui import QIcon, QKeySequence

from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

from ..utils.constants import (
    APP_NAME, DEFAULT_MODEL, DEFAULT_SYSTEM_PROMPT, DEFAULT_GEN_PARAMS,
    DEFAULT_OLLAMA_URL, DARK_THEME_QSS, DRAFT_FILE,
    load_settings, save_settings, set_ollama_url, estimate_tokens
)
from ..core.api import (
    OllamaWorker, ModelLoader, TitleWorker, unload_model, unload_all_models, ConnectionChecker
)
from ..core.store import ConversationStore, new_conversation
from ..core.renderer import ChatRenderer
from .sidebar import SidebarWidget
from .input import InputWidget
from .workspace import WorkspacePanel, EditorTabs
from .activity_bar import ActivityBar
from .diff_view import DiffViewDialog
from ..core.indexer import WorkspaceIndexer, search_index
from ..core.agent import ToolExecutor
from .tool_approval import ToolApprovalDialog
from .model_manager import ModelManagerPanel
from .system_prompt import SystemPromptDialog
from .command_palette import CommandPalette
from .settings_dialog import SettingsDialog
from .compare_dialog import CompareDialog
from ..core.plugins import PluginManager
from ..core.mcp import MCPClientManager
from ..core.git import GitStatusWorker, is_git_repo
from .terminal import TerminalWidget
from .git_panel import GitPanel
from .workspace_search import WorkspaceSearchDialog
from ..utils.themes import THEMES

log = logging.getLogger(__name__)

class ChatPage(QWebEnginePage):
    action_requested = pyqtSignal(str, int)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        url_str = url.toString()
        if url_str.startswith("action://"):
            parts = url_str.replace("action://", "").split("/")
            action = parts[0] if parts else ""
            index = int(parts[1]) if len(parts) > 1 else -1
            self.action_requested.emit(action, index)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

class _MCPCallWorker:
    """Helper for executing MCP tools in a non-blocking way."""

    def __init__(self, mcp_manager, name, args):
        self.mcp_manager = mcp_manager
        self.name = name
        self.args = args
        self.result = None

    def execute(self):
        """Execute the MCP tool call."""
        self.result = self.mcp_manager.execute_tool(self.name, self.args)
        return self.result


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1200, 800)

        self.settings_data = load_settings()
        set_ollama_url(self.settings_data.get("ollama_url", DEFAULT_OLLAMA_URL))
        
        self.store = ConversationStore()
        self.renderer = ChatRenderer()
        self.current_conv = None
        self.worker = None
        self.indexer = None
        self.workspace_index = {}
        self.tool_executor = ToolExecutor()
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_all()
        self.mcp_manager = MCPClientManager()
        self.mcp_manager.load_from_settings(self.settings_data)
        self.mcp_manager.servers_changed.connect(self._update_mcp_status)
        self._tab_conversations = {}  # tab_index -> conv dict (preserves reference)
        self._edit_history = []  # stack of (Path, old_content) for multi-level undo
        self._streaming_text = ""
        self._streaming_dirty = False
        self._streaming_token_count = 0
        self._streaming_start_time = 0
        self._zoom = self.settings_data.get("zoom", 100)
        self._active_stream_conv = None
        self._active_stream_tab_index = -1
        self._last_requested_model = None

        self._tray_icon = None
        unload_all_models()
        self._setup_ui()
        self._setup_tray()
        self._setup_timers()
        self._setup_conn_checker()
        self._setup_shortcuts()
        self._load_models()
        self._restore_geometry()
        self._restore_workspace()
        
        # Open initial chat tab
        self._new_chat()
        self.sidebar.refresh()
        self._restore_draft()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Activity Bar
        self.activity_bar = ActivityBar()
        self.activity_bar.activity_changed.connect(self._on_activity_changed)
        self.activity_bar.settings_requested.connect(self._open_settings)
        main_layout.addWidget(self.activity_bar)

        # Sidebar Stack
        self.sidebar_container = QWidget()
        self.sidebar_container.setFixedWidth(280)
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.sidebar_stack = QStackedWidget()
        
        self.workspace_panel = WorkspacePanel()
        self.workspace_panel.file_selected.connect(self._on_file_selected)
        self.workspace_panel.workspace_changed.connect(self._on_workspace_changed)
        self.sidebar_stack.addWidget(self.workspace_panel)
        
        self.sidebar = SidebarWidget(self.store)
        self.sidebar.conversation_selected.connect(self._load_conversation)
        self.sidebar.new_chat_requested.connect(self._new_chat)
        self.sidebar_stack.addWidget(self.sidebar)

        self.model_manager = ModelManagerPanel()
        self.model_manager.models_changed.connect(self._load_models)
        self.sidebar_stack.addWidget(self.model_manager)

        self.git_panel = GitPanel()
        self.git_panel.status_changed.connect(self._on_git_status_changed)
        self.sidebar_stack.addWidget(self.git_panel)

        sidebar_layout.addWidget(self.sidebar_stack)
        main_layout.addWidget(self.sidebar_container)

        self.sidebar_stack.setCurrentIndex(1) # Start with Chat sidebar

        # Main Content
        self.content_splitter = QSplitter(Qt.Horizontal)

        # Editor area: vertical splitter with tabs on top, terminal below
        self.editor_splitter = QSplitter(Qt.Vertical)
        self.editor_tabs = EditorTabs()
        self.editor_splitter.addWidget(self.editor_tabs)

        self.terminal = TerminalWidget()
        self.editor_splitter.addWidget(self.terminal)
        self.editor_splitter.setSizes([500, 200])

        self.content_splitter.addWidget(self.editor_splitter)

        # Chat Panel
        self.chat_panel = QWidget()
        chat_layout = QVBoxLayout(self.chat_panel)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)
        
        # Top Bar (Title Only)
        top_bar = QWidget()
        top_bar.setFixedHeight(40)
        top_bar.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e3e;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 0, 10, 0)
        
        self.title_label = QLabel(APP_NAME)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff;")
        top_layout.addWidget(self.title_label)
        top_layout.addStretch()

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        self.model_combo.currentTextChanged.connect(self._on_model_combo_changed)
        top_layout.addWidget(self.model_combo)
        
        chat_layout.addWidget(top_bar)
        
        # Add Global Toolbar for visibility
        self.toolbar = self.addToolBar("Controls")
        self.toolbar.setMovable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        
        # Summarize Action
        self.sum_action = QAction("Summarize (0% Context)", self)
        self.sum_action.triggered.connect(self._trigger_summarization)
        self.toolbar.addAction(self.sum_action)
        self.toolbar.addSeparator()

        sys_prompt_btn = QPushButton("System Prompt")
        sys_prompt_btn.clicked.connect(self._open_system_prompt)
        self.toolbar.addWidget(sys_prompt_btn)

        self.toolbar.addSeparator()

        compare_btn = QPushButton("Compare Models")
        compare_btn.clicked.connect(self._open_compare)
        self.toolbar.addWidget(compare_btn)

        self.toolbar.addSeparator()

        log_btn = QPushButton("View Logs")
        log_btn.clicked.connect(self._view_logs)
        self.toolbar.addWidget(log_btn)

        theme_btn = QPushButton("Change Theme")
        theme_menu = QMenu(self)
        for tname in THEMES:
            action = theme_menu.addAction(tname)
            action.triggered.connect(lambda checked, n=tname: self._on_theme_changed(n))
        theme_btn.setMenu(theme_menu)
        self.toolbar.addWidget(theme_btn)
        
        # Chat Tabs Container
        self.chat_tabs = QTabWidget()
        self.chat_tabs.setTabsClosable(True)
        self.chat_tabs.setMovable(True)
        self.chat_tabs.tabCloseRequested.connect(self._on_close_chat_tab)
        self.chat_tabs.currentChanged.connect(self._on_chat_tab_changed)
        chat_layout.addWidget(self.chat_tabs)
        
        # Input
        self.input_widget = InputWidget()
        self.input_widget.message_submitted.connect(self._send_message)
        self.input_widget.stop_btn.clicked.connect(self._stop_generation)
        chat_layout.addWidget(self.input_widget)
        
        self.content_splitter.addWidget(self.chat_panel)
        self.content_splitter.setSizes([600, 600])
        main_layout.addWidget(self.content_splitter)

        # Status Bar
        self.status_bar = self.statusBar()
        
        self.connection_dot = QLabel("\u25cf")
        self.connection_dot.setStyleSheet("color: #808080; font-size: 14px; padding: 0 10px;")
        self.connection_dot.setToolTip("Checking Ollama connection...")
        self.status_bar.addWidget(self.connection_dot)

        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        self.git_branch_label = QLabel("")
        self.git_branch_label.setStyleSheet("color: #c678dd; font-size: 11px; padding: 0 10px;")
        self.status_bar.addWidget(self.git_branch_label)

        self.mcp_status_label = QLabel("MCP: —")
        self.mcp_status_label.setStyleSheet("color: #8b949e; font-size: 11px; padding: 0 8px;")
        self.mcp_status_label.setToolTip("MCP server connection status")
        self.status_bar.addWidget(self.mcp_status_label)

        # Permanent Widgets (Right Side)
        self.context_label = QLabel("Context: 0/4096")
        self.context_label.setStyleSheet("padding: 0 10px; color: #8b949e;")
        self.status_bar.addPermanentWidget(self.context_label)

        self.editor_pos_label = QLabel("Ln 1, Col 1")
        self.editor_pos_label.setStyleSheet("padding: 0 10px; color: #8b949e;")
        self.status_bar.addPermanentWidget(self.editor_pos_label)

        self.auto_exec_check = QPushButton("Frictionless: OFF")
        self.auto_exec_check.setCheckable(True)
        self.auto_exec_check.setChecked(self.settings_data.get("auto_exec", False))
        self.auto_exec_check.toggled.connect(self._on_auto_exec_toggled)
        self.auto_exec_check.setFlat(True)
        self.status_bar.addPermanentWidget(self.auto_exec_check)
        
        self.summarize_status_btn = QPushButton("Summarize: OFF")
        self.summarize_status_btn.setCheckable(True)
        self.summarize_status_btn.setFlat(True)
        self.summarize_status_btn.clicked.connect(self._trigger_summarization)
        self.status_bar.addPermanentWidget(self.summarize_status_btn)

        self._update_frictionless_style(self.auto_exec_check.isChecked())
        self._set_summarize_running(False)

    def _setup_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = QSystemTrayIcon(self)
            self._tray_icon.setToolTip(APP_NAME)
            tray_menu = QMenu()
            show_action = tray_menu.addAction("Show")
            show_action.triggered.connect(self.showNormal)
            quit_action = tray_menu.addAction("Quit")
            quit_action.triggered.connect(QApplication.quit)
            self._tray_icon.setContextMenu(tray_menu)
            self._tray_icon.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.Trigger else None)
            self._tray_icon.show()

    def _setup_timers(self):
        self._stream_timer = QTimer()
        self._stream_timer.setInterval(50)
        self._stream_timer.timeout.connect(self._update_streaming_display)

        self._draft_timer = QTimer()
        self._draft_timer.setInterval(5000)
        self._draft_timer.timeout.connect(self._save_draft)
        self._draft_timer.start()

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self, self._new_chat)
        QShortcut(QKeySequence("Ctrl+B"), self, self._toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_workspace_file)
        QShortcut(QKeySequence("Ctrl+Z"), self, self._rollback_last_edit)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self._open_command_palette)
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: self.input_widget.focus_input())
        QShortcut(QKeySequence("Ctrl+W"), self, self._close_current_tab)
        QShortcut(QKeySequence("Ctrl+Tab"), self, self._next_tab)
        QShortcut(QKeySequence("Ctrl+Shift+Tab"), self, self._prev_tab)
        QShortcut(QKeySequence("Ctrl+Shift+N"), self, self._new_window)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self, self._global_search)
        QShortcut(QKeySequence("Ctrl+,"), self, self._open_settings)
        QShortcut(QKeySequence("Ctrl+I"), self, self._import_conversation)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_reset)
        QShortcut(QKeySequence("Ctrl+V"), self, lambda: self.input_widget.paste_image_from_clipboard())
        QShortcut(QKeySequence("Ctrl+`"), self, self._toggle_terminal)
        QShortcut(QKeySequence("Ctrl+Shift+H"), self, self._workspace_search_replace)

    def _load_models(self):
        self.loader = ModelLoader()
        self.loader.models_loaded.connect(self._on_models_loaded)
        self.loader.start()

    def _on_models_loaded(self, models):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        # Put preferred model at the top of the list
        preferred = self.settings_data.get("model", DEFAULT_MODEL)
        if preferred in models:
            models = [preferred] + [m for m in models if m != preferred]

        self.model_combo.addItems(models)
        self.model_combo.setCurrentIndex(0)
        self.model_combo.blockSignals(False)

        if self.current_conv:
            self.current_conv["model"] = self.model_combo.currentText() or DEFAULT_MODEL

    def _on_model_combo_changed(self, model_name):
        if model_name and self.current_conv:
            previous_model = self.current_conv.get("model")
            self.current_conv["model"] = model_name
            if previous_model and previous_model != model_name:
                unload_model(previous_model)
            self.settings_data["model"] = model_name
            save_settings(self.settings_data)

    def _on_activity_changed(self, index):
        self.sidebar_stack.setCurrentIndex(index)

    def _on_file_selected(self, filepath):
        editor = self.editor_tabs.open_file(filepath)
        if editor:
            editor.cursor_changed.connect(self._update_cursor_pos)
            # Initial update
            cursor = editor.textCursor()
            self._update_cursor_pos(cursor.blockNumber() + 1, cursor.columnNumber() + 1)

    def _update_cursor_pos(self, line, col):
        self.editor_pos_label.setText(f"Ln {line}, Col {col}")

    def _start_indexing(self):
        ws = self.workspace_panel.get_workspace_dir()
        if not ws:
            return
        
        if self.indexer and self.indexer.isRunning():
            self.indexer.stop()
            self.indexer.wait()
            
        self.status_label.setText("Indexing workspace...")
        self.indexer = WorkspaceIndexer(ws)
        self.indexer.indexing_complete.connect(self._on_indexing_complete)
        self.indexer.start()

    def _on_indexing_complete(self, index):
        self.workspace_index = index
        self.tool_executor.workspace_dir = self.workspace_panel.get_workspace_dir()
        self.status_label.setText(f"Indexed {len(index)} files")
        log.info(f"Indexing complete: {len(index)} files")
        self.input_widget.set_workspace_files(list(index.keys()))

    def _new_chat(self):
        model = self.model_combo.currentText() or DEFAULT_MODEL
        conv = new_conversation(model)
        self._add_chat_tab(conv)

    def _get_tab_conv(self, tab_index):
        return self._tab_conversations.get(tab_index)

    def _add_chat_tab(self, conv):
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        view = QWebEngineView()
        page = ChatPage(view)
        page.action_requested.connect(self._on_chat_action)
        page.featurePermissionRequested.connect(
            lambda origin, feature: page.setFeaturePermission(
                origin, feature, QWebEnginePage.PermissionGrantedByUser
            )
        )
        view.setPage(page)
        from PyQt5.QtWebEngineWidgets import QWebEngineSettings
        settings = view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptCanAccessClipboard, True)
        tab_layout.addWidget(view)

        title = conv.get("title", "New Chat")
        idx = self.chat_tabs.addTab(tab_widget, title)
        self._tab_conversations[idx] = conv
        self.chat_tabs.setCurrentIndex(idx)

        self.current_conv = conv
        self.title_label.setText(title)
        self._render_chat(idx)
        self.input_widget.focus_input()

    def _load_conversation(self, conv_id):
        for i in range(self.chat_tabs.count()):
            conv = self._get_tab_conv(i)
            if conv and conv.get("id") == conv_id:
                self.chat_tabs.setCurrentIndex(i)
                return

        conv = self.store.load(conv_id)
        if conv:
            self._add_chat_tab(conv)

    def _render_chat(self, tab_index=None):
        if tab_index is None:
            tab_index = self.chat_tabs.currentIndex()
        if tab_index < 0:
            return

        tab_widget = self.chat_tabs.widget(tab_index)
        if not tab_widget:
            return
        conv = self._get_tab_conv(tab_index)
        if not conv:
            return

        from PyQt5.QtCore import QUrl
        messages = conv.get("messages", [])
        html = self.renderer.build_html(messages, self.model_combo.currentText())
        view = tab_widget.findChild(QWebEngineView)
        if view:
            view.setHtml(html, QUrl("qrc:/"))
        else:
            log.warning("_render_chat: no QWebEngineView found in tab")

    def _on_chat_tab_changed(self, index):
        if index < 0: return
        self.current_conv = self._get_tab_conv(index)
        if self.current_conv:
            self.title_label.setText(self.current_conv.get("title", "Untitled"))
            self.model_combo.blockSignals(True)
            idx = self.model_combo.findText(self.current_conv.get("model", DEFAULT_MODEL))
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            self.model_combo.blockSignals(False)
            total_text = "".join([m.get("content", "") for m in self.current_conv.get("messages", [])])
            tokens = estimate_tokens(total_text)
            max_ctx = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS).get("num_ctx", 4096)
            self.context_label.setText(f"Context: ~{tokens}/{max_ctx}")
        self.input_widget.focus_input()

    def _on_close_chat_tab(self, index):
        self._tab_conversations.pop(index, None)
        if self.chat_tabs.count() > 1:
            self.chat_tabs.removeTab(index)
            self._reindex_tab_conversations()
        else:
            self._new_chat()
            self.chat_tabs.removeTab(0)
            self._reindex_tab_conversations()

    def _reindex_tab_conversations(self):
        old = self._tab_conversations
        new_map = {}
        sorted_keys = sorted(old.keys())
        new_idx = 0
        for old_idx in sorted_keys:
            if old_idx in old and new_idx < self.chat_tabs.count():
                new_map[new_idx] = old[old_idx]
                new_idx += 1
        self._tab_conversations = new_map

    def _on_theme_changed(self, theme_name):
        from ..utils.constants import get_theme_qss
        qss = get_theme_qss(theme_name)
        QApplication.instance().setStyleSheet(qss)
        self.settings_data["theme"] = theme_name
        save_settings(self.settings_data)

    def _view_logs(self):
        log_path = Path.home() / ".synapse.log"
        if log_path.exists():
            self.editor_tabs.open_file(str(log_path))
        else:
            self.status_label.setText("Log file not found")

    def _send_message(self, text, images=None, files=None, bypass_rag=False):
        idx = self.chat_tabs.currentIndex()
        if idx < 0:
            self._new_chat()
            idx = self.chat_tabs.currentIndex()
        conv = self._get_tab_conv(idx)
        if not conv:
            self._new_chat()
            idx = self.chat_tabs.currentIndex()
            conv = self._get_tab_conv(idx)
            if not conv:
                return
        self.current_conv = conv

        if text.startswith("/"):
            self._handle_slash_command(text)
            return

        content = text

        # @file mentions: inject file contents
        if content:
            content = self._expand_file_mentions(content)

        # RAG: Search workspace for context mapping to the query
        if not bypass_rag and text:
            context_snippets = self._search_workspace(text)
            if context_snippets:
                context_header = "\n\n---\nRelevant Workspace Context:\n"
                content += context_header + "\n".join(context_snippets)

        if text: # Don't add empty user messages for tool continuations
            msg = {
                "role": "user",
                "content": content,
                "timestamp": datetime.now().isoformat(),
            }
            if images: msg["images"] = images
            conv["messages"].append(msg)

        self._render_chat(self.chat_tabs.currentIndex())
        self.input_widget.set_streaming(True)

        self._streaming_text = ""
        self._streaming_dirty = False
        self._streaming_start_time = time.time()
        self._streaming_token_count = 0
        self._streaming_initialized = False
        self._stream_flushed_text = ""
        self._stream_pending_text = ""

        model = self.model_combo.currentText() or DEFAULT_MODEL
        if self._last_requested_model and self._last_requested_model != model:
            unload_model(self._last_requested_model)
        unload_all_models(except_model=model)
        self._last_requested_model = model
        gen_params = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS)
        tools = (
            self.tool_executor.registry.get_tool_definitions()
            + self.plugin_manager.get_tool_definitions()
            + self.mcp_manager.get_tool_definitions()
        )
        log.info(f"Sending {len(tools)} tools to model ({len(self.mcp_manager.get_tool_definitions())} from MCP)")

        system_prompt = conv.get("system_prompt", "")
        mcp_tools = self.mcp_manager.get_tool_definitions()
        if mcp_tools:
            tool_names = [t["function"]["name"] for t in mcp_tools]
            mcp_hint = "\n\nYou have access to external MCP tools. IMPORTANT RULES:\n"
            if any("github" in n for n in tool_names):
                gh_user = self.settings_data.get("github_username", "")
                if gh_user:
                    mcp_hint += f"- The GitHub user is '{gh_user}'. When asked about 'my repos/issues/PRs', search for owner:{gh_user}. Use mcp__github__search_repositories with 'user:{gh_user}' to list their repos.\n"
                    mcp_hint += "- NEVER ask the user for their GitHub username — you already know it.\n"
                else:
                    mcp_hint += "- When asked about 'my repos', call mcp__github__get_me first to get the username, then search with that.\n"
            mcp_hint += "- Always call the relevant tool instead of saying you can't or asking for info you can look up.\n"
            mcp_hint += f"- Available tools: {', '.join(tool_names[:10])}\n"
            system_prompt = (system_prompt + mcp_hint) if system_prompt else mcp_hint.strip()

        self.worker = OllamaWorker(
            model,
            conv["messages"],
            system_prompt,
            gen_params,
            tools=tools
        )
        self._active_stream_conv = conv
        self._active_stream_tab_index = self.chat_tabs.currentIndex()
        self.worker.token_received.connect(self._on_token)
        self.worker.tool_calls_received.connect(self._on_tool_calls)
        self.worker.response_finished.connect(self._on_response_done)
        self.worker.error_occurred.connect(self._on_worker_error)
        self.worker.start()
        self._set_streaming_state(True)
        self._stream_timer.start()
        
        # Update context guess
        total_text = "".join([m.get("content", "") for m in conv["messages"]])
        tokens = estimate_tokens(total_text)
        max_ctx = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS).get("num_ctx", 4096)
        self.context_label.setText(f"Context: ~{tokens}/{max_ctx}")

    def _set_streaming_state(self, streaming):
        self.input_widget.set_streaming(streaming)

    def _on_tool_calls(self, tool_calls):
        if self.worker:
            self.worker.stop()
            self.worker.wait()

        tool_names = [tc["function"]["name"] for tc in tool_calls]
        self.status_label.setText(f"Tool call: {', '.join(tool_names)}")
        QApplication.processEvents()

        results = []
        for tc in tool_calls:
            name = tc["function"]["name"]
            args = tc["function"]["arguments"]
            approved = False
            
            if name == "write_file":
                try:
                    path = args.get("path")
                    new_content = args.get("content")
                    
                    full_path = Path(path)
                    if not full_path.is_absolute():
                        ws_dir = self.workspace_panel.get_workspace_dir()
                        full_path = ws_dir / path if ws_dir else full_path
                    
                    old_content = ""
                    if full_path.exists():
                        old_content = full_path.read_text(errors='replace')
                    
                    if self.auto_exec_check.isChecked():
                        approved = True
                        self._edit_history.append((full_path, old_content))
                    else:
                        dialog = DiffViewDialog(self, str(path), old_content, new_content)
                        if dialog.exec_() == QDialog.Accepted:
                            approved = True
                            self._edit_history.append((full_path, old_content))
                except Exception as e:
                    log.error(f"Error preparing tool execution: {e}")
                    if not self.auto_exec_check.isChecked():
                        dialog = ToolApprovalDialog(self, name, args)
                        if dialog.exec_() == QDialog.Accepted:
                            approved = True
                    else:
                        approved = True
            else:
                if self.auto_exec_check.isChecked():
                    approved = True
                else:
                    dialog = ToolApprovalDialog(self, name, args)
                    if dialog.exec_() == QDialog.Accepted:
                        approved = True

            if approved:
                self.status_label.setText(f"Running tool: {name}...")

                # Three-tier dispatch: built-in, plugin, then MCP
                res = self.tool_executor.registry.execute(name, args)  # returns None if not found

                if res is None:
                    res = self.plugin_manager.execute_tool(name, args)  # returns None if not found

                if res is None:
                    # For MCP tools, execute synchronously
                    worker = _MCPCallWorker(self.mcp_manager, name, args)
                    res = worker.execute()

                if res is None:
                    res = f"Error: No handler found for tool '{name}'."

                results.append({"id": tc.get("id"), "content": res})
                self._start_indexing() # Always re-index after tool use to stay in sync
                if name == "write_file":
                    self.workspace_panel.refresh()
            else:
                results.append({"id": tc.get("id"), "content": "User rejected the tool execution."})
        
        conv = self._active_stream_conv or self.current_conv
        if not conv:
            return

        # Add tool result message to conversation
        if results:
            conv["messages"].append({
                "role": "assistant",
                "content": "", # Optional text before tools
                "tool_calls": tool_calls
            })
            conv["messages"].append({
                "role": "tool_results", # Custom role for internal tracking
                "tool_results": results
            })
            
            # Auto-continue with results
            self._send_message("", bypass_rag=True)

    def _on_token(self, token):
        if self._streaming_token_count == 0:
            self._streaming_start_time = time.time()
        self._streaming_text += token
        self._streaming_token_count += 1
        self._streaming_dirty = True

    def _update_streaming_display(self):
        if not self._streaming_dirty:
            return
        self._streaming_dirty = False

        elapsed = time.time() - self._streaming_start_time
        tps = self._streaming_token_count / elapsed if elapsed > 0 else 0
        self.status_label.setText(f"Streaming: {self._streaming_token_count} tokens \u00b7 {tps:.1f} tok/s")

        idx = self._active_stream_tab_index if self._active_stream_tab_index >= 0 else self.chat_tabs.currentIndex()
        if idx < 0:
            return
        tab_widget = self.chat_tabs.widget(idx)
        if not tab_widget:
            return
        view = tab_widget.findChild(QWebEngineView)
        if not view:
            return
        conv = self._active_stream_conv or self.current_conv
        if not conv:
            return

        if not self._streaming_initialized:
            self._streaming_initialized = True
            preview_msgs = list(conv["messages"]) + [{
                "role": "assistant",
                "content": '<pre id="streaming-content" style="white-space:pre-wrap;font-family:inherit;margin:0;background:transparent;border:none;padding:0;"></pre>',
                "timestamp": datetime.now().isoformat(),
            }]
            html = self.renderer.build_html(preview_msgs, self.model_combo.currentText())
            html = html.replace(
                '&lt;pre id=&quot;streaming-content&quot;',
                '<pre id="streaming-content"'
            ).replace(
                '&lt;/pre&gt;',
                '</pre>'
            )
            from PyQt5.QtCore import QUrl
            view.setHtml(html, QUrl("qrc:/"))
            self._stream_pending_text = self._streaming_text
        else:
            new_text = self._streaming_text[len(self._stream_flushed_text):]
            if new_text:
                import html as html_mod
                escaped = html_mod.escape(new_text).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")
                view.page().runJavaScript(f"appendStreamToken('{escaped}');")
                self._stream_flushed_text = self._streaming_text

        if self._streaming_token_count % 50 == 0:
            total_text = "".join(m.get("content", "") for m in conv["messages"]) + self._streaming_text
            tokens = estimate_tokens(total_text)
            max_ctx = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS).get("num_ctx", 4096)
            pct = min(100, int(tokens / max_ctx * 100))
            self.context_label.setText(f"Context: ~{tokens}/{max_ctx} ({pct}%)")
            self.sum_action.setText(f"Summarize ({pct}% Context)")

    def _on_response_done(self, full_text, stats):
        self._stream_timer.stop()
        conv = self._active_stream_conv or self.current_conv
        if not conv:
            self.input_widget.set_streaming(False)
            return

        eval_count = stats.get("eval_count", 0)
        eval_duration = stats.get("eval_duration", 0)
        duration_ms = int(eval_duration / 1_000_000) if eval_duration else int((time.time() - self._streaming_start_time) * 1000)

        msg = {
            "role": "assistant",
            "content": full_text,
            "timestamp": datetime.now().isoformat(),
            "model": self.model_combo.currentText(),
            "tokens": eval_count or self._streaming_token_count,
            "duration_ms": duration_ms,
        }
        conv["messages"].append(msg)
        self.store.save(conv)
        self.sidebar.refresh(select_id=conv["id"])

        if self._active_stream_tab_index >= 0:
            self._render_chat(self._active_stream_tab_index)
        else:
            self._render_chat()
        self.input_widget.set_streaming(False)

        tps = msg["tokens"] / (duration_ms / 1000) if duration_ms > 0 else 0
        self.status_label.setText(f"Done: {msg['tokens']} tokens \u00b7 {tps:.1f} tok/s \u00b7 {duration_ms/1000:.1f}s")

        total_text = "".join(m.get("content", "") for m in conv["messages"])
        tokens = estimate_tokens(total_text)
        max_ctx = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS).get("num_ctx", 4096)
        pct = min(100, int(tokens / max_ctx * 100))
        self.context_label.setText(f"Context: ~{tokens}/{max_ctx} ({pct}%)")
        self.sum_action.setText(f"Summarize ({pct}% Context)")

        # Auto-title after first assistant response
        if len([m for m in conv["messages"] if m["role"] == "assistant"]) == 1 and conv.get("title") == "New Chat":
            self._auto_title(conv)

        self._active_stream_conv = None
        self._active_stream_tab_index = -1

        if not self.isActiveWindow() and self.settings_data.get("notifications", True):
            self._notify_completion(conv.get("title", "Chat"), msg["tokens"])

        queued = self.input_widget.text_edit.toPlainText().strip()
        if queued:
            self.input_widget.text_edit.clear()
            self._send_message(queued)

    def _notify_completion(self, title, tokens):
        try:
            if self._tray_icon and self._tray_icon.isVisible():
                self._tray_icon.showMessage(
                    APP_NAME, f"Response complete: {tokens} tokens in '{title}'",
                    QSystemTrayIcon.Information, 3000
                )
        except Exception:
            pass

    def _on_worker_error(self, err_msg):
        if self._stream_timer.isActive():
            self._stream_timer.stop()
        self.input_widget.set_streaming(False)
        self._set_summarize_running(False)
        self._active_stream_conv = None
        self._active_stream_tab_index = -1
        self.status_label.setText("API Error occurred")
        QMessageBox.critical(
            self,
            "API Error",
            "An error occurred with the AI model request:\n\n"
            f"{err_msg}\n\n"
            "Notes:\n"
            "- Synapse now unloads Ollama memory and retries once on model-load failures.\n"
            "- If this still fails, the model may be too large for the current setup or the Ollama blob may be corrupted.\n"
            "- If this is a 400 about tools, the model does not support tools and Synapse will fall back without them."
        )

    def _handle_slash_command(self, cmd_text):
        parts = cmd_text.split()
        cmd = parts[0].lower()
        arg = " ".join(parts[1:])

        if cmd == "/search":
            if not arg:
                self.status_label.setText("Usage: /search <query>")
                return
            if not self.workspace_index:
                self.status_label.setText("Workspace not indexed")
                return
            results = search_index(self.workspace_index, arg)
            if results:
                info = "\n".join(f"- {r['path']}" for r in results[:10])
                QMessageBox.information(self, "Search Results", f"Found in:\n{info}")
            else:
                self.status_label.setText("No results found")
        elif cmd == "/summarize":
            self._run_summarization()
        elif cmd == "/clear":
            self._new_chat()
        elif cmd == "/model":
            if arg:
                idx = self.model_combo.findText(arg)
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)
                    self.status_label.setText(f"Switched to {arg}")
                else:
                    self.status_label.setText(f"Model not found: {arg}")
            else:
                self.status_label.setText(f"Current model: {self.model_combo.currentText()}")
        elif cmd == "/system":
            self._open_system_prompt()
        elif cmd == "/export":
            fmt = arg.strip().lower() if arg else "md"
            if fmt in ("md", "html", "json", "pdf"):
                self._export_current(fmt)
            else:
                self.status_label.setText("Usage: /export [md|html|json|pdf]")
        elif cmd == "/stats":
            if self.current_conv:
                msgs = self.current_conv["messages"]
                total = len(msgs)
                user_msgs = sum(1 for m in msgs if m["role"] == "user")
                asst_msgs = sum(1 for m in msgs if m["role"] == "assistant")
                total_tokens = sum(m.get("tokens", 0) for m in msgs)
                info = f"Messages: {total} ({user_msgs} user, {asst_msgs} assistant)\nTokens: {total_tokens}\nModel: {self.model_combo.currentText()}"
                QMessageBox.information(self, "Conversation Stats", info)
        elif cmd == "/mcp":
            if not arg:
                statuses = self.mcp_manager.get_server_statuses()
                if not statuses:
                    self.status_label.setText("No MCP servers configured. Add them in Settings.")
                else:
                    info = "\n".join(f"{'✓' if s['connected'] else '✗'} {s['name']} ({'enabled' if s['enabled'] else 'disabled'}) - {s['tools_count']} tools" for s in statuses)
                    QMessageBox.information(self, "MCP Servers", info)
            else:
                server_name = arg.strip()
                for cfg in self.settings_data.get("mcp_servers", []):
                    if cfg["name"] == server_name:
                        cfg["enabled"] = not cfg.get("enabled", True)
                        state = "enabled" if cfg["enabled"] else "disabled"
                        save_settings(self.settings_data)
                        self.mcp_manager.load_from_settings(self.settings_data)
                        self._update_mcp_status()
                        self.status_label.setText(f"MCP server '{server_name}' {state}")
                        break
                else:
                    self.status_label.setText(f"MCP server '{server_name}' not found")
        elif cmd == "/help":
            help_text = (
                "/clear - New chat\n/model <name> - Switch model\n/system - Edit system prompt\n"
                "/search <query> - Search workspace\n/summarize - Summarize to free context\n"
                "/export [md|html|json|pdf] - Export conversation\n/stats - Show conversation stats\n"
                "/mcp [name] - Show MCP status or toggle a server\n"
                "/help - Show this help\n\n"
                "Shortcuts:\n"
                "Ctrl+N: New chat | Ctrl+B: Toggle sidebar | Ctrl+L: Focus input\n"
                "Ctrl+S: Save file | Ctrl+W: Close tab | Ctrl+Tab/Shift+Tab: Switch tabs\n"
                "Ctrl+Shift+P: Command palette | Ctrl+Shift+F: Search conversations\n"
                "Ctrl+Shift+H: Search & replace workspace | Ctrl+`: Toggle terminal\n"
                "Ctrl+,: Settings | Ctrl+I: Import | Ctrl+=/-/0: Zoom\n"
                "Ctrl+V: Paste image | @ in input: Mention workspace file"
            )
            QMessageBox.information(self, "Slash Commands & Shortcuts", help_text)
        else:
            plugin_result = self.plugin_manager.handle_slash(cmd.lstrip("/"), arg)
            if plugin_result:
                self.status_label.setText(str(plugin_result))
            else:
                self.status_label.setText(f"Unknown command: {cmd}")

    def _expand_file_mentions(self, text):
        import re as _re
        mentions = _re.findall(r'@(\S+)', text)
        if not mentions or not self.workspace_index:
            return text
        ws = self.workspace_panel.get_workspace_dir()
        if not ws:
            return text
        appended = []
        for mention in mentions:
            for indexed_path in self.workspace_index:
                if mention in indexed_path or indexed_path.endswith(mention):
                    full = ws / indexed_path
                    try:
                        file_content = full.read_text(errors='replace')[:10000]
                        appended.append(f"\n\n--- File: {indexed_path} ---\n```\n{file_content}\n```")
                    except OSError:
                        pass
                    break
        if appended:
            text += "\n".join(appended)
        return text

    def _search_workspace(self, query):
        if not self.workspace_index:
            return []
        
        results = search_index(self.workspace_index, query)
        snippets = []
        for r in results[:3]: # Limit to top 3 files
            path = r["path"]
            data = self.workspace_index[path]
            snippets.append(f"File: {path}\nContent Snippet:\n{data['content'][:1000]}\n")
        return snippets

    def _on_chat_action(self, action, index):
        if not self.current_conv:
            return

        if action == "applycode" or action == "proposecode":
            self._propose_code_block(index, auto_apply=(action == "applycode"))
        elif action == "savecode":
            self._propose_code_block(index, auto_apply=True)
        elif action == "runcode":
            self._run_code_block(index)
        elif action == "copy":
            if 0 <= index < len(self.current_conv["messages"]):
                msg = self.current_conv["messages"][index]
                QApplication.clipboard().setText(msg.get("content", ""))
                self.status_label.setText("Copied to clipboard")
        elif action == "edit":
            self._edit_message(index)
        elif action == "regenerate":
            self._regenerate(index)
        elif action == "retrywith":
            self._retry_with_model(index)
        elif action == "bookmark":
            self._toggle_bookmark(index)
        elif action == "continue":
            self._continue_generation()
        elif action == "fork":
            self._fork_conversation(index)

    def _run_code_block(self, code_block_index):
        if not self.current_conv:
            return
        all_blocks = []
        for msg in self.current_conv["messages"]:
            if msg.get("role") == "assistant":
                matches = list(re.finditer(r'```(\w*)\n(.*?)\n```', msg["content"], re.DOTALL))
                for m in matches:
                    all_blocks.append((m.group(1), m.group(2)))
        if code_block_index < 0 or code_block_index >= len(all_blocks):
            self.status_label.setText("Code block not found")
            return
        lang, code = all_blocks[code_block_index]
        if lang.lower() not in ('python', 'python3', 'py', 'bash', 'sh'):
            self.status_label.setText(f"Cannot run {lang} code blocks")
            return
        cmd = ["python3", "-c", code] if lang.lower() in ('python', 'python3', 'py') else ["bash", "-c", code]
        ws = self.workspace_panel.get_workspace_dir()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd=str(ws) if ws else None
            )
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr
            output = output.strip() or "(no output)"
            exec_msg = f"```\n$ Run {lang} code block\nExit code: {result.returncode}\n\n{output}\n```"
            self.current_conv["messages"].append({
                "role": "assistant",
                "content": exec_msg,
                "timestamp": datetime.now().isoformat(),
                "model": "code-execution",
            })
            self.store.save(self.current_conv)
            self._render_chat()
            self.status_label.setText(f"Code executed (exit {result.returncode})")
        except subprocess.TimeoutExpired:
            self.status_label.setText("Code execution timed out (30s)")
        except Exception as e:
            self.status_label.setText(f"Execution error: {e}")

    def _edit_message(self, index):
        if not self.current_conv or index < 0 or index >= len(self.current_conv["messages"]):
            return
        msg = self.current_conv["messages"][index]
        if msg["role"] != "user":
            return
        new_text, ok = QInputDialog.getMultiLineText(self, "Edit Message", "Edit:", msg["content"])
        if ok and new_text.strip():
            self.current_conv["messages"] = self.current_conv["messages"][:index]
            self._send_message(new_text.strip())

    def _regenerate(self, index):
        if not self.current_conv:
            return
        while self.current_conv["messages"] and self.current_conv["messages"][-1]["role"] == "assistant":
            self.current_conv["messages"].pop()
        self._send_message("", bypass_rag=True)

    def _retry_with_model(self, index):
        if not self.current_conv:
            return
        models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        model, ok = QInputDialog.getItem(self, "Retry With", "Select model:", models, 0, False)
        if ok and model:
            self.model_combo.setCurrentText(model)
            self._regenerate(index)

    def _toggle_bookmark(self, index):
        if not self.current_conv or index < 0 or index >= len(self.current_conv["messages"]):
            return
        msg = self.current_conv["messages"][index]
        msg["bookmarked"] = not msg.get("bookmarked", False)
        self.store.save(self.current_conv)
        self._render_chat()

    def _continue_generation(self):
        if self.current_conv:
            self._send_message("Continue from where you left off.", bypass_rag=True)

    def _fork_conversation(self, index):
        if not self.current_conv:
            return
        msgs = self.current_conv["messages"]
        if index < 0 or index >= len(msgs):
            return
        forked = new_conversation(self.current_conv.get("model", DEFAULT_MODEL))
        forked["title"] = f"Fork: {self.current_conv.get('title', 'Untitled')}"
        forked["messages"] = [dict(m) for m in msgs[:index + 1]]
        forked["system_prompt"] = self.current_conv.get("system_prompt", "")
        self.store.save(forked)
        self._add_chat_tab(forked)
        self.sidebar.refresh(select_id=forked["id"])
        self.status_label.setText(f"Forked at message {index + 1}")

    def _propose_code_block(self, code_block_index, auto_apply=False):
        if not self.current_conv:
            return
        
        all_blocks = []
        for msg in self.current_conv["messages"]:
            if msg["role"] == "assistant":
                content = msg["content"]
                # Match blocks and capture context
                matches = list(re.finditer(r'```(?:\w*)\n(.*?)\n```', content, re.DOTALL))
                for m in matches:
                    # Look for filename in the 300 chars BEFORE or 300 chars AFTER the match
                    start = max(0, m.start() - 300)
                    end = min(len(content), m.end() + 300)
                    context = content[start:end]
                    
                    # Search for common path patterns
                    path_match = re.search(r'[`"\' ]([\w\-/._]+\.\w+)[`"\' ]', context)
                    # Also look for "File: path" or "in path"
                    if not path_match:
                        path_match = re.search(r'(?:[Ff]ile|[Ii]n):?\s*([\w\-/._]+\.\w+)', context)
                    
                    path = path_match.group(1) if path_match else None
                    all_blocks.append((path, m.group(1)))
        
        if code_block_index < 0 or code_block_index >= len(all_blocks):
            self.status_label.setText(f"Code block {code_block_index} not found (Total blocks: {len(all_blocks)})")
            return
            
        detected_path, code = all_blocks[code_block_index]
        workspace = self.workspace_panel.get_workspace_dir()
        
        if not workspace:
            QMessageBox.warning(self, "No Workspace", "Open a folder first.")
            return

        filename = detected_path
        if not filename:
             filename, ok = QInputDialog.getText(self, "Apply Code", "Filename to modify:", text="main.py")
             if not ok or not filename: return
        
        filepath = workspace / filename if not Path(filename).is_absolute() else Path(filename)
        
        old_content = ""
        exists = filepath.exists()
        if exists:
            old_content = filepath.read_text(errors='replace')
        
        # If it's a new file, just write it without diff (user explicitly clicked Apply/Save)
        if not exists:
            filepath.write_text(code)
            self.status_label.setText(f"Created new file {filename}")
            self.workspace_panel.refresh()
            self.editor_tabs.open_file(str(filepath))
            self._start_indexing()
            return

        # If it exists, either show diff or auto-apply
        if auto_apply:
            self._edit_history.append((filepath, old_content))
            filepath.write_text(code)
            self.status_label.setText(f"Applied changes to {filename}. (Ctrl+Z to Rollback)")
            self.workspace_panel.refresh()
            self.editor_tabs.open_file(str(filepath))
            self._start_indexing()
        else:
            dialog = DiffViewDialog(self, str(filename), old_content, code)
            if dialog.exec_() == QDialog.Accepted and dialog.accepted_change:
                # Backup for rollback
                self._edit_history.append((filepath, old_content))
                filepath.write_text(code)
                self.status_label.setText(f"Applied changes to {filename}. (Ctrl+Z to Rollback)")
                self.workspace_panel.refresh()
                self.editor_tabs.open_file(str(filepath))
                self._start_indexing()

    def _rollback_last_edit(self):
        if not self._edit_history:
            self.status_label.setText("No edits to rollback")
            return
        filepath, old_content = self._edit_history.pop()
        try:
            filepath.write_text(old_content)
            self.status_label.setText(f"Rolled back {filepath.name} ({len(self._edit_history)} remaining)")
            self.workspace_panel.refresh()
            self.editor_tabs.open_file(str(filepath))
            self._start_indexing()
        except Exception as e:
            QMessageBox.critical(self, "Rollback Failed", str(e))

    def _toggle_sidebar(self):
        self.sidebar_container.setVisible(not self.sidebar_container.isVisible())

    def _toggle_terminal(self):
        self.terminal.setVisible(not self.terminal.isVisible())
        if self.terminal.isVisible():
            self.terminal.input_line.setFocus()

    def _save_workspace_file(self):
        self.editor_tabs.save_current()

    def _stop_generation(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)
        self._stream_timer.stop()
        self.input_widget.set_streaming(False)
        self._active_stream_conv = None
        self._active_stream_tab_index = -1
        self.status_label.setText("Generation stopped")

    def _restore_geometry(self):
        settings = QSettings(APP_NAME, APP_NAME)
        geo = settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)

    def _on_workspace_changed(self, path):
        self.terminal.set_cwd(path)
        self.git_panel.set_workspace(path)

    def _on_git_status_changed(self, branch, count):
        suffix = f" ({count})" if count else ""
        self.git_branch_label.setText(f"\u2387 {branch}{suffix}")

    def _update_mcp_status(self):
        """Update MCP status indicator in status bar."""
        statuses = self.mcp_manager.get_server_statuses()
        if not statuses:
            self.mcp_status_label.setText("MCP: —")
            return

        connected = sum(1 for s in statuses if s["connected"])
        total = len(statuses)

        if connected == total:
            color = "#7ee787"  # green
        elif connected > 0:
            color = "#e3b341"  # yellow
        else:
            color = "#f85149"  # red

        self.mcp_status_label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 0 8px;")
        self.mcp_status_label.setText(f"MCP: {connected}/{total}")

        names = ", ".join(s["name"] for s in statuses if s["connected"])
        self.mcp_status_label.setToolTip(f"Connected: {names}" if names else "No MCP servers connected")

    def _restore_workspace(self):
        ws = self.settings_data.get("workspace_dir")
        if ws:
            self.workspace_panel.set_workspace(ws)
            self.terminal.set_cwd(ws)
            self.git_panel.set_workspace(ws)
            self._start_indexing()

    def _save_draft(self):
        text = self.input_widget.text_edit.toPlainText()
        try:
            if text.strip():
                DRAFT_FILE.write_text(text)
            elif DRAFT_FILE.exists():
                DRAFT_FILE.unlink()
        except OSError:
            pass

    def _restore_draft(self):
        try:
            if DRAFT_FILE.exists():
                text = DRAFT_FILE.read_text()
                if text.strip():
                    self.input_widget.text_edit.setPlainText(text)
        except OSError:
            pass

    def _open_system_prompt(self):
        if not self.current_conv:
            return
        dlg = SystemPromptDialog(self.current_conv.get("system_prompt", ""), self)
        dlg.prompt_changed.connect(self._on_system_prompt_changed)
        dlg.exec_()

    def _on_system_prompt_changed(self, prompt):
        if self.current_conv:
            self.current_conv["system_prompt"] = prompt
            self.store.save(self.current_conv)
            self.status_label.setText("System prompt updated")

    def _open_compare(self):
        if not self.current_conv or not self.current_conv.get("messages"):
            self.status_label.setText("Need a conversation to compare")
            return
        models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        if len(models) < 2:
            self.status_label.setText("Need at least 2 models to compare")
            return
        from PyQt5.QtWidgets import QDialog as _QD
        dlg = QDialog(self)
        dlg.setWindowTitle("Select Models to Compare")
        dlg.setMinimumWidth(400)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Select 2-3 models:"))
        from PyQt5.QtWidgets import QListWidget as _LW
        lw = _LW()
        lw.setSelectionMode(_LW.MultiSelection)
        for m in models:
            lw.addItem(m)
        lay.addWidget(lw)
        ok_btn = QPushButton("Compare")
        ok_btn.clicked.connect(dlg.accept)
        lay.addWidget(ok_btn)
        if dlg.exec_() == QDialog.Accepted:
            selected = [lw.item(i).text() for i in range(lw.count()) if lw.item(i).isSelected()]
            if len(selected) >= 2:
                last_user = ""
                for m in reversed(self.current_conv["messages"]):
                    if m["role"] == "user":
                        last_user = m["content"]
                        break
                gen_params = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS)
                compare_dlg = CompareDialog(
                    last_user, self.current_conv["messages"], selected[:3],
                    self.current_conv.get("system_prompt", ""), gen_params, self
                )
                compare_dlg.exec_()

    def _open_settings(self):
        dlg = SettingsDialog(self.settings_data, self)
        dlg.settings_changed.connect(self._on_settings_changed)
        dlg.exec_()

    def _on_settings_changed(self, new_settings):
        self.settings_data = new_settings
        set_ollama_url(new_settings.get("ollama_url", DEFAULT_OLLAMA_URL))
        self.renderer.font_size = new_settings.get("font_size", 15)
        self._on_theme_changed(new_settings.get("theme", "One Dark"))
        self._update_frictionless_style(new_settings.get("auto_exec", False))
        self.auto_exec_check.setChecked(new_settings.get("auto_exec", False))
        self.mcp_manager.load_from_settings(new_settings)
        self._update_mcp_status()
        if self.current_conv:
            self._render_chat()

    def _open_command_palette(self):
        commands = [
            {"id": "new_chat", "label": "New Chat", "shortcut": "Ctrl+N"},
            {"id": "toggle_sidebar", "label": "Toggle Sidebar", "shortcut": "Ctrl+B"},
            {"id": "system_prompt", "label": "Edit System Prompt", "shortcut": ""},
            {"id": "compare", "label": "Compare Models", "shortcut": ""},
            {"id": "settings", "label": "Open Settings", "shortcut": "Ctrl+,"},
            {"id": "save", "label": "Save File", "shortcut": "Ctrl+S"},
            {"id": "close_tab", "label": "Close Tab", "shortcut": "Ctrl+W"},
            {"id": "focus_input", "label": "Focus Chat Input", "shortcut": "Ctrl+L"},
            {"id": "global_search", "label": "Search All Conversations", "shortcut": "Ctrl+Shift+F"},
            {"id": "import", "label": "Import Conversation", "shortcut": "Ctrl+I"},
            {"id": "export_md", "label": "Export as Markdown", "shortcut": ""},
            {"id": "export_html", "label": "Export as HTML", "shortcut": ""},
            {"id": "export_json", "label": "Export as JSON", "shortcut": ""},
            {"id": "export_pdf", "label": "Export as PDF", "shortcut": ""},
            {"id": "view_logs", "label": "View Logs", "shortcut": ""},
            {"id": "summarize", "label": "Summarize Context", "shortcut": ""},
            {"id": "zoom_in", "label": "Zoom In", "shortcut": "Ctrl+="},
            {"id": "zoom_out", "label": "Zoom Out", "shortcut": "Ctrl+-"},
            {"id": "zoom_reset", "label": "Reset Zoom", "shortcut": "Ctrl+0"},
            {"id": "clear", "label": "Clear / New Chat", "shortcut": ""},
            {"id": "toggle_terminal", "label": "Toggle Terminal", "shortcut": "Ctrl+`"},
            {"id": "git_refresh", "label": "Git: Refresh Status", "shortcut": ""},
            {"id": "workspace_search", "label": "Search & Replace in Workspace", "shortcut": "Ctrl+Shift+H"},
            {"id": "export_all", "label": "Export All Conversations (JSON)", "shortcut": ""},
            {"id": "delete_all", "label": "Delete All Conversations", "shortcut": ""},
        ]
        for tname in THEMES:
            commands.append({"id": f"theme_{tname}", "label": f"Theme: {tname}", "shortcut": ""})

        palette = CommandPalette(commands, self)
        palette.command_selected.connect(self._execute_command)
        palette.move(self.geometry().center().x() - 250, self.geometry().top() + 80)
        palette.exec_()

    def _execute_command(self, cmd_id):
        dispatch = {
            "new_chat": self._new_chat,
            "toggle_sidebar": self._toggle_sidebar,
            "system_prompt": self._open_system_prompt,
            "compare": self._open_compare,
            "settings": self._open_settings,
            "save": self._save_workspace_file,
            "close_tab": self._close_current_tab,
            "focus_input": self.input_widget.focus_input,
            "global_search": self._global_search,
            "import": self._import_conversation,
            "export_md": lambda: self._export_current("md"),
            "export_html": lambda: self._export_current("html"),
            "export_json": lambda: self._export_current("json"),
            "export_pdf": lambda: self._export_current("pdf"),
            "view_logs": self._view_logs,
            "summarize": self._trigger_summarization,
            "zoom_in": self._zoom_in,
            "zoom_out": self._zoom_out,
            "zoom_reset": self._zoom_reset,
            "clear": self._new_chat,
            "toggle_terminal": self._toggle_terminal,
            "git_refresh": self.git_panel.refresh,
            "workspace_search": self._workspace_search_replace,
            "export_all": self._export_all_conversations,
            "delete_all": self._delete_all_conversations,
        }
        for tname in THEMES:
            dispatch[f"theme_{tname}"] = lambda n=tname: self._on_theme_changed(n)

        fn = dispatch.get(cmd_id)
        if fn:
            fn()

    def _close_current_tab(self):
        idx = self.chat_tabs.currentIndex()
        if idx >= 0:
            self._on_close_chat_tab(idx)

    def _next_tab(self):
        idx = self.chat_tabs.currentIndex()
        if idx < self.chat_tabs.count() - 1:
            self.chat_tabs.setCurrentIndex(idx + 1)

    def _prev_tab(self):
        idx = self.chat_tabs.currentIndex()
        if idx > 0:
            self.chat_tabs.setCurrentIndex(idx - 1)

    def _new_window(self):
        new_win = MainWindow()
        new_win.show()

    def _global_search(self):
        query, ok = QInputDialog.getText(self, "Search All Conversations", "Search:")
        if ok and query.strip():
            results = self.store.search(query.strip())
            if results:
                info = "\n".join(f"- {r['title']}" for r in results[:20])
                QMessageBox.information(self, f"Search: {query}", f"Found {len(results)} conversations:\n{info}")
            else:
                self.status_label.setText("No results found")

    def _workspace_search_replace(self):
        ws = self.workspace_panel.get_workspace_dir()
        if not ws:
            self.status_label.setText("No workspace open")
            return
        dlg = WorkspaceSearchDialog(str(ws), self)
        dlg.file_requested.connect(self._on_search_file_requested)
        dlg.exec_()

    def _on_search_file_requested(self, filepath, line):
        editor = self.editor_tabs.open_file(filepath)
        if editor:
            cursor = editor.textCursor()
            cursor.movePosition(cursor.Start)
            for _ in range(line - 1):
                cursor.movePosition(cursor.Down)
            editor.setTextCursor(cursor)
            editor.centerCursor()

    def _import_conversation(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Conversation", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                for conv in data:
                    if "id" in conv and "messages" in conv:
                        self.store.save(conv)
                self.sidebar.refresh()
                self.status_label.setText(f"Imported {len(data)} conversations")
            elif "id" in data and "messages" in data:
                self.store.save(data)
                self.sidebar.refresh()
                self._add_chat_tab(data)
                self.status_label.setText("Imported conversation")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _export_current(self, fmt):
        if not self.current_conv:
            return
        conv = self.current_conv
        title = conv.get("title", "conversation")
        if fmt == "md":
            path, _ = QFileDialog.getSaveFileName(self, "Export", f"{title}.md", "Markdown (*.md)")
            if path:
                with open(path, "w") as f:
                    f.write(f"# {title}\n\nModel: {conv.get('model', '')}\n\n---\n\n")
                    for msg in conv.get("messages", []):
                        role = "**You**" if msg.get("role") == "user" else "**Assistant**"
                        f.write(f"{role}:\n\n{msg.get('content', '')}\n\n---\n\n")
        elif fmt == "html":
            path, _ = QFileDialog.getSaveFileName(self, "Export", f"{title}.html", "HTML (*.html)")
            if path:
                html = self.renderer.build_html(conv.get("messages", []), conv.get("model", ""))
                with open(path, "w") as f:
                    f.write(html)
        elif fmt == "json":
            path, _ = QFileDialog.getSaveFileName(self, "Export", f"{title}.json", "JSON (*.json)")
            if path:
                with open(path, "w") as f:
                    json.dump(conv, f, indent=2)
        elif fmt == "pdf":
            path, _ = QFileDialog.getSaveFileName(self, "Export", f"{title}.pdf", "PDF (*.pdf)")
            if path:
                html = self.renderer.build_html(conv.get("messages", []), conv.get("model", ""))
                tab_widget = self.chat_tabs.currentWidget()
                view = tab_widget.findChild(QWebEngineView) if tab_widget else None
                if view:
                    from PyQt5.QtCore import QMarginsF
                    from PyQt5.QtGui import QPageLayout, QPageSize
                    page_layout = QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(15, 15, 15, 15))
                    view.page().printToPdf(path, page_layout)
                    self.status_label.setText("PDF export started...")
                    return
        self.status_label.setText(f"Exported as {fmt.upper()}")

    def _export_all_conversations(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export All", "all_conversations.json", "JSON (*.json)")
        if not path:
            return
        all_convs = self.store.list_conversations()
        loaded = []
        for meta in all_convs:
            conv = self.store.load(meta["id"])
            if conv:
                loaded.append(conv)
        with open(path, "w") as f:
            json.dump(loaded, f, indent=2)
        self.status_label.setText(f"Exported {len(loaded)} conversations")

    def _delete_all_conversations(self):
        reply = QMessageBox.warning(
            self, "Delete All Conversations",
            "This will permanently delete ALL conversations. Continue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        all_convs = self.store.list_conversations()
        for meta in all_convs:
            self.store.delete(meta["id"])
        while self.chat_tabs.count() > 0:
            self._tab_conversations.pop(0, None)
            self.chat_tabs.removeTab(0)
        self._tab_conversations.clear()
        self._new_chat()
        self.sidebar.refresh()
        self.status_label.setText(f"Deleted {len(all_convs)} conversations")

    def _zoom_in(self):
        self._zoom = min(200, self._zoom + 10)
        self.renderer.font_size = int(15 * self._zoom / 100)
        self._render_chat()
        self.settings_data["zoom"] = self._zoom
        save_settings(self.settings_data)

    def _zoom_out(self):
        self._zoom = max(50, self._zoom - 10)
        self.renderer.font_size = int(15 * self._zoom / 100)
        self._render_chat()
        self.settings_data["zoom"] = self._zoom
        save_settings(self.settings_data)

    def _zoom_reset(self):
        self._zoom = 100
        self.renderer.font_size = 15
        self._render_chat()
        self.settings_data["zoom"] = 100
        save_settings(self.settings_data)

    def _auto_title(self, conv):
        model = self.model_combo.currentText() or DEFAULT_MODEL
        self._title_worker = TitleWorker(model, conv["id"], conv["messages"])
        self._title_worker.title_ready.connect(self._on_auto_title)
        self._title_worker.start()

    def _on_auto_title(self, conv_id, title):
        for i in range(self.chat_tabs.count()):
            conv = self._get_tab_conv(i)
            if conv and conv.get("id") == conv_id:
                conv["title"] = title
                self.chat_tabs.setTabText(i, title)
                if conv is self.current_conv:
                    self.title_label.setText(title)
                self.store.save(conv)
                self.sidebar.refresh(select_id=conv_id)
                break

    def closeEvent(self, event):
        if self.current_conv:
            self.store.save(self.current_conv)
        settings = QSettings(APP_NAME, APP_NAME)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        self._save_draft()
        if self._conn_checker:
            self._conn_checker.stop()
        super().closeEvent(event)

    def _trigger_summarization(self):
        if not self.summarize_status_btn.isEnabled():
            return
        if self.worker and self.worker.isRunning():
            return
        self._set_summarize_running(True)
        self._run_summarization()

    def _set_summarize_running(self, running):
        self.summarize_status_btn.setChecked(running)
        self.summarize_status_btn.setEnabled(not running)
        if running:
            self.summarize_status_btn.setStyleSheet("color: #2ea043; font-weight: bold; padding: 0 10px; background: transparent; border: none;")
            self.summarize_status_btn.setText("Summarize: ON")
        else:
            self.summarize_status_btn.setEnabled(True)
            self.summarize_status_btn.setStyleSheet("color: #8b949e; font-weight: bold; padding: 0 10px; background: transparent; border: none;")
            self.summarize_status_btn.setText("Summarize: OFF")

    def _run_summarization(self):
        if not self.current_conv or not self.current_conv.get("messages"):
            self._set_summarize_running(False)
            self.status_label.setText("Nothing to summarize")
            return
            
        self.status_label.setText("Summarizing conversation to free context...")
        
        # Create a temporary worker for summarization
        model = self.model_combo.currentText() or DEFAULT_MODEL
        summary_prompt = "Please provide a concise but comprehensive summary of our conversation so far. Focus on key decisions, code changes, and current goals. This summary will be used to reset the context window while preserving our progress."
        
        # Use a copy of messages to avoid mutation issues
        temp_messages = list(self.current_conv["messages"]) + [{"role": "user", "content": summary_prompt}]
        
        self.worker = OllamaWorker(model, temp_messages, self.current_conv.get("system_prompt", ""))
        self.worker.response_finished.connect(self._on_summary_done)
        self.worker.error_occurred.connect(self._on_worker_error)
        self.worker.start()
        self.input_widget.set_streaming(True)

    def _on_auto_exec_toggled(self, checked):
        self.settings_data["auto_exec"] = checked
        save_settings(self.settings_data)
        self._update_frictionless_style(checked)
        self.status_label.setText(f"Frictionless Mode: {'Enabled' if checked else 'Disabled'}")

    def _update_frictionless_style(self, enabled):
        if enabled:
            # Green "On" state
            self.auto_exec_check.setStyleSheet("color: #2ea043; font-weight: bold; padding: 0 10px; background: transparent; border: none;")
            self.auto_exec_check.setText("Frictionless: ON")
        else:
            # Subtle "Off" state
            self.auto_exec_check.setStyleSheet("color: #8b949e; font-weight: bold; padding: 0 10px; background: transparent; border: none;")
            self.auto_exec_check.setText("Frictionless: OFF")

    def _setup_conn_checker(self):
        self._conn_checker = ConnectionChecker()
        self._conn_checker.status_changed.connect(self._on_connection_status_changed)
        self._conn_checker.start()

    def _on_connection_status_changed(self, online):
        if online:
            self.connection_dot.setStyleSheet("color: #2ea043; font-size: 14px; padding: 0 4px;")
            self.connection_dot.setToolTip("Ollama Connected")
        else:
            self.connection_dot.setStyleSheet("color: #d32f2f; font-size: 14px; padding: 0 4px;")
            self.connection_dot.setToolTip("Ollama Offline")

    def _on_summary_done(self, summary_text, stats):
        if not self.current_conv:
            self._set_summarize_running(False)
            return

        reply = QMessageBox.question(
            self, "Context Reset",
            f"Replace {len(self.current_conv['messages'])} messages with a summary?\n\n"
            f"Preview:\n{summary_text[:300]}...\n\n"
            "This cannot be undone. The original conversation will be saved as a backup.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            self.input_widget.set_streaming(False)
            self._set_summarize_running(False)
            self.status_label.setText("Summarization cancelled")
            return

        import copy
        backup = copy.deepcopy(self.current_conv)
        backup["id"] = str(__import__('uuid').uuid4())
        backup["title"] = self.current_conv.get("title", "Untitled") + " (pre-summary backup)"
        self.store.save(backup)

        self.current_conv["messages"] = [
            {
                "role": "system",
                "content": f"The following is a condensed summary of the previous conversation context to save tokens. Proceed based on this summary:\n\n{summary_text}",
                "timestamp": datetime.now().isoformat()
            }
        ]
        self.store.save(self.current_conv)
        self._render_chat()
        self.input_widget.set_streaming(False)
        self._set_summarize_running(False)
        self.sidebar.refresh(select_id=self.current_conv["id"])
        self.status_label.setText("Context reset with summary (backup saved)")
