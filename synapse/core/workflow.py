import json
import logging
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
        # We need to bridge to the AI Worker and wait for result
        # This is tricky because Workers are usually QThreads.
        # We'll use a local event loop or a simple wait.
        from .api import WorkerFactory
        
        # Mocking the sync wait for now - in reality, we'd need to connect signals
        # and use a QEventLoop to block without freezing.
        # But since we're IN a QThread already (WorkflowExecutor), we can wait.
        
        result_container = {"text": "", "error": None, "done": False}
        
        def on_done(text, stats):
            result_container["text"] = text
            result_container["done"] = True
            
        def on_error(err):
            result_container["error"] = err
            result_container["done"] = True

        # Note: messages list for single prompt
        messages = [{"role": "user", "content": prompt}]
        
        # We must create worker in this thread to wait for it or ensure signal delivery
        worker = WorkerFactory(model, messages)
        worker.response_finished.connect(on_done)
        worker.error_occurred.connect(on_error)
        worker.start()
        
        while not result_container["done"]:
            self.msleep(100) # Wait in 100ms chunks
            
        if result_container["error"]:
            raise Exception(result_container["error"])
            
        return result_container["text"]

class WorkflowManager:
    def __init__(self):
        self.workflows_path = Path.home() / ".synapse" / "workflows.json"
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
            self.workflows_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            log.error(f"Failed to save workflows: {e}")

    def add_workflow(self, workflow):
        self.workflows.append(workflow)
        self.save()

    def remove_workflow(self, workflow_id):
        self.workflows = [w for w in self.workflows if w.id != workflow_id]
        self.save()
