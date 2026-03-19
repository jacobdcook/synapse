"""Tests for model manager."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_model_router():
    from synapse.core.model_router import classify_task, route, get_available_models
    assert classify_task("fix the bug") == "code"
    assert classify_task("hello") == "simple"
    r = route("refactor this", {}, {"model_router_enabled": False, "default_model": "x"})
    assert r == "x"
    models = get_available_models()
    assert isinstance(models, list)
