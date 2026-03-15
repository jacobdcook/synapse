import re
import markdown
import html as html_module
from pygments.formatters import HtmlFormatter
from ..utils.constants import APP_NAME, CHAT_HTML_TEMPLATE, detect_mime, format_time


class ChatRenderer:
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
        html = self.md.convert(text)
        self._code_idx = code_block_offset

        def _code_block_replace(match):
            lang = ""
            lang_match = re.search(r'class="[^"]*language-(\w+)', match.group(0))
            if lang_match:
                lang = lang_match.group(1)
            code_content = match.group(0)

            if lang.lower() == 'mermaid':
                inner = re.search(r'<code[^>]*>(.*?)</code>', code_content, re.DOTALL)
                if inner:
                    mermaid_src = html_module.unescape(inner.group(1))
                    return f'<div class="mermaid">{mermaid_src}</div>'

            lang_label = lang or "text"
            ci = self._code_idx
            self._code_idx += 1

            run_btn = ""
            if lang.lower() in ('python', 'python3', 'py'):
                run_btn = f'<button class="cb-btn cb-run" onclick="window.location.href=\'action://runcode/{ci}\'">&#9654; Run</button>'

            btns = (
                f'<button class="cb-btn" onclick="copyCode(this)">Copy</button>'
                f'<button class="cb-btn" onclick="window.location.href=\'action://applycode/{ci}\'">Apply</button>'
                f'<button class="cb-btn" onclick="window.location.href=\'action://proposecode/{ci}\'">Propose</button>'
                f'<button class="cb-btn" onclick="window.location.href=\'action://savecode/{ci}\'">Save</button>'
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

    def build_html(self, messages, model_name="", available_models=None):
        msgs_html = ""
        if not messages:
            msgs_html = self._build_welcome()
        else:
            global_code_idx = 0
            for idx, msg in enumerate(messages):
                role = msg.get("role", "assistant")
                if role in ("tool_results", "tool"):
                    continue
                content = str(msg.get("content", ""))
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
                    f'<div class="msg {role}">'
                    f'  <div class="msg-gutter">{avatar}</div>'
                    f'  <div class="msg-body">'
                    f'    <div class="msg-head"><span class="msg-name">{label}</span>{time_html}</div>'
                    f'    {images_html}{files_html}'
                    f'    <div class="msg-content">{rendered}</div>'
                    f'    {meta}'
                    f'    <div class="msg-toolbar">{actions}</div>'
                    f'  </div>'
                    f'</div>\n'
                )

        template = CHAT_HTML_TEMPLATE.replace("PYGMENTS_CSS", self.pygments_css)
        template = template.replace("FONT_SIZE_VAL", str(self.font_size))
        return template.replace("MESSAGES_HTML", msgs_html)

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
        return (
            f'<button onclick="window.location.href=\'action://edit/{idx}\'">Edit</button>'
            f'<button onclick="window.location.href=\'action://fork/{idx}\'">Fork</button>'
            f'<button onclick="window.location.href=\'action://bookmark/{idx}\'">{bm}</button>'
        )

    @staticmethod
    def _assistant_actions(idx, msg, is_last):
        bm = "Unbookmark" if msg.get("bookmarked") else "Bookmark"
        cont = f'<button onclick="window.location.href=\'action://continue/{idx}\'">Continue</button>' if is_last else ""
        return (
            f'<button onclick="window.location.href=\'action://copy/{idx}\'">Copy</button>'
            f'<button onclick="window.location.href=\'action://regenerate/{idx}\'">Regenerate</button>'
            f'<button onclick="window.location.href=\'action://retrywith/{idx}\'">Retry with&hellip;</button>'
            f'<button onclick="window.location.href=\'action://fork/{idx}\'">Fork</button>'
            f'<button id="rawbtn-{idx}" onclick="toggleRaw({idx})">Raw</button>'
            f'<button onclick="window.location.href=\'action://bookmark/{idx}\'">{bm}</button>'
            f'{cont}'
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
