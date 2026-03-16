from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel,
    QPushButton, QComboBox, QWidget, QSlider, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt


class PromptLabColumn(QFrame):
    """Single comparison column with its own model/system/temp config."""

    def __init__(self, models, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background: #161b22; border: 1px solid #30363d; border-radius: 8px; }")
        self._buf = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        self.model_combo = QComboBox()
        self.model_combo.addItems(models)
        layout.addWidget(self.model_combo)

        self.system_input = QTextEdit()
        self.system_input.setPlaceholderText("System prompt (optional)")
        self.system_input.setMaximumHeight(50)
        layout.addWidget(self.system_input)

        temp_row = QHBoxLayout()
        temp_row.addWidget(QLabel("Temp:"))
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(0, 200)
        self.temp_slider.setValue(70)
        self.temp_label = QLabel("0.7")
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"{v/100:.1f}"))
        temp_row.addWidget(self.temp_slider)
        temp_row.addWidget(self.temp_label)
        layout.addLayout(temp_row)

        self.response_view = QTextEdit()
        self.response_view.setReadOnly(True)
        self.response_view.setPlaceholderText("Response...")
        layout.addWidget(self.response_view, 1)

        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("color: #484f58; font-size: 10px; border: none;")
        layout.addWidget(self.stats_label)


class PromptLab(QDialog):
    """Multi-column prompt comparison — same prompt, different configs."""

    def __init__(self, models, settings_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Prompt Lab")
        self.resize(1200, 750)
        self.settings_data = settings_data
        self.models = models
        self._workers = []

        self.setStyleSheet("""
            QDialog { background: #1a1b1e; }
            QTextEdit { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px; padding: 6px; }
            QLabel { color: #8b949e; }
            QPushButton { background: #238636; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #2ea043; }
            QPushButton#add_btn { background: #21262d; color: #c9d1d9; }
            QPushButton#add_btn:hover { background: #30363d; }
            QComboBox { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; padding: 4px; border-radius: 4px; }
            QSlider::groove:horizontal { background: #30363d; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #58a6ff; width: 12px; margin: -4px 0; border-radius: 6px; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Shared Prompt:"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Enter your prompt — it will be sent to all columns...")
        self.prompt_input.setMaximumHeight(80)
        layout.addWidget(self.prompt_input)

        # Columns
        self.columns_layout = QHBoxLayout()
        self.columns = []
        for _ in range(2):
            self._add_column()
        layout.addLayout(self.columns_layout, 1)

        # Buttons
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Column")
        add_btn.setObjectName("add_btn")
        add_btn.clicked.connect(self._add_column)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        run_btn = QPushButton("Run All")
        run_btn.clicked.connect(self._run_all)
        btn_row.addWidget(run_btn)
        layout.addLayout(btn_row)

    def _add_column(self):
        if len(self.columns) >= 4:
            return
        col = PromptLabColumn(self.models)
        # Offset default model so columns start with different models
        if len(self.columns) < len(self.models):
            col.model_combo.setCurrentIndex(len(self.columns))
        self.columns.append(col)
        self.columns_layout.addWidget(col)

    def _run_all(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            return

        from ..core.api import WorkerFactory
        from ..utils.constants import DEFAULT_GEN_PARAMS

        for col in self.columns:
            col.response_view.clear()
            col._buf = ""
            col.stats_label.clear()

            model = col.model_combo.currentText()
            system = col.system_input.toPlainText().strip()
            temp = col.temp_slider.value() / 100
            gen_params = dict(DEFAULT_GEN_PARAMS)
            gen_params["temperature"] = temp
            messages = [{"role": "user", "content": prompt}]

            worker = WorkerFactory(model, messages, system, gen_params, self.settings_data)
            worker.token_received.connect(lambda tok, c=col: self._stream(c, tok))
            worker.response_finished.connect(lambda text, stats, c=col: self._done(c, text, stats))
            worker.error_occurred.connect(lambda err, c=col: c.response_view.setPlainText(f"Error: {err}"))
            worker.start()
            self._workers.append(worker)

    def _stream(self, col, token):
        col._buf += token
        col.response_view.setPlainText(col._buf)

    def _done(self, col, text, stats):
        col.response_view.setPlainText(text)
        tokens = stats.get("eval_count", 0)
        duration = stats.get("eval_duration", 0)
        if duration > 0:
            tps = tokens / (duration / 1e9) if duration > 1e6 else 0
            col.stats_label.setText(f"{tokens} tok | {tps:.1f} tok/s")
        elif tokens:
            col.stats_label.setText(f"{tokens} tok")
