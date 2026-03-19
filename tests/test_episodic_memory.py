"""Tests for synapse.core.episodic_memory."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_log_and_query_recent():
    from synapse.core.episodic_memory import EpisodicMemory
    with tempfile.TemporaryDirectory() as d:
        em = EpisodicMemory(Path(d) / "ep.db")
        em.log_episode("c1", 0, "user", "Python debugging", outcome="Asked about breakpoints")
        em.log_episode("c1", 1, "assistant", "Python debugging", outcome="Explained pdb usage", tools_used=["read_file"])
        recent = em.query_recent(conv_id="c1", limit=5)
        assert len(recent) == 2
        assert recent[0]["outcome"] == "Explained pdb usage"
        assert "read_file" in recent[0]["tools_used"]


def test_query_by_topic():
    from synapse.core.episodic_memory import EpisodicMemory
    with tempfile.TemporaryDirectory() as d:
        em = EpisodicMemory(Path(d) / "ep.db")
        em.log_episode("c1", 0, "assistant", "Docker build", outcome="Built image successfully")
        em.log_episode("c2", 0, "assistant", "Python loops", outcome="Explained for/while")
        results = em.query_by_topic("Docker", limit=5)
        assert len(results) >= 1
        assert "Docker" in (results[0].get("topic") or "") or "Docker" in (results[0].get("outcome") or "")


def test_get_user_patterns():
    from synapse.core.episodic_memory import EpisodicMemory
    with tempfile.TemporaryDirectory() as d:
        em = EpisodicMemory(Path(d) / "ep.db")
        em.log_episode("c1", 0, "assistant", "Python", outcome="x", tools_used=["read_file", "read_file"])
        em.log_episode("c2", 0, "assistant", "Python", outcome="y", tools_used=["read_file"])
        patterns = em.get_user_patterns()
        assert "topics" in patterns
        assert "preferred_tools" in patterns
        assert "read_file" in patterns["preferred_tools"]


def test_cleanup():
    from synapse.core.episodic_memory import EpisodicMemory
    with tempfile.TemporaryDirectory() as d:
        em = EpisodicMemory(Path(d) / "ep.db")
        em.log_episode("c1", 0, "assistant", "test", outcome="x")
        assert len(em.query_recent(limit=10)) == 1
        em.cleanup(days=0)
        assert len(em.query_recent(limit=10)) == 0


def test_clear_all():
    from synapse.core.episodic_memory import EpisodicMemory
    with tempfile.TemporaryDirectory() as d:
        em = EpisodicMemory(Path(d) / "ep.db")
        em.log_episode("c1", 0, "assistant", "x", outcome="y")
        em.clear_all()
        assert len(em.query_recent(limit=10)) == 0
