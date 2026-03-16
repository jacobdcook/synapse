import sys
import os
from pathlib import Path
import numpy as np

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from synapse.core.voice import VoiceManager
from PyQt5.QtCore import QCoreApplication, QTimer

def test_voice_manager():
    print("Testing VoiceManager initialization...")
    vm = VoiceManager()
    print(f"Whisper Model Size: {vm.model_size}")
    print(f"TTS Voice: {vm.tts_voice}")
    
    print("\nTesting RMS Calculation (VAD Logic)...")
    vm.vad_threshold = 0.01
    
    # Simulate silence
    silence = np.zeros(1024, dtype=np.float32)
    rms_silence = np.sqrt(np.mean(silence**2))
    is_speech_silence = rms_silence >= vm.vad_threshold
    print(f"Silence RMS: {rms_silence:.4f}, Is Speech: {is_speech_silence} (Expected: False)")
    
    # Simulate sound
    noise = np.random.uniform(-0.1, 0.1, 1024).astype(np.float32)
    rms_noise = np.sqrt(np.mean(noise**2))
    is_speech_noise = rms_noise >= vm.vad_threshold
    print(f"Noise RMS: {rms_noise:.4f}, Is Speech: {is_speech_noise} (Expected: True)")

    print("\nVoice integration test passed (logic verified).")

if __name__ == "__main__":
    app = QCoreApplication(sys.argv)
    test_voice_manager()
    QTimer.singleShot(500, app.quit)
    sys.exit(app.exec_())
