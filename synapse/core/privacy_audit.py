"""Log mask events (hash only, never original values)."""
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)
AUDIT_FILE = CONFIG_DIR / "privacy_audit.jsonl"


def log_mask_event(rule_name, original_hash, replacement):
    try:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AUDIT_FILE, "a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "rule": rule_name,
                "hash": original_hash,
                "replacement": replacement
            }) + "\n")
    except Exception as e:
        log.warning(f"Privacy audit log failed: {e}")


def get_report(days=7):
    if not AUDIT_FILE.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    events = []
    try:
        with open(AUDIT_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    if e.get("ts", "") >= cutoff:
                        events.append(e)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        log.warning(f"Privacy audit read failed: {e}")
    return events
