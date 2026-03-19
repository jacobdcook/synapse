"""Tests for synapse.core.tool_audit."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_log_call():
    from synapse.core.tool_audit import ToolAuditLog
    with tempfile.TemporaryDirectory() as d:
        log = ToolAuditLog(Path(d) / "audit.jsonl")
        log.log_call("read_file", {"path": "x"}, "content", 10.5, True)
        entries = log.get_recent(10)
        assert len(entries) == 1
        assert entries[0]["tool_name"] == "read_file"
        assert entries[0]["duration_ms"] == 10.5
        assert entries[0]["success"] is True


def test_get_stats():
    from synapse.core.tool_audit import ToolAuditLog
    with tempfile.TemporaryDirectory() as d:
        log = ToolAuditLog(Path(d) / "audit.jsonl")
        log.log_call("a", {}, "ok", 10, True)
        log.log_call("a", {}, "ok", 20, True)
        log.log_call("b", {}, "err", 5, False)
        stats = log.get_stats()
        assert "a" in stats
        assert stats["a"]["count"] == 2
        assert stats["a"]["success_rate"] == 1.0
        assert stats["a"]["avg_duration_ms"] == 15.0
        assert stats["b"]["success_rate"] == 0.0


def test_rotate():
    from synapse.core.tool_audit import ToolAuditLog
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "audit.jsonl"
        log = ToolAuditLog(p)
        for _ in range(1000):
            log.log_call("x", {"data": "y" * 1000}, "z" * 1000, 1, True)
        assert p.exists()
        entries = log.get_recent(50)
        assert len(entries) <= 50
