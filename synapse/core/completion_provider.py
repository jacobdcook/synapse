import json
import logging
from typing import Optional, List
from PyQt5.QtCore import QThread, pyqtSignal
from .api import _request_json

log = logging.getLogger(__name__)

class CompletionWorker(QThread):
    """
    Asynchronously fetches code completions from Ollama using FIM (Fill-In-the-Middle).
    """
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, prefix: str, suffix: str, model: str = "qwen2.5-coder:1.5b", workspace_root: str = ""):
        super().__init__()
        self.prefix = prefix
        self.suffix = suffix
        self.model = model
        self.workspace_root = workspace_root

    def run(self):
        try:
            # FIM patterns vary by model. Qwen2.5-Coder uses:
            # <|fim_prefix|>...<|fim_suffix|>...<|fim_middle|>
            # We'll try to use the most common one or a generic prompt if not sure.
            # For qwen2.5-coder, we can use the raw template.
            
            prompt = f"<|fim_prefix|>{self.prefix}<|fim_suffix|>{self.suffix}<|fim_middle|>"
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 64,
                    "temperature": 0.0,
                    "stop": ["<|fim_prefix|>", "<|fim_suffix|>", "<|fim_middle|>", "<|endoftext|>", "\n\n"]
                }
            }
            
            # Use the internal _request_json from api.py
            response = _request_json("/api/generate", payload, timeout=5)
            completion = response.get("response", "").strip()
            
            # If it's empty or just whitespace, ignore
            if not completion.strip():
                self.finished.emit("")
                return

            self.finished.emit(completion)
            
        except Exception as e:
            log.error(f"Completion request failed: {e}")
            self.error.emit(str(e))
