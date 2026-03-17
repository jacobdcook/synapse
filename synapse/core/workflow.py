import json
import logging
import os
import tempfile
import uuid
import re
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, QThread

log = logging.getLogger(__name__)

class WorkflowNode:
    def __init__(self, name=None, model=None, prompt_template=None):
        self.id = str(uuid.uuid4())
        self.name = name or "New Step"
        self.model = model or ""
        self.prompt_template = prompt_template or ""
        self.output = ""

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "model": self.model,
            "prompt_template": self.prompt_template
        }

    @classmethod
    def from_dict(cls, data):
        node = cls(data.get("name"), data.get("model"), data.get("prompt_template"))
        node.id = data.get("id", node.id)
        return node

class Workflow:
    def __init__(self, name="New Workflow"):
        self.id = str(uuid.uuid4())
        self.name = name
        self.nodes = [] # List of WorkflowNode

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes]
        }

    @classmethod
    def from_dict(cls, data):
        wf = cls(data.get("name", "New Workflow"))
        wf.id = data.get("id", wf.id)
        wf.nodes = [WorkflowNode.from_dict(n) for n in data.get("nodes", [])]
        return wf

class WorkflowExecutor(QThread):
    node_started = pyqtSignal(int, str) # index, node_name
    node_finished = pyqtSignal(int, str) # index, output
    node_error = pyqtSignal(int, str) # index, error
    workflow_finished = pyqtSignal(str) # final output or summary

    def __init__(self, workflow, api_worker_factory):
        super().__init__()
        self.workflow = workflow
        self.worker_factory = api_worker_factory
        self.context = {} # Shared state between nodes

    def run(self):
        log.info(f"Starting workflow: {self.workflow.name}")
        last_output = ""
        
        for i, node in enumerate(self.workflow.nodes):
            self.node_started.emit(i, node.name)
            
            # Resolve variables in prompt
            prompt = self._resolve_variables(node.prompt_template, last_output)
            
            try:
                # In a real sync-to-async bridge, we'd wait for the worker
                # For now, we'll simulate the blocking call if possible or use a promise-like wait
                output = self._run_node_sync(node.model, prompt)
                node.output = output
                last_output = output
                self.context[node.name] = output # Allow named reference like {{Step Name}}
                self.node_finished.emit(i, output)
            except Exception as e:
                log.error(f"Workflow error at node {node.name}: {e}")
                self.node_error.emit(i, str(e))
                return

        self.workflow_finished.emit(last_output)

    def _resolve_variables(self, template, last_output):
        resolved = template
        # Handle {{last}}
        resolved = resolved.replace("{{last}}", last_output)
        # Handle {{input}} (if we add global input later)
        
        # Handle {{Node Name}}
        for name, output in self.context.items():
            resolved = resolved.replace(f"{{{{{name}}}}}", output)
            
        return resolved

    def _run_node_sync(self, model, prompt):
        from .api import WorkerFactory
        from PyQt5.QtCore import QEventLoop, QTimer

        loop = QEventLoop()
        result_container = {"text": "", "error": None}

        def on_done(text, stats):
            result_container["text"] = text
            loop.quit()

        def on_error(err):
            result_container["error"] = err
            loop.quit()

        def on_timeout():
            result_container["error"] = "Workflow node timed out (120s)"
            loop.quit()

        messages = [{"role": "user", "content": prompt}]
        worker = WorkerFactory(model, messages)
        worker.response_finished.connect(on_done)
        worker.error_occurred.connect(on_error)
        worker.start()

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(on_timeout)
        timer.start(120000)
        loop.exec_()
        timer.stop()

        if result_container["error"]:
            raise Exception(result_container["error"])
        return result_container["text"]

class WorkflowManager:
    def __init__(self):
        self.workflows_path = Path.home() / ".local" / "share" / "synapse" / "workflows.json"
        self.workflows = self._load()

    def _load(self):
        if not self.workflows_path.exists():
            return []
        try:
            data = json.loads(self.workflows_path.read_text())
            return [Workflow.from_dict(w) for w in data]
        except Exception as e:
            log.error(f"Failed to load workflows: {e}")
            return []

    def save(self):
        try:
            self.workflows_path.parent.mkdir(parents=True, exist_ok=True)
            data = [w.to_dict() for w in self.workflows]
            fd, tmp_path = tempfile.mkstemp(dir=str(self.workflows_path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(data, f, indent=2)
                os.replace(tmp_path, str(self.workflows_path))
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            log.error(f"Failed to save workflows: {e}")

    def add_workflow(self, workflow):
        self.workflows.append(workflow)
        self.save()

    def remove_workflow(self, workflow_id):
        self.workflows = [w for w in self.workflows if w.id != workflow_id]
        self.save()
