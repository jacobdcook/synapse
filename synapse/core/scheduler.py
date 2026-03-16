import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)

TASKS_FILE = CONFIG_DIR / "scheduled_tasks.json"

class TaskScheduler(QObject):
    task_started = pyqtSignal(dict)
    task_finished = pyqtSignal(dict, str) # task, result

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tasks = []
        self._load_tasks()
        
        # Check every 60 seconds
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_tasks)

    def start(self):
        if not self.timer.isActive():
            self.timer.start(60000)
            log.info("Task scheduler started.")

    def _load_tasks(self):
        try:
            if TASKS_FILE.exists():
                with open(TASKS_FILE, "r") as f:
                    self.tasks = json.load(f)
        except Exception as e:
            log.error(f"Failed to load tasks: {e}")
            self.tasks = []

    def _save_tasks(self):
        try:
            TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=str(TASKS_FILE.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self.tasks, f, indent=2)
                os.replace(tmp_path, str(TASKS_FILE))
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            log.error(f"Failed to save tasks: {e}")

    def add_task(self, prompt, model, conversation_id, schedule_time):
        task = {
            "id": str(uuid.uuid4()),
            "prompt": prompt,
            "model": model,
            "conversation_id": conversation_id,
            "schedule_time": schedule_time, # ISO format
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.tasks.append(task)
        self._save_tasks()
        return task

    def remove_task(self, task_id):
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        self._save_tasks()

    def _check_tasks(self):
        now = datetime.now(timezone.utc)
        for task in self.tasks:
            if task["status"] == "pending":
                try:
                    sched_time = datetime.fromisoformat(task["schedule_time"])
                    if sched_time.tzinfo is None:
                        sched_time = sched_time.replace(tzinfo=timezone.utc)
                    if sched_time <= now:
                        self._execute_task(task)
                except Exception as e:
                    log.error(f"Error parsing schedule time for task {task['id']}: {e}")

    def _execute_task(self, task):
        task["status"] = "running"
        self._save_tasks()
        self.task_started.emit(task)
        
        # We'll need a way to run this in the background. 
        # For now, we'll just log that it SHOULD run.
        # Implementation of actual execution will happen in main.py via signal.
        log.info(f"Executing scheduled task: {task['id']}")

# Global instance
scheduler = TaskScheduler()
