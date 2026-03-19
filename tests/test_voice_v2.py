"""Tests for voice V2."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_voice_commands():
    from synapse.core.voice import VOICE_COMMANDS
    assert "new chat" in VOICE_COMMANDS
    assert "stop" in VOICE_COMMANDS
    assert "read that again" in VOICE_COMMANDS


def test_voice_manager_attrs():
    from synapse.core.voice import VoiceManager
    vm = VoiceManager()
    assert hasattr(vm, "voice_command")
    assert hasattr(vm, "tts_engine")
    assert hasattr(vm, "tts_speed")
    assert hasattr(vm, "speak_queue")
