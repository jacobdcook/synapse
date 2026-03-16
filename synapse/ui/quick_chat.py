from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont


class QuickChatWidget(QWidget):
    """Floating quick-chat popup triggered from system tray."""
    closed = pyqtSignal()

    def __init__(self, models=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedSize(500, 380)
        self._response_text = ""
        self._worker = None

        self.setStyleSheet("""
            QWidget { background: #1e1f23; border: 1px solid #30363d; border-radius: 10px; }
            QTextEdit { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px; padding: 6px; }
            QPushButton { background: #238636; color: white; border: none; padding: 6px 16px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #2ea043; }
            QPushButton#close_btn { background: transparent; color: #8b949e; font-size: 16px; padding: 2px 8px; }
            QPushButton#close_btn:hover { color: #ff6b6b; }
            QComboBox { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; padding: 4px; border-radius: 4px; }
            QLabel { color: #8b949e; border: none; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Quick Chat")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #e6edf3; border: none;")
        header.addWidget(title)
        header.addStretch()
        self.model_combo = QComboBox()
        self.model_combo.setFixedWidth(160)
        if models:
            self.model_combo.addItems(models)
        header.addWidget(self.model_combo)
        close_btn = QPushButton("\u2715")
        close_btn.setObjectName("close_btn")
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("Ask a quick question...")
        self.input_box.setMaximumHeight(60)
        self.input_box.setFont(QFont("monospace", 10))
        layout.addWidget(self.input_box)

        btn_row = QHBoxLayout()
        self.send_btn = QPushButton("Ask")
        self.send_btn.clicked.connect(self._send)
        btn_row.addStretch()
        btn_row.addWidget(self.send_btn)
        layout.addLayout(btn_row)

        self.response_box = QTextEdit()
        self.response_box.setReadOnly(True)
        self.response_box.setPlaceholderText("Response will appear here...")
        self.response_box.setFont(QFont("monospace", 10))
        layout.addWidget(self.response_box, 1)

    def set_models(self, models):
        current = self.model_combo.currentText()
        self.model_combo.clear()
        self.model_combo.addItems(models)
        idx = self.model_combo.findText(current)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

    def _send(self):
        text = self.input_box.toPlainText().strip()
        if not text:
            return
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Thinking...")
        self.response_box.clear()
        self._response_text = ""

        model = self.model_combo.currentText()
        if not model:
            self.response_box.setPlainText("No model selected.")
            self.send_btn.setEnabled(True)
            self.send_btn.setText("Ask")
            return

        from ..core.api import WorkerFactory
        from ..utils.constants import DEFAULT_GEN_PARAMS, load_settings
        settings = load_settings()
        messages = [{"role": "user", "content": text}]
        self._worker = WorkerFactory(model, messages, "Be concise.", DEFAULT_GEN_PARAMS, settings)
        self._worker.token_received.connect(self._on_token)
        self._worker.response_finished.connect(self._on_done)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_token(self, token):
        self._response_text += token
        self.response_box.setPlainText(self._response_text)

    def _on_done(self, text, stats):
        self._response_text = text
        self.response_box.setPlainText(text)
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Ask")

    def _on_error(self, err):
        self.response_box.setPlainText(f"Error: {err}")
        self.send_btn.setEnabled(True)
        self.send_btn.setText("Ask")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        elif event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            self._send()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def showAtCursor(self):
        from PyQt5.QtGui import QCursor
        pos = QCursor.pos()
        self.move(pos.x() - 250, pos.y() - 200)
        self.show()
        self.input_box.setFocus()
        self.raise_()
        self.activateWindow()

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1e1f23")
        input_bg = theme.get("input_bg", "#0d1117")
        fg = theme.get("fg", "#e6edf3")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#238636")
        self.setStyleSheet(f"""
            QWidget {{ background: {bg}; border: 1px solid {border}; border-radius: 10px; }}
            QTextEdit {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; border-radius: 6px; padding: 6px; }}
            QPushButton {{ background: {accent}; color: white; border: none; padding: 6px 16px; border-radius: 6px; font-weight: bold; }}
            QPushButton:hover {{ background: {accent}; }}
            QPushButton#close_btn {{ background: transparent; color: {fg}; font-size: 16px; padding: 2px 8px; }}
            QPushButton#close_btn:hover {{ color: #ff6b6b; }}
            QComboBox {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; padding: 4px; border-radius: 4px; }}
            QLabel {{ color: {fg}; border: none; }}
        """)
