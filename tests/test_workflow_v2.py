"""Tests for Workflow V2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_workflow_templates():
    from synapse.core.workflow_templates import get_template, TEMPLATES
    for name in TEMPLATES:
        wf = get_template(name)
        assert wf is not None
        assert len(wf.nodes) >= 1


def test_code_review_workflow():
    from synapse.core.workflow_templates import get_code_review_workflow
    w = get_code_review_workflow()
    assert w.name == "Code Review"
    assert len(w.nodes) == 3
