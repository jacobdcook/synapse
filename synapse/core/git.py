import subprocess
import logging
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

log = logging.getLogger(__name__)


def is_git_repo(path):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, cwd=str(path), timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def git_branch(path):
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=str(path), timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def git_status(path):
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(path), timeout=10
        )
        if result.returncode != 0:
            return []
        entries = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            status = line[:2].strip()
            filepath = line[3:].strip()
            entries.append({"status": status, "file": filepath})
        return entries
    except Exception:
        return []


def git_diff(path, filepath=None):
    try:
        cmd = ["git", "diff"]
        if filepath:
            cmd.append(filepath)
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(path), timeout=10
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


def git_log(path, count=20):
    try:
        result = subprocess.run(
            ["git", "log", f"--max-count={count}", "--oneline", "--graph", "--decorate"],
            capture_output=True, text=True, cwd=str(path), timeout=10
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


def git_commit(path, message, files=None):
    try:
        if files:
            add_result = subprocess.run(["git", "add"] + files, cwd=str(path), timeout=10, capture_output=True, text=True)
        else:
            add_result = subprocess.run(["git", "add", "-A"], cwd=str(path), timeout=10, capture_output=True, text=True)
        if add_result.returncode != 0:
            return f"Git add failed (exit {add_result.returncode}): {add_result.stderr}"
        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True, text=True, cwd=str(path), timeout=30
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            return f"Commit failed (exit {result.returncode}): {output}"
        return output
    except Exception as e:
        return f"Error: {e}"


class GitStatusWorker(QThread):
    status_ready = pyqtSignal(str, list)  # branch, status_entries

    def __init__(self, workspace_dir):
        super().__init__()
        self.workspace_dir = workspace_dir

    def run(self):
        if not self.workspace_dir or not is_git_repo(self.workspace_dir):
            return
        branch = git_branch(self.workspace_dir)
        status = git_status(self.workspace_dir)
        self.status_ready.emit(branch, status)
