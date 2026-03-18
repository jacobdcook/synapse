import re
import json
import markdown
import html as html_module
from pygments.formatters import HtmlFormatter
from ..utils.constants import (
    APP_NAME, CHAT_HTML_TEMPLATE, MERMAID_JS_URL,
    KATEX_CSS_URL, KATEX_JS_URL, KATEX_AUTO_RENDER_JS_URL,
    detect_mime, format_time
)


class ChatRenderer:
    @staticmethod
    def _safe_truncate(text, limit=2000):
        if len(text) <= limit:
            return text
        t = text[:limit]
        amp = t.rfind('&')
        if amp != -1 and ';' not in t[amp:]:
            t = t[:amp]
        return t + "..."

    def __init__(self):
        self.formatter = HtmlFormatter(style="monokai", noclasses=True, nowrap=False)
        self.pygments_css = HtmlFormatter(style="monokai").get_style_defs('.highlight')
        self.md = markdown.Markdown(extensions=[
            'fenced_code', 'tables', 'nl2br', 'sane_lists'
        ])
        self.font_size = 15
        self._code_idx = 0

    def render_markdown(self, text, code_block_offset=0):
        self.md.reset()

        # Extract <think> blocks before markdown conversion
        think_blocks = []
        def _extract_think(match):
            think_blocks.append(match.group(1).strip())
            return ""
        text = re.sub(r'<think>(.*?)</think>', _extract_think, text, flags=re.DOTALL)

        html = self.md.convert(text)

        # Prepend collapsible thinking blocks
        if think_blocks:
            for i, block in enumerate(think_blocks):
                think_html = html_module.escape(block).replace("\n", "<br>")
                tid = f"think-{id(text)}-{i}"
                html = (
                    f'<div class="think-block">'
                    f'<div class="think-header" onclick="toggleThink(\'{tid}\')">'
                    f'<span class="think-chevron" id="thinkchev-{tid}">&#9654;</span> Thinking&hellip;'
                    f'</div>'
                    f'<div class="think-body" id="thinkbody-{tid}">{think_html}</div>'
                    f'</div>'
                ) + html

        self._code_idx = code_block_offset

        def _code_block_replace(match):
            lang = ""
            filename = ""
            # Detect language and filename from class: class="language-python:main.py"
            lang_match = re.search(r'class="[^"]*language-([^ ":\n]+)(?::([^ "> \n]+))?', match.group(0))
            if lang_match:
                lang = lang_match.group(1)
                filename = lang_match.group(2) if lang_match.group(2) else ""

            code_content = match.group(0)

            ci = self._code_idx
            self._code_idx += 1

            if lang.lower() == 'mermaid':
                inner = re.search(r'<code[^>]*>(.*?)</code>', code_content, re.DOTALL)
                if inner:
                    mermaid_src = html_module.unescape(inner.group(1))
                    mermaid_src = re.sub(r'<script[^>]*>.*?</script>', '', mermaid_src, flags=re.DOTALL | re.IGNORECASE)
                    mermaid_src = re.sub(r'\bon\w+\s*=', '', mermaid_src, flags=re.IGNORECASE)
                    btns = f'<button class="cb-btn cb-preview" onclick="window.location.href=\'action://previewartifact/{ci}\'">&#128065; Open in Canvas</button>'
                    return (
                        f'<div class="code-block">'
                        f'<div class="cb-header"><span class="cb-lang">mermaid</span><span class="cb-actions">{btns}</span></div>'
                        f'<div class="mermaid">{mermaid_src}</div>'
                        f'</div>'
                    )

            lang_label = html_module.escape(lang) if lang else "text"
            if filename:
                lang_label += f": {html_module.escape(filename)}"

            lang_lower = lang.lower()
            preview_btn = ""
            if lang_lower in ('html', 'svg', 'xml', 'react', 'jsx', 'tsx', 'javascript', 'js'):
                # Artifact-capable language
                preview_btn = f'<button class="cb-btn cb-preview" onclick="window.location.href=\'action://previewartifact/{ci}\'">&#128065; Open in Canvas</button>'

            run_btn = ""
            if lang_lower in ('python', 'python3', 'py'):
                run_btn = f'<button class="cb-btn cb-run" onclick="window.location.href=\'action://runcode/{ci}\'">&#9654; Run</button>'

            # Include filename in apply/save actions if present
            fn_param = f"/{html_module.escape(filename)}" if filename else ""
            btns = (
                f'<button class="cb-btn" onclick="copyCode(this)">Copy</button>'
                f'<button class="cb-btn" onclick="window.location.href=\'action://applycode/{ci}{fn_param}\'">Apply</button>'
                f'<button class="cb-btn" onclick="window.location.href=\'action://proposecode/{ci}{fn_param}\'">Propose</button>'
                f'<button class="cb-btn" onclick="window.location.href=\'action://savecode/{ci}{fn_param}\'">Save</button>'
                f'{preview_btn}'
                f'{run_btn}'
            )

            inner_code = code_content[5:]  # strip leading <pre>
            return (
                f'<div class="code-block">'
                f'<div class="cb-header"><span class="cb-lang">{lang_label}</span><span class="cb-actions">{btns}</span></div>'
                f'<pre>{inner_code}'
                f'</div>'
            )

        html = re.sub(r'<pre><code[^>]*>.*?</code></pre>', _code_block_replace, html, flags=re.DOTALL)

        def _img_replace(match):
            src = match.group(1)
            return (
                f'<div class="inline-img-container">'
                f'<img src="{src}" class="inline-img" style="max-width:100%; max-height:500px; border-radius:8px; border:1px solid var(--border); cursor:pointer;" '
                f'onclick="window.open(this.src)" />'
                f'</div>'
            )
        html = re.sub(r'!\[.*?\]\((data:image/[^)]+)\)', _img_replace, html)
        html = re.sub(r'!\[.*?\]\((https?://[^\s)]+\.(?:png|jpg|jpeg|gif|webp|svg))\)', _img_replace, html)

        return html

    def build_html(self, messages, history=None, model_name="", available_models=None):
        history = history or []
        msgs_html = ""
        if not messages:
            msgs_html = self._build_welcome()
        else:
            global_code_idx = 0
            tool_idx = 0
            for idx, msg in enumerate(messages):
                role = msg.get("role", "assistant")

                # Render tool_results as collapsible blocks
                if role == "tool_results":
                    tool_calls_msg = messages[idx - 1] if idx > 0 else {}
                    tcs = tool_calls_msg.get("tool_calls", [])
                    results = msg.get("tool_results", [])
                    for i, tr in enumerate(results):
                        tc = tcs[i] if i < len(tcs) else {}
                        tc_name = tc.get("function", {}).get("name", "tool")
                        tc_args = tc.get("function", {}).get("arguments", {})
                        result_text = str(tr.get("content", ""))
                        is_err = result_text.startswith("Error") or "rejected" in result_text.lower()
                        icon_cls = "tool-err" if is_err else "tool-ok"
                        icon_char = "&#10007;" if is_err else "&#10003;"
                        display_name = tc_name.replace("mcp__github__", "github/").replace("mcp__", "")
                        args_summary = self._tool_args_summary(tc_args)
                        result_escaped = html_module.escape(self._safe_truncate(result_text))
                        args_escaped = html_module.escape(self._safe_truncate(json.dumps(tc_args, indent=2), 1000)) if tc_args else ""
                        tid = f"t{tool_idx}"
                        tool_idx += 1
                        args_section = f'<div class="tool-label">Input</div><div class="tool-output">{args_escaped}</div>' if args_escaped else ""
                        msgs_html += (
                            f'<div class="tool-block">'
                            f'  <div class="tool-header" onclick="toggleTool(\'{tid}\')">'
                            f'    <span class="tool-icon {icon_cls}">{icon_char}</span>'
                            f'    <span class="tool-name">{display_name}</span>'
                            f'    <span class="tool-summary">{args_summary}</span>'
                            f'    <span id="toolchev-{tid}" class="tool-chevron">&#9654;</span>'
                            f'  </div>'
                            f'  <div id="toolbody-{tid}" class="tool-body">'
                            f'    {args_section}'
                            f'    <div class="tool-label">Output</div>'
                            f'    <div class="tool-output">{result_escaped}</div>'
                            f'  </div>'
                            f'</div>\n'
                        )
                    continue
                if role == "tool":
                    continue
                content = str(msg.get("content", ""))
                # Show tool call message as a heading, skip if empty text
                if role == "assistant" and not content.strip() and msg.get("tool_calls"):
                    continue

                is_user = role == "user"
                is_system = role == "system"
                avatar = self._avatar(role)
                label = "You" if is_user else ("System" if is_system else "Synapse")
                timestamp = format_time(msg.get("timestamp", ""))
                time_html = f'<span class="ts">{timestamp}</span>' if timestamp else ""

                images_html = ""
                if msg.get("images"):
                    images_html = '<div class="msg-images">'
                    for img_b64 in msg["images"]:
                        mime = detect_mime(img_b64)
                        images_html += f'<img src="data:{mime};base64,{img_b64}" class="att-img" />'
                    images_html += '</div>'

                files_html = ""
                if msg.get("attached_files"):
                    files_html = '<div class="msg-files">'
                    for af in msg["attached_files"]:
                        files_html += f'<span class="att-file">{af["name"]}</span>'
                    files_html += '</div>'

                if is_user:
                    rendered = html_module.escape(content).replace("\n", "<br>")
                    actions = self._user_actions(idx, msg)
                elif role == "assistant":
                    rendered = self.render_markdown(content, code_block_offset=global_code_idx)
                    num_blocks = len(re.findall(r'```', content)) // 2
                    global_code_idx += num_blocks
                    raw_escaped = html_module.escape(content).replace("\n", "<br>")
                    rendered = (
                        f'<div id="rendered-{idx}">{rendered}</div>'
                        f'<div id="raw-{idx}" class="raw-md" style="display:none"><pre class="raw-pre">{raw_escaped}</pre></div>'
                    )
                    actions = self._assistant_actions(idx, msg, idx == len(messages) - 1)
                else:
                    rendered = html_module.escape(content).replace("\n", "<br>")
                    actions = ""

                meta = self._meta(msg) if role == "assistant" else ""

                msgs_html += (
                    f'<div class="msg {role}" data-idx="{idx}">'
                    f'  <div class="msg-gutter">{avatar}</div>'
                    f'  <div class="msg-body">'
                    f'    <div class="msg-head"><span class="msg-name">{label}</span>{time_html}{self._branch_navigation(idx, msg, history)}</div>'
                    f'    {images_html}{files_html}'
                    f'    <div class="msg-content">{rendered}</div>'
                    f'    {meta}'
                    f'    <div class="msg-toolbar">{actions}</div>'
                    f'  </div>'
                    f'</div>\n'
                )

        template = self._apply_template_vars(CHAT_HTML_TEMPLATE)
        return template.replace("MESSAGES_HTML", msgs_html)

    def _apply_template_vars(self, template):
        template = template.replace("PYGMENTS_CSS", self.pygments_css)
        template = template.replace("FONT_SIZE_VAL", str(self.font_size))
        template = template.replace("MERMAID_JS_URL", MERMAID_JS_URL)
        template = template.replace("KATEX_CSS_URL", KATEX_CSS_URL)
        template = template.replace("KATEX_JS_URL", KATEX_JS_URL)
        template = template.replace("KATEX_AUTO_RENDER_JS_URL", KATEX_AUTO_RENDER_JS_URL)
        return template

    @staticmethod
    def _avatar(role):
        if role == "user":
            return '<div class="avatar av-user">U</div>'
        if role == "system":
            return '<div class="avatar av-sys">S</div>'
        return '<div class="avatar av-ai">&#10038;</div>'

    @staticmethod
    def _user_actions(idx, msg):
        bm = "Unbookmark" if msg.get("bookmarked") else "Bookmark"
        drag = f'<span class="drag-handle" draggable="true" ondragstart="event.dataTransfer.setData(\'text/plain\',\'{idx}\')" title="Drag to reorder">&#x2630;</span>'
        return (
            f'{drag}'
            f'<button onclick="window.location.href=\'action://edit/{idx}\'">Edit</button>'
            f'<button onclick="window.location.href=\'action://fork/{idx}\'">Fork</button>'
            f'<button onclick="window.location.href=\'action://bookmark/{idx}\'">{bm}</button>'
        )

    @staticmethod
    def _assistant_actions(idx, msg, is_last):
        bm = "Unbookmark" if msg.get("bookmarked") else "Bookmark"
        cont = f'<button onclick="window.location.href=\'action://continue/{idx}\'">Continue</button>' if is_last else ""
        
        fb_up_active = "fb-active" if msg.get("feedback") == "up" else ""
        fb_down_active = "fb-active" if msg.get("feedback") == "down" else ""
        feedback = (
            f'<button class="fb-btn {fb_up_active}" onclick="window.location.href=\'action://feedback/{idx}/up\'" title="Thumbs Up">&#128077;</button>'
            f'<button class="fb-btn {fb_down_active}" onclick="window.location.href=\'action://feedback/{idx}/down\'" title="Thumbs Down">&#128078;</button>'
        )

        return (
            f'<span style="margin-right:8px">{feedback}</span>'
            f'<button onclick="window.location.href=\'action://copy/{idx}\'">Copy</button>'
            f'<button onclick="window.location.href=\'action://regenerate/{idx}\'">Regenerate</button>'
            f'<button onclick="window.location.href=\'action://retrywith/{idx}\'">Retry with&hellip;</button>'
            f'<button onclick="window.location.href=\'action://fork/{idx}\'">Fork</button>'
            f'<button id="rawbtn-{idx}" onclick="toggleRaw({idx})">Raw</button>'
            f'<button onclick="window.location.href=\'action://bookmark/{idx}\'">{bm}</button>'
            f'{cont}'
        )

    @staticmethod
    def _branch_navigation(idx, msg, history):
        parent_id = msg.get("parent_id")
        msg_id = msg.get("id")
        if not history or not msg_id:
            return ""

        # Find all messages with same parent
        siblings = [m for m in history if m.get("parent_id") == parent_id]
        if len(siblings) <= 1:
            return ""

        # Find current index among siblings
        try:
            current_idx = next(i for i, s in enumerate(siblings) if s.get("id") == msg_id)
        except StopIteration:
            return ""

        return (
            f'<div class="branch-switcher">'
            f'  <span class="br-btn" onclick="window.location.href=\'action://navbranch/{idx}/prev\'">&lt;</span>'
            f'  <span class="br-info">{current_idx + 1} / {len(siblings)}</span>'
            f'  <span class="br-btn" onclick="window.location.href=\'action://navbranch/{idx}/next\'">&gt;</span>'
            f'</div>'
        )

    @staticmethod
    def _meta(msg):
        if not msg.get("model"):
            return ""
        parts = [msg["model"]]
        if msg.get("duration_ms"):
            parts.append(f"{msg['duration_ms'] / 1000:.1f}s")
        if msg.get("tokens"):
            parts.append(f"{msg['tokens']} tok")
            if msg.get("duration_ms") and msg["duration_ms"] > 0:
                tps = msg["tokens"] / (msg["duration_ms"] / 1000)
                parts.append(f"{tps:.1f} tok/s")
        return f'<div class="msg-meta">{" &middot; ".join(parts)}</div>'

    @staticmethod
    def _tool_args_summary(args):
        if not args:
            return ""
        if isinstance(args, str):
            return html_module.escape(args[:60])
        parts = []
        for k, v in args.items():
            val = str(v)
            if len(val) > 40:
                val = val[:37] + "..."
            parts.append(f"{k}={val}")
        summary = ", ".join(parts)
        if len(summary) > 80:
            summary = summary[:77] + "..."
        return html_module.escape(summary)

    @staticmethod
    def _build_welcome():
        return (
            '<div class="welcome">'
            f'<div class="w-logo">&#10038;</div>'
            f'<h1>{APP_NAME}</h1>'
            '<p class="w-sub">Your local AI &mdash; multiple minds, one interface</p>'
            '<div class="w-grid">'
            '<div class="w-card"><div class="w-card-icon">&#128172;</div><div class="w-card-label">Chat with AI models</div></div>'
            '<div class="w-card"><div class="w-card-icon">&#128187;</div><div class="w-card-label">Write &amp; edit code</div></div>'
            '<div class="w-card"><div class="w-card-icon">&#128269;</div><div class="w-card-label">Search workspace</div></div>'
            '<div class="w-card"><div class="w-card-icon">&#9881;</div><div class="w-card-label">Run tools &amp; agents</div></div>'
            '<div class="w-card"><div class="w-card-icon">&#128194;</div><div class="w-card-label">@file mentions</div></div>'
            '<div class="w-card"><div class="w-card-icon">&#9000;</div><div class="w-card-label">Integrated terminal</div></div>'
            '</div>'
            '<div class="w-keys">'
            '<kbd>Ctrl+N</kbd> New Chat &nbsp;&nbsp;'
            '<kbd>Ctrl+B</kbd> Sidebar &nbsp;&nbsp;'
            '<kbd>Ctrl+Shift+P</kbd> Command Palette &nbsp;&nbsp;'
            '<kbd>Ctrl+`</kbd> Terminal &nbsp;&nbsp;'
            '<kbd>/help</kbd> All Commands'
            '</div>'
            '</div>'
        )

    def build_loading_html(self):
        template = self._apply_template_vars(CHAT_HTML_TEMPLATE)
        skeleton = (
            '<div class="welcome" style="opacity:0.5">'
            '<div class="skeleton-line" style="width:60%;height:18px;margin:24px auto 12px;background:#333;border-radius:4px;animation:pulse 1.2s infinite"></div>'
            '<div class="skeleton-line" style="width:80%;height:14px;margin:8px auto;background:#2a2a2a;border-radius:4px;animation:pulse 1.2s infinite"></div>'
            '<div class="skeleton-line" style="width:70%;height:14px;margin:8px auto;background:#2a2a2a;border-radius:4px;animation:pulse 1.2s infinite"></div>'
            '</div>'
            '<style>@keyframes pulse{0%,100%{opacity:0.4}50%{opacity:1}}</style>'
        )
        return template.replace("MESSAGES_HTML", skeleton)
