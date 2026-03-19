"""Tests for Terminal V2."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_tmp = tempfile.mkdtemp()
_d = Path(_tmp)
import synapse.utils.constants as _c
_c.CONFIG_DIR = _d / "config"
_c.CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def test_terminal_history():
    from synapse.ui.terminal import TerminalHistory
    hist = TerminalHistory(path=_d / "th.json")
    hist.append("ls -la")
    hist.append("cd /tmp")
    all_ = hist.get_all()
    assert "ls -la" in all_
    assert "cd /tmp" in all_
    hist2 = TerminalHistory(path=_d / "th.json")
    assert "ls -la" in hist2.get_all()


def test_ansi_strip():
    from synapse.ui.terminal import _strip_ansi
    text = "\x1b[31mred\x1b[0m normal"
    out = _strip_ansi(text)
    assert "red" in out
    assert "normal" in out
    assert "\x1b" not in out
