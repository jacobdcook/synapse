import os
import subprocess
import json
import logging
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name, func, description, parameters):
        self._tools[name] = {
            "function": func,
            "description": description,
            "parameters": parameters
        }

    def get_tool_definitions(self):
        definitions = []
        for name, tool in self._tools.items():
            definitions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
        return definitions

    def execute(self, name, arguments):
        if name not in self._tools:
            return None

        try:
            return self._tools[name]["function"](**arguments)
        except Exception as e:
            return f"Error executing '{name}': {str(e)}"

class ToolExecutor(QObject):
    approval_requested = pyqtSignal(str, dict) # tool_name, arguments
    execution_finished = pyqtSignal(str) # result

    def __init__(self, workspace_dir=None):
        super().__init__()
        self.workspace_dir = Path(workspace_dir) if workspace_dir else None
        self.registry = ToolRegistry()
        self._setup_default_tools()

    def _setup_default_tools(self):
        self.registry.register(
            "read_file",
            self._read_file,
            "Read the contents of a file in the workspace.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the file."}
                },
                "required": ["path"]
            }
        )
        self.registry.register(
            "write_file",
            self._write_file,
            "Write or overwrite a file in the workspace.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the file."},
                    "content": {"type": "string", "description": "Content to write."}
                },
                "required": ["path", "content"]
            }
        )
        self.registry.register(
            "run_command",
            self._run_command,
            "Run a terminal command. Use with caution.",
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run."}
                },
                "required": ["command"]
            }
        )

    def _validate_path(self, path):
        if not self.workspace_dir:
            return None, "Error: No workspace open."
        full_path = (self.workspace_dir / path).resolve()
        ws_resolved = self.workspace_dir.resolve()
        if not str(full_path).startswith(str(ws_resolved)):
            return None, f"Error: Path '{path}' escapes workspace boundary."
        return full_path, None

    def _read_file(self, path):
        full_path, err = self._validate_path(path)
        if err:
            return err
        try:
            return full_path.read_text(errors='replace')
        except Exception as e:
            return f"Error reading file {path}: {e}"

    def _write_file(self, path, content):
        full_path, err = self._validate_path(path)
        if err:
            return err
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            return f"Successfully wrote {path}"
        except Exception as e:
            return f"Error writing file {path}: {e}"

    def _run_command(self, command):
        import shlex
        try:
            args = shlex.split(command)
            result = subprocess.run(
                args, capture_output=True, text=True,
                cwd=str(self.workspace_dir) if self.workspace_dir else None,
                timeout=60
            )
            output = result.stdout
            if result.stderr:
                output += "\nErrors:\n" + result.stderr
            return f"Exit code {result.returncode}\nOutput:\n{output}"
        except Exception as e:
            return f"Error running command: {e}"

    def request_approval(self, name, arguments):
        # In a real app, this would show a dialog.
        # For now, we signal it.
        self.approval_requested.emit(name, arguments)
