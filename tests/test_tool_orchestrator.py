"""Tests for synapse.core.tool_orchestrator."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_execute_batch_single():
    from synapse.core.tool_orchestrator import ToolOrchestrator
    def exec_fn(name, args):
        return f"{name}:{args}"
    orch = ToolOrchestrator(exec_fn)
    calls = [{"id": "1", "function": {"name": "read_file", "arguments": {"path": "x"}}}]
    results = orch.execute_batch(calls)
    assert len(results) == 1
    assert "read_file" in results[0]["content"]


def test_execute_batch_multiple():
    from synapse.core.tool_orchestrator import ToolOrchestrator
    def exec_fn(name, args):
        return "ok"
    orch = ToolOrchestrator(exec_fn)
    calls = [
        {"id": "1", "function": {"name": "read_file", "arguments": {"path": "a"}}},
        {"id": "2", "function": {"name": "read_file", "arguments": {"path": "b"}}},
    ]
    results = orch.execute_batch(calls)
    assert len(results) == 2
