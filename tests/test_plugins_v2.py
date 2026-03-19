"""Tests for synapse.core.plugins v2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_plugin_execute_tool():
    from synapse.core.plugins import PluginManager, SynapsePlugin

    class MockPlugin(SynapsePlugin):
        def get_tools(self):
            return [{"name": "test_tool", "description": "Test", "handler": lambda x: x.upper(), "parameters": {"type": "object", "properties": {"x": {}}, "required": ["x"]}}]

    api = object()
    pm = PluginManager(api)
    pm.plugins["mock"] = MockPlugin(api)
    result = pm.execute_tool("plugin__test_tool", {"x": "hi"})
    assert result == "HI"


def test_plugin_handle_slash():
    from synapse.core.plugins import PluginManager, SynapsePlugin

    class MockPlugin(SynapsePlugin):
        def get_slash_commands(self):
            return [{"name": "echo", "handler": lambda a: a, "description": "Echo"}]

    api = object()
    pm = PluginManager(api)
    pm.plugins["mock"] = MockPlugin(api)
    assert pm.handle_slash("echo", "hello") == "hello"
