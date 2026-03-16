import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QSlider, QSpinBox, QLineEdit,
    QComboBox, QCheckBox, QGroupBox, QFormLayout, QListWidget,
    QListWidgetItem, QMessageBox, QTableWidget, QTableWidgetItem,
    QKeySequenceEdit, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from ..utils.constants import (
    DEFAULT_GEN_PARAMS, DEFAULT_OLLAMA_URL, DEFAULT_SHORTCUTS,
    load_settings, save_settings
)
from ..utils.themes import get_all_themes

log = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(dict)

    def __init__(self, settings_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 500)
        self.settings_data = dict(settings_data)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_general_tab(), "General")
        self.tabs.addTab(self._build_model_tab(), "Models")
        self.tabs.addTab(self._build_appearance_tab(), "Appearance")
        self.tabs.addTab(self._build_advanced_tab(), "Advanced")
        self.tabs.addTab(self._build_mcp_tab(), "MCP")
        self.tabs.addTab(self._build_providers_tab(), "Providers")
        self.tabs.addTab(self._build_voice_tab(), "Voice")
        self.tabs.addTab(self._build_shortcuts_tab(), "Shortcuts")
        layout.addWidget(self.tabs)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #2ea043; color: white; font-weight: bold; padding: 8px 20px;")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _build_general_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.auto_title_check = QCheckBox("Auto-generate chat titles")
        self.auto_title_check.setChecked(self.settings_data.get("auto_title", True))
        layout.addRow(self.auto_title_check)

        self.ollama_url = QLineEdit(self.settings_data.get("ollama_url", DEFAULT_OLLAMA_URL))
        layout.addRow("Ollama URL:", self.ollama_url)

        self.auto_summary_check = QCheckBox("Auto-summarize long conversations")
        self.auto_summary_check.setChecked(self.settings_data.get("auto_summary", True))
        layout.addRow(self.auto_summary_check)

        self.notification_check = QCheckBox("Sound on completion")
        self.notification_check.setChecked(self.settings_data.get("notification_sound", False))
        layout.addRow(self.notification_check)

        self.auto_exec_check = QCheckBox("Frictionless mode (auto-approve tools)")
        self.auto_exec_check.setChecked(self.settings_data.get("auto_exec", False))
        layout.addRow(self.auto_exec_check)

        self.auto_continue_check = QCheckBox("Auto-continue truncated responses")
        self.auto_continue_check.setChecked(self.settings_data.get("auto_continue", True))
        layout.addRow(self.auto_continue_check)

        layout.addRow(QLabel("<hr>"))
        rerun_btn = QPushButton("Re-run Onboarding Wizard")
        rerun_btn.clicked.connect(self._rerun_onboarding)
        layout.addRow("Setup:", rerun_btn)

        return w

    def _rerun_onboarding(self):
        self.settings_data["onboarding_complete"] = False
        save_settings(self.settings_data)
        QMessageBox.information(self, "Onboarding", "Onboarding flag reset. Please restart Synapse or the wizard will trigger if you hit Save.")
        self.accept()

    def _build_model_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        gen = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS)

        temp_row = QHBoxLayout()
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(0, 200)
        self.temp_slider.setValue(int(gen.get("temperature", 0.7) * 100))
        self.temp_label = QLabel(f"{gen.get('temperature', 0.7):.2f}")
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"{v/100:.2f}"))
        temp_row.addWidget(self.temp_slider)
        temp_row.addWidget(self.temp_label)
        layout.addRow("Temperature:", temp_row)

        top_p_row = QHBoxLayout()
        self.top_p_slider = QSlider(Qt.Horizontal)
        self.top_p_slider.setRange(0, 100)
        self.top_p_slider.setValue(int(gen.get("top_p", 0.9) * 100))
        self.top_p_label = QLabel(f"{gen.get('top_p', 0.9):.2f}")
        self.top_p_slider.valueChanged.connect(lambda v: self.top_p_label.setText(f"{v/100:.2f}"))
        top_p_row.addWidget(self.top_p_slider)
        top_p_row.addWidget(self.top_p_label)
        layout.addRow("Top P:", top_p_row)

        self.ctx_spin = QSpinBox()
        self.ctx_spin.setRange(512, 131072)
        self.ctx_spin.setSingleStep(512)
        self.ctx_spin.setValue(gen.get("num_ctx", 4096))
        layout.addRow("Context Length:", self.ctx_spin)

        return w

    def _build_appearance_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(get_all_themes().keys())
        current_theme = self.settings_data.get("theme", "One Dark")
        idx = self.theme_combo.findText(current_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        layout.addRow("Theme:", self.theme_combo)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(10, 24)
        self.font_size_spin.setValue(self.settings_data.get("font_size", 15))
        layout.addRow("Chat Font Size:", self.font_size_spin)

        self.editor_font_spin = QSpinBox()
        self.editor_font_spin.setRange(8, 24)
        self.editor_font_spin.setValue(self.settings_data.get("editor_font_size", 12))
        layout.addRow("Editor Font Size:", self.editor_font_spin)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setRange(50, 200)
        self.zoom_spin.setSingleStep(10)
        self.zoom_spin.setValue(self.settings_data.get("zoom", 100))
        self.zoom_spin.setSuffix("%")
        layout.addRow("Zoom:", self.zoom_spin)

        return w

    def _build_advanced_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.workspace_dir = QLineEdit(self.settings_data.get("workspace_dir", ""))
        layout.addRow("Workspace Dir:", self.workspace_dir)

        info = QLabel("Changes take effect after restart for some settings.")
        info.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addRow(info)

        return w

    def _build_providers_tab(self):
        w = QWidget()
        layout = QFormLayout(w)

        self.openai_key = QLineEdit(self.settings_data.get("openai_key", ""))
        self.openai_key.setEchoMode(QLineEdit.Password)
        layout.addRow("OpenAI API Key:", self.openai_key)

        self.anthropic_key = QLineEdit(self.settings_data.get("anthropic_key", ""))
        self.anthropic_key.setEchoMode(QLineEdit.Password)
        layout.addRow("Anthropic API Key:", self.anthropic_key)

        self.openrouter_key = QLineEdit(self.settings_data.get("openrouter_key", ""))
        self.openrouter_key.setEchoMode(QLineEdit.Password)
        layout.addRow("OpenRouter API Key:", self.openrouter_key)

        return w

    def _build_mcp_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # Title
        title = QLabel("MCP Servers (Model Context Protocol)")
        title.setStyleSheet("font-weight: bold; font-size: 12px; margin-bottom: 8px;")
        layout.addWidget(title)

        # Server list
        list_label = QLabel("Configured Servers:")
        layout.addWidget(list_label)

        self.mcp_server_list = QListWidget()
        self.mcp_server_list.itemClicked.connect(self._on_mcp_server_selected)
        layout.addWidget(self.mcp_server_list)

        # Server config form
        form_label = QLabel("Server Configuration:")
        form_label.setStyleSheet("font-weight: bold; font-size: 11px; margin-top: 12px;")
        layout.addWidget(form_label)

        form_layout = QFormLayout()

        self.mcp_name = QLineEdit()
        form_layout.addRow("Name:", self.mcp_name)

        self.mcp_command = QLineEdit()
        self.mcp_command.setPlaceholderText("e.g., npx")
        form_layout.addRow("Command:", self.mcp_command)

        self.mcp_args = QLineEdit()
        self.mcp_args.setPlaceholderText("Comma-separated args (e.g., -y,@modelcontextprotocol/server-filesystem,/home)")
        form_layout.addRow("Arguments:", self.mcp_args)

        self.mcp_enabled = QCheckBox("Enabled")
        self.mcp_enabled.setChecked(True)
        form_layout.addRow(self.mcp_enabled)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        add_btn = QPushButton("Add / Update")
        add_btn.clicked.connect(self._mcp_add_or_update)
        button_layout.addWidget(add_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._mcp_remove)
        button_layout.addWidget(remove_btn)

        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._mcp_test_connection)
        button_layout.addWidget(test_btn)

        layout.addLayout(button_layout)

        self.mcp_status_label = QLabel("")
        self.mcp_status_label.setStyleSheet("color: #8b949e; font-size: 10px; margin-top: 8px;")
        layout.addWidget(self.mcp_status_label)

        layout.addStretch()

        # Load existing MCP servers
        self._mcp_servers = list(self.settings_data.get("mcp_servers", []))
        self._selected_mcp_idx = -1
        self._refresh_mcp_list()

        return w

    def _refresh_mcp_list(self):
        """Rebuild the MCP server list widget."""
        self.mcp_server_list.clear()
        for i, cfg in enumerate(self._mcp_servers):
            name = cfg.get("name", "Unknown")
            enabled = cfg.get("enabled", True)
            status = "✓" if enabled else "✗"
            item_text = f"[{status}] {name}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, i)
            self.mcp_server_list.addItem(item)

    def _on_mcp_server_selected(self, item):
        """Load selected server config into form."""
        idx = item.data(Qt.UserRole)
        if 0 <= idx < len(self._mcp_servers):
            self._selected_mcp_idx = idx
            cfg = self._mcp_servers[idx]
            self.mcp_name.setText(cfg.get("name", ""))
            self.mcp_command.setText(cfg.get("command", ""))
            self.mcp_args.setText(",".join(cfg.get("args", [])))
            self.mcp_enabled.setChecked(cfg.get("enabled", True))

    def _mcp_add_or_update(self):
        """Add a new MCP server or update the selected one."""
        name = self.mcp_name.text().strip()
        command = self.mcp_command.text().strip()
        args_text = self.mcp_args.text().strip()

        if not name or not command:
            QMessageBox.warning(self, "Validation Error", "Name and Command are required.")
            return

        # Parse args from comma-separated string
        args = [a.strip() for a in args_text.split(",") if a.strip()] if args_text else []

        cfg = {
            "name": name,
            "command": command,
            "args": args,
            "transport": "stdio",
            "enabled": self.mcp_enabled.isChecked()
        }

        if self._selected_mcp_idx >= 0:
            # Update existing
            self._mcp_servers[self._selected_mcp_idx] = cfg
        else:
            # Add new
            self._mcp_servers.append(cfg)

        self._refresh_mcp_list()
        self.mcp_name.clear()
        self.mcp_command.clear()
        self.mcp_args.clear()
        self.mcp_enabled.setChecked(True)
        self._selected_mcp_idx = -1
        self.mcp_status_label.setText("Server added/updated.")

    def _mcp_remove(self):
        """Remove the selected MCP server."""
        if self._selected_mcp_idx >= 0 and self._selected_mcp_idx < len(self._mcp_servers):
            self._mcp_servers.pop(self._selected_mcp_idx)
            self._refresh_mcp_list()
            self.mcp_name.clear()
            self.mcp_command.clear()
            self.mcp_args.clear()
            self._selected_mcp_idx = -1
            self.mcp_status_label.setText("Server removed.")

    def _mcp_test_connection(self):
        """Test connection to the selected server."""
        if self._selected_mcp_idx < 0:
            QMessageBox.info(self, "Test Connection", "Select a server to test.")
            return

        cfg = self._mcp_servers[self._selected_mcp_idx]
        self.mcp_status_label.setText(f"Testing connection to {cfg['name']}...")
        self.mcp_status_label.repaint()

        # Import here to avoid circular dependency
        from ..core.mcp import MCPServerConnection
        conn = MCPServerConnection(cfg)

        def on_connected():
            self.mcp_status_label.setText(f"✓ {cfg['name']} connected successfully ({len(conn._tools_cache)} tools)")
            conn.disconnect()

        def on_disconnected(reason):
            self.mcp_status_label.setText(f"✗ {cfg['name']} connection failed: {reason}")
            conn.disconnect()

        conn.connected.connect(on_connected)
        conn.disconnected.connect(on_disconnected)

        # Timeout after 10 seconds
        QTimer.singleShot(10000, lambda: self.mcp_status_label.setText(f"✗ {cfg['name']} test timed out"))

        try:
            conn.connect()
        except Exception as e:
            self.mcp_status_label.setText(f"✗ Error: {str(e)}")

    def _build_shortcuts_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        self.shortcut_table = QTableWidget()
        self.shortcut_table.setColumnCount(3)
        self.shortcut_table.setHorizontalHeaderLabels(["Action", "Shortcut", ""])
        self.shortcut_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.shortcut_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.shortcut_table.setColumnWidth(1, 150)
        self.shortcut_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.shortcut_table.setColumnWidth(2, 60)
        layout.addWidget(self.shortcut_table)

        self._shortcut_edits = {} # action_id -> QKeySequenceEdit
        shortcuts = self.settings_data.get("shortcuts", DEFAULT_SHORTCUTS)
        
        row = 0
        for action_id, default_key in DEFAULT_SHORTCUTS.items():
            current_key = shortcuts.get(action_id, default_key)
            self.shortcut_table.insertRow(row)
            
            # Action Label
            label = action_id.replace("_", " ").title()
            self.shortcut_table.setItem(row, 0, QTableWidgetItem(label))
            
            # Key Edit
            edit = QKeySequenceEdit(current_key)
            self.shortcut_table.setCellWidget(row, 1, edit)
            self._shortcut_edits[action_id] = edit
            
            # Reset button
            reset_btn = QPushButton("↺")
            reset_btn.setToolTip("Reset to default")
            reset_btn.setFixedWidth(40)
            reset_btn.clicked.connect(lambda checked, aid=action_id, ed=edit: ed.setKeySequence(DEFAULT_SHORTCUTS[aid]))
            self.shortcut_table.setCellWidget(row, 2, reset_btn)
            
            row += 1

        reset_all = QPushButton("Reset All Shortcuts")
        reset_all.clicked.connect(self._reset_all_shortcuts)
        layout.addWidget(reset_all)

        return w

    def _reset_all_shortcuts(self):
        reply = QMessageBox.question(self, "Reset All", "Reset all keyboard shortcuts to defaults?", QMessageBox.Yes|QMessageBox.No)
        if reply == QMessageBox.Yes:
            for action_id, edit in self._shortcut_edits.items():
                edit.setKeySequence(DEFAULT_SHORTCUTS[action_id])

    def _build_voice_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        
        form_group = QGroupBox("Voice Configuration")
        form_layout = QFormLayout(form_group)
        
        self.whisper_model_combo = QComboBox()
        self.whisper_model_combo.addItems(["tiny", "base", "small", "medium", "large-v3"])
        voice_settings = self.settings_data.get("voice", {})
        if not isinstance(voice_settings, dict): voice_settings = {}
        current_model = voice_settings.get("whisper_model", "base")
        self.whisper_model_combo.setCurrentText(str(current_model))
        form_layout.addRow("Whisper Model:", self.whisper_model_combo)
        
        self.tts_voice_combo = QComboBox()
        # Common edge-tts voices
        voices = ["en-US-AndrewNeural", "en-US-AvaNeural", "en-GB-SoniaNeural", "en-AU-NatashaNeural"]
        self.tts_voice_combo.addItems(voices)
        current_voice = voice_settings.get("tts_voice", "en-US-AndrewNeural")
        self.tts_voice_combo.setCurrentText(str(current_voice))
        form_layout.addRow("TTS Voice:", self.tts_voice_combo)
        
        self.vad_threshold_spin = QSpinBox()
        self.vad_threshold_spin.setRange(1, 100)
        self.vad_threshold_spin.setSuffix("%")
        val = int(voice_settings.get("vad_threshold", 0.01) * 1000)
        self.vad_threshold_spin.setValue(val)
        form_layout.addRow("VAD Sensitivity:", self.vad_threshold_spin)
        
        self.silence_timeout_spin = QSpinBox()
        self.silence_timeout_spin.setRange(5, 50) # 0.5s to 5.0s
        self.silence_timeout_spin.setValue(int(voice_settings.get("silence_timeout", 1.5) * 10))
        self.silence_timeout_spin.setSuffix(" x 0.1s")
        form_layout.addRow("Silence Timeout:", self.silence_timeout_spin)
        
        layout.addWidget(form_group)
        
        manage_btn = QPushButton("Manage Whisper Models")
        manage_btn.clicked.connect(self._open_whisper_manager)
        layout.addWidget(manage_btn)
        
        layout.addStretch()
        return w

    def _open_whisper_manager(self):
        from .whisper_manager import WhisperManagerPanel
        dlg = QDialog(self)
        dlg.setWindowTitle("Whisper Model Manager")
        dlg.resize(800, 500)
        l = QVBoxLayout(dlg)
        l.addWidget(WhisperManagerPanel())
        dlg.exec_()

    def _save(self):
        self.settings_data["ollama_url"] = self.ollama_url.text().strip()
        self.settings_data["auto_title"] = self.auto_title_check.isChecked()
        self.settings_data["notification_sound"] = self.notification_check.isChecked()
        self.settings_data["auto_exec"] = self.auto_exec_check.isChecked()
        self.settings_data["auto_continue"] = self.auto_continue_check.isChecked()
        self.settings_data["gen_params"] = {
            "temperature": self.temp_slider.value() / 100,
            "top_p": self.top_p_slider.value() / 100,
            "num_ctx": self.ctx_spin.value(),
        }
        self.settings_data["theme"] = self.theme_combo.currentText()
        self.settings_data["font_size"] = self.font_size_spin.value()
        self.settings_data["editor_font_size"] = self.editor_font_spin.value()
        self.settings_data["zoom"] = self.zoom_spin.value()
        self.settings_data["workspace_dir"] = self.workspace_dir.text().strip()
        self.settings_data["mcp_servers"] = self._mcp_servers

        self.settings_data["openai_key"] = self.openai_key.text()
        self.settings_data["anthropic_key"] = self.anthropic_key.text()
        self.settings_data["openrouter_key"] = self.openrouter_key.text()

        # Save Shortcuts
        new_shortcuts = {}
        if hasattr(self, "_shortcut_edits"):
            for aid, edit in self._shortcut_edits.items():
                new_shortcuts[aid] = edit.keySequence().toString()
            self.settings_data["shortcuts"] = new_shortcuts

        self.settings_data["voice"] = {
            "whisper_model": self.whisper_model_combo.currentText(),
            "tts_voice": self.tts_voice_combo.currentText(),
            "vad_threshold": self.vad_threshold_spin.value() / 1000.0,
            "silence_timeout": self.silence_timeout_spin.value() / 10.0,
        }

        self.settings_data["auto_summary"] = self.auto_summary_check.isChecked()

        save_settings(self.settings_data)
        self.settings_changed.emit(self.settings_data)
        self.accept()
