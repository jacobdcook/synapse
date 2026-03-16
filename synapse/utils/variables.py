import re
import os
import platform
from datetime import datetime
from PyQt5.QtWidgets import QApplication

class VariableResolver:
    """Resolves {{variable}} patterns in text."""

    def __init__(self, workspace_path=None):
        self.workspace_path = workspace_path

    def get_built_in_vars(self):
        """Returns a dict of built-in variables and their values."""
        now = datetime.now()
        
        # Get clipboard text
        clipboard = QApplication.clipboard().text()
        
        return {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "clipboard": clipboard,
            "os": platform.system(),
            "project_name": os.path.basename(self.workspace_path) if self.workspace_path else "Synapse",
        }

    def find_variables(self, text):
        """Returns a set of all {{variable}} names found in the text."""
        return set(re.findall(r'\{\{(.*?)\}\}', text))

    def resolve_built_ins(self, text):
        """Resolves only the built-in variables in the text."""
        built_ins = self.get_built_in_vars()
        resolved = text
        for name, val in built_ins.items():
            resolved = resolved.replace(f"{{{{{name}}}}}", str(val))
        return resolved

    def resolve_all(self, text, user_vars):
        """Resolves both built-in and user-provided variables."""
        # First resolve user vars so they can potentially contain built-ins (unlikely but possible)
        resolved = text
        for name, val in user_vars.items():
            resolved = resolved.replace(f"{{{{{name}}}}}", str(val))
            
        # Then resolve built-ins
        return self.resolve_built_ins(resolved)
