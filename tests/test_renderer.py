"""Tests for synapse.core.renderer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_build_html_code_blocks():
    from synapse.core.renderer import ChatRenderer
    r = ChatRenderer()
    msgs = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "```python\nx=1\n```"}]
    html = r.build_html(msgs)
    assert "code-block" in html
    assert "cb-lang" in html
    assert "python" in html
    assert "action://runcode" in html or "action://applycode" in html


def test_build_html_tables():
    from synapse.core.renderer import ChatRenderer
    r = ChatRenderer()
    msgs = [{"role": "assistant", "content": "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |"}]
    html = r.build_html(msgs)
    assert "<table" in html
    assert "nth-child(even)" in html or "tbody" in html


def test_render_markdown_images():
    from synapse.core.renderer import ChatRenderer
    r = ChatRenderer()
    html = r.render_markdown("![x](data:image/png;base64,abc)")
    assert "inline-img" in html or "img" in html
    html2 = r.render_markdown("![x](file:///tmp/img.png)")
    assert "inline-img" in html2 or "img" in html2


def test_markdown_edge_cases():
    from synapse.core.renderer import ChatRenderer
    r = ChatRenderer()
    html = r.render_markdown("**bold** and *italic*")
    assert "bold" in html and "italic" in html
    html2 = r.render_markdown("`code`")
    assert "code" in html2
    html3 = r.render_markdown("> quote")
    assert "blockquote" in html3 or "quote" in html3
