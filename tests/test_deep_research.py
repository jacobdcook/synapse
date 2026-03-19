"""Tests for synapse.core.deep_research."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_chunk_text():
    from synapse.core.deep_research import _chunk_text
    short = "hello world"
    assert len(_chunk_text(short)) == 1
    assert _chunk_text(short)[0] == short
    long_text = "a" * 100 + "\n\n" + "b" * 100 + "\n\n" + "c" * 4000
    chunks = _chunk_text(long_text, 500)
    assert len(chunks) >= 2
    assert sum(len(c) for c in chunks) >= len(long_text) - 100


def test_extract_question():
    from synapse.core.deep_research import extract_question
    assert "?" in extract_question("some long text\n\nwhat size for a 94 lb dog?")
    short = "hi"
    assert extract_question(short) == short


def test_deep_research_worker_exists():
    from synapse.core.deep_research import DeepResearchWorker
    w = DeepResearchWorker("content", "q", "llama3.2:3b", "", {})
    assert hasattr(w, "progress")
    assert hasattr(w, "finished")


def test_run_deep_research_signature():
    from synapse.core.deep_research import run_deep_research
    import inspect
    sig = inspect.signature(run_deep_research)
    assert "content" in sig.parameters
    assert "question" in sig.parameters
    assert "model" in sig.parameters
