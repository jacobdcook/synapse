# Synapse Improvement Roadmap

Daily work reference. Each section is self-contained—open it, do the work, verify, done.

---

## How to Use

1. Pick a session from the current phase.
2. Read the full section before starting.
3. Do the work. Verify with the checkmarks.
4. Mark complete and move to next.

**Note:** Each session typically takes minutes, not days. Plan ambitiously.

---

## Test Prompts (Required)

After every feature, the implementer must provide a copy-paste prompt you can run to verify it works. See each section's "Test Prompt" block.

**Consolidated Phase 1 Test Prompt** (run after Phase 1 complete):

```
1. Run: python3 -m synapse 2>&1 | head -20
   Expected: No "Unknown property cursor" in output.

2. New chat. Paste: [paste 3000+ chars of product text] what size for 94 lb dog?
   Expected: Model answers the question, not "Hello, I'm Synapse..."

3. Create ~/.local/share/synapse/themes/custom.json with:
   {"name":"Custom","qss":"QWidget{background:#1a1a2e;color:#eee;}","bg":"#1a1a2e","fg":"#eee","accent":"#00ff88"}
   Restart Synapse. Settings > Theme > Custom.
   Expected: Dark purple background.
```

---

**Phase 1 (Sessions 1–4):** Quick wins  
**Phase 2 (Sessions 5–6):** Long message complete  
**Phase 3 (Sessions 7+):** Reliability, memory, planning

---

# Phase 1: Quick Wins

## Session 1: Long Message — Tier 1 (System Prompt) (Est: 5 min)

**Objective:** Add instructions so the model answers long pastes instead of giving a generic intro.

**Files:** `synapse/utils/constants.py`

**What to do:**
1. Open `constants.py`. Find `DEFAULT_SYSTEM_PROMPT` (around line 85).
2. Append this block to the end of the string (before the closing `"""`):

```
When the user pastes long content (product pages, articles, docs):
1. Extract and answer their explicit question first. Never respond with a generic intro.
2. If they provide two items to compare, compare them and give a clear recommendation.
3. If they ask for a specific size/option, state it explicitly.
```

3. Ensure the string ends with `Prioritize efficiency, quality, and clear communication."` and the new block is on new lines before the closing `"""`.

**Verification:**
- [ ] Start Synapse, new chat
- [ ] Paste ~2k chars of product text + "what size for 94 lb dog?" at end
- [ ] Model should answer the question, not "Hello, I'm Synapse..."

**Edge cases:** None. This is additive only.

**Test Prompt:** Start Synapse: `python3 -m synapse`. New chat. Paste 2000+ chars of any product page, then at the end add: `what size for 94 lb GSD pit mix?` Send. Expected: Model answers the size question, not "Hello, I'm Synapse..."

---

## Session 2: Long Message — Tier 2 (Message Preprocessor) (Est: 15 min)

**Objective:** For messages > 3000 chars, restructure so the question appears first.

**Files to create:** `synapse/core/message_preprocessor.py`  
**Files to edit:** `synapse/ui/main.py`

**Part A — Create preprocessor:**

1. Create `synapse/core/message_preprocessor.py`:

```python
"""Preprocess long user messages so the model sees the question first."""
LONG_MESSAGE_THRESHOLD = 3000

def preprocess_long_message(content: str, threshold: int = LONG_MESSAGE_THRESHOLD) -> str:
    if not content or len(content) <= threshold:
        return content
    # Extract question: last 400 chars, or last paragraph, or last line ending in ?
    tail = content[-500:].strip()
    question = None
    for sep in ["\n\n", "\n"]:
        parts = tail.rsplit(sep, 1)
        if len(parts) == 2:
            candidate = parts[-1].strip()
            if "?" in candidate or len(candidate) < 300:
                question = candidate
                break
    if not question:
        question = tail[-400:] if len(tail) > 400 else tail
    # Context: truncate to ~6000 chars
    ctx = content[:6000] + ("..." if len(content) > 6000 else "")
    return f"USER QUESTION:\n{question}\n\nCONTEXT (for reference):\n{ctx}"
```

2. Add `__all__ = ["preprocess_long_message"]` if needed for imports.

**Part B — Integrate in main.py:**

1. In `_start_generation`, after the privacy filter (around line 1524) and before `if text:`:
   - Add: `from ..core.message_preprocessor import preprocess_long_message`
   - Replace `content` with `content = preprocess_long_message(content)`

2. In `_send_message`, after `conv["messages"].append(msg)` (around line 1410) and before the `if is_agentic:` block:
   - Add: `from ..core.message_preprocessor import preprocess_long_message`
   - Add: `conv["messages"][-1]["content"] = preprocess_long_message(conv["messages"][-1]["content"])`

**Verification:**
- [ ] Paste two product pages + question at end. Response should address the question.
- [ ] Short message (< 3k chars) unchanged.
- [ ] Agent mode: same behavior.

**Edge cases:** Message with no newlines (use last 400 chars). No question mark (use last paragraph). Multiple questions (use last one).

**Test Prompt:** Same as Session 1. Also: short message `hello` returns unchanged. Agent mode: same long paste test.

---

## Session 3: Suppress "Unknown property cursor" Warning (Est: 5 min)

**Objective:** Stop Qt from printing "Unknown property cursor" to stderr on startup.

**Files:** `synapse/__main__.py`

**What to do:**
1. At the top of `main()`, before `app = QApplication(sys.argv)`:
   - Add a filter for stderr that drops lines containing "Unknown property cursor".
   - Or: wrap `sys.stderr` in a small filter class that writes all lines except those matching that string.

2. Minimal approach—add after imports, before `def main()`:

```python
class _StderrFilter:
    def __init__(self, inner):
        self._inner = inner
    def write(self, s):
        if "Unknown property cursor" not in s:
            self._inner.write(s)
    def flush(self):
        self._inner.flush()
```

3. At the start of `main()`, before `app = QApplication(...)`:
   - `sys.stderr = _StderrFilter(sys.stderr)`

**Verification:**
- [ ] Run `python3 -m synapse`. No "Unknown property cursor" in terminal.
- [ ] Other stderr (e.g. real errors) still appears.

**Edge case:** Don't filter stderr from child processes. This only affects the Python process.

**Test Prompt:** `python3 -m synapse 2>&1 | head -20` — should print no "Unknown property cursor". Run `python3 -m synapse 2>&1 | grep -q "Unknown property cursor" && echo "FAIL" || echo "PASS"` — should print PASS.

---

## Session 4: External Theme Support (Est: 15 min)

**Objective:** Custom themes in `~/.local/share/synapse/themes/*.json` apply when selected.

**Files:** `synapse/utils/constants.py`, `synapse/ui/main.py`

**Part A — constants.py:**

1. Change `get_theme_qss` to use `get_all_themes()`:
   - Add: `from .themes import get_all_themes`
   - Replace: `return THEMES.get(name, THEMES["One Dark"])["qss"]`
   - With: `return get_all_themes().get(name, THEMES["One Dark"])["qss"]`
   - (Fallback stays `THEMES["One Dark"]` for backward compat.)

**Part B — main.py:**

1. In `_on_theme_changed` (around line 1259):
   - Replace `THEMES.get(theme_name, THEMES["One Dark"])` with `get_all_themes().get(theme_name, THEMES["One Dark"])` for the `theme` dict used by `apply_theme`.

2. In `__init__` where `_current_theme` is set (around line 224):
   - Use `get_all_themes().get(..., THEMES["One Dark"])` instead of `THEMES.get(...)`.

3. Add `from ..utils.themes import get_all_themes` if not present.

**Verification:**
- [ ] Create `~/.local/share/synapse/themes/custom.json`:
```json
{"name": "Custom", "qss": "QWidget { background: #1a1a2e; color: #eee; }", "bg": "#1a1a2e", "fg": "#eee", "accent": "#00ff88"}
```
- [ ] Restart Synapse → Settings → Theme → select "Custom". Background should change.
- [ ] Built-in themes still work.

**Edge case:** Invalid JSON in theme file → skip that theme, don't crash.

**Test Prompt:** Create `~/.local/share/synapse/themes/custom.json` with `{"name":"Custom","qss":"QWidget{background:#1a1a2e;color:#eee;}","bg":"#1a1a2e","fg":"#eee","accent":"#00ff88"}`. Restart Synapse. Settings > Theme > Custom. Expected: dark purple background.

---

# Phase 2: Long Message Complete

## Session 5: Deep Research — Settings & Module (Est: 30 min)

**Objective:** Add settings and a worker for Tier 3 pre-summarization.

**Files to create:** `synapse/core/deep_research.py`  
**Files to edit:** `synapse/ui/settings_dialog.py`, `synapse/utils/constants.py`

**Part A — constants.py:**
- Add defaults: `DEEP_RESEARCH_THRESHOLD = 8000`, `DEEP_RESEARCH_MODEL = ""` (empty = use main model).

**Part B — settings_dialog.py:**
- In General tab, after `auto_summary_check`:
  - Add `QCheckBox("Deep Research (auto-analyze long messages)")`
  - Bind to `settings_data["deep_research_enabled"]`
- In `_save`, persist `deep_research_enabled` and `deep_research_threshold` (optional spinbox).

**Part C — deep_research.py:**
- Create `DeepResearchWorker(QThread)`:
  - `__init__(self, content: str, model: str, settings: dict)`
  - `finished = pyqtSignal(str)` — emits processed content
  - `run()`: if `len(content) > threshold`, chunk into ~3500 char pieces, call Ollama `/api/chat` non-streaming with prompt "Summarize. Extract: product names, specs, prices, questions. Be concise."
  - Combine summaries, prepend extracted question (reuse logic from message_preprocessor), emit result.
  - If content shorter than threshold or error, emit original content.

**Verification:**
- [ ] Settings has Deep Research checkbox.
- [ ] `DeepResearchWorker` runs without errors.

**Test Prompt:** Start Synapse. Settings > General. Expected: "Deep Research (auto-analyze long messages)" checkbox exists.

---

## Session 6: Deep Research — Integration (Est: 30 min)

**Objective:** Wire Deep Research into the send flow.

**Files:** `synapse/ui/main.py`

**What to do:**
1. In `_start_generation`, after Tier 2 (before appending):
   - If `settings.get("deep_research_enabled")` and `len(content) > settings.get("deep_research_threshold", 8000)`:
   - Set status: "Deep Research: Analyzing..."
   - Create `DeepResearchWorker(content, model, settings)`
   - Use `QEventLoop` or connect `finished` to a slot that sets `content = result`, then continues.
   - Block until worker finishes (or 60s timeout).
   - Replace `content` with result, then proceed with append.

2. In `_send_message`, before `_run_agentic`:
   - Same check. If Deep Research triggers, run worker, block, replace `conv["messages"][-1]["content"]` with result.

**Verification:**
- [ ] Enable Deep Research, paste 15k chars. Status shows "Analyzing...", then response is informed.
- [ ] Disable: no change.

**Test Prompt:** Enable Deep Research in Settings. New chat. Paste 15k+ chars of product text + "summarize the key differences". Send. Expected: Status shows "Analyzing..." briefly, then model responds with informed summary.

---

# Phase 3: Reliability & Memory

## Session 7: Tool Call Audit Log (Est: 20 min)

**Objective:** Log tool calls and results to a file for debugging.

**Files:** `synapse/core/tool_executor.py` (or wherever tools run), `synapse/utils/constants.py`

**What to do:**
1. Add `TOOL_AUDIT_LOG = CONFIG_DIR / "tool_audit.log"`.
2. When a tool is invoked: append `timestamp | tool_name | args_summary | result_summary` to the file.
3. Keep result summary short (e.g. first 200 chars).

**Verification:**
- [ ] Run a tool. Check `~/.local/share/synapse/tool_audit.log` exists and has an entry.

**Test Prompt:** Send a message that triggers a tool (e.g. `read_file` on a file). Check `~/.local/share/synapse/tool_audit.log` exists and has an entry.

---

## Session 8: Tool Execution Verification (Part 1) (Est: 30 min)

**Objective:** After `write_file`, verify the file exists and matches expected content.

**Files:** `synapse/core/tool_executor.py` (or tool registry)

**What to do:**
1. After `write_file` returns success: read the file, compare to what was written.
2. If mismatch: log warning, optionally retry once.
3. Emit a signal or set a flag the model can see (e.g. "Tool reported success but file unchanged").

**Verification:**
- [ ] Simulate a failed write. Verify detection.

**Test Prompt:** (TBD after implementation)

---

## Session 9: Episodic Memory (Part 1) (Est: 45 min)

**Objective:** Store conversation events (conv_id, turn, topic, outcome) in a simple store.

**Files to create:** `synapse/core/episodic_store.py`  
**Files to edit:** `synapse/ui/main.py`

**What to do:**
1. Create `episodic_store.py`:
   - SQLite or JSON file at `CONFIG_DIR / "episodic.db"`.
   - `log_event(conv_id, turn_idx, role, topic_summary, outcome)`.
   - `query_recent(conv_id=None, limit=20)`.

2. In `main.py`, after each assistant response:
   - Call `log_event(conv_id, turn, "assistant", topic_from_first_user_msg[:50], "completed")`.

**Verification:**
- [ ] Have a chat. Check episodic store has entries.

**Test Prompt:** Have a chat. Check `~/.local/share/synapse/episodic.db` exists and has entries.

---

# Phase 4: Context & UX

## Session 10: Tab Context Injection (Est: 20 min)

**Objective:** On tab switch, inject minimal context so the model knows which conversation it's in.

**Files:** `synapse/ui/main.py`

**What to do:**
1. On tab change: store `conv_id` and `last_topic` (first 30 chars of last user msg).
2. When building the next user message (in `_send_message` or before worker): if switching tabs, prepend `[Tab: {title}. Last topic: {last_topic}]` to the message.

**Verification:**
- [ ] Two tabs, different topics. Switch. Send message. Model should not confuse which tab.

**Test Prompt:** Create two tabs. Tab 1: "Help me with Python". Tab 2: "Help me with Rust". Switch to Tab 2. Send "what did I ask about?". Expected: Model answers "Rust", not Python.

---

# Reference: File Locations

| Concern | File |
|---------|------|
| System prompt | `synapse/utils/constants.py` |
| Message flow | `synapse/ui/main.py` `_send_message`, `_start_generation` |
| Themes | `synapse/utils/themes.py`, `constants.py` `get_theme_qss` |
| App entry | `synapse/__main__.py` |
| Tools | `synapse/core/tool_executor.py` (or wherever tools execute) |

---

# Completion Tracker

## PHASE 1 COMPLETE — 2025-03-19

- [x] Session 1: Tier 1
- [x] Session 2: Tier 2
- [x] Session 3: Cursor warning
- [x] Session 4: External themes
- [ ] Session 5: Deep Research module
- [ ] Session 6: Deep Research integration
- [ ] Session 7: Tool audit log
- [ ] Session 8: Tool verification
- [ ] Session 9: Episodic memory
- [ ] Session 10: Tab context
