from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel,
    QPushButton, QCheckBox, QFrame
)
from PyQt5.QtCore import Qt


class ConsensusDialog(QDialog):
    """Multi-model consensus: send same prompt to N models, optionally synthesize."""

    def __init__(self, models, settings_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Multi-Model Consensus")
        self.resize(1200, 750)
        self.settings_data = settings_data
        self.models = models
        self._workers = []
        self._responses = {}
        self._bufs = {}

        self.setStyleSheet("""
            QDialog { background: #1a1b1e; }
            QTextEdit { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px; padding: 6px; }
            QLabel { color: #8b949e; }
            QPushButton { background: #238636; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #2ea043; }
            QPushButton:disabled { background: #21262d; color: #484f58; }
            QCheckBox { color: #c9d1d9; spacing: 6px; }
            QFrame { background: #161b22; border: 1px solid #30363d; border-radius: 8px; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Prompt:"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Enter your prompt...")
        self.prompt_input.setMaximumHeight(80)
        layout.addWidget(self.prompt_input)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Models:"))
        self.model_checks = []
        for m in models[:8]:
            cb = QCheckBox(m)
            if len(self.model_checks) < 3:
                cb.setChecked(True)
            self.model_checks.append(cb)
            model_row.addWidget(cb)
        model_row.addStretch()
        layout.addLayout(model_row)

        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Run All")
        self.run_btn.clicked.connect(self._run)
        btn_row.addWidget(self.run_btn)
        self.synth_btn = QPushButton("Synthesize")
        self.synth_btn.setEnabled(False)
        self.synth_btn.clicked.connect(self._synthesize)
        btn_row.addWidget(self.synth_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.panels_layout = QHBoxLayout()
        self.panels = {}
        layout.addLayout(self.panels_layout, 1)

        self.synth_label = QLabel("Synthesis:")
        self.synth_label.setStyleSheet("font-weight: bold; color: #58a6ff;")
        self.synth_label.hide()
        layout.addWidget(self.synth_label)
        self.synth_view = QTextEdit()
        self.synth_view.setReadOnly(True)
        self.synth_view.setMaximumHeight(150)
        self.synth_view.hide()
        layout.addWidget(self.synth_view)

    def _run(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            return

        selected = [cb.text() for cb in self.model_checks if cb.isChecked()]
        if len(selected) < 2:
            return

        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.synth_btn.setEnabled(False)
        self._responses = {}
        self._bufs = {}

        while self.panels_layout.count():
            w = self.panels_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.panels = {}

        from ..core.api import WorkerFactory
        from ..utils.constants import DEFAULT_GEN_PARAMS

        messages = [{"role": "user", "content": prompt}]

        for model in selected:
            frame = QFrame()
            fl = QVBoxLayout(frame)
            label = QLabel(model)
            label.setStyleSheet("font-weight: bold; color: #e6edf3; border: none;")
            fl.addWidget(label)
            tv = QTextEdit()
            tv.setReadOnly(True)
            fl.addWidget(tv)
            self.panels_layout.addWidget(frame)
            self.panels[model] = tv
            self._bufs[model] = ""

            worker = WorkerFactory(model, messages, "", DEFAULT_GEN_PARAMS, settings=self.settings_data, tools=[])
            worker.token_received.connect(lambda tok, m=model: self._stream(m, tok))
            worker.response_finished.connect(lambda text, stats, m=model: self._done(m, text))
            worker.error_occurred.connect(lambda err, m=model: self._on_error(m, err))
            worker.start()
            self._workers.append(worker)

    def _stream(self, model, token):
        self._bufs[model] = self._bufs.get(model, "") + token
        if model in self.panels:
            self.panels[model].setPlainText(self._bufs[model])

    def _done(self, model, text):
        self._responses[model] = text
        if model in self.panels:
            self.panels[model].setPlainText(text)
        selected = [cb.text() for cb in self.model_checks if cb.isChecked()]
        if len(self._responses) >= len(selected):
            self.run_btn.setEnabled(True)
            self.run_btn.setText("Run All")
            self.synth_btn.setEnabled(True)

    def _on_error(self, model, err):
        if model in self.panels:
            self.panels[model].setPlainText(f"Error: {err}")
        self._responses[model] = f"Error: {err}"

    def _synthesize(self):
        if len(self._responses) < 2:
            return
        self.synth_btn.setEnabled(False)
        self.synth_btn.setText("Synthesizing...")
        self.synth_label.show()
        self.synth_view.show()
        self.synth_view.clear()

        summary = "You are a consensus synthesizer. Compare these responses and provide a synthesized answer:\n\n"
        for m, text in self._responses.items():
            summary += f"--- {m} ---\n{text}\n\n"
        summary += "Provide a final, high-quality synthesized response combining the best parts."

        from ..core.api import WorkerFactory
        from ..utils.constants import DEFAULT_GEN_PARAMS

        judge = [cb.text() for cb in self.model_checks if cb.isChecked()][0]
        messages = [{"role": "user", "content": summary}]
        self._synth_buf = ""

        worker = WorkerFactory(judge, messages, "", DEFAULT_GEN_PARAMS, settings=self.settings_data, tools=[])
        worker.token_received.connect(self._synth_stream)
        worker.response_finished.connect(self._synth_done)
        worker.start()
        self._workers.append(worker)

    def _synth_stream(self, token):
        self._synth_buf += token
        self.synth_view.setPlainText(self._synth_buf)

    def _synth_done(self, text, stats):
        self.synth_view.setPlainText(text)
        self.synth_btn.setEnabled(True)
        self.synth_btn.setText("Synthesize")
