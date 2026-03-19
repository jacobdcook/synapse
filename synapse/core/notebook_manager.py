import sys
import json
import logging
import subprocess
import threading
import queue
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt5.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

class NotebookCell:
    def __init__(self, cell_id: str, cell_type: str = "code", source: str = ""):
        self.id = cell_id
        self.type = cell_type # "code" or "markdown"
        self.source = source
        self.outputs = []
        self.execution_count = None

class NotebookKernel(QObject):
    output_received = pyqtSignal(str, str) # cell_id, text
    error_received = pyqtSignal(str, str) # cell_id, error
    finished = pyqtSignal(str, int) # cell_id, execution_count

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: Optional[subprocess.Popen] = None
        self.execution_queue = queue.Queue()
        self.is_running = False
        self.execution_counter = 0

    def start(self):
        if self.is_running:
            return
        
        # In a real implementation, this would use jupyter_client or similar.
        # Here we simulate a simple persistent Python REPL.
        self.process = subprocess.Popen(
            [sys.executable, "-i", "-u"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self.is_running = True
        threading.Thread(target=self._listen_stdout, daemon=True).start()
        threading.Thread(target=self._listen_stderr, daemon=True).start()
        log.info("Notebook kernel started")

    def stop(self):
        if self.process:
            self.process.terminate()
            self.is_running = False
            log.info("Notebook kernel stopped")

    def execute(self, cell_id: str, code: str):
        self.execution_counter += 1
        self.execution_queue.put((cell_id, code, self.execution_counter))
        threading.Thread(target=self._execution_thread, daemon=True).start()

    def _execution_thread(self):
        try:
            cell_id, code, count = self.execution_queue.get(timeout=1)
            if self.process and self.process.stdin:
                # Wrap code to print a sentinel for end-of-execution
                sentinel = f"__SYN_EXEC_DONE_{count}__"
                full_code = f"{code}\nprint('{sentinel}')\n"
                self.process.stdin.write(full_code)
                self.process.stdin.flush()
                # The output listener will handle emitting signals
                # We wait for the sentinel in a simplified way here
                # (In production, this would be much more robust)
        except queue.Empty:
            pass

    def _listen_stdout(self):
        if not self.process: return
        for line in iter(self.process.stdout.readline, ""):
            if "__SYN_EXEC_DONE_" in line:
                # Cell execution finished
                try:
                    count = int(line.split("_")[-1].strip())
                    # How to map back to cell_id? Simplified for now.
                    self.finished.emit("unknown", count)
                except Exception as e:
                    log.warning(f"Kernel execute error: {e}")
                continue
            self.output_received.emit("unknown", line)

    def _listen_stderr(self):
        if not self.process: return
        for line in iter(self.process.stderr.readline, ""):
            self.error_received.emit("unknown", line)

class NotebookManager(QObject):
    def __init__(self, workspace_root: str):
        super().__init__()
        self.workspace_root = workspace_root
        self.kernel = NotebookKernel()
        self.current_notebook: List[NotebookCell] = []
        self._exec_namespace: Dict[str, Any] = {}

    def execute_cell_subprocess(self, code: str) -> tuple:
        """Execute code via python -c, return (stdout, stderr, success)."""
        try:
            r = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, timeout=60,
                cwd=self.workspace_root or "."
            )
            return r.stdout, r.stderr, r.returncode == 0
        except Exception as e:
            return "", str(e), False

    def get_variable_inspector(self) -> Dict[str, str]:
        """Return dict of var name -> repr(value) from exec namespace."""
        return {k: repr(v)[:200] for k, v in self._exec_namespace.items() if not k.startswith("_")}

    def export_to_py(self, cells: List[NotebookCell], filepath: str):
        lines = []
        for c in cells:
            if c.type == "code":
                lines.append(c.source)
                lines.append("")
            else:
                lines.append(f'# {c.source.replace(chr(10), " ")}')
        Path(filepath).write_text("\n".join(lines), encoding="utf-8")

    def export_to_html(self, cells: List[NotebookCell], filepath: str):
        html = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
        for c in cells:
            if c.type == "markdown":
                html.append(f"<div class='md'>{c.source.replace('<', '&lt;')}</div>")
            else:
                html.append(f"<pre><code>{c.source.replace('<', '&lt;')}</code></pre>")
        html.append("</body></html>")
        Path(filepath).write_text("\n".join(html), encoding="utf-8")

    def load_notebook(self, filepath: str) -> List[NotebookCell]:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                cells = []
                # Support both .ipynb and .synb (simple format)
                raw_cells = data.get("cells", [])
                for i, c in enumerate(raw_cells):
                    cell_type = c.get("cell_type", "code")
                    source = "".join(c.get("source", []))
                    cell = NotebookCell(str(i), cell_type, source)
                    cells.append(cell)
                self.current_notebook = cells
                return cells
        except Exception as e:
            log.error(f"Failed to load notebook {filepath}: {e}")
            return []

    def save_notebook(self, filepath: str, cells: List[NotebookCell]):
        data = {
            "cells": [
                {
                    "cell_type": c.type,
                    "source": c.source.splitlines(keepends=True),
                    "execution_count": c.execution_count,
                    "outputs": c.outputs
                } for c in cells
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5
        }
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save notebook {filepath}: {e}")
