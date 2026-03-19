"""Tests for Git V2."""
import sys
import tempfile
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_stage_unstage():
    from synapse.core.git import is_git_repo, stage_file, unstage_file, git_status
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init"], cwd=d, capture_output=True, check=True)
        (Path(d) / "a.txt").write_text("hello")
        assert is_git_repo(d)
        stage_file(d, "a.txt")
        st = git_status(d)
        assert any("a.txt" in e["file"] for e in st)
        unstage_file(d, "a.txt")


def test_get_file_diff():
    from synapse.core.git import get_file_diff
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init"], cwd=d, capture_output=True, check=True)
        (Path(d) / "x.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "x.py"], cwd=d, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=d, capture_output=True, check=True)
        (Path(d) / "x.py").write_text("x = 2\n")
        hunks = get_file_diff(d, "x.py", staged=False)
        assert isinstance(hunks, list)


def test_stash():
    from synapse.core.git import stash_save, stash_list, stash_pop
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init"], cwd=d, capture_output=True, check=True)
        (Path(d) / "f").write_text("x")
        subprocess.run(["git", "add", "f"], cwd=d, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "c"], cwd=d, capture_output=True, check=True)
        (Path(d) / "f").write_text("y")
        stash_save(d, "test stash")
        lst = stash_list(d)
        assert len(lst) >= 1
        ok, _ = stash_pop(d)
