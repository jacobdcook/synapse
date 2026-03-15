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
| Multiple conversations | No | Sidebar with search + pinning |
| Model switching | Restart required | Dropdown + auto VRAM unload |
| Markdown / code blocks | Raw text | Live-rendered with syntax highlighting |
| Image support | No | Multimodal (paste, drag-drop, file picker) |
| System prompts | Manual prefix | Presets + per-conversation editor |
| Model management | Terminal commands | Pull, delete, VRAM-aware recommendations |
| Generation controls | Hardcoded | Temperature, Top P, context length |
| Export | No | Markdown, HTML, JSON |

## Features

### Core Chat
- **Multi-Model Support** — Switch between any Ollama model from a dropdown. Synapse automatically unloads the previous model from VRAM before loading the new one.
- **Streaming Markdown** — Responses render markdown live during streaming, not just after completion. Code blocks, tables, and formatting appear in real-time.
- **Edit & Regenerate** — Click to edit any sent message or regenerate any response. "Retry with..." lets you regenerate using a different model.
- **Auto-Title** — Conversations are automatically titled by the model after the first exchange.
- **System Prompt Presets** — Built-in presets (Coder, Creative Writer, Concise, Analyst) plus save/load custom presets.

### Multimodal
- **Image Attachment** — Attach images via file picker, drag-and-drop, or Ctrl+V paste from clipboard. Works with vision models (LLaVA, Llama 3.2 Vision).
- **Text File Context** — Drag .py, .js, .md, or any text file into the chat. Contents are injected as context with the message.

### Model Management
- **Pull Models** — Download new models from within the app with a live progress bar.
- **Delete Models** — Remove models you don't use.
- **VRAM-Aware Recommendations** — Detects your GPU VRAM (via nvidia-smi) and shows a curated list of models that will fit. Color-coded: green = installed, orange = tight fit.
- **Model Info Tooltips** — Hover any model in the dropdown to see parameter count, quantization level, and family.

### Organization
- **Pin Conversations** — Pin important chats to the top of the sidebar.
- **Conversation Search** — Search across all conversations by title or message content.
- **Conversation Stats** — View total messages, tokens generated, throughput, and context usage.
- **Import/Export** — Import JSON conversations. Export as Markdown or self-contained HTML.
- **Relative Timestamps** — Sidebar shows "2h ago", "Yesterday", etc.
- **Double-Click Rename** — Double-click any sidebar item to rename it.

### Power User
- **Generation Parameters** — Temperature, Top P, and context length controls via settings dialog.
- **Context Window Bar** — Visual indicator showing estimated context usage. Changes color as you approach the limit.
- **Remote Ollama** — Connect to Ollama on another machine by configuring the server URL.
- **Notification Sound** — Optional sound when a response finishes and the window isn't focused.
- **Zoom Controls** — Ctrl+=/- to zoom the chat view in/out.
- **Slash Commands** — `/clear`, `/model`, `/system`, `/export`, `/stats`, `/pull`, `/help` typed directly in the input.

### UI
- **Dark Theme** — VS Code-inspired dark UI.
- **Auto-Scroll Lock** — Scroll up during streaming to read without being yanked to the bottom. A floating button appears to jump back down.
- **Message Timestamps** — Each message shows the time it was sent.
- **Copy Response** — Hover any assistant message to copy the full response. Code blocks have individual copy buttons.
- **Token/s Display** — Throughput shown in the status bar and per-message metadata.
- **Connection Indicator** — Green/red dot showing Ollama connection status.

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running with at least one model pulled
- PyQt5 and PyQtWebEngine

### Install & Run

```bash
pip install PyQt5 PyQtWebEngine markdown pygments

ollama serve

git clone https://github.com/jacobdcook/synapse.git
cd synapse
python3 synapse.py
```

### Linux Desktop Launcher

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
synapse.py          # Single-file application (~2800 lines)
~/.local/share/synapse/
├── conversations/  # JSON files, one per conversation
└── settings.json   # Model, gen params, presets, server URL, zoom, notifications
```

**Tech stack:**
- **PyQt5** — Native desktop widgets + QWebEngineView for chat rendering
- **QWebEngineView** — Chromium-based view for live markdown/HTML rendering
- **Ollama REST API** — `/api/chat` (streaming), `/api/tags` (models), `/api/show` (model info), `/api/pull` (download), `/api/delete` (remove), `/api/generate` (VRAM unload)
- **Pygments** — Syntax highlighting (Monokai theme)
- **Python `markdown`** — Fenced code, tables, smart lists

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `Ctrl+N` | New chat |
| `Ctrl+B` | Toggle sidebar |
| `Ctrl+I` | Import conversation |
| `Ctrl+Shift+C` | Copy last response |
| `Ctrl+L` | Focus input |
| `Ctrl+=` | Zoom in |
| `Ctrl+-` | Zoom out |
| `Ctrl+0` | Reset zoom |
| `Ctrl+V` | Paste image from clipboard |

## Supported Models

Synapse works with any model available through Ollama. The built-in model manager recommends models based on your GPU VRAM. Some popular options:

| Model | VRAM | Use Case |
|---|---|---|
| `llama3.2:3b` | 2 GB | Fast, lightweight |
| `qwen2.5:7b` | 5 GB | Great coding + general |
| `llama3.1:8b` | 5 GB | Very capable all-rounder |
| `gemma2:9b` | 5 GB | Google, strong |
| `qwen2.5:14b` | 9 GB | Excellent all-rounder |
| `qwen2.5-coder:14b` | 9 GB | Strong coding |
| `deepseek-r1:14b` | 9 GB | Advanced reasoning |
| `gemma2:27b` | 16 GB | Near frontier quality |
| `qwen2.5:32b` | 20 GB | Premium quality |
| `deepseek-r1:32b` | 20 GB | Premium reasoning |
| `llama3.2-vision:11b` | 8 GB | Multimodal (images) |

## License

MIT
