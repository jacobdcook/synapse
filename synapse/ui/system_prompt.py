import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QPlainTextEdit, QComboBox, QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from ..utils.constants import DEFAULT_SYSTEM_PROMPT, load_settings, save_settings

log = logging.getLogger(__name__)

PRESET_PROMPTS = {
    "Default": DEFAULT_SYSTEM_PROMPT,
    "Coder": "You are an expert software engineer. Write clean, efficient, well-tested code. Explain your reasoning. Use best practices and design patterns. Prefer simple solutions.",
    "Creative Writer": "You are a creative writing assistant. Help with stories, poetry, scripts, and other creative text. Be imaginative, use vivid language, and adapt to the user's style.",
    "Concise": "Be extremely concise. Answer in as few words as possible. No preamble, no filler. Direct answers only.",
    "Analyst": "You are a data analyst. Provide thorough, evidence-based analysis. Use structured formats (tables, lists). Cite assumptions. Quantify when possible.",
    "Teacher": "You are a patient, thorough teacher. Explain concepts step by step. Use analogies and examples. Check understanding. Adapt to the student's level.",
    "Debugger": "You are a debugging assistant. Analyze error messages, stack traces, and code carefully. Identify root causes, not just symptoms. Suggest fixes with explanations.",
    "Reviewer": "You are a code reviewer. Focus on bugs, security issues, performance problems, and readability. Be constructive. Suggest specific improvements with examples.",
}


class SystemPromptDialog(QDialog):
    prompt_changed = pyqtSignal(str)

    def __init__(self, current_prompt="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Prompt")
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)

        header = QLabel("System Prompt")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Presets:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESET_PROMPTS.keys())

        settings = load_settings()
        custom_presets = settings.get("custom_presets", {})
        for name in custom_presets:
            self.preset_combo.addItem(name)
            PRESET_PROMPTS[name] = custom_presets[name]

        self.preset_combo.currentTextChanged.connect(self._on_preset_selected)
        preset_row.addWidget(self.preset_combo, 1)

        save_preset_btn = QPushButton("Save as Preset")
        save_preset_btn.clicked.connect(self._save_preset)
        preset_row.addWidget(save_preset_btn)
        layout.addLayout(preset_row)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(current_prompt or DEFAULT_SYSTEM_PROMPT)
        self.editor.setStyleSheet("font-family: 'JetBrains Mono', monospace; font-size: 12px;")
        layout.addWidget(self.editor)

        char_label = QLabel(f"{len(current_prompt)} chars")
        char_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.editor.textChanged.connect(lambda: char_label.setText(f"{len(self.editor.toPlainText())} chars"))
        layout.addWidget(char_label)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet("background-color: #2ea043; color: white; font-weight: bold; padding: 8px 20px;")
        apply_btn.clicked.connect(self._apply)
        btn_row.addWidget(apply_btn)
        layout.addLayout(btn_row)

    def _on_preset_selected(self, name):
        if name in PRESET_PROMPTS:
            self.editor.setPlainText(PRESET_PROMPTS[name])

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if ok and name.strip():
            name = name.strip()
            settings = load_settings()
            custom = settings.get("custom_presets", {})
            custom[name] = self.editor.toPlainText()
            settings["custom_presets"] = custom
            save_settings(settings)
            PRESET_PROMPTS[name] = self.editor.toPlainText()
            if self.preset_combo.findText(name) < 0:
                self.preset_combo.addItem(name)
            self.preset_combo.setCurrentText(name)

    def _apply(self):
        self.prompt_changed.emit(self.editor.toPlainText())
        self.accept()

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        fg = theme.get("fg", "#e6edf3")
        input_bg = theme.get("input_bg", "#0d1117")
        border = theme.get("border", "#30363d")
        self.setStyleSheet(f"""
            QDialog {{ background: {bg}; color: {fg}; }}
            QPlainTextEdit {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; }}
            QComboBox {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; padding: 4px; }}
            QPushButton {{ background: {border}; color: {fg}; border: none; padding: 6px 16px; border-radius: 4px; }}
            QPushButton:hover {{ background: {input_bg}; }}
            QLabel {{ color: {fg}; }}
        """)
