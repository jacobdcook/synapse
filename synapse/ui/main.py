import sys
import os
import json
import time
import uuid
import logging
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Any, Tuple

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStackedWidget, QComboBox, QLabel, QProgressBar,
    QMessageBox, QFileDialog, QInputDialog, QPlainTextEdit, QTextEdit, QShortcut,
    QSystemTrayIcon, QMenu, QAction, QDialog, QTabWidget, QPushButton,
    QGraphicsDropShadowEffect, QStatusBar
)
from PyQt5.QtCore import Qt, QTimer, QSettings, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QKeySequence, QColor

from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

from ..utils.constants import (
    APP_NAME, DEFAULT_MODEL, DEFAULT_SYSTEM_PROMPT, DEFAULT_GEN_PARAMS,
    DEFAULT_OLLAMA_URL, RECOMMENDED_MODELS, DEFAULT_SHORTCUTS, DRAFT_FILE,
    CONFIG_DIR, get_ollama_url, set_ollama_url, load_settings, save_settings,
    format_time, relative_time, estimate_tokens
)
from ..core.api import (
    WorkerFactory, ModelLoader, TitleWorker, SummaryWorker, YouTubeWorker, unload_model, unload_all_models, ConnectionChecker,
    BaseAIWorker
)
from ..core.renderer import ChatRenderer
from ..core.store import ConversationStore, new_conversation
from .chat_page import ChatPage
from .split_view import SplitViewWidget
from .sidebar import SidebarWidget
from .input import InputWidget
from .editor import CodeEditor
from .workspace import WorkspacePanel, EditorTabs
from .canvas import CanvasWidget
from .activity_bar import ActivityBar
from .plugin_sidebar import PluginSidebar
from ..core.indexer import WorkspaceIndexer, search_index, load_index, save_index, extract_text_from_pdf, extract_text_from_docx
from ..core.graph_rag import GraphRAGService
from ..core.code_executor import CodeExecutor
from ..core.agent import ToolExecutor
from .tool_approval import ToolApprovalDialog
from .model_manager import ModelManagerPanel
from .system_prompt import SystemPromptDialog
from .command_palette import CommandPalette
from .screenshot import ScreenCaptureWidget
from .settings_dialog import SettingsDialog
from .compare_dialog import CompareDialog
from .diff_view import DiffViewDialog
from ..core.plugins import PluginManager
from ..core.mcp import MCPClientManager
from ..core.git import GitStatusWorker, is_git_repo, GitRemoteService
from .terminal import TerminalWidget
from ..core.lsp_manager import LSPManager
from ..core.semantic_indexer import SemanticIndexer, SemanticWorkspaceIndexer
from ..core.context_manager import ContextManager
from ..core.project_rules import ProjectRulesManager
from .git_panel import GitPanel
from .workspace_search import WorkspaceSearchDialog
from .knowledge_sidebar import KnowledgeSidebar
from .plan import PlanPanel
from ..utils.themes import THEMES
from ..utils.hotkey_manager import GlobalHotkeyManager
from ..core.voice import VoiceManager
from .onboarding import OnboardingWizard
from .template_library import TemplateLibrary
from .analytics_sidebar import AnalyticsSidebar
from ..core.analytics import analytics_manager
from .tree_visualizer import ConversationTreeSidebar as BranchTreeSidebar
from .ScheduleSidebar import ScheduleSidebar
from ..core.scheduler import scheduler
from .ImageGenSidebar import ImageGenSidebar
from ..core.image_gen import ImageGenerator
from .workflow_sidebar import WorkflowSidebar
from .bookmarks_panel import BookmarksPanel
from .table_editor import TableEditorDialog
from .quick_chat import QuickChatWidget
from .playground import PlaygroundPanel
from .arena_dialog import ArenaDialog
from .prompt_lab import PromptLab
from .consensus_dialog import ConsensusDialog
from ..core.code_extractor import CodeExtractor
from .shortcuts_dialog import ShortcutsDialog
from .replay_dialog import ReplayDialog
from ..core.backend_manager import BackendManager
from ..core.agent_manager import AgentManager
from .agent_forge import AgentForgeSidebar
from .mcp_marketplace import MCPMarketplacePanel
from ..core.task_manager import TaskManager
from .task_board import TaskBoardPanel
from ..core.privacy_filter import PrivacyFilter
from ..core.lora_manager import LoRAManager
from .fine_tuning import FineTuningPanel
from ..core.debug_manager import DebugManager
from .debug_sidebar import DebugSidebar
from .debug_toolbar import DebugToolbar
from ..core.test_manager import TestManager
from .test_sidebar import TestSidebar
from ..core.build_manager import BuildTaskManager
from .task_runner_sidebar import TaskRunnerSidebar
from .pr_sidebar import PullRequestSidebar
from .pr_review_view import PRReviewView
from ..core.docker_manager import DockerManager
from .docker_sidebar import DockerSidebar
from ..core.notebook_manager import NotebookManager
from ..core.plugins import PluginManager, SynapsePlugin
from ..core.agentic import AgenticLoop
from ..core.file_applier import FileApplier

log = logging.getLogger(__name__)

class PluginAPI:
    """The interface exposed to plugins."""
    def __init__(self, main_window: 'MainWindow'):
        self.main_window = main_window

    def add_activity(self, icon: str, tooltip: str, callback: callable) -> int:
        """Add a new icon to the activity bar."""
        index = 100 + len(self.main_window.activity_bar.buttons) # Dynamic index
        self.main_window.activity_bar.add_activity(icon, index, tooltip)
        # Register callback for activity change
        # This requires a bit more logic in MainWindow to handle dynamic indices
        return index

    def add_sidebar(self, widget: QWidget, index: int):
        """Add a widget to the sidebar stack."""
        self.main_window.sidebar_stack.addWidget(widget)
        # We might need a mapping of index to widget to show it correctly

    def log(self, message: str):
        log.info(f"[Plugin] {message}")

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
        self.workspace_index = load_index()
        self.graph_rag = GraphRAGService()
        self.code_executor = CodeExecutor()
        
        # Restore index stats to sidebar if loaded
        if self.workspace_index:
            QTimer.singleShot(500, lambda: self.knowledge_sidebar.update_stats(self.workspace_index))
        # self.tool_executor initialized below
        self.voice_manager = VoiceManager()
        self.voice_manager.transcription_result.connect(self._on_transcription_received)
        self.voice_manager.error_occurred.connect(lambda msg: self.status_label.setText(msg))
        self.agent_manager = AgentManager()
        self.mcp_manager = MCPClientManager()
        self.context_manager = ContextManager(self.workspace_root)
        self.lsp_manager = LSPManager(self.workspace_root)
        self.lsp_manager.diagnostics_received.connect(self._on_lsp_diagnostics)
        self.semantic_indexer = SemanticIndexer(self.workspace_root)
        self.project_rules = ProjectRulesManager(self.workspace_root)
        self.debug_manager = DebugManager(self.workspace_root)
        self.test_manager = TestManager(self.workspace_root)
        self.build_manager = BuildTaskManager(self.workspace_root)
        self.remote_service = GitRemoteService(self.workspace_root)
        self.docker_manager = DockerManager(self.workspace_root)
        self.notebook_manager = NotebookManager(self.workspace_root)
        self.editor_tabs.notebook_manager = self.notebook_manager
        
        # PH16: Plugin System
        self.plugin_api = PluginAPI(self)
        self.plugin_manager = PluginManager(self.plugin_api)
        self.plugin_sidebar = PluginSidebar(self.plugin_manager)
        self.sidebar_stack.addWidget(self.plugin_sidebar)
        QTimer.singleShot(5000, self.plugin_manager.discover_plugins) # Delay to let UI stabilize

        # Connect notebook kernel signals
        self.notebook_manager.kernel.output_received.connect(self._on_notebook_output)
        self.notebook_manager.kernel.error_received.connect(self._on_notebook_error)
        self.notebook_manager.kernel.finished.connect(self._on_notebook_finished)
        
        self.agent = ToolExecutor(self.workspace_root)
        self.mcp_manager.load_from_settings(self.settings_data)
        self.mcp_manager.servers_changed.connect(self._update_mcp_status)
        self._recent_files = []
        self._current_coverage = {} # {filepath: {line_no: status}}
        self._tab_conversations = {}  # tab_index -> conv dict (preserves reference)
        self._edit_history = []  # stack of (Path, old_content) for multi-level undo
        self._streaming_text = ""
        self._streaming_dirty = False
        self._streaming_token_count = 0
        self._streaming_start_time = 0
        self._zoom = self.settings_data.get("zoom", 100)
        self._active_stream_tab_index = -1
        self._last_requested_model = None
        self._recursion_depth = 0
        self._max_recursion = 10
        self._auto_continue_count = 0
        self.backend_manager = BackendManager()
        self._shortcut_objects = []
        self._consensus_active = False
        self._consensus_responses = {}
        self._rag_enabled = False
        self._active_stream_conv = None
        self._zen_mode = False
        self._autocomplete_enabled = self.settings_data.get("autocomplete", True)
        self._current_theme = THEMES.get(self.settings_data.get("theme", "One Dark"), THEMES["One Dark"])
        
        try:
            unload_all_models()
        except Exception:
            log.info("Ollama not available at startup — continuing in offline mode")
        self._setup_ui()
        
        # Start background services
        scheduler.start()
        self._setup_tray()
        self._setup_timers()
        self._setup_conn_checker()
        self._setup_shortcuts()
        self._clipboard = QApplication.clipboard()
        self._clipboard.dataChanged.connect(self._on_clipboard_changed)
        self._load_models()
        self._restore_geometry()
        self._restore_workspace()
        
        # Open initial chat tab
        self._new_chat()
        theme_name = self.settings_data.get("theme", "Synapse Glass")
        self._on_theme_changed(theme_name)
        self.sidebar.refresh()
        self._restore_draft()
        self._setup_global_hotkey()

        # Phase 1: Onboarding check
        if not self.settings_data.get("onboarding_complete"):
            QTimer.singleShot(1000, self.run_onboarding)

    def run_onboarding(self):
        wizard = OnboardingWizard(self)
        if wizard.exec_():
            # Refresh settings and UI after wizard
            self.settings_data = load_settings()
            self._restore_workspace()
            self.sidebar.refresh()
            theme_name = self.settings_data.get("theme", "Synapse Glass")
            self._on_theme_changed(theme_name)

    def _setup_ui(self):
        # Main Horizontal Layout with Splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        
        self._prev_width = self.width()
        self._sidebar_visible_before_collapse = True

        # Activity Bar (Left Side)
        self.activity_bar = ActivityBar()
        self.activity_bar.activity_changed.connect(self._on_activity_changed)
        self.activity_bar.settings_requested.connect(self._open_settings)
        # Note: Added to splitter later

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
        self.sidebar.fork_requested.connect(self._fork_from_sidebar)
        self.sidebar_stack.addWidget(self.sidebar)

        self.model_manager = ModelManagerPanel()
        self.model_manager.models_changed.connect(self._load_models)
        self.sidebar_stack.addWidget(self.model_manager)

        self.plan_panel = PlanPanel()
        self.tool_executor.plan_updated.connect(self.plan_panel.set_plan)
        self.sidebar_stack.addWidget(self.plan_panel) # Index 3

        self.git_panel = GitPanel()
        self.sidebar_stack.addWidget(self.git_panel) # Index 4

        self.template_library = TemplateLibrary()
        self.template_library.template_applied.connect(self._on_template_applied)
        self.analytics_sidebar = AnalyticsSidebar()
        self.knowledge_sidebar = KnowledgeSidebar() # Was missing instantiation?
        self.knowledge_sidebar.reindex_requested.connect(self._start_indexing)
        
        self.branch_tree_sidebar = BranchTreeSidebar()
        self.branch_tree_sidebar.branch_requested.connect(self._on_branch_requested)
        
        self.schedule_sidebar = ScheduleSidebar()
        scheduler.task_started.connect(self._on_scheduled_task)

        self.image_gen_backend = ImageGenerator()
        self.image_gen_sidebar = ImageGenSidebar(backend_manager=self.backend_manager)
        self.image_gen_sidebar.generation_requested.connect(self._on_image_gen_requested)
        self.image_gen_sidebar.image_selected.connect(self._on_image_selected)
        
        self.workflow_sidebar = WorkflowSidebar()
        self.bookmarks_panel = BookmarksPanel()
        self.bookmarks_panel.bookmark_selected.connect(self._on_bookmark_selected)
        
        self.agent_forge = AgentForgeSidebar(self.agent_manager)
        self.agent_forge.agent_selected.connect(self._on_agent_selected)
        
        self.mcp_marketplace = MCPMarketplacePanel(self.mcp_manager, self.settings_data)
        
        self.task_manager = TaskManager(CONFIG_DIR)
        self.task_board = TaskBoardPanel(self.task_manager, self.agent_manager)
        self.task_board.execution_requested.connect(self._on_task_execution_requested)

        self.debug_sidebar = DebugSidebar()
        self.debug_sidebar.breakpoint_clicked.connect(self._on_debug_breakpoint_clicked)
        self.sidebar_stack.addWidget(self.debug_sidebar) # Index 17 (Debugger)

        self.test_sidebar = TestSidebar()
        self.test_sidebar.run_all_requested.connect(self.test_manager.run_tests)
        self.test_sidebar.run_coverage_requested.connect(self.test_manager.run_coverage)
        self.test_sidebar.refresh_requested.connect(self.test_manager.discover_tests)
        self.sidebar_stack.addWidget(self.test_sidebar) # Index 18 (Testing)

        self.test_manager.discovery_done.connect(self.test_sidebar.set_tests)
        self.test_manager.test_result_ready.connect(self._on_test_result)
        self.test_manager.test_session_finished.connect(self._on_test_session_finished)
        self.test_manager.coverage_updated.connect(self._on_coverage_updated)

        self.task_runner_sidebar = TaskRunnerSidebar()
        self.task_runner_sidebar.run_task_requested.connect(self.build_manager.run_task)
        self.task_runner_sidebar.stop_task_requested.connect(self.build_manager.stop_task)
        self.task_runner_sidebar.refresh_requested.connect(self.build_manager.load_tasks)
        self.sidebar_stack.addWidget(self.task_runner_sidebar) # Index 19 (Tasks)

        self.build_manager.tasks_loaded.connect(self.task_runner_sidebar.update_tasks)
        self.build_manager.task_started.connect(self._on_task_started)
        self.build_manager.task_finished.connect(self._on_task_finished)
        self.build_manager.task_output.connect(self._on_task_output)

        self.pr_sidebar = PullRequestSidebar()
        self.pr_sidebar.refresh_requested.connect(self._on_pr_refresh_requested)
        self.pr_sidebar.pr_selected.connect(self._on_pr_selected)
        self.sidebar_stack.addWidget(self.pr_sidebar) # Index 20 (Remote)

        self.remote_service.prs_ready.connect(self.pr_sidebar.set_prs)
        self.remote_service.issues_ready.connect(self.pr_sidebar.set_issues)
        self.remote_service.error_occurred.connect(lambda err: self.status_label.setText(f"Remote error: {err}"))

        self.docker_sidebar = DockerSidebar()
        self.docker_sidebar.refresh_requested.connect(self.docker_manager.refresh_all)
        self.docker_sidebar.start_requested.connect(self.docker_manager.start_container)
        self.docker_sidebar.stop_requested.connect(self.docker_manager.stop_container)
        self.docker_sidebar.remove_requested.connect(self.docker_manager.remove_container)
        self.docker_sidebar.view_logs_requested.connect(self.docker_manager.fetch_logs)
        self.sidebar_stack.addWidget(self.docker_sidebar) # Index 21 (Docker)

        self.docker_manager.containers_updated.connect(self.docker_sidebar.update_containers)
        self.docker_manager.images_updated.connect(self.docker_sidebar.update_images)
        self.docker_manager.volumes_updated.connect(self.docker_sidebar.update_volumes)
        self.docker_manager.logs_received.connect(self.docker_sidebar.append_logs)
        self.docker_manager.error_occurred.connect(lambda err: self.status_label.setText(f"Docker error: {err}"))

        self.lora_manager = LoRAManager(CONFIG_DIR)
        self.fine_tuning_panel = FineTuningPanel(self.lora_manager)

        self.debug_toolbar = DebugToolbar(self)
        self.debug_toolbar.start_requested.connect(self._on_debug_start)
        self.debug_toolbar.stop_requested.connect(self._on_debug_stop)
        self.debug_toolbar.step_over_requested.connect(self.debug_manager.step_over)
        self.debug_toolbar.step_into_requested.connect(self.debug_manager.step_into)
        self.debug_toolbar.step_out_requested.connect(self.debug_manager.step_out)
        self.debug_toolbar.continue_requested.connect(self.debug_manager.continue_exec)
        # Add to window (will be positioned later in _setup_ui or manually)
        self.addToolBar(Qt.TopToolBarArea, self.debug_toolbar)
        self.debug_toolbar.hide()

        self.debug_manager.session_started.connect(self._on_debug_session_started)
        self.debug_manager.session_stopped.connect(self._on_debug_session_stopped)
        self.debug_manager.paused.connect(self._on_debug_paused)
        self.debug_manager.continued.connect(self._on_debug_continued)
        self.debug_manager.variables_updated.connect(self.debug_sidebar.set_variables)
        self.debug_manager.stack_updated.connect(self.debug_sidebar.set_stack)
        self.debug_manager.breakpoints_updated.connect(self.debug_sidebar.set_breakpoints)

        self.privacy_filter = PrivacyFilter(self.settings_data.get("privacy_firewall", False))

        # Add knowledge_sidebar, template_library, and analytics_sidebar directly to sidebar_layout
        # and manage their visibility manually, instead of using sidebar_stack
        sidebar_layout.addWidget(self.sidebar_stack)
        sidebar_layout.addWidget(self.knowledge_sidebar)
        sidebar_layout.addWidget(self.template_library)
        sidebar_layout.addWidget(self.analytics_sidebar)
        sidebar_layout.addWidget(self.branch_tree_sidebar)
        sidebar_layout.addWidget(self.schedule_sidebar)
        sidebar_layout.addWidget(self.image_gen_sidebar)
        sidebar_layout.addWidget(self.workflow_sidebar)
        sidebar_layout.addWidget(self.bookmarks_panel)
        sidebar_layout.addWidget(self.agent_forge)
        sidebar_layout.addWidget(self.mcp_marketplace)
        sidebar_layout.addWidget(self.task_board)
        sidebar_layout.addWidget(self.fine_tuning_panel)
        sidebar_layout.addWidget(self.debug_sidebar)
        sidebar_layout.addWidget(self.test_sidebar)
        sidebar_layout.addWidget(self.plugin_sidebar)
        
        self.knowledge_sidebar.hide()
        self.template_library.hide()
        self.analytics_sidebar.hide()
        self.branch_tree_sidebar.hide()
        self.schedule_sidebar.hide()
        self.image_gen_sidebar.hide()
        self.workflow_sidebar.hide()
        self.bookmarks_panel.hide()
        self.agent_forge.hide()
        self.mcp_marketplace.hide()
        self.task_board.hide()
        self.fine_tuning_panel.hide()
        self.debug_sidebar.hide()
        self.test_sidebar.hide()
        self.plugin_sidebar.hide()

        self.sidebar_stack.setCurrentIndex(1) # Start with Chat sidebar

        # Main Content
        self.content_splitter = QSplitter(Qt.Horizontal)

        # Editor area: vertical splitter with tabs on top, terminal below
        self.editor_splitter = QSplitter(Qt.Vertical)
        self.editor_tabs = EditorTabs()
        self.editor_tabs.currentChanged.connect(self._on_editor_tab_changed)
        self.editor_splitter.addWidget(self.editor_tabs)

        self.terminal = TerminalWidget()
        self.terminal.output_received.connect(self._on_terminal_output)
        self.editor_splitter.addWidget(self.terminal)
        self.editor_splitter.setSizes([600, 200])

        # Check for dev container
        QTimer.singleShot(2000, self._check_dev_container)
        
        # Add components to splitter
        self.main_splitter.addWidget(self.activity_bar)
        self.main_splitter.addWidget(self.sidebar_container)
        
        self.chat_area = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_area)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(0)
        
        self.chat_tabs = QTabWidget()
        self.chat_tabs.setTabsClosable(True)
        self.chat_tabs.setMovable(True)
        self.chat_tabs.tabCloseRequested.connect(self._on_close_chat_tab)
        self.chat_tabs.currentChanged.connect(self._on_chat_tab_changed)
        self.chat_layout.addWidget(self.chat_tabs)

        self.input_widget = InputWidget()
        self.input_widget.message_submitted.connect(self._send_message)
        self.input_widget.search_toggled.connect(self._on_search_toggled)
        self.input_widget.sync_toggled.connect(self._on_sync_toggled)
        self.input_widget.mic_triggered.connect(self._on_mic_triggered)
        self.input_widget.hands_free_toggled.connect(self._on_hands_free_toggled)
        self.input_widget.stop_btn.clicked.connect(self._stop_generation)
        self.input_widget.force_send_requested.connect(self._force_send_next)
        self.chat_layout.addWidget(self.input_widget)

        # Central Stack for switching between Chat and Editor
        self.central_stack = QStackedWidget()
        self.central_stack.addWidget(self.chat_area)      # Index 0: Chat
        self.central_stack.addWidget(self.editor_splitter) # Index 1: Code Editor
        
        self.main_splitter.addWidget(self.central_stack)

        # Connect voice signals after input_widget is created
        self.voice_manager.mic_level.connect(self.input_widget.update_mic_level)
        
        # Removed redundant addWidget(self.editor_area)
        
        # Set initial sizes for splitter: Bar (48), Sidebar (260), Editor (Remainder)
        self.main_splitter.setSizes([48, 260, 800])
        # Prevent activity bar from being resized by user if possible
        # We can set its handle to non-collapsible at least
        self.main_splitter.setCollapsible(0, False)
        self.main_splitter.setCollapsible(1, False)
        
        # Top Bar (Title Only)
        top_bar = QWidget()
        top_bar.setFixedHeight(40)
        top_bar.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e3e;")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(10, 0, 10, 0)
        
        self.title_label = QLabel(APP_NAME)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #58a6ff; letter-spacing: 1px;")
        self._setup_logo_animation()
        top_layout.addWidget(self.title_label)
        top_layout.addStretch()

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(200)
        self.model_combo.currentTextChanged.connect(self._on_model_combo_changed)
        top_layout.addWidget(self.model_combo)
        
        # Add to window with a top container for the global top bar
        central_container = QWidget()
        self.setCentralWidget(central_container)
        layout = QVBoxLayout(central_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(top_bar)
        layout.addWidget(self.main_splitter)

        # Add Global Toolbar
        self.toolbar = self.addToolBar("Controls")
        self.toolbar.setMovable(False)
        self.toolbar.setObjectName("MainToolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        
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

        self.toolbar.addSeparator()

        export_btn = QPushButton("Export Chat")
        export_menu = QMenu(self)
        export_menu.addAction("Markdown (.md)", lambda: self._export_current("md"))
        export_menu.addAction("HTML (.html)", lambda: self._export_current("html"))
        export_menu.addAction("JSON (.json)", lambda: self._export_current("json"))
        export_menu.addAction("PDF (.pdf)", lambda: self._export_current("pdf"))
        export_btn.setMenu(export_menu)
        self.toolbar.addWidget(export_btn)

        self.toolbar.addSeparator()

        stats_btn = QPushButton("\U0001f4ca Stats") # Chart icon
        stats_btn.clicked.connect(self._show_stats)
        self.toolbar.addWidget(stats_btn)

        self.toolbar.addSeparator()

        table_btn = QPushButton("\U0001f5d2 Table") # Table icon
        table_btn.clicked.connect(self._open_table_editor)
        self.toolbar.addWidget(table_btn)

        # Status Bar
        self.status_bar = self.statusBar()
        self.status_label = QLabel("Ready")
        self.status_bar.addPermanentWidget(self.status_label)

        self.tool_progress = QProgressBar()
        self.tool_progress.setMaximumWidth(140)
        self.tool_progress.setMaximumHeight(14)
        self.tool_progress.setTextVisible(False)
        self.tool_progress.setRange(0, 0)  # indeterminate
        self.tool_progress.setStyleSheet("""
            QProgressBar { background: #21262d; border-radius: 7px; border: 1px solid #30363d; }
            QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #58a6ff, stop:1 #bc8cff); border-radius: 7px; }
        """)
        self.tool_progress.hide()
        self.status_bar.addPermanentWidget(self.tool_progress)

        self.conn_dot = QLabel("\u25CF") # Circle Icon
        self.conn_dot.setStyleSheet("color: #f85149; font-size: 14px; padding-right: 4px;")
        self.conn_dot.setToolTip("Ollama Disconnected")
        self.status_bar.addPermanentWidget(self.conn_dot)

        self.context_prog = QProgressBar()
        self.context_prog.setMaximumWidth(100)
        self.context_prog.setMaximumHeight(12)
        self.context_prog.setTextVisible(False)
        self.context_prog.setStyleSheet("""
            QProgressBar { background: #333; border-radius: 6px; }
            QProgressBar::chunk { background: #58a6ff; border-radius: 6px; }
        """)
        self.status_bar.addPermanentWidget(self.context_prog)

        self.git_branch_label = QLabel("")
        self.git_branch_label.setStyleSheet("color: #c678dd; font-size: 11px; padding: 0 10px;")
        self.status_bar.addWidget(self.git_branch_label)

        self.mcp_status_label = QLabel("MCP: —")
        self.mcp_status_label.setStyleSheet("color: #8b949e; font-size: 11px; padding: 0 8px;")
        self.status_bar.addWidget(self.mcp_status_label)

        # Local Backends Status
        self.sd_status_icon = ClickableLabel("SD: \u25CF")
        self.sd_status_icon.setStyleSheet("color: #8b949e; font-size: 11px; padding: 0 8px;")
        self.sd_status_icon.setToolTip("Stable Diffusion Forge (Stopped)")
        self.sd_status_icon.clicked.connect(lambda: self._toggle_backend("sd"))
        self.status_bar.addWidget(self.sd_status_icon)
        
        self.comfy_status_icon = ClickableLabel("Comfy: \u25CF")
        self.comfy_status_icon.setStyleSheet("color: #8b949e; font-size: 11px; padding: 0 8px;")
        self.comfy_status_icon.setToolTip("ComfyUI (Stopped)")
        self.comfy_status_icon.clicked.connect(lambda: self._toggle_backend("comfy"))
        self.status_bar.addWidget(self.comfy_status_icon)
        
        if self.backend_manager:
            self.backend_manager.status_changed.connect(self._update_backend_status_bar)
            self._update_backend_status_bar()

        self.context_label = QLabel("Context: 0/4096")
        self.context_label.setStyleSheet("padding: 0 10px; color: #8b949e;")
        self.status_bar.addPermanentWidget(self.context_label)

        self.editor_pos_label.setStyleSheet("padding: 0 10px; color: #8b949e;")
        self.status_bar.addPermanentWidget(self.editor_pos_label)

        self.terminal_toggle = QPushButton("\ud83d\udda5 Terminal")
        self.terminal_toggle.setCheckable(True)
        self.terminal_toggle.setChecked(True)
        self.terminal_toggle.setFlat(True)
        self.terminal_toggle.setStyleSheet("padding: 0 5px; color: #8b949e;")
        self.terminal_toggle.clicked.connect(self._toggle_terminal)
        self.status_bar.addPermanentWidget(self.terminal_toggle)

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

        self.autocomplete_status_btn = QPushButton(f"Autocomplete: {'ON' if self._autocomplete_enabled else 'OFF'}")
        self.autocomplete_status_btn.setCheckable(True)
        self.autocomplete_status_btn.setChecked(self._autocomplete_enabled)
        self.autocomplete_status_btn.setFlat(True)
        self.autocomplete_status_btn.clicked.connect(self._on_autocomplete_toggled)
        self.status_bar.addPermanentWidget(self.autocomplete_status_btn)

        self._update_frictionless_style(self.auto_exec_check.isChecked())
        self._set_summarize_running(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = event.size().width()
        
        # Responsive thresholds
        SIDEBAR_COLLAPSE_WIDTH = 900
        
        if width < SIDEBAR_COLLAPSE_WIDTH and self._prev_width >= SIDEBAR_COLLAPSE_WIDTH:
            # Collapse sidebar
            self._sidebar_visible_before_collapse = self.sidebar_container.isVisible()
            self.sidebar_container.hide()
            self.activity_bar.hide()
        elif width >= SIDEBAR_COLLAPSE_WIDTH and self._prev_width < SIDEBAR_COLLAPSE_WIDTH:
            # Restore sidebar if it was visible
            if self._sidebar_visible_before_collapse:
                self.sidebar_container.show()
                self.activity_bar.show()
                
        self._prev_width = width

    def _setup_tray(self):
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray_icon = QSystemTrayIcon(self)
            self._tray_icon.setToolTip(APP_NAME)
            from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
            pm = QPixmap(64, 64)
            pm.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor("#58a6ff"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(4, 4, 56, 56)
            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Arial", 28, QFont.Bold))
            painter.drawText(pm.rect(), Qt.AlignCenter, "S")
            painter.end()
            self._tray_icon.setIcon(QIcon(pm))
            self.setWindowIcon(QIcon(pm))
            tray_menu = QMenu()
            show_action = tray_menu.addAction("Show")
            show_action.triggered.connect(self.showNormal)
            quick_chat_action = tray_menu.addAction("Quick Chat")
            quick_chat_action.triggered.connect(self._open_quick_chat)
            tray_menu.addSeparator()
            quit_action = tray_menu.addAction("Quit")
            quit_action.triggered.connect(QApplication.quit)
            self._tray_icon.setContextMenu(tray_menu)
            self._tray_icon.activated.connect(lambda reason: self.showNormal() if reason == QSystemTrayIcon.Trigger else None)
            self._tray_icon.show()

    def _setup_timers(self):
        self._stream_timer = QTimer()
        self._streaming_delay = self.settings_data.get("streaming_speed", 50)
        self._stream_timer.setInterval(max(10, self._streaming_delay))
        self._stream_timer.timeout.connect(self._update_streaming_display)

        self._draft_timer = QTimer()
        self._draft_timer.setInterval(5000)
        self._draft_timer.timeout.connect(self._save_draft)
        self._draft_timer.start()

    def _toggle_terminal(self):
        if self.terminal.isVisible():
            self.terminal.hide()
            self.terminal_toggle.setChecked(False)
        else:
            self.terminal.show()
            self.terminal_toggle.setChecked(True)
            self.terminal.input_line.setFocus()

    def _setup_shortcuts(self):
        self._apply_shortcuts()

    def _apply_shortcuts(self):
        # Clear existing
        for s in self._shortcut_objects:
            s.setEnabled(False)
            s.deleteLater()
        self._shortcut_objects = []

        bindings = self.settings_data.get("shortcuts", DEFAULT_SHORTCUTS)
        
        # Map actions to methods
        actions = {
            "new_chat": self._new_chat,
            "toggle_sidebar": self._toggle_sidebar,
            "save_file": self._save_workspace_file,
            "rollback": self._rollback_last_edit,
            "command_palette": self._open_command_palette,
            "focus_input": lambda: self.input_widget.focus_input(),
            "close_tab": self._close_current_tab,
            "next_tab": self._next_tab,
            "prev_tab": self._prev_tab,
            "new_window": self._new_window,
            "global_search": self._global_search,
            "settings": self._open_settings,
            "import_conv": self._import_conversation,
            "zoom_in": self._zoom_in,
            "zoom_out": self._zoom_out,
            "zoom_reset": self._zoom_reset,
            "paste_image": lambda: self.input_widget.paste_image_from_clipboard(),
            "toggle_terminal": self._toggle_terminal,
            "search_replace": self._workspace_search_replace,
            "screenshot": self._on_screenshot_triggered,
            "zen_mode": self._toggle_zen_mode,
        }

        for action_id, key in bindings.items():
            if action_id in actions and key:
                s = QShortcut(QKeySequence(key), self, actions[action_id])
                self._shortcut_objects.append(s)

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
        for i in range(self.chat_tabs.count()):
            sv = self.chat_tabs.widget(i).findChild(SplitViewWidget)
            if sv:
                sv.set_available_models(models)

        if self.current_conv:
            self.current_conv["model"] = self.model_combo.currentText() or DEFAULT_MODEL

        self.schedule_sidebar.set_models(models)

    def _on_model_combo_changed(self, model_name):
        if model_name and self.current_conv:
            previous_model = self.current_conv.get("model")
            self.current_conv["model"] = model_name
            if previous_model and previous_model != model_name:
                unload_model(previous_model)
            self.settings_data["model"] = model_name
            save_settings(self.settings_data)

    def _on_task_execution_requested(self, task):
        """Triggered when a task moves to DOING and has an agent assigned."""
        agent_id = task.get("agent_id")
        if not agent_id: return
        
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            QMessageBox.warning(self, "Agent Not Found", f"Agent '{agent_id}' no longer exists.")
            return

        # Switch to chat and start a new session
        self.activity_bar.buttons[1].click() # Select Chat
        self._new_chat()
        
        # Set agent and system prompt
        conv = self.current_conv
        if conv:
            conv["agent_id"] = agent_id
            conv["system_prompt"] = agent.system_prompt
            conv["title"] = f"Task: {task['title']}"
            
            # Formulate task prompt
            prompt = f"I am delegating the following task to you:\n\n"
            prompt += f"**Title**: {task['title']}\n"
            prompt += f"**Description**: {task['description']}\n"
            prompt += f"**Priority**: {task['priority']}\n\n"
            prompt += f"Please execute this task or provide a plan for its completion."
            
            self._send_message(prompt)
            self.status_label.setText(f"Executing task with {agent.name}...")

    def _on_activity_changed(self, index):
        # Hide all custom sidebars first
        for w in (self.knowledge_sidebar, self.template_library, self.analytics_sidebar,
                  self.branch_tree_sidebar, self.schedule_sidebar, self.image_gen_sidebar,
                  self.workflow_sidebar, self.bookmarks_panel, self.agent_forge, self.mcp_marketplace,
                  self.task_board, self.fine_tuning_panel, self.debug_sidebar, self.test_sidebar,
                  self.task_runner_sidebar, self.pr_sidebar, self.docker_sidebar, self.plugin_sidebar):
            w.hide()
        self.sidebar_stack.show()

        if index == 17:
            if hasattr(self, 'debug_sidebar'):
                self.sidebar_stack.setCurrentWidget(self.debug_sidebar)
            else:
                log.error("Debug sidebar not initialized")
        elif index == 18:
            if hasattr(self, 'test_sidebar'):
                self.sidebar_stack.setCurrentWidget(self.test_sidebar)
                self.test_manager.discover_tests() # Refresh on switch
            else:
                log.error("Test sidebar not initialized")
        elif index == 19:
            if hasattr(self, 'task_runner_sidebar'):
                self.sidebar_stack.setCurrentWidget(self.task_runner_sidebar)
                self.build_manager.load_tasks()
            else:
                log.error("Task runner sidebar not initialized")
        elif index == 20:
            if hasattr(self, 'pr_sidebar'):
                self.sidebar_stack.setCurrentWidget(self.pr_sidebar)
                self.remote_service.fetch_prs()
                self.remote_service.fetch_issues()
            else:
                log.error("Remote sidebar not initialized")
        elif index == 21:
            if hasattr(self, 'docker_sidebar'):
                self.sidebar_stack.setCurrentWidget(self.docker_sidebar)
                self.docker_manager.refresh_all()
            else:
                log.error("Docker sidebar not initialized")
        elif index == 22:
            self.terminal.show()
            self.terminal.execute_command("python3")
            self.status_label.setText("REPL: Python 3 started in terminal")
        elif index == 5:
            self.sidebar_stack.hide()
            self.knowledge_sidebar.show()
        elif index == 6:
            self.sidebar_stack.hide()
            self.template_library.show()
        elif index == 7:
            self.sidebar_stack.hide()
            self.analytics_sidebar.refresh()
            self.analytics_sidebar.show()
        elif index == 8:
            self.sidebar_stack.hide()
            if self.current_conv:
                msgs = self.current_conv.get("messages", [])
                active_id = msgs[-1].get("id") if msgs else None
                self.branch_tree_sidebar.refresh(self.current_conv.get("history", []), active_id)
            self.branch_tree_sidebar.show()
        elif index == 9:
            self.sidebar_stack.hide()
            self.schedule_sidebar.refresh()
            self.schedule_sidebar.show()
        elif index == 10:
            self.sidebar_stack.hide()
            self.image_gen_sidebar.show()
        elif index == 11:
            self.sidebar_stack.hide()
            self.workflow_sidebar.refresh()
            self.workflow_sidebar.show()
        elif index == 12:
            self.sidebar_stack.hide()
            self.bookmarks_panel.refresh()
            self.bookmarks_panel.show()
        elif index == 13:
            self.sidebar_stack.hide()
            self.agent_forge.refresh()
            self.agent_forge.show()
        elif index == 14:
            self.sidebar_stack.hide()
            self.mcp_marketplace.refresh()
            self.mcp_marketplace.show()
        elif index == 15:
            self.sidebar_stack.hide()
            self.task_board.refresh()
            self.task_board.show()
        elif index == 16:
            self.sidebar_stack.hide()
            self.fine_tuning_panel.refresh()
            self.fine_tuning_panel.show()
        elif index == 23: # Extensions
            self.sidebar_stack.hide()
            self.plugin_sidebar.show()
        elif index >= 100:
            # Handle Plugin-registered activities
            for plugin in self.plugin_manager.get_active_plugins():
                if hasattr(plugin, 'activity_index') and plugin.activity_index == index:
                    if hasattr(plugin, 'on_activity_activated'):
                        plugin.on_activity_activated()
                    return
        else:
            self.sidebar_stack.setCurrentIndex(index)
            self.sidebar_stack.show()
        
        # Switch central area based on activity
        if index == 0: # Explorer
            self.central_stack.setCurrentIndex(1) # Show Editor
        elif index == 1: # Chat
            self.central_stack.setCurrentIndex(0) # Show Chat
        elif index in (2, 3, 4, 11): # Models, Plan, Git, Workflows usually need Editor
            self.central_stack.setCurrentIndex(1)
        else:
            self.central_stack.setCurrentIndex(0) # Default to Chat

    def _show_stats(self):
        if not self.current_conv:
            return
        
        stats = self.current_conv.get("stats", {})
        msg_count = stats.get("message_count", len(self.current_conv.get("messages", [])))
        tokens = stats.get("total_tokens", 0)
        
        # Simple heuristic if stats not yet calculated
        if tokens == 0:
            for m in self.current_conv.get("messages", []):
                tokens += len(str(m.get("content", "")).split()) * 1.5 + 20
        
        text = f"<h3>Conversation Statistics</h3>"
        text += f"<b>Messages:</b> {msg_count}<br>"
        text += f"<b>Est. Tokens:</b> {int(tokens)}<br>"
        text += f"<b>Model:</b> {self.current_conv.get('model', 'Unknown')}<br>"
        created = self.current_conv.get("created_at", "")
        if created:
            text += f"<b>Created:</b> {created[:10]}<br>"
        
        QMessageBox.information(self, "Stats", text)

    def _on_bookmark_selected(self, conv_id, msg_id):
        self._load_conversation(conv_id)
        if len(self.activity_bar.buttons) > 1:
            self.activity_bar.buttons[1].click()
        if msg_id and self.current_conv:
            for i, msg in enumerate(self.current_conv.get("messages", [])):
                if msg.get("id") == msg_id:
                    idx = self.chat_tabs.currentIndex()
                    tab_widget = self.chat_tabs.widget(idx) if idx >= 0 else None
                    if tab_widget:
                        from PyQt5.QtWebEngineWidgets import QWebEngineView
                        view = tab_widget.findChild(QWebEngineView)
                        if view:
                            view.page().runJavaScript(f"document.querySelectorAll('.message')[{i}]?.scrollIntoView({{behavior:'smooth',block:'center'}});")
                    break

    def _open_table_editor(self):
        dialog = TableEditorDialog(parent=self)
        if dialog.exec_():
            md = dialog.get_markdown()
            self.editor_tabs.current_editor().insertText(md)

    def _on_file_selected(self, filepath):
        editor = self.editor_tabs.open_file(filepath)
        if editor:
            editor.cursor_changed.connect(self._update_cursor_pos)
            if hasattr(editor, 'breakpoint_toggled'):
                editor.breakpoint_toggled.connect(self._on_editor_breakpoint_toggled)
            # Initial update
            cursor = editor.textCursor()
            self._update_cursor_pos(cursor.blockNumber() + 1, cursor.columnNumber() + 1)

    def _update_cursor_pos(self, line, col):
        self.editor_pos_label.setText(f"Ln {line}, Col {col}")

    def _on_search_toggled(self, enabled):
        if enabled:
            self.status_label.setText("Web Grounding: ON")
        else:
            self.status_label.setText("Web Grounding: OFF")

    def _on_mic_triggered(self, enabled):
        if enabled:
            # Load settings for latest values
            voice_cfg = self.settings_data.get("voice", {})
            self.voice_manager.vad_threshold = voice_cfg.get("vad_threshold", 0.01)
            self.voice_manager.silence_timeout = voice_cfg.get("silence_timeout", 1.5)
            self.voice_manager.model_size = voice_cfg.get("whisper_model", "base")
            self.voice_manager.tts_voice = voice_cfg.get("tts_voice", "en-US-AndrewNeural")
            
            hands_free = self.input_widget._hands_free if hasattr(self.input_widget, "_hands_free") else False
            self.voice_manager.start_recording(hands_free=hands_free)
        else:
            self.voice_manager.stop_recording()

    def _toggle_mic(self):
        self.input_widget.mic_btn.click()

    def _on_transcription_received(self, text):
        if not text.strip(): 
            # In hands-free mode, if we got silence/nothing, we might want to stay in recording 
            # but usually VoiceManager handles the stop. 
            # If we are here, something was detected.
            return
            
        self.input_widget.append_text(text)
        hands_free = self.input_widget._hands_free if hasattr(self.input_widget, "_hands_free") else False
        
        if hands_free:
            # Auto-submit in hands-free mode
            self.input_widget._submit()
        else:
            # Normal mode: stop recording and let user edit
            self.input_widget.mic_btn.setChecked(False)
            self.input_widget._on_mic_clicked(False) # Reset UI state

    def _on_hands_free_toggled(self, enabled):
        if enabled:
            self.status_label.setText("Hands-free Mode: ON")
        else:
            self.status_label.setText("Hands-free Mode: OFF")
            if self.voice_manager.is_recording:
                self.voice_manager.stop_recording()
                self.input_widget.mic_btn.setChecked(False)
                self.input_widget._on_mic_clicked(False)

    def _start_indexing(self):
        ws = self.workspace_panel.get_workspace_dir()
        if not ws:
            return
        
        if self.indexer and self.indexer.isRunning():
            self.indexer.stop()
            self.indexer.wait()
            
        self.status_label.setText("Indexing (Vector RAG)...")
        self.indexer = WorkspaceIndexer(ws)
        self.indexer.indexing_progress.connect(
            lambda cur, tot: self.status_label.setText(f"Indexing: {cur}/{tot} files...")
        )
        self.indexer.indexing_complete.connect(self._on_indexing_complete)
        self.indexer.start()

    def _on_indexing_complete(self, index):
        self.workspace_index = index
        save_index(index)
        self.knowledge_sidebar.update_stats(index)
        self.tool_executor.workspace_dir = self.workspace_panel.get_workspace_dir()
        self.status_label.setText(f"RAG Ready: {len(index)} files")
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

        split_view = SplitViewWidget()
        split_view.action_requested.connect(lambda pane, action, idx: self._on_chat_action(action, idx))
        split_view.voted.connect(lambda pane_idx, msg_idx: self._on_vote_cast_by_index(split_view, pane_idx))

        # Initial pane
        models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        split_view.add_pane(models, self.model_combo.currentText())
        
        tab_layout.addWidget(split_view)

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

        # Show loading skeleton while conversation loads
        from PyQt5.QtCore import QUrl, QTimer
        idx = self.chat_tabs.currentIndex()
        if idx >= 0:
            tab_widget = self.chat_tabs.widget(idx)
            view = tab_widget.findChild(QWebEngineView) if tab_widget else None
            if view:
                view.setHtml(self.renderer.build_loading_html(), QUrl("qrc:/"))

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
        history = conv.get("history", [])
        
        split_view = tab_widget.findChild(SplitViewWidget)
        if split_view:
            for pane in split_view.panes:
                pane_model = pane.model_combo.currentText()
                html = self.renderer.build_html(messages, history, model_name=pane_model)
                pane.view.setHtml(html, QUrl("qrc:/"))
        else:
            # Fallback for old tabs or single view
            html = self.renderer.build_html(messages, history, model_name=self.model_combo.currentText())
            view = tab_widget.findChild(QWebEngineView)
            if view:
                view.setHtml(html, QUrl("qrc:/"))

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
        if self.chat_tabs.count() > 1:
            self.chat_tabs.removeTab(index)
            self._tab_conversations.pop(index, None)
            self._reindex_tab_conversations()
        else:
            self._tab_conversations.pop(index, None)
            self._new_chat()
            self.chat_tabs.removeTab(0)
            self._reindex_tab_conversations()

    def _reindex_tab_conversations(self):
        old = dict(self._tab_conversations)
        tab_count = self.chat_tabs.count()
        new_map = {}
        new_idx = 0
        for old_idx in sorted(old.keys()):
            if new_idx < tab_count:
                new_map[new_idx] = old[old_idx]
                new_idx += 1
        self._tab_conversations = new_map

    def _on_theme_changed(self, theme_name):
        from ..utils.constants import get_theme_qss
        qss = get_theme_qss(theme_name)
        QApplication.instance().setStyleSheet(qss)
        self.settings_data["theme"] = theme_name
        save_settings(self.settings_data)
        theme = THEMES.get(theme_name, THEMES["One Dark"])
        self._current_theme = theme
        self.title_label.setStyleSheet(f"font-weight: bold; font-size: 16px; color: {theme['accent']}; letter-spacing: 1px;")
        for widget in (
            self.activity_bar, self.sidebar, self.input_widget,
            self.bookmarks_panel, self.workflow_sidebar, self.schedule_sidebar,
            self.knowledge_sidebar, self.plan_panel, self.branch_tree_sidebar,
        ):
            if hasattr(widget, 'apply_theme'):
                widget.apply_theme(theme)
        for attr in ('canvas', 'terminal_widget', 'workspace_panel'):
            w = getattr(self, attr, None)
            if w and hasattr(w, 'apply_theme'):
                w.apply_theme(theme)

    def _setup_logo_animation(self):
        """Creates a pulsating glow effect for the Synapse Logo."""
        effect = QGraphicsDropShadowEffect(self.title_label)
        effect.setBlurRadius(15)
        effect.setColor(QColor("#58a6ff"))
        effect.setOffset(0, 0)
        self.title_label.setGraphicsEffect(effect)

        self.logo_anim = QPropertyAnimation(effect, b"blurRadius")
        self.logo_anim.setDuration(1500)
        self.logo_anim.setStartValue(5)
        self.logo_anim.setEndValue(25)
        self.logo_anim.setEasingCurve(QEasingCurve.InOutSine)
        self.logo_anim.setLoopCount(-1)
        self.logo_anim.start()

    def _view_logs(self):
        from ..utils.constants import CONFIG_DIR
        log_path = CONFIG_DIR / "synapse.log"
        if log_path.exists():
            try:
                content = log_path.read_text(errors='replace')
                # Show last 500 lines in a dialog
                lines = content.splitlines()
                tail = "\n".join(lines[-500:])
                dlg = QDialog(self)
                dlg.setWindowTitle("Synapse Logs")
                dlg.resize(900, 600)
                layout = QVBoxLayout(dlg)
                text = QTextEdit()
                text.setReadOnly(True)
                text.setFontFamily("monospace")
                text.setStyleSheet("background: #0d1117; color: #c9d1d9; border: none;")
                text.setPlainText(tail)
                layout.addWidget(text)
                btn_row = QHBoxLayout()
                open_ext_btn = QPushButton("Open in External Editor")
                open_ext_btn.clicked.connect(lambda: __import__('webbrowser').open(str(log_path)))
                refresh_btn = QPushButton("Refresh")
                def _refresh():
                    new_content = log_path.read_text(errors='replace')
                    text.setPlainText("\n".join(new_content.splitlines()[-500:]))
                    text.moveCursor(text.textCursor().End)
                refresh_btn.clicked.connect(_refresh)
                close_btn = QPushButton("Close")
                close_btn.clicked.connect(dlg.close)
                clear_btn = QPushButton("Clear Logs")
                clear_btn.setStyleSheet("color: #f85149;")
                def _clear_logs():
                    if QMessageBox.question(dlg, "Clear Logs", "Delete all log history?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
                        try:
                            log_path.write_text("")
                            text.setPlainText("")
                            log.info("Logs cleared by user")
                        except Exception as ex:
                            log.error(f"Failed to clear logs: {ex}")
                clear_btn.clicked.connect(_clear_logs)
                btn_row.addWidget(open_ext_btn)
                btn_row.addWidget(refresh_btn)
                btn_row.addWidget(clear_btn)
                btn_row.addStretch()
                btn_row.addWidget(close_btn)
                layout.addLayout(btn_row)
                # Scroll to bottom
                text.moveCursor(text.textCursor().End)
                dlg.exec_()
            except Exception as e:
                self.status_label.setText(f"Error reading logs: {e}")
        else:
            self.status_label.setText("Log file not found at " + str(log_path))

    def _send_message(self, text, images=None, files=None, bypass_rag=False):
        if not self.current_conv:
            return

        # PH15: Handle /repl slash command
        if text.startswith("/repl "):
            code = text[6:].strip()
            self.notebook_manager.kernel.execute("chat_repl", code)
            self.status_label.setText("REPL: Executing...")
            # Optionally show in chat? For now just execute.
            return

        # Check for Agent Mode
        is_agentic = self.input_widget.agent_mode_btn.isChecked()

        # Reset recursion counter for new user messages
        if text:
            self._recursion_depth = 0
            self._auto_continue_count = 0

        # PH3: Resolve @ Mentions context
        workspace = self.workspace_panel.current_workspace()
        if workspace:
            self.context_manager.workspace_root = Path(workspace)
            terminal_output = self.terminal.get_recent_output(100)
            resolved = self.context_manager.resolve_context(text, terminal_output=terminal_output)
            if resolved:
                context_prompt = self.context_manager.build_context_prompt(resolved)
                # Inject into the text for the AI (but don't necessarily show it duplicated to user? 
                # Actually, adding it to the message content is the safest way to ensure the AI sees it.)
                text = f"{context_prompt}\n{text}"

        # ... (skipping some recursion checks for clarity, assuming they'll be integrated or replaced by AgenticLoop) ...

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

        # Add message to history
        msg_id = str(uuid.uuid4())
        msg = {
            "id": msg_id,
            "role": "user",
            "content": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": self.model_combo.currentText()
        }
        if images: msg["images"] = images
        if files: msg["files"] = files
        
        conv["messages"].append(msg)
        self._save_conv(conv)
        self._refresh_chat_display()

        # Prepare tools
        tools = self.tool_executor.registry.get_tool_definitions()
        if self.settings_data.get("mcp_enabled", True):
            tools += self.mcp_manager.get_tool_definitions()

        if is_agentic:
            self._run_agentic(conv, tools, text, images, files)
        else:
            self._start_generation(conv, tools, text, images, files, bypass_rag)

    def _run_agentic(self, conv, tools, text, images, files):
        """Autonomous tool execution loop."""
        gen_params = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS)
        system_prompt = conv.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        
        # Inject long-term memory
        memory_context = self.tool_executor.memory.get_context_string()
        if memory_context:
            system_prompt = f"{system_prompt}\n\n{memory_context}"
            
        # Inject project-specific rules
        project_instructions = self.project_rules.get_system_instructions()
        if project_instructions:
            system_prompt += project_instructions

        self._agentic_loop = AgenticLoop(
            model=self.model_combo.currentText() or DEFAULT_MODEL,
            messages=conv["messages"],
            system_prompt=system_prompt,
            tools=tools,
            agent=self.agent,
            mcp_manager=self.mcp_manager,
            settings=self.settings_data,
            gen_params=gen_params
        )
        
        # Connect signals
        self._agentic_loop.token_received.connect(lambda t: self._on_token(t, 0)) # Default to pane 0
        self._agentic_loop.tool_executing.connect(self._inject_tool_status)
        self._agentic_loop.tool_result.connect(lambda name, result: self._inject_tool_status(name, {}, status="done"))
        self._agentic_loop.finished.connect(self._on_agentic_done)
        self._agentic_loop.error_occurred.connect(self._on_worker_error)
        
        # Initialize streaming display data
        self._streaming_data[0] = {
            "text": "",
            "tokens": 0,
            "start_time": time.time(),
            "dirty": False,
            "initialized": False,
            "flushed_text": ""
        }
        
        self._active_stream_conv = conv
        self._active_stream_tab_index = self.chat_tabs.currentIndex()
        self._set_streaming_state(True)
        self._stream_timer.start()
        
        self._agentic_loop.start()

    def _on_agentic_done(self, final_text, all_messages, stats):
        """Called when AgenticLoop finishes its run."""
        self._set_streaming_state(False)
        self._stream_timer.stop()
        
        if self._active_stream_conv:
            # Update history with all messages from the loop
            self._active_stream_conv["messages"] = all_messages
            self._save_conv(self._active_stream_conv)
            self._refresh_chat_display()
            
        self.status_label.setText(f"Agentic Finished. {stats.get('total_duration', '')}")
        log.info(f"Agentic loop finished: {stats}")

    def _start_generation(self, conv, tools, text, images, files, bypass_rag=False):
        """Legacy single-shot generation."""
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

        # Web Grounding: Automatic search if enabled
        if not bypass_rag and text and self.input_widget.web_search_btn.isChecked():
            self.status_label.setText(f"Searching web for '{text[:20]}...'")
            QApplication.processEvents()
            search_results = self.tool_executor._web_search(text)
            if search_results and "Search error" not in search_results:
                content += f"\n\n---\nWeb Search Results:\n{search_results}"
                log.info("Injected web search results for grounding")
            self.status_label.setText("RAG Ready" if self.workspace_index else "Ready")

        # Apply Privacy Firewall if enabled
        if self.settings_data.get("privacy_firewall", False):
            content = self.privacy_filter.mask(content)

        if text: # Don't add empty user messages for tool continuations
            msg = {
                "role": "user",
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if images: msg["images"] = images
            conv["messages"].append(msg)

        self._render_chat(self.chat_tabs.currentIndex())
        self.input_widget.set_streaming(True)

        self._streaming_text = ""
        self._streaming_dirty = False
        self._streaming_start_time = 0
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
        
        # Inject project-specific rules
        project_instructions = self.project_rules.get_system_instructions()
        if project_instructions:
            system_prompt += project_instructions
            
        mcp_tools = self.mcp_manager.get_tool_definitions()
        if mcp_tools:
            tool_names = [t["function"]["name"] for t in mcp_tools]
            mcp_hint = "\n\nYou have access to external MCP tools. IMPORTANT RULES:\n"
            if any("github" in n for n in tool_names):
                gh_user = self.settings_data.get("github_username", "")
                if gh_user:
                    mcp_hint += f"- The GitHub account owner is '{gh_user}'. This is NOT optional context — use it.\n"
                    mcp_hint += f"- For 'my repos': call mcp__github__search_repositories with query 'user:{gh_user}'\n"
                    mcp_hint += f"- For 'my issues/PRs': call mcp__github__search_issues with query 'author:{gh_user}'\n"
                    mcp_hint += f"- For 'list my repos': call mcp__github__search_repositories with query 'user:{gh_user}' — do NOT ask for the username, you already have it.\n"
                else:
                    mcp_hint += "- When asked about 'my repos', call mcp__github__get_me first to get the username, then search with that.\n"
            mcp_hint += "- ALWAYS call the relevant tool. NEVER say you can't do something if a tool exists for it.\n"
            mcp_hint += "- NEVER ask the user for information you can look up with a tool call.\n"
            system_prompt = (system_prompt + mcp_hint) if system_prompt else mcp_hint.strip()

        # Multi-worker management
        self._workers = {}
        self._streaming_data = {}
        
        split_view = None
        tab_widget = self.chat_tabs.widget(self.chat_tabs.currentIndex())
        if tab_widget:
            split_view = tab_widget.findChild(SplitViewWidget)
        
        sync_enabled = self.input_widget.sync_btn.isChecked()
        targets = []
        
        if sync_enabled and split_view:
            for i, pane in enumerate(split_view.panes):
                targets.append((i, pane.model_combo.currentText() or DEFAULT_MODEL))
        else:
            targets.append((0, self.model_combo.currentText() or DEFAULT_MODEL))

        system_prompt = conv.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        
        # Inject long-term memory
        memory_context = self.tool_executor.memory.get_context_string()
        if memory_context:
            system_prompt = f"{system_prompt}\n\n{memory_context}"
        # ... (MCP/Tool logic handled above) ...

        for pane_idx, m_name in targets:
            worker = WorkerFactory(
                m_name,
                conv["messages"],
                system_prompt,
                gen_params,
                tools=tools,
                settings=self.settings_data
            )
            worker.token_received.connect(lambda token, p=pane_idx: self._on_token(token, p))
            worker.tool_calls_received.connect(self._on_tool_calls)
            worker.response_finished.connect(lambda text, stats, p=pane_idx, m=m_name: self._on_response_done(text, stats, p, m))
            worker.truncated.connect(self._on_response_truncated)
            worker.error_occurred.connect(self._on_worker_error)
            
            self._workers[pane_idx] = worker
            self._streaming_data[pane_idx] = {
                "text": "",
                "tokens": 0,
                "start_time": time.time(),
                "dirty": False,
                "initialized": False,
                "flushed_text": ""
            }
            worker.start()

        self._active_stream_conv = conv
        self._active_stream_tab_index = self.chat_tabs.currentIndex()
        self._set_streaming_state(True)
        self._stream_timer.start()
        
        # Update context guess
        total_text = "".join([m.get("content", "") for m in conv["messages"]])
        tokens = estimate_tokens(total_text)
        max_ctx = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS).get("num_ctx", 4096)
        self.context_label.setText(f"Context: ~{tokens}/{max_ctx}")

    def _set_streaming_state(self, streaming):
        self.input_widget.set_streaming(streaming)

    def _inject_tool_status(self, name, args, status="running"):
        """Inject a live tool status block into the chat via JS."""
        idx = self._active_stream_tab_index if self._active_stream_tab_index >= 0 else self.chat_tabs.currentIndex()
        if idx < 0:
            return
        tab_widget = self.chat_tabs.widget(idx)
        if not tab_widget:
            return
        view = tab_widget.findChild(QWebEngineView)
        if not view:
            return
        import html as html_mod
        display_name = name.replace("mcp__github__", "github/").replace("mcp__", "")
        args_summary = ""
        if isinstance(args, dict):
            parts = []
            for k, v in args.items():
                val = str(v)
                if len(val) > 40:
                    val = val[:37] + "..."
                parts.append(f"{k}={val}")
            args_summary = ", ".join(parts)[:80]
        args_summary = html_mod.escape(args_summary).replace("'", "\\'")
        display_name = html_mod.escape(display_name).replace("'", "\\'")

        if status == "running":
            icon_cls = "tool-wait"
            icon_char = "&#9679;"
            extra_cls = " tool-running"
        elif status == "done":
            icon_cls = "tool-ok"
            icon_char = "&#10003;"
            extra_cls = ""
        else:
            icon_cls = "tool-err"
            icon_char = "&#10007;"
            extra_cls = ""

        js = (
            f"(function(){{"
            f"var old=document.getElementById('tool-live');if(old)old.remove();"
            f"var d=document.createElement('div');"
            f"d.id='tool-live';"
            f"d.className='tool-block{extra_cls}';"
            f"d.innerHTML='"
            f"<div class=\"tool-header\">"
            f"<span class=\"tool-icon {icon_cls}\">{icon_char}</span>"
            f"<span class=\"tool-name\">{display_name}</span>"
            f"<span class=\"tool-summary\">{args_summary}</span>"
            f"</div>';"
            f"document.body.appendChild(d);"
            f"window.scrollTo(0,document.body.scrollHeight);"
            f"}})();"
        )
        view.page().runJavaScript(js)

    def _remove_tool_live(self):
        idx = self._active_stream_tab_index if self._active_stream_tab_index >= 0 else self.chat_tabs.currentIndex()
        if idx < 0:
            return
        tab_widget = self.chat_tabs.widget(idx)
        if not tab_widget:
            return
        view = tab_widget.findChild(QWebEngineView)
        if view:
            view.page().runJavaScript("var el=document.getElementById('tool-live');if(el)el.remove();")

    def _on_tool_calls(self, tool_calls):
        for w in self._workers.values():
            if w.isRunning():
                w.stop()
                w.wait()

        tool_names = [tc["function"]["name"] for tc in tool_calls]
        friendly = [n.replace("mcp__github__", "github/").replace("_", " ") for n in tool_names]
        self.status_label.setText(f"Running: {', '.join(friendly)}")
        self.tool_progress.show()
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
                        if hasattr(dialog, 'apply_theme'): dialog.apply_theme(self._current_theme)
                        if dialog.exec_() == QDialog.Accepted:
                            approved = True
                    else:
                        approved = True
            else:
                if self.auto_exec_check.isChecked():
                    approved = True
                else:
                    dialog = ToolApprovalDialog(self, name, args)
                    if hasattr(dialog, 'apply_theme'): dialog.apply_theme(self._current_theme)
                    if dialog.exec_() == QDialog.Accepted:
                        approved = True

            if approved:
                self.status_label.setText(f"Running tool: {name}...")
                self._inject_tool_status(name, args, "running")
                QApplication.processEvents()

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

                self._remove_tool_live()
                results.append({"id": tc.get("id"), "content": res})
                self._start_indexing() # Always re-index after tool use to stay in sync
                if name == "write_file":
                    self.workspace_panel.refresh()
            else:
                self._remove_tool_live()
                results.append({"id": tc.get("id"), "content": "User rejected the tool execution."})
        
        conv = self._active_stream_conv or self.current_conv
        if not conv:
            self.tool_progress.hide()
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
            
            self.tool_progress.hide()
            self.status_label.setText("Processing results...")
            self._send_message("", bypass_rag=True)

    def _on_token(self, token, pane_index=0):
        if pane_index not in self._streaming_data:
            self._streaming_data[pane_index] = {
                "text": "", "tokens": 0, "start_time": time.time(),
                "dirty": False, "initialized": False, "flushed_text": ""
            }
        data = self._streaming_data[pane_index]
        data["text"] += token
        data["tokens"] += 1
        data["dirty"] = True

    def _update_streaming_display(self):
        idx = self._active_stream_tab_index if self._active_stream_tab_index >= 0 else self.chat_tabs.currentIndex()
        if idx < 0: return
        tab_widget = self.chat_tabs.widget(idx)
        if not tab_widget: return
        split_view = tab_widget.findChild(SplitViewWidget)
        conv = self._active_stream_conv or self.current_conv
        if not conv: return

        any_dirty = any(d.get("dirty", False) for d in self._streaming_data.values())
        if not any_dirty: return

        from PyQt5.QtCore import QUrl
        import html as html_mod

        for pane_idx, data in self._streaming_data.items():
            if not data.get("dirty", False): continue
            data["dirty"] = False

            elapsed = time.time() - data.get("start_time", time.time())
            tps = data["tokens"] / elapsed if elapsed > 0 else 0
            self.status_label.setText(f"Streaming: {data['tokens']} tokens \u00b7 {tps:.1f} tok/s")

            view = None
            if split_view and pane_idx < len(split_view.panes):
                view = split_view.panes[pane_idx].view
            elif pane_idx == 0:
                view = tab_widget.findChild(QWebEngineView)
            
            if not view: continue

            if not data.get("initialized", False):
                data["initialized"] = True
                m_name = split_view.panes[pane_idx].model_combo.currentText() if split_view else self.model_combo.currentText()
                preview_msgs = list(conv["messages"]) + [{
                    "role": "assistant",
                    "content": '<pre id="streaming-content" style="white-space:pre-wrap;font-family:inherit;margin:0;background:transparent;border:none;padding:0;"></pre>',
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }]
                html = self.renderer.build_html(preview_msgs, conv.get("history", []), model_name=m_name)
                html = html.replace('&lt;pre id=&quot;streaming-content&quot;', '<pre id="streaming-content"') \
                           .replace('&lt;/pre&gt;', '</pre>')
                view.setHtml(html, QUrl("qrc:/"))
            else:
                new_text = data["text"][len(data.get("flushed_text", "")):]
                if new_text:
                    escaped = html_mod.escape(new_text).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")
                    view.page().runJavaScript(f"appendStreamToken('{escaped}');")
                    data["flushed_text"] = data["text"]
                    
                    # Hot Reload Canvas if active
                    if lang_lower := re.search(r'```(\w+)', data["text"]):
                        lang = lang_lower.group(1).lower()
                        if lang in ('html', 'svg', 'react', 'jsx', 'tsx'):
                            content_match = re.search(r'```(?:\w+)\n(.*?)(?:```|$)', data["text"], re.DOTALL)
                            if content_match:
                                self._maybe_hot_reload_canvas(content_match.group(1), f"Live Preview: {lang.upper()}")

        # Use pane 0 as the reference for context estimation/labels
        primary_data = self._streaming_data.get(0, next(iter(self._streaming_data.values())))
        if primary_data.get("tokens", 0) % 50 == 0:
            total_text = "".join(m.get("content", "") for m in conv["messages"]) + primary_data.get("text", "")
            tokens = estimate_tokens(total_text)
            max_ctx = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS).get("num_ctx", 4096)
            pct = min(100, int(tokens / max_ctx * 100))
            self.context_label.setText(f"Context: ~{tokens}/{max_ctx} ({pct}%)")
            self.sum_action.setText(f"Summarize ({pct}% Context)")

    def _on_screenshot_triggered(self):
        self.screenshot_widget = ScreenCaptureWidget()
        self.screenshot_widget.screenshot_captured.connect(self.input_widget.add_image_pixmap)
        self.screenshot_widget.show()

    def _toggle_zen_mode(self):
        self._zen_mode = not self._zen_mode
        self.activity_bar.setVisible(not self._zen_mode)
        self.sidebar_container.setVisible(not self._zen_mode)
        # Collapse workspace panel if it's there
        if hasattr(self, "workspace_panel"):
            self.workspace_panel.setVisible(not self._zen_mode)
        
        if self._zen_mode:
            self.status_label.setText("Focus Mode: ON")
        else:
            self.status_label.setText("Focus Mode: OFF")

    def _on_clipboard_changed(self):
        mime = self._clipboard.mimeData()
        if mime.hasImage():
            self.status_label.setText("📋 Image detected in clipboard. Use /attach or Ctrl+V to add.")
        elif mime.hasText():
            text = mime.text()
            # Simple heuristic for code
            if "def " in text or "class " in text or "import " in text or "{" in text:
                self.status_label.setText("📋 Code detected in clipboard. Use /attach or Ctrl+V to add.")

    def _on_response_done(self, full_text, stats, pane_idx=0, model_name=None):
        conv = self._active_stream_conv or self.current_conv
        if not conv: return

        eval_count = stats.get("eval_count", 0)
        eval_duration = stats.get("eval_duration", 0)
        data = self._streaming_data.get(pane_idx, {})
        duration_ms = int(eval_duration / 1_000_000) if eval_duration else int((time.time() - data.get("start_time", time.time())) * 1000)

        msg = {
            "id": str(uuid.uuid4()),
            "parent_id": conv["messages"][-1].get("id") if conv["messages"] else None,
            "role": "assistant",
            "content": full_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model_name or self.model_combo.currentText(),
            "tokens": eval_count or data.get("tokens", 0),
            "duration_ms": duration_ms,
        }
        
        # Branching logic: If multiple models finish, they all become siblings of the same user message
        if "history" not in conv: conv["history"] = []
        conv["history"].append(msg)
        
        # Add to messages if last message is user prompt OR tool results (post-tool continuation)
        if conv["messages"] and conv["messages"][-1].get("role") in ("user", "tool_results"):
            conv["messages"].append(msg)
        
        self.store.save(conv)
        self.sidebar.refresh(select_id=conv["id"])

        # Log analytics
        m_name = model_name or self.model_combo.currentText()
        provider = "Ollama"
        if "gpt" in m_name.lower(): provider = "OpenAI"
        elif "claude" in m_name.lower(): provider = "Anthropic"
        
        in_tokens = stats.get("prompt_eval_count") or stats.get("prompt_tokens") or stats.get("input_tokens") or 0
        out_tokens = stats.get("eval_count") or stats.get("completion_tokens") or stats.get("output_tokens") or 0
        
        analytics_manager.log_usage(m_name, provider, in_tokens, out_tokens, duration_ms)
        if self.analytics_sidebar.isVisible():
            self.analytics_sidebar.refresh()
            
        # Refresh branch tree if visible
        if self.branch_tree_sidebar.isVisible() and self.current_conv:
            self.branch_tree_sidebar.refresh(self.current_conv.get("history", []), self.current_conv.get("messages", [{}])[-1].get("id"))

        if pane_idx in self._workers:
            del self._workers[pane_idx]
            
        if self._consensus_active:
            self._consensus_responses[m_name] = full_text
            # If all expected workers are done
            expected = len(self._streaming_data) # targets count from _send_message
            if len(self._consensus_responses) >= expected:
                QTimer.singleShot(500, self._synthesize_consensus)

        if not self._workers:
            self._stream_timer.stop()
            self.input_widget.set_streaming(False)

        if self._active_stream_tab_index >= 0:
            self._render_chat(self._active_stream_tab_index)
        else:
            self._render_chat()
        self.input_widget.set_streaming(False)

        # Auto-Read implementation
        if self.input_widget.voice_btn.isChecked() and full_text:
            # Strip markdown for cleaner TTS
            clean_text = re.sub(r'```.*?```', '', full_text, flags=re.DOTALL)
            clean_text = re.sub(r'[*_#`]', '', clean_text)
            self.voice_manager.speak(clean_text)

        # Hands-free loop: Trigger recording after response finishes (if enabled)
        tps = msg["tokens"] / (duration_ms / 1000) if duration_ms > 0 else 0
        self.status_label.setText(f"Done: {msg['tokens']} tokens \u00b7 {tps:.1f} tok/s \u00b7 {duration_ms/1000:.1f}s")

        # Auto-Summary logic
        if len(conv.get("messages", [])) >= 10 and not conv.get("summary"):
            self._request_summary(conv)

        total_text = "".join(m.get("content", "") for m in conv["messages"])
        tokens = estimate_tokens(total_text)
        max_ctx = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS).get("num_ctx", 4096)
        pct = min(100, int(tokens / max_ctx * 100))
        self.context_label.setText(f"Context: ~{tokens}/{max_ctx} ({pct}%)")
        self.sum_action.setText(f"Summarize ({pct}% Context)")

        # Auto-title after first real assistant response (skip empty tool-call-only messages)
        real_assistant = [m for m in conv["messages"] if m["role"] == "assistant" and m.get("content", "").strip()]
        log.debug(f"Auto-title check: {len(real_assistant)} real assistant msgs, title='{conv.get('title')}'")
        if len(real_assistant) >= 1 and conv.get("title") == "New Chat":
            self._auto_title(conv)

        # Smart Auto-Tagging (F12) - Trigger after first assistant turn or every 5 user messages
        user_msgs = [m for m in conv["messages"] if m["role"] == "user"]
        assistant_msgs = [m for m in conv["messages"] if m["role"] == "assistant"]
        if (len(assistant_msgs) == 1 or (len(user_msgs) > 0 and len(user_msgs) % 5 == 0)) and not conv.get("tags"):
            self._auto_tag_conversation()

        self._active_stream_conv = None
        self._active_stream_tab_index = -1

        if not self.isActiveWindow() and self.settings_data.get("notifications", True):
            self._notify_completion(conv.get("title", "Chat"), msg["tokens"])

        queued = self.input_widget.pop_queued_message()
        if queued:
            self._send_message(queued["text"], queued.get("images"), queued.get("files"))

    def _on_response_truncated(self):
        if not self.settings_data.get("auto_continue", True):
            self.status_label.setText("Response truncated. Auto-continue is disabled in settings.")
            return
        max_continues = self.settings_data.get("auto_continue_max", 3)
        if self._auto_continue_count >= max_continues:
            log.warning(f"Max auto-continue reached ({max_continues}). Stopping.")
            self.status_label.setText(f"Response truncated — auto-continue limit ({max_continues}) reached.")
            self._auto_continue_count = 0
            return

        self._auto_continue_count += 1
        log.info(f"Auto-continuing truncated response (Attempt {self._auto_continue_count}/{max_continues})")
        self.status_label.setText(f"Auto-continuing... ({self._auto_continue_count}/{max_continues})")

        continuation = "Please continue from where you left off."
        self._send_message(continuation, bypass_rag=True)

    def _run_consensus(self, prompt):
        """Run a prompt against multiple models in parallel for consensus."""
        if not self.current_conv:
            self._new_chat()
        
        # Determine target models
        available = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        if not available:
            self.status_label.setText("No models available for consensus")
            return
            
        # Select up to 3 models: 1. Current, 2. A GPT model if available, 3. A Claude model if available
        # If not, just take the first 3 unique ones
        targets = [self.model_combo.currentText()]
        
        gpt_models = [m for m in available if "gpt" in m.lower() and m not in targets]
        if gpt_models: targets.append(gpt_models[0])
        
        claude_models = [m for m in available if "claude" in m.lower() and m not in targets]
        if claude_models: targets.append(claude_models[0])
        
        while len(targets) < 3 and len(targets) < len(available):
            for m in available:
                if m not in targets:
                    targets.append(m)
                    break
        
        self.status_label.setText(f"Consensus: Running {len(targets)} models...")
        
        # Configure SplitView
        idx = self.chat_tabs.currentIndex()
        tab_widget = self.chat_tabs.widget(idx)
        split_view = tab_widget.findChild(SplitViewWidget)
        
        if not split_view:
            # Rebuild tab with SplitView if it's a simple QWebEngineView tab
            self._add_chat_tab(self.current_conv) # This creates a SplitView by default now
            idx = self.chat_tabs.currentIndex()
            tab_widget = self.chat_tabs.widget(idx)
            split_view = tab_widget.findChild(SplitViewWidget)
        
        if split_view:
            # Clear extra panes or add new ones
            while len(split_view.panes) < len(targets):
                split_view.add_pane(available)
            while len(split_view.panes) > len(targets):
                split_view.remove_pane(len(split_view.panes)-1)
            
            # Set target models for each pane
            for i, model_name in enumerate(targets):
                split_view.panes[i].model_combo.setCurrentText(model_name)
            
            # Turn on SYNC mode for the input widget automatically
            self.input_widget.sync_btn.setChecked(True)
            self._on_sync_toggled(True)
            
            # Send the message
            self._consensus_active = True
            self._consensus_responses = {}
            self._send_message(prompt)

    def _synthesize_consensus(self):
        """Analyze responses from multiple models and provide a synthesized conclusion."""
        if not self._consensus_responses:
            return

        self._consensus_active = False
        self.status_label.setText("Synthesizing consensus...")

        # Construct synthesis prompt
        summary = "You are a consensus synthesizer. Below are responses from different AI models to the same user query. Compare them, identify key points of agreement and disagreement, and provide a final, high-quality synthesized response.\n\n"
        
        for m_name, text in self._consensus_responses.items():
            summary += f"### Model: {m_name}\n{text}\n\n"
        
        summary += "---\nFinal Analysis and Synthesized Response:"

        # Reset split view to normal mode or just append synthesis to chat
        # For now, let's append it as a system message then trigger assistant
        # Actually, let's just trigger a normal assistant response with this as context
        
        self._send_message(summary, bypass_rag=True)

    def _notify_completion(self, title, tokens):
        try:
            if self._tray_icon and self._tray_icon.isVisible():
                self._tray_icon.showMessage(
                    APP_NAME, f"Response complete: {tokens} tokens in '{title}'",
                    QSystemTrayIcon.Information, 3000
                )
        except Exception as e:
            log.debug(f"Tray notification failed: {e}")

    def _on_worker_error(self, err_msg):
        if self._stream_timer.isActive():
            self._stream_timer.stop()
        self.input_widget.set_streaming(False)
        self._set_summarize_running(False)
        self._active_stream_conv = None
        self._active_stream_tab_index = -1
        self.tool_progress.hide()
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

        if cmd == "/run":
            if not arg:
                self.status_label.setText("Usage: /run <task_id>")
                return
            self.build_manager.run_task(arg)
            return

        if cmd == "/search":
            if not arg:
                self.status_label.setText("Usage: /search <query>")
                return
            results = self.semantic_indexer.search(arg)
            if results:
                info = "\n".join(f"- {r['path']} (score: {r['score']:.2f})" for r in results)
                QMessageBox.information(self, "Semantic Search Results", f"Found relevant snippets in:\n{info}")
            else:
                self.status_label.setText("No semantic results found")
        elif cmd == "/index":
            self.status_label.setText("Starting semantic indexing...")
            self._indexer_thread = SemanticWorkspaceIndexer(self.workspace_root, self.semantic_indexer)
            self._indexer_thread.progress.connect(lambda cur, tot: self.status_bar.showMessage(f"Indexing: {cur}/{tot} files...", 2000))
            self._indexer_thread.finished.connect(lambda: self.status_label.setText("Semantic indexing complete!"))
            self._indexer_thread.start()
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
                self._show_conv_stats()
        elif cmd == "/terminal":
            if not self.terminal.isVisible():
                self._toggle_terminal()
            self.terminal.input_line.setFocus()
            self.status_label.setText("Terminal focused")
        elif cmd == "/diff":
            # Logic to open the diff view for the current active file
            cur_tab = self.editor_tabs.currentWidget()
            if cur_tab and hasattr(cur_tab, 'file_path'):
                self._diff_active_file(cur_tab.file_path)
            else:
                self.status_label.setText("No active file to diff")
        elif cmd == "/file":
            if arg:
                self._open_file_by_path(arg)
            else:
                self.status_label.setText("Usage: /file <path>")
        elif cmd == "/help":
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
        elif cmd == "/rag":
            if not hasattr(self, '_rag_enabled'):
                self._rag_enabled = True
            self._rag_enabled = not self._rag_enabled
            state = "ON" if self._rag_enabled else "OFF"
            self.status_label.setText(f"RAG context injection: {state}")
        elif cmd == "/autocomplete":
            self._on_autocomplete_toggled()
            state = "ON" if self._autocomplete_enabled else "OFF"
            self.status_label.setText(f"AI Autocomplete: {state}")
        elif cmd == "/consensus":
            if not arg:
                self.status_label.setText("Usage: /consensus <prompt>")
                return
            self._run_consensus(arg)
        elif cmd == "/memory":
            if arg == "clear":
                self.tool_executor.memory.clear()
                self.status_label.setText("Memory cleared")
            else:
                ctx = self.tool_executor.memory.get_context_string()
                if ctx:
                    msg_box = QMessageBox(self)
                    msg_box.setWindowTitle("Persistent Memory")
                    msg_box.setText(ctx)
                    msg_box.setStandardButtons(QMessageBox.Ok)
                    clear_btn = msg_box.addButton("Clear All", QMessageBox.DestructiveRole)
                    msg_box.exec_()
                    if msg_box.clickedButton() == clear_btn:
                        self.tool_executor.memory.clear()
                        self.status_label.setText("Memory cleared")
                else:
                    self.status_label.setText("No memories stored yet")
        elif cmd == "/rules":
            rules_text = self.project_rules.get_system_instructions()
            if rules_text:
                QMessageBox.information(self, "Active Project Rules", rules_text)
            else:
                self.status_label.setText("No project-specific rules found (.synapserc, .cursorrules, etc.)")
        elif cmd == "/help":
            help_text = (
                "/clear - New chat\n/model <name> - Switch model\n/system - Edit system prompt\n"
                "/search <query> - Search workspace\n/summarize - Summarize to free context\n"
                "/export [md|html|json|pdf] - Export conversation\n/stats - Show conversation stats\n"
                "/mcp [name] - Show MCP status or toggle a server\n"
                "/rag - Toggle RAG context injection\n"
                "/memory [clear] - View or clear persistent memory\n"
                "/rules - Show active project-specific rules\n"
                "/autocomplete - Toggle AI code completion\n"
                "/youtube <url> - Fetch YouTube transcript for RAG\n"
                "/consensus <prompt> - Query multiple models side-by-side\n"
                "/help - Show this help\n\n"
                "Shortcuts:\n"
                "Ctrl+N: New chat | Ctrl+B: Toggle sidebar | Ctrl+L: Focus input\n"
                "Ctrl+S: Save file | Ctrl+W: Close tab | Ctrl+Tab/Shift+Tab: Switch tabs\n"
                "Ctrl+Shift+P: Command palette | Ctrl+Shift+F: Search conversations\n"
                "Ctrl+Shift+D: Duplicate chat\n"
                "Ctrl+Shift+H: Search & replace workspace | Ctrl+`: Toggle terminal\n"
                "Ctrl+,: Settings | Ctrl+I: Import | Ctrl+TextZoom: Ctrl+=/-/0\n"
                "Ctrl+V: Paste image | @ in input: Mention workspace file"
            )
            QMessageBox.information(self, "Slash Commands & Shortcuts", help_text)
        else:
            plugin_result = self.plugin_manager.handle_slash(cmd.lstrip("/"), arg)
            if plugin_result:
                self.status_label.setText(str(plugin_result))
            else:
                self.status_label.setText(f"Unknown command: {cmd}")

    def _open_file_by_path(self, path):
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path) and os.path.isfile(abs_path):
            editor = self.editor_tabs.open_file(abs_path)
            # Enable LSP for this file
            if editor:
                editor.set_lsp_manager(self.lsp_manager, abs_path)
                editor.autocomplete.enabled = self._autocomplete_enabled
            
            self.status_bar.showMessage(f"Opened {abs_path}", 3000)
        else:
            self.status_label.setText(f"File not found: {path}")

    def _diff_active_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                old_content = f.read()
            
            # Get current editor content
            editor = self.editor_tabs.currentWidget().findChild(CodeEditor)
            if editor:
                new_content = editor.toPlainText()
                dialog = DiffViewDialog(self, str(file_path), old_content, new_content)
                dialog.exec_()
        except Exception as e:
            self.status_label.setText(f"Diff failed: {e}")

    def _expand_file_mentions(self, text):
        import re as _re
        mentions = _re.findall(r'@([a-zA-Z0-9_\-\./\+]+)', text)
        if not mentions:
            return text
            
        ws = self.workspace_panel.get_workspace_dir()
        if not ws:
            return text
            
        appended = []
        for mention in set(mentions):
            found = False
            # 1. Try direct filename match in existing index
            if self.workspace_index:
                for indexed_path in self.workspace_index:
                    if mention == indexed_path or indexed_path.endswith("/" + mention) or indexed_path.endswith("\\" + mention):
                        full = ws / indexed_path
                        try:
                            content = full.read_text(errors='replace')[:20000]
                            appended.append(f"\n\n--- File: {indexed_path} ---\n```\n{content}\n```")
                            found = True
                            break
                        except: pass
            
            # 2. Try semantic match if not found directly
            if not found:
                results = self.semantic_indexer.search(mention, top_k=1)
                if results:
                    best = results[0]
                    indexed_path = best["path"]
                    full = ws / indexed_path
                    try:
                        content = full.read_text(errors='replace')[:20000]
                        appended.append(f"\n\n--- File: {indexed_path} (Semantic Match) ---\n```\n{content}\n```")
                        log.info(f"Injected semantic @mention: {indexed_path}")
                    except: pass

        if appended:
            text += "\n".join(appended)
        return text

    def _search_workspace(self, query):
        if not self.workspace_index:
            return []
        
        results = search_index(self.workspace_index, query)
        snippets = []
        for r in results:
            path = r["path"]
            content = r.get("content", "No snippet available.")
            score = r.get("score", 0.0)
            snippets.append(f"File: {path} (Match Score: {score:.2f})\nRelevant Context:\n{content}\n")
        
        # GraphRAG Augmentation (G1)
        if self._rag_enabled:
            try:
                graph_context = self.graph_rag.search(query, results)
                if graph_context:
                    snippets.append(f"\n--- Deep Relationship Knowledge ---\n{graph_context}")
            except Exception as ge:
                log.warning(f"GraphRAG search failed: {ge}")
                
        return snippets

    def _on_chat_action(self, action, index_or_data):
        if not self.current_conv:
            return

        # Parse index and optional filename
        code_idx = -1
        filename = None
        if isinstance(index_or_data, str) and "/" in index_or_data:
            parts = index_or_data.split("/")
            try:
                code_idx = int(parts[0])
                filename = parts[1] if len(parts) > 1 else None
            except:
                pass
        else:
            try:
                code_idx = int(index_or_data)
            except:
                pass

        if action == "applycode" or action == "proposecode":
            self._propose_code_block(code_idx, auto_apply=(action == "applycode"), forced_filename=filename)
        elif action == "savecode":
            self._propose_code_block(code_idx, auto_apply=True, forced_filename=filename)
        elif action == "runcode":
            self._run_code_block(code_idx)
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
        elif action == "previewartifact":
            self._preview_artifact(index)
        elif action == "feedback":
            try:
                parts = str(index).split("/")
                if len(parts) >= 2:
                    m_idx = int(parts[0])
                    rating = parts[1]
                    if 0 <= m_idx < len(self.current_conv["messages"]):
                        self.current_conv["messages"][m_idx]["feedback"] = rating
                        self.store.save(self.current_conv)
                        self.status_label.setText(f"Feedback recorded: {rating}")
                        self._render_chat()
            except Exception as e:
                log.error(f"Error handling feedback: {e}")
        elif action == "navbranch":
            idx, direction = str(index).split("/", 1)
            self._on_navigate_branch(int(idx), direction)
        elif action == "reorder":
            try:
                parts = str(index).split("/")
                if len(parts) >= 2:
                    from_idx = int(parts[0])
                    to_idx = int(parts[1])
                    msgs = self.current_conv["messages"]
                    if 0 <= from_idx < len(msgs) and 0 <= to_idx < len(msgs) and from_idx != to_idx:
                        msg = msgs.pop(from_idx)
                        msgs.insert(to_idx, msg)
                        self.store.save(self.current_conv)
                        self._render_chat()
                        self.status_label.setText(f"Message moved from {from_idx} to {to_idx}")
            except Exception as e:
                log.error(f"Reorder error: {e}")
        elif action == "conv_stats":
            self._show_conv_stats()

    def _get_code_blocks(self):
        """Helper to collect all code blocks in the current conversation."""
        if not self.current_conv:
            return []
        all_blocks = []
        for msg in self.current_conv["messages"]:
            if msg.get("role") == "assistant":
                # Find both fenced code blocks and artifact-like patterns
                matches = list(re.finditer(r'```(\w*)\n(.*?)\n```', msg["content"], re.DOTALL))
                for m in matches:
                    all_blocks.append((m.group(1), m.group(2)))
        return all_blocks

    def _run_code_block(self, code_block_index):
        all_blocks = self._get_code_blocks()
        if code_block_index < 0 or code_block_index >= len(all_blocks):
            self.status_label.setText("Code block not found")
            return
        lang, code = all_blocks[code_block_index]
        
        if lang.lower() in ('python', 'python3', 'py'):
            self.status_label.setText("Running Python...")
            res = self.code_executor.execute_python(code)
            
            output = f"Exit code {res['exit_code']}\n"
            if res['stdout']:
                output += f"STDOUT:\n{res['stdout']}\n"
            if res['stderr']:
                output += f"STDERR:\n{res['stderr']}\n"
            
            content = f"```\n$ Run {lang} code block\n{output}\n```"
            if res['images']:
                for img_b64 in res['images']:
                    content += f"\n![Plot](data:image/png;base64,{img_b64})\n"
                    
            msg = {
                "role": "assistant",
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model": "code-execution",
            }
            self.current_conv["messages"].append(msg)
            self.store.save(self.current_conv)
            self._render_chat()
            self.status_label.setText("Execution finished")
            
        elif lang.lower() in ('bash', 'sh'):
            self.status_label.setText("Running Bash...")
            ws = self.workspace_panel.get_workspace_dir()
            try:
                result = subprocess.run(
                    ["bash", "-c", code], capture_output=True, text=True, timeout=30,
                    cwd=str(ws) if ws else None
                )
                output = (result.stdout + "\n" + result.stderr).strip() or "(no output)"
                exec_msg = f"```\n$ Run {lang} code block\nExit code: {result.returncode}\n\n{output}\n```"
                self.current_conv["messages"].append({
                    "role": "assistant",
                    "content": exec_msg,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model": "code-execution",
                })
                self.store.save(self.current_conv)
                self._render_chat()
                self.status_label.setText("Execution finished")
            except Exception as e:
                self.status_label.setText(f"Run failed: {e}")
        else:
            self.status_label.setText(f"Cannot run {lang} code blocks")

    def _on_template_applied(self, content):
        self.input_widget.set_text(content)
        self.input_widget.focus_input()
        self.status_label.setText("Template applied.")

    def _preview_artifact(self, code_block_index):
        """Show the selected code block in a side-panel Canvas."""
        all_blocks = self._get_code_blocks()
        if code_block_index < 0 or code_block_index >= len(all_blocks):
            self.status_label.setText("Artifact not found")
            return
        
        lang, code = all_blocks[code_block_index]
        title = f"Preview: {lang.upper()}"
        
        # Find or create Canvas tab
        canvas = None
        for i in range(self.editor_tabs.count()):
            tab = self.editor_tabs.widget(i)
            if isinstance(tab, CanvasWidget):
                canvas = tab
                self.editor_tabs.setCurrentIndex(i)
                break
        
        if not canvas:
            canvas = CanvasWidget()
            idx = self.editor_tabs.addTab(canvas, "Canvas")
            self.editor_tabs.setCurrentIndex(idx)
            
        if canvas:
            canvas.set_content(code, title, content_type=lang)
            # Ensure focus stays on the editor area if it was there
            self.status_label.setText(f"Showing {lang.upper()} artifact in Canvas")

    def _maybe_hot_reload_canvas(self, code, title):
        """Update any open Canvas with new content if active."""
        for i in range(self.editor_tabs.count()):
            tab = self.editor_tabs.widget(i)
            if isinstance(tab, CanvasWidget):
                tab.set_content(code, title)
                break

    def _edit_message(self, index):
        if not self.current_conv or index < 0 or index >= len(self.current_conv["messages"]):
            return
        msg = self.current_conv["messages"][index]
        if msg["role"] != "user":
            return
        new_text, ok = QInputDialog.getMultiLineText(self, "Edit Message", "Edit:", msg["content"])
        if ok and new_text.strip():
            # Create a new branch
            parent_id = msg.get("parent_id")
            new_msg = {
                "id": str(uuid.uuid4()),
                "parent_id": parent_id,
                "role": "user",
                "content": new_text.strip(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            # Archive current active path to history
            if "history" not in self.current_conv:
                self.current_conv["history"] = []
            for m in self.current_conv["messages"]:
                if not any(h["id"] == m["id"] for h in self.current_conv["history"]):
                    self.current_conv["history"].append(m)
            
            # Truncate to parent and add new message
            self.current_conv["messages"] = self.current_conv["messages"][:index]
            self.current_conv["messages"].append(new_msg)
            self.store.save(self.current_conv)
            
            # Send (this will append the assistant response to the new branch)
            self._trigger_send()

    def _regenerate(self, index):
        if not self.current_conv:
            return
        
        # Ensure current version is in history
        if "history" not in self.current_conv:
            self.current_conv["history"] = []
        for m in self.current_conv["messages"]:
            if not any(h["id"] == m["id"] for h in self.current_conv["history"]):
                self.current_conv["history"].append(m)

        # Pop assistant and trigger send (which adds a new version)
        while self.current_conv["messages"] and self.current_conv["messages"][-1]["role"] == "assistant":
            self.current_conv["messages"].pop()
        
        self._trigger_send(bypass_rag=True)

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

    def _trigger_send(self, bypass_rag=False):
        """Re-send to model using current conversation state (no new user text)."""
        self._render_chat()
        self._send_message("", bypass_rag=bypass_rag)

    def _continue_generation(self):
        if self.current_conv:
            self._send_message("Continue from where you left off.", bypass_rag=True)

    def _duplicate_active_chat(self):
        if self.current_conv:
            self.sidebar._duplicate_chat(self.current_conv["id"])
            self.status_label.setText("Conversation duplicated")

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

    def _fork_from_sidebar(self, conv_id):
        conv = self.store.load(conv_id)
        if not conv or not conv.get("messages"):
            return
        self._load_conversation(conv_id)
        self._fork_conversation(len(conv["messages"]) - 1)

    def _on_navigate_branch(self, index, direction):
        if not self.current_conv:
            return
        
        history = self.current_conv.get("history", [])
        messages = self.current_conv.get("messages", [])
        if index < 0 or index >= len(messages):
            return
            
        current_msg = messages[index]
        parent_id = current_msg.get("parent_id")
        
        # Find all siblings
        siblings = [m for m in history if m.get("parent_id") == parent_id]
        if len(siblings) <= 1:
            return
            
        # Current index in siblings
        try:
            curr_sib_idx = next(i for i, s in enumerate(siblings) if s.get("id") == current_msg.get("id"))
        except StopIteration:
            return
            
        # Next sibling index
        if direction == "next":
            new_sib_idx = (curr_sib_idx + 1) % len(siblings)
        else:
            new_sib_idx = (curr_sib_idx - 1) % len(siblings)
            
        new_msg = siblings[new_sib_idx]
        
        # Build new path
        new_messages = messages[:index]
        new_messages.append(new_msg)
        
        # Follow children (greedy path)
        curr = new_msg
        while True:
            children = [m for m in history if m.get("parent_id") == curr.get("id")]
            if not children:
                break
            curr = children[0] # Pick first child
            new_messages.append(curr)
            
        self.current_conv["messages"] = new_messages
        self.store.save(self.current_conv)
        self._render_chat()

    def _propose_code_block(self, code_block_index, auto_apply=False, forced_filename=None):
        if not self.current_conv:
            return
        
        all_blocks = []
        for msg in self.current_conv["messages"]:
            if msg["role"] == "assistant":
                content = msg["content"]
                # Match blocks and capture context
                matches = list(re.finditer(r'```(\w*)\n(.*?)\n```', content, re.DOTALL))
                for m in matches:
                    start, end = m.span()
                    # Context: 100 chars before the block
                    context = content[max(0, start-100):start]
                    
                    # Search for common path patterns
                    # 1. Look for language block filename pattern: ```python:main.py
                    lang_marker = m.group(1)
                    path_match = re.search(r'[:/]([\w\-/._]+\.\w+)', lang_marker)
                    
                    # 2. Search for common path patterns in context
                    if not path_match:
                        # Improved: Look for paths surrounded by quotes or backticks
                        path_match = re.search(r'[`"\' ]([\w\-/._]+\.\w+)[`"\' ]', context)
                    
                    # 3. Also look for "File: path" or "in path"
                    if not path_match:
                        path_match = re.search(r'(?:[Ff]ile|[Ii]n):?\s*([\w\-/._]+\.\w+)', context)
                    
                    path = path_match.group(1) if path_match else None
                    all_blocks.append((path, m.group(2)))
        
        if code_block_index < 0 or code_block_index >= len(all_blocks):
            self.status_label.setText(f"Code block {code_block_index} not found (Total blocks: {len(all_blocks)})")
            return
            
        detected_path, code = all_blocks[code_block_index]
        workspace = self.workspace_panel.get_workspace_dir()
        
        if not workspace:
            QMessageBox.warning(self, "No Workspace", "Open a folder first.")
            return

        filename = forced_filename or detected_path
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

        # Use FileApplier for smart merging
        applier = FileApplier(workspace_root=str(workspace))
        new_content = applier.merge_snippet(old_content, code)

        # If it exists, either show diff or auto-apply
        if auto_apply:
            try:
                filepath.write_text(new_content)
                self._edit_history.append((filepath, old_content))
                self.status_label.setText(f"Applied changes to {filename}. (Ctrl+Z to Rollback)")
                self.workspace_panel.refresh()
                self.editor_tabs.open_file(str(filepath))
                self._start_indexing()
            except OSError as e:
                self.status_label.setText(f"Failed to write {filename}: {e}")
        else:
            dialog = DiffViewDialog(self, str(filename), old_content, new_content)
            if dialog.exec_() == QDialog.Accepted and dialog.accepted_change:
                try:
                    filepath.write_text(new_content)
                    self._edit_history.append((filepath, old_content))
                    self.status_label.setText(f"Applied changes to {filename}. (Ctrl+Z to Rollback)")
                    self.workspace_panel.refresh()
                    self.editor_tabs.open_file(str(filepath))
                    self._start_indexing()
                except OSError as e:
                    QMessageBox.warning(self, "Write Error", f"Failed to write {filename}: {e}")

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
        for w in list(self._workers.values()):
            if w.isRunning():
                w.stop()
                w.wait(2000)
        self._workers.clear()
        self._stream_timer.stop()
        self.input_widget.set_streaming(False)
        self._active_stream_conv = None
        self._active_stream_tab_index = -1
        self._recursion_depth = 0
        self.status_label.setText("Generation stopped")

    def _force_send_next(self):
        self._stop_generation()
        queued = self.input_widget.pop_queued_message()
        if queued:
            self._send_message(queued["text"], queued.get("images"), queued.get("files"))

    def _restore_geometry(self):
        settings = QSettings(APP_NAME, APP_NAME)
        geo = settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)

    def _on_settings_requested(self):
        self.settings_dialog.show()

    def add_sidebar_widget(self, widget: QWidget, name: str):
        """Plugin API hook to add a new sidebar widget."""
        self.sidebar_stack.addWidget(widget)
        log.info(f"Plugin sidebar widget added: {name}")

    def _on_workspace_changed(self, path):
        self.terminal.set_cwd(path)
        self.git_panel.set_workspace(path)
        self.settings_data["workspace_dir"] = path
        self.settings_data["recent_projects"] = self.workspace_panel.get_recent_projects()
        save_settings(self.settings_data)
        self._start_indexing()

    def _on_git_status_changed(self, branch, count):
        suffix = f" ({count})" if count else ""
        self.git_branch_label.setText(f"\u2387 {branch}{suffix}")

    def _update_mcp_status(self):
        """Update MCP status indicator in status bar."""
        if not hasattr(self, "mcp_status_label"):
            return
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

    def _update_backend_status_bar(self, backend_id=None, status=None):
        if not self.backend_manager:
            return
            
        for bid in ["sd", "comfy"]:
            status = self.backend_manager.get_status(bid)
            label = self.sd_status_icon if bid == "sd" else self.comfy_status_icon
            name = "Stable Diffusion" if bid == "sd" else "ComfyUI"
            
            colors = {
                "running": "#7ee787",
                "error": "#f85149",
                "starting": "#e3b341",
                "installing": "#58a6ff",
                "stopped": "#8b949e",
                "not_installed": "#484f58"
            }
            color = colors.get(status, "#8b949e")
            label.setStyleSheet(f"color: {color}; font-size: 11px; padding: 0 8px;")
            label.setToolTip(f"{name} ({status.title()})")

    def _toggle_backend(self, backend_id):
        if not self.backend_manager:
            return
        status = self.backend_manager.get_status(backend_id)
        if status == "stopped":
            self.backend_manager.start(backend_id)
        elif status == "running":
            self.backend_manager.stop(backend_id)

    def _restore_workspace(self):
        recent = self.settings_data.get("recent_projects", [])
        self.workspace_panel.set_recent_projects(recent)
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
        if hasattr(dlg, 'apply_theme'):
            dlg.apply_theme(self._current_theme)
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
                if hasattr(compare_dlg, 'apply_theme'): compare_dlg.apply_theme(self._current_theme)
                compare_dlg.exec_()

    def _open_settings(self):
        dlg = SettingsDialog(self.settings_data, backend_manager=self.backend_manager, parent=self)
        dlg.settings_changed.connect(self._on_settings_changed)
        if hasattr(dlg, 'apply_theme'):
            dlg.apply_theme(self._current_theme)
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
        self._apply_shortcuts()
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
            {"id": "quick_chat", "label": "Quick Chat (Floating)", "shortcut": ""},
            {"id": "playground", "label": "Model Playground", "shortcut": ""},
            {"id": "arena", "label": "Model Arena (A/B Test)", "shortcut": ""},
            {"id": "prompt_lab", "label": "Prompt Lab (Multi-Compare)", "shortcut": ""},
            {"id": "conv_stats", "label": "Conversation Statistics", "shortcut": ""},
            {"id": "session_replay", "label": "Session Replay", "shortcut": ""},
            {"id": "auto_tag", "label": "Auto-Tag Current Conversation", "shortcut": ""},
            {"id": "import_theme", "label": "Import Custom Theme (.qss)", "shortcut": ""},
            {"id": "extract_code", "label": "Extract All Code Blocks to Files", "shortcut": ""},
            {"id": "consensus", "label": "Multi-Model Consensus", "shortcut": ""},
            {"id": "streaming_instant", "label": "Streaming Speed: Instant (10ms)", "shortcut": ""},
            {"id": "streaming_fast", "label": "Streaming Speed: Fast (30ms)", "shortcut": ""},
            {"id": "streaming_normal", "label": "Streaming Speed: Normal (50ms)", "shortcut": ""},
            {"id": "streaming_slow", "label": "Streaming Speed: Slow (100ms)", "shortcut": ""},
            {"id": "streaming_typewriter", "label": "Streaming Speed: Typewriter (200ms)", "shortcut": ""},
            {"id": "show_shortcuts", "label": "Show Keyboard Shortcuts", "shortcut": ""},
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
            "quick_chat": self._open_quick_chat,
            "playground": self._open_playground,
            "arena": self._open_arena,
            "prompt_lab": self._open_prompt_lab,
            "conv_stats": self._show_conv_stats,
            "session_replay": self._start_replay,
            "auto_tag": self._auto_tag_conversation,
            "replay": self._show_replay,
            "import_theme": self._import_custom_theme,
            "extract_code": self._extract_code,
            "consensus": self._open_consensus,
            "streaming_instant": lambda: self._set_streaming_speed(10),
            "streaming_fast": lambda: self._set_streaming_speed(30),
            "streaming_normal": lambda: self._set_streaming_speed(50),
            "streaming_slow": lambda: self._set_streaming_speed(100),
            "streaming_typewriter": lambda: self._set_streaming_speed(200),
            "show_shortcuts": self._show_shortcuts,
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
                    # YAML Frontmatter
                    f.write("---\n")
                    f.write(f"title: {title}\n")
                    f.write(f"model: {conv.get('model', 'unknown')}\n")
                    f.write(f"date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    if conv.get("system_prompt"):
                        f.write(f"system_prompt: |\n  {conv['system_prompt'].replace('\\n', '  \\n')}\n")
                    f.write("---\n\n")
                    f.write(f"# {title}\n\n")
                    
                    for msg in conv.get("messages", []):
                        role = msg.get("role", "assistant")
                        role_label = "**You**" if role == "user" else f"**{role.capitalize()}**"
                        content = msg.get("content", "")
                        
                        f.write(f"{role_label}:\n\n{content}\n\n")
                        
                        if msg.get("tool_calls"):
                            f.write("*Tool Calls:*\n")
                            for tc in msg["tool_calls"]:
                                name = tc.get("function", {}).get("name", "tool")
                                args = tc.get("function", {}).get("arguments", {})
                                f.write(f"- `{name}({args})`\n")
                            f.write("\n")
                            
                        f.write("---\n\n")
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
        self._title_worker = TitleWorker(model, conv["id"], conv["messages"], settings=self.settings_data)
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

    def _on_lsp_diagnostics(self, uri, diagnostics):
        """Routes diagnostics from LSP to the correct editor tab."""
        # Convert URI back to local path
        if not uri.startswith("file://"): return
        path = uri[7:]
        if os.name == 'nt' and path.startswith('/'):
            path = path[1:]
        
        # Find the editor for this path
        for i in range(self.tabs.count()):
            editor = self.tabs.widget(i)
            if hasattr(editor, '_filepath') and editor._filepath == path:
                editor.set_diagnostics(diagnostics)
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
        # Wait for title worker to finish so title gets saved
        tw = getattr(self, "_title_worker", None)
        if tw and tw.isRunning():
            tw.wait(3000)
        for worker_list in (
            getattr(self, "_summary_workers", []),
            getattr(self, "_tag_workers", []),
            getattr(self, "_yt_workers", []),
        ):
            for w in worker_list:
                if w.isRunning():
                    w.quit()
                    w.wait(2000)
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
        
        # Use WorkerFactory to support Ollama, OpenAI, and Anthropic
        self.worker = WorkerFactory(
            model,
            temp_messages,
            self.current_conv.get("system_prompt", ""),
            self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS),
            tools=[],
            settings=self.settings_data
        )
        self.worker.response_finished.connect(self._on_summary_done)
        self.worker.error_occurred.connect(self._on_worker_error)
        self.worker.start()
        self.input_widget.set_streaming(True)

    def _on_auto_exec_toggled(self, checked):
        state = "ON" if checked else "OFF"
        self.status_label.setText(f"Frictionless mode: {state}")
        save_settings({"auto_exec": checked})
        self._update_frictionless_style(checked)

    def _on_debug_start(self):
        editor = self.editor_tabs.currentWidget()
        if not editor or not isinstance(editor, CodeEditor):
            return
        
        filepath = editor._filepath
        if not filepath:
            return
            
        # Sync breakpoints
        self.debug_manager.clear_breakpoints()
        for line in editor.breakpoints:
            self.debug_manager.add_breakpoint(filepath, line)
            
        self.debug_manager.start_debug(filepath)

    def _on_debug_stop(self):
        self.debug_manager.stop_debug()

    def _on_debug_session_started(self):
        self.debug_toolbar.show()
        self.debug_toolbar._set_session_active(True)
        self.status_label.setText("Debug session started")

    def _on_debug_session_stopped(self):
        self.debug_toolbar.hide()
        self.debug_toolbar._set_session_active(False)
        self.status_label.setText("Debug session stopped")
        # Clear highlights
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            if isinstance(editor, CodeEditor):
                editor.set_execution_line(-1)

    def _on_debug_paused(self, reason, filepath, line):
        self.status_label.setText(f"Paused: {reason} at {os.path.basename(filepath)}:{line}")
        # Open file if not open
        self._open_file_internal(filepath)
        # Find editor and highlight
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor._filepath == filepath:
                self.editor_tabs.setCurrentIndex(i)
                editor.set_execution_line(line)
        self.debug_toolbar.continue_action.setVisible(True)
        self.debug_toolbar.pause_action.setVisible(False)

    def _on_debug_continued(self):
        self.status_label.setText("Running...")
        self.debug_toolbar.continue_action.setVisible(False)
        self.debug_toolbar.pause_action.setVisible(True)
        # Clear execution highlight
        editor = self.editor_tabs.currentWidget()
        if isinstance(editor, CodeEditor):
            editor.set_execution_line(-1)

    def _on_debug_breakpoint_clicked(self, filepath, line):
        self._open_file_internal(filepath)
        for i in range(self.editor_tabs.count()):
            editor = self.editor_tabs.widget(i)
            if isinstance(editor, CodeEditor) and editor._filepath == filepath:
                self.editor_tabs.setCurrentIndex(i)
                block = editor.document().findBlockByLineNumber(line - 1)
                cursor = editor.textCursor()
                cursor.setPosition(block.position())
                editor.setTextCursor(cursor)

    def _on_editor_breakpoint_toggled(self, line):
        editor = self.sender()
        if not isinstance(editor, CodeEditor) or not editor._filepath:
            return
        
        if line in editor.breakpoints:
            self.debug_manager.add_breakpoint(editor._filepath, line)
        else:
            self.debug_manager.remove_breakpoint(editor._filepath, line)
        # Update sidebar
        self.debug_sidebar.set_breakpoints(self.debug_manager.breakpoints)

    def _on_notebook_output(self, cell_id, text):
        # Find the active notebook editor and update cell
        editor = self.editor_tabs.currentWidget()
        from .notebook_editor import NotebookEditor
        if isinstance(editor, QWidget):
            nb_editor = editor.findChild(NotebookEditor)
            if nb_editor:
                nb_editor.update_cell_output(cell_id, text)

    def _on_notebook_error(self, cell_id, text):
        self._on_notebook_output(cell_id, f"Error: {text}")

    def _on_notebook_finished(self, cell_id, count):
        self.status_label.setText(f"Cell execution finished [{count}]")
        # Update execution count in UI if needed

    def _on_test_session_finished(self, summary):
        self.status_label.setText(f"Test session finished with exit code {summary.get('exit_code')}")

    def _on_task_started(self, task_id):
        self.task_runner_sidebar.set_task_status(task_id, "Running")
        self.status_label.setText(f"Task started: {task_id}")
        self.terminal.show() # Ensure terminal is visible for output

    def _on_task_finished(self, task_id, exit_code):
        status = "Finished" if exit_code == 0 else "Failed"
        self.task_runner_sidebar.set_task_status(task_id, status)
        self.status_label.setText(f"Task {task_id} {status.lower()} (exit code {exit_code})")

    def _on_task_output(self, task_id, output):
        # We'll pipe this to the terminal
        self.terminal.append_output(output)

    def _on_pr_refresh_requested(self):
        self.remote_service.fetch_prs()
        self.remote_service.fetch_issues()

    def _on_pr_selected(self, pr_data):
        log.info(f"Opening PR review for #{pr_data.get('number')}")
        dialog = PRReviewView(pr_data, self)
        dialog.apply_theme(self._current_theme)
        dialog.exec_()

    def _on_test_result(self, result):
        nodeid = result.get("nodeid", "")
        status = result.get("status", "UNKNOWN")
        if hasattr(self, 'test_sidebar'):
            self.test_sidebar.update_test_result(nodeid, status)

    def _on_coverage_updated(self, coverage_data):
        self._current_coverage.update(coverage_data)
        editor = self.editor_tabs.current_editor()
        if editor and editor._filepath in self._current_coverage:
            editor.set_coverage(self._current_coverage[editor._filepath])
        self.status_label.setText("Coverage results updated")

    def _on_editor_tab_changed(self, index):
        editor = self.editor_tabs.current_editor()
        if editor and editor._filepath in self._current_coverage:
            editor.set_coverage(self._current_coverage[editor._filepath])

    def _on_autocomplete_toggled(self):
        self._autocomplete_enabled = not self._autocomplete_enabled
        state = "ON" if self._autocomplete_enabled else "OFF"
        self.autocomplete_status_btn.setText(f"Autocomplete: {state}")
        self.autocomplete_status_btn.setChecked(self._autocomplete_enabled)
        save_settings({"autocomplete": self._autocomplete_enabled})
        
        # Update all open editors
        for i in range(self.editor_tabs.count()):
            tab = self.editor_tabs.widget(i)
            editor = tab.findChild(CodeEditor)
            if editor:
                editor.autocomplete.enabled = self._autocomplete_enabled
                editor.autocomplete.clear()

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
        was_offline = getattr(self, '_ollama_was_offline', True)
        if online:
            self.conn_dot.setStyleSheet("color: #2ea043; font-size: 14px; padding: 0 4px;")
            self.conn_dot.setToolTip("Ollama Connected")
            if was_offline:
                log.info("Ollama came online — refreshing models")
                self._load_models()
            self._ollama_was_offline = False
        else:
            self.conn_dot.setStyleSheet("color: #d32f2f; font-size: 14px; padding: 0 4px;")
            self.conn_dot.setToolTip("Ollama Offline")
            self._ollama_was_offline = True

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
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
        self.store.save(self.current_conv)
        self._render_chat()
        self.input_widget.set_streaming(False)
        self._set_summarize_running(False)
        self.sidebar.refresh(select_id=self.current_conv["id"])
        self.status_label.setText("Context reset with summary (backup saved)")

    def _on_vote_cast_by_index(self, split_view, pane_idx):
        """Handle 'Best' response vote from a SplitPane."""
        chat_pane = split_view.get_pane(pane_idx)
        if not chat_pane:
            return

        is_voted = chat_pane.best_btn.isChecked()
        
        # Exclusive vote within this split view
        if is_voted:
            for pane in split_view.panes:
                if pane != chat_pane:
                    pane.best_btn.setChecked(False)
        
        # Persist vote in conversation
        idx = self.chat_tabs.currentIndex()
        conv = self._get_tab_conv(idx)
        if not conv: return

        model_name = chat_pane.model_combo.currentText()
        history = conv.get("history", [])
        
        # Find the most recent assistant message from this model to tag
        found = False
        for msg in reversed(history):
            if msg.get("role") == "assistant" and msg.get("model") == model_name:
                msg["voted_best"] = is_voted
                found = True
                # Also reset others for the same parent (user prompt)
                parent_id = msg.get("parent_id")
                if is_voted and parent_id:
                    for other in history:
                        if other != msg and other.get("parent_id") == parent_id:
                            other.pop("voted_best", None)
                break
        
        if found:
            self.store.save(conv)
            self.status_label.setText(f"Ranked {model_name} as Best" if is_voted else "Vote cleared")
            self._render_chat(idx)

    def _on_sync_toggled(self, enabled):
        """Update UI and status when sync is toggled."""
        if enabled:
            self.status_label.setText("Input Sync Enabled")
        else:
            self.status_label.setText("Ready")

    def _on_branch_requested(self, msg_id):
        if not self.current_conv or "history" not in self.current_conv:
            return
            
        history = self.current_conv["history"]
        # Reconstruct path from msg_id upwards
        new_messages = []
        curr_id = msg_id
        
        while curr_id:
            msg = next((m for m in history if m.get("id") == curr_id), None)
            if not msg: break
            new_messages.insert(0, msg)
            curr_id = msg.get("parent_id")
            
        self.current_conv["messages"] = new_messages
        self.store.save(self.current_conv)
        self._render_chat()
        self.branch_tree_sidebar.refresh(history, msg_id)

    def _on_scheduled_task(self, task):
        log.info(f"Scheduled task executing: {task['id']}")
        self.status_label.setText(f"Running task: {task['prompt'][:30]}...")

        model = task.get("model", self.model_combo.currentText() or DEFAULT_MODEL)
        messages = [{"role": "user", "content": task["prompt"]}]
        gen_params = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS)

        worker = WorkerFactory(
            model, messages, "",
            gen_params, self.settings_data, tools=[]
        )
        worker.response_finished.connect(
            lambda text, stats, t=task: self._on_scheduled_task_done(t, text)
        )
        worker.error_occurred.connect(
            lambda err, t=task: self._on_scheduled_task_done(t, f"Error: {err}")
        )
        worker.start()

    def _on_scheduled_task_done(self, task, result):
        task["status"] = "finished"
        scheduler._save_tasks()
        self.schedule_sidebar.refresh()
        log.info(f"Scheduled task {task['id']} finished")
        self.status_label.setText(f"Task done: {task['prompt'][:30]}...")
        if self._tray_icon:
            self._tray_icon.showMessage("Synapse", f"Task completed: {task['prompt'][:50]}", 3000)

    def _on_image_gen_requested(self, provider, params):
        if provider == "openai":
            params["api_key"] = self.settings_data.get("openai_key")
        elif provider == "hf":
            params["hf_token"] = self.settings_data.get("hf_token")
            params["hf_model"] = self.settings_data.get("hf_model", "black-forest-labs/FLUX.1-schnell")
        self.image_gen_backend.generate(provider, params, self._on_image_gen_finished)

    def _on_image_gen_finished(self, result):
        if result.get("success"):
            self.image_gen_sidebar.add_to_gallery(result["path"])
            self.status_label.setText(f"Image generated: {os.path.basename(result['path'])}")
        else:
            self.image_gen_sidebar.gen_btn.setEnabled(True)
            self.image_gen_sidebar.gen_btn.setText("Generate Image")
            QMessageBox.warning(self, "Generation Error", result.get("error", "Unknown error"))

    def _on_image_selected(self, filepath):
        import webbrowser
        webbrowser.open(filepath)
    def _request_summary(self, conv):
        log.info(f"Requesting auto-summary for conversation {conv['id']}")
        model = self.model_combo.currentText() or DEFAULT_MODEL
        worker = SummaryWorker(model, conv["id"], conv["messages"], self.settings_data)
        worker.summary_ready.connect(self._on_summary_ready)
        worker.start()
        # Keep reference to avoid GC
        self._summary_workers = getattr(self, "_summary_workers", [])
        self._summary_workers.append(worker)

    def _on_summary_ready(self, conv_id, summary):
        log.info(f"Summary received for {conv_id}: {summary}")
        if self.current_conv and self.current_conv["id"] == conv_id:
            self.current_conv["summary"] = summary
            self.store.save(self.current_conv)
            self.status_label.setText(f"Auto-Summary: {summary[:60]}...")
            # Cleanup worker
            sender = self.sender()
            if sender in self._summary_workers:
                self._summary_workers.remove(sender)
    def _run_youtube_rag(self, url):
        self.status_label.setText(f"Fetching YouTube transcript: {url[:30]}...")
        self.input_widget.set_streaming(True)
        worker = YouTubeWorker(url)
        worker.finished.connect(self._on_youtube_finished)
        worker.start()
        # Keep reference
        self._yt_workers = getattr(self, "_yt_workers", [])
        self._yt_workers.append(worker)

    def _on_youtube_finished(self, transcript, metadata, error):
        self.input_widget.set_streaming(False)
        sender = self.sender()
        if sender in getattr(self, "_yt_workers", []):
            self._yt_workers.remove(sender)

        if error:
            QMessageBox.warning(self, "YouTube Error", f"Failed to fetch transcript: {error}")
            self.status_label.setText("YouTube fetch failed")
            return

        from ..utils.youtube_handler import YouTubeHandler
        context = YouTubeHandler.format_as_context(transcript, metadata)
        
        # Add a special system-like message to conversation
        msg = {
            "id": str(uuid.uuid4()),
            "role": "system",
            "content": context,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"type": "youtube", "video_id": metadata["id"]}
        }
        if self.current_conv:
            self.current_conv["messages"].append(msg)
            self.store.save(self.current_conv)
            self._render_chat()
            self.status_label.setText(f"YouTube context added: {metadata['title']}")
            
            # Proactively suggest a summary or let the user ask
            self.input_widget.input_box.setPlainText(f"Summarize the key points from this video: '{metadata['title']}'")
            self.input_widget.input_box.setFocus()
    def _setup_global_hotkey(self):
        hotkey_str = self.settings_data.get("shortcuts", DEFAULT_SHORTCUTS).get("global_summon", "<ctrl>+<alt>+s")
        self.hotkey_manager = GlobalHotkeyManager(hotkey_str)
        self.hotkey_manager.hotkey_triggered.connect(self._on_global_hotkey)
        self.hotkey_manager.start()

    def _on_global_hotkey(self):
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.showNormal()
            self.activateWindow()
            self.raise_()
            self.input_widget.input_box.setFocus()

    # --- F11: Quick Chat ---
    def _open_quick_chat(self):
        if not hasattr(self, '_quick_chat') or self._quick_chat is None:
            models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
            self._quick_chat = QuickChatWidget(models)
            self._quick_chat.closed.connect(lambda: setattr(self, '_quick_chat', None))
            if hasattr(self, '_current_theme'):
                self._quick_chat.apply_theme(self._current_theme)
        self._quick_chat.showAtCursor()

    # --- F13: Playground ---
    def _open_playground(self):
        models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        dlg = PlaygroundPanel(models, self.settings_data, self)
        if hasattr(self, '_current_theme'):
            dlg.apply_theme(self._current_theme)
        dlg.exec_()

    # --- F30: Arena ---
    def _open_arena(self):
        models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        if len(models) < 2:
            QMessageBox.information(self, "Arena", "Need at least 2 models for an arena battle.")
            return
        dlg = ArenaDialog(models, self.settings_data, self)
        if hasattr(self, '_current_theme'):
            dlg.apply_theme(self._current_theme)
        dlg.exec_()

    # --- F34: Prompt Lab ---
    def _open_prompt_lab(self):
        models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        dlg = PromptLab(models, self.settings_data, self)
        if hasattr(self, '_current_theme'):
            dlg.apply_theme(self._current_theme)
        dlg.exec_()

    # --- F28: Conversation Statistics ---
    def _show_conv_stats(self):
        if not self.current_conv:
            return
        msgs = self.current_conv.get("messages", [])
        user_msgs = [m for m in msgs if m.get("role") == "user"]
        asst_msgs = [m for m in msgs if m.get("role") == "assistant"]
        total_tokens = sum(m.get("tokens", 0) for m in asst_msgs)
        total_duration = sum(m.get("duration_ms", 0) for m in asst_msgs)
        avg_time = (total_duration // max(len(asst_msgs), 1))
        models_used = list(set(m.get("model", "?") for m in asst_msgs if m.get("model")))
        code_blocks = sum(m.get("content", "").count("```") // 2 for m in msgs)
        created = self.current_conv.get("created_at", "?")

        stats_text = (
            f"Messages: {len(msgs)} ({len(user_msgs)} user, {len(asst_msgs)} assistant)\n"
            f"Total tokens: {total_tokens:,}\n"
            f"Avg response time: {avg_time}ms\n"
            f"Code blocks: {code_blocks}\n"
            f"Models used: {', '.join(models_used) if models_used else 'N/A'}\n"
            f"Created: {created[:10] if len(created) > 10 else created}"
        )

        dlg = QDialog(self)
        dlg.setWindowTitle("Conversation Statistics")
        dlg.resize(400, 280)
        layout = QVBoxLayout(dlg)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setStyleSheet("background: #0d1117; color: #e6edf3; border: none; font-family: monospace;")
        text.setPlainText(stats_text)
        layout.addWidget(text)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.close)
        layout.addWidget(close_btn)
        dlg.exec_()

    # --- F31: Session Replay ---
    def _start_replay(self):
        if not self.current_conv or not self.current_conv.get("messages"):
            return
        self._replay_msgs = list(self.current_conv["messages"])
        self._replay_idx = 0
        self._replay_char_idx = 0
        self._replay_buf = ""
        self._replay_speed = 15  # ms per char

        # Build partial conversation for replay
        self._replay_conv_backup = self.current_conv.copy()
        self.current_conv["messages"] = []
        self._render_chat()
        self.status_label.setText("Replay mode - press Escape to stop")
        QTimer.singleShot(500, self._replay_next)

    def _replay_next(self):
        if not hasattr(self, '_replay_msgs') or self._replay_idx >= len(self._replay_msgs):
            self._stop_replay()
            return

        msg = self._replay_msgs[self._replay_idx]
        if msg.get("role") == "user":
            self.current_conv["messages"].append(dict(msg))
            self._render_chat()
            self._replay_idx += 1
            QTimer.singleShot(400, self._replay_next)
        elif msg.get("role") == "assistant":
            if self._replay_char_idx == 0:
                # Start streaming this message
                partial_msg = dict(msg)
                partial_msg["content"] = ""
                self.current_conv["messages"].append(partial_msg)
                self._replay_buf = msg.get("content", "")

            content = self._replay_buf
            self._replay_char_idx += 3  # 3 chars at a time for speed
            if self._replay_char_idx >= len(content):
                self.current_conv["messages"][-1]["content"] = content
                self._render_chat()
                self._replay_idx += 1
                self._replay_char_idx = 0
                QTimer.singleShot(400, self._replay_next)
            else:
                self.current_conv["messages"][-1]["content"] = content[:self._replay_char_idx]
                self._render_chat()
                QTimer.singleShot(self._replay_speed, self._replay_next)
        else:
            self.current_conv["messages"].append(dict(msg))
            self._replay_idx += 1
            QTimer.singleShot(100, self._replay_next)

    def _stop_replay(self):
        if hasattr(self, '_replay_conv_backup'):
            self.current_conv.update(self._replay_conv_backup)
            self._render_chat()
            del self._replay_conv_backup
        if hasattr(self, '_replay_msgs'):
            del self._replay_msgs
        self.status_label.setText("Replay finished")

    # --- F12: Auto-Tagging ---
    def _auto_tag_conversation(self):
        if not self.current_conv or not self.current_conv.get("messages"):
            return
        msgs = self.current_conv["messages"][:4]
        preview = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in msgs)
        tag_prompt = (
            "Classify this conversation into 1-2 tags from this list: "
            "coding, writing, research, math, data, debugging, learning, creative, general. "
            "Reply with ONLY the tag names separated by commas, nothing else.\n\n"
            f"{preview}"
        )
        model = self.model_combo.currentText() or DEFAULT_MODEL
        messages = [{"role": "user", "content": tag_prompt}]
        worker = WorkerFactory(model, messages, "", DEFAULT_GEN_PARAMS, self.settings_data, tools=[])
        worker.response_finished.connect(self._on_auto_tag_done)
        worker.error_occurred.connect(lambda e: self.status_label.setText(f"Auto-tag failed: {e}"))
        worker.start()
        self._tag_workers = getattr(self, '_tag_workers', [])
        self._tag_workers.append(worker)
        self.status_label.setText("Auto-tagging...")

    def _on_auto_tag_done(self, text, stats):
        sender = self.sender()
        if sender in getattr(self, "_tag_workers", []):
            self._tag_workers.remove(sender)
        tags = [t.strip().lower() for t in text.strip().split(",") if t.strip()]
        valid = {"coding", "writing", "research", "math", "data", "debugging", "learning", "creative", "general"}
        tags = [t for t in tags if t in valid][:2]
        if tags and self.current_conv:
            existing = self.current_conv.get("tags", [])
            for t in tags:
                if t not in existing:
                    existing.append(t)
            self.current_conv["tags"] = existing
            self.store.save(self.current_conv)
            self.status_label.setText(f"Tagged: {', '.join(tags)}")

    # --- F31: Session Replay ---
    def _show_replay(self):
        if not self.current_conv:
            return
        dlg = ReplayDialog(self.current_conv, self)
        dlg.exec_()

    # --- F29: Custom CSS Themes ---
    def _import_custom_theme(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Theme", "", "QSS Files (*.qss);;All (*)")
        if not path:
            return
        from ..utils.constants import CONFIG_DIR
        themes_dir = CONFIG_DIR / "themes"
        themes_dir.mkdir(parents=True, exist_ok=True)
        name = Path(path).stem
        dest = themes_dir / f"{name}.qss"
        dest.write_text(Path(path).read_text())
        QApplication.instance().setStyleSheet(dest.read_text())
        self.status_label.setText(f"Theme imported and applied: {name}")

    # --- F38: Streaming Speed Control ---
    def _set_streaming_speed(self, speed_ms):
        self._streaming_delay = speed_ms
        self._stream_timer.setInterval(max(10, speed_ms))
        self.settings_data["streaming_speed"] = speed_ms
        save_settings(self.settings_data)
        speed_name = {10: "Instant", 30: "Fast", 50: "Normal", 100: "Slow", 200: "Typewriter"}.get(speed_ms, f"Custom ({speed_ms}ms)")
        self.status_label.setText(f"Streaming: {speed_name}")

    # --- F21: Chat-to-Code Extractor ---
    def _extract_code(self):
        if not self.current_conv or not self.current_conv.get("messages"):
            self.status_label.setText("No conversation to extract from")
            return
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        target_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not target_dir:
            return
        results = CodeExtractor.extract_to_directory(self.current_conv["messages"], target_dir)
        if results:
            summary = "\n".join(f"  {name} ({lang}, {lines} lines)" for name, lang, lines in results)
            self.status_label.setText(f"Extracted {len(results)} code blocks to {target_dir}")
            QMessageBox.information(self, "Code Extracted", f"Extracted {len(results)} files:\n{summary}")
        else:
            self.status_label.setText("No code blocks found in conversation")

    def _show_shortcuts(self):
        shortcuts = self.settings_data.get("shortcuts", DEFAULT_SHORTCUTS)
        dlg = ShortcutsDialog(shortcuts, self)
        if hasattr(self, '_current_theme'):
            dlg.apply_theme(self._current_theme)
        dlg.exec_()

    # --- F16: Multi-Model Consensus Dialog ---
    def _open_consensus(self):
        models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        if len(models) < 2:
            self.status_label.setText("Need 2+ models for consensus")
            return
        dlg = ConsensusDialog(models, self.settings_data, self)
        if hasattr(self, '_current_theme'):
            dlg.apply_theme(self._current_theme)
        dlg.exec_()

    def _on_agent_selected(self, agent_id):
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return
            
        if not self.current_conv:
            self._new_chat()
            
        self.current_conv["system_prompt"] = agent.system_prompt
        if agent.model:
            model_index = self.model_combo.findText(agent.model)
            if model_index >= 0:
                self.model_combo.setCurrentIndex(model_index)
            
        self.status_label.setText(f"Active Agent: {agent.name}")

    def _check_dev_container(self):
        config = self.docker_manager.get_devcontainer_config()
        if config:
            res = QMessageBox.question(
                self,
                "Dev Container Detected",
                f"This workspace contains a Dev Container configuration ({config.get('name', 'unnamed')}).\n\nWould you like to reopen this workspace in a container?",
                QMessageBox.Yes | QMessageBox.No
            )
            if res == QMessageBox.Yes:
                self.status_label.setText("Building / Starting Dev Container...")
                # Placeholder for building/running dev container logic
                QMessageBox.information(self, "Dev Container", "Dev Container support is partially implemented. Building environment...")

    def _on_terminal_output(self, text):
        # Handle terminal interaction or context updates based on output
        pass

class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)
