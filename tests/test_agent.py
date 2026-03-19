"""Tests for synapse.core.agent."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_tool_registry_register_execute():
    from synapse.core.agent import ToolRegistry
    reg = ToolRegistry()
    reg.register("add", lambda a, b: a + b, "Add numbers", {"type": "object", "properties": {"a": {}, "b": {}}, "required": ["a", "b"]})
    assert reg.execute("add", {"a": 1, "b": 2}) == 3
    assert reg.execute("nonexistent", {}) is None


def test_tool_registry_get_definitions():
    from synapse.core.agent import ToolRegistry
    reg = ToolRegistry()
    reg.register("x", lambda: 1, "X", {"type": "object"})
    defs = reg.get_tool_definitions()
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "x"
    assert defs[0]["function"]["description"] == "X"
