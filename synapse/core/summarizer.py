"""
Conversation summarization for Synapse.
Powers context window management and episodic memory.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from ..utils.constants import CONFIG_DIR, get_ollama_url

log = logging.getLogger(__name__)

_CACHE_FILE = CONFIG_DIR / "summary_cache.json"
_CACHE_MAX = 500
_RETRIES = 2
_TIMEOUT = 15


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


class ConversationSummarizer:
    """Summarizes messages and extracts key facts. Uses Ollama with cache and retries."""

    def __init__(self, model: str = "llama3.2:3b", ollama_url: Optional[str] = None):
        self.model = model
        self._ollama_url = (ollama_url or get_ollama_url()).rstrip("/")
        self._cache: dict[str, str] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        if _CACHE_FILE.exists():
            try:
                data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
                self._cache = data.get("entries", {})
            except Exception as e:
                log.warning("Failed to load summary cache: %s", e)

    def _save_cache(self) -> None:
        try:
            entries = dict(list(self._cache.items())[-_CACHE_MAX:])
            _CACHE_FILE.write_text(json.dumps({"entries": entries}, indent=0), encoding="utf-8")
        except Exception as e:
            log.warning("Failed to save summary cache: %s", e)

    def _call_ollama(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user[:8000]},
            ],
            "stream": False,
        }
        req = urllib.request.Request(
            f"{self._ollama_url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        for attempt in range(_RETRIES + 1):
            try:
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                return (data.get("message", {}).get("content", "") or "").strip()
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                if attempt < _RETRIES:
                    time.sleep(2 ** attempt)
                    continue
                raise
        return ""

    def summarize_message(self, content: str, max_length: int = 500) -> str:
        """Summarize a single message. Uses cache. Falls back to truncation on failure."""
        if not content or len(content) <= max_length:
            return content
        h = _content_hash(content)
        if h in self._cache:
            return self._cache[h]
        try:
            summary = self._call_ollama(
                "Summarize the following message concisely. Preserve: key facts, names, numbers, decisions, code snippets. Output only the summary.",
                content,
            )
            if summary:
                out = summary[:max_length] + ("..." if len(summary) > max_length else "")
                self._cache[h] = out
                self._save_cache()
                return out
        except Exception as e:
            log.warning("Summarization failed: %s", e)
        return content[:max_length] + "..."

    def summarize_conversation(self, messages: list[dict], max_length: int = 1000) -> str:
        """Summarize a conversation segment."""
        texts = []
        for m in messages:
            c = m.get("content", "")
            if isinstance(c, str):
                texts.append(c)
            elif isinstance(c, list):
                for item in c:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(item.get("text", ""))
        combined = "\n\n".join(texts)
        if len(combined) <= max_length:
            return combined
        try:
            return self._call_ollama(
                "Summarize this conversation concisely. Preserve the narrative arc and key decisions.",
                combined,
            )[:max_length] + "..."
        except Exception as e:
            log.warning("Conversation summarization failed: %s", e)
            return combined[:max_length] + "..."

    def extract_key_facts(self, messages: list[dict]) -> list[str]:
        """Extract discrete facts from a conversation."""
        texts = []
        for m in messages:
            c = m.get("content", "")
            if isinstance(c, str):
                texts.append(c)
        combined = "\n".join(texts)
        if not combined.strip():
            return []
        try:
            result = self._call_ollama(
                "Extract key facts from this conversation. Output one fact per line, short phrases only. No numbering.",
                combined,
            )
            return [r.strip() for r in result.splitlines() if r.strip()][:20]
        except Exception as e:
            log.warning("Key facts extraction failed: %s", e)
            return []
