# Synapse

A polished, ChatGPT-style desktop chat client that connects to your local [Ollama](https://ollama.com) models. Run any LLM on your own hardware — no API keys, no cloud, no data leaving your machine.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![PyQt5](https://img.shields.io/badge/PyQt5-Desktop_GUI-green?logo=qt&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-Local_LLMs-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Why Synapse?

Most local LLM interfaces are either terminal-only or bloated Electron apps. Synapse is a lightweight, native desktop client that gives you the ChatGPT experience with models running entirely on your own GPU — with features the terminal can't match.

| Feature | Terminal (`ollama run`) | Synapse |
|---|---|---|
| Conversation history | Per-session only | Persistent across sessions |
| Multiple conversations | No | Sidebar with search |
| Model switching | Restart required | Dropdown + auto VRAM unload |
| Markdown / code blocks | Raw text | Rendered with syntax highlighting |
| Copy code button | Manual select | One click |
| System prompts | Manual prefix | Per-conversation GUI editor |
| Export conversations | No | Markdown export |

## Features

- **Multi-Model Support** — Switch between any Ollama model (Qwen, DeepSeek, Gemma, Mistral, Llama, etc.) from a dropdown. Synapse automatically unloads the previous model from VRAM before loading the new one.
- **Conversation Memory** — Every conversation is saved locally as JSON. Reopen the app and pick up where you left off.
- **Streaming Responses** — Tokens appear in real-time as the model generates, with a stop button to cancel mid-response.
- **Markdown Rendering** — Full markdown support including fenced code blocks with syntax highlighting (Monokai theme) and one-click copy buttons.
- **Dark Theme** — VS Code-inspired dark UI that's easy on the eyes during long sessions.
- **System Prompts** — Set per-conversation system prompts to shape model behavior.
- **Conversation Management** — Rename, delete, search, and export conversations from the sidebar.
- **Lightweight** — Single Python file, no Electron, no npm, no Docker. Just Python + PyQt5.

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running with at least one model pulled
- PyQt5 and PyQtWebEngine

### Install & Run

```bash
# Install dependencies (if not already installed)
pip install PyQt5 PyQtWebEngine markdown pygments

# Make sure Ollama is running
ollama serve

# Pull a model (if you haven't already)
ollama pull qwen2.5:14b

# Clone and run
git clone https://github.com/jacobdcook/synapse.git
cd synapse
python3 synapse.py
```

### Linux Desktop Launcher

To add Synapse to your application menu:

```bash
cat > ~/.local/share/applications/synapse.desktop << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Synapse
Comment=Multi-model AI chat client for local Ollama models
Exec=python3 /path/to/synapse/synapse.py
Icon=chat
Terminal=false
Categories=Utility;Development;
EOF
```

## Architecture

```
synapse.py          # Single-file application (~650 lines)
~/.local/share/synapse/
├── conversations/  # JSON files, one per conversation
└── settings.json   # Last-used model, window geometry, default system prompt
```

**Tech stack:**
- **PyQt5** — Native desktop widgets + QWebEngineView for chat rendering
- **QWebEngineView** — Chromium-based view for markdown/HTML rendering with syntax highlighting
- **Ollama REST API** — `/api/chat` for streaming responses, `/api/tags` for model listing, `/api/generate` with `keep_alive: 0` for VRAM unloading
- **Pygments** — Syntax highlighting for code blocks (Monokai theme)
- **Python `markdown`** — Markdown-to-HTML conversion with fenced code, tables, and smart lists

**Key design decisions:**
- **Streaming via QThread + signals** — Background thread reads Ollama's streaming response line-by-line, emits tokens to the UI thread via Qt signals. Zero shared mutable state.
- **VRAM-aware model switching** — When you switch models, Synapse sends `keep_alive: 0` to unload the current model before the new one loads. Critical for GPUs with limited VRAM.
- **Lazy conversation persistence** — New conversations are only saved to disk after the first assistant response, preventing empty conversation clutter.

## Supported Models

Synapse works with any model available through Ollama. Some popular options:

| Model | Size | Use Case |
|---|---|---|
| `qwen2.5:14b` | 9 GB | Strong general-purpose, great at code |
| `qwen3:14b` | 9 GB | Latest Qwen with improved reasoning |
| `deepseek-r1:14b` | 9 GB | Chain-of-thought reasoning |
| `deepseek-r1:32b` | 19 GB | Heavy reasoning tasks |
| `gemma3:27b` | 17 GB | Google's latest, strong multilingual |
| `mistral-small:24b` | 14 GB | Fast, efficient, good at instruction following |
| `llama3.1:8b` | 5 GB | Meta's latest, lightweight |

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Enter` | Send message |
| `Shift+Enter` | New line in message |

## License

MIT
