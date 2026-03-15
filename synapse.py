#!/usr/bin/env python3
"""Synapse - A multi-model AI chat client for local Ollama models."""

import sys
import os
import json
import uuid
import re
import base64
import subprocess
import time
import html as html_module
import urllib.request
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QSettings, QSize, QTimer, QUrl, QMimeData,
    QBuffer, QIODevice, QByteArray
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QLineEdit, QPushButton,
    QComboBox, QLabel, QPlainTextEdit, QStatusBar, QMenu, QAction,
    QDialog, QDialogButtonBox, QInputDialog, QMessageBox, QSizePolicy,
    QFileDialog, QSlider, QShortcut, QFrame, QGridLayout, QCheckBox,
    QProgressBar, QTextEdit
)
from PyQt5.QtGui import QFont, QIcon, QKeySequence, QColor, QPixmap, QImage
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings

import markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter


# --- Constants ---

APP_NAME = "Synapse"
DATA_DIR = Path.home() / ".local" / "share" / "synapse"
CONV_DIR = DATA_DIR / "conversations"
SETTINGS_FILE = DATA_DIR / "settings.json"
DEFAULT_MODEL = "qwen2.5:14b"
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."
DEFAULT_OLLAMA_URL = "http://localhost:11434"
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')
TEXT_EXTENSIONS = (
    '.py', '.txt', '.md', '.js', '.ts', '.jsx', '.tsx', '.html', '.css',
    '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.sh', '.bash',
    '.c', '.cpp', '.h', '.hpp', '.java', '.rs', '.go', '.rb', '.php',
    '.sql', '.xml', '.csv', '.log', '.env', '.conf', '.r', '.swift',
    '.kt', '.scala', '.lua', '.pl', '.ex', '.exs', '.zig', '.nim',
    '.dockerfile', '.makefile',
)

DEFAULT_PRESETS = {
    "Default": "You are a helpful assistant.",
    "Coder": "You are an expert programmer. Write clean, efficient code. Explain your approach briefly when asked.",
    "Creative Writer": "You are a creative writing assistant. Help craft vivid stories, poetry, and creative content.",
    "Concise": "Be direct and concise. Short answers, no filler.",
    "Analyst": "You are a data analyst. Focus on accuracy, evidence-based reasoning, and clear methodology.",
}

DEFAULT_GEN_PARAMS = {
    "temperature": 0.7,
    "top_p": 0.9,
    "num_ctx": 8192,
}

DRAFT_FILE = DATA_DIR / "draft.json"

DEFAULT_PROMPT_TEMPLATES = {
    "Explain": "Explain the following in simple terms:\n\n",
    "Summarize": "Summarize the following text:\n\n",
    "Code Review": "Review the following code for bugs, performance, and best practices:\n\n```\n\n```",
    "Translate": "Translate the following to English:\n\n",
    "Debug": "Help me debug this error:\n\n",
    "Unit Tests": "Write unit tests for the following code:\n\n```\n\n```",
    "Refactor": "Refactor the following code for clarity and efficiency:\n\n```\n\n```",
    "ELI5": "Explain like I'm 5:\n\n",
}

_ollama_url = DEFAULT_OLLAMA_URL


def get_ollama_url():
    return _ollama_url


def set_ollama_url(url):
    global _ollama_url
    _ollama_url = url.rstrip("/") if url else DEFAULT_OLLAMA_URL


# --- Helpers ---

def relative_time(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        delta = datetime.now() - dt
        seconds = delta.total_seconds()
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            return f"{int(seconds / 60)}m ago"
        if seconds < 86400:
            return f"{int(seconds / 3600)}h ago"
        if delta.days == 1:
            return "Yesterday"
        if delta.days < 7:
            return f"{delta.days}d ago"
        return dt.strftime("%b %d")
    except (ValueError, TypeError):
        return ""


def format_time(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%I:%M %p").lstrip("0")
    except (ValueError, TypeError):
        return ""


def detect_mime(b64_data):
    try:
        header = base64.b64decode(b64_data[:32])
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return 'image/png'
        if header[:2] == b'\xff\xd8':
            return 'image/jpeg'
        if header[:6] in (b'GIF87a', b'GIF89a'):
            return 'image/gif'
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return 'image/webp'
    except Exception:
        pass
    return 'image/png'


def estimate_tokens(text):
    return max(1, int(len(text) / 3.5))


def format_size(size_bytes):
    if size_bytes >= 1_000_000_000:
        return f"{size_bytes / 1_000_000_000:.1f} GB"
    if size_bytes >= 1_000_000:
        return f"{size_bytes / 1_000_000:.0f} MB"
    return f"{size_bytes / 1_000:.0f} KB"


def get_gpu_vram_gb():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            total_mb = max(int(line.strip()) for line in lines if line.strip())
            return round(total_mb / 1024, 1)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return 0


def get_gpu_vram_usage():
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            line = result.stdout.strip().split('\n')[0]
            used, total = [int(x.strip()) for x in line.split(',')]
            return round(used / 1024, 1), round(total / 1024, 1)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return 0, 0


RECOMMENDED_MODELS = [
    {"name": "llama3.2:1b", "size_gb": 1.3, "desc": "Llama 3.2 1B - Fast, lightweight"},
    {"name": "llama3.2:3b", "size_gb": 2.0, "desc": "Llama 3.2 3B - Good balance"},
    {"name": "gemma2:2b", "size_gb": 1.6, "desc": "Gemma 2 2B - Google, compact"},
    {"name": "phi3.5:3.8b", "size_gb": 2.2, "desc": "Phi 3.5 3.8B - Microsoft, strong reasoning"},
    {"name": "qwen2.5:3b", "size_gb": 1.9, "desc": "Qwen 2.5 3B - Alibaba, multilingual"},
    {"name": "mistral:7b", "size_gb": 4.1, "desc": "Mistral 7B - Excellent general purpose"},
    {"name": "llama3.1:8b", "size_gb": 4.7, "desc": "Llama 3.1 8B - Meta, very capable"},
    {"name": "gemma2:9b", "size_gb": 5.4, "desc": "Gemma 2 9B - Google, strong"},
    {"name": "qwen2.5:7b", "size_gb": 4.7, "desc": "Qwen 2.5 7B - Great coding + general"},
    {"name": "deepseek-coder-v2:16b", "size_gb": 8.9, "desc": "DeepSeek Coder V2 16B - Top coding"},
    {"name": "qwen2.5:14b", "size_gb": 9.0, "desc": "Qwen 2.5 14B - Excellent all-rounder"},
    {"name": "gemma2:27b", "size_gb": 15.8, "desc": "Gemma 2 27B - Near frontier quality"},
    {"name": "llama3.1:70b", "size_gb": 40.0, "desc": "Llama 3.1 70B - Frontier class (needs quantization)"},
    {"name": "qwen2.5:32b", "size_gb": 19.8, "desc": "Qwen 2.5 32B - Premium quality"},
    {"name": "mixtral:8x7b", "size_gb": 26.0, "desc": "Mixtral 8x7B MoE - Fast, capable"},
    {"name": "command-r:35b", "size_gb": 20.0, "desc": "Command R 35B - Cohere, RAG optimized"},
    {"name": "llama3.2-vision:11b", "size_gb": 7.9, "desc": "Llama 3.2 Vision 11B - Multimodal"},
    {"name": "llava:13b", "size_gb": 8.0, "desc": "LLaVA 13B - Vision + language"},
    {"name": "codellama:13b", "size_gb": 7.4, "desc": "Code Llama 13B - Meta, code focused"},
    {"name": "starcoder2:7b", "size_gb": 4.0, "desc": "StarCoder2 7B - Code generation"},
    {"name": "llama3.3:70b", "size_gb": 43.0, "desc": "Llama 3.3 70B - Latest Meta frontier"},
    {"name": "qwen2.5-coder:7b", "size_gb": 4.7, "desc": "Qwen 2.5 Coder 7B - Dedicated coding"},
    {"name": "qwen2.5-coder:14b", "size_gb": 9.0, "desc": "Qwen 2.5 Coder 14B - Strong coding"},
    {"name": "deepseek-r1:7b", "size_gb": 4.7, "desc": "DeepSeek R1 7B - Reasoning model"},
    {"name": "deepseek-r1:14b", "size_gb": 9.0, "desc": "DeepSeek R1 14B - Advanced reasoning"},
    {"name": "deepseek-r1:32b", "size_gb": 19.8, "desc": "DeepSeek R1 32B - Premium reasoning"},
]


def play_notification_sound():
    try:
        sound = "/usr/share/sounds/freedesktop/stereo/message-new-instant.oga"
        if os.path.exists(sound):
            subprocess.Popen(['paplay', sound],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            QApplication.beep()
    except Exception:
        QApplication.beep()


# --- Styles ---

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
QPlainTextEdit, QTextEdit {
    background-color: #2d2d2d;
    border: 1px solid #3e3e3e;
    border-radius: 8px;
    padding: 10px;
    color: #cccccc;
    selection-background-color: #0078d4;
    font-size: 14px;
}
QPlainTextEdit:focus, QTextEdit:focus {
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
QPushButton#attachBtn {
    background-color: transparent;
    color: #808080;
    border: 1px solid #3e3e3e;
    border-radius: 18px;
    min-width: 36px;
    min-height: 36px;
    max-width: 36px;
    max-height: 36px;
    font-size: 18px;
    font-weight: normal;
    padding: 0;
}
QPushButton#attachBtn:hover {
    color: #cccccc;
    border-color: #0078d4;
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
QPushButton#gearBtn {
    background-color: transparent;
    color: #808080;
    border: 1px solid #3e3e3e;
    font-weight: normal;
    padding: 4px 10px;
    font-size: 14px;
}
QPushButton#gearBtn:hover {
    color: #cccccc;
    border-color: #0078d4;
}
QPushButton#previewCloseBtn {
    background-color: #d32f2f;
    border-radius: 8px;
    min-width: 16px;
    min-height: 16px;
    max-width: 16px;
    max-height: 16px;
    font-size: 9px;
    padding: 0;
}
QPushButton#dangerBtn {
    background-color: #d32f2f;
}
QPushButton#dangerBtn:hover {
    background-color: #e53935;
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
QSlider::groove:horizontal {
    border: 1px solid #3e3e3e;
    height: 6px;
    background: #2d2d2d;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #0078d4;
    border: none;
    width: 14px;
    margin: -4px 0;
    border-radius: 7px;
}
QSlider::sub-page:horizontal {
    background: #0078d4;
    border-radius: 3px;
}
QProgressBar {
    background-color: #2d2d2d;
    border: 1px solid #3e3e3e;
    border-radius: 4px;
    text-align: center;
    color: white;
    font-size: 11px;
    min-height: 16px;
    max-height: 16px;
}
QProgressBar::chunk {
    background-color: #0078d4;
    border-radius: 3px;
}
QCheckBox {
    spacing: 8px;
    color: #cccccc;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3e3e3e;
    border-radius: 3px;
    background: #2d2d2d;
}
QCheckBox::indicator:checked {
    background: #0078d4;
    border-color: #0078d4;
}
"""

# --- HTML Template ---

CHAT_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/mermaid@9.4.3/dist/mermaid.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
    background-color: #1e1e1e;
    color: #cccccc;
    font-family: 'Segoe UI', 'Ubuntu', 'Cantarell', sans-serif;
    font-size: FONT_SIZE_VALpx;
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
    position: relative;
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
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.user .message-header { color: #8ab4d6; }
.assistant .message-header { color: #808080; }
.message-time {
    font-weight: normal;
    font-size: 10px;
    text-transform: none;
    letter-spacing: normal;
    margin-left: 8px;
    opacity: 0.7;
}
.message-actions {
    display: none;
    gap: 8px;
    font-size: 11px;
    font-weight: normal;
    text-transform: none;
    letter-spacing: normal;
}
.message:hover .message-actions {
    display: flex;
}
.message-actions a, .message-actions button {
    color: #888;
    text-decoration: none;
    cursor: pointer;
    background: none;
    border: none;
    font-size: 11px;
    padding: 2px 6px;
    border-radius: 3px;
    font-family: inherit;
}
.message-actions a:hover, .message-actions button:hover {
    color: #fff;
    background: rgba(255,255,255,0.1);
}
.message-meta {
    font-size: 10px;
    color: #606060;
    margin-top: 8px;
    text-align: right;
}
.message-images {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 8px;
}
.message-images img {
    max-width: 300px;
    max-height: 200px;
    border-radius: 8px;
    border: 1px solid #3e3e3e;
}
.file-attachment {
    background: #252526;
    border: 1px solid #3e3e3e;
    border-radius: 6px;
    padding: 6px 12px;
    margin-bottom: 8px;
    font-size: 12px;
    color: #888;
    display: inline-block;
}
.file-attachment .filename {
    color: #4fc3f7;
    font-weight: bold;
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
.welcome .shortcuts-hint {
    color: #444;
    font-size: 12px;
    margin-top: 32px;
    line-height: 2.2;
}
.welcome .shortcuts-hint kbd {
    background: #2d2d2d;
    border: 1px solid #3e3e3e;
    border-radius: 4px;
    padding: 2px 8px;
    font-family: inherit;
    font-size: 11px;
    color: #999;
}
.welcome .slash-hint {
    color: #444;
    font-size: 12px;
    margin-top: 16px;
    line-height: 2;
}
.welcome .slash-hint code {
    font-size: 11px;
    color: #999;
}
#streaming-content {
    background-color: #2d2d2d;
    max-width: 85%;
    margin: 12px 0;
    padding: 14px 18px;
    border-radius: 12px;
    border-bottom-left-radius: 4px;
    word-wrap: break-word;
    overflow-wrap: break-word;
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
#scroll-to-bottom {
    position: fixed;
    bottom: 20px;
    right: 30px;
    width: 36px;
    height: 36px;
    background: #0078d4;
    color: white;
    border: none;
    border-radius: 50%;
    cursor: pointer;
    font-size: 18px;
    display: none;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
    z-index: 1000;
    line-height: 36px;
    text-align: center;
}
#scroll-to-bottom:hover {
    background: #1a8ae8;
}
.bookmarked {
    border-left: 3px solid #ffc107 !important;
}
.raw-content {
    white-space: pre-wrap;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 13px;
    color: #aaa;
}
.mermaid {
    background: #1a1a1a;
    border-radius: 8px;
    padding: 16px;
    margin: 10px 0;
    text-align: center;
}
.mermaid svg {
    max-width: 100%;
}
.run-btn {
    background: #2ea043;
    color: white;
    border: none;
    padding: 2px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
    margin-left: 8px;
}
.run-btn:hover {
    background: #3fb950;
}
.code-output {
    background: #0d1117;
    border: 1px solid #3e3e3e;
    border-top: none;
    border-radius: 0 0 8px 8px;
    padding: 10px 14px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: #8b949e;
    white-space: pre-wrap;
    max-height: 300px;
    overflow-y: auto;
}
.code-output .output-header {
    color: #58a6ff;
    font-weight: bold;
    margin-bottom: 4px;
}
PYGMENTS_CSS
</style>
</head>
<body>
MESSAGES_HTML
<div id="streaming-content">
    <div id="streaming-header">Assistant <span class="typing-indicator"></span></div>
    <div id="streaming-text"></div>
</div>
<div id="scroll-to-bottom" onclick="scrollToBottom()">&#8595;</div>
<script>
var _autoScroll = true;
window.addEventListener('scroll', function() {
    var atBottom = (window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 80);
    _autoScroll = atBottom;
    var btn = document.getElementById('scroll-to-bottom');
    if (btn) btn.style.display = atBottom ? 'none' : 'flex';
});
function scrollToBottom() {
    _autoScroll = true;
    window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
    var btn = document.getElementById('scroll-to-bottom');
    if (btn) btn.style.display = 'none';
}
function copyCode(btn) {
    const code = btn.closest('.code-header').nextElementSibling;
    const text = code.textContent;
    navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
    });
}
function updateStreaming(html) {
    var el = document.getElementById('streaming-text');
    var container = document.getElementById('streaming-content');
    container.style.display = 'block';
    el.innerHTML = html;
    if (_autoScroll) {
        window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
    }
}
function showStreaming() {
    document.getElementById('streaming-content').style.display = 'block';
    document.getElementById('streaming-text').innerHTML = '';
    if (_autoScroll) {
        window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
    }
}
function clearStreaming() {
    document.getElementById('streaming-text').innerHTML = '';
    document.getElementById('streaming-content').style.display = 'none';
}
function toggleRaw(idx) {
    var rendered = document.getElementById('rendered-' + idx);
    var raw = document.getElementById('raw-' + idx);
    var btn = document.getElementById('rawbtn-' + idx);
    if (!rendered || !raw || !btn) return;
    if (raw.style.display === 'none') {
        raw.style.display = 'block';
        rendered.style.display = 'none';
        btn.textContent = 'Rendered';
    } else {
        raw.style.display = 'none';
        rendered.style.display = 'block';
        btn.textContent = 'Raw';
    }
}
function initPage() {
    if (typeof mermaid !== 'undefined') {
        mermaid.initialize({startOnLoad: false, theme: 'dark', securityLevel: 'loose'});
        try {
            document.querySelectorAll('.mermaid').forEach(function(el) {
                if (!el.getAttribute('data-processed')) {
                    mermaid.init(undefined, el);
                }
            });
        } catch(e) { console.log('mermaid error:', e); }
    }
    if (typeof renderMathInElement !== 'undefined') {
        renderMathInElement(document.body, {
            delimiters: [
                {left: '$$', right: '$$', display: true},
                {left: '$', right: '$', display: false},
                {left: '\\\\(', right: '\\\\)', display: false},
                {left: '\\\\[', right: '\\\\]', display: true}
            ],
            throwOnError: false
        });
    }
}
window.addEventListener('load', initPage);
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
                        "pinned": data.get("pinned", False),
                        "tags": data.get("tags", []),
                    })
            except (json.JSONDecodeError, KeyError):
                continue
        convos.sort(key=lambda c: (not c.get("pinned", False), c["updated_at"]), reverse=False)
        pinned = [c for c in convos if c.get("pinned")]
        unpinned = [c for c in convos if not c.get("pinned")]
        pinned.sort(key=lambda c: c["updated_at"], reverse=True)
        unpinned.sort(key=lambda c: c["updated_at"], reverse=True)
        return pinned + unpinned

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
            tags = c.get("tags", [])
            if any(query.lstrip("#") in t.lower() for t in tags):
                results.append(c)
                continue
            full = self.load(c["id"])
            if full:
                for msg in full.get("messages", []):
                    if query in msg.get("content", "").lower():
                        results.append(c)
                        break
        return results

    def import_conversation(self, filepath):
        try:
            with open(filepath) as f:
                data = json.load(f)
            if "id" not in data:
                data["id"] = str(uuid.uuid4())
            if "messages" not in data:
                return None
            data.setdefault("title", "Imported Chat")
            data.setdefault("model", DEFAULT_MODEL)
            data.setdefault("system_prompt", DEFAULT_SYSTEM_PROMPT)
            data.setdefault("created_at", datetime.now().isoformat())
            data["updated_at"] = datetime.now().isoformat()
            self.save(data)
            return data["id"]
        except (json.JSONDecodeError, OSError, KeyError):
            return None


def new_conversation(model=DEFAULT_MODEL, system_prompt=DEFAULT_SYSTEM_PROMPT):
    return {
        "id": str(uuid.uuid4()),
        "title": "New Chat",
        "model": model,
        "system_prompt": system_prompt,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "messages": [],
        "pinned": False,
    }


# --- Settings ---

def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE) as f:
                s = json.load(f)
            s.setdefault("gen_params", dict(DEFAULT_GEN_PARAMS))
            s.setdefault("presets", dict(DEFAULT_PRESETS))
            s.setdefault("ollama_url", DEFAULT_OLLAMA_URL)
            s.setdefault("notify_sound", True)
            s.setdefault("zoom", 100)
            return s
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "model": DEFAULT_MODEL,
        "system_prompt": DEFAULT_SYSTEM_PROMPT,
        "gen_params": dict(DEFAULT_GEN_PARAMS),
        "presets": dict(DEFAULT_PRESETS),
        "ollama_url": DEFAULT_OLLAMA_URL,
        "notify_sound": True,
        "zoom": 100,
    }


def save_settings(settings):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


# --- Ollama Backend ---

def unload_model(model_name):
    try:
        payload = json.dumps({"model": model_name, "keep_alive": 0}).encode()
        req = urllib.request.Request(
            f"{get_ollama_url()}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception:
        pass


class ModelSwitcher(QThread):
    switch_complete = pyqtSignal(str)
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

    def __init__(self, model, messages, system_prompt="", gen_params=None):
        super().__init__()
        self.model = model
        self.messages = messages
        self.system_prompt = system_prompt
        self.gen_params = gen_params or {}
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        try:
            api_messages = []
            if self.system_prompt:
                api_messages.append({"role": "system", "content": self.system_prompt})
            for msg in self.messages:
                entry = {"role": msg["role"], "content": msg["content"]}
                if msg.get("images"):
                    entry["images"] = msg["images"]
                api_messages.append(entry)

            payload = {"model": self.model, "messages": api_messages, "stream": True}
            if self.gen_params:
                opts = {}
                for k in ("temperature", "top_p", "num_ctx"):
                    if k in self.gen_params:
                        opts[k] = self.gen_params[k]
                if opts:
                    payload["options"] = opts

            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{get_ollama_url()}/api/chat",
                data=data,
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
            req = urllib.request.Request(f"{get_ollama_url()}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                models.sort()
                self.models_loaded.emit(models)
        except Exception:
            self.models_loaded.emit([DEFAULT_MODEL])


class ModelInfoWorker(QThread):
    info_loaded = pyqtSignal(dict)

    def __init__(self, models):
        super().__init__()
        self.models = models

    def run(self):
        result = {}
        for model in self.models:
            try:
                payload = json.dumps({"name": model}).encode()
                req = urllib.request.Request(
                    f"{get_ollama_url()}/api/show",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    details = data.get("details", {})
                    result[model] = {
                        "family": details.get("family", ""),
                        "parameter_size": details.get("parameter_size", ""),
                        "quantization": details.get("quantization_level", ""),
                        "format": details.get("format", ""),
                    }
            except Exception:
                pass
        self.info_loaded.emit(result)


class TitleWorker(QThread):
    title_generated = pyqtSignal(str)

    def __init__(self, model, user_message):
        super().__init__()
        self.model = model
        self.user_message = user_message

    def run(self):
        try:
            messages = [
                {"role": "system", "content": "Generate a concise title (3-6 words) for this conversation. Reply with ONLY the title, no quotes, no punctuation at the end."},
                {"role": "user", "content": self.user_message}
            ]
            payload = json.dumps({
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.3, "num_ctx": 512},
            }).encode()
            req = urllib.request.Request(
                f"{get_ollama_url()}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                title = data["message"]["content"].strip().strip('"').strip("'").strip(".")
                if title and len(title) < 80:
                    self.title_generated.emit(title)
        except Exception:
            pass


class ConnectionChecker(QThread):
    status_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        while self._running:
            try:
                req = urllib.request.Request(f"{get_ollama_url()}/api/tags")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    resp.read()
                self.status_changed.emit(True)
            except Exception:
                self.status_changed.emit(False)
            self.sleep(30)

    def stop(self):
        self._running = False


class PullWorker(QThread):
    progress_update = pyqtSignal(str, int)
    pull_complete = pyqtSignal(bool, str)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            payload = json.dumps({"name": self.model_name}).encode()
            req = urllib.request.Request(
                f"{get_ollama_url()}/api/pull",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3600) as resp:
                for line in resp:
                    try:
                        chunk = json.loads(line.decode().strip())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    status = chunk.get("status", "")
                    total = chunk.get("total", 0)
                    completed = chunk.get("completed", 0)
                    pct = int(completed / total * 100) if total > 0 else 0
                    self.progress_update.emit(status, pct)
            self.pull_complete.emit(True, f"Pulled {self.model_name}")
        except Exception as e:
            self.pull_complete.emit(False, str(e))


class DeleteModelWorker(QThread):
    delete_complete = pyqtSignal(bool, str)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            payload = json.dumps({"name": self.model_name}).encode()
            req = urllib.request.Request(
                f"{get_ollama_url()}/api/delete",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="DELETE",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
            self.delete_complete.emit(True, f"Deleted {self.model_name}")
        except Exception as e:
            self.delete_complete.emit(False, str(e))


class GpuMonitor(QThread):
    usage_updated = pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        while self._running:
            used, total = get_gpu_vram_usage()
            if total > 0:
                self.usage_updated.emit(used, total)
            self.sleep(5)

    def stop(self):
        self._running = False


# --- Chat Renderer ---

class ChatRenderer:
    def __init__(self):
        self.formatter = HtmlFormatter(style="monokai", noclasses=True, nowrap=False)
        self.pygments_css = HtmlFormatter(style="monokai").get_style_defs('.highlight')
        self.md = markdown.Markdown(extensions=[
            'fenced_code', 'tables', 'nl2br', 'sane_lists'
        ])
        self.font_size = 15

    def render_markdown(self, text, code_block_offset=0):
        self.md.reset()
        html = self.md.convert(text)

        self._code_idx = code_block_offset

        def add_code_header(match):
            lang = ""
            lang_match = re.search(r'class="[^"]*language-(\w+)', match.group(0))
            if lang_match:
                lang = lang_match.group(1)
            code_content = match.group(0)

            if lang.lower() == 'mermaid':
                inner = re.search(r'<code[^>]*>(.*?)</code>', code_content, re.DOTALL)
                if inner:
                    mermaid_src = html_module.unescape(inner.group(1))
                    return f'<div class="mermaid">{mermaid_src}</div>'

            run_html = ""
            if lang.lower() in ('python', 'python3', 'py'):
                run_html = f'<button class="run-btn" onclick="window.location.href=\'action://runcode/{self._code_idx}\'">Run</button>'
                self._code_idx += 1
            else:
                self._code_idx += 1

            return (f'<pre><div class="code-header"><span>{lang}</span>'
                    f'<button onclick="copyCode(this)">Copy</button>{run_html}</div>'
                    f'{code_content[4:]}')

        html = re.sub(r'<pre><code[^>]*>.*?</code></pre>', add_code_header, html, flags=re.DOTALL)
        return html

    def build_html(self, messages, model_name="", available_models=None):
        msgs_html = ""
        if not messages:
            msgs_html = (
                '<div class="welcome">'
                f'<h1>{APP_NAME}</h1>'
                '<p class="tagline">Your local AI, multiple minds, one interface</p>'
                '<p class="models-hint">Select a model from the dropdown above to get started</p>'
                '<div class="shortcuts-hint">'
                '<kbd>Ctrl+N</kbd> New Chat &nbsp; '
                '<kbd>Ctrl+B</kbd> Toggle Sidebar &nbsp; '
                '<kbd>Ctrl+I</kbd> Import &nbsp; '
                '<kbd>Ctrl+Shift+C</kbd> Copy Last Response<br>'
                '<kbd>Ctrl+=</kbd> Zoom In &nbsp; '
                '<kbd>Ctrl+-</kbd> Zoom Out &nbsp; '
                '<kbd>Ctrl+0</kbd> Reset Zoom &nbsp; '
                '<kbd>Ctrl+L</kbd> Focus Input<br>'
                '<kbd>Ctrl+F</kbd> Search &nbsp; '
                '<kbd>Ctrl+T</kbd> Templates &nbsp; '
                '<kbd>Ctrl+Up/Down</kbd> Switch Model'
                '</div>'
                '<div class="slash-hint">'
                'Slash commands: '
                '<code>/clear</code> <code>/model name</code> <code>/system prompt</code> '
                '<code>/export</code> <code>/stats</code> <code>/pull name</code> '
                '<code>/templates</code> <code>/manage</code> <code>/help</code>'
                '</div>'
                '</div>'
            )
        else:
            for idx, msg in enumerate(messages):
                role = msg["role"]
                content = msg["content"]
                header = "You" if role == "user" else "Assistant"
                css_class = role

                timestamp = format_time(msg.get("timestamp", ""))
                time_html = f'<span class="message-time">{timestamp}</span>' if timestamp else ""

                images_html = ""
                if msg.get("images"):
                    images_html = '<div class="message-images">'
                    for img_b64 in msg["images"]:
                        mime = detect_mime(img_b64)
                        images_html += f'<img src="data:{mime};base64,{img_b64}" />'
                    images_html += '</div>'

                files_html = ""
                if msg.get("attached_files"):
                    for af in msg["attached_files"]:
                        files_html += f'<div class="file-attachment"><span class="filename">{af["name"]}</span></div>'

                is_bookmarked = msg.get("bookmarked", False)
                bookmark_class = " bookmarked" if is_bookmarked else ""
                bookmark_label = "Unbookmark" if is_bookmarked else "Bookmark"

                if role == "user":
                    rendered = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    rendered = rendered.replace("\n", "<br>")
                    actions = (
                        f'<span class="message-actions">'
                        f'<a href="action://edit/{idx}">Edit</a>'
                        f'<a href="action://bookmark/{idx}">{bookmark_label}</a>'
                        f'</span>'
                    )
                else:
                    rendered = self.render_markdown(content)
                    raw_escaped = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    rendered = (
                        f'<div id="rendered-{idx}">{rendered}</div>'
                        f'<div id="raw-{idx}" class="raw-content" style="display:none">{raw_escaped}</div>'
                    )
                    continue_html = ""
                    if idx == len(messages) - 1:
                        continue_html = f'<a href="action://continue/{idx}">Continue</a>'
                    actions = (
                        f'<span class="message-actions">'
                        f'<a href="action://copy/{idx}">Copy</a>'
                        f'<a href="action://regenerate/{idx}">Regenerate</a>'
                        f'<a href="action://retrywith/{idx}">Retry with...</a>'
                        f'<button id="rawbtn-{idx}" onclick="toggleRaw({idx})">Raw</button>'
                        f'<a href="action://bookmark/{idx}">{bookmark_label}</a>'
                        f'{continue_html}'
                        f'</span>'
                    )

                meta = ""
                if role == "assistant" and msg.get("model"):
                    parts = [msg["model"]]
                    if msg.get("duration_ms"):
                        parts.append(f"{msg['duration_ms'] / 1000:.1f}s")
                    if msg.get("tokens"):
                        parts.append(f"{msg['tokens']} tokens")
                        if msg.get("duration_ms") and msg["duration_ms"] > 0:
                            tps = msg["tokens"] / (msg["duration_ms"] / 1000)
                            parts.append(f"{tps:.1f} tok/s")
                    meta = f'<div class="message-meta">{" \u00b7 ".join(parts)}</div>'

                msgs_html += (
                    f'<div class="message {css_class}{bookmark_class}">'
                    f'<div class="message-header"><span>{header}{time_html}</span>{actions}</div>'
                    f'{images_html}{files_html}{rendered}{meta}</div>\n'
                )

        template = CHAT_HTML_TEMPLATE.replace("PYGMENTS_CSS", self.pygments_css)
        template = template.replace("FONT_SIZE_VAL", str(self.font_size))
        return template.replace("MESSAGES_HTML", msgs_html)


# --- Custom Web Page ---

class ChatPage(QWebEnginePage):
    action_requested = pyqtSignal(str, int)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        url_str = url.toString()
        if url_str.startswith("action://"):
            parts = url_str.replace("action://", "").split("/")
            action = parts[0] if parts else ""
            index = int(parts[1]) if len(parts) > 1 else -1
            self.action_requested.emit(action, index)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


# --- Dialogs ---

class SystemPromptDialog(QDialog):
    def __init__(self, parent, current_prompt, presets=None):
        super().__init__(parent)
        self.setWindowTitle("System Prompt")
        self.setMinimumSize(550, 400)
        self.presets = dict(presets or DEFAULT_PRESETS)

        layout = QVBoxLayout(self)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("(custom)")
        for name in sorted(self.presets.keys()):
            self.preset_combo.addItem(name)
        self.preset_combo.currentTextChanged.connect(self._on_preset_selected)
        preset_row.addWidget(self.preset_combo, 1)

        self.save_preset_btn = QPushButton("Save as Preset")
        self.save_preset_btn.clicked.connect(self._save_preset)
        preset_row.addWidget(self.save_preset_btn)

        self.del_preset_btn = QPushButton("Delete")
        self.del_preset_btn.clicked.connect(self._delete_preset)
        preset_row.addWidget(self.del_preset_btn)

        layout.addLayout(preset_row)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(current_prompt)
        self.editor.setPlaceholderText("You are a helpful assistant.")
        layout.addWidget(self.editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_preset_selected(self, name):
        if name in self.presets:
            self.editor.setPlainText(self.presets[name])

    def _save_preset(self):
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if ok and name.strip():
            self.presets[name.strip()] = self.editor.toPlainText().strip()
            if self.preset_combo.findText(name.strip()) < 0:
                self.preset_combo.addItem(name.strip())

    def _delete_preset(self):
        name = self.preset_combo.currentText()
        if name and name != "(custom)" and name in self.presets:
            del self.presets[name]
            idx = self.preset_combo.findText(name)
            if idx >= 0:
                self.preset_combo.removeItem(idx)

    def get_prompt(self):
        return self.editor.toPlainText().strip()

    def get_presets(self):
        return self.presets


class SettingsDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Generation Parameters"))
        grid = QGridLayout()

        grid.addWidget(QLabel("Temperature:"), 0, 0)
        params = settings.get("gen_params", DEFAULT_GEN_PARAMS)
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(0, 200)
        self.temp_slider.setValue(int(params.get("temperature", 0.7) * 100))
        self.temp_label = QLabel(f"{params.get('temperature', 0.7):.2f}")
        self.temp_slider.valueChanged.connect(
            lambda v: self.temp_label.setText(f"{v / 100:.2f}")
        )
        grid.addWidget(self.temp_slider, 0, 1)
        grid.addWidget(self.temp_label, 0, 2)

        grid.addWidget(QLabel("Top P:"), 1, 0)
        self.top_p_slider = QSlider(Qt.Horizontal)
        self.top_p_slider.setRange(0, 100)
        self.top_p_slider.setValue(int(params.get("top_p", 0.9) * 100))
        self.top_p_label = QLabel(f"{params.get('top_p', 0.9):.2f}")
        self.top_p_slider.valueChanged.connect(
            lambda v: self.top_p_label.setText(f"{v / 100:.2f}")
        )
        grid.addWidget(self.top_p_slider, 1, 1)
        grid.addWidget(self.top_p_label, 1, 2)

        grid.addWidget(QLabel("Context Length:"), 2, 0)
        self.ctx_combo = QComboBox()
        ctx_options = [2048, 4096, 8192, 16384, 32768, 65536, 131072]
        for c in ctx_options:
            self.ctx_combo.addItem(str(c))
        current_ctx = params.get("num_ctx", 8192)
        idx = self.ctx_combo.findText(str(current_ctx))
        if idx >= 0:
            self.ctx_combo.setCurrentIndex(idx)
        else:
            self.ctx_combo.addItem(str(current_ctx))
            self.ctx_combo.setCurrentIndex(self.ctx_combo.count() - 1)
        grid.addWidget(self.ctx_combo, 2, 1, 1, 2)

        layout.addLayout(grid)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setStyleSheet("color: #3e3e3e;")
        layout.addWidget(sep1)

        layout.addWidget(QLabel("Server"))
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("Ollama URL:"))
        self.url_edit = QLineEdit()
        self.url_edit.setText(settings.get("ollama_url", DEFAULT_OLLAMA_URL))
        self.url_edit.setPlaceholderText(DEFAULT_OLLAMA_URL)
        url_row.addWidget(self.url_edit, 1)
        layout.addLayout(url_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setStyleSheet("color: #3e3e3e;")
        layout.addWidget(sep2)

        layout.addWidget(QLabel("Notifications"))
        self.sound_check = QCheckBox("Play sound when response finishes (unfocused)")
        self.sound_check.setChecked(settings.get("notify_sound", True))
        layout.addWidget(self.sound_check)

        layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_settings(self):
        return {
            "gen_params": {
                "temperature": self.temp_slider.value() / 100,
                "top_p": self.top_p_slider.value() / 100,
                "num_ctx": int(self.ctx_combo.currentText()),
            },
            "ollama_url": self.url_edit.text().strip() or DEFAULT_OLLAMA_URL,
            "notify_sound": self.sound_check.isChecked(),
        }


class ModelManagementDialog(QDialog):
    models_changed = pyqtSignal()

    def __init__(self, parent, models, model_info=None):
        super().__init__(parent)
        self.setWindowTitle("Model Management")
        self.setMinimumSize(600, 600)
        self.models = list(models)
        self.model_info = model_info or {}
        self._pull_worker = None
        self._delete_worker = None
        self._vram_gb = get_gpu_vram_gb()

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Installed Models"))
        self.model_list = QListWidget()
        self._populate_models()
        layout.addWidget(self.model_list)

        del_row = QHBoxLayout()
        del_row.addStretch()
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.clicked.connect(self._delete_model)
        del_row.addWidget(self.delete_btn)
        layout.addLayout(del_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #3e3e3e;")
        layout.addWidget(sep)

        vram_text = f"  (GPU: {self._vram_gb} GB VRAM)" if self._vram_gb > 0 else "  (no GPU detected)"
        layout.addWidget(QLabel(f"Pull New Model{vram_text}"))

        pull_row = QHBoxLayout()
        self.pull_input = QLineEdit()
        self.pull_input.setPlaceholderText("e.g. llama3.2:3b, gemma2:9b, qwen2.5:14b")
        pull_row.addWidget(self.pull_input, 1)
        self.pull_btn = QPushButton("Pull")
        self.pull_btn.clicked.connect(self._pull_model)
        pull_row.addWidget(self.pull_btn)
        layout.addLayout(pull_row)

        if self._vram_gb > 0:
            layout.addWidget(QLabel(f"Recommended for your {self._vram_gb} GB GPU:"))
            self.rec_list = QListWidget()
            self.rec_list.setMaximumHeight(180)
            compatible = [m for m in RECOMMENDED_MODELS if m["size_gb"] <= self._vram_gb * 0.9]
            compatible.sort(key=lambda m: m["size_gb"], reverse=True)
            installed_names = {m.split(":")[0] for m in self.models}
            for m in compatible:
                base_name = m["name"].split(":")[0]
                installed_tag = " [installed]" if any(m["name"] in n for n in self.models) else ""
                label = f'{m["desc"]} ({m["size_gb"]} GB){installed_tag}'
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, m["name"])
                if installed_tag:
                    item.setForeground(QColor("#4caf50"))
                elif m["size_gb"] > self._vram_gb * 0.7:
                    item.setForeground(QColor("#ffaa44"))
                self.rec_list.addItem(item)
            self.rec_list.itemDoubleClicked.connect(self._pull_recommended)
            layout.addWidget(self.rec_list)
            hint = QLabel("Double-click to pull. Orange = tight fit, may need lower context.")
            hint.setStyleSheet("color: #666; font-size: 11px;")
            layout.addWidget(hint)

        self.pull_status = QLabel("")
        layout.addWidget(self.pull_status)

        self.pull_progress = QProgressBar()
        self.pull_progress.setRange(0, 100)
        self.pull_progress.hide()
        layout.addWidget(self.pull_progress)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _populate_models(self):
        self.model_list.clear()
        for m in self.models:
            info = self.model_info.get(m, {})
            parts = [m]
            if info.get("parameter_size"):
                parts.append(info["parameter_size"])
            if info.get("quantization"):
                parts.append(info["quantization"])
            if info.get("family"):
                parts.append(info["family"])
            self.model_list.addItem(" | ".join(parts))

    def _delete_model(self):
        item = self.model_list.currentItem()
        if not item:
            return
        model_name = item.text().split(" | ")[0]
        reply = QMessageBox.question(
            self, "Delete Model", f"Delete {model_name}? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.delete_btn.setEnabled(False)
        self.pull_status.setText(f"Deleting {model_name}...")
        self._delete_worker = DeleteModelWorker(model_name)
        self._delete_worker.delete_complete.connect(self._on_delete_complete)
        self._delete_worker.start()

    def _on_delete_complete(self, success, msg):
        self.delete_btn.setEnabled(True)
        self.pull_status.setText(msg)
        if success:
            self.models_changed.emit()
            model_name = msg.replace("Deleted ", "")
            if model_name in self.models:
                self.models.remove(model_name)
            self._populate_models()

    def _pull_recommended(self, item):
        name = item.data(Qt.UserRole)
        if name:
            self.pull_input.setText(name)
            self._pull_model()

    def _pull_model(self):
        name = self.pull_input.text().strip()
        if not name:
            return
        self.pull_btn.setEnabled(False)
        self.pull_progress.show()
        self.pull_progress.setValue(0)
        self.pull_status.setText(f"Pulling {name}...")
        self._pull_worker = PullWorker(name)
        self._pull_worker.progress_update.connect(self._on_pull_progress)
        self._pull_worker.pull_complete.connect(self._on_pull_complete)
        self._pull_worker.start()

    def _on_pull_progress(self, status, pct):
        self.pull_progress.setValue(pct)
        self.pull_status.setText(status)

    def _on_pull_complete(self, success, msg):
        self.pull_btn.setEnabled(True)
        self.pull_progress.hide()
        self.pull_status.setText(msg)
        if success:
            self.models_changed.emit()
            self.pull_input.clear()


class ConvStatsDialog(QDialog):
    def __init__(self, parent, conv):
        super().__init__(parent)
        self.setWindowTitle("Conversation Statistics")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        messages = conv.get("messages", [])
        user_msgs = [m for m in messages if m["role"] == "user"]
        asst_msgs = [m for m in messages if m["role"] == "assistant"]
        total_tokens = sum(m.get("tokens", 0) for m in asst_msgs)
        total_time_ms = sum(m.get("duration_ms", 0) for m in asst_msgs)
        avg_tps = (total_tokens / (total_time_ms / 1000)) if total_time_ms > 0 else 0

        total_chars = sum(len(m.get("content", "")) for m in messages)
        est_ctx_tokens = estimate_tokens(
            " ".join(m.get("content", "") for m in messages)
        )

        grid = QGridLayout()
        stats = [
            ("Title", conv.get("title", "Untitled")),
            ("Model", conv.get("model", "N/A")),
            ("Created", conv.get("created_at", "")[:19]),
            ("Last Updated", conv.get("updated_at", "")[:19]),
            ("", ""),
            ("Total Messages", str(len(messages))),
            ("User Messages", str(len(user_msgs))),
            ("Assistant Messages", str(len(asst_msgs))),
            ("", ""),
            ("Tokens Generated", f"{total_tokens:,}"),
            ("Total Gen Time", f"{total_time_ms / 1000:.1f}s"),
            ("Avg Throughput", f"{avg_tps:.1f} tok/s"),
            ("", ""),
            ("Total Characters", f"{total_chars:,}"),
            ("Est. Context Usage", f"~{est_ctx_tokens:,} tokens"),
        ]
        row = 0
        for label, value in stats:
            if not label:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setStyleSheet("color: #3e3e3e;")
                grid.addWidget(sep, row, 0, 1, 2)
            else:
                lbl = QLabel(label + ":")
                lbl.setStyleSheet("color: #808080;")
                grid.addWidget(lbl, row, 0)
                val = QLabel(value)
                val.setStyleSheet("color: #ffffff; font-weight: bold;")
                val.setTextInteractionFlags(Qt.TextSelectableByMouse)
                grid.addWidget(val, row, 1)
            row += 1

        layout.addLayout(grid)
        layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class ManageConversationsDialog(QDialog):
    conversations_deleted = pyqtSignal()

    def __init__(self, parent, store):
        super().__init__(parent)
        self.setWindowTitle("Manage Conversations")
        self.setMinimumSize(500, 500)
        self.store = store

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select conversations to delete:"))

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.MultiSelection)
        convos = store.list_conversations()
        for c in convos:
            item = QListWidgetItem(f"{c['title']}  ({c.get('updated_at', '')[:10]})")
            item.setData(Qt.UserRole, c["id"])
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.list_widget.selectAll)
        btn_row.addWidget(self.select_all_btn)

        self.deselect_btn = QPushButton("Deselect All")
        self.deselect_btn.clicked.connect(self.list_widget.clearSelection)
        btn_row.addWidget(self.deselect_btn)
        btn_row.addStretch()

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.setObjectName("dangerBtn")
        self.delete_btn.clicked.connect(self._delete_selected)
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _delete_selected(self):
        selected = self.list_widget.selectedItems()
        if not selected:
            return
        reply = QMessageBox.question(
            self, "Bulk Delete",
            f"Delete {len(selected)} conversation(s)? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        for item in selected:
            conv_id = item.data(Qt.UserRole)
            self.store.delete(conv_id)
        for item in selected:
            self.list_widget.takeItem(self.list_widget.row(item))
        self.conversations_deleted.emit()


class PromptTemplateDialog(QDialog):
    template_selected = pyqtSignal(str)

    def __init__(self, parent, templates=None):
        super().__init__(parent)
        self.setWindowTitle("Prompt Templates")
        self.setMinimumWidth(450)
        self.templates = templates or dict(DEFAULT_PROMPT_TEMPLATES)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Select a template to insert:"))

        self.list_widget = QListWidget()
        for name in sorted(self.templates.keys()):
            item = QListWidgetItem(name)
            item.setToolTip(self.templates[name][:100] + "..." if len(self.templates[name]) > 100 else self.templates[name])
            self.list_widget.addItem(item)
        self.list_widget.itemDoubleClicked.connect(self._select)
        layout.addWidget(self.list_widget)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(100)
        self.preview.setPlaceholderText("Select a template to preview...")
        self.list_widget.currentItemChanged.connect(
            lambda cur, _: self.preview.setPlainText(self.templates.get(cur.text(), "")) if cur else None
        )
        layout.addWidget(self.preview)

        btn_row = QHBoxLayout()
        insert_btn = QPushButton("Insert")
        insert_btn.clicked.connect(self._select_current)
        btn_row.addWidget(insert_btn)

        add_btn = QPushButton("Add Template")
        add_btn.clicked.connect(self._add_template)
        btn_row.addWidget(add_btn)

        del_btn = QPushButton("Delete")
        del_btn.setObjectName("dangerBtn")
        del_btn.clicked.connect(self._delete_template)
        btn_row.addWidget(del_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _select(self, item):
        if item and item.text() in self.templates:
            self.template_selected.emit(self.templates[item.text()])
            self.accept()

    def _select_current(self):
        item = self.list_widget.currentItem()
        if item:
            self._select(item)

    def _add_template(self):
        name, ok = QInputDialog.getText(self, "Add Template", "Template name:")
        if ok and name.strip():
            text, ok2 = QInputDialog.getMultiLineText(self, "Template Content", "Enter template text:")
            if ok2 and text.strip():
                self.templates[name.strip()] = text
                self.list_widget.addItem(name.strip())

    def _delete_template(self):
        item = self.list_widget.currentItem()
        if item and item.text() in self.templates:
            del self.templates[item.text()]
            self.list_widget.takeItem(self.list_widget.row(item))

    def get_templates(self):
        return self.templates


class SearchBar(QWidget):
    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.page = page
        self.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e3e;")
        self.setFixedHeight(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find in conversation...")
        self.search_input.returnPressed.connect(self._find_next)
        self.search_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.search_input, 1)

        prev_btn = QPushButton("<")
        prev_btn.setFixedWidth(28)
        prev_btn.clicked.connect(self._find_prev)
        layout.addWidget(prev_btn)

        next_btn = QPushButton(">")
        next_btn.setFixedWidth(28)
        next_btn.clicked.connect(self._find_next)
        layout.addWidget(next_btn)

        close_btn = QPushButton("x")
        close_btn.setFixedWidth(28)
        close_btn.clicked.connect(self._close)
        layout.addWidget(close_btn)

        self.hide()

    def show_bar(self):
        self.show()
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _close(self):
        self.page.findText("")
        self.hide()

    def _on_text_changed(self, text):
        if text:
            self.page.findText(text)
        else:
            self.page.findText("")

    def _find_next(self):
        text = self.search_input.text()
        if text:
            self.page.findText(text)

    def _find_prev(self):
        text = self.search_input.text()
        if text:
            self.page.findText(text, QWebEnginePage.FindBackward)


# --- Input Widget ---

class InputWidget(QWidget):
    message_submitted = pyqtSignal(str, list, list)  # text, images, file_attachments

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attached_images = []
        self._attached_files = []

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 4, 12, 12)
        outer_layout.setSpacing(4)

        self.preview_area = QWidget()
        self.preview_layout = QHBoxLayout(self.preview_area)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.setSpacing(6)
        self.preview_layout.addStretch()
        self.preview_area.hide()
        outer_layout.addWidget(self.preview_area)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.attach_btn = QPushButton("+")
        self.attach_btn.setObjectName("attachBtn")
        self.attach_btn.setToolTip("Attach image or file (drag & drop also works)")
        self.attach_btn.clicked.connect(self._pick_file)
        input_row.addWidget(self.attach_btn, alignment=Qt.AlignBottom)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("Type a message... (Enter to send, Shift+Enter for new line)")
        self.text_edit.setMaximumHeight(150)
        self.text_edit.setMinimumHeight(44)
        self.text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.text_edit.textChanged.connect(self._auto_resize)
        input_row.addWidget(self.text_edit)

        self.send_btn = QPushButton("\u2191")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setToolTip("Send (Enter)")
        self.send_btn.clicked.connect(self._submit)
        input_row.addWidget(self.send_btn, alignment=Qt.AlignBottom)

        self.stop_btn = QPushButton("\u25a0")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setToolTip("Stop generating")
        self.stop_btn.setFixedSize(36, 36)
        self.stop_btn.hide()
        input_row.addWidget(self.stop_btn, alignment=Qt.AlignBottom)

        outer_layout.addLayout(input_row)

        self.char_count_label = QLabel("0 chars | 0 words")
        self.char_count_label.setStyleSheet("color: #555; font-size: 10px; padding-left: 48px;")
        self.text_edit.textChanged.connect(self._update_char_count)
        outer_layout.addWidget(self.char_count_label)

        self.setAcceptDrops(True)

    def _auto_resize(self):
        doc = self.text_edit.document()
        line_count = max(1, doc.blockCount())
        line_height = self.text_edit.fontMetrics().lineSpacing()
        new_height = min(150, max(44, line_count * line_height + 20))
        self.text_edit.setFixedHeight(new_height)

    def _update_char_count(self):
        text = self.text_edit.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        self.char_count_label.setText(f"{chars} chars | {words} words")

    def _submit(self):
        text = self.text_edit.toPlainText().strip()
        images = [img[1] for img in self._attached_images]
        files = list(self._attached_files)
        if text or images or files:
            self.message_submitted.emit(text, images, files)
            self.text_edit.clear()
            self._clear_attachments()

    def set_streaming(self, streaming):
        self.send_btn.setVisible(not streaming)
        self.stop_btn.setVisible(streaming)
        self.text_edit.setReadOnly(streaming)
        self.attach_btn.setEnabled(not streaming)

    def focus_input(self):
        self.text_edit.setFocus()

    def _pick_file(self):
        all_ext = " ".join(f"*{e}" for e in IMAGE_EXTENSIONS + TEXT_EXTENSIONS)
        img_ext = " ".join(f"*{e}" for e in IMAGE_EXTENSIONS)
        txt_ext = " ".join(f"*{e}" for e in TEXT_EXTENSIONS)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach Files", "",
            f"All supported ({all_ext});;Images ({img_ext});;Text files ({txt_ext})"
        )
        for path in paths:
            self._add_file(path)

    def _add_file(self, filepath):
        try:
            lower = filepath.lower()
            if lower.endswith(IMAGE_EXTENSIONS):
                with open(filepath, 'rb') as f:
                    data = base64.b64encode(f.read()).decode()
                self._attached_images.append((filepath, data))
            elif lower.endswith(TEXT_EXTENSIONS) or not os.path.splitext(lower)[1]:
                with open(filepath, 'r', errors='replace') as f:
                    content = f.read(500_000)
                name = Path(filepath).name
                self._attached_files.append({"name": name, "content": content})
            self._update_preview()
        except (OSError, IOError):
            pass

    def paste_image_from_clipboard(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime.hasImage():
            image = clipboard.image()
            if image.isNull():
                return False
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            image.save(buf, "PNG")
            b64 = base64.b64encode(ba.data()).decode()
            self._attached_images.append(("clipboard.png", b64))
            self._update_preview()
            return True
        return False

    def _remove_attachment(self, att_type, index):
        if att_type == "image" and 0 <= index < len(self._attached_images):
            self._attached_images.pop(index)
        elif att_type == "file" and 0 <= index < len(self._attached_files):
            self._attached_files.pop(index)
        self._update_preview()

    def _update_preview(self):
        while self.preview_layout.count() > 1:
            item = self.preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pos = 0
        for i, (filepath, b64_data) in enumerate(self._attached_images):
            frame = QFrame()
            frame.setStyleSheet("background: #2d2d2d; border-radius: 6px; padding: 2px;")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(4, 4, 4, 4)
            frame_layout.setSpacing(2)

            thumb = QLabel()
            pixmap = QPixmap(filepath)
            if not pixmap.isNull():
                thumb.setPixmap(pixmap.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                thumb.setText(Path(filepath).name[:12])
                thumb.setStyleSheet("color: #aaa; font-size: 10px;")
            frame_layout.addWidget(thumb, alignment=Qt.AlignCenter)

            close_btn = QPushButton("\u00d7")
            close_btn.setObjectName("previewCloseBtn")
            idx = i
            close_btn.clicked.connect(lambda checked, x=idx: self._remove_attachment("image", x))
            frame_layout.addWidget(close_btn, alignment=Qt.AlignCenter)

            self.preview_layout.insertWidget(pos, frame)
            pos += 1

        for i, af in enumerate(self._attached_files):
            frame = QFrame()
            frame.setStyleSheet("background: #2d2d2d; border-radius: 6px; padding: 2px;")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(4, 4, 4, 4)
            frame_layout.setSpacing(2)

            name_label = QLabel(af["name"][:15])
            name_label.setStyleSheet("color: #4fc3f7; font-size: 10px;")
            frame_layout.addWidget(name_label, alignment=Qt.AlignCenter)

            size_label = QLabel(f"{len(af['content']):,} chars")
            size_label.setStyleSheet("color: #888; font-size: 9px;")
            frame_layout.addWidget(size_label, alignment=Qt.AlignCenter)

            close_btn = QPushButton("\u00d7")
            close_btn.setObjectName("previewCloseBtn")
            idx = i
            close_btn.clicked.connect(lambda checked, x=idx: self._remove_attachment("file", x))
            frame_layout.addWidget(close_btn, alignment=Qt.AlignCenter)

            self.preview_layout.insertWidget(pos, frame)
            pos += 1

        has_attachments = len(self._attached_images) > 0 or len(self._attached_files) > 0
        self.preview_area.setVisible(has_attachments)

    def _clear_attachments(self):
        self._attached_images.clear()
        self._attached_files.clear()
        self._update_preview()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile().lower()
                if path.endswith(IMAGE_EXTENSIONS) or path.endswith(TEXT_EXTENSIONS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            lower = filepath.lower()
            if lower.endswith(IMAGE_EXTENSIONS) or lower.endswith(TEXT_EXTENSIONS):
                self._add_file(filepath)


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

        self.pinned_label = QLabel("PINNED")
        self.pinned_label.setObjectName("sidebarTitle")
        self.pinned_label.hide()
        layout.addWidget(self.pinned_label)

        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._context_menu)
        self.list_widget.currentItemChanged.connect(self._on_select)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        self._all_convos = []

    def refresh(self, select_id=None):
        self._all_convos = self.store.list_conversations()
        self._populate(self._all_convos, select_id)

    def _populate(self, convos, select_id=None):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        pinned = [c for c in convos if c.get("pinned")]
        unpinned = [c for c in convos if not c.get("pinned")]
        self.pinned_label.setVisible(bool(pinned))

        if pinned:
            sep_item = QListWidgetItem("--- PINNED ---")
            sep_item.setFlags(Qt.NoItemFlags)
            sep_item.setForeground(QColor("#555"))
            font = sep_item.font()
            font.setPointSize(9)
            sep_item.setFont(font)
            self.list_widget.addItem(sep_item)

        for c in pinned:
            self._add_conv_item(c, select_id, is_pinned=True)

        if pinned and unpinned:
            sep_item = QListWidgetItem("--- RECENT ---")
            sep_item.setFlags(Qt.NoItemFlags)
            sep_item.setForeground(QColor("#555"))
            font = sep_item.font()
            font.setPointSize(9)
            sep_item.setFont(font)
            self.list_widget.addItem(sep_item)

        for c in unpinned:
            self._add_conv_item(c, select_id)

        self.list_widget.blockSignals(False)

    def _add_conv_item(self, c, select_id=None, is_pinned=False):
        rel = relative_time(c.get("updated_at", ""))
        prefix = "[*] " if is_pinned else ""
        display = f"{prefix}{c['title']}"
        tags = c.get("tags", [])
        if tags:
            display += f"  [{', '.join('#' + t for t in tags[:3])}]"
        if rel:
            display += f"  \u00b7  {rel}"
        item = QListWidgetItem(display)
        item.setData(Qt.UserRole, c["id"])
        item.setData(Qt.UserRole + 1, c["title"])
        item.setData(Qt.UserRole + 2, c.get("pinned", False))
        item.setToolTip(f"Model: {c['model']}\nUpdated: {c['updated_at'][:19]}")
        self.list_widget.addItem(item)
        if select_id and c["id"] == select_id:
            self.list_widget.setCurrentItem(item)

    def _filter(self, text):
        if not text.strip():
            self._populate(self._all_convos)
            return
        results = self.store.search(text.strip())
        self._populate(results)

    def _on_select(self, current, _previous):
        if current and current.data(Qt.UserRole):
            conv_id = current.data(Qt.UserRole)
            self.conversation_selected.emit(conv_id)

    def _on_double_click(self, item):
        if not item.data(Qt.UserRole):
            return
        conv_id = item.data(Qt.UserRole)
        old_title = item.data(Qt.UserRole + 1) or item.text()
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New title:", text=old_title
        )
        if ok and new_name.strip():
            conv = self.store.load(conv_id)
            if conv:
                conv["title"] = new_name.strip()
                self.store.save(conv)
                self.refresh(select_id=conv_id)

    def _context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item or not item.data(Qt.UserRole):
            return
        conv_id = item.data(Qt.UserRole)
        title = item.data(Qt.UserRole + 1) or item.text()
        is_pinned = item.data(Qt.UserRole + 2)

        menu = QMenu(self)
        pin_action = menu.addAction("Unpin" if is_pinned else "Pin")
        rename_action = menu.addAction("Rename")
        duplicate_action = menu.addAction("Duplicate")
        tags_action = menu.addAction("Edit Tags")
        delete_action = menu.addAction("Delete")
        menu.addSeparator()
        export_md_action = menu.addAction("Export as Markdown")
        export_html_action = menu.addAction("Export as HTML")
        action = menu.exec_(self.list_widget.mapToGlobal(pos))

        if action == pin_action:
            conv = self.store.load(conv_id)
            if conv:
                conv["pinned"] = not is_pinned
                self.store.save(conv)
                self.refresh(select_id=conv_id)

        elif action == rename_action:
            new_name, ok = QInputDialog.getText(
                self, "Rename", "New title:", text=title
            )
            if ok and new_name.strip():
                conv = self.store.load(conv_id)
                if conv:
                    conv["title"] = new_name.strip()
                    self.store.save(conv)
                    self.refresh(select_id=conv_id)

        elif action == duplicate_action:
            conv = self.store.load(conv_id)
            if conv:
                import copy
                new_conv = copy.deepcopy(conv)
                new_conv["id"] = str(uuid.uuid4())
                new_conv["title"] = conv.get("title", "Untitled") + " (copy)"
                new_conv["updated_at"] = datetime.now().isoformat()
                self.store.save(new_conv)
                self.refresh(select_id=new_conv["id"])
                self.conversation_selected.emit(new_conv["id"])

        elif action == tags_action:
            conv = self.store.load(conv_id)
            if conv:
                current_tags = ", ".join(conv.get("tags", []))
                new_tags, ok = QInputDialog.getText(
                    self, "Edit Tags", "Tags (comma-separated):", text=current_tags
                )
                if ok:
                    tags = [t.strip().lstrip("#") for t in new_tags.split(",") if t.strip()]
                    conv["tags"] = tags
                    self.store.save(conv)
                    self.refresh(select_id=conv_id)

        elif action == delete_action:
            reply = QMessageBox.question(
                self, "Delete", f'Delete "{title}"?',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.store.delete(conv_id)
                self.refresh()
                self.new_chat_requested.emit()

        elif action == export_md_action:
            self._export_markdown(conv_id)

        elif action == export_html_action:
            self._export_html(conv_id)

    def _export_markdown(self, conv_id):
        conv = self.store.load(conv_id)
        if not conv:
            return
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

    def _export_html(self, conv_id):
        conv = self.store.load(conv_id)
        if not conv:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as HTML",
            f"{conv['title']}.html", "HTML (*.html)"
        )
        if not path:
            return
        renderer = ChatRenderer()
        html = renderer.build_html(conv.get("messages", []), conv.get("model", ""))
        with open(path, "w") as f:
            f.write(html)

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
        set_ollama_url(self.settings_data.get("ollama_url", DEFAULT_OLLAMA_URL))
        self.current_conv = None
        self.worker = None
        self._active_model = None
        self._switcher = None
        self._title_worker = None
        self._streaming_text = ""
        self._streaming_dirty = False
        self._streaming_start_time = 0
        self._streaming_token_count = 0
        self._connected = False
        self._model_info = {}
        self._zoom = self.settings_data.get("zoom", 100)
        self.renderer.font_size = int(15 * self._zoom / 100)

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._load_models()
        self._restore_geometry()
        self._new_chat()
        self._start_connection_checker()
        self._start_gpu_monitor()

        self._stream_timer = QTimer()
        self._stream_timer.setInterval(200)
        self._stream_timer.timeout.connect(self._update_streaming_display)

        self._draft_timer = QTimer()
        self._draft_timer.setInterval(5000)
        self._draft_timer.timeout.connect(self._save_draft)
        self._draft_timer.start()

        self._restore_draft()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        self.sidebar_container = QWidget()
        self.sidebar_container.setStyleSheet("background-color: #252526;")
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar = SidebarWidget(self.store)
        sidebar_layout.addWidget(self.sidebar)
        self.splitter.addWidget(self.sidebar_container)

        main_area = QWidget()
        main_area_layout = QVBoxLayout(main_area)
        main_area_layout.setContentsMargins(0, 0, 0, 0)
        main_area_layout.setSpacing(0)

        top_bar = QWidget()
        top_bar.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e3e;")
        top_bar.setFixedHeight(48)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 0, 16, 0)

        self.title_label = QLabel(APP_NAME)
        self.title_label.setObjectName("titleLabel")
        top_layout.addWidget(self.title_label)

        top_layout.addStretch()

        self.system_prompt_btn = QPushButton("System Prompt")
        self.system_prompt_btn.setObjectName("systemPromptBtn")
        top_layout.addWidget(self.system_prompt_btn)

        self.gear_btn = QPushButton("\u2699")
        self.gear_btn.setObjectName("gearBtn")
        self.gear_btn.setToolTip("Settings")
        top_layout.addWidget(self.gear_btn)

        self.manage_btn = QPushButton("\u2261")
        self.manage_btn.setObjectName("gearBtn")
        self.manage_btn.setToolTip("Manage conversations (bulk delete)")
        top_layout.addWidget(self.manage_btn)

        self.models_btn = QPushButton("\u2193")
        self.models_btn.setObjectName("gearBtn")
        self.models_btn.setToolTip("Model management (pull / delete)")
        top_layout.addWidget(self.models_btn)

        self.model_combo = QComboBox()
        self.model_combo.addItem(DEFAULT_MODEL)
        top_layout.addWidget(self.model_combo)

        main_area_layout.addWidget(top_bar)

        self.ctx_bar = QProgressBar()
        self.ctx_bar.setRange(0, 100)
        self.ctx_bar.setValue(0)
        self.ctx_bar.setFormat("Context: %v%")
        self.ctx_bar.setFixedHeight(14)
        self.ctx_bar.setStyleSheet("""
            QProgressBar { background-color: #1e1e1e; border: none; border-radius: 0; font-size: 9px; color: #888; }
            QProgressBar::chunk { background-color: #0078d4; border-radius: 0; }
        """)
        main_area_layout.addWidget(self.ctx_bar)

        self.chat_page = ChatPage()
        self.chat_page.setBackgroundColor(QColor("#1e1e1e"))
        self.chat_page.settings().setAttribute(
            QWebEngineSettings.LocalContentCanAccessRemoteUrls, True
        )
        self.chat_view = QWebEngineView()
        self.chat_view.setPage(self.chat_page)
        self.chat_view.setStyleSheet("background-color: #1e1e1e;")

        self.search_bar = SearchBar(self.chat_page)
        main_area_layout.addWidget(self.search_bar)

        main_area_layout.addWidget(self.chat_view)

        self.input_widget = InputWidget()
        main_area_layout.addWidget(self.input_widget)

        self.splitter.addWidget(main_area)
        self.splitter.setSizes([260, 640])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.connection_dot = QLabel("\u25cf")
        self.connection_dot.setStyleSheet("color: #808080; font-size: 14px; padding: 0 4px;")
        self.connection_dot.setToolTip("Checking Ollama connection...")
        self.status_bar.addWidget(self.connection_dot)

        self.status_label = QLabel(f"Model: {DEFAULT_MODEL}")
        self.status_bar.addPermanentWidget(self.status_label)

        self.gpu_label = QLabel("")
        self.gpu_label.setStyleSheet("padding: 0 8px;")
        self.gpu_label.setToolTip("GPU VRAM usage")
        self.status_bar.addPermanentWidget(self.gpu_label)

        self.zoom_label = QLabel(f"{self._zoom}%")
        self.zoom_label.setStyleSheet("padding: 0 8px;")
        self.status_bar.addPermanentWidget(self.zoom_label)

        self.sidebar.refresh()
        self._render_chat()

    def _connect_signals(self):
        self.sidebar.new_chat_requested.connect(self._new_chat)
        self.sidebar.conversation_selected.connect(self._load_conversation)
        self.input_widget.message_submitted.connect(self._send_message)
        self.input_widget.stop_btn.clicked.connect(self._stop_generation)
        self.system_prompt_btn.clicked.connect(self._edit_system_prompt)
        self.gear_btn.clicked.connect(self._open_settings)
        self.manage_btn.clicked.connect(self._manage_conversations)
        self.models_btn.clicked.connect(self._open_model_management)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        self.chat_page.action_requested.connect(self._on_chat_action)
        self.input_widget.text_edit.installEventFilter(self)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self, self._new_chat)
        QShortcut(QKeySequence("Ctrl+B"), self, self._toggle_sidebar)
        QShortcut(QKeySequence("Ctrl+I"), self, self._import_conversation)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self._copy_last_response)
        QShortcut(QKeySequence("Ctrl+L"), self, lambda: self.input_widget.focus_input())
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_reset)
        QShortcut(QKeySequence("Ctrl+F"), self, self._toggle_search)
        QShortcut(QKeySequence("Ctrl+Up"), self, self._model_prev)
        QShortcut(QKeySequence("Ctrl+Down"), self, self._model_next)
        QShortcut(QKeySequence("Ctrl+T"), self, self._show_templates)
        QShortcut(QKeySequence("Escape"), self, self._escape_handler)

    def _start_connection_checker(self):
        self._conn_checker = ConnectionChecker()
        self._conn_checker.status_changed.connect(self._on_connection_status)
        self._conn_checker.start()

    def _restart_connection_checker(self):
        if hasattr(self, '_conn_checker'):
            self._conn_checker.stop()
            self._conn_checker.wait(2000)
        self._start_connection_checker()

    def _on_connection_status(self, connected):
        self._connected = connected
        if connected:
            self.connection_dot.setStyleSheet("color: #4caf50; font-size: 14px; padding: 0 4px;")
            self.connection_dot.setToolTip("Ollama connected")
        else:
            self.connection_dot.setStyleSheet("color: #f44336; font-size: 14px; padding: 0 4px;")
            self.connection_dot.setToolTip("Ollama disconnected")

    def eventFilter(self, obj, event):
        if obj == self.input_widget.text_edit and event.type() == event.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() & Qt.ShiftModifier:
                    return False
                self.input_widget._submit()
                return True
            if event.key() == Qt.Key_V and event.modifiers() & Qt.ControlModifier:
                if self.input_widget.paste_image_from_clipboard():
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
        self._fetch_model_info(models)

    def _fetch_model_info(self, models):
        self._info_worker = ModelInfoWorker(models)
        self._info_worker.info_loaded.connect(self._on_model_info)
        self._info_worker.start()

    def _on_model_info(self, info):
        self._model_info = info
        for i in range(self.model_combo.count()):
            model = self.model_combo.itemText(i)
            if model in info:
                mi = info[model]
                parts = []
                if mi.get("parameter_size"):
                    parts.append(mi["parameter_size"])
                if mi.get("quantization"):
                    parts.append(mi["quantization"])
                if mi.get("family"):
                    parts.append(mi["family"])
                if parts:
                    self.model_combo.setItemData(i, " | ".join(parts), Qt.ToolTipRole)

    def _on_model_changed(self, new_model):
        if not new_model:
            return
        old_model = self._active_model
        if old_model == new_model:
            return
        self.model_combo.setEnabled(False)
        self.status_label.setText(f"Switching: {old_model} -> {new_model}...")
        self._switcher = ModelSwitcher(old_model, new_model)
        self._switcher.status_update.connect(lambda msg: self.status_label.setText(msg))
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
        self.title_label.setText(APP_NAME)
        self._render_chat()
        self._update_context_bar()
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
            self._update_context_bar()
            self.input_widget.focus_input()

    def _render_chat(self):
        messages = self.current_conv.get("messages", []) if self.current_conv else []
        html = self.renderer.build_html(messages, self.model_combo.currentText())
        self.chat_view.setHtml(html)

    def _update_context_bar(self):
        if not self.current_conv:
            self.ctx_bar.setValue(0)
            self.ctx_bar.setFormat("Context: 0%")
            return
        messages = self.current_conv.get("messages", [])
        all_text = " ".join(m.get("content", "") for m in messages)
        sys_prompt = self.current_conv.get("system_prompt", "")
        est = estimate_tokens(all_text + " " + sys_prompt)
        num_ctx = self.settings_data.get("gen_params", {}).get("num_ctx", 8192)
        pct = min(100, int(est / num_ctx * 100))
        self.ctx_bar.setValue(pct)
        self.ctx_bar.setFormat(f"Context: ~{est:,} / {num_ctx:,} tokens ({pct}%)")
        if pct > 85:
            self.ctx_bar.setStyleSheet("""
                QProgressBar { background-color: #1e1e1e; border: none; font-size: 9px; color: #ff8888; }
                QProgressBar::chunk { background-color: #d32f2f; }
            """)
        elif pct > 60:
            self.ctx_bar.setStyleSheet("""
                QProgressBar { background-color: #1e1e1e; border: none; font-size: 9px; color: #ffaa44; }
                QProgressBar::chunk { background-color: #f9a825; }
            """)
        else:
            self.ctx_bar.setStyleSheet("""
                QProgressBar { background-color: #1e1e1e; border: none; font-size: 9px; color: #888; }
                QProgressBar::chunk { background-color: #0078d4; }
            """)

    def _send_message(self, text, images=None, files=None):
        if text.startswith("/"):
            self._handle_slash_command(text)
            return

        if not self.current_conv:
            self._new_chat()

        content = text
        attached_file_info = []
        if files:
            for af in files:
                ext = os.path.splitext(af["name"])[1].lstrip(".")
                content = f'[File: {af["name"]}]\n```{ext}\n{af["content"]}\n```\n\n' + content
                attached_file_info.append({"name": af["name"]})

        msg = {
            "role": "user",
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        if images:
            msg["images"] = images
        if attached_file_info:
            msg["attached_files"] = attached_file_info
        self.current_conv["messages"].append(msg)

        if len(self.current_conv["messages"]) == 1:
            title = text[:50].replace("\n", " ")
            if len(text) > 50:
                title += "..."
            self.current_conv["title"] = title
            self.title_label.setText(title)

        self._render_chat()
        self._update_context_bar()
        self.input_widget.set_streaming(True)

        self._streaming_text = ""
        self._streaming_dirty = False
        self._streaming_start_time = time.time()
        self._streaming_token_count = 0

        model = self.model_combo.currentText() or DEFAULT_MODEL
        self.current_conv["model"] = model
        gen_params = self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS)
        self.worker = OllamaWorker(
            model,
            self.current_conv["messages"],
            self.current_conv.get("system_prompt", ""),
            gen_params,
        )
        self.worker.token_received.connect(self._on_token)
        self.worker.response_finished.connect(self._on_response_done)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()
        self._stream_timer.start()
        self.chat_view.page().runJavaScript("showStreaming();")

    def _handle_slash_command(self, text):
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/clear":
            if self.current_conv:
                self.current_conv["messages"] = []
                self.store.save(self.current_conv)
                self._render_chat()
                self._update_context_bar()
                self.status_label.setText("Conversation cleared")

        elif cmd == "/model":
            if arg:
                idx = self.model_combo.findText(arg)
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)
                else:
                    self.status_label.setText(f"Model not found: {arg}")
            else:
                self.status_label.setText(f"Current model: {self.model_combo.currentText()}")

        elif cmd == "/system":
            if arg:
                if self.current_conv:
                    self.current_conv["system_prompt"] = arg
                self.settings_data["system_prompt"] = arg
                save_settings(self.settings_data)
                self.status_label.setText("System prompt updated")
            else:
                self._edit_system_prompt()

        elif cmd == "/export":
            self._export_current_html()

        elif cmd == "/stats":
            self._show_conv_stats()

        elif cmd == "/pull":
            if arg:
                self._pull_model_quick(arg)
            else:
                self.status_label.setText("Usage: /pull model_name")

        elif cmd == "/templates":
            self._show_templates()

        elif cmd == "/manage":
            self._manage_conversations()

        elif cmd == "/help":
            self.status_label.setText("/clear /model /system /export /stats /pull /templates /manage /help")

        else:
            self.status_label.setText(f"Unknown command: {cmd}. Try /help")

    def _on_token(self, token):
        self._streaming_text += token
        self._streaming_token_count += 1
        self._streaming_dirty = True

    def _update_streaming_display(self):
        if not self._streaming_dirty:
            return
        self._streaming_dirty = False
        try:
            html = self.renderer.render_markdown(self._streaming_text)
            html_escaped = (html.replace("\\", "\\\\")
                               .replace("`", "\\`")
                               .replace("${", "\\${"))
            self.chat_view.page().runJavaScript(
                f"document.getElementById('streaming-text').innerHTML = `{html_escaped}`;"
                "if (_autoScroll) {{ window.scrollTo({{top: document.body.scrollHeight, behavior: 'smooth'}}); }}"
            )
        except Exception:
            pass

        elapsed = time.time() - self._streaming_start_time
        if elapsed > 0.5 and self._streaming_token_count > 0:
            tps = self._streaming_token_count / elapsed
            self.status_label.setText(
                f"Generating... {self._streaming_token_count} tokens | {tps:.1f} tok/s"
            )

    def _on_response_done(self, full_text, stats):
        self._stream_timer.stop()

        duration_ns = stats.get("total_duration", 0)
        eval_count = stats.get("eval_count", 0)
        eval_duration_ns = stats.get("eval_duration", 0)
        duration_ms = duration_ns / 1_000_000

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
        self._update_context_bar()
        self.input_widget.set_streaming(False)
        self.input_widget.focus_input()

        model_name = self.model_combo.currentText()
        parts = [f"Model: {model_name}"]
        if eval_count:
            parts.append(f"{eval_count} tokens")
        if duration_ms > 0:
            parts.append(f"{duration_ms / 1000:.1f}s")
        if eval_count and eval_duration_ns > 0:
            tps = eval_count / (eval_duration_ns / 1_000_000_000)
            parts.append(f"{tps:.1f} tok/s")
        self.status_label.setText(" \u00b7 ".join(parts))

        if len(self.current_conv["messages"]) == 2:
            self._generate_auto_title()

        if self.settings_data.get("notify_sound", True) and not self.isActiveWindow():
            play_notification_sound()

    def _generate_auto_title(self):
        if not self.current_conv or not self.current_conv["messages"]:
            return
        user_msg = self.current_conv["messages"][0].get("content", "")
        if not user_msg:
            return
        model = self.model_combo.currentText() or DEFAULT_MODEL
        self._title_worker = TitleWorker(model, user_msg)
        self._title_worker.title_generated.connect(self._on_title_generated)
        self._title_worker.start()

    def _on_title_generated(self, title):
        if self.current_conv:
            self.current_conv["title"] = title
            self.title_label.setText(title)
            self.store.save(self.current_conv)
            self.sidebar.refresh(select_id=self.current_conv["id"])

    def _on_error(self, error):
        self._stream_timer.stop()
        self.input_widget.set_streaming(False)
        self.chat_view.page().runJavaScript("clearStreaming();")
        QMessageBox.warning(self, "Error", f"Ollama error:\n{error}")

    def _stop_generation(self):
        if self.worker:
            self.worker.stop()

    def _on_chat_action(self, action, index):
        if not self.current_conv:
            return
        messages = self.current_conv.get("messages", [])
        if index < 0 or index >= len(messages):
            return

        if action == "copy":
            content = messages[index].get("content", "")
            QApplication.clipboard().setText(content)
            self.status_label.setText("Copied to clipboard")
            QTimer.singleShot(2000, lambda: self.status_label.setText(
                f"Model: {self.model_combo.currentText()}"
            ))

        elif action == "edit":
            old_text = messages[index].get("content", "")
            new_text, ok = QInputDialog.getMultiLineText(
                self, "Edit Message", "Edit your message:", old_text
            )
            if ok and new_text.strip() and new_text.strip() != old_text.strip():
                self.current_conv["messages"] = messages[:index]
                self.store.save(self.current_conv)
                self._render_chat()
                images = messages[index].get("images", [])
                self._send_message(new_text.strip(), images if images else None)

        elif action == "regenerate":
            if messages[index]["role"] == "assistant":
                self.current_conv["messages"] = messages[:index]
                self.store.save(self.current_conv)
                self._render_chat()
                if self.current_conv["messages"]:
                    last_user = self.current_conv["messages"][-1]
                    if last_user["role"] == "user":
                        self.current_conv["messages"].pop()
                        images = last_user.get("images")
                        self._send_message(last_user["content"], images if images else None)

        elif action == "retrywith":
            if messages[index]["role"] == "assistant":
                models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
                model, ok = QInputDialog.getItem(
                    self, "Regenerate with Model", "Select model:", models,
                    current=models.index(self.model_combo.currentText()) if self.model_combo.currentText() in models else 0,
                    editable=False
                )
                if ok and model:
                    self.current_conv["messages"] = messages[:index]
                    self.store.save(self.current_conv)
                    self._render_chat()
                    self.model_combo.blockSignals(True)
                    idx = self.model_combo.findText(model)
                    if idx >= 0:
                        self.model_combo.setCurrentIndex(idx)
                    self.model_combo.blockSignals(False)
                    if self.current_conv["messages"]:
                        last_user = self.current_conv["messages"][-1]
                        if last_user["role"] == "user":
                            self.current_conv["messages"].pop()
                            images = last_user.get("images")
                            self._send_message(last_user["content"], images if images else None)

        elif action == "bookmark":
            messages[index]["bookmarked"] = not messages[index].get("bookmarked", False)
            self.store.save(self.current_conv)
            self._render_chat()
            state = "bookmarked" if messages[index]["bookmarked"] else "removed bookmark"
            self.status_label.setText(f"Message {state}")

        elif action == "continue":
            if messages[index]["role"] == "assistant":
                self._send_message("Continue from where you left off.")

        elif action == "runcode":
            self._execute_code_block(index)

    def _edit_system_prompt(self):
        current = ""
        if self.current_conv:
            current = self.current_conv.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        presets = self.settings_data.get("presets", DEFAULT_PRESETS)
        dialog = SystemPromptDialog(self, current, presets)
        if dialog.exec_() == QDialog.Accepted:
            prompt = dialog.get_prompt()
            if self.current_conv:
                self.current_conv["system_prompt"] = prompt
            self.settings_data["system_prompt"] = prompt
            self.settings_data["presets"] = dialog.get_presets()
            save_settings(self.settings_data)

    def _open_settings(self):
        dialog = SettingsDialog(self, self.settings_data)
        if dialog.exec_() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            old_url = self.settings_data.get("ollama_url", DEFAULT_OLLAMA_URL)
            self.settings_data["gen_params"] = new_settings["gen_params"]
            self.settings_data["ollama_url"] = new_settings["ollama_url"]
            self.settings_data["notify_sound"] = new_settings["notify_sound"]
            save_settings(self.settings_data)
            set_ollama_url(new_settings["ollama_url"])
            self._update_context_bar()
            if new_settings["ollama_url"] != old_url:
                self._restart_connection_checker()
                self._load_models()

    def _open_model_management(self):
        models = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        dialog = ModelManagementDialog(self, models, self._model_info)
        dialog.models_changed.connect(self._load_models)
        dialog.exec_()

    def _toggle_sidebar(self):
        visible = self.sidebar_container.isVisible()
        self.sidebar_container.setVisible(not visible)

    def _import_conversation(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Conversation", "", "JSON (*.json)"
        )
        if path:
            conv_id = self.store.import_conversation(path)
            if conv_id:
                self.sidebar.refresh(select_id=conv_id)
                self._load_conversation(conv_id)
            else:
                QMessageBox.warning(self, "Import Failed", "Could not import conversation file.")

    def _copy_last_response(self):
        if not self.current_conv:
            return
        messages = self.current_conv.get("messages", [])
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                QApplication.clipboard().setText(msg["content"])
                self.status_label.setText("Copied last response to clipboard")
                QTimer.singleShot(2000, lambda: self.status_label.setText(
                    f"Model: {self.model_combo.currentText()}"
                ))
                return

    def _export_current_html(self):
        if not self.current_conv:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as HTML",
            f"{self.current_conv.get('title', 'chat')}.html", "HTML (*.html)"
        )
        if path:
            html = self.renderer.build_html(
                self.current_conv.get("messages", []),
                self.current_conv.get("model", "")
            )
            with open(path, "w") as f:
                f.write(html)
            self.status_label.setText(f"Exported to {Path(path).name}")

    def _show_conv_stats(self):
        if not self.current_conv:
            return
        dialog = ConvStatsDialog(self, self.current_conv)
        dialog.exec_()

    def _pull_model_quick(self, model_name):
        self.status_label.setText(f"Pulling {model_name}...")
        self._quick_pull_worker = PullWorker(model_name)
        self._quick_pull_worker.progress_update.connect(
            lambda status, pct: self.status_label.setText(f"Pulling: {status} ({pct}%)")
        )
        self._quick_pull_worker.pull_complete.connect(self._on_quick_pull_done)
        self._quick_pull_worker.start()

    def _on_quick_pull_done(self, success, msg):
        self.status_label.setText(msg)
        if success:
            self._load_models()

    def _zoom_in(self):
        self._zoom = min(200, self._zoom + 10)
        self._apply_zoom()

    def _zoom_out(self):
        self._zoom = max(50, self._zoom - 10)
        self._apply_zoom()

    def _zoom_reset(self):
        self._zoom = 100
        self._apply_zoom()

    def _apply_zoom(self):
        self.renderer.font_size = int(15 * self._zoom / 100)
        self.zoom_label.setText(f"{self._zoom}%")
        self.settings_data["zoom"] = self._zoom
        save_settings(self.settings_data)
        self._render_chat()

    def _start_gpu_monitor(self):
        self._gpu_monitor = GpuMonitor()
        self._gpu_monitor.usage_updated.connect(self._on_gpu_update)
        self._gpu_monitor.start()

    def _on_gpu_update(self, used, total):
        pct = int(used / total * 100) if total > 0 else 0
        self.gpu_label.setText(f"GPU: {used:.1f}/{total:.0f} GB ({pct}%)")
        if pct > 85:
            self.gpu_label.setStyleSheet("padding: 0 8px; color: #ff8888;")
        elif pct > 60:
            self.gpu_label.setStyleSheet("padding: 0 8px; color: #ffaa44;")
        else:
            self.gpu_label.setStyleSheet("padding: 0 8px;")

    def _toggle_search(self):
        if self.search_bar.isVisible():
            self.search_bar._close()
        else:
            self.search_bar.show_bar()

    def _escape_handler(self):
        if self.search_bar.isVisible():
            self.search_bar._close()

    def _model_prev(self):
        idx = self.model_combo.currentIndex()
        if idx > 0:
            self.model_combo.setCurrentIndex(idx - 1)

    def _model_next(self):
        idx = self.model_combo.currentIndex()
        if idx < self.model_combo.count() - 1:
            self.model_combo.setCurrentIndex(idx + 1)

    def _show_templates(self):
        templates = self.settings_data.get("prompt_templates", dict(DEFAULT_PROMPT_TEMPLATES))
        dialog = PromptTemplateDialog(self, templates)
        dialog.template_selected.connect(self._insert_template)
        result = dialog.exec_()
        self.settings_data["prompt_templates"] = dialog.get_templates()
        save_settings(self.settings_data)

    def _insert_template(self, text):
        cursor = self.input_widget.text_edit.textCursor()
        cursor.insertText(text)
        self.input_widget.text_edit.setFocus()

    def _manage_conversations(self):
        dialog = ManageConversationsDialog(self, self.store)
        dialog.conversations_deleted.connect(self._on_bulk_delete)
        dialog.exec_()

    def _on_bulk_delete(self):
        self.sidebar.refresh()
        self._new_chat()

    def _save_draft(self):
        text = self.input_widget.text_edit.toPlainText()
        conv_id = self.current_conv["id"] if self.current_conv else ""
        if text.strip():
            try:
                draft = {"text": text, "conv_id": conv_id}
                with open(DRAFT_FILE, "w") as f:
                    json.dump(draft, f)
            except OSError:
                pass
        elif DRAFT_FILE.exists():
            try:
                DRAFT_FILE.unlink()
            except OSError:
                pass

    def _restore_draft(self):
        if DRAFT_FILE.exists():
            try:
                with open(DRAFT_FILE) as f:
                    draft = json.load(f)
                text = draft.get("text", "")
                if text.strip():
                    self.input_widget.text_edit.setPlainText(text)
            except (json.JSONDecodeError, OSError):
                pass

    def _execute_code_block(self, code_block_index):
        if not self.current_conv:
            return
        messages = self.current_conv.get("messages", [])
        code_blocks = []
        for msg in messages:
            if msg["role"] == "assistant":
                blocks = re.findall(
                    r'```(?:python|python3|py)\n(.*?)```',
                    msg["content"], re.DOTALL
                )
                code_blocks.extend(blocks)

        if code_block_index < 0 or code_block_index >= len(code_blocks):
            self.status_label.setText("Code block not found")
            return

        code = code_blocks[code_block_index]
        reply = QMessageBox.question(
            self, "Run Python Code",
            f"Execute this code?\n\n{code[:200]}{'...' if len(code) > 200 else ''}",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            result = subprocess.run(
                ['python3', '-c', code],
                capture_output=True, text=True, timeout=30,
                cwd=str(Path.home())
            )
            output = result.stdout
            if result.stderr:
                output += "\n" + result.stderr if output else result.stderr
            if not output.strip():
                output = "(no output)"
            QMessageBox.information(
                self, "Code Output",
                f"Exit code: {result.returncode}\n\n{output[:2000]}"
            )
        except subprocess.TimeoutExpired:
            QMessageBox.warning(self, "Timeout", "Code execution timed out (30s limit)")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to run code: {e}")

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
        self._save_draft()
        if hasattr(self, '_conn_checker'):
            self._conn_checker.stop()
            self._conn_checker.wait(2000)
        if hasattr(self, '_gpu_monitor'):
            self._gpu_monitor.stop()
            self._gpu_monitor.wait(2000)
        if hasattr(self, '_draft_timer'):
            self._draft_timer.stop()
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
