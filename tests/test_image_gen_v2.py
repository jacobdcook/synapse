"""Tests for image gen V2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_image_presets():
    from synapse.core.image_gen import IMAGE_PRESETS
    assert "Photorealistic" in IMAGE_PRESETS
    assert "Anime" in IMAGE_PRESETS
    p = IMAGE_PRESETS["Fast Draft"]
    assert p["steps"] == 15
    assert p["cfg_scale"] == 6


def test_gen_dir_exists():
    from synapse.core.image_gen import GEN_DIR
    assert GEN_DIR.exists()
