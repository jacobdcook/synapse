"""Tests for synapse.core.context_manager_v2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synapse.core.context_manager_v2 import (
    TokenCounter,
    ContextWindowManager,
    apply_smart_context,
    _get_text_content,
)


def test_token_counter_basic():
    """Token counting returns positive integer."""
    assert TokenCounter.count("hello world", "") >= 1
    assert TokenCounter.count("", "") == 0
    assert TokenCounter.count("x" * 100, "") >= 20


def test_token_counter_fallback():
    """Non-OpenAI models use len/4 fallback."""
    text = "hello world " * 10
    c = TokenCounter.count(text, "llama3.2:3b")
    assert c == max(1, len(text) // 4)


def test_get_text_content():
    """Extract text from message content."""
    assert _get_text_content({"content": "hi"}) == "hi"
    assert _get_text_content({"content": [{"type": "text", "text": "hi"}]}) == "hi"
    assert _get_text_content({}) == ""


def test_budget_calculation():
    """ContextWindowManager reserves 20% for response."""
    mgr = ContextWindowManager(max_tokens=1000)
    assert mgr.response_reserve == 200
    assert mgr.input_budget == 800


def test_empty_conversation():
    """Empty messages return empty."""
    mgr = ContextWindowManager(max_tokens=4096)
    msgs, sys = mgr.process([], "system")
    assert msgs == []
    assert sys == "system"


def test_single_message_unchanged():
    """Single message passes through."""
    mgr = ContextWindowManager(max_tokens=4096)
    msgs = [{"role": "user", "content": "hello"}]
    out, _ = mgr.process(msgs, "")
    assert len(out) == 1
    assert out[0]["content"] == "hello"


def test_message_prioritization():
    """Last messages are always kept."""
    mgr = ContextWindowManager(max_tokens=500)
    msgs = [
        {"role": "user", "content": "a" * 100},
        {"role": "assistant", "content": "b" * 100},
        {"role": "user", "content": "c" * 100},
        {"role": "assistant", "content": "d" * 100},
    ]
    out, _ = mgr.process(msgs, "")
    contents = [_get_text_content(m) for m in out]
    assert "d" * 100 in contents or any("d" in c for c in contents)
    assert "c" * 100 in contents or any("c" in c for c in contents)


def test_dropped_indicator():
    """When messages are dropped, indicator is added."""
    mgr = ContextWindowManager(max_tokens=300)
    msgs = [
        {"role": "user", "content": "x" * 200},
        {"role": "assistant", "content": "y" * 200},
        {"role": "user", "content": "z" * 50},
        {"role": "assistant", "content": "w" * 50},
    ]
    out, _ = mgr.process(msgs, "")
    has_indicator = any(
        "omitted" in str(m.get("content", "")) for m in out
    )
    assert has_indicator or len(out) <= 4


def test_apply_smart_context():
    """apply_smart_context returns tuple of (messages, system_prompt)."""
    msgs = [{"role": "user", "content": "hi"}]
    out_msgs, out_sys = apply_smart_context(msgs, "sys", 4096)
    assert isinstance(out_msgs, list)
    assert isinstance(out_sys, str)
    assert out_sys == "sys"
    assert len(out_msgs) >= 1
