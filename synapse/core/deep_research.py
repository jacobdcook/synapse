"""
Deep Research: pre-analyze long inputs before the main model responds.
Chunks content, extracts key info per chunk, synthesizes an answer.
"""
from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from PyQt5.QtCore import QThread, pyqtSignal

from ..utils.constants import get_ollama_url

log = logging.getLogger(__name__)

_CHUNK_SIZE = 3500
_EXTRACT_PROMPT = "Extract from this text: product names, specifications, prices, key claims, and any information relevant to the user's question. Be concise and factual. Output as bullet points."
_SYNTH_PROMPT = "You have analyzed a long document in chunks. Here are the extracted facts. Synthesize a comprehensive answer to the user's question. Be specific and cite details from the analysis."


def _chunk_text(text: str, size: int = _CHUNK_SIZE) -> list[str]:
    """Split text into chunks on paragraph boundaries."""
    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= size:
            chunks.append(remaining.strip())
            break
        cut = remaining[:size]
        last_para = max(cut.rfind("\n\n"), cut.rfind("\n"), 0)
        if last_para > size // 2:
            chunk = remaining[:last_para + 1].strip()
            remaining = remaining[last_para + 1:].lstrip()
        else:
            chunk = remaining[:size].strip()
            remaining = remaining[size:].lstrip()
        if chunk:
            chunks.append(chunk)
    return chunks


class DeepResearchWorker(QThread):
    """QThread that runs deep research on long content."""
    progress = pyqtSignal(str)
    chunk_processed = pyqtSignal(int, int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        content: str,
        question: str,
        model: str,
        ollama_url: str,
        settings: dict,
        timeout: int = 120,
    ):
        super().__init__()
        self.content = content
        self.question = question
        self.model = model or "llama3.2:3b"
        self._ollama_url = (ollama_url or get_ollama_url()).rstrip("/")
        self.settings = settings or {}
        self.timeout = timeout

    def _call_ollama(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        req = urllib.request.Request(
            f"{self._ollama_url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return (data.get("message", {}).get("content", "") or "").strip()

    def run(self) -> None:
        try:
            chunks = _chunk_text(self.content)
            if not chunks:
                self.finished.emit(self.content)
                return
            self.progress.emit("Deep Research: Analyzing...")
            summaries = []
            for i, ch in enumerate(chunks):
                if self.isInterruptionRequested():
                    self.finished.emit(self.content)
                    return
                self.chunk_processed.emit(i + 1, len(chunks))
                self.progress.emit(f"Deep Research: Analyzing chunk {i + 1}/{len(chunks)}...")
                try:
                    out = self._call_ollama([
                        {"role": "system", "content": _EXTRACT_PROMPT},
                        {"role": "user", "content": ch},
                    ])
                    if out:
                        summaries.append(out)
                except Exception as e:
                    log.warning("Deep research chunk %s failed: %s", i + 1, e)
            if not summaries:
                self.finished.emit(self.content)
                return
            combined = "\n\n".join(summaries)
            self.progress.emit("Deep Research: Synthesizing...")
            result = self._call_ollama([
                {"role": "system", "content": _SYNTH_PROMPT},
                {"role": "user", "content": f"User question: {self.question}\n\nExtracted facts:\n{combined}"},
            ])
            if result:
                self.finished.emit(result)
            else:
                self.finished.emit(self.content)
        except Exception as e:
            log.error("Deep research failed: %s", e)
            self.error.emit(str(e))
            self.finished.emit(self.content)


def run_deep_research(
    content: str,
    question: str,
    model: str,
    ollama_url: str,
    settings: dict,
    timeout: int = 120,
) -> str:
    """
    Run deep research synchronously. Blocks until done.
    Returns processed content or original on error.
    """
    from PyQt5.QtCore import QEventLoop, QTimer
    result = [content]

    def on_done(text: str):
        result[0] = text
        loop.quit()

    worker = DeepResearchWorker(content, question, model, ollama_url, settings, timeout)
    worker.finished.connect(on_done)
    worker.error.connect(lambda _: loop.quit())
    worker.start()
    loop = QEventLoop()
    QTimer.singleShot(timeout * 1000, loop.quit)
    loop.exec_()
    return result[0]


def extract_question(content: str) -> str:
    """Extract the user's question from long content (last ~400 chars or last paragraph)."""
    tail = content[-500:].strip()
    for sep in ["\n\n", "\n"]:
        parts = tail.rsplit(sep, 1)
        if len(parts) == 2:
            candidate = parts[-1].strip()
            if "?" in candidate or len(candidate) < 300:
                return candidate
    return tail[-400:] if len(tail) > 400 else tail
