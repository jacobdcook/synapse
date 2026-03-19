"""Tests for debug V2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_dap_client_import():
    from synapse.core.debug_manager import DAPClient
    c = DAPClient()
    assert hasattr(c, "connect")
    assert hasattr(c, "send_request")


def test_debug_manager_has_breakpoints():
    from synapse.core.debug_manager import DebugManager
    dm = DebugManager("/tmp")
    assert hasattr(dm, "breakpoints")
    assert hasattr(dm, "start_debug")
