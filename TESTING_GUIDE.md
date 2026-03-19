# Synapse IDE - Complete QA Testing Guide

Report results back to Claude using this format per test:
- PASS - worked as described
- FAIL - describe what happened instead
- SKIP - couldn't test (say why)

---

## SECTION 1: LAUNCH & STARTUP

```bash
cd /home/z1337/Desktop/PROJECTS/Synapse && python3 -m synapse
```

| # | Test | Expected Result | Your Result |
|---|------|----------------|-------------|
| 1.1 | Launch the app | Window opens, no crash, no terminal errors | |
| 1.2 | Activity bar visible on left | 22 icons + gear at bottom, all unique (no duplicates) | |
| 1.3 | Default theme loads | One Dark theme, dark background, readable text everywhere | |
| 1.4 | Chat panel is default view | Right side shows chat area with input box at bottom | |

---

## SECTION 2: ACTIVITY BAR (Left sidebar - click each icon top to bottom)

| # | Panel | What to check | Expected Result | Your Result |
|---|-------|---------------|----------------|-------------|
| 2.1 | Explorer | Click 1st icon | File tree shows workspace files/folders | |
| 2.2 | Search | Click 2nd icon | Search text input + results area | |
| 2.3 | Git | Click 3rd icon | Branch name, changed files list, commit area | |
| 2.4 | Chat | Click 4th icon | Conversation list (past chats) | |
| 2.5 | Debugger | Click 5th icon | 3 sections: Variables, Call Stack, Breakpoints | |
| 2.6 | Knowledge | Click 6th icon | Knowledge base panel (may show stats or empty) | |
| 2.7 | Extensions | Click 7th icon | 28 marketplace items, search bar at top, "Community coming soon" banner | |
| 2.8 | Agent Forge | Click 8th icon | List of pre-built agents (Code Architect, etc.), names readable | |
| 2.9 | Docker | Click 9th icon | If no docker: error msg + "Install Docker" button + "Retry" button | |
| 2.10 | Tasks | Click task icon | "No Tasks Detected" empty state with explanation text | |
| 2.11 | REPL | Click REPL icon | Notebook/REPL interface or empty state | |
| 2.12 | Testing | Click test icon | Test tree or "No tests discovered" | |
| 2.13 | Plan | Click plan icon | "No active plan" empty state message | |
| 2.14 | Templates | Click templates icon | Prompt template library | |
| 2.15 | Analytics | Click analytics icon | Token/usage analytics panel | |
| 2.16 | Branch Tree | Click branch icon | Conversation branch visualization | |
| 2.17 | Schedules | Click schedules icon | Task scheduling panel | |
| 2.18 | Image Gen | Click image icon | Stable Diffusion / ComfyUI interface | |
| 2.19 | Workflows | Click workflows icon | Workflow automation panel | |
| 2.20 | Bookmarks | Click bookmarks icon | Saved bookmarks list | |
| 2.21 | Marketplace | Click marketplace icon | MCP server marketplace | |
| 2.22 | Delegative Board | Click board icon | Kanban board (Todo/In Progress/Done) | |
| 2.23 | Fine-Tuning | Click fine-tune icon | LoRA fine-tuning interface | |
| 2.24 | Settings (gear) | Click gear at bottom | Settings dialog opens as a popup | |

For EVERY panel above, also check:
- Panel content is **readable** (not dark text on dark background)
- No crash when clicking
- Panel switches cleanly (previous panel hides)

---

## SECTION 3: THEMES (test EVERY theme)

Open Settings > Appearance tab, switch theme, then check these:

### For EACH theme (One Dark, Monokai, GitHub Dark, Synapse Glass, GitHub Light):

| # | Test | Expected | Your Result |
|---|------|----------|-------------|
| 3.1 | Switch to theme | UI updates without crash | |
| 3.2 | Activity bar icons visible | All 22 icons clearly visible, not blending into background | |
| 3.3 | Hover tooltips readable | Hover every icon - tooltip text readable against tooltip bg | |
| 3.4 | Chat text readable | Messages in chat area have good contrast | |
| 3.5 | Input box readable | Can see typed text in chat input | |
| 3.6 | Explorer readable | File names visible in file tree | |
| 3.7 | Agent Forge readable | Agent names clearly visible | |
| 3.8 | Extensions readable | All 28 extension names/descriptions visible | |
| 3.9 | Settings dialog readable | All text in settings dialog legible | |
| 3.10 | Status bar readable | Bottom bar text visible | |

Report format: "Theme: [name] - 3.X FAIL: [what happened]"

---

## SECTION 4: CHAT & MESSAGING

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 4.1 | Send a message | Type "hello" + press Enter (or click send arrow) | Message appears in chat, AI responds | |
| 4.2 | Shift+Enter newline | Type "line1", Shift+Enter, type "line2", Enter | Multi-line message sent | |
| 4.3 | Stop generation | Send a long prompt, click Stop (square) button | Generation stops mid-stream | |
| 4.4 | New chat | Ctrl+N or /clear | Chat clears, new conversation | |
| 4.5 | Conversation appears in list | After sending a message | New convo in Chat sidebar with auto-title | |
| 4.6 | Switch conversations | Click different convo in Chat sidebar | Chat area loads that conversation's history | |
| 4.7 | Delete conversation | Right-click convo > delete (if available) | Conversation removed | |
| 4.8 | Code block actions | AI sends code > hover the code block | Copy/Run buttons appear on code blocks | |
| 4.9 | Markdown rendering | Ask AI to "format a table and a bullet list" | Rendered as formatted HTML, not raw markdown | |

---

## SECTION 5: INPUT WIDGET BUTTONS

| # | Button | Location | Test | Expected | Your Result |
|---|--------|----------|------|----------|-------------|
| 5.1 | AG (Agent Mode) | Left of input | Click it | Turns yellow, tooltip says "Agent Mode" | |
| 5.2 | AG toggle off | Click AG again | Returns to gray/inactive | |
| 5.3 | Attach (+) | Left of input | Click it | File picker opens | |
| 5.4 | Web Search globe | Near input | Click it | Toggles web grounding on/off | |
| 5.5 | Mic button | Near input | Click it | Recording starts (or error if no mic/whisper) | |
| 5.6 | Voice/TTS button | Near input | Click it | Toggles auto-read responses | |
| 5.7 | Send arrow | Right of input | Click after typing | Sends message | |

---

## SECTION 6: SLASH COMMANDS

Type each command in the chat input:

| # | Command | Expected | Your Result |
|---|---------|----------|-------------|
| 6.1 | / (just slash) | Autocomplete dropdown appears with command list | |
| 6.2 | /clear | Chat clears, new conversation | |
| 6.3 | /model | Model selection appears | |
| 6.4 | /system | System prompt editor opens | |
| 6.5 | /export | Export options appear | |
| 6.6 | /stats | Token/message statistics shown | |
| 6.7 | /help | List of available commands | |
| 6.8 | /search [term] | Semantic search runs on workspace | |
| 6.9 | /rag | RAG toggle | |
| 6.10 | /memory | Memory management | |

---

## SECTION 7: @ MENTIONS & VARIABLES

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 7.1 | File mention | Type @ in input | Autocomplete dropdown with workspace files | |
| 7.2 | Select file | Pick a file from @ dropdown | File path inserted into message | |
| 7.3 | Variable | Type {{ in input | Variable autocomplete (DATE, TIME, etc.) | |

---

## SECTION 8: KEYBOARD SHORTCUTS

| # | Shortcut | Expected | Your Result |
|---|----------|----------|-------------|
| 8.1 | Ctrl+N | New chat | |
| 8.2 | Ctrl+B | Toggle sidebar visibility | |
| 8.3 | Ctrl+L | Focus moves to chat input | |
| 8.4 | Ctrl+Shift+P | Command palette opens | |
| 8.5 | Ctrl+, | Settings dialog opens | |
| 8.6 | Ctrl+= | Zoom in (text gets larger) | |
| 8.7 | Ctrl+- | Zoom out (text gets smaller) | |
| 8.8 | Ctrl+0 | Zoom resets to 100% | |
| 8.9 | Ctrl+` | Terminal panel toggles | |
| 8.10 | Ctrl+W | Close current tab | |
| 8.11 | Ctrl+Tab | Next tab | |
| 8.12 | Ctrl+Shift+Tab | Previous tab | |
| 8.13 | Ctrl+Shift+F | Global search dialog | |
| 8.14 | Ctrl+Shift+H | Search & replace | |
| 8.15 | Ctrl+S | Save current file | |
| 8.16 | Ctrl+Z | Rollback last change | |
| 8.17 | Ctrl+Shift+Z | Zen mode toggle | |

---

## SECTION 9: COMMAND PALETTE (Ctrl+Shift+P)

Open palette, type each command:

| # | Command | Expected | Your Result |
|---|---------|----------|-------------|
| 9.1 | "new chat" | Creates new chat | |
| 9.2 | "edit system prompt" | System prompt editor opens | |
| 9.3 | "compare models" (with no convo) | Dialog says "Select or start a conversation first" | |
| 9.4 | "compare models" (with active convo) | Compare panel opens | |
| 9.5 | "export as markdown" | Exports current chat as .md | |
| 9.6 | "export as html" | Exports as .html | |
| 9.7 | "view logs" | Log viewer opens | |
| 9.8 | "conversation statistics" | Stats dialog with token counts | |
| 9.9 | "playground" | Model playground opens | |
| 9.10 | "arena" | A/B model comparison opens | |
| 9.11 | "prompt lab" | Multi-model comparison opens | |
| 9.12 | "consensus" | Multi-model voting opens | |
| 9.13 | "quick chat" | Floating chat window appears | |
| 9.14 | "delete all conversations" | Confirmation dialog, then clears all | |
| 9.15 | "session replay" | Replay dialog opens | |
| 9.16 | "extract all code blocks" | Saves code blocks to files | |
| 9.17 | Streaming speed: "instant" | Changes streaming to 10ms delay | |
| 9.18 | Streaming speed: "typewriter" | Changes to slow 200ms typewriter effect | |
| 9.19 | "import custom theme" | File picker for .qss/.json theme | |
| 9.20 | "git refresh" | Refreshes git status in sidebar | |

---

## SECTION 10: AGENTIC LOOP (Critical feature)

### Prerequisites
- You need a working AI backend (Ollama running, or API key set in Settings > Providers)
- Check: Settings > Providers > at least one API key set, OR Ollama running on localhost:11434

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 10.1 | Enable agent mode | Click AG button in chat input | Button turns yellow | |
| 10.2 | Simple read task | With AG on, send: "Read the file synapse/ui/main.py and tell me what the MainWindow class does" | AI calls read_file tool, shows tool execution in chat, then summarizes | |
| 10.3 | Tool visualization | During 10.2 | Tool calls appear as expandable blocks in chat showing what tool ran and its result | |
| 10.4 | Plan population | Click Plan sidebar during/after 10.2 | Plan panel shows steps the AI is working through | |
| 10.5 | Multi-step task | With AG on, send: "Find all Python files in synapse/ui/, count lines in each, and tell me which is largest" | AI chains multiple tool calls (list dir -> read files -> report) | |
| 10.6 | Write with approval | With AG on, send: "Create a file called /tmp/synapse_test.txt with the text 'hello world'" | Approval dialog appears asking permission for write_file | |
| 10.7 | Approve tool | Click Approve on 10.6 dialog | File gets created, AI confirms | |
| 10.8 | Deny tool | Try another write, click Deny | AI acknowledges denial, adjusts approach | |
| 10.9 | Stop mid-loop | Send complex task, click Stop while tools are running | Loop stops, partial results shown | |
| 10.10 | AG off = no tools | Turn AG off, send: "Read synapse/ui/main.py" | AI responds conversationally WITHOUT calling tools | |

---

## SECTION 11: FILE EXPLORER

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 11.1 | Browse files | Click Explorer icon | File tree of workspace | |
| 11.2 | Open file | Double-click a .py file | File opens in editor tab | |
| 11.3 | Multiple tabs | Open 2-3 different files | Each in its own tab, switchable | |
| 11.4 | Syntax highlighting | Open a .py file | Python syntax colored | |
| 11.5 | Edit file | Click in editor, type something | Text appears, file marked as modified | |
| 11.6 | Save file | Ctrl+S after editing | File saved, modified indicator clears | |
| 11.7 | Close tab | Ctrl+W on active tab | Tab closes | |

---

## SECTION 12: GIT INTEGRATION

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 12.1 | Git sidebar | Click Git icon | Shows current branch, changed files | |
| 12.2 | Branch display | Check top of git panel | Shows "main" (or current branch) | |
| 12.3 | File status | Make a change to a file | File appears in changed files list | |
| 12.4 | Diff view | Click on a changed file in git sidebar | Diff shown (added/removed lines) | |

---

## SECTION 13: EXTENSIONS MARKETPLACE

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 13.1 | Extension count | Click Extensions icon | 28 extensions listed | |
| 13.2 | Search filter | Type "python" in search bar | Only Python-related extensions shown | |
| 13.3 | Clear search | Clear search text | All 28 extensions return | |
| 13.4 | Extension details | Each extension shows | Name, description, author, category | |
| 13.5 | "Coming soon" banner | Visible somewhere in panel | "Community extensions coming soon" or similar | |

---

## SECTION 14: DOCKER PANEL

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 14.1 | Error state | Click Docker icon (docker not installed) | Error message visible, not a crash | |
| 14.2 | Install button | Click "Install Docker" | Browser opens to docker install page | |
| 14.3 | Retry button | Click "Retry Detection" | Re-checks for docker, shows result | |
| 14.4 | With docker (if installed) | Click Docker icon | Container list, images, controls | |

---

## SECTION 15: SETTINGS DIALOG

Open with Ctrl+, or gear icon:

| # | Tab | Test | Expected | Your Result |
|---|-----|------|----------|-------------|
| 15.1 | General | Toggle "Auto-generate titles" | Setting saves | |
| 15.2 | General | Set Ollama URL | Text field accepts URL | |
| 15.3 | General | Toggle "Frictionless mode" | Controls auto-approve for tools | |
| 15.4 | Models | Adjust Temperature slider | Moves 0.0-2.0 | |
| 15.5 | Models | Adjust Context Length | Shows value 512-131072 | |
| 15.6 | Appearance | Switch theme | Theme applies immediately | |
| 15.7 | Appearance | Change chat font size | Chat text resizes | |
| 15.8 | Appearance | Change zoom | Entire UI scales | |
| 15.9 | Advanced | Set workspace directory | Directory picker or text field | |
| 15.10 | Advanced | Toggle Privacy Firewall | Enables PII masking | |
| 15.11 | MCP | Add new MCP server | Form with name, command, args | |
| 15.12 | MCP | Test connection | Button attempts connection, shows result | |
| 15.13 | Providers | Enter API key | Key field accepts text, saves | |
| 15.14 | Voice | Select whisper model | Dropdown with tiny/base/small/medium/large | |
| 15.15 | Voice | Select TTS voice | Dropdown with voice options | |
| 15.16 | Shortcuts | View all shortcuts | Table showing all keybindings | |
| 15.17 | Shortcuts | Edit a shortcut | Key sequence capture works | |
| 15.18 | Shortcuts | Reset one shortcut | Reverts to default | |
| 15.19 | Local Backends | SD Forge status | Shows installed/not installed | |
| 15.20 | Local Backends | ComfyUI status | Shows installed/not installed | |

---

## SECTION 16: VOICE & AUDIO

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 16.1 | Mic button | Click mic in input | Recording indicator appears (or error about whisper) | |
| 16.2 | Stop recording | Click mic again or wait | Audio transcribed to text in input | |
| 16.3 | TTS toggle | Click voice/speaker button | Toggle indicator changes | |
| 16.4 | TTS playback | With TTS on, get AI response | Response read aloud | |
| 16.5 | Hands-free | Right-click mic > hands-free mode | Auto-sends after silence timeout | |

---

## SECTION 17: EXPORT & IMPORT

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 17.1 | Export MD | Command palette > "Export as Markdown" | .md file saved with conversation | |
| 17.2 | Export HTML | Command palette > "Export as HTML" | .html file with formatted chat | |
| 17.3 | Export JSON | Command palette > "Export as JSON" | .json with full conversation data | |
| 17.4 | Import | Ctrl+I or command palette > Import | File picker, loads conversation | |

---

## SECTION 18: SPLIT VIEW & TABS

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 18.1 | Open split | If split view exists in menu/palette | Second chat pane appears | |
| 18.2 | Independent models | Set different model per pane | Each pane talks to different model | |
| 18.3 | Sync input | Click sync button (if visible) | Same message sent to all panes | |

---

## SECTION 19: EDGE CASES & ERROR HANDLING

| # | Test | Steps | Expected | Your Result |
|---|------|-------|----------|-------------|
| 19.1 | No API key, send msg | Remove all API keys, send chat message | Helpful error, not crash | |
| 19.2 | No Ollama, send msg | Stop Ollama, send message | Connection error message, not crash | |
| 19.3 | Very long message | Paste 10000+ characters, send | Handles gracefully (sends or warns) | |
| 19.4 | Empty message | Press Enter with nothing typed | Nothing sent (no empty bubble) | |
| 19.5 | Rapid clicking | Click activity bar icons very fast | No crash, panels switch cleanly | |
| 19.6 | Resize window | Drag window very small then very large | UI adapts, no overflow/clipping | |
| 19.7 | Close during generation | Close app while AI is responding | Closes cleanly, no zombie process | |
| 19.8 | Multiple rapid sends | Send 5 messages very quickly | Queued or handled, no crash | |

---

## SECTION 20: ADVANCED FEATURES (if accessible)

| # | Feature | Test | Expected | Your Result |
|---|---------|------|----------|-------------|
| 20.1 | Arena | Cmd palette > Arena | A/B comparison UI with voting | |
| 20.2 | Prompt Lab | Cmd palette > Prompt Lab | Multi-model side-by-side | |
| 20.3 | Consensus | Cmd palette > Consensus | Multi-model voting interface | |
| 20.4 | Session Replay | Cmd palette > Session Replay | Playback of previous session | |
| 20.5 | Playground | Cmd palette > Playground | Single model test with param sliders | |
| 20.6 | Image Generation | Image Gen sidebar | SD/ComfyUI interface | |
| 20.7 | Fine-Tuning | Fine-Tuning sidebar | LoRA training UI | |
| 20.8 | Workflows | Workflows sidebar | Automation workflow editor | |
| 20.9 | Delegative Board | Board sidebar | Kanban with 3 columns | |
| 20.10 | Schedules | Schedules sidebar | Task scheduling UI | |

---

## HOW TO REPORT BACK

Copy this template for each failure:

```
Test: [number] [name]
Theme: [which theme was active]
What happened: [describe exactly what you saw]
Error in terminal: [paste any error output from the terminal where you launched synapse]
Screenshot: [if you can, take one]
```

Group your results like:
- "Sections 1-3: all PASS except 2.7 FAIL and 3.4 FAIL on GitHub Light"
- Then I'll know exactly what to fix.

---

## PRIORITY ORDER

Test in this order (most critical first):
1. Section 1 (Launch)
2. Section 4 (Chat - core functionality)
3. Section 10 (Agentic loop)
4. Section 2 (All panels load)
5. Section 3 (Themes)
6. Section 8 (Shortcuts)
7. Section 5-7 (Input features)
8. Section 19 (Edge cases)
9. Everything else
