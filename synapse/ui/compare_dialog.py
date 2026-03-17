import json
import logging
import time
import urllib.request
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QTextEdit, QComboBox, QPushButton, QWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from ..utils.constants import get_ollama_url, DEFAULT_GEN_PARAMS

log = logging.getLogger(__name__)


class CompareWorker(QThread):
    token_received = pyqtSignal(int, str)  # slot_index, token
    finished = pyqtSignal(int, str, float)  # slot_index, full_text, tok_per_sec

    def __init__(self, slot_index, model, messages, system_prompt="", gen_params=None):
        super().__init__()
        self.slot_index = slot_index
        self.model = model
        self.messages = messages
        self.system_prompt = system_prompt
        self.gen_params = gen_params or DEFAULT_GEN_PARAMS

    def run(self):
        try:
            api_messages = []
            if self.system_prompt:
                api_messages.append({"role": "system", "content": self.system_prompt})
            for m in self.messages:
                if m.get("role") in ("user", "assistant"):
                    api_messages.append({"role": m["role"], "content": m.get("content", "")})

            payload = json.dumps({
                "model": self.model,
                "messages": api_messages,
                "stream": True,
                "options": {k: v for k, v in self.gen_params.items() if k in ("temperature", "top_p", "num_ctx")}
            }).encode()

            req = urllib.request.Request(
                f"{get_ollama_url()}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )

            full_text = ""
            token_count = 0
            start = time.time()

            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    try:
                        chunk = json.loads(line.decode().strip())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if "message" in chunk and "content" in chunk["message"]:
                        token = chunk["message"]["content"]
                        full_text += token
                        token_count += 1
                        self.token_received.emit(self.slot_index, token)

            elapsed = time.time() - start
            tps = token_count / elapsed if elapsed > 0 else 0
            self.finished.emit(self.slot_index, full_text, tps)
        except Exception as e:
            self.finished.emit(self.slot_index, f"Error: {e}", 0)


class CompareDialog(QDialog):
    def __init__(self, prompt, messages, models, system_prompt="", gen_params=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Compare Models")
        self.setMinimumSize(1000, 600)
        self.workers = []

        layout = QVBoxLayout(self)

        header = QLabel(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
        header.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        self.panels = []

        for i, model in enumerate(models[:3]):
            panel = QWidget()
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(4, 4, 4, 4)

            model_label = QLabel(model)
            model_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #58a6ff;")
            panel_layout.addWidget(model_label)

            status_label = QLabel("Generating...")
            status_label.setStyleSheet("color: #8b949e; font-size: 11px;")
            panel_layout.addWidget(status_label)

            text_view = QTextEdit()
            text_view.setReadOnly(True)
            text_view.setStyleSheet("background: #0d1117; color: #e6edf3; border: 1px solid #30363d; font-size: 13px;")
            panel_layout.addWidget(text_view)

            splitter.addWidget(panel)
            self.panels.append({"view": text_view, "status": status_label, "model": model})

            worker = CompareWorker(i, model, messages, system_prompt, gen_params)
            worker.token_received.connect(self._on_token)
            worker.finished.connect(self._on_finished)
            worker.start()
            self.workers.append(worker)

        layout.addWidget(splitter)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def _on_token(self, slot, token):
        if slot < len(self.panels):
            self.panels[slot]["view"].insertPlainText(token)

    def _on_finished(self, slot, full_text, tps):
        if slot < len(self.panels):
            self.panels[slot]["status"].setText(f"Done \u00b7 {tps:.1f} tok/s")

    def closeEvent(self, event):
        for w in self.workers:
            try:
                w.token_received.disconnect()
                w.finished.disconnect()
            except (TypeError, RuntimeError):
                pass
            if w.isRunning():
                w.terminate()
                w.wait(2000)
        super().closeEvent(event)

    def apply_theme(self, theme):
        fg = theme.get("fg", "#e6edf3")
        input_bg = theme.get("input_bg", "#0d1117")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#58a6ff")
        for panel in self.panels:
            panel["view"].setStyleSheet(f"background: {input_bg}; color: {fg}; border: 1px solid {border}; font-size: 13px;")
            panel["status"].setStyleSheet(f"color: {border}; font-size: 11px;")
