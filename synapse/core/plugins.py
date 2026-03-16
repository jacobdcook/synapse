import os
import importlib.util
import logging
from pathlib import Path
from PyQt5.QtCore import QFileSystemWatcher

log = logging.getLogger(__name__)

PLUGIN_DIR = Path.home() / ".local" / "share" / "synapse" / "plugins"
PLUGIN_DIR.mkdir(parents=True, exist_ok=True)


class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.tools = {}
        self.slash_commands = {}
        self.failed_plugins = []
        self.watcher = QFileSystemWatcher()
        self.watcher.directoryChanged.connect(self._on_dir_changed)
        if PLUGIN_DIR.exists():
            self.watcher.addPath(str(PLUGIN_DIR))

    def load_all(self):
        if not PLUGIN_DIR.exists():
            return
        for f in PLUGIN_DIR.glob("*.py"):
            self._load_plugin(f)

    def _load_plugin(self, path):
        name = path.stem
        try:
            spec = importlib.util.spec_from_file_location(f"synapse_plugin_{name}", str(path))
            if not spec or not spec.loader:
                return
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "register"):
                ctx = PluginContext(name)
                module.register(ctx)
                self.plugins[name] = module
                self.tools.update(ctx._tools)
                self.slash_commands.update(ctx._commands)
                log.info(f"Loaded plugin: {name}")
        except Exception as e:
            log.error(f"Failed to load plugin {name}: {e}")
            self.failed_plugins.append({"name": name, "error": str(e)})

    def _on_dir_changed(self, path):
        self.plugins.clear()
        self.tools.clear()
        self.slash_commands.clear()
        self.failed_plugins.clear()
        self.load_all()
        log.info("Plugins reloaded due to directory change")

    def get_tool_definitions(self):
        defs = []
        for name, tool in self.tools.items():
            defs.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {"type": "object", "properties": {}})
                }
            })
        return defs

    def execute_tool(self, name, args):
        if name in self.tools:
            try:
                return self.tools[name]["function"](**args)
            except Exception as e:
                return f"Plugin tool error: {e}"
        return None

    def handle_slash(self, cmd, args_str):
        if cmd in self.slash_commands:
            try:
                return self.slash_commands[cmd](args_str)
            except Exception as e:
                return f"Plugin command error: {e}"
        return None


class PluginContext:
    def __init__(self, name):
        self.name = name
        self._tools = {}
        self._commands = {}

    def register_tool(self, name, func, description="", parameters=None):
        self._tools[name] = {
            "function": func,
            "description": description,
            "parameters": parameters or {"type": "object", "properties": {}}
        }

    def register_command(self, name, func):
        self._commands[name] = func
