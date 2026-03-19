# Synapse IDE Evolution Plan
## From AI Chat Client → Cursor/Windsurf-Level AI IDE

**Project:** `/home/z1337/Desktop/PROJECTS/Synapse/`
**Current State:** 66,680 lines across 72 files. Feature-rich chat client with tools, MCP, RAG, workspace, git, voice, image gen.
**Goal:** Transform into a full AI-powered IDE that competes with Cursor, Windsurf, and Augment Code.
**Verify after each phase:** `cd /home/z1337/Desktop/PROJECTS/Synapse && python3 -c "from synapse.ui.main import MainWindow; print('OK')"`

---

## Architecture Overview (Read First)

```
synapse/
├── core/           # Business logic, API, tools
│   ├── api.py      # OllamaWorker, OpenRouterWorker, WorkerFactory (988 lines)
│   ├── agent.py    # ToolRegistry with 11 default tools (376 lines)
│   ├── mcp.py      # MCP server management, JSON-RPC (380 lines)
│   ├── renderer.py # Markdown→HTML with code block action buttons (500 lines)
│   ├── store.py    # SQLite FTS conversation storage (285 lines)
│   ├── indexer.py  # Workspace file chunking + embeddings (250 lines)
│   ├── graph_rag.py# Hybrid vector + graph search (203 lines)
│   ├── git.py      # Git operations wrapper (108 lines)
│   └── code_executor.py # Sandboxed Python execution (111 lines)
├── ui/             # PyQt5 widgets
│   ├── main.py     # MainWindow orchestrator (3551 lines) — THE central file
│   ├── input.py    # Chat input with @mention, /commands, attachments (838 lines)
│   ├── workspace.py# File tree + EditorTabs with syntax highlighting (300 lines)
│   ├── diff_view.py# Side-by-side diff dialog with accept/reject (106 lines)
│   ├── git_panel.py# Git status, diff, commit UI (181 lines)
│   ├── editor.py   # CodeEditor with Pygments highlighting (500 lines)
│   ├── sidebar.py  # Conversation list with folders/tags/search (550 lines)
│   ├── activity_bar.py # Left icon bar for panel switching (150 lines)
│   ├── terminal.py # Embedded terminal widget (exists but basic)
│   └── canvas.py   # QWebEngineView for HTML/SVG/Mermaid preview (121 lines)
└── utils/
    ├── constants.py# Themes, shortcuts, settings I/O (644 lines)
    └── themes.py   # Color schemes
```

### Key Patterns to Follow
- **Qt Signal/Slot** for all async: QThread workers + pyqtSignal
- **Action protocol**: HTML links with `action://` prefix handled by `chat_page.py` → `MainWindow`
- **Tool registry**: `agent.py` has `ToolRegistry` class — register new tools there
- **MCP namespacing**: `mcp__server_name__tool_name` format for external tools
- **Settings**: JSON at `~/.local/share/synapse/settings.json`, loaded/saved via `constants.py`
- **Theme**: Dict with keys `bg`, `fg`, `sidebar_bg`, `accent`, `input_bg`, `border` — pass to `apply_theme()`
- **Streaming**: Tokens arrive via `token_received` signal, batched rendering every 100ms
- **Message format**: `{"id": uuid, "role": "user"|"assistant"|"tool_results", "content": str, "timestamp": iso, "model": str}`

### How Messages Flow
```
InputWidget.message_submitted → MainWindow._send_message()
  → Build messages list, inject RAG/search context
  → WorkerFactory(model, messages, tools=[agent_tools + mcp_tools])
  → Worker.token_received → _render_token() → QWebEngineView
  → Worker.tool_calls_received → _handle_tool_calls() → agent.execute() or mcp.execute_tool()
  → Worker.response_finished → _on_response_done() → save, auto-title, render final
```

### How Tool Calls Work
```python
# In agent.py, tools are registered:
registry = ToolRegistry()
registry.register("tool_name", handler_fn, schema_dict)

# In main.py _send_message(), tools are collected:
tools = self.agent.get_tool_definitions()  # Returns Ollama-format tool defs
tools += self.mcp_manager.get_tool_definitions()

# Worker sends tools in API payload, model returns tool_calls
# _handle_tool_calls() dispatches to agent.execute(name, args) or mcp_manager.execute_tool()
# Results appended as tool_results message, then model continues
```

---

## Phase 1: Agentic Loop (CRITICAL — This is what makes Cursor "Cursor")

**Priority: HIGHEST**
**Files to modify:** `synapse/ui/main.py`, `synapse/core/agent.py`, `synapse/core/api.py`
**New file:** `synapse/core/agentic.py`

### What Cursor Does
The AI doesn't just make one tool call and stop. It autonomously chains: read file → edit file → run tests → see error → fix → re-run → success. The user watches this happen in real-time without pressing send each time.

### Current State
Synapse handles tool calls in `_handle_tool_calls()` (main.py ~line 1300). After executing tools, it sends results back to the model as a follow-up message. But this is **single-round** — the model responds once after tools, then stops. The user must manually send again for another iteration.

### Implementation

#### 1a. Create `synapse/core/agentic.py` — Agentic Loop Controller
```python
"""
Agentic loop controller. Runs tool calls in a loop until the model
stops requesting tools or hits the iteration limit.

Usage from main.py:
    loop = AgenticLoop(model, messages, tools, settings, max_iterations=15)
    loop.token_received.connect(self._render_token)
    loop.tool_executing.connect(self._show_tool_progress)
    loop.iteration_complete.connect(self._on_iteration)
    loop.finished.connect(self._on_agentic_done)
    loop.start()
"""
import logging
from PyQt5.QtCore import QThread, pyqtSignal

log = logging.getLogger(__name__)

class AgenticLoop(QThread):
    # Signals
    token_received = pyqtSignal(str)           # Streaming tokens from model
    tool_executing = pyqtSignal(str, dict)     # tool_name, args — for progress UI
    tool_result = pyqtSignal(str, str)         # tool_name, result — for display
    iteration_complete = pyqtSignal(int, str)  # iteration_number, summary
    finished = pyqtSignal(str, list, dict)     # final_text, all_messages, stats
    error_occurred = pyqtSignal(str)
    permission_requested = pyqtSignal(str, str, dict, int)  # tool_name, description, args, request_id

    def __init__(self, model, messages, system_prompt, tools, agent, mcp_manager,
                 settings, gen_params, max_iterations=15):
        super().__init__()
        self.model = model
        self.messages = list(messages)  # Copy
        self.system_prompt = system_prompt
        self.tools = tools
        self.agent = agent
        self.mcp_manager = mcp_manager
        self.settings = settings
        self.gen_params = gen_params
        self.max_iterations = max_iterations
        self._stop = False
        self._permission_responses = {}  # request_id -> bool
        self._iteration = 0

        # Tools that are always auto-approved (read-only)
        self.auto_approve = {
            "read_file", "web_search", "scrape_url",
            "execute_python", "run_test"
        }
        # Tools that need user approval (destructive)
        self.needs_approval = {
            "write_file", "run_command", "git_commit"
        }

    def stop(self):
        self._stop = True

    def approve_tool(self, request_id, approved):
        self._permission_responses[request_id] = approved

    def run(self):
        """Main agentic loop — runs in background thread."""
        try:
            from .api import WorkerFactory
            import queue, time

            all_text = ""

            for iteration in range(self.max_iterations):
                if self._stop:
                    break

                self._iteration = iteration

                # Create a synchronous worker call
                result_q = queue.Queue()
                tool_calls_q = queue.Queue()
                tokens_buf = []

                worker = WorkerFactory(
                    self.model, self.messages, self.system_prompt,
                    self.gen_params, settings=self.settings, tools=self.tools
                )

                # Collect tokens for streaming display
                worker.token_received.connect(lambda t: (tokens_buf.append(t), self.token_received.emit(t)))
                worker.tool_calls_received.connect(lambda tc: tool_calls_q.put(tc))
                worker.response_finished.connect(lambda text, stats: result_q.put(("done", text, stats)))
                worker.error_occurred.connect(lambda err: result_q.put(("error", err, {})))
                worker.start()

                # Wait for completion
                result_type, result_data, stats = result_q.get(timeout=300)

                if result_type == "error":
                    self.error_occurred.emit(result_data)
                    return

                full_text = result_data
                all_text = full_text

                # Check if model made tool calls
                if tool_calls_q.empty():
                    # No tool calls — model is done, agentic loop ends
                    self.finished.emit(full_text, self.messages, stats)
                    return

                # Process tool calls
                tool_calls = tool_calls_q.get()

                # Add assistant message with tool calls to history
                self.messages.append({
                    "role": "assistant",
                    "content": full_text,
                    "tool_calls": tool_calls
                })

                # Execute each tool call
                tool_results = []
                for call in tool_calls:
                    name = call.get("function", {}).get("name", "")
                    args = call.get("function", {}).get("arguments", {})

                    self.tool_executing.emit(name, args)

                    # Permission check for destructive tools
                    # (For now, auto-approve all — Phase 1b adds permission UI)

                    # Execute via agent or MCP
                    if name.startswith("mcp__"):
                        result = self.mcp_manager.execute_tool(name, args)
                    else:
                        result = self.agent.execute(name, args)

                    self.tool_result.emit(name, str(result)[:500])
                    tool_results.append({
                        "tool_call_id": call.get("id", ""),
                        "name": name,
                        "content": str(result)
                    })

                # Add tool results to messages
                self.messages.append({
                    "role": "tool_results",
                    "content": tool_results
                })

                self.iteration_complete.emit(iteration + 1, f"Executed {len(tool_calls)} tools")

                # Loop continues — model will see tool results and decide next action

            # Hit max iterations
            self.finished.emit(all_text, self.messages, {"max_iterations": True})

        except Exception as e:
            log.error(f"Agentic loop error: {e}")
            self.error_occurred.emit(str(e))
```

#### 1b. Wire into `main.py` — Add Agent Mode Toggle
In `InputWidget` (input.py), add an "Agent Mode" toggle button next to the send button:
```python
# In InputWidget.__init__:
self.agent_mode_btn = QPushButton("⚡")
self.agent_mode_btn.setCheckable(True)
self.agent_mode_btn.setToolTip("Agent Mode: AI autonomously uses tools in a loop")
self.agent_mode_btn.setFixedSize(32, 32)
# Add to button_layout next to send_btn
```

In `MainWindow._send_message()`, check agent mode:
```python
if self.input_widget.agent_mode_btn.isChecked():
    self._run_agentic(conv, messages, tools)
else:
    # Existing single-shot flow
    ...

def _run_agentic(self, conv, messages, tools):
    from synapse.core.agentic import AgenticLoop
    self._agentic_loop = AgenticLoop(
        model=self.model_combo.currentText(),
        messages=messages,
        system_prompt=self._get_system_prompt(),
        tools=tools,
        agent=self.agent,
        mcp_manager=self.mcp_manager,
        settings=self.settings_data,
        gen_params=self.settings_data.get("gen_params", DEFAULT_GEN_PARAMS)
    )
    self._agentic_loop.token_received.connect(self._render_token)
    self._agentic_loop.tool_executing.connect(self._show_tool_executing)
    self._agentic_loop.tool_result.connect(self._show_tool_result)
    self._agentic_loop.iteration_complete.connect(self._on_agentic_iteration)
    self._agentic_loop.finished.connect(self._on_agentic_done)
    self._agentic_loop.error_occurred.connect(self._on_error)
    self._agentic_loop.start()
    self.input_widget.set_streaming(True)
```

#### 1c. Agentic Progress UI
Add a collapsible "Agent Activity" panel below the chat that shows:
```
Iteration 1:
  🔧 read_file("src/main.py") → 3551 lines
  🔧 read_file("src/input.py") → 838 lines
Iteration 2:
  ✏️ write_file("src/input.py") → Updated @mention handler
  ▶️ run_command("python -m pytest tests/") → 12 passed, 1 failed
Iteration 3:
  ✏️ write_file("src/input.py") → Fixed failing test
  ▶️ run_command("python -m pytest tests/") → 13 passed ✓
Done (3 iterations, 6 tool calls)
```

#### 1d. Permission System for Destructive Actions
When the agent wants to write a file or run a command, show an inline approval widget:
```
┌────────────────────────────────────────────────┐
│ ⚠️ Agent wants to: write_file("src/input.py")  │
│ Preview: +15 lines, -3 lines                   │
│ [Allow] [Allow All] [Deny] [View Diff]         │
└────────────────────────────────────────────────┘
```

Settings for permission levels:
- **Ask Always** — Approve every write/command (safest)
- **Auto-approve reads, ask for writes** — Default
- **YOLO Mode** — Auto-approve everything (power users)

Store in settings: `"agent_permission_level": "ask_writes"`

---

## Phase 2: Inline File Editing & Apply System

**Priority: HIGH**
**Files to modify:** `synapse/core/renderer.py`, `synapse/ui/main.py`, `synapse/ui/workspace.py`, `synapse/ui/diff_view.py`
**New file:** `synapse/core/file_applier.py`

### What Cursor Does
When AI generates a code block with a filename, there's an "Apply" button. Clicking it:
1. Opens a diff view showing current file vs proposed changes
2. User can accept/reject individual hunks
3. Changes are applied directly to the file on disk
4. Editor tab updates live

### Current State
Synapse already has:
- "Apply" and "Propose" buttons on code blocks (renderer.py action buttons)
- `action://applycode/N` and `action://proposecode/N` protocol handlers
- `DiffViewDialog` with accept/reject
- `EditorTabs` showing open files with syntax highlighting

But the current "Apply" button just copies to clipboard or opens the editor — it doesn't do smart file detection or diff-based application.

### Implementation

#### 2a. Create `synapse/core/file_applier.py` — Smart File Application
```python
"""
Detects target file from code block context and applies changes intelligently.

Strategies:
1. Filename in code fence: ```python:src/main.py
2. Filename in preceding text: "Update `src/main.py`:"
3. Filename in code comment: # file: src/main.py
4. Search-and-replace: If code block is a partial snippet, find the matching
   location in the file and replace just that section
5. Full file replacement: If code block appears to be a complete file
"""

class FileApplier:
    def __init__(self, workspace_path):
        self.workspace = workspace_path

    def detect_target_file(self, code_block, surrounding_text, language):
        """Return (filepath, confidence) or (None, 0)."""
        # Strategy 1: fence label  ```python:path/to/file.py
        # Strategy 2: text mentions "in `filename`" or "Update filename:"
        # Strategy 3: comment header
        # Strategy 4: search workspace for matching function/class names
        pass

    def compute_application(self, target_path, new_code, mode="smart"):
        """
        Returns an ApplicationPlan:
        - full_replace: Replace entire file content
        - patch: List of hunks [{start_line, end_line, old_text, new_text}]
        - insert: Insert at specific location
        """
        pass

    def apply(self, plan):
        """Execute the application plan, writing to disk."""
        pass
```

#### 2b. Enhanced Code Fence Detection in `renderer.py`
Update code block parsing to extract filename from fence:
```python
# Current: ```python
# New support: ```python:src/main.py or ```python src/main.py
# The filename gets stored in a data attribute on the code block div
# The "Apply" button reads this to know where to write
```

#### 2c. Hunk-Level Diff Accept/Reject
Upgrade `DiffViewDialog` to show individual hunks (like VS Code's inline diff):
```
┌─ src/input.py ─────────────────────────────────────┐
│ @@ -45,7 +45,12 @@ class InputWidget:                │
│   def __init__(self):                                │
│ -     self.completer = None                          │ [✓ Accept] [✗ Reject]
│ +     self.completer = FileCompleter()               │
│ +     self.completer.setModel(self._file_model)      │
│                                                      │
│ @@ -120,3 +125,8 @@ def _on_submit:                 │
│ -     pass                                           │ [✓ Accept] [✗ Reject]
│ +     self._apply_context_files()                    │
│ +     self.message_submitted.emit(text)              │
└──────────────────────────────────────────────────────┘
                              [Accept All] [Reject All]
```

#### 2d. Live Editor Sync
When a file is modified via Apply:
1. If file is open in EditorTabs → reload content, flash green briefly
2. If file is NOT open → open it in a new tab with the diff highlighted
3. Show a toast: "Applied changes to src/input.py (+15, -3 lines)"
4. Git panel auto-refreshes to show the modified file

---

## Phase 3: @ Context Mentions System

**Priority: HIGH**
**Files to modify:** `synapse/ui/input.py`, `synapse/ui/main.py`
**New file:** `synapse/core/context_provider.py`

### What Cursor Does
Users type `@filename.py` to include a file's content in the prompt. Also supports:
- `@folder/` — include all files in folder
- `@codebase` — semantic search across entire repo
- `@docs` — search documentation
- `@web` — search the web
- `@git` — include recent git changes
- `@terminal` — include terminal output
- `@selection` — include currently selected code in editor

### Current State
Synapse already has `@` mention detection in `input.py` (lines ~240-260) with a `_FileCompleter` that shows workspace files. But it only inserts the filename text — it doesn't actually inject file content into the prompt.

### Implementation

#### 3a. Create `synapse/core/context_provider.py`
```python
"""
Resolves @ mentions into context that gets injected into the prompt.

Each provider returns: {type, name, content, token_estimate}
"""

class ContextProvider:
    def __init__(self, workspace_path, indexer, git_module):
        self.workspace = workspace_path
        self.indexer = indexer
        self.git = git_module
        self.providers = {
            "file": self._resolve_file,       # @src/main.py
            "folder": self._resolve_folder,    # @src/core/
            "codebase": self._resolve_codebase,# @codebase query
            "git": self._resolve_git,          # @git (recent changes)
            "terminal": self._resolve_terminal,# @terminal (last output)
            "web": self._resolve_web,          # @web search query
            "docs": self._resolve_docs,        # @docs search query
            "selection": self._resolve_selection,# @selection (editor selection)
            "diff": self._resolve_diff,        # @diff (uncommitted changes)
            "errors": self._resolve_errors,    # @errors (terminal errors)
        }

    def resolve(self, mention_text):
        """Parse @mention and return context dict."""
        # @src/main.py → file provider
        # @codebase how does auth work → codebase provider
        # @git → git provider
        pass

    def _resolve_file(self, path):
        """Read file content, return with line numbers."""
        pass

    def _resolve_folder(self, path):
        """Read all files in folder (up to token limit), return concatenated."""
        pass

    def _resolve_codebase(self, query):
        """Use RAG/embeddings to find relevant code chunks."""
        pass

    def _resolve_git(self, args):
        """Return git diff, recent commits, or specific commit."""
        pass

    def _resolve_terminal(self, args):
        """Return last N lines of terminal output."""
        pass
```

#### 3b. Update `input.py` — Rich @ Mention Completer
Replace the simple `_FileCompleter` with a multi-type completer:
```
Typing "@" shows:
┌────────────────────────────────────┐
│ 📁 Files                           │
│   src/main.py                      │
│   src/input.py                     │
│   src/core/api.py                  │
│ 📂 Folders                          │
│   src/core/                        │
│   src/ui/                          │
│ 🔍 Special                          │
│   @codebase — Search entire repo   │
│   @git — Recent changes            │
│   @terminal — Terminal output      │
│   @web — Web search                │
│   @diff — Uncommitted changes      │
│   @errors — Recent errors          │
│   @selection — Editor selection    │
└────────────────────────────────────┘
```

#### 3c. Context Injection in `_send_message()`
Before sending to the model, resolve all @ mentions:
```python
def _send_message(self, text, images=None, files=None):
    # Extract @ mentions from text
    mentions = re.findall(r'@(\S+)', text)
    context_blocks = []
    for mention in mentions:
        ctx = self.context_provider.resolve(mention)
        if ctx:
            context_blocks.append(ctx)

    # Build augmented message
    if context_blocks:
        context_text = "\n\n".join(
            f"<context name=\"{c['name']}\">\n{c['content']}\n</context>"
            for c in context_blocks
        )
        augmented = f"{context_text}\n\n{text}"
    else:
        augmented = text
```

#### 3d. Context Token Counter
Show token usage of attached context in the input area:
```
[@src/main.py 3.2k] [@src/core/ 8.1k] [@git 0.4k]  ← chips showing token cost
Total context: 11.7k / 32k tokens
```

---

## Phase 4: Integrated Terminal with AI Awareness

**Priority: HIGH**
**Files to modify:** `synapse/ui/terminal.py`, `synapse/ui/main.py`

### Current State
`terminal.py` exists but is basic. Need a full PTY-based terminal that:
1. AI can read output from
2. AI can write commands to
3. Shows in a panel (like VS Code's integrated terminal)
4. Supports `@terminal` context mention

### Implementation

#### 4a. Upgrade `terminal.py` — Full PTY Terminal
```python
"""
Full PTY terminal using QProcess or pty module.
Captures all output in a ring buffer for AI context injection.
"""
import pty, os, select
from PyQt5.QtWidgets import QPlainTextEdit
from PyQt5.QtCore import QThread, pyqtSignal

class TerminalWidget(QPlainTextEdit):
    command_finished = pyqtSignal(str, str, int)  # command, output, exit_code
    output_received = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._output_buffer = []  # Ring buffer, last 10000 lines
        self._history = []        # Command history
        self._current_command = ""
        # Fork PTY
        # Read loop in QThread
        # Keyboard input → write to PTY

    def run_command(self, cmd):
        """Programmatically run a command (called by AI agent)."""
        pass

    def get_recent_output(self, lines=100):
        """Return last N lines for @terminal context."""
        pass

    def get_last_error(self):
        """Parse output for error patterns, return error context."""
        pass
```

#### 4b. AI Terminal Commands
Add a tool to `agent.py`:
```python
registry.register("terminal_run", {
    "type": "function",
    "function": {
        "name": "terminal_run",
        "description": "Run a shell command in the integrated terminal and see the output",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "wait": {"type": "boolean", "description": "Wait for completion", "default": True}
            },
            "required": ["command"]
        }
    }
})
```

#### 4c. Error Detection & Auto-Fix Loop
Terminal watches for error patterns:
```python
ERROR_PATTERNS = [
    r"Traceback \(most recent call last\)",
    r"error\[E\d+\]",           # Rust
    r"ERROR in .+",              # Webpack
    r"FAILED .+",                # pytest
    r"error TS\d+:",             # TypeScript
    r"SyntaxError:",             # Python/JS
    r"ModuleNotFoundError:",     # Python
]
```
When detected, show: "Terminal error detected. [Ask AI to fix] [Ignore]"

Clicking "Ask AI to fix" sends:
```
@terminal
@errors

Fix the error shown in the terminal output above.
```

---

## Phase 5: Multi-File Editing & Refactoring

**Priority: HIGH**
**Files to modify:** `synapse/core/agent.py`, `synapse/ui/main.py`, `synapse/ui/diff_view.py`
**New file:** `synapse/core/multi_edit.py`

### What Cursor Does
AI can propose changes to multiple files in a single response. Shows a "Changes" panel listing all modified files with diffs. User reviews and accepts/rejects per-file.

### Implementation

#### 5a. Create `synapse/core/multi_edit.py`
```python
"""
Tracks multiple file edits from a single AI response.
Presents them as a unified changeset for review.
"""

class EditPlan:
    def __init__(self):
        self.edits = []  # [{path, old_content, new_content, hunks}]

    def add_edit(self, path, old_content, new_content):
        pass

    def get_summary(self):
        """Return: 3 files changed, +45 -12 lines"""
        pass

class MultiEditManager:
    def __init__(self, workspace_path):
        self.workspace = workspace_path
        self.pending_plan = None

    def parse_response(self, ai_text):
        """
        Extract all code blocks with file targets from AI response.
        Build an EditPlan.
        """
        pass

    def show_review(self, plan):
        """Open the multi-file review dialog."""
        pass

    def apply_plan(self, plan, accepted_files):
        """Apply accepted edits to disk."""
        pass
```

#### 5b. Changes Panel (like VS Code Source Control)
New sidebar panel showing pending AI changes:
```
┌─ Changes (3 files) ──────────────────┐
│ ✅ src/main.py        +12 -3         │
│ ✅ src/input.py       +45 -8         │
│ ❌ src/test_input.py  +22 -0         │
│                                       │
│ [Apply Selected] [Discard All]        │
└───────────────────────────────────────┘
```

Click a file → opens DiffViewDialog for that file.

#### 5c. Search-and-Replace Edits
For partial code blocks (snippets, not full files), implement intelligent matching:
```python
def find_edit_location(self, filepath, snippet):
    """
    Given a code snippet from AI, find where it belongs in the file.
    Uses:
    1. Function/class name matching
    2. Surrounding context lines
    3. Fuzzy line matching (difflib.SequenceMatcher)
    """
    pass
```

This is critical — Cursor's "Apply" works even when the AI outputs partial files with `// ... existing code ...` markers.

---

## Phase 6: LSP Integration (Language Intelligence)

**Priority: MEDIUM-HIGH**
**New files:** `synapse/core/lsp_client.py`, `synapse/ui/diagnostics_panel.py`

### What This Enables
- Red squiggles on errors in the editor
- Go to definition, find references
- Hover documentation
- Auto-import suggestions
- AI sees diagnostics and can auto-fix

### Implementation

#### 6a. Create `synapse/core/lsp_client.py`
```python
"""
Generic LSP client that can connect to any language server.
Manages lifecycle, sends/receives JSON-RPC over stdio.

Supported servers (auto-detected from workspace):
- Python: pyright, pylsp
- JavaScript/TypeScript: typescript-language-server
- Rust: rust-analyzer
- Go: gopls
- C/C++: clangd
"""

class LSPClient:
    def __init__(self, language, server_command, workspace_path):
        pass

    def initialize(self):
        """Send initialize request, negotiate capabilities."""
        pass

    def did_open(self, filepath, content):
        """Notify server of opened file."""
        pass

    def did_change(self, filepath, changes):
        """Notify server of edits."""
        pass

    def get_diagnostics(self, filepath):
        """Return list of errors/warnings."""
        pass

    def goto_definition(self, filepath, line, col):
        """Return definition location."""
        pass

    def find_references(self, filepath, line, col):
        """Return all references."""
        pass

    def completions(self, filepath, line, col):
        """Return completion items."""
        pass

    def hover(self, filepath, line, col):
        """Return hover documentation."""
        pass
```

#### 6b. Create `synapse/ui/diagnostics_panel.py`
```
Problems panel (like VS Code):
┌─ Problems (12) ──────────────────────────────────┐
│ ❌ src/main.py:145 — Undefined variable 'foo'     │
│ ❌ src/api.py:89 — Missing return type annotation │
│ ⚠️ src/utils.py:23 — Unused import 'os'           │
│                                                    │
│ [AI: Fix All] [AI: Fix Selected]                   │
└────────────────────────────────────────────────────┘
```

"AI: Fix All" sends all diagnostics to the model with file context, asks for fixes, applies via multi-edit system.

#### 6c. Editor Integration
In `editor.py`, add:
- Red underlines for errors, yellow for warnings
- Hover tooltip showing diagnostic message
- Ctrl+Click → go to definition
- F2 → rename symbol (via LSP rename)
- Ctrl+Space → completions popup

---

## Phase 7: Codebase-Wide Semantic Search

**Priority: MEDIUM-HIGH**
**Files to modify:** `synapse/core/indexer.py`, `synapse/core/graph_rag.py`
**New file:** `synapse/core/code_intelligence.py`

### Current State
Synapse has workspace indexing (chunking + embeddings via `nomic-embed-text`) and graph RAG. But it's designed for document search, not code-aware search.

### Implementation

#### 7a. Create `synapse/core/code_intelligence.py`
```python
"""
Code-aware indexing that understands:
- Function/class/method boundaries
- Import relationships
- Call graphs
- Type hierarchies
- Module dependencies
"""

class CodeIntelligence:
    def __init__(self, workspace_path):
        self.workspace = workspace_path
        self.symbols = {}      # {filepath: [Symbol]}
        self.references = {}   # {symbol_id: [Location]}
        self.imports = {}      # {filepath: [import_path]}

    def index_workspace(self):
        """
        Parse all source files using tree-sitter or ast module.
        Build symbol table and reference graph.
        """
        pass

    def search(self, query, mode="semantic"):
        """
        Modes:
        - "semantic": Embedding-based similarity (existing)
        - "symbol": Exact symbol name search
        - "grep": Regex text search across files
        - "definition": Find where symbol is defined
        - "references": Find all usages of symbol
        - "related": Find files related to a concept
        """
        pass

    def get_context_for_file(self, filepath, max_tokens=4000):
        """
        Get the most relevant context for editing a file:
        - The file itself
        - Files that import it
        - Files it imports
        - Files with related symbols
        Prioritize by relevance, fit within token budget.
        """
        pass
```

#### 7b. Upgrade `@codebase` Provider
When user types `@codebase how does authentication work`:
1. Embed the query
2. Search symbol table for auth-related functions
3. Search vector index for relevant chunks
4. Traverse import graph from matching files
5. Return ranked, deduplicated context within token budget

---

## Phase 8: Project-Aware Context & Rules

**Priority: MEDIUM**
**New file:** `synapse/core/project_rules.py`

### What Cursor Does
Cursor reads `.cursorrules` files and includes them in every prompt. This lets users define coding standards, preferred libraries, architectural patterns.

### Implementation

#### 8a. Create `synapse/core/project_rules.py`
```python
"""
Reads project rules from multiple sources and injects into system prompt:
- .synapse/rules.md (project-level rules)
- .synapse/context.md (always-included context)
- .cursorrules (Cursor compatibility)
- .github/copilot-instructions.md (Copilot compatibility)
- CLAUDE.md (Claude Code compatibility)
"""

class ProjectRules:
    RULE_FILES = [
        ".synapse/rules.md",
        ".synapse/context.md",
        ".cursorrules",
        ".cursorules",
        ".github/copilot-instructions.md",
        "CLAUDE.md",
    ]

    def __init__(self, workspace_path):
        self.workspace = workspace_path

    def get_rules(self):
        """Read and concatenate all rule files found in workspace."""
        pass

    def get_file_rules(self, filepath):
        """
        Get rules specific to a file type or directory.
        .synapse/rules/python.md → applies to *.py files
        .synapse/rules/tests.md → applies to test_*.py files
        """
        pass
```

#### 8b. Auto-inject into System Prompt
In `main.py._get_system_prompt()`:
```python
def _get_system_prompt(self):
    base = self.settings_data.get("system_prompt", "")
    if self.workspace_path:
        rules = self.project_rules.get_rules()
        if rules:
            base = f"{rules}\n\n{base}"
    return base
```

#### 8c. Rules Editor UI
Add a "Project Rules" section in settings or a dedicated sidebar:
```
┌─ Project Rules ──────────────────────────┐
│ .synapse/rules.md                        │
│ ┌──────────────────────────────────────┐ │
│ │ Always use TypeScript strict mode.   │ │
│ │ Prefer functional components.        │ │
│ │ Use Tailwind CSS, never inline CSS.  │ │
│ │ Write tests for all new functions.   │ │
│ └──────────────────────────────────────┘ │
│ [Save] [Generate from Codebase]          │
└──────────────────────────────────────────┘
```

"Generate from Codebase" button asks AI to analyze the project and suggest rules.

---

## Phase 9: AI-Powered Code Completion (Tab Autocomplete)

**Priority: MEDIUM**
**New files:** `synapse/core/completion_engine.py`, `synapse/ui/completion_popup.py`

### What Cursor Does
As you type code, ghost text appears showing AI-predicted completions. Press Tab to accept.

### Implementation

#### 9a. Create `synapse/core/completion_engine.py`
```python
"""
Code completion using fill-in-the-middle (FIM) models.
Ollama supports FIM via /api/generate with suffix parameter.

Compatible models:
- codellama (any size)
- deepseek-coder
- starcoder2
- qwen2.5-coder
"""

class CompletionEngine:
    def __init__(self, model="qwen2.5-coder:1.5b", ollama_url="http://localhost:11434"):
        self.model = model
        self.url = ollama_url
        self._debounce_ms = 300
        self._cache = {}  # (prefix_hash, suffix_hash) -> completion

    def get_completion(self, prefix, suffix, filepath=None, language=None):
        """
        Send FIM request to Ollama:
        POST /api/generate
        {
            "model": "qwen2.5-coder:1.5b",
            "prompt": prefix,
            "suffix": suffix,
            "stream": false,
            "options": {"temperature": 0.1, "num_predict": 100}
        }
        """
        pass

    def get_multi_line_completion(self, context_before, context_after, indent_level):
        """Generate multi-line completion (function body, etc.)."""
        pass
```

#### 9b. Ghost Text in Editor
In `editor.py`, add ghost text rendering:
```python
class CodeEditor(QPlainTextEdit):
    def __init__(self):
        self._ghost_text = ""
        self._ghost_position = None
        self._completion_timer = QTimer()
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._request_completion)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab and self._ghost_text:
            self._accept_ghost()
            return
        if event.key() == Qt.Key_Escape:
            self._ghost_text = ""
            self.viewport().update()
            return
        super().keyPressEvent(event)
        self._completion_timer.start(300)  # Debounce 300ms

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._ghost_text:
            # Paint ghost text in gray after cursor
            pass
```

#### 9c. Settings
```json
{
    "completion_enabled": true,
    "completion_model": "qwen2.5-coder:1.5b",
    "completion_debounce_ms": 300,
    "completion_max_tokens": 100
}
```

Small FIM model (1.5B) runs concurrently with the main chat model on Ollama. Fast enough for real-time completions.

---

## Phase 10: Debugging Integration

**Priority: MEDIUM**
**New files:** `synapse/core/debugger.py`, `synapse/ui/debug_panel.py`

### Implementation

#### 10a. Create `synapse/core/debugger.py`
```python
"""
Debug Adapter Protocol (DAP) client.
Connects to debugpy (Python), node-debug (JS), codelldb (Rust/C++).

Provides:
- Set breakpoints
- Step over/into/out
- Inspect variables
- Evaluate expressions
- Call stack visualization
"""

class DebugAdapter:
    def __init__(self, adapter_type="python"):
        pass

    def launch(self, program, args=None, env=None):
        pass

    def attach(self, pid=None, port=None):
        pass

    def set_breakpoint(self, filepath, line):
        pass

    def continue_(self):
        pass

    def step_over(self):
        pass

    def step_into(self):
        pass

    def get_variables(self, scope="local"):
        pass

    def evaluate(self, expression):
        pass
```

#### 10b. Debug Panel UI
```
┌─ Debug ──────────────────────────────────┐
│ ▶️ Launch  ⏸ Pause  ⏹ Stop  ⏭ Step Over │
│                                           │
│ 📍 Breakpoints:                           │
│   src/main.py:145                         │
│   src/api.py:89                           │
│                                           │
│ 📊 Variables:                              │
│   response = {"status": 200, ...}         │
│   messages = [3 items]                    │
│     ├── [0]: {"role": "user", ...}        │
│     ├── [1]: {"role": "assistant", ...}   │
│     └── [2]: {"role": "user", ...}        │
│                                           │
│ 📚 Call Stack:                             │
│   _send_message (main.py:450)             │
│   _handle_submit (main.py:380)            │
│   keyPressEvent (input.py:210)            │
│                                           │
│ 💬 AI: "The response object is missing    │
│   the 'content' field. This happens when  │
│   the API returns a tool_call instead..." │
└───────────────────────────────────────────┘
```

"AI" section auto-analyzes current debug state and explains what's happening.

---

## Phase 11: Test Runner & Coverage

**Priority: MEDIUM**
**New files:** `synapse/core/test_runner.py`, `synapse/ui/test_panel.py`

### Implementation

#### 11a. Create `synapse/core/test_runner.py`
```python
"""
Detects and runs tests across frameworks:
- pytest (Python)
- jest/vitest (JavaScript)
- cargo test (Rust)
- go test (Go)

Parses output into structured results.
Generates coverage reports.
"""

class TestRunner:
    def detect_framework(self, workspace_path):
        """Auto-detect test framework from config files."""
        # pytest.ini, setup.cfg, pyproject.toml → pytest
        # package.json with jest/vitest → jest/vitest
        # Cargo.toml → cargo test
        # go.mod → go test
        pass

    def run_tests(self, filepath=None, test_name=None):
        """
        Run tests. If filepath given, run only that file.
        If test_name given, run only that test.
        Returns TestResults with pass/fail/error per test.
        """
        pass

    def run_coverage(self):
        """Run with coverage and return per-file/line coverage data."""
        pass
```

#### 11b. Test Panel UI
```
┌─ Tests ──────────────────────────────────┐
│ ▶️ Run All  ▶️ Run File  🔄 Watch Mode    │
│                                           │
│ ✅ test_api.py (5/5 passed)               │
│   ✅ test_connection                      │
│   ✅ test_streaming                       │
│   ✅ test_tool_calls                      │
│   ✅ test_error_handling                  │
│   ✅ test_retry_logic                     │
│                                           │
│ ❌ test_input.py (3/4 passed, 1 failed)   │
│   ✅ test_submit                          │
│   ✅ test_at_mention                      │
│   ❌ test_file_attach — AssertionError    │
│      Expected: 5 files                    │
│      Got: 4 files                         │
│      [AI: Fix This Test]                  │
│   ✅ test_slash_command                   │
│                                           │
│ Coverage: 78% (target: 80%)              │
└───────────────────────────────────────────┘
```

"AI: Fix This Test" sends the test code + error + source code to the agent.

#### 11c. Coverage Gutters
In `editor.py`, show coverage in the gutter:
- Green line = covered
- Red line = not covered
- Yellow line = partially covered (branches)

---

## Phase 12: Build System & Task Runner

**Priority: MEDIUM-LOW**
**New file:** `synapse/core/build_system.py`

### Implementation

#### 12a. Auto-detect build system
```python
"""
Detects and integrates with project build systems:
- Makefile → make targets
- package.json → npm scripts
- pyproject.toml → poetry/pip scripts
- Cargo.toml → cargo commands
- CMakeLists.txt → cmake targets
- docker-compose.yml → docker services
"""

class BuildSystem:
    def detect(self, workspace_path):
        """Return list of available tasks/scripts."""
        pass

    def run_task(self, task_name):
        """Execute in terminal, capture output."""
        pass
```

#### 12b. Tasks Panel
Sidebar showing available tasks:
```
┌─ Tasks ──────────────────────────────────┐
│ npm scripts:                              │
│   ▶️ dev — next dev                       │
│   ▶️ build — next build                   │
│   ▶️ test — jest --watchAll               │
│   ▶️ lint — eslint .                      │
│                                           │
│ Makefile:                                 │
│   ▶️ all                                  │
│   ▶️ clean                                │
│   ▶️ install                              │
│                                           │
│ Docker:                                   │
│   ▶️ up — docker-compose up               │
│   ▶️ down — docker-compose down           │
└───────────────────────────────────────────┘
```

---

## Phase 13: GitHub/GitLab Deep Integration

**Priority: MEDIUM-LOW**
**New file:** `synapse/core/github_integration.py`, `synapse/ui/pr_panel.py`

### Implementation

#### 13a. PR Creation from Chat
After the AI makes changes via agentic loop:
```
"Create a PR for these changes" →
1. Auto-create branch (feature/fix-auth-middleware)
2. Commit all AI-modified files with descriptive message
3. Push to remote
4. Create PR with AI-generated description
5. Show PR link in chat
```

#### 13b. PR Review Assistant
```
"Review PR #42" →
1. Fetch PR diff via GitHub API
2. Analyze changes file by file
3. Show inline comments with suggestions
4. Option to submit review comments directly
```

#### 13c. Issue → Implementation Flow
```
"Implement issue #15" →
1. Fetch issue description
2. Analyze codebase for relevant files
3. Create implementation plan
4. Enter agentic loop to implement
5. Run tests
6. Create PR referencing the issue
```

---

## Phase 14: Docker & Dev Container Support

**Priority: LOW**
**New file:** `synapse/core/containers.py`

### Implementation
```python
"""
Manage development containers:
- Read .devcontainer/devcontainer.json
- Docker Compose integration
- Container terminal access
- Forward ports for preview
"""
```

---

## Phase 15: Notebook / REPL Integration

**Priority: LOW**
**New file:** `synapse/ui/notebook.py`

### Implementation
Jupyter-style notebook cells in the editor:
- Code cells with inline output
- Markdown cells
- Plot rendering inline
- Variable inspector
- AI can create/modify notebook cells

---

## Phase 16: Plugin/Extension System

**Priority: LOW**
**New file:** `synapse/core/plugin_system.py`

### Implementation
```python
"""
Allow third-party extensions:
- Python plugins in ~/.synapse/extensions/
- Each plugin: manifest.json + main.py
- Can register: tools, sidebar panels, commands, keybindings
- Hot-reload support
"""
```

---

## Implementation Order & Dependencies

```
Phase 1: Agentic Loop ←── FOUNDATION (everything else builds on this)
  │
  ├── Phase 2: File Apply System (needs agentic for auto-apply)
  │     └── Phase 5: Multi-File Editing (extends apply system)
  │
  ├── Phase 3: @ Context Mentions (standalone, high impact)
  │     └── Phase 7: Semantic Search (enhances @codebase)
  │
  ├── Phase 4: Terminal Integration (standalone, high impact)
  │     └── Phase 12: Build System (uses terminal)
  │
  ├── Phase 8: Project Rules (standalone, easy win)
  │
  ├── Phase 6: LSP Integration (standalone, complex)
  │     ├── Phase 9: Tab Autocomplete (can use LSP completions)
  │     └── Phase 10: Debugging (similar DAP protocol)
  │
  ├── Phase 11: Test Runner (uses terminal + agentic)
  │
  ├── Phase 13: GitHub Integration (uses agentic + multi-edit)
  │
  └── Phase 14-16: Lower priority extensions
```

## Estimated Scope

| Phase | New Lines | Modified Lines | New Files | Difficulty |
|-------|-----------|---------------|-----------|------------|
| 1. Agentic Loop | ~400 | ~200 | 1 | Medium |
| 2. File Apply | ~500 | ~150 | 1 | Medium |
| 3. @ Context | ~350 | ~200 | 1 | Medium |
| 4. Terminal | ~400 | ~100 | 0 (upgrade) | Medium |
| 5. Multi-File Edit | ~450 | ~150 | 1 | Medium-Hard |
| 6. LSP | ~600 | ~200 | 2 | Hard |
| 7. Semantic Search | ~400 | ~200 | 1 | Medium |
| 8. Project Rules | ~200 | ~50 | 1 | Easy |
| 9. Tab Autocomplete | ~500 | ~200 | 2 | Hard |
| 10. Debugging | ~700 | ~100 | 2 | Hard |
| 11. Test Runner | ~400 | ~100 | 2 | Medium |
| 12. Build System | ~250 | ~50 | 1 | Easy |
| 13. GitHub | ~500 | ~100 | 2 | Medium |
| 14. Containers | ~300 | ~50 | 1 | Medium |
| 15. Notebooks | ~500 | ~100 | 1 | Medium |
| 16. Plugins | ~400 | ~100 | 1 | Hard |
| **Total** | **~6,850** | **~2,050** | **18** | |

## Critical Rules for Implementation

1. **NEVER break existing functionality** — always run the verify command after changes
2. **Follow existing patterns** — use QThread + pyqtSignal for async, `action://` protocol for HTML interactions
3. **Theme-aware** — all new UI must have `apply_theme(theme_dict)` method
4. **Settings integration** — all new features must be toggleable in settings
5. **Keyboard shortcuts** — every new panel/action needs a shortcut in DEFAULT_SHORTCUTS
6. **Command palette** — every new action must be registered in the command palette
7. **Activity bar** — new panels get an icon in the activity bar
8. **Error handling** — never crash the UI; catch exceptions, show user-friendly messages
9. **Memory efficient** — use ring buffers for logs/output, don't accumulate unbounded data
10. **Cross-platform** — test on Linux (primary), consider macOS/Windows paths
