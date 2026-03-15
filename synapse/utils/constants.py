import os
import json
from pathlib import Path
from .themes import THEMES

# Application Constants
APP_NAME = "Synapse"
APP_VERSION = "1.0.0"
ORG_NAME = "JacobCook"

# Paths
HOME_DIR = Path.home()
CONFIG_DIR = HOME_DIR / ".local" / "share" / "synapse"
CONV_DIR = CONFIG_DIR / "conversations"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DRAFT_FILE = CONFIG_DIR / "draft.txt"

# Create directories if they don't exist
for d in [CONFIG_DIR, CONV_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Model Recommendations
RECOMMENDED_MODELS = [
    {"name": "mannix/llama3.1-8b-abliterated:tools-q5_k_m", "size_gb": 5.7, "desc": "Llama 3.1 8B Abliterated - UNCENSORED + TOOLS"},
    {"name": "huihui_ai/qwen3-coder-abliterated:latest", "size_gb": 19.0, "desc": "Qwen 3 Coder 30B Abliterated - Best uncensored coding (no tools)"},
    {"name": "huihui_ai/qwen3-vl-abliterated:latest", "size_gb": 5.0, "desc": "Qwen 3 VL Abliterated - Uncensored vision"},
    {"name": "huihui_ai/qwen2.5-coder-abliterate:32b", "size_gb": 19.0, "desc": "Qwen 2.5 Coder 32B Abliterated - Strong uncensored coding"},
    {"name": "llama3.2:3b", "size_gb": 2.0, "desc": "Llama 3.2 3B - Fast & efficient"},
    {"name": "qwen2.5-coder:7b", "size_gb": 4.7, "desc": "Qwen 2.5 Coder 7B - Standard coding"},
    {"name": "deepseek-r1:7b", "size_gb": 4.7, "desc": "DeepSeek R1 7B - Reasoning model"},
    {"name": "deepseek-r1:32b", "size_gb": 19.8, "desc": "DeepSeek R1 32B - Premium reasoning"},
    {"name": "qwen2.5:14b", "size_gb": 9.0, "desc": "Qwen 2.5 14B - Excellent all-rounder"},
]

# UI Defaults
DEFAULT_MODEL = "huihui_ai/qwen3.5-abliterated:27b-Claude"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_GEN_PARAMS = {"temperature": 0.7, "top_p": 0.9, "num_ctx": 4096}
DEFAULT_SYSTEM_PROMPT = "You are Synapse, a helpful AI coding assistant. You prioritize efficiency and quality."
DARK_THEME_QSS = THEMES["One Dark"]["qss"]

# Utility Functions
def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_settings(data):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

_ollama_url = DEFAULT_OLLAMA_URL
def get_ollama_url():
    return _ollama_url

def set_ollama_url(url):
    global _ollama_url
    _ollama_url = url

def estimate_tokens(text):
    if not text:
        return 0
    return max(len(text.split()), int(len(text) / 3.5))

def get_theme_qss(name):
    return THEMES.get(name, THEMES["One Dark"])["qss"]

import mimetypes
from datetime import datetime as _dt

def detect_mime(data_or_path):
    if isinstance(data_or_path, str) and len(data_or_path) > 260:
        import base64
        try:
            header = base64.b64decode(data_or_path[:32])
        except Exception:
            header = b""
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return "image/png"
        if header[:2] == b'\xff\xd8':
            return "image/jpeg"
        if header[:4] == b'GIF8':
            return "image/gif"
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return "image/webp"
        return "image/png"
    mime, _ = mimetypes.guess_type(str(data_or_path))
    return mime or "application/octet-stream"

def format_time(iso_str):
    try:
        dt = _dt.fromisoformat(iso_str)
        return dt.strftime("%I:%M %p")
    except Exception:
        return ""

def _build_chat_template():
    """Build the chat HTML template at import time with real braces."""
    return (
        '<!DOCTYPE html>\n<html>\n<head>\n<meta charset="utf-8">\n<style>\n'
        ':root {\n'
        '  --bg: #0d1117;\n'
        '  --surface: #161b22;\n'
        '  --surface2: #1c2128;\n'
        '  --border: #30363d;\n'
        '  --border-subtle: #21262d;\n'
        '  --fg: #e6edf3;\n'
        '  --fg2: #8b949e;\n'
        '  --fg3: #484f58;\n'
        '  --accent: #58a6ff;\n'
        '  --accent2: #7ee787;\n'
        '  --purple: #bc8cff;\n'
        '  --yellow: #e3b341;\n'
        '  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;\n'
        '  --mono: "JetBrains Mono", "Fira Code", "Cascadia Code", "SF Mono", Consolas, monospace;\n'
        '}\n'
        '*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }\n'
        'html { -webkit-font-smoothing: antialiased; }\n'
        'body {\n'
        '  background: var(--bg);\n'
        '  color: var(--fg);\n'
        '  font-family: var(--font);\n'
        '  font-size: FONT_SIZE_VALpx;\n'
        '  line-height: 1.6;\n'
        '  padding: 0 0 80px;\n'
        '}\n'
        '\n'
        '.msg {\n'
        '  display: flex;\n'
        '  gap: 14px;\n'
        '  padding: 20px 24px;\n'
        '  border-bottom: 1px solid var(--border-subtle);\n'
        '  transition: background .15s;\n'
        '}\n'
        '.msg:hover { background: rgba(255,255,255,.02); }\n'
        '.msg:hover .msg-toolbar { opacity: 1; }\n'
        '.msg.user { background: transparent; }\n'
        '.msg.assistant { background: var(--surface); }\n'
        '.msg.system { background: var(--surface2); }\n'
        '\n'
        '.msg-gutter { flex-shrink: 0; padding-top: 2px; }\n'
        '.avatar {\n'
        '  width: 30px; height: 30px;\n'
        '  border-radius: 8px;\n'
        '  display: flex; align-items: center; justify-content: center;\n'
        '  font-size: 13px; font-weight: 700;\n'
        '  color: #fff;\n'
        '}\n'
        '.av-user { background: linear-gradient(135deg, #8b5cf6, #6d28d9); }\n'
        '.av-ai   { background: linear-gradient(135deg, #3b82f6, #2563eb); font-size: 16px; }\n'
        '.av-sys  { background: linear-gradient(135deg, #eab308, #ca8a04); }\n'
        '\n'
        '.msg-body { flex: 1; min-width: 0; }\n'
        '.msg-head {\n'
        '  display: flex; align-items: center; gap: 8px;\n'
        '  margin-bottom: 4px;\n'
        '}\n'
        '.msg-name { font-weight: 600; font-size: 13px; color: var(--fg); }\n'
        '.ts { font-size: 11px; color: var(--fg3); }\n'
        '\n'
        '.msg-content {\n'
        '  font-size: FONT_SIZE_VALpx;\n'
        '  line-height: 1.65;\n'
        '  color: var(--fg);\n'
        '  overflow-wrap: break-word;\n'
        '  word-break: break-word;\n'
        '}\n'
        '.msg-content p { margin: 6px 0; }\n'
        '.msg-content ul, .msg-content ol { margin: 6px 0 6px 20px; }\n'
        '.msg-content li { margin: 2px 0; }\n'
        '.msg-content table { border-collapse: collapse; margin: 10px 0; font-size: 13px; }\n'
        '.msg-content th, .msg-content td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; }\n'
        '.msg-content th { background: var(--surface2); font-weight: 600; }\n'
        '.msg-content blockquote {\n'
        '  border-left: 3px solid var(--accent);\n'
        '  padding: 4px 12px;\n'
        '  margin: 8px 0;\n'
        '  color: var(--fg2);\n'
        '}\n'
        '.msg-content a { color: var(--accent); text-decoration: none; }\n'
        '.msg-content a:hover { text-decoration: underline; }\n'
        '.msg-content code {\n'
        '  font-family: var(--mono);\n'
        '  font-size: 0.88em;\n'
        '  background: rgba(110,118,129,.15);\n'
        '  padding: 2px 5px;\n'
        '  border-radius: 4px;\n'
        '}\n'
        '\n'
        '.code-block {\n'
        '  margin: 12px 0;\n'
        '  border: 1px solid var(--border);\n'
        '  border-radius: 8px;\n'
        '  overflow: hidden;\n'
        '  background: #0d1117;\n'
        '}\n'
        '.cb-header {\n'
        '  display: flex;\n'
        '  justify-content: space-between;\n'
        '  align-items: center;\n'
        '  padding: 6px 12px;\n'
        '  background: var(--surface2);\n'
        '  border-bottom: 1px solid var(--border);\n'
        '  font-size: 12px;\n'
        '}\n'
        '.cb-lang { color: var(--fg2); font-family: var(--mono); font-size: 11px; }\n'
        '.cb-actions { display: flex; gap: 4px; }\n'
        '.cb-btn {\n'
        '  font-family: var(--font);\n'
        '  font-size: 11px;\n'
        '  padding: 2px 8px;\n'
        '  border-radius: 4px;\n'
        '  border: 1px solid var(--border);\n'
        '  background: var(--surface);\n'
        '  color: var(--fg2);\n'
        '  cursor: pointer;\n'
        '  transition: all .12s;\n'
        '}\n'
        '.cb-btn:hover { background: var(--border-subtle); color: var(--fg); }\n'
        '.cb-run { border-color: var(--accent2); color: var(--accent2); }\n'
        '.cb-run:hover { background: rgba(126,231,135,.12); }\n'
        '.code-block pre {\n'
        '  margin: 0; padding: 14px 16px;\n'
        '  overflow-x: auto; border: none; border-radius: 0; background: transparent;\n'
        '}\n'
        '.code-block code {\n'
        '  font-family: var(--mono); font-size: 13px;\n'
        '  background: none; padding: 0; border-radius: 0;\n'
        '}\n'
        'pre { background: #0d1117; border-radius: 8px; margin: 10px 0; overflow: auto; }\n'
        '.highlight { padding: 14px 16px; overflow-x: auto; }\n'
        '\n'
        '.raw-md { margin: 8px 0; }\n'
        '.raw-pre {\n'
        '  font-family: var(--mono); font-size: 13px; color: var(--fg2);\n'
        '  white-space: pre-wrap; word-break: break-word;\n'
        '  background: var(--surface2); border: 1px solid var(--border);\n'
        '  border-radius: 6px; padding: 12px;\n'
        '}\n'
        '\n'
        '.msg-meta { margin-top: 8px; font-size: 11px; color: var(--fg3); }\n'
        '\n'
        '.msg-toolbar {\n'
        '  opacity: 0; transition: opacity .15s;\n'
        '  margin-top: 6px; display: flex; gap: 2px; flex-wrap: wrap;\n'
        '}\n'
        '.msg-toolbar a, .msg-toolbar button {\n'
        '  font-family: var(--font); font-size: 11px;\n'
        '  color: var(--fg3); background: var(--surface2);\n'
        '  border: 1px solid var(--border); border-radius: 4px;\n'
        '  padding: 2px 8px; text-decoration: none; cursor: pointer;\n'
        '  transition: all .12s;\n'
        '}\n'
        '.msg-toolbar a:hover, .msg-toolbar button:hover {\n'
        '  color: var(--accent); border-color: var(--accent);\n'
        '  background: rgba(88,166,255,.08);\n'
        '}\n'
        '\n'
        '.msg-images { margin: 6px 0; display: flex; flex-wrap: wrap; gap: 6px; }\n'
        '.att-img { max-height: 200px; border-radius: 8px; border: 1px solid var(--border); }\n'
        '.msg-files { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; }\n'
        '.att-file {\n'
        '  font-size: 12px; background: var(--surface2);\n'
        '  border: 1px solid var(--border); padding: 3px 10px;\n'
        '  border-radius: 6px; color: var(--accent);\n'
        '}\n'
        '\n'
        '.welcome {\n'
        '  display: flex; flex-direction: column; align-items: center; justify-content: center;\n'
        '  min-height: 70vh; text-align: center; padding: 40px 24px;\n'
        '}\n'
        '.w-logo { font-size: 48px; color: var(--accent); margin-bottom: 12px; }\n'
        '.welcome h1 { font-size: 28px; font-weight: 700; color: var(--fg); margin-bottom: 6px; }\n'
        '.w-sub { font-size: 15px; color: var(--fg2); margin-bottom: 32px; }\n'
        '.w-grid {\n'
        '  display: grid; grid-template-columns: repeat(2, 1fr);\n'
        '  gap: 12px; max-width: 420px; margin-bottom: 28px;\n'
        '}\n'
        '.w-card {\n'
        '  background: var(--surface); border: 1px solid var(--border);\n'
        '  border-radius: 10px; padding: 18px 14px; text-align: center;\n'
        '  transition: border-color .15s, background .15s; cursor: default;\n'
        '}\n'
        '.w-card:hover { border-color: var(--accent); background: var(--surface2); }\n'
        '.w-card-icon { font-size: 24px; margin-bottom: 6px; }\n'
        '.w-card-label { font-size: 12px; color: var(--fg2); font-weight: 500; }\n'
        '.w-keys { font-size: 12px; color: var(--fg3); }\n'
        '.w-keys kbd {\n'
        '  font-family: var(--mono); font-size: 11px;\n'
        '  background: var(--surface); border: 1px solid var(--border);\n'
        '  padding: 2px 6px; border-radius: 4px;\n'
        '}\n'
        '\n'
        '.tool-block {\n'
        '  margin: 8px 0;\n'
        '  border: 1px solid var(--border);\n'
        '  border-radius: 8px;\n'
        '  overflow: hidden;\n'
        '  background: var(--surface);\n'
        '  font-size: 13px;\n'
        '}\n'
        '.tool-block.tool-running {\n'
        '  border-color: var(--yellow);\n'
        '}\n'
        '.tool-header {\n'
        '  display: flex;\n'
        '  align-items: center;\n'
        '  gap: 8px;\n'
        '  padding: 8px 12px;\n'
        '  background: var(--surface2);\n'
        '  border-bottom: 1px solid var(--border);\n'
        '  cursor: pointer;\n'
        '  user-select: none;\n'
        '}\n'
        '.tool-header:hover { background: rgba(255,255,255,.04); }\n'
        '.tool-icon {\n'
        '  width: 20px; height: 20px;\n'
        '  border-radius: 4px;\n'
        '  display: flex; align-items: center; justify-content: center;\n'
        '  font-size: 11px; font-weight: 700;\n'
        '  flex-shrink: 0;\n'
        '}\n'
        '.tool-icon.tool-ok { background: rgba(126,231,135,.15); color: var(--accent2); }\n'
        '.tool-icon.tool-err { background: rgba(248,81,73,.15); color: #f85149; }\n'
        '.tool-icon.tool-wait { background: rgba(227,179,65,.15); color: var(--yellow); }\n'
        '.tool-name {\n'
        '  font-family: var(--mono);\n'
        '  font-size: 12px;\n'
        '  font-weight: 600;\n'
        '  color: var(--fg);\n'
        '}\n'
        '.tool-summary {\n'
        '  font-size: 12px;\n'
        '  color: var(--fg3);\n'
        '  margin-left: auto;\n'
        '  white-space: nowrap;\n'
        '  overflow: hidden;\n'
        '  text-overflow: ellipsis;\n'
        '  max-width: 50%;\n'
        '}\n'
        '.tool-chevron {\n'
        '  color: var(--fg3);\n'
        '  font-size: 10px;\n'
        '  transition: transform .15s;\n'
        '  flex-shrink: 0;\n'
        '}\n'
        '.tool-chevron.open { transform: rotate(90deg); }\n'
        '.tool-body {\n'
        '  display: none;\n'
        '  padding: 10px 12px;\n'
        '  font-family: var(--mono);\n'
        '  font-size: 12px;\n'
        '  color: var(--fg2);\n'
        '  max-height: 300px;\n'
        '  overflow: auto;\n'
        '  white-space: pre-wrap;\n'
        '  word-break: break-word;\n'
        '}\n'
        '.tool-body.open { display: block; }\n'
        '.tool-label {\n'
        '  font-size: 10px;\n'
        '  font-weight: 600;\n'
        '  color: var(--fg3);\n'
        '  text-transform: uppercase;\n'
        '  letter-spacing: .5px;\n'
        '  margin: 6px 0 3px;\n'
        '}\n'
        '.tool-label:first-child { margin-top: 0; }\n'
        '.tool-output {\n'
        '  background: var(--bg);\n'
        '  border: 1px solid var(--border);\n'
        '  border-radius: 4px;\n'
        '  padding: 8px 10px;\n'
        '  margin: 4px 0 8px;\n'
        '  max-height: 200px;\n'
        '  overflow: auto;\n'
        '}\n'
        '@keyframes tool-pulse {\n'
        '  0%,100% { opacity: 1; }\n'
        '  50% { opacity: .4; }\n'
        '}\n'
        '.tool-running .tool-icon { animation: tool-pulse 1.5s ease-in-out infinite; }\n'
        '\n'
        'PYGMENTS_CSS\n'
        '</style>\n</head>\n<body>\n'
        'MESSAGES_HTML\n'
        '<script>\n'
        'function copyCode(btn) {\n'
        '  var block = btn.closest(".code-block");\n'
        '  var code = block ? block.querySelector("code") : null;\n'
        '  if (code) {\n'
        '    navigator.clipboard.writeText(code.innerText);\n'
        '    btn.textContent = "Copied!";\n'
        '    setTimeout(function(){ btn.textContent = "Copy"; }, 1500);\n'
        '  }\n'
        '}\n'
        'function toggleRaw(idx) {\n'
        '  var r = document.getElementById("rendered-" + idx);\n'
        '  var raw = document.getElementById("raw-" + idx);\n'
        '  var btn = document.getElementById("rawbtn-" + idx);\n'
        '  if (!r || !raw || !btn) return;\n'
        '  if (raw.style.display === "none") {\n'
        '    raw.style.display = "block"; r.style.display = "none"; btn.textContent = "Rendered";\n'
        '  } else {\n'
        '    raw.style.display = "none"; r.style.display = "block"; btn.textContent = "Raw";\n'
        '  }\n'
        '}\n'
        'var _autoScroll = true;\n'
        'var _lastScrollTop = 0;\n'
        'window.addEventListener("scroll", function() {\n'
        '  var atBottom = (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 60;\n'
        '  _autoScroll = atBottom;\n'
        '});\n'
        'function _scrollBottom() { if (_autoScroll) window.scrollTo(0, document.body.scrollHeight); }\n'
        'function appendStreamToken(token) {\n'
        '  var el = document.getElementById("streaming-content");\n'
        '  if (!el) return;\n'
        '  el.textContent += token;\n'
        '  _scrollBottom();\n'
        '}\n'
        'function finalizeStream(html) {\n'
        '  var el = document.getElementById("streaming-content");\n'
        '  if (el) el.outerHTML = html;\n'
        '  _scrollBottom();\n'
        '}\n'
        'function toggleTool(id) {\n'
        '  var body = document.getElementById("toolbody-" + id);\n'
        '  var chev = document.getElementById("toolchev-" + id);\n'
        '  if (!body) return;\n'
        '  body.classList.toggle("open");\n'
        '  if (chev) chev.classList.toggle("open");\n'
        '}\n'
        'window.scrollTo(0, document.body.scrollHeight);\n'
        '</script>\n</body>\n</html>'
    )

CHAT_HTML_TEMPLATE = _build_chat_template()

# File type sets used by sidebar/indexer
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico")
TEXT_EXTENSIONS  = (
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".yaml", ".yml",
    ".md", ".txt", ".sh", ".bash", ".zsh", ".env", ".toml", ".ini", ".cfg",
    ".rs", ".go", ".cpp", ".c", ".h", ".java", ".kt", ".rb", ".php", ".sql",
    ".xml", ".csv", ".log",
)

def relative_time(iso_str):
    """Return a human-readable relative time string like '2h ago'."""
    try:
        from datetime import timezone
        dt = _dt.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = _dt.now(timezone.utc) - dt
        secs = int(diff.total_seconds())
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return ""
