"""Tests for GitHub integration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_list_prs_import():
    from synapse.core.github_integration import list_prs, get_pr_diff, create_review, list_issues
    assert callable(list_prs)
    assert callable(get_pr_diff)


def test_list_issues_import():
    from synapse.core.github_integration import list_issues
    assert callable(list_issues)
