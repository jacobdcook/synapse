import logging
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QScrollArea, QFrame, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
log = logging.getLogger(__name__)

class ReplayDialog(QDialog):
    """
    A dialog for turn-by-turn playback of a conversation history.
    Useful for reviewing long agentic loops or complex multi-turn chats.
    """
    def __init__(self, conversation, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Session Replay: {conversation.get('title', 'Untitled')}")
        self.resize(800, 600)
        
        self.messages = conversation.get("messages", [])
        self.current_idx = 0
        
        self._setup_ui()
        self._update_display()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Info Header
        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: #888; font-weight: bold;")
        layout.addWidget(self.info_label)
        
        # Display Area (using QWebEngineView or just a ScrollArea with labels)
        # Since ChatRenderer builds full HTML, a simple QWebEngineView would be best,
        # but for turn-by-turn replay, we might want just the current message.
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("background: #0d1117;")
        
        self.content_view = QTextEdit()
        self.content_view.setReadOnly(True)
        self.content_view.setFrameShape(QFrame.NoFrame)
        # We can't easily use the full ChatRenderer HTML in a QTextEdit, 
        # but we can render simplified markdown or HTML.
        # For simplicity and performance, let's just use the messages directly.
        
        self.scroll.setWidget(self.content_view)
        layout.addWidget(self.scroll)
        
        # Controls
        ctrl_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("<< Start")
        self.prev_btn = QPushButton("< Prev")
        self.next_btn = QPushButton("Next >")
        self.end_btn = QPushButton("End >>")
        
        self.start_btn.clicked.connect(self._go_start)
        self.prev_btn.clicked.connect(self._go_prev)
        self.next_btn.clicked.connect(self._go_next)
        self.end_btn.clicked.connect(self._go_end)
        
        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.prev_btn)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.next_btn)
        ctrl_layout.addWidget(self.end_btn)
        
        layout.addLayout(ctrl_layout)

    def _update_display(self):
        if not self.messages:
            self.content_view.setPlainText("No messages to replay.")
            self.info_label.setText("0 / 0")
            return
            
        msg = self.messages[self.current_idx]
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        
        # Simple formatting for now
        # Ideally we'd use ChatRenderer.render_markdown but that returns HTML
        # QTextEdit supports some HTML
        html = f"<div style='color: #58a6ff; font-weight: bold;'>{role.upper()}</div>"
        html += f"<div style='color: #e6edf3; margin-top: 10px; font-family: sans-serif; line-height: 1.4;'>{content.replace('\n', '<br>')}</div>"
        
        self.content_view.setHtml(html)
        self.info_label.setText(f"Message {self.current_idx + 1} / {len(self.messages)}")
        
        self.prev_btn.setEnabled(self.current_idx > 0)
        self.start_btn.setEnabled(self.current_idx > 0)
        self.next_btn.setEnabled(self.current_idx < len(self.messages) - 1)
        self.end_btn.setEnabled(self.current_idx < len(self.messages) - 1)

    def _go_start(self):
        self.current_idx = 0
        self._update_display()

    def _go_prev(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self._update_display()

    def _go_next(self):
        if self.current_idx < len(self.messages) - 1:
            self.current_idx += 1
            self._update_display()

    def _go_end(self):
        self.current_idx = len(self.messages) - 1
        self._update_display()
