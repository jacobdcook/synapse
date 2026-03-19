"""Tests for analytics."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_analytics_get_stats():
    from synapse.core.analytics import AnalyticsManager
    am = AnalyticsManager()
    stats = am.get_stats()
    assert "total_input" in stats
    assert "total_output" in stats
    assert "by_model" in stats
    assert "count" in stats


def test_analytics_estimate_cost():
    from synapse.core.analytics import AnalyticsManager
    am = AnalyticsManager()
    cost = am.estimate_cost()
    assert isinstance(cost, (int, float))
    assert cost >= 0


def test_analytics_messages_per_day():
    from synapse.core.analytics import AnalyticsManager
    am = AnalyticsManager()
    by_day = am.get_messages_per_day(days=7)
    assert isinstance(by_day, dict)
