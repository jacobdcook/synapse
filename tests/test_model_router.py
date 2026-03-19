"""Tests for synapse.core.model_router."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_classify_task():
    from synapse.core.model_router import classify_task
    assert classify_task("refactor this code") == "code"
    assert classify_task("analyze the data") == "analysis"
    assert classify_task("hi") == "simple"


def test_route():
    from synapse.core.model_router import route
    settings = {"model_router_enabled": True, "code_model": "coder", "fast_model": "fast"}
    assert "coder" in route("refactor the function", None, settings)
