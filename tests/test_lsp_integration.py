"""Tests for LSP integration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_lsp_manager_init():
    from synapse.core.lsp_manager import LSPManager
    mgr = LSPManager("/tmp")
    assert mgr.workspace_root == "/tmp"
    mgr.workspace_root = "/home"
    assert mgr.workspace_root == "/home"


def test_lsp_request_completion_exists():
    from synapse.core.lsp_manager import LSPManager
    mgr = LSPManager("/tmp")
    assert hasattr(mgr, "request_completion")
    assert hasattr(mgr, "request_definition")
    assert hasattr(mgr, "request_hover")


def test_problems_panel():
    from synapse.ui.problems_panel import ProblemsPanel, SEVERITY_LABELS
    from PyQt5.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    panel = ProblemsPanel()
    panel.add_diagnostics("file:///tmp/test.py", [
        {"range": {"start": {"line": 0, "character": 0}}, "message": "Undefined", "severity": 1},
        {"range": {"start": {"line": 1, "character": 2}}, "message": "Unused", "severity": 2},
    ])
    assert panel.list_widget.count() >= 1
