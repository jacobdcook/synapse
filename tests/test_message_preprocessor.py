"""Tests for message_preprocessor."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from synapse.core.message_preprocessor import preprocess_long_message, LONG_MESSAGE_THRESHOLD

def test_short_unchanged():
    assert preprocess_long_message("short") == "short"
    assert preprocess_long_message("x" * 100) == "x" * 100
    assert preprocess_long_message("") == ""
    assert preprocess_long_message(None) == ""

def test_long_restructured():
    content = "x" * 4000
    result = preprocess_long_message(content)
    assert "USER QUESTION:" in result
    assert "CONTEXT (for reference):" in result
    assert "x" in result

def test_question_extracted():
    content = "a" * 3500 + "\n\nwhat size for 94 lb dog?"
    result = preprocess_long_message(content)
    assert "what size for 94 lb dog?" in result
    assert "USER QUESTION:" in result

def test_at_threshold_unchanged():
    content = "x" * LONG_MESSAGE_THRESHOLD
    assert preprocess_long_message(content) == content

if __name__ == "__main__":
    test_short_unchanged()
    test_long_restructured()
    test_question_extracted()
    test_at_threshold_unchanged()
    print("All tests passed")
