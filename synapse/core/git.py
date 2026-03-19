import subprocess
import re
import logging
from pathlib import Path
from typing import List, Optional
from PyQt5.QtCore import QThread, pyqtSignal

log = logging.getLogger(__name__)

DiffHunk = dict
GraphNode = dict
BlameLine = dict


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


def stage_file(path, filepath):
    try:
        r = subprocess.run(["git", "add", filepath], cwd=str(path), capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def unstage_file(path, filepath):
    try:
        r = subprocess.run(["git", "reset", "HEAD", "--", filepath], cwd=str(path), capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def stage_hunk(path, filepath, hunk_header):
    try:
        r = subprocess.run(
            ["git", "apply", "--cached", "--allow-overlap"],
            input=hunk_header, cwd=str(path), capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception:
        return False


def get_file_diff(path, filepath, staged=False) -> List[DiffHunk]:
    try:
        cmd = ["git", "diff", "--no-color"]
        if staged:
            cmd.append("--cached")
        cmd.append("--")
        cmd.append(filepath)
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(path), timeout=10)
        if r.returncode != 0:
            return []
        return _parse_diff_hunks(r.stdout)
    except Exception:
        return []


def _parse_diff_hunks(diff_text):
    hunks = []
    for m in re.finditer(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*?)(?=@@|\Z)", diff_text, re.DOTALL):
        old_start = int(m.group(1))
        old_count = int(m.group(2) or 1)
        new_start = int(m.group(3))
        new_count = int(m.group(4) or 1)
        body = m.group(5).strip()
        lines = [ln for ln in body.split("\n") if ln]
        hunks.append({
            "old_start": old_start, "old_count": old_count,
            "new_start": new_start, "new_count": new_count,
            "lines": lines
        })
    return hunks


def get_branch_graph(path) -> List[GraphNode]:
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", "--graph", "--decorate", "-20", "--format=%h %s %d"],
            capture_output=True, text=True, cwd=str(path), timeout=10
        )
        if r.returncode != 0:
            return []
        nodes = []
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            nodes.append({"text": line.strip(), "hash": line.split()[0] if line.split() else ""})
        return nodes
    except Exception:
        return []


def stash_save(path, message=""):
    try:
        cmd = ["git", "stash", "push", "-m", message] if message else ["git", "stash", "push"]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(path), timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def stash_pop(path):
    try:
        r = subprocess.run(["git", "stash", "pop"], capture_output=True, text=True, cwd=str(path), timeout=10)
        return r.returncode == 0, r.stdout + r.stderr
    except Exception as e:
        return False, str(e)


def stash_list(path) -> List[dict]:
    try:
        r = subprocess.run(["git", "stash", "list"], capture_output=True, text=True, cwd=str(path), timeout=10)
        if r.returncode != 0:
            return []
        entries = []
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            m = re.match(r"stash@\{(\d+)\}: (.*)", line.strip())
            ref = m.group(1) if m else "0"
            msg = m.group(2) if m else line
            entries.append({"ref": f"stash@{{{ref}}}", "message": msg})
        return entries
    except Exception:
        return []


def blame(path, filepath) -> List[BlameLine]:
    try:
        r = subprocess.run(
            ["git", "blame", "-l", "-w", "--line-porcelain", filepath],
            capture_output=True, text=True, cwd=str(path), timeout=15
        )
        if r.returncode != 0:
            return []
        lines = []
        current = {}
        for line in r.stdout.split("\n"):
            if line.startswith("\t"):
                current["content"] = line[1:]
                lines.append(dict(current))
                current = {}
            elif line.startswith("author "):
                current["author"] = line[7:]
            elif line.startswith("committer-time "):
                current["time"] = line[15:]
            elif line.startswith("summary "):
                current["summary"] = line[8:]
        return lines
    except Exception:
        return []


def git_branches(path):
    try:
        r = subprocess.run(["git", "branch", "-a"], capture_output=True, text=True, cwd=str(path), timeout=10)
        if r.returncode != 0:
            return []
        branches = []
        current = git_branch(path)
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            is_current = line.startswith("*")
            name = line.lstrip("* ").strip()
            if name.startswith("remotes/"):
                continue
            branches.append({"name": name, "current": name == current})
        return branches
    except Exception:
        return []


def git_switch_branch(path, branch_name):
    try:
        r = subprocess.run(["git", "checkout", branch_name], capture_output=True, text=True, cwd=str(path), timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def git_create_branch(path, branch_name):
    try:
        r = subprocess.run(["git", "branch", branch_name], capture_output=True, text=True, cwd=str(path), timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def git_delete_branch(path, branch_name):
    try:
        r = subprocess.run(["git", "branch", "-d", branch_name], capture_output=True, text=True, cwd=str(path), timeout=10)
        return r.returncode == 0
    except Exception:
        return False


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


def git_remote(path):
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=str(path), timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


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


class GitRemoteService(QThread):
    prs_ready = pyqtSignal(list)
    issues_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, workspace_dir):
        super().__init__()
        self.workspace_dir = workspace_dir
        self.token = ""
        self.provider = "github" # default
        self.repo_full_name = "" # e.g. "owner/repo"
        self._action = "" # "list_prs", "list_issues"

    def set_config(self, token, provider="github"):
        self.token = token
        self.provider = provider

    def fetch_prs(self):
        self._action = "list_prs"
        self.start()

    def fetch_issues(self):
        self._action = "list_issues"
        self.start()

    def run(self):
        import requests
        remote_url = git_remote(self.workspace_dir)
        if not remote_url:
            self.error_occurred.emit("No remote URL found (origin)")
            return

        # Simple repo name extraction
        # Handle https://github.com/owner/repo.git or git@github.com:owner/repo.git
        if "github.com" in remote_url:
            self.provider = "github"
            if "https://" in remote_url:
                self.repo_full_name = remote_url.split("github.com/")[-1].replace(".git", "")
            else:
                self.repo_full_name = remote_url.split(":")[-1].replace(".git", "")
        elif "gitlab.com" in remote_url:
            self.provider = "gitlab"
            if "https://" in remote_url:
                self.repo_full_name = remote_url.split("gitlab.com/")[-1].replace(".git", "")
            else:
                self.repo_full_name = remote_url.split(":")[-1].replace(".git", "")
            # GitLab API uses URL-encoded path
            self.repo_full_name = self.repo_full_name.replace("/", "%2F")

        try:
            if self._action == "list_prs":
                if self.provider == "github":
                    url = f"https://api.github.com/repos/{self.repo_full_name}/pulls"
                    headers = {"Authorization": f"token {self.token}"} if self.token else {}
                    r = requests.get(url, headers=headers, timeout=10)
                else: # gitlab
                    url = f"https://gitlab.com/api/v4/projects/{self.repo_full_name}/merge_requests"
                    headers = {"PRIVATE-TOKEN": self.token} if self.token else {}
                    r = requests.get(url, headers=headers, timeout=10)
                
                r.raise_for_status()
                data = r.json()
                prs = []
                for item in data:
                    prs.append({
                        "id": item.get("id") or item.get("iid"),
                        "title": item.get("title"),
                        "number": item.get("number") or item.get("iid"),
                        "author": (item.get("user") or item.get("author", {})).get("login") or item.get("author", {}).get("username"),
                        "url": item.get("html_url") or item.get("web_url"),
                        "state": item.get("state")
                    })
                self.prs_ready.emit(prs)

            elif self._action == "list_issues":
                if self.provider == "github":
                    url = f"https://api.github.com/repos/{self.repo_full_name}/issues"
                    headers = {"Authorization": f"token {self.token}"} if self.token else {}
                    r = requests.get(url, headers=headers, timeout=10)
                else: # gitlab
                    url = f"https://gitlab.com/api/v4/projects/{self.repo_full_name}/issues"
                    headers = {"PRIVATE-TOKEN": self.token} if self.token else {}
                    r = requests.get(url, headers=headers, timeout=10)
                
                r.raise_for_status()
                data = r.json()
                issues = []
                for item in data:
                    # GitHub API includes PRs in issues, so we need to filter
                    if self.provider == "github" and "pull_request" in item:
                        continue
                    issues.append({
                        "id": item.get("id") or item.get("iid"),
                        "title": item.get("title"),
                        "number": item.get("number") or item.get("iid"),
                        "author": (item.get("user") or item.get("author", {})).get("login") or item.get("author", {}).get("username"),
                        "url": item.get("html_url") or item.get("web_url"),
                        "state": item.get("state")
                    })
                self.issues_ready.emit(issues)

        except Exception as e:
            self.error_occurred.emit(str(e))
