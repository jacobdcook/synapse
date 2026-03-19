"""Tests for scheduler V2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_scheduler_cron_matches():
    from synapse.core.scheduler import TaskScheduler
    from datetime import datetime, timezone
    s = TaskScheduler()
    dt = datetime(2025, 3, 14, 10, 30, tzinfo=timezone.utc)
    assert s._cron_matches("30 10 * * *", dt)
    assert not s._cron_matches("0 10 * * *", dt)


def test_add_task_with_cron():
    from synapse.core.scheduler import TaskScheduler
    s = TaskScheduler()
    t = s.add_task("test", "llama", "conv1", "2025-01-01T00:00:00Z", cron_expr="0 12 * * *")
    assert "cron_expr" in t
    assert t["cron_expr"] == "0 12 * * *"
