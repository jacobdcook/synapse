#!/usr/bin/env python3
"""Synapse - A multi-model AI chat client for local Ollama models."""

import sys
import os
import json
import uuid
import re
import urllib.request
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QSettings, QSize, QTimer
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QLineEdit, QPushButton,
    QComboBox, QLabel, QPlainTextEdit, QStatusBar, QMenu, QAction,
    QDialog, QDialogButtonBox, QInputDialog, QMessageBox, QSizePolicy,
    QFileDialog
)
from PyQt5.QtGui import QFont, QIcon, QKeySequence, QColor
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage

import markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter

APP_NAME = "Synapse"
OLLAMA_URL = "http://localhost:11434"
DATA_DIR = Path.home() / ".local" / "share" / "synapse"
CONV_DIR = DATA_DIR / "conversations"
SETTINGS_FILE = DATA_DIR / "settings.json"
DEFAULT_MODEL = "qwen2.5:14b"
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."

DARK_THEME_QSS = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #cccccc;
    font-family: 'Segoe UI', 'Ubuntu', 'Cantarell', sans-serif;
    font-size: 13px;
}
QSplitter::handle {
    background-color: #3e3e3e;
    width: 1px;
}
QListWidget {
    background-color: #252526;
    border: none;
    outline: none;
    padding: 4px;
}
QListWidget::item {
    padding: 10px 12px;
    border-radius: 6px;
    margin: 1px 4px;
    color: #cccccc;
}
QListWidget::item:hover {
    background-color: #2a2d2e;
}
QListWidget::item:selected {
    background-color: #37373d;
    color: #ffffff;
}
QLineEdit {
    background-color: #3c3c3c;
    border: 1px solid #3e3e3e;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cccccc;
    selection-background-color: #0078d4;
}
QLineEdit:focus {
    border-color: #0078d4;
}
QPlainTextEdit {
    background-color: #2d2d2d;
    border: 1px solid #3e3e3e;
    border-radius: 8px;
    padding: 10px;
    color: #cccccc;
    selection-background-color: #0078d4;
    font-size: 14px;
}
QPlainTextEdit:focus {
    border-color: #0078d4;
}
QPushButton {
    background-color: #0078d4;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #1a8ae8;
}
QPushButton:pressed {
    background-color: #005fa3;
}
QPushButton:disabled {
    background-color: #3e3e3e;
    color: #808080;
}
QPushButton#sidebarBtn {
    background-color: transparent;
    color: #cccccc;
    text-align: left;
    padding: 8px 12px;
    border-radius: 6px;
}
QPushButton#sidebarBtn:hover {
    background-color: #2a2d2e;
}
QPushButton#newChatBtn {
    background-color: #0078d4;
    font-size: 14px;
    padding: 10px;
    margin: 8px;
    border-radius: 8px;
}
QPushButton#stopBtn {
    background-color: #d32f2f;
}
QPushButton#stopBtn:hover {
    background-color: #e53935;
}
QPushButton#sendBtn {
    background-color: #0078d4;
    border-radius: 18px;
    min-width: 36px;
    min-height: 36px;
    max-width: 36px;
    max-height: 36px;
    font-size: 16px;
    padding: 0;
}
QPushButton#systemPromptBtn {
    background-color: transparent;
    color: #808080;
    border: 1px solid #3e3e3e;
    font-weight: normal;
    padding: 4px 10px;
    font-size: 12px;
}
QPushButton#systemPromptBtn:hover {
    color: #cccccc;
    border-color: #0078d4;
}
QComboBox {
    background-color: #3c3c3c;
    border: 1px solid #3e3e3e;
    border-radius: 6px;
    padding: 5px 10px;
    color: #cccccc;
    min-width: 160px;
}
QComboBox:hover {
    border-color: #0078d4;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    border: 1px solid #3e3e3e;
    color: #cccccc;
    selection-background-color: #0078d4;
}
QStatusBar {
    background-color: #007acc;
    color: white;
    font-size: 12px;
    padding: 2px;
}
QLabel#titleLabel {
    font-size: 15px;
    font-weight: bold;
    color: #ffffff;
    padding: 0 8px;
}
QLabel#sidebarTitle {
    color: #808080;
    font-size: 11px;
    font-weight: bold;
    padding: 8px 16px 4px 16px;
    text-transform: uppercase;
}
QMenu {
    background-color: #2d2d2d;
    border: 1px solid #3e3e3e;
    border-radius: 6px;
    padding: 4px;
    color: #cccccc;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #0078d4;
}
QDialog {
    background-color: #1e1e1e;
}
"""

CHAT_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background-color: #1e1e1e;
    color: #cccccc;
    font-family: 'Segoe UI', 'Ubuntu', 'Cantarell', sans-serif;
    font-size: 15px;
    line-height: 1.6;
    padding: 20px;
    padding-bottom: 40px;
}
.message {
    max-width: 85%;
    margin: 12px 0;
    padding: 14px 18px;
    border-radius: 12px;
    word-wrap: break-word;
    overflow-wrap: break-word;
}
.user {
    background-color: #2b5278;
    margin-left: auto;
    border-bottom-right-radius: 4px;
    color: #e0e0e0;
}
.assistant {
    background-color: #2d2d2d;
    margin-right: auto;
    border-bottom-left-radius: 4px;
}
.message-header {
    font-size: 11px;
    color: #808080;
    margin-bottom: 6px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.user .message-header { color: #8ab4d6; }
.assistant .message-header { color: #808080; }
.message-meta {
    font-size: 10px;
    color: #606060;
    margin-top: 8px;
    text-align: right;
}
pre {
    background-color: #1a1a1a;
    border: 1px solid #3e3e3e;
    border-radius: 8px;
    padding: 0;
    margin: 10px 0;
    overflow-x: auto;
    position: relative;
}
pre .code-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: #2d2d2d;
    padding: 6px 12px;
    border-bottom: 1px solid #3e3e3e;
    border-radius: 8px 8px 0 0;
    font-size: 12px;
    color: #808080;
}
pre .code-header button {
    background: transparent;
    border: 1px solid #555;
    color: #aaa;
    padding: 2px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
}
pre .code-header button:hover {
    background: #3e3e3e;
    color: #fff;
}
pre code {
    display: block;
    padding: 14px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.5;
}
code {
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
    background-color: #363636;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
}
pre code { background: transparent; padding: 0; }
p { margin: 8px 0; }
ul, ol { margin: 8px 0; padding-left: 24px; }
li { margin: 4px 0; }
table {
    border-collapse: collapse;
    margin: 10px 0;
    width: 100%;
}
th, td {
    border: 1px solid #3e3e3e;
    padding: 8px 12px;
    text-align: left;
}
th { background-color: #2d2d2d; font-weight: bold; }
blockquote {
    border-left: 3px solid #0078d4;
    padding-left: 14px;
    margin: 10px 0;
    color: #999;
}
h1, h2, h3, h4 { color: #e0e0e0; margin: 12px 0 6px 0; }
a { color: #4fc3f7; }
hr { border: none; border-top: 1px solid #3e3e3e; margin: 16px 0; }
.welcome {
    text-align: center;
    padding: 80px 20px;
    color: #555;
}
.welcome h1 {
    font-size: 32px;
    color: #0078d4;
    margin-bottom: 6px;
    font-weight: 700;
}
.welcome .tagline {
    color: #666;
    font-size: 15px;
    margin-bottom: 24px;
}
.welcome .models-hint {
    color: #555;
    font-size: 13px;
    margin-top: 16px;
}
#streaming-content {
    background-color: #2d2d2d;
    max-width: 85%;
    margin: 12px 0;
    padding: 14px 18px;
    border-radius: 12px;
    border-bottom-left-radius: 4px;
    white-space: pre-wrap;
    word-wrap: break-word;
    display: none;
}
#streaming-header {
    font-size: 11px;
    color: #808080;
    margin-bottom: 6px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.typing-indicator {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: #0078d4;
    border-radius: 50%;
    animation: pulse 1s infinite;
    margin-left: 4px;
    vertical-align: middle;
}
@keyframes pulse {
    0%, 100% { opacity: 0.3; }
    50% { opacity: 1; }
}
PYGMENTS_CSS
</style>
</head>
<body>
MESSAGES_HTML
<div id="streaming-content">
    <div id="streaming-header">Assistant</div>
    <div id="streaming-text"></div>
</div>
<script>
function copyCode(btn) {
    const code = btn.closest('.code-header').nextElementSibling;
    const text = code.textContent;
    navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    });
}
function appendToken(token) {
    const el = document.getElementById('streaming-text');
    const container = document.getElementById('streaming-content');
    container.style.display = 'block';
    el.textContent += token;
    window.scrollTo(0, document.body.scrollHeight);
}
function clearStreaming() {
    document.getElementById('streaming-text').textContent = '';
    document.getElementById('streaming-content').style.display = 'none';
}
window.scrollTo(0, document.body.scrollHeight);
</script>
</body>
</html>"""


# --- Conversation Store ---

class ConversationStore:
    def __init__(self):
        CONV_DIR.mkdir(parents=True, exist_ok=True)

    def list_conversations(self):
        convos = []
        for f in CONV_DIR.glob("*.json"):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                    convos.append({
                        "id": data["id"],
                        "title": data.get("title", "Untitled"),
                        "updated_at": data.get("updated_at", ""),
                        "model": data.get("model", DEFAULT_MODEL),
                    })
            except (json.JSONDecodeError, KeyError):
                continue
        convos.sort(key=lambda c: c["updated_at"], reverse=True)
        return convos

    def load(self, conv_id):
        path = CONV_DIR / f"{conv_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def save(self, conversation):
        conversation["updated_at"] = datetime.now().isoformat()
        path = CONV_DIR / f"{conversation['id']}.json"
        with open(path, "w") as f:
            json.dump(conversation, f, indent=2)

    def delete(self, conv_id):
        path = CONV_DIR / f"{conv_id}.json"
        if path.exists():
            path.unlink()

    def search(self, query):
        query = query.lower()
        results = []
        for c in self.list_conversations():
            if query in c["title"].lower():
                results.append(c)
                continue
            full = self.load(c["id"])
            if full:
                for msg in full.get("messages", []):
                    if query in msg.get("content", "").lower():
                        results.append(c)
                        break
        return results


def new_conversation(model=DEFAULT_MODEL, system_prompt=DEFAULT_SYSTEM_PROMPT):
    return {
        "id": str(uuid.uuid4()),
        "title": "New Chat",
        "model": model,
        "system_prompt": system_prompt,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "messages": [],
    }


# --- Settings ---

def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"model": DEFAULT_MODEL, "system_prompt": DEFAULT_SYSTEM_PROMPT}


def save_settings(settings):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


# --- Ollama Model Manager ---

def unload_model(model_name):
    """Unload a model from VRAM by setting keep_alive to 0."""
    try:
        payload = json.dumps({
            "model": model_name,
            "keep_alive": 0,
        }).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception:
        pass


class ModelSwitcher(QThread):
    """Unloads old model from VRAM, then signals ready for new model."""
    switch_complete = pyqtSignal(str)  # new model name
    status_update = pyqtSignal(str)

    def __init__(self, old_model, new_model):
        super().__init__()
        self.old_model = old_model
        self.new_model = new_model

    def run(self):
        if self.old_model and self.old_model != self.new_model:
            self.status_update.emit(f"Unloading {self.old_model}...")
            unload_model(self.old_model)
        self.status_update.emit(f"Ready: {self.new_model}")
        self.switch_complete.emit(self.new_model)


class OllamaWorker(QThread):
    token_received = pyqtSignal(str)
    response_finished = pyqtSignal(str, dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, model, messages, system_prompt=""):
        super().__init__()
        self.model = model
        self.messages = messages
        self.system_prompt = system_prompt
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        try:
            api_messages = []
            if self.system_prompt:
                api_messages.append({"role": "system", "content": self.system_prompt})
            for msg in self.messages:
                api_messages.append({"role": msg["role"], "content": msg["content"]})

            payload = json.dumps({
                "model": self.model,
                "messages": api_messages,
                "stream": True,
            }).encode()

            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )

            full_text = ""
            stats = {}
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    if self._stop_flag:
                        break
                    try:
                        chunk = json.loads(line.decode().strip())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if "message" in chunk and "content" in chunk["message"]:
                        token = chunk["message"]["content"]
                        full_text += token
                        self.token_received.emit(token)
                    if chunk.get("done"):
                        stats = {
                            "total_duration": chunk.get("total_duration", 0),
                            "eval_count": chunk.get("eval_count", 0),
                            "eval_duration": chunk.get("eval_duration", 0),
                        }

            self.response_finished.emit(full_text, stats)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ModelLoader(QThread):
    models_loaded = pyqtSignal(list)

    def run(self):
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                models.sort()
                self.models_loaded.emit(models)
        except Exception:
            self.models_loaded.emit([DEFAULT_MODEL])


# --- Chat Renderer ---

class ChatRenderer:
    def __init__(self):
        self.formatter = HtmlFormatter(style="monokai", noclasses=True, nowrap=False)
        self.pygments_css = HtmlFormatter(style="monokai").get_style_defs('.highlight')
        self.md = markdown.Markdown(extensions=[
            'fenced_code', 'tables', 'nl2br', 'sane_lists'
        ])

    def render_markdown(self, text):
        self.md.reset()
        html = self.md.convert(text)
        def add_code_header(match):
            lang = ""
            lang_match = re.search(r'class="[^"]*language-(\w+)', match.group(0))
            if lang_match:
                lang = lang_match.group(1)
            code_content = match.group(0)
            return (f'<pre><div class="code-header"><span>{lang}</span>'
                    f'<button onclick="copyCode(this)">Copy</button></div>'
                    f'{code_content[4:]}')
        html = re.sub(r'<pre><code[^>]*>.*?</code></pre>', add_code_header, html, flags=re.DOTALL)
        return html

    def build_html(self, messages, model_name=""):
        msgs_html = ""
        if not messages:
            msgs_html = (
                '<div class="welcome">'
                f'<h1>{APP_NAME}</h1>'
                '<p class="tagline">Your local AI, multiple minds, one interface</p>'
                '<p class="models-hint">Select a model from the dropdown above to get started</p>'
                '</div>'
            )
        else:
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                header = "You" if role == "user" else "Assistant"
                css_class = role

                if role == "user":
                    rendered = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    rendered = rendered.replace("\n", "<br>")
                else:
                    rendered = self.render_markdown(content)

                meta = ""
                if role == "assistant" and msg.get("model"):
                    parts = [msg["model"]]
                    if msg.get("duration_ms"):
                        parts.append(f"{msg['duration_ms'] / 1000:.1f}s")
                    if msg.get("tokens"):
                        parts.append(f"{msg['tokens']} tokens")
                    meta = f'<div class="message-meta">{" · ".join(parts)}</div>'

                msgs_html += (f'<div class="message {css_class}">'
                              f'<div class="message-header">{header}</div>'
                              f'{rendered}{meta}</div>\n')

        template = CHAT_HTML_TEMPLATE.replace("PYGMENTS_CSS", self.pygments_css)
        return template.replace("MESSAGES_HTML", msgs_html)


# --- System Prompt Dialog ---

class SystemPromptDialog(QDialog):
    def __init__(self, parent, current_prompt):
        super().__init__(parent)
        self.setWindowTitle("System Prompt")
        self.setMinimumSize(500, 300)
        layout = QVBoxLayout(self)

        label = QLabel("Set the system prompt for this conversation:")
        layout.addWidget(label)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(current_prompt)
        self.editor.setPlaceholderText("You are a helpful assistant.")
        layout.addWidget(self.editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_prompt(self):
        return self.editor.toPlainText().strip()


# --- Input Widget ---

class InputWidget(QWidget):
    message_submitted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Type a message... (Enter to send, Shift+Enter for new line)")
        self.text_edit.setMaximumHeight(150)
        self.text_edit.setMinimumHeight(44)
        self.text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.text_edit.textChanged.connect(self._auto_resize)
        layout.addWidget(self.text_edit)

        self.send_btn = QPushButton("\u2191")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setToolTip("Send (Enter)")
        self.send_btn.clicked.connect(self._submit)
        layout.addWidget(self.send_btn, alignment=Qt.AlignBottom)

        self.stop_btn = QPushButton("\u25a0")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setToolTip("Stop generating")
        self.stop_btn.setFixedSize(36, 36)
        self.stop_btn.hide()
        layout.addWidget(self.stop_btn, alignment=Qt.AlignBottom)

    def _auto_resize(self):
        doc = self.text_edit.document()
        line_count = max(1, doc.blockCount())
        line_height = self.text_edit.fontMetrics().lineSpacing()
        new_height = min(150, max(44, line_count * line_height + 20))
        self.text_edit.setFixedHeight(new_height)

    def _submit(self):
        text = self.text_edit.toPlainText().strip()
        if text:
            self.message_submitted.emit(text)
            self.text_edit.clear()

    def set_streaming(self, streaming):
        self.send_btn.setVisible(not streaming)
        self.stop_btn.setVisible(streaming)
        self.text_edit.setReadOnly(streaming)

    def focus_input(self):
        self.text_edit.setFocus()


# --- Sidebar ---

class SidebarWidget(QWidget):
    conversation_selected = pyqtSignal(str)
    new_chat_requested = pyqtSignal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setMinimumWidth(200)
        self.setMaximumWidth(350)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.new_btn = QPushButton("+ New Chat")
        self.new_btn.setObjectName("newChatBtn")
        self.new_btn.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self.new_btn)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search conversations...")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self._filter)
        self.search_field.setContentsMargins(8, 4, 8, 4)
        layout.addWidget(self.search_field)

        label = QLabel("RECENT")
        label.setObjectName("sidebarTitle")
        layout.addWidget(label)

        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._context_menu)
        self.list_widget.currentItemChanged.connect(self._on_select)
        layout.addWidget(self.list_widget)

        self._all_convos = []

    def refresh(self, select_id=None):
        self._all_convos = self.store.list_conversations()
        self._populate(self._all_convos, select_id)

    def _populate(self, convos, select_id=None):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for c in convos:
            item = QListWidgetItem(c["title"])
            item.setData(Qt.UserRole, c["id"])
            item.setToolTip(f"Model: {c['model']}\nUpdated: {c['updated_at'][:19]}")
            self.list_widget.addItem(item)
            if select_id and c["id"] == select_id:
                self.list_widget.setCurrentItem(item)
        self.list_widget.blockSignals(False)

    def _filter(self, text):
        if not text.strip():
            self._populate(self._all_convos)
            return
        results = self.store.search(text.strip())
        self._populate(results)

    def _on_select(self, current, _previous):
        if current:
            conv_id = current.data(Qt.UserRole)
            self.conversation_selected.emit(conv_id)

    def _context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        conv_id = item.data(Qt.UserRole)
        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        export_action = menu.addAction("Export as Markdown")
        action = menu.exec_(self.list_widget.mapToGlobal(pos))

        if action == rename_action:
            new_name, ok = QInputDialog.getText(
                self, "Rename", "New title:", text=item.text()
            )
            if ok and new_name.strip():
                conv = self.store.load(conv_id)
                if conv:
                    conv["title"] = new_name.strip()
                    self.store.save(conv)
                    self.refresh(select_id=conv_id)

        elif action == delete_action:
            reply = QMessageBox.question(
                self, "Delete", f"Delete \"{item.text()}\"?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.store.delete(conv_id)
                self.refresh()
                self.new_chat_requested.emit()

        elif action == export_action:
            conv = self.store.load(conv_id)
            if conv:
                path, _ = QFileDialog.getSaveFileName(
                    self, "Export Conversation",
                    f"{conv['title']}.md", "Markdown (*.md)"
                )
                if path:
                    with open(path, "w") as f:
                        f.write(f"# {conv['title']}\n\n")
                        f.write(f"Model: {conv['model']}\n")
                        f.write(f"Date: {conv['created_at'][:10]}\n\n---\n\n")
                        for msg in conv.get("messages", []):
                            role = "**You**" if msg["role"] == "user" else "**Assistant**"
                            f.write(f"{role}:\n\n{msg['content']}\n\n---\n\n")

    def select_conversation(self, conv_id):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.UserRole) == conv_id:
                self.list_widget.blockSignals(True)
                self.list_widget.setCurrentItem(item)
                self.list_widget.blockSignals(False)
                return


# --- Main Window ---

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 600)

        self.store = ConversationStore()
        self.renderer = ChatRenderer()
        self.settings_data = load_settings()
        self.current_conv = None
        self.worker = None
        self._active_model = None
        self._switcher = None

        self._build_ui()
        self._connect_signals()
        self._load_models()
        self._restore_geometry()
        self._new_chat()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # Sidebar
        sidebar_container = QWidget()
        sidebar_container.setStyleSheet("background-color: #252526;")
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar = SidebarWidget(self.store)
        sidebar_layout.addWidget(self.sidebar)
        self.splitter.addWidget(sidebar_container)

        # Main area
        main_area = QWidget()
        main_area_layout = QVBoxLayout(main_area)
        main_area_layout.setContentsMargins(0, 0, 0, 0)
        main_area_layout.setSpacing(0)

        # Top bar
        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e3e;")
        top_bar.setFixedHeight(48)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 0, 16, 0)

        self.title_label = QLabel("New Chat")
        self.title_label.setObjectName("titleLabel")
        top_layout.addWidget(self.title_label)

        top_layout.addStretch()

        self.system_prompt_btn = QPushButton("System Prompt")
        self.system_prompt_btn.setObjectName("systemPromptBtn")
        top_layout.addWidget(self.system_prompt_btn)

        self.model_combo = QComboBox()
        self.model_combo.addItem(DEFAULT_MODEL)
        top_layout.addWidget(self.model_combo)

        main_area_layout.addWidget(top_bar)

        # Chat display
        self.chat_view = QWebEngineView()
        self.chat_view.setStyleSheet("background-color: #1e1e1e;")
        page = self.chat_view.page()
        page.setBackgroundColor(QColor("#1e1e1e"))
        main_area_layout.addWidget(self.chat_view)

        # Input area
        self.input_widget = InputWidget()
        main_area_layout.addWidget(self.input_widget)

        self.splitter.addWidget(main_area)
        self.splitter.setSizes([260, 640])

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel(f"Model: {DEFAULT_MODEL}")
        self.status_bar.addPermanentWidget(self.status_label)

        # Load sidebar
        self.sidebar.refresh()

        # Render empty chat
        self._render_chat()

    def _connect_signals(self):
        self.sidebar.new_chat_requested.connect(self._new_chat)
        self.sidebar.conversation_selected.connect(self._load_conversation)
        self.input_widget.message_submitted.connect(self._send_message)
        self.input_widget.stop_btn.clicked.connect(self._stop_generation)
        self.system_prompt_btn.clicked.connect(self._edit_system_prompt)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)

        self.input_widget.text_edit.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.input_widget.text_edit and event.type() == event.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False
                self.input_widget._submit()
                return True
        return super().eventFilter(obj, event)

    def _load_models(self):
        self.model_loader = ModelLoader()
        self.model_loader.models_loaded.connect(self._on_models_loaded)
        self.model_loader.start()

    def _on_models_loaded(self, models):
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for m in models:
            self.model_combo.addItem(m)
        idx = self.model_combo.findText(
            self.settings_data.get("model", DEFAULT_MODEL)
        )
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        elif self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)
        self.model_combo.blockSignals(False)
        self._active_model = self.model_combo.currentText()

    def _on_model_changed(self, new_model):
        if not new_model:
            return
        old_model = self._active_model
        if old_model == new_model:
            return

        self.model_combo.setEnabled(False)
        self.status_label.setText(f"Switching: {old_model} -> {new_model}...")

        self._switcher = ModelSwitcher(old_model, new_model)
        self._switcher.status_update.connect(
            lambda msg: self.status_label.setText(msg)
        )
        self._switcher.switch_complete.connect(self._on_switch_complete)
        self._switcher.start()

    def _on_switch_complete(self, new_model):
        self._active_model = new_model
        self.model_combo.setEnabled(True)
        self.status_label.setText(f"Model: {new_model}")

        if self.current_conv:
            self.current_conv["model"] = new_model
        self.settings_data["model"] = new_model
        save_settings(self.settings_data)

    def _new_chat(self):
        model = self.model_combo.currentText() or DEFAULT_MODEL
        system_prompt = self.settings_data.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        self.current_conv = new_conversation(model, system_prompt)
        self.title_label.setText("New Chat")
        self._render_chat()
        self.input_widget.focus_input()

    def _load_conversation(self, conv_id):
        conv = self.store.load(conv_id)
        if conv:
            self.current_conv = conv
            self.title_label.setText(conv.get("title", "Untitled"))
            idx = self.model_combo.findText(conv.get("model", DEFAULT_MODEL))
            if idx >= 0:
                self.model_combo.blockSignals(True)
                self.model_combo.setCurrentIndex(idx)
                self.model_combo.blockSignals(False)
            self._render_chat()
            self.input_widget.focus_input()

    def _render_chat(self):
        messages = self.current_conv.get("messages", []) if self.current_conv else []
        html = self.renderer.build_html(messages, self.model_combo.currentText())
        self.chat_view.setHtml(html)

    def _send_message(self, text):
        if not self.current_conv:
            self._new_chat()

        self.current_conv["messages"].append({
            "role": "user",
            "content": text,
            "timestamp": datetime.now().isoformat(),
        })

        if len(self.current_conv["messages"]) == 1:
            title = text[:50].replace("\n", " ")
            if len(text) > 50:
                title += "..."
            self.current_conv["title"] = title
            self.title_label.setText(title)

        self._render_chat()
        self.input_widget.set_streaming(True)

        model = self.model_combo.currentText() or DEFAULT_MODEL
        self.current_conv["model"] = model
        self.worker = OllamaWorker(
            model,
            self.current_conv["messages"],
            self.current_conv.get("system_prompt", ""),
        )
        self.worker.token_received.connect(self._on_token)
        self.worker.response_finished.connect(self._on_response_done)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

        self.chat_view.page().runJavaScript(
            "document.getElementById('streaming-content').style.display='block';"
            "window.scrollTo(0, document.body.scrollHeight);"
        )

    def _on_token(self, token):
        escaped = token.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")
        self.chat_view.page().runJavaScript(f"appendToken('{escaped}');")

    def _on_response_done(self, full_text, stats):
        duration_ms = stats.get("total_duration", 0) / 1_000_000
        eval_count = stats.get("eval_count", 0)

        self.current_conv["messages"].append({
            "role": "assistant",
            "content": full_text,
            "timestamp": datetime.now().isoformat(),
            "model": self.model_combo.currentText(),
            "duration_ms": round(duration_ms),
            "tokens": eval_count,
        })

        self.store.save(self.current_conv)
        self.sidebar.refresh(select_id=self.current_conv["id"])

        self._render_chat()
        self.input_widget.set_streaming(False)
        self.input_widget.focus_input()

        duration_s = duration_ms / 1000
        self.status_label.setText(
            f"Model: {self.model_combo.currentText()} \u00b7 "
            f"{eval_count} tokens \u00b7 {duration_s:.1f}s"
        )

    def _on_error(self, error):
        self.input_widget.set_streaming(False)
        self.chat_view.page().runJavaScript("clearStreaming();")
        QMessageBox.warning(self, "Error", f"Ollama error:\n{error}")

    def _stop_generation(self):
        if self.worker:
            self.worker.stop()

    def _edit_system_prompt(self):
        current = ""
        if self.current_conv:
            current = self.current_conv.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        dialog = SystemPromptDialog(self, current)
        if dialog.exec_() == QDialog.Accepted:
            prompt = dialog.get_prompt()
            if self.current_conv:
                self.current_conv["system_prompt"] = prompt
            self.settings_data["system_prompt"] = prompt
            save_settings(self.settings_data)

    def _restore_geometry(self):
        settings = QSettings(APP_NAME, APP_NAME)
        geom = settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)
        state = settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event):
        settings = QSettings(APP_NAME, APP_NAME)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", self.saveState())
        if self.current_conv and self.current_conv.get("messages"):
            self.store.save(self.current_conv)
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(DARK_THEME_QSS)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
