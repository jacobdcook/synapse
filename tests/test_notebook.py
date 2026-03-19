"""Tests for notebook support."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_notebook_manager_execute():
    from synapse.core.notebook_manager import NotebookManager
    mgr = NotebookManager(tempfile.gettempdir())
    out, err, ok = mgr.execute_cell_subprocess("print(1+1)")
    assert ok
    assert "2" in out


def test_notebook_load_save():
    from synapse.core.notebook_manager import NotebookManager, NotebookCell
    with tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False) as f:
        path = f.name
    try:
        Path(path).write_text('{"cells":[{"cell_type":"code","source":["x=1"]}],"metadata":{},"nbformat":4,"nbformat_minor":5}')
        mgr = NotebookManager(tempfile.gettempdir())
        cells = mgr.load_notebook(path)
        assert len(cells) >= 1
        mgr.save_notebook(path, cells)
    finally:
        Path(path).unlink(missing_ok=True)
