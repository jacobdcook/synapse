"""
Tool execution audit log for debugging and verification.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)

_MAX_ARGS_LEN = 500
_MAX_RESULT_LEN = 500
_ROTATE_SIZE = 10 * 1024 * 1024
_MAX_ROTATIONS = 3


class ToolAuditLog:
    """Appends tool call records to a JSONL file with rotation support."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or (CONFIG_DIR / "tool_audit.jsonl")

    def log_call(
        self,
        tool_name: str,
        arguments: dict,
        result: str,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Append a tool call record to the audit log."""
        args_str = json.dumps(arguments, default=str)[:_MAX_ARGS_LEN]
        result_str = str(result)[:_MAX_RESULT_LEN]
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "arguments": args_str,
            "result": result_str,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "error": error,
        }
        try:
            self._rotate_if_needed()
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            log.warning("Failed to write tool audit: %s", e)

    def _rotate_if_needed(self) -> None:
        if not self.log_path.exists():
            return
        if self.log_path.stat().st_size < _ROTATE_SIZE:
            return
        for i in range(_MAX_ROTATIONS - 1, 0, -1):
            old_path = self.log_path.parent / f"{self.log_path.stem}.{i}.jsonl"
            new_path = self.log_path.parent / f"{self.log_path.stem}.{i + 1}.jsonl"
            if old_path.exists():
                new_path.write_text(old_path.read_text(encoding="utf-8"), encoding="utf-8")
        if self.log_path.exists():
            rot1 = self.log_path.parent / f"{self.log_path.stem}.1.jsonl"
            rot1.write_text(self.log_path.read_text(encoding="utf-8"), encoding="utf-8")
            self.log_path.write_text("", encoding="utf-8")

    def get_recent(self, limit: int = 50) -> list[dict]:
        """Read last N entries from the log."""
        if not self.log_path.exists():
            return []
        try:
            lines = self.log_path.read_text(encoding="utf-8").strip().split("\n")
            entries = []
            for line in reversed(lines[-limit:]):
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return entries
        except Exception as e:
            log.warning("Failed to read tool audit: %s", e)
            return []

    def get_stats(self) -> dict:
        """Get per-tool counts, success rates, avg duration."""
        entries = self.get_recent(500)
        by_tool: dict[str, dict] = {}
        for e in entries:
            name = e.get("tool_name", "unknown")
            if name not in by_tool:
                by_tool[name] = {"count": 0, "success": 0, "durations": []}
            by_tool[name]["count"] += 1
            if e.get("success"):
                by_tool[name]["success"] += 1
            if "duration_ms" in e:
                by_tool[name]["durations"].append(e["duration_ms"])
        stats = {}
        for name, data in by_tool.items():
            count = data["count"]
            success = data["success"]
            durations = data["durations"]
            stats[name] = {
                "count": count,
                "success_rate": success / count if count else 0,
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            }
        return stats
