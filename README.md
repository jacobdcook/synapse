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
| Multiple conversations | No | Tabbed chats + sidebar with search |
| Model switching | Restart required | Dropdown + auto VRAM unload |
| Markdown / code blocks | Raw text | Live-rendered with syntax highlighting |
| Image support | No | Multimodal (paste, drag-drop, file picker) |
| System prompts | Manual prefix | Presets + per-conversation editor |
| Tool use | No | Built-in tools + MCP server support |
| Model management | Terminal commands | Pull, delete, VRAM-aware recommendations |
| Workspace | No | File browser, editor, terminal, git panel |

## Features

### Core Chat
- **Multi-Model Support** — Switch between any Ollama model from a dropdown. Synapse automatically unloads the previous model from VRAM before loading the new one.
- **Streaming Markdown** — Responses render markdown live during streaming. Code blocks, tables, and formatting appear in real-time.
- **Edit & Regenerate** — Edit any sent message or regenerate any response. "Retry with..." regenerates using a different model.
- **Tabbed Conversations** — Open multiple chats in tabs, drag to reorder.
- **Auto-Title** — Conversations are automatically titled by the model after the first exchange.
- **Type While Streaming** — Queue your next message while the model is still generating.

### Tool Use & MCP
- **Built-in Tools** — File read/write, command execution, web search — the model can use tools to accomplish tasks.
- **MCP (Model Context Protocol)** — Connect external tool servers (GitHub, filesystem, databases) via the MCP standard. Configure servers in Settings > MCP Servers.
- **Tool Approval** — Review and approve/reject each tool call, or enable auto-execute for trusted workflows.
- **Three-tier Dispatch** — Built-in tools > plugins > MCP servers, with automatic routing.

### Workspace
- **File Browser** — Browse and open project files from the sidebar.
- **Built-in Editor** — Edit files with syntax highlighting directly in Synapse.
- **Integrated Terminal** — Run commands without leaving the app.
- **Git Panel** — View status, stage files, commit, and push.
- **Workspace Search** — Full-text search across your project files.
- **RAG Context** — Workspace files are automatically indexed and injected as context when relevant.

### Multimodal
- **Image Attachment** — Attach images via file picker, drag-and-drop, or Ctrl+V paste from clipboard.
- **Text File Context** — Drag .py, .js, .md, or any text file into the chat. Contents are injected as context.

### Model Management
- **Pull Models** — Download new models from within the app with a live progress bar.
- **Delete Models** — Remove models you don't use.
- **VRAM-Aware Recommendations** — Detects your GPU VRAM and shows models that will fit, color-coded by availability.

### Organization
- **Pin & Bookmark** — Pin conversations to the top, bookmark individual messages.
- **Conversation Search** — Search across all conversations by title or content.
- **Compare Mode** — Compare two conversations side-by-side.
- **Import/Export** — Import JSON conversations. Export as Markdown or self-contained HTML.
- **Command Palette** — Ctrl+Shift+P to quickly access any action.

### Power User
- **Slash Commands** — `/clear`, `/model`, `/system`, `/export`, `/stats`, `/pull`, `/mcp`, `/help` and more.
- **Generation Parameters** — Temperature, Top P, context length, repeat penalty.
- **System Prompt Presets** — Built-in presets (Coder, Creative Writer, Concise, Analyst) plus custom presets.
- **Remote Ollama** — Connect to Ollama on another machine by configuring the server URL.
- **Notification Sound** — Optional notification when a response finishes and the window isn't focused.
- **Zoom Controls** — Ctrl+=/- to zoom the chat view.

## Primary Models

These are the models I primarily use with Synapse on an RTX 4090 (24GB VRAM):

| Model | Parameters | Use Case | Tool Support |
|---|---|---|---|
| `huihui_ai/qwen3.5-abliterated:27b-Claude` | 27B | Primary — uncensored, coding + general chat | Yes |
| `huihui_ai/qwen3-coder-abliterated` | 30B | Coding-focused alternative | No |
| `qwen2.5:32b` | 32B | High-quality general purpose | Yes |
| `gemma3:27b` | 27B | Google, strong general reasoning | No |

Synapse works with **any** Ollama model. The built-in model manager recommends models based on your GPU VRAM.

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running (`ollama serve`)
- PyQt5 and PyQtWebEngine

### Install & Run

```bash
pip install PyQt5 PyQtWebEngine markdown pygments

ollama serve

git clone https://github.com/jacobdcook/synapse.git
cd synapse
python3 -m synapse
```

### Linux Desktop Launcher

```bash
cat > ~/.local/share/applications/synapse.desktop << 'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Synapse
Comment=Multi-model AI chat client for local Ollama models
Exec=python3 -m synapse
Icon=chat
Terminal=false
Categories=Utility;Development;
StartupWMClass=Synapse
EOF
```

## Architecture

```
synapse/
├── __main__.py          # Entry point
├── core/
│   ├── api.py           # Ollama API client (streaming, tool support)
│   ├── agent.py         # Tool registry & execution
│   ├── mcp.py           # MCP client manager (JSON-RPC over stdio)
│   ├── renderer.py      # HTML/CSS chat renderer
│   ├── store.py         # Conversation persistence
│   ├── indexer.py       # Workspace file indexer (RAG)
│   ├── git.py           # Git operations
│   └── plugins.py       # Plugin system
├── ui/
│   ├── main.py          # Main window & orchestration
│   ├── input.py         # Chat input with completers
│   ├── sidebar.py       # Conversation list
│   ├── workspace.py     # File browser panel
│   ├── editor.py        # Built-in code editor
│   ├── terminal.py      # Integrated terminal
│   ├── git_panel.py     # Git status/commit UI
│   ├── settings_dialog.py  # Settings (gen params, MCP, themes)
│   ├── command_palette.py  # Ctrl+Shift+P command palette
│   └── ...
├── utils/
│   ├── constants.py     # App constants
│   └── themes.py        # Theme definitions
└── resources/           # Icons, sounds

~/.local/share/synapse/
├── conversations/       # JSON files, one per conversation
└── settings.json        # All settings (model, MCP servers, gen params, etc.)
```

**Tech stack:**
- **PyQt5** — Native desktop widgets + QWebEngineView for chat rendering
- **QWebEngineView** — Chromium-based view for live markdown/HTML rendering
- **Ollama REST API** — Streaming chat, model management, tool calling
- **MCP** — Model Context Protocol for external tool servers
- **Pygments** — Syntax highlighting (Monokai theme)

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `Ctrl+N` | New chat |
| `Ctrl+T` | New tab |
| `Ctrl+W` | Close tab |
| `Ctrl+B` | Toggle sidebar |
| `Ctrl+Shift+P` | Command palette |
| `Ctrl+L` | Focus input |
| `Ctrl+=` | Zoom in |
| `Ctrl+-` | Zoom out |
| `Ctrl+0` | Reset zoom |
| `Ctrl+V` | Paste image from clipboard |
| `Ctrl+Z` | Undo last file edit (tool use) |

## License

MIT
