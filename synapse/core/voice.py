"""Voice: STT/TTS with VAD and voice commands."""
__all__ = ["VoiceManager", "VOICE_COMMANDS"]

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
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

# Optional dependencies handled at runtime
# from faster_whisper import WhisperModel
# import edge_tts

log = logging.getLogger(__name__)

VOICE_COMMANDS = ["new chat", "stop", "read that again"]

class VoiceManager(QObject):
    transcription_result = pyqtSignal(str)
    voice_command = pyqtSignal(str)
    recording_status = pyqtSignal(bool)
    mic_level = pyqtSignal(float)
    playback_status = pyqtSignal(bool)
    error_occurred = pyqtSignal(str)

    def __init__(self, model_size="base"):
        super().__init__()
        self.model_size = model_size
        self.whisper_model = None
        self._recording = False
        self.hands_free = False
        self.vad_threshold = 0.01
        self.silence_timeout = 1.5
        self._audio_data = []
        self._sample_rate = 16000
        self._stream = None
        self._playback_process = None
        self._silence_start = None
        self._tts_generation = 0
        self.tts_voice = "en-US-AndrewNeural"
        self.tts_engine = "edge"
        self.tts_speed = 1.0
        self._tts_queue = []
        self._tts_playing = False

    @property
    def is_recording(self):
        return self._recording

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

    def start_recording(self, hands_free=False):
        if sd is None:
            self.error_occurred.emit("Voice requires: pip install sounddevice numpy")
            return
        if self._recording:
            return
        
        try:
            self._recording = True
            self.hands_free = hands_free
            self._audio_data = []
            self._silence_start = None
            
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

                    if self.hands_free:
                        import time as _time
                        if rms < self.vad_threshold:
                            if self._silence_start is None:
                                self._silence_start = _time.monotonic()
                            elif _time.monotonic() - self._silence_start > self.silence_timeout:
                                # Silence threshold met, trigger stop in a safe way
                                # We can't call stop_recording directly if it closes the stream from here
                                # Instead, we flag it.
                                self._recording = False
                        else:
                            self._silence_start = None

            self._stream = sd.InputStream(samplerate=self._sample_rate, channels=1, callback=callback)
            self._stream.start()
            self.recording_status.emit(True)
            log.info(f"Recording started (hands_free={hands_free})")
            
            if self.hands_free:
                # Poll to check if _recording was set to False by callback
                QTimer.singleShot(100, self._check_hands_free_stop)
                
        except Exception as e:
            self._recording = False
            log.error(f"Failed to start recording: {e}")
            self.error_occurred.emit(f"Mic Error: {e}")

    def _check_hands_free_stop(self):
        if not self._recording:
            self.stop_recording()
        elif self.hands_free:
            QTimer.singleShot(100, self._check_hands_free_stop)

    def stop_recording(self):
        # Allow being called even if _recording is False (to finish up)
        if not self._stream:
            return
        
        was_recording = self._recording
        self._recording = False
        
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                log.debug(f"Stream cleanup: {e}")
            self._stream = None
        
        self.recording_status.emit(False)
        log.info("Recording stopped")

        if not self._audio_data:
            return

        # Process transcription in a separate thread
        threading.Thread(target=self._process_audio, daemon=True).start()

    def _process_audio(self):
        if np is None:
            self.error_occurred.emit("Voice requires: pip install numpy")
            return
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
            except Exception as e:
                log.debug(f"Playback stop cleanup: {e}")
        self.playback_status.emit(False)

    def speak(self, text, voice=None):
        if not text:
            return
        voice = voice or self.tts_voice
        if self.tts_engine == "queue" and self._tts_playing:
            self._tts_queue.append((text, voice))
            return
        self.stop_playback()
        self._tts_generation += 1
        threading.Thread(target=self._run_tts, args=(text, voice), daemon=True).start()

    def speak_queue(self, text, voice=None):
        voice = voice or self.tts_voice
        self._tts_queue.append((text, voice))
        if not self._tts_playing:
            self._play_next_queued()

    def _play_next_queued(self):
        if not self._tts_queue:
            self._tts_playing = False
            return
        self._tts_playing = True
        text, voice = self._tts_queue.pop(0)
        self.stop_playback()
        self._tts_generation += 1
        threading.Thread(target=self._run_tts, args=(text, voice, True), daemon=True).start()

    def _run_tts(self, text, voice, from_queue=False):
        try:
            if self.tts_engine == "espeak":
                self._play_espeak(text)
            else:
                asyncio.run(self._generate_and_play(text, voice))
        except Exception as e:
            log.error(f"TTS Thread Error: {e}")
        finally:
            if from_queue and self._tts_playing:
                QTimer.singleShot(0, self._play_next_queued)

    async def _generate_and_play(self, text, voice):
        output_path = None
        gen = self._tts_generation
        try:
            import edge_tts
            self.playback_status.emit(True)
            rate = f"{int((self.tts_speed - 1) * 100):+d}%" if self.tts_speed != 1.0 else "+0%"
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                output_path = f.name

            await communicate.save(output_path)

            if self._tts_generation != gen:
                return

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

        except Exception as e:
            log.error(f"TTS Error: {e}")
            self.error_occurred.emit(f"TTS Error: {e}")
        finally:
            self.playback_status.emit(False)
            self._playback_process = None
            if output_path:
                try:
                    os.remove(output_path)
                except OSError:
                    pass

    def _play_espeak(self, text):
        self.playback_status.emit(True)
        try:
            rate = int(175 * self.tts_speed)
            self._playback_process = subprocess.Popen(
                ["espeak", "-s", str(rate), text],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._playback_process.wait()
        except FileNotFoundError:
            self.error_occurred.emit("espeak not found. Install: sudo apt install espeak")
        except Exception as e:
            self.error_occurred.emit(f"espeak error: {e}")
        finally:
            self.playback_status.emit(False)
            self._playback_process = None
