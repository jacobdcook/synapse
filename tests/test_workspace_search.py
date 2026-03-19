"""Tests for workspace search."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_search_workspace_sync():
    from synapse.ui.workspace_search import search_workspace_sync
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "a.py").write_text("def foo(): pass\nx = 1\n")
        (Path(d) / "b.py").write_text("def bar(): pass\nfoo()\n")
        (Path(d) / "c.txt").write_text("hello world\n")
        results = search_workspace_sync(d, "foo", limit=10)
        assert len(results) >= 1
        paths = [r[0] for r in results]
        assert any("a.py" in p or "b.py" in p for p in paths)


def test_search_workspace_regex():
    from synapse.ui.workspace_search import search_workspace_sync
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "x.py").write_text("class Foo:\n  def bar(self): pass\n")
        results = search_workspace_sync(d, r"def \w+", use_regex=True, limit=10)
        assert len(results) >= 1


def test_search_workspace_tool():
    from synapse.core.agent import ToolExecutor
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "test.py").write_text("magic = 42\n")
        agent = ToolExecutor(d)
        out = agent._search_workspace("magic")
        assert "magic" in out or "42" in out
