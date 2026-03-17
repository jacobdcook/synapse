import json
import os
import tempfile
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# Constants for task states
TODO = "todo"
DOING = "doing"
DONE = "done"

class TaskManager:
    """Manages global tasks for the Delegative Board."""
    
    def __init__(self, config_dir):
        self.config_dir = Path(config_dir)
        self.tasks_file = self.config_dir / "tasks.json"
        self.tasks = []
        self._load()

    def _load(self):
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file, "r") as f:
                    self.tasks = json.load(f)
            except Exception as e:
                log.error(f"Failed to load tasks: {e}")
                self.tasks = []
        else:
            self.tasks = []

    def save(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=str(self.config_dir), suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self.tasks, f, indent=2)
                os.replace(tmp_path, str(self.tasks_file))
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            log.error(f"Failed to save tasks: {e}")

    def add_task(self, title, description="", agent_id=None, priority="Medium"):
        task = {
            "id": str(uuid.uuid4()),
            "title": title,
            "description": description,
            "status": TODO,
            "agent_id": agent_id,
            "priority": priority,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "progress": 0,
            "subtasks": []
        }
        self.tasks.append(task)
        self.save()
        return task

    def update_task(self, task_id, **kwargs):
        for task in self.tasks:
            if task["id"] == task_id:
                for k, v in kwargs.items():
                    task[k] = v
                task["updated_at"] = datetime.now(timezone.utc).isoformat()
                self.save()
                return task
        return None

    def delete_task(self, task_id):
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        self.save()

    def get_tasks_by_status(self, status):
        return [t for t in self.tasks if t["status"] == status]

    def move_task(self, task_id, new_status):
        return self.update_task(task_id, status=new_status)
