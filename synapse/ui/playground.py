from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel,
    QPushButton, QComboBox, QSplitter, QWidget, QSlider
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView


class PlaygroundPanel(QDialog):
    """Model Playground — test prompts without creating conversations."""

    def __init__(self, models, settings_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Model Playground")
        self.resize(900, 650)
        self.settings_data = settings_data
        self._workers = []

        self.setStyleSheet("""
            QDialog { background: #1a1b1e; }
            QTextEdit { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px; padding: 8px; }
            QLabel { color: #8b949e; }
            QPushButton { background: #238636; color: white; border: none; padding: 8px 20px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #2ea043; }
            QPushButton:disabled { background: #21262d; color: #484f58; }
            QComboBox { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; padding: 4px 8px; border-radius: 4px; }
            QSlider::groove:horizontal { background: #30363d; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #58a6ff; width: 14px; margin: -5px 0; border-radius: 7px; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # System prompt
        layout.addWidget(QLabel("System Prompt:"))
        self.system_input = QTextEdit()
        self.system_input.setPlaceholderText("Optional system prompt...")
        self.system_input.setMaximumHeight(60)
        layout.addWidget(self.system_input)

        # User prompt
        layout.addWidget(QLabel("Prompt:"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Enter your test prompt...")
        self.prompt_input.setMaximumHeight(100)
        layout.addWidget(self.prompt_input)

        # Config row
        config = QHBoxLayout()
        config.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(models)
        config.addWidget(self.model_combo)

        config.addWidget(QLabel("Temp:"))
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(0, 200)
        self.temp_slider.setValue(70)
        self.temp_slider.setFixedWidth(120)
        self.temp_label = QLabel("0.7")
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"{v/100:.1f}"))
        config.addWidget(self.temp_slider)
        config.addWidget(self.temp_label)

        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self._run)
        config.addWidget(self.run_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet("background: #21262d; color: #c9d1d9;")
        self.clear_btn.clicked.connect(self._clear)
        config.addWidget(self.clear_btn)
        layout.addLayout(config)

        # Response
        layout.addWidget(QLabel("Response:"))
        self.response_view = QTextEdit()
        self.response_view.setReadOnly(True)
        layout.addWidget(self.response_view, 1)

        # Stats bar
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #484f58; font-size: 11px;")
        layout.addWidget(self.stats_label)

        self._response_text = ""

    def _run(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.response_view.clear()
        self._response_text = ""
        self.stats_label.setText("")

        model = self.model_combo.currentText()
        system = self.system_input.toPlainText().strip()
        temp = self.temp_slider.value() / 100

        from ..core.api import WorkerFactory
        from ..utils.constants import DEFAULT_GEN_PARAMS

        gen_params = dict(DEFAULT_GEN_PARAMS)
        gen_params["temperature"] = temp
        messages = [{"role": "user", "content": prompt}]

        worker = WorkerFactory(model, messages, system, gen_params, self.settings_data)
        worker.token_received.connect(self._on_token)
        worker.response_finished.connect(self._on_done)
        worker.error_occurred.connect(self._on_error)
        worker.start()
        self._workers.append(worker)

    def _on_token(self, token):
        self._response_text += token
        self.response_view.setPlainText(self._response_text)

    def _on_done(self, text, stats):
        self._response_text = text
        self.response_view.setPlainText(text)
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run")
        tokens = stats.get("eval_count", 0)
        duration = stats.get("eval_duration", 0)
        if duration > 1e6:
            tps = tokens / (duration / 1e9)
            self.stats_label.setText(f"{tokens} tokens | {tps:.1f} tok/s")
        elif tokens:
            self.stats_label.setText(f"{tokens} tokens")

    def _on_error(self, err):
        self.response_view.setPlainText(f"Error: {err}")
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run")

    def _clear(self):
        self.prompt_input.clear()
        self.system_input.clear()
        self.response_view.clear()
        self.stats_label.clear()
        self._response_text = ""

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        input_bg = theme.get("input_bg", "#0d1117")
        fg = theme.get("fg", "#e6edf3")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#238636")
        self.setStyleSheet(f"""
            QDialog {{ background: {bg}; }}
            QTextEdit {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; border-radius: 6px; padding: 8px; }}
            QLabel {{ color: {fg}; }}
            QPushButton {{ background: {accent}; color: white; border: none; padding: 8px 20px; border-radius: 6px; font-weight: bold; }}
            QPushButton:hover {{ background: {accent}; }}
            QPushButton:disabled {{ background: {border}; color: #484f58; }}
            QComboBox {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; padding: 4px 8px; border-radius: 4px; }}
        """)
