"""Tests for collaboration module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_session_server_import():
    from synapse.core.collaboration import SessionServer, SessionClient, MSG_CHAT
    assert SessionServer is not None
    assert SessionClient is not None
    assert MSG_CHAT == "CHAT_MESSAGE"


def test_session_client():
    from synapse.core.collaboration import SessionClient
    c = SessionClient("ws://127.0.0.1:8765")
    assert c.url == "ws://127.0.0.1:8765"
