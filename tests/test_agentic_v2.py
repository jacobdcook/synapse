"""Tests for synapse.core.agentic AgenticLoop V2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_planning_heuristic():
    from synapse.core.agentic import AgenticLoop
    assert hasattr(AgenticLoop, "plan_created")
    assert hasattr(AgenticLoop, "reflection")
    assert hasattr(AgenticLoop, "progress")


def test_signals_exist():
    from synapse.core.agentic import AgenticLoop
    assert AgenticLoop.plan_created is not None
    assert AgenticLoop.reflection is not None
    assert AgenticLoop.progress is not None
