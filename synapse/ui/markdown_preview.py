import markdown
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl

PREVIEW_CSS = """
body { background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       padding: 20px; line-height: 1.6; max-width: 800px; margin: 0 auto; }
h1, h2, h3, h4 { color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 0.3em; }
code { background: #161b22; padding: 2px 6px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; }
pre { background: #161b22; padding: 12px; border-radius: 6px; overflow-x: auto; }
pre code { background: none; padding: 0; }
blockquote { border-left: 3px solid #3b82f6; margin-left: 0; padding-left: 16px; color: #8b949e; }
a { color: #58a6ff; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #30363d; padding: 8px 12px; }
th { background: #161b22; }
img { max-width: 100%; border-radius: 6px; }
hr { border: none; border-top: 1px solid #30363d; }
ul, ol { padding-left: 24px; }
"""


class MarkdownPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view)
        self._md = markdown.Markdown(extensions=['fenced_code', 'tables', 'nl2br', 'sane_lists', 'toc'])

    def update_preview(self, md_text):
        self._md.reset()
        body = self._md.convert(md_text)
        html = f"<!DOCTYPE html><html><head><style>{PREVIEW_CSS}</style></head><body>{body}</body></html>"
        self.web_view.setHtml(html, QUrl("qrc:/"))
