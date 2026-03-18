import os
import sys
import importlib.util
import logging
import json
from typing import Dict, Any, List, Optional, Set
from PyQt5.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)
from ..utils.constants import PLUGINS_DIR, PLUGIN_SETTINGS_FILE

class SynapsePlugin:
    """Base class for all Synapse plugins."""
    def __init__(self, api: Any):
        self.api = api
        self.name = "Unknown Plugin"
        self.version = "0.1.0"
        self.description = ""

    def activate(self):
        """Called when the plugin is enabled."""
        pass

    def deactivate(self):
        """Called when the plugin is disabled."""
        pass

class PluginManager(QObject):
    plugin_loaded = pyqtSignal(str) # name
    plugin_unloaded = pyqtSignal(str) # name

    def __init__(self, api: Any):
        super().__init__()
        self.api = api
        self.plugins: Dict[str, SynapsePlugin] = {}
        self.plugin_dir = str(PLUGINS_DIR)
        self.settings_file = str(PLUGIN_SETTINGS_FILE)
        
        if not os.path.exists(self.plugin_dir):
            os.makedirs(self.plugin_dir)
            
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                log.error(f"Failed to load plugin settings: {e}")
        return {"enabled_plugins": []}

    def _save_settings(self):
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            log.error(f"Failed to save plugin settings: {e}")

    def discover_plugins(self):
        """Scan the plugin directory for .py files."""
        if not os.path.exists(self.plugin_dir):
            return

        enabled_list = self.settings.get("enabled_plugins", [])
        
        # On first run or if empty, we might want to enable everything found?
        # For now, let's treat the settings as the source of truth.
        # If a plugin is in the directory but NOT in settings, it's newly discovered.
        
        for filename in os.listdir(self.plugin_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = os.path.splitext(filename)[0]
                if module_name in enabled_list or not enabled_list:
                    # If enabled_list is empty, we auto-enable found plugins (first run behavior)
                    if module_name not in enabled_list:
                        enabled_list.append(module_name)
                    
                    plugin_path = os.path.join(self.plugin_dir, filename)
                    self.load_plugin(plugin_path)
        
        self.settings["enabled_plugins"] = enabled_list
        self._save_settings()

    def load_plugin(self, path: str):
        """Dynamically load a plugin from a file path."""
        try:
            module_name = os.path.basename(path)[:-3]
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                # Look for a class that inherits from SynapsePlugin
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, SynapsePlugin) and 
                        attr is not SynapsePlugin):
                        
                        plugin_instance = attr(self.api)
                        self.plugins[module_name] = plugin_instance
                        plugin_instance.activate()
                        self.plugin_loaded.emit(plugin_instance.name)
                        log.info(f"Loaded plugin: {plugin_instance.name} ({module_name})")
                        return
        except Exception as e:
            log.error(f"Failed to load plugin from {path}: {e}")

    def unload_plugin(self, module_name: str):
        """Deactivate and remove a plugin by its module name."""
        if module_name in self.plugins:
            try:
                plugin = self.plugins[module_name]
                plugin.deactivate()
                del self.plugins[module_name]
                self.plugin_unloaded.emit(plugin.name)
                log.info(f"Unloaded plugin: {plugin.name} ({module_name})")
            except Exception as e:
                log.error(f"Failed to unload plugin {module_name}: {e}")

    def enable_plugin(self, module_name: str):
        """Enable and load a plugin."""
        enabled_list = self.settings.get("enabled_plugins", [])
        if module_name not in enabled_list:
            enabled_list.append(module_name)
            self.settings["enabled_plugins"] = enabled_list
            self._save_settings()
            
            plugin_path = os.path.join(self.plugin_dir, f"{module_name}.py")
            if os.path.exists(plugin_path):
                self.load_plugin(plugin_path)

    def disable_plugin(self, module_name: str):
        """Disable and unload a plugin."""
        enabled_list = self.settings.get("enabled_plugins", [])
        if module_name in enabled_list:
            enabled_list.remove(module_name)
            self.settings["enabled_plugins"] = enabled_list
            self._save_settings()
            self.unload_plugin(module_name)

    def uninstall_plugin(self, module_name: str):
        """Unload and delete a plugin's source file."""
        self.disable_plugin(module_name)
        plugin_path = os.path.join(self.plugin_dir, f"{module_name}.py")
        if os.path.exists(plugin_path):
            try:
                os.remove(plugin_path)
                log.info(f"Uninstalled plugin (deleted file): {module_name}")
            except Exception as e:
                log.error(f"Failed to delete plugin file {module_name}: {e}")

    def get_available_plugins(self) -> List[Dict[str, str]]:
        """Return info about all .py files in the plugin directory."""
        available = []
        if os.path.exists(self.plugin_dir):
            for filename in os.listdir(self.plugin_dir):
                if filename.endswith(".py") and not filename.startswith("__"):
                    module_name = filename[:-3]
                    # We might want to peek into the file for name/description?
                    # For now, just return basic info.
                    plugin_instance = self.plugins.get(module_name)
                    available.append({
                        "id": module_name,
                        "name": plugin_instance.name if plugin_instance else module_name.replace("_", " ").title(),
                        "enabled": module_name in self.settings.get("enabled_plugins", []),
                        "description": plugin_instance.description if plugin_instance else "No description available."
                    })
        return available

    def get_active_plugins(self) -> List[SynapsePlugin]:
        return list(self.plugins.values())
