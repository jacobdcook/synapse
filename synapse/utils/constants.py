import os
import platform
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)
from .themes import THEMES

# Application Constants
APP_NAME = "Synapse"
APP_VERSION = "3.0.0"
ORG_NAME = "JacobCook"

# Paths
HOME_DIR = Path.home()
SYSTEM = platform.system()

if SYSTEM == "Windows":
    CONFIG_DIR = Path(os.environ.get("APPDATA", HOME_DIR)) / "Synapse"
elif SYSTEM == "Darwin":
    CONFIG_DIR = HOME_DIR / "Library" / "Application Support" / "Synapse"
else:
    # Linux/Other
    CONFIG_DIR = HOME_DIR / ".local" / "share" / "synapse"

CONV_DIR = CONFIG_DIR / "conversations"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DRAFT_FILE = CONFIG_DIR / "draft.txt"

TEMPLATE_DIR = CONFIG_DIR / "templates"
PLUGINS_DIR = CONFIG_DIR / "plugins"
PLUGIN_SETTINGS_FILE = CONFIG_DIR / "plugin_settings.json"

# Create directories if they don't exist
for d in [CONFIG_DIR, CONV_DIR, TEMPLATE_DIR, PLUGINS_DIR]:
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
    {"name": "gpt-4o", "size_gb": 0, "desc": "OpenAI GPT-4o - Flagship cloud model"},
    {"name": "claude-3-5-sonnet-20240620", "size_gb": 0, "desc": "Anthropic Claude 3.5 Sonnet - Best for coding"},
]

# Model Pricing (per 1M tokens)
MODEL_PRICES = {
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "claude-3-5-sonnet-20240620": {"input": 3.0, "output": 15.0},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
}

MERMAID_JS_URL = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"

KATEX_VERSION = "0.16.9"
KATEX_CSS_URL = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.css"
KATEX_JS_URL = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/katex.min.js"
KATEX_AUTO_RENDER_JS_URL = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist/contrib/auto-render.min.js"

DEFAULT_FOLDERS = ["General", "Work", "Research", "Archive"]
TAG_COLORS = {
    "urgent": "#e57373",   # Red
    "todo": "#ffb74d",     # Orange
    "idea": "#fff176",     # Yellow
    "ref": "#81c784",      # Green
    "personal": "#64b5f6", # Blue
    "misc": "#ba68c8"      # Purple
}
# UI Defaults
DEFAULT_MODEL = "huihui_ai/qwen3.5-abliterated:27b-Claude"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_SD_URL = "http://127.0.0.1:7860"
DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"
DEFAULT_GEN_PARAMS = {"temperature": 0.7, "top_p": 0.9, "num_ctx": 4096, "streaming_delay": 0.0}
DEFAULT_SYSTEM_PROMPT = """You are Synapse, a powerful AI coding assistant.
You have access to advanced tools and long-term memory.
1. MEMORY: Use 'remember_fact' for persistent info and 'update_preference' for user style.
2. PLANNING: For complex tasks, use 'update_plan' to maintain a visible checklist in the sidebar.
3. AGENTIC LOOPS: You can run multiple tool turns automatically. If a command fails, use 'run_test' and self-correct.
Prioritize efficiency, quality, and clear communication.

When the user pastes long content (product pages, articles, docs):
1. Extract and answer their explicit question first. Never respond with a generic intro.
2. If they provide two items to compare, compare them and give a clear recommendation.
3. If they ask for a specific size/option, state it explicitly."""
DARK_THEME_QSS = THEMES["One Dark"]["qss"]

# Keyboard Shortcuts
DEFAULT_SHORTCUTS = {
    "palette": "Ctrl+K",
    "new_chat": "Ctrl+N",
    "close_tab": "Ctrl+W",
    "next_tab": "Ctrl+Tab",
    "prev_tab": "Ctrl+Shift+Tab",
    "send": "Ctrl+Enter",
    "send_agentic": "Ctrl+Shift+Enter",
    "toggle_sidebar": "Ctrl+/",
    "clear": "Ctrl+L",
    "regenerate": "Ctrl+R",
    "cancel": "Escape",
    "toggle_sidebar_alt": "Ctrl+B",
    "save_file": "Ctrl+S",
    "rollback": "Ctrl+Z",
    "command_palette": "Ctrl+Shift+P",
    "focus_input": "Ctrl+L",
    "close_tab": "Ctrl+W",
    "next_tab": "Ctrl+Tab",
    "prev_tab": "Ctrl+Shift+Tab",
    "new_window": "Ctrl+Shift+N",
    "global_search": "Ctrl+Shift+F",
    "settings": "Ctrl+,",
    "import_conv": "Ctrl+I",
    "zoom_in": "Ctrl+=",
    "zoom_out": "Ctrl+-",
    "zoom_reset": "Ctrl+0",
    "paste_image": "Ctrl+V",
    "toggle_terminal": "Ctrl+`",
    "search_replace": "Ctrl+Shift+H",
    "screenshot": "Ctrl+Shift+S",
    "zen_mode": "Ctrl+Shift+Z",
    "global_summon": "<ctrl>+<alt>+s"
}

# Utility Functions
def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Failed to load settings from {SETTINGS_FILE}: {e}")
    return {}

def save_settings(data):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        log.error(f"Failed to save settings to {SETTINGS_FILE}: {e}")

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
    from .themes import get_all_themes
    theme = get_all_themes().get(name, THEMES["One Dark"])
    return theme.get("qss", THEMES["One Dark"]["qss"])

import mimetypes
from datetime import datetime as _dt

def detect_mime(data_or_path):
    if isinstance(data_or_path, str) and len(data_or_path) > 260:
        import base64
        try:
            sample = data_or_path[:64]
            header = base64.b64decode(sample)
        except Exception:
            header = b""
        
        if header.startswith(b'\x89PNG\r\n\x1a\n'):
            return "image/png"
        if header.startswith(b'\xff\xd8'):
            return "image/jpeg"
        if header.startswith(b'GIF8'):
            return "image/gif"
        if header.startswith(b'RIFF') and b'WEBP' in header:
            return "image/webp"
        return "image/png"
    
    mime, _ = mimetypes.guess_type(str(data_or_path))
    return mime or "application/octet-stream"
def format_time(iso_str):
    try:
        dt = _dt.fromisoformat(iso_str)
        # Convert to local time if it's offset-aware
        if dt.tzinfo is not None:
            dt = dt.astimezone() # astimezone() with no args converts to local time
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
        '.branch-switcher {\n'
        '  display: inline-flex; align-items: center; gap: 4px;\n'
        '  margin-left: 8px; padding: 1px 6px; border-radius: 4px;\n'
        '  background: var(--surface2); border: 1px solid var(--border);\n'
        '  font-size: 10px; color: var(--fg2); user-select: none;\n'
        '}\n'
        '.br-btn {\n'
        '  cursor: pointer; padding: 0 2px; color: var(--fg3); transition: color .12s;\n'
        '  font-weight: bold;\n'
        '}\n'
        '.br-btn:hover { color: var(--accent); }\n'
        '.br-info { font-weight: 600; min-width: 24px; text-align: center; }\n'
        '\n'
        '.fb-btn {\n'
        '  color: var(--fg3); background: transparent; border: none;\n'
        '  cursor: pointer; padding: 2px 4px; border-radius: 4px; font-size: 14px;\n'
        '  transition: color .12s, transform .12s;\n'
        '}\n'
        '.fb-btn:hover { color: var(--accent); transform: scale(1.1); }\n'
        '.fb-btn.fb-active { color: var(--accent); }\n'
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
        '.msg-content table tbody tr:nth-child(even) { background: rgba(0,0,0,.15); }\n'
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
        '.cb-preview { border-color: var(--purple); color: var(--purple); }\n'
        '.cb-preview:hover { background: rgba(188,140,255,.12); }\n'
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
        '.drag-handle {\n'
        '  cursor: grab; opacity: 0.3; font-size: 14px; padding: 2px 4px;\n'
        '  transition: opacity .15s; user-select: none;\n'
        '}\n'
        '.drag-handle:hover { opacity: 0.8; }\n'
        '.drag-handle:active { cursor: grabbing; }\n'
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
        '.think-block {\n'
        '  margin: 8px 0;\n'
        '  border: 1px solid var(--border);\n'
        '  border-radius: 8px;\n'
        '  overflow: hidden;\n'
        '  background: rgba(139,148,158,.06);\n'
        '  font-size: 12px;\n'
        '}\n'
        '.think-header {\n'
        '  padding: 6px 12px;\n'
        '  color: var(--fg3);\n'
        '  cursor: pointer;\n'
        '  user-select: none;\n'
        '  font-style: italic;\n'
        '  font-size: 11px;\n'
        '}\n'
        '.think-header:hover { color: var(--fg2); }\n'
        '.think-chevron { display: inline-block; transition: transform .15s; font-style: normal; }\n'
        '.think-chevron.open { transform: rotate(90deg); }\n'
        '.think-body {\n'
        '  display: none;\n'
        '  padding: 8px 14px;\n'
        '  color: var(--fg3);\n'
        '  border-top: 1px solid var(--border);\n'
        '  line-height: 1.5;\n'
        '  font-size: 12px;\n'
        '  max-height: 400px;\n'
        '  overflow-y: auto;\n'
        '}\n'
        '.think-body.open { display: block; }\n'
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
        '@keyframes stream-blink { 50% { opacity: 0; } }\n'
        '#streaming-content::after { content: "|"; animation: stream-blink 1s step-end infinite; color: var(--accent); }\n'
        '.thinking-placeholder { color: var(--fg3); font-style: italic; }\n'
        '\n'
        'PYGMENTS_CSS\n'
        '</style>\n</head>\n<body>\n'
        'MESSAGES_HTML\n'
        '<script>\n'
        'if (typeof structuredClone === "undefined") {\n'
        '  window.structuredClone = function(obj) { try { return JSON.parse(JSON.stringify(obj)); } catch(e) { return obj; } };\n'
        '}\n'
        '</script>\n'
        '<link rel="stylesheet" href="KATEX_CSS_URL">\n'
        '<script src="KATEX_JS_URL"></script>\n'
        '<script src="KATEX_AUTO_RENDER_JS_URL"></script>\n'
        '<script src="MERMAID_JS_URL"></script>\n'
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
        '  var ph = document.querySelector(".thinking-placeholder");\n'
        '  if (ph && el.textContent === "") ph.style.display = "none";\n'
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
        'function toggleThink(id) {\n'
        '  var body = document.getElementById("thinkbody-" + id);\n'
        '  var chev = document.getElementById("thinkchev-" + id);\n'
        '  if (!body) return;\n'
        '  body.classList.toggle("open");\n'
        '  if (chev) chev.classList.toggle("open");\n'
        '}\n'
        'function injectPlan(planText) {\n'
        '  var div = document.createElement("div");\n'
        '  div.className = "think-block";\n'
        '  div.innerHTML = \'<div class="think-header" onclick="this.nextElementSibling.classList.toggle(\\\'open\\\')">Plan</div><div class="think-body open"><pre style="margin:0;white-space:pre-wrap;">\' + planText + \'</pre></div>\';\n'
        '  document.body.appendChild(div);\n'
        '  _scrollBottom();\n'
        '}\n'
        '    try { mermaid.initialize({ startOnLoad: true, theme: "dark", securityLevel: "loose" }); } catch(e) { console.error("Mermaid init failed:", e); }\n'
        'renderMathInElement(document.body, {\n'
        '  delimiters: [\n'
        '    {left: "$$", right: "$$", display: true},\n'
        '    {left: "$", right: "$", display: false},\n'
        '    {left: "\\\\(", right: "\\\\)", display: false},\n'
        '    {left: "\\\\[", right: "\\\\]", display: true}\n'
        '  ], throwOnError: false\n'
        '});\n'
        'window.scrollTo(0, document.body.scrollHeight);\n'
        '/* Drag-and-drop message reordering */\n'
        'document.querySelectorAll(".msg").forEach(function(el) {\n'
        '  el.addEventListener("dragover", function(e) { e.preventDefault(); el.style.borderTop = "2px solid #58a6ff"; });\n'
        '  el.addEventListener("dragleave", function(e) { el.style.borderTop = ""; });\n'
        '  el.addEventListener("drop", function(e) {\n'
        '    e.preventDefault(); el.style.borderTop = "";\n'
        '    var fromIdx = e.dataTransfer.getData("text/plain");\n'
        '    var toIdx = el.dataset.idx;\n'
        '    if (fromIdx !== toIdx) window.location.href = "action://reorder/" + fromIdx + "/" + toIdx;\n'
        '  });\n'
        '});\n'
        '</script>\n'
        '</body>\n</html>'
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
        now = _dt.now(timezone.utc)
        
        if dt.tzinfo is None:
            # Assume naive timestamps are local time, so we should compare with naive now
            now = _dt.now()
        else:
            # Aware timestamp, ensure we compare in UTC
            dt = dt.astimezone(timezone.utc)
            
        diff = now - dt
        secs = int(diff.total_seconds())
        if secs < 0: secs = 0 # Handle slight clock drifts
        if secs < 60:
            return "just now"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return ""
