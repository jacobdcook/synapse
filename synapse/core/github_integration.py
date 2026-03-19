"""GitHub integration via gh CLI."""
__all__ = ["list_prs", "get_pr_diff", "create_review", "list_issues"]

import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

log = logging.getLogger(__name__)


def _run_gh(*args: str, cwd: Optional[Path] = None) -> Optional[Dict]:
    try:
        out = subprocess.run(
            ["gh", *args, "--json", "body,title,state,additions,deletions,files"],
            capture_output=True, text=True, timeout=30, cwd=cwd
        )
        if out.returncode != 0:
            return None
        return json.loads(out.stdout) if out.stdout.strip() else {}
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        log.warning(f"gh CLI error: {e}")
        return None


def list_prs(repo: Optional[str] = None, state: str = "open") -> List[Dict]:
    args = ["pr", "list", "--state", state]
    if repo:
        args.extend(["--repo", repo])
    out = subprocess.run(["gh", *args, "--json", "number,title,state,author"], capture_output=True, text=True, timeout=15)
    if out.returncode != 0:
        return []
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return []


def get_pr_diff(pr_number: int, repo: Optional[str] = None) -> Optional[str]:
    args = ["pr", "diff", str(pr_number)]
    if repo:
        args.extend(["--repo", repo])
    out = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60)
    return out.stdout if out.returncode == 0 else None


def create_review(pr_number: int, body: str, event: str = "COMMENT", repo: Optional[str] = None) -> bool:
    args = ["pr", "review", str(pr_number), "--body", body, "--event", event]
    if repo:
        args.extend(["--repo", repo])
    out = subprocess.run(["gh", *args], capture_output=True, timeout=30)
    return out.returncode == 0


def list_issues(repo: Optional[str] = None, state: str = "open") -> List[Dict]:
    args = ["issue", "list", "--state", state]
    if repo:
        args.extend(["--repo", repo])
    out = subprocess.run(["gh", *args, "--json", "number,title,state"], capture_output=True, text=True, timeout=15)
    if out.returncode != 0:
        return []
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return []
