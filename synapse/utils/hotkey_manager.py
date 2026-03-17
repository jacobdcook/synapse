import logging
try:
    from pynput import keyboard
except ImportError:
    keyboard = None
from PyQt5.QtCore import QThread, pyqtSignal

log = logging.getLogger(__name__)

class GlobalHotkeyManager(QThread):
    hotkey_triggered = pyqtSignal()

    def __init__(self, hotkey_str):
        super().__init__()
        self.hotkey_str = hotkey_str
        self._listener = None

    def run(self):
        if keyboard is None:
            log.warning("pynput not installed — global hotkeys disabled. Install with: pip install pynput")
            return
        try:
            log.info(f"Starting global hotkey listener for: {self.hotkey_str}")
            with keyboard.GlobalHotKeys({
                self.hotkey_str: self._on_triggered
            }) as self._listener:
                self._listener.join()
        except Exception as e:
            log.error(f"Global hotkey listener failed: {e}")

    def _on_triggered(self):
        log.info("Global hotkey triggered!")
        self.hotkey_triggered.emit()

    def stop(self):
        if self._listener:
            self._listener.stop()
        self.quit()
