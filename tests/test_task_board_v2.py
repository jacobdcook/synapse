"""Tests for task board V2."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_add_subtask():
    from synapse.core.task_manager import TaskManager
    td = tempfile.mkdtemp()
    tm = TaskManager(td)
    t = tm.add_task("Parent", "desc")
    st = tm.add_subtask(t["id"], "Sub 1")
    assert st is not None
    assert st["title"] == "Sub 1"
    assert st["done"] is False
    assert any(s["title"] == "Sub 1" for s in tm.tasks[0]["subtasks"])


def test_add_dependency():
    from synapse.core.task_manager import TaskManager
    td = tempfile.mkdtemp()
    tm = TaskManager(td)
    t1 = tm.add_task("A", "")
    t2 = tm.add_task("B", "")
    ok = tm.add_dependency(t2["id"], t1["id"])
    assert ok
    assert t1["id"] in tm.tasks[1]["dependencies"]
