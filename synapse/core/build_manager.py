import os
import json
import logging
from typing import List, Dict, Any, Optional
from PyQt5.QtCore import QObject, pyqtSignal, QProcess

log = logging.getLogger(__name__)

class BuildTaskManager(QObject):
    task_started = pyqtSignal(str) # task_id
    task_finished = pyqtSignal(str, int) # task_id, exit_code
    task_output = pyqtSignal(str, str) # task_id, output
    tasks_loaded = pyqtSignal(list)

    def __init__(self, workspace_root: str):
        super().__init__()
        self.workspace_root = workspace_root
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._processes: Dict[str, QProcess] = {}

    def load_tasks(self):
        """Loads tasks from .synapse/tasks.json or other sources."""
        self.tasks = {}
        
        # 1. Look for .synapse/tasks.json
        synapse_tasks_path = os.path.join(self.workspace_root, ".synapse", "tasks.json")
        if os.path.exists(synapse_tasks_path):
            try:
                with open(synapse_tasks_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for task in data:
                            tid = task.get("id")
                            if tid:
                                self.tasks[tid] = task
                    elif isinstance(data, dict):
                        self.tasks.update(data)
            except Exception as e:
                log.error(f"Failed to load tasks from {synapse_tasks_path}: {e}")

        # 2. Look for package.json (Node.js)
        package_json_path = os.path.join(self.workspace_root, "package.json")
        if os.path.exists(package_json_path):
            try:
                with open(package_json_path, 'r') as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})
                    for name, cmd in scripts.items():
                        tid = f"npm:{name}"
                        self.tasks[tid] = {
                            "id": tid,
                            "name": name,
                            "command": f"npm run {name}",
                            "type": "npm"
                        }
            except Exception as e:
                log.error(f"Failed to load tasks from {package_json_path}: {e}")

        # 3. Look for Makefile
        makefile_path = os.path.join(self.workspace_root, "Makefile")
        if os.path.exists(makefile_path):
            # Simple heuristic for Makefile targets
            try:
                with open(makefile_path, 'r') as f:
                    for line in f:
                        if line and line[0].isalpha() and ':' in line and not line.startswith('.'):
                            target = line.split(':')[0].strip()
                            tid = f"make:{target}"
                            self.tasks[tid] = {
                                "id": tid,
                                "name": target,
                                "command": f"make {target}",
                                "type": "make"
                            }
            except Exception as e:
                log.error(f"Failed to load tasks from {makefile_path}: {e}")

        self.tasks_loaded.emit(list(self.tasks.values()))

    def run_task(self, task_id: str):
        if task_id not in self.tasks:
            log.error(f"Task {task_id} not found")
            return

        if task_id in self._processes and self._processes[task_id].state() != QProcess.NotRunning:
            log.warning(f"Task {task_id} is already running")
            return

        task = self.tasks[task_id]
        command = task.get("command")
        if not command:
            log.error(f"Task {task_id} has no command")
            return

        process = QProcess(self)
        process.setWorkingDirectory(self.workspace_root)
        
        # Use shell execution if needed, otherwise split
        # For simplicity, we'll use a bash -c wrapper for complex strings
        process.setProgram("/bin/bash")
        process.setArguments(["-c", command])

        process.readyReadStandardOutput.connect(lambda: self._handle_output(task_id, process))
        process.readyReadStandardError.connect(lambda: self._handle_output(task_id, process))
        process.finished.connect(lambda exit_code, exit_status: self._handle_finished(task_id, exit_code))

        self._processes[task_id] = process
        process.start()
        self.task_started.emit(task_id)

    def stop_task(self, task_id: str):
        if task_id in self._processes:
            self._processes[task_id].terminate()
            if not self._processes[task_id].waitForFinished(2000):
                self._processes[task_id].kill()

    def _handle_output(self, task_id, process):
        data = process.readAllStandardOutput().data().decode()
        err_data = process.readAllStandardError().data().decode()
        combined = data + err_data
        if combined:
            self.task_output.emit(task_id, combined)

    def _handle_finished(self, task_id, exit_code):
        self.task_finished.emit(task_id, exit_code)
        if task_id in self._processes:
            del self._processes[task_id]
