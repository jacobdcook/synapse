"""Tests for conversation branching."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_tmp = tempfile.mkdtemp()
_d = Path(_tmp)
import synapse.utils.constants as _c
_c.CONV_DIR = _d / "conv"
_c.CONFIG_DIR = _d / "config"
_c.CONV_DIR.mkdir(parents=True, exist_ok=True)
_c.CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def test_create_branch():
    from synapse.core.store import ConversationStore, new_conversation
    store = ConversationStore()
    conv = new_conversation()
    conv["messages"] = [
        {"id": "m1", "role": "user", "content": "hi", "parent_id": None, "branch_id": "main"},
        {"id": "m2", "role": "assistant", "content": "hello", "parent_id": "m1", "branch_id": "main"},
    ]
    conv["history"] = list(conv["messages"])
    store.save(conv)
    bid = store.create_branch(conv["id"], "m2", "Test Branch")
    assert bid
    branches = store.get_branches(conv["id"])
    assert len(branches) == 2
    assert any(b["name"] == "Test Branch" for b in branches)


def test_get_branch_messages():
    from synapse.core.store import ConversationStore, new_conversation
    store = ConversationStore()
    conv = new_conversation()
    conv["messages"] = [{"id": "m1", "role": "user", "content": "hi", "parent_id": None}]
    conv["history"] = list(conv["messages"])
    store.save(conv)
    msgs = store.get_branch_messages(conv["id"], "main")
    assert len(msgs) >= 1
