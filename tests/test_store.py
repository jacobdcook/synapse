"""Tests for synapse.core.store."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_create():
    from synapse.core.store import ConversationStore, new_conversation
    store = ConversationStore()
    conv = new_conversation("llama3.2:3b")
    conv["title"] = "Test"
    assert conv["id"]
    assert conv["title"] == "Test"


def test_save_load():
    from synapse.core.store import ConversationStore, new_conversation
    store = ConversationStore()
    conv = new_conversation("llama3.2:3b")
    conv["title"] = "SaveTest"
    conv["messages"] = [{"role": "user", "content": "hi"}]
    store.save(conv)
    loaded = store.load(conv["id"])
    assert loaded
    assert loaded["messages"][0]["content"] == "hi"


def test_search():
    from synapse.core.store import ConversationStore
    store = ConversationStore()
    results = store.search("")
    assert isinstance(results, list)
