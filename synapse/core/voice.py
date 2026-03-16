import os
import logging
import time
import tempfile
import threading
import subprocess
import asyncio
try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    np = None
    sd = None
from PyQt5.QtCore import QObject, pyqtSignal

# Optional dependencies handled at runtime
# from faster_whisper import WhisperModel
# import edge_tts

log = logging.getLogger(__name__)

class VoiceManager(QObject):
    transcription_result = pyqtSignal(str)
    recording_status = pyqtSignal(bool) # True = recording, False = idle
    mic_level = pyqtSignal(float)      # 0.0 to 1.0
    playback_status = pyqtSignal(bool) # True = speaking, False = silent
    error_occurred = pyqtSignal(str)

    def __init__(self, model_size="base"):
        super().__init__()
        self.model_size = model_size
        self.whisper_model = None
        self._recording = False
        self._audio_data = []
        self._sample_rate = 16000
        self._stream = None
        self._playback_process = None

    def _ensure_whisper(self):
        if self.whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                import torch
                
                device = "cuda" if torch.cuda.is_available() else "cpu"
                compute_type = "float16" if device == "cuda" else "int8"
                
                log.info(f"Loading Whisper model: {self.model_size} on {device} ({compute_type})")
                self.whisper_model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
            except Exception as e:
                log.error(f"Failed to load Whisper: {e}")
                self.error_occurred.emit(f"Whisper Error: {e}")
                return False
        return True

    def start_recording(self):
        if self._recording:
            return
        
        try:
            self._recording = True
            self._audio_data = []
            
            def callback(indata, frames, time, status):
                if status:
                    log.warning(f"Audio status: {status}")
                if self._recording:
                    self._audio_data.append(indata.copy())
                    # Calculate RMS for mic level visualization
                    rms = np.sqrt(np.mean(indata**2))
                    # Normalizing roughly; typical vocal range is 0.01 to 0.3
                    level = min(1.0, rms * 5.0) 
                    self.mic_level.emit(level)

            self._stream = sd.InputStream(samplerate=self._sample_rate, channels=1, callback=callback)
            self._stream.start()
            self.recording_status.emit(True)
            log.info("Recording started")
        except Exception as e:
            self._recording = False
            log.error(f"Failed to start recording: {e}")
            self.error_occurred.emit(f"Mic Error: {e}")

    def stop_recording(self):
        if not self._recording:
            return
        
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
        
        self.recording_status.emit(False)
        log.info("Recording stopped")

        if not self._audio_data:
            return

        # Process transcription in a separate thread
        threading.Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        try:
            if not self._audio_data:
                return
                
            # faster-whisper can take a float32 array normalized to [-1, 1]
            # sounddevice typically gives float32 if requested, or we convert here
            audio_np = np.concatenate(self._audio_data, axis=0).flatten().astype(np.float32)
            
            if self._ensure_whisper():
                # Transcribe directly from numpy array
                segments, info = self.whisper_model.transcribe(audio_np, beam_size=5)
                text = " ".join([s.text for s in segments]).strip()
                
                if text:
                    log.info(f"Transcribed: {text}")
                    self.transcription_result.emit(text)
                else:
                    log.info("No speech detected.")
            
            # No file cleanup needed as we're in-memory
                
        except Exception as e:
            log.error(f"STT Processing Error: {e}")
            self.error_occurred.emit(f"STT Error: {e}")

    def stop_playback(self):
        if self._playback_process:
            try:
                self._playback_process.terminate()
                self._playback_process = None
            except:
                pass
        self.playback_status.emit(False)

    def speak(self, text, voice="en-US-AndrewNeural"):
        if not text:
            return
        self.stop_playback()
        threading.Thread(target=self._run_tts, args=(text, voice), daemon=True).start()

    def _run_tts(self, text, voice):
        try:
            asyncio.run(self._generate_and_play(text, voice))
        except Exception as e:
            log.error(f"TTS Thread Error: {e}")

    async def _generate_and_play(self, text, voice):
        try:
            import edge_tts
            self.playback_status.emit(True)
            
            communicate = edge_tts.Communicate(text, voice)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                output_path = f.name
                
            await communicate.save(output_path)
            
            # Play using available system player
            # On Linux: mpv, ffplay, paplay, etc.
            played = False
            for player_args in [
                ["mpv", "--no-video", "--autoexit", output_path],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", output_path],
                ["cvlc", "--play-and-exit", output_path]
            ]:
                try:
                    self._playback_process = subprocess.Popen(player_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self._playback_process.wait()
                    played = True
                    break
                except FileNotFoundError:
                    continue
                except Exception as e:
                    log.warning(f"Player {player_args[0]} failed: {e}")
                    continue

            if not played:
                log.error("No suitable audio player found (mpv, ffplay, cvlc).")
                self.error_occurred.emit("No audio player found. Please install mpv or ffmpeg.")
            
            # Cleanup
            if os.path.exists(output_path):
                os.remove(output_path)
                
        except Exception as e:
            log.error(f"TTS Error: {e}")
            self.error_occurred.emit(f"TTS Error: {e}")
        finally:
            self.playback_status.emit(False)
            self._playback_process = None
