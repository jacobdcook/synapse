# Synapse — Work Sessions

**Each session = maximum context window usage.** One paste into a new Cursor composer. Let it run until it says DONE or hits the limit. Do NOT prompt again until it finishes or stalls.

**Rules:**
- Copy the FULL session prompt. Do not truncate.
- The AI must complete EVERY numbered item. No skipping.
- If it finishes early, it missed items. Tell it to re-read the prompt.
- Run the test prompt at the end to verify.

**Testing cadence:**
- Per-section: Create `tests/test_*.py` when the session explicitly asks for it (e.g. "Create tests/test_X.py").
- End of session: Run all tests (`python -m pytest tests/ -v` or `python -c "from tests.test_X import *; ..."` if no pytest) and fix failures before marking DONE.
- After multi-session work: Run full test suite and fix regressions before starting the next session.

---

# SESSION 1 (Day 1 — DONE)
Context management, summarizer, deep research. Already implemented.

---

# SESSION 2

Copy everything between the triple-backtick fences below into a **new** Cursor composer session.

```
You are working on Synapse, a PyQt5 AI desktop app at /home/z1337/Desktop/PROJECTS/Synapse. Complete EVERY item below. Do not stop until all items are done. Mark each section DONE as you finish it.

=== A. TOOL AUDIT SYSTEM (synapse/core/tool_audit.py) ===
1. Create tool_audit.py with ToolAuditLog class:
   - __init__(log_path=CONFIG_DIR / "tool_audit.jsonl")
   - log_call(tool_name, arguments, result, duration_ms, success, error=None): append JSON line with timestamp, tool_name, args (truncated 500), result (truncated 500), duration_ms, success, error
   - get_recent(limit=50): read last N entries
   - get_stats(): per-tool counts, success rates, avg duration
   - rotate(): if file > 10MB, rotate to .1.jsonl (keep max 3)
   - Full typing, docstrings, error handling

2. In agent.py ToolExecutor, wrap EVERY tool call:
   - try/except with timing (time.time before/after)
   - Log to ToolAuditLog on every call
   - After write_file: read back, compare hash, if mismatch add "[VERIFICATION WARNING]"
   - After run_command: if exit code != 0, add "[WARNING: exit code N]"
   - After web_search/scrape_url: if empty result, add "[WARNING: empty result]"
   - Retry web_search/scrape_url 2x on network error (1s delay)
   - Retry write_file 1x on verification failure

3. Create tests/test_tool_audit.py: log/read/rotate/stats tests

=== B. EPISODIC MEMORY (synapse/core/episodic_memory.py) ===
4. Create episodic_memory.py:
   - SQLite at CONFIG_DIR / "episodic.db"
   - Schema: episodes(id, conversation_id, turn_index, timestamp, role, topic, key_facts JSON, outcome, tools_used JSON, sentiment)
   - Indexes on conversation_id, topic, timestamp
   - EpisodicMemory class:
     a. log_episode(conv_id, turn_idx, role, topic, key_facts, outcome, tools_used, sentiment)
     b. query_recent(conv_id=None, limit=20)
     c. query_by_topic(keywords, limit=10) — FTS5 search
     d. get_conversation_summary(conv_id) — one-paragraph summary
     e. get_user_patterns() — most asked topics, preferred tools, frustrations
     f. cleanup(days=90)
   - Thread-safe: one connection per thread (threading.local)
   - Graceful degradation if DB locked

5. Integrate into main.py:
   - After each assistant response: log episode (topic from first user msg, outcome, tools used)
   - Before sending message: query by topic, prepend "[Memory: ...]" to system prompt (max 3 memories, 500 tokens)

6. Create synapse/ui/memory_sidebar.py:
   - QWidget for the sidebar
   - Recent episodes grouped by conversation
   - Search bar (QLineEdit) connected to query_by_topic
   - "User Patterns" section with get_user_patterns()
   - "Clear Memory" button with QMessageBox confirm
   - Add to activity bar in main.py

7. Create tests/test_episodic_memory.py: CRUD, FTS, patterns, cleanup

=== C. AGENTIC LOOP V2 (synapse/core/agentic.py) ===
8. Add PLANNING phase:
   - If task complex (msg > 500 chars, or contains "refactor"/"build"/"implement"/"create"/"fix all"):
     send planning prompt, parse numbered steps, store _plan, emit plan_created(str) signal
   - Add plan_created = pyqtSignal(str) to signals

9. Add REFLECTION every 3 iterations:
   - Inject "Review progress. What's done? Remaining? Issues?" as user message
   - Parse response, emit reflection(str) signal
   - Add reflection = pyqtSignal(str) to signals

10. Add SELF-CORRECTION:
    - Track last tool call (name + args hash). If same twice in a row, inject warning
    - If 3 consecutive failures, inject "Stop and explain what's going wrong"

11. Add PROGRESS:
    - After each tool, if plan exists, emit progress(int, int, str) signal
    - Add progress = pyqtSignal(int, int, str) to signals

12. In main.py:
    - Connect plan_created: inject collapsible plan HTML into chat via JS
    - Connect reflection: inject subtle collapsed reflection
    - Connect progress: update status label "Step 3/7: Reading files..."

13. In tool_approval.py: show plan step context "Step 3/7: [description]"

14. Create tests/test_agentic_v2.py: planning heuristic, reflection timing, duplicate detection

=== D. PARALLEL TOOL EXECUTION (synapse/core/tool_orchestrator.py) ===
15. Create tool_orchestrator.py:
    - ToolOrchestrator: analyze dependencies, group independent calls, execute batches in parallel via QThreadPool
    - DependencyAnalyzer: DAG, topological sort
    - Timeout per call 30s, per batch 60s
    - Return results in original order

16. In agentic.py: when multiple tool_calls, use orchestrator. Single call: direct.

17. In agent.py: add metadata per tool: parallelizable, side_effects
    - read_file, web_search, scrape_url, execute_python = parallelizable
    - write_file, run_command = not parallelizable

18. Create tests/test_tool_orchestrator.py

=== E. PLUGIN SYSTEM V2 (synapse/core/plugins.py) ===
19. Extend SynapsePlugin base class:
    - get_tools() -> list[dict] (tool definitions)
    - get_slash_commands() -> list[dict] (name, description, handler)
    - get_hooks() -> dict[str, callable]: on_message_send, on_message_receive, on_tool_execute, on_tool_result, on_conversation_create
    - get_settings_schema() -> dict (JSON schema)

20. Extend PluginManager:
    - _collect_tools(): aggregate from active plugins, register with "plugin__" prefix
    - _collect_slash_commands(): aggregate
    - dispatch_hook(name, **kwargs): call all plugins, wrapped in try/except
    - reload_plugin(name): hot-reload without restart

21. Create synapse/plugins/ directory (NOT in CONFIG_DIR, in the source tree):
    - word_count.py: tool word_count(text)->int, slash /wc
    - timestamp.py: hook on_message_send prepends timestamp, slash /time

22. In main.py:
    - dispatch_hook("on_message_send") in _send_message
    - dispatch_hook("on_message_receive") after response
    - Include plugin tools in tool list
    - Check plugin slash commands in _handle_slash_command

23. In plugin_sidebar.py: show tools/commands/hooks per plugin, Reload button

24. Create tests/test_plugins_v2.py

=== F. PRIVACY FIREWALL V2 (synapse/core/privacy_filter.py) ===
25. Rewrite PrivacyFilter → PrivacyFirewall:
    - PrivacyRule dataclass: name, pattern (compiled regex), replacement, enabled, category, severity
    - Built-in rules: email, phone, SSN, CC, API keys (AWS/GitHub/OpenAI/Anthropic), IP, JWT, private keys, passwords
    - Custom rules from CONFIG_DIR/privacy_rules.json
    - mask(text) -> tuple[str, list[MaskEvent]]: MaskEvent has rule_name, original_hash (sha256), replacement
    - get_stats(): counts by rule and category

26. Create privacy_audit.py: log mask events (hash only, NEVER original values), get_report(days)

27. In settings_dialog.py: add Privacy tab with per-rule toggles, custom rule editor (name, regex, replacement), Test button

28. In main.py: use PrivacyFirewall, log to audit, status bar indicator "🔒 N masked"

29. Create tests/test_privacy_firewall.py: every built-in rule, custom rules, no original values in logs

=== G. MCP DISCOVERY & HEALTH ===
30. Create mcp_discovery.py:
    - scan_system(): check npx/uvx/pip for MCP packages, check MCP_REGISTRY prerequisites
    - verify_server(cmd, args): start, initialize, check, kill
    - auto_configure(candidates)

31. Create mcp_health.py:
    - MCPHealthMonitor: QTimer 5min, ping servers, track latency/errors
    - get_health_report()
    - Signals: server_unhealthy, server_recovered

32. In mcp.py: auto-reconnect with exponential backoff, disable after 5 failures

33. In mcp_marketplace.py: Auto-Discover button, health indicators (colored dots)

34. Create tests/test_mcp_discovery.py, tests/test_mcp_health.py

=== H. CHAT UX IMPROVEMENTS ===
35. In renderer.py:
    - Add blinking cursor during streaming (CSS animation)
    - Add "Synapse is thinking..." indicator before first token
    - Code blocks: ensure Copy/Apply/Run buttons work (verify action:// handlers in chat_page.py)
    - Add language label on code blocks
    - Tables: alternating row colors
    - Images: render inline for base64 and local paths

36. In input.py:
    - Add character count label (bottom-right, subtle)
    - Add token estimate (using len/4)

37. Fix the _on_chat_action bug in main.py: the `index` variable is undefined for copy/edit/regenerate/bookmark/fork actions. Find where the message index should come from and fix it.

38. Create tests/test_renderer.py: code block HTML generation, markdown edge cases

=== I. MODEL ROUTER ===
39. Create model_router.py:
    - classify_task(msg) -> "simple"/"code"/"analysis"/"creative"/"general" (heuristics only)
    - route(msg, context) -> model name (based on classification + settings)
    - get_available_models(): Ollama /api/tags + configured providers, cache 5min

40. In main.py: add "Auto" to model selector. When Auto, use router. Show "(auto: model)" in message.

41. In settings_dialog.py Models tab: Enable Router toggle, fast_model/code_model/analysis_model fields

42. Create tests/test_model_router.py

=== J. KEYBOARD SHORTCUTS V2 ===
43. In constants.py: add comprehensive DEFAULT_SHORTCUTS dict:
    Ctrl+K: palette, Ctrl+N: new chat, Ctrl+W: close tab, Ctrl+Tab/Shift+Tab: switch tabs,
    Ctrl+Enter: send, Ctrl+Shift+Enter: send agentic, Ctrl+/: toggle sidebar,
    Ctrl+L: clear, Ctrl+R: regenerate, Escape: cancel generation

44. Create shortcuts.py ShortcutManager: register, dispatch, conflict detection

45. In command_palette.py: add fuzzy search, recent commands (persist top 10), categories

46. Create tests/test_shortcuts.py

=== K. SETTINGS ADDITIONS ===
47. In settings_dialog.py:
    - Add Privacy tab (from F above)
    - Add Router settings (from I above)
    - Move deep_research settings to their own group box in General
    - Add "Completion Model" field in Models tab (currently hardcoded qwen2.5-coder:1.5b)
    - Add "Debug Mode" checkbox in Advanced (sets log level to DEBUG)
    - Save ALL new settings in _save

=== L. FIX KNOWN BUGS ===
48. Fix editor.py: _lsp_timer is used in _on_text_changed but never created in __init__. Add self._lsp_timer = QTimer(); self._lsp_timer.setSingleShot(True); self._lsp_timer.setInterval(300) in __init__.

49. Fix scheduler.py: _execute_task is a stub that only logs. Wire it to actually create a conversation and run the prompt through _send_message (emit task_started signal, let main.py handle execution).

50. Fix plugins.py: execute_tool and handle_slash return None. Wire them to iterate loaded plugins and call their methods.

51. Fix tree_visualizer.py: paintEvent has pass. Add basic tree rendering (draw circles for nodes, lines for edges using QPainter).

52. Fix all bare `except: pass` patterns in: agent_manager.py, analytics.py, code_executor.py, file_applier.py, memory.py, notebook_manager.py, store.py, workspace.py, workspace_search.py — change to `except Exception as e: log.warning(...)` so errors are visible.

=== M. TESTS FOR UNTESTED MODULES ===
53. Create tests/test_agent.py: test ToolRegistry register/execute/get_definitions
54. Create tests/test_renderer.py: test build_html with code blocks, tables, tool blocks
55. Create tests/test_store.py: test ConversationStore create/save/load/delete/search
56. Create tests/test_privacy_filter_rules.py: test each regex pattern individually

After ALL items are complete, say "SESSION 2 DONE" and list what was created/modified.
```

**Test prompt (paste into Synapse after session):**
```
1. Agentic: "Create /tmp/synapse_test.txt with 'hello', read it back." Check ~/.local/share/synapse/tool_audit.jsonl.
2. Three chats (Python, Docker, cooking). Fourth: "What have we talked about?" Memory sidebar shows all.
3. Agentic: "Read all .py files in synapse/core/, list functions without docstrings." See plan + progress.
4. Enable privacy. Send "email test@example.com key AKIAIOSFODNN7EXAMPLE". Masked. Status bar.
5. Ctrl+K opens palette. Ctrl+N new chat. Escape cancels generation.
```

---

# SESSION 3

Copy everything between the triple-backtick fences below into a **new** Cursor composer session.

```
You are working on Synapse, a PyQt5 AI desktop app at /home/z1337/Desktop/PROJECTS/Synapse. Complete EVERY item. Do not stop.

=== A. CONVERSATION BRANCHING ===
1. In store.py ConversationStore:
   - Add msg_id (uuid), parent_id, branch_id to message schema
   - create_branch(conv_id, from_msg_id, branch_name=None) -> branch_id
   - get_branches(conv_id) -> list[BranchInfo]
   - get_branch_messages(conv_id, branch_id) -> list[dict]
   - merge_branch(conv_id, source, target)
   - delete_branch(conv_id, branch_id)
   - Migration for existing conversations (add "main" branch)

2. Create branch_navigator.py: dropdown selector, New Branch button, Compare Branches

3. In main.py: wire Branch action from chat, switch branches, append to current

4. Create tests/test_branching.py

=== B. TERMINAL V2 ===
5. Rewrite terminal.py with proper PTY:
   - Use pty module for PTY allocation
   - ANSI color parsing (16+256 colors) — use pyte library if available, else regex fallback
   - Proper cursor handling, terminal resize (SIGWINCH)
   - TerminalMultiplexer: multiple tabs, naming, kill per tab
   - Scrollback buffer 10k lines (configurable)
   - TerminalHistory: command history, persist across sessions

6. Agent terminal: dedicated "Agent" tab for run_command output

7. "Run in Terminal" on code blocks: open in new terminal tab

8. Settings: shell selection, terminal font size, scrollback size

9. Create tests/test_terminal.py

=== C. EDITOR + LSP ===
10. Fix editor.py _lsp_timer bug (if not fixed in Session 2)

11. Wire LSP integration:
    - On file open: start appropriate LSP server via lsp_manager
    - Real-time diagnostics: red/yellow underlines via QTextCharFormat, gutter markers
    - Autocomplete on "." and Ctrl+Space: completion popup from LSP
    - Go to definition: Ctrl+Click or F12
    - Hover info: show type/docs in tooltip
    - Handle LSP server crashes (restart, notify)

12. Create problems_panel.py: list all diagnostics, filter by severity, click to jump

13. Editor gutter: line numbers, fold markers, git diff indicators, diagnostic markers

14. Settings: LSP enable/disable, per-language config, format on save

15. Create tests/test_lsp_integration.py

=== D. WORKSPACE SEARCH V2 ===
16. Update indexer.py:
    - FTS5 index for full-text search
    - Watch filesystem with QFileSystemWatcher for incremental updates
    - Symbol extraction (function/class names) via regex or tree-sitter

17. Upgrade workspace_search.py:
    - Text search (FTS5), regex search, symbol search
    - Results grouped by file, click to open at location
    - Replace functionality for text/regex
    - Filters: file type, include/exclude patterns

18. Add search_workspace tool to agent.py: search(query, mode, file_type)

19. Create tests/test_workspace_search.py

=== E. GIT V2 ===
20. In git.py:
    - stage_file, unstage_file, stage_hunk
    - get_file_diff(path, staged) -> list[DiffHunk] (old_start, old_count, new_start, new_count, lines)
    - get_branch_graph() -> list[GraphNode]
    - stash_save, stash_pop, stash_list
    - blame(file_path) -> list[BlameLine]

21. Create/update git_sidebar.py or git_panel.py:
    - Changed files with M/A/D/? indicators
    - Stage/unstage checkboxes, commit input + button
    - Branch list with switch/create/delete
    - Stash section

22. Update diff_view.py: side-by-side diff, hunk staging, syntax highlighting in both panes

23. "Explain diff" button: send diff to model. "Review changes": send all staged to model.

24. Create tests/test_git_v2.py

=== F. WORKFLOW ENGINE V2 ===
25. In workflow.py:
    - Add node types: condition (if/else), loop (N times or until), parallel, human_input, model_call, tool_call, transform
    - Variable passing between nodes
    - Error handling per node (retry, skip, abort)
    - Pause/resume/cancel
    - Execution log with timing

26. In workflow_sidebar.py:
    - Visual builder: canvas with draggable nodes, connection drawing
    - Node palette, zoom/pan
    - Execution view: highlight current node, show output

27. Create workflow_templates.py:
    - "Code Review": read file → analyze → write review
    - "Research": web search → scrape top 3 → summarize
    - "Test & Fix": run tests → if fail → fix → rerun (loop)

28. Add run_workflow tool to agent.py

29. Create tests/test_workflow_v2.py

=== G. NOTEBOOK SUPPORT ===
30. Update notebook_manager.py:
    - Execute cells via subprocess (python -c)
    - Capture stdout/stderr/matplotlib
    - Variable inspector: list all vars from exec namespace
    - Load/save .ipynb, export .py/.html

31. Create/update notebook_view.py or notebook_editor.py:
    - Cell list: code cells with editor + output, markdown cells with render
    - Cell toolbar: Run (Shift+Enter), add above/below, delete, type selector
    - Notebook toolbar: Run All, Restart, Variable Inspector

32. AI per cell: Explain, Fix error, Generate next, Optimize buttons

33. Create tests/test_notebook.py

=== H. IMAGE GEN V2 ===
34. In image_gen.py:
    - Add img2img support (SD /sdapi/v1/img2img)
    - Add parameter presets: Photorealistic, Artistic, Fast Draft, Anime
    - Prompt enhancement: optional LLM call to expand prompt

35. In ImageGenSidebar.py:
    - Gallery view: grid of thumbnails, click for full + details
    - Presets dropdown, negative prompt, batch generation (N images)
    - History with re-generate and variations

36. Inline images in chat: when generate_image tool used, show image. Regenerate button.

37. Create tests/test_image_gen_v2.py

=== I. VOICE V2 ===
38. In voice.py:
    - Continuous listening mode with VAD (energy-based silence detection)
    - Voice commands (local): "new chat", "stop", "read that again"
    - TTS: support espeak/piper/system, speed control, queue

39. Create voice_panel.py: status indicator, waveform, transcript, push-to-talk, mute

40. Settings Voice tab: VAD sensitivity, TTS engine/voice/speed

41. Create tests/test_voice_v2.py

=== J. MODEL MANAGER V2 ===
42. Create/update model_manager.py UI:
    - Unified browser: all models from Ollama + API providers
    - Model cards: name, provider, size, context length
    - Pull with progress bar, delete with confirm
    - Comparison view: select 2+ models side by side
    - Provider status (connected/disconnected)

43. In main.py: auto-fallback if model fails (try next in chain). Notify user.

44. Settings: fallback chain config, default models per task

45. Create tests/test_model_manager.py

=== K. DEBUG V2 ===
46. In debug_manager.py:
    - Support Python debugging via debugpy
    - Launch configs: stored in .synapse/launch.json
    - Breakpoints: file+line, conditional, logpoints
    - Variable inspection, call stack, step controls

47. In debug_sidebar.py:
    - Variables tree view, Watch panel, Call Stack, Breakpoints list
    - Launch config selector

48. In debug_toolbar.py: Continue, Step Over, Step Into, Step Out, Restart, Stop

49. In editor.py: breakpoint gutter click, current line highlight, inline variable values

50. Create tests/test_debug_v2.py

=== L. GITHUB / PR INTEGRATION ===
51. Create github_integration.py:
    - Wrap gh CLI: list_prs, get_pr_diff, create_review, list_issues
    - PRReviewAssistant: analyze diff via model, generate review comments

52. In pr_sidebar.py: PR list, click for detail, AI Review button, Post Review

53. In pr_review_view.py: side-by-side diff with AI comments

54. Create tests/test_github.py

=== M. COLLABORATION ===
55. Create collaboration.py:
    - SessionServer (WebSocket via asyncio + websockets): host session, sync state
    - SessionClient: connect, send/receive, reconnect
    - Message types: CHAT_MESSAGE, TYPING_INDICATOR, MODEL_RESPONSE

56. Create collaboration_panel.py:
    - Host/Join buttons, share code, connected users
    - Typing indicators, user colors

57. Create tests/test_collaboration.py

=== N. SCHEDULER V2 ===
58. In scheduler.py:
    - Cron-style scheduling expressions
    - Event triggers: on_file_change, on_git_commit
    - Chain tasks: output → next input
    - Actually execute tasks (fix stub)

59. In ScheduleSidebar.py: calendar view, create/edit/delete tasks

60. Create tests/test_scheduler_v2.py

=== O. TASK BOARD V2 ===
61. In task_manager.py:
    - Sub-tasks, dependencies (DAG), time tracking
    - AI estimation: model estimates complexity

62. In task_board.py:
    - Drag-and-drop Kanban columns
    - Task detail editor, sub-task list
    - "AI Break Down" button: model creates sub-tasks

63. Create tests/test_task_board_v2.py

=== P. ANALYTICS DASHBOARD ===
64. In analytics.py:
    - Track: messages, tokens, tool calls, response time per model per day
    - Cost estimation for API models

65. Create analytics_dashboard.py or update analytics_sidebar.py:
    - Overview: messages today, tokens, conversations
    - Charts (render as HTML in QWebEngineView): messages/day, tokens by model, tool usage

66. Create tests/test_analytics.py

=== Q. SECURITY ===
67. Code execution sandbox in code_executor.py:
    - resource module limits: 256MB memory, 30s CPU
    - Blacklist dangerous commands: rm -rf /, dd, mkfs, format

68. Secret management: move API keys to system keyring (keyring library). Warn if plaintext in settings.

69. Create tests/test_security.py

=== R. PERFORMANCE & POLISH ===
70. Profile startup: lazy-load heavy imports (lsp_manager, debug_manager, voice, image_gen)
71. Fix all remaining bare `except: pass` (if not done in Session 2)
72. Add __all__ exports to all synapse/core/ modules
73. Create synapse/core/__init__.py with version info

After ALL items are complete, say "SESSION 3 DONE" and list what was created/modified.
```

**Test prompt:**
```
1. Branch: 3 messages, branch from msg 2, different path. Switch branches.
2. Terminal: ls --color. Agent run_command in Agent tab.
3. Editor: open .py, diagnostics, autocomplete.
4. Git: change file, stage, commit in sidebar.
5. Workflow: Code Review template on a file.
6. Ctrl+K palette. Agentic "read 3 files" — parallel execution.
```

---

# SESSION 4 (if sessions 2+3 complete)

```
You are working on Synapse at /home/z1337/Desktop/PROJECTS/Synapse. This is the polish and integration session.

=== A. ACCESSIBILITY ===
1. High contrast theme in themes.py
2. Keyboard-only navigation: all panels reachable via Tab/Shift+Tab
3. Font scaling: respect system DPI settings
4. Reduced motion: disable animations via setting

=== B. I18N ===
5. Create synapse/i18n/ with en.json, es.json
6. tr() function that looks up keys
7. Extract all user-facing strings from UI files (at least main.py, settings_dialog.py, sidebar.py)

=== C. CONFIG SYNC ===
8. Export all settings + themes + shortcuts as .synapse-config.json
9. Import from .synapse-config.json
10. Settings: Export/Import buttons

=== D. ONBOARDING V2 ===
11. Update onboarding.py: interactive feature tour
12. "What's New" dialog on version upgrade
13. Feature tips: subtle highlights on unused features

=== E. RELEASE PREP ===
14. Version in constants.py, update setup.py
15. Changelog generation from git log
16. Package: ensure pip install -e . works cleanly
17. Add .desktop file for Linux
18. Add app icon

=== F. COMPREHENSIVE TESTS ===
19. tests/test_api.py: WorkerFactory, TitleWorker (mock HTTP)
20. tests/test_mcp.py: MCPServerConnection, MCPClientManager (mock subprocess)
21. tests/test_workflow.py: node execution, variable passing, error handling
22. tests/test_voice.py: VoiceManager methods (mock audio)
23. tests/test_image_gen.py: presets, metadata
24. tests/test_terminal.py: PTY, ANSI, history
25. Run ALL tests, fix any failures

After ALL items complete, say "SESSION 4 DONE".
```

---

# Quick Reference

| Session | Scope | Items |
|---------|-------|-------|
| 1 | Context + Summarizer + Deep Research | DONE |
| 2 | Tool audit, Memory, Agentic V2, Plugins, Privacy, MCP, Chat UX, Router, Shortcuts, Bug fixes | 56 items |
| 3 | Branching, Terminal, Editor/LSP, Search, Git, Workflow, Notebook, Image, Voice, Models, Debug, PR, Collab, Scheduler, Tasks, Analytics, Security | 73 items |
| 4 | Accessibility, i18n, Config, Onboarding, Release, Tests | 25 items |

**Start with Session 2.** Copy its prompt into a new Cursor composer session.
