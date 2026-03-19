"""Tests for security (sandbox, command blacklist)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_dangerous_command_blocked():
    from synapse.core.agent import ToolExecutor
    te = ToolExecutor("/tmp")
    res = te._run_command("rm -rf /")
    assert "Blocked" in res


def test_code_executor_sandbox_import():
    from synapse.core.code_executor import _apply_sandbox_limits, DANGEROUS_PATTERNS
    assert callable(_apply_sandbox_limits)
    assert "rm -rf /" in DANGEROUS_PATTERNS
