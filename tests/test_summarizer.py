"""Tests for synapse.core.summarizer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_content_hash():
    from synapse.core.summarizer import _content_hash
    assert len(_content_hash("hello")) == 64
    assert _content_hash("a") == _content_hash("a")
    assert _content_hash("a") != _content_hash("b")


def test_summarize_message_short():
    from synapse.core.summarizer import ConversationSummarizer
    s = ConversationSummarizer()
    assert s.summarize_message("hi", 500) == "hi"
    assert s.summarize_message("", 500) == ""


def test_extract_key_facts_empty():
    from synapse.core.summarizer import ConversationSummarizer
    s = ConversationSummarizer()
    assert s.extract_key_facts([]) == []
    assert s.extract_key_facts([{"content": ""}]) == []


def test_cache_loaded():
    from synapse.core.summarizer import ConversationSummarizer
    s = ConversationSummarizer()
    assert hasattr(s, "_cache")


def test_summarize_conversation_short():
    from synapse.core.summarizer import ConversationSummarizer
    s = ConversationSummarizer()
    msgs = [{"role": "user", "content": "hello"}]
    out = s.summarize_conversation(msgs, 1000)
    assert "hello" in out or len(out) <= 1000
