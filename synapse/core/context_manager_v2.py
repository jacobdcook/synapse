"""
Smart context window management for Synapse.
Trims and summarizes messages to fit within token budget while preserving
recent context and user intent.
"""
from __future__ import annotations

import logging
from typing import Optional

from ..utils.constants import get_ollama_url

log = logging.getLogger(__name__)


def _get_text_content(msg: dict) -> str:
    """Extract text content from a message for token counting."""
    content = msg.get("content", "")
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return " ".join(parts)
    return str(content) if content else ""


class TokenCounter:
    """
    Estimates token count for text.
    Uses tiktoken for OpenAI models, len/4 fallback otherwise.
    """

    _tiktoken_available: Optional[bool] = None
    _tiktoken_enc = None

    @classmethod
    def count(cls, text: str, model: str = "") -> int:
        """
        Estimate token count for the given text.
        Uses tiktoken for OpenAI models if available, else len/4.
        """
        if not text:
            return 0
        if model and (model.startswith("gpt-") or model.startswith("o1-")):
            try:
                if cls._tiktoken_available is None:
                    import tiktoken
                    cls._tiktoken_enc = tiktoken.get_encoding("cl100k_base")
                    cls._tiktoken_available = True
            except ImportError:
                cls._tiktoken_available = False
            if cls._tiktoken_available and cls._tiktoken_enc:
                return len(cls._tiktoken_enc.encode(text))
        return max(1, len(text) // 4)


class ContextWindowManager:
    """
    Manages conversation context to fit within token budget.
    Reserves 20% for response, keeps system + last 2 user + last assistant,
    fills remaining budget from history. Summarizes long messages when needed.
    """

    def __init__(
        self,
        max_tokens: int = 4096,
        response_reserve_ratio: float = 0.2,
        model: str = "",
        ollama_url: Optional[str] = None,
        summarizer=None,
        summarization_model: str = "llama3.2:3b",
    ):
        self.max_tokens = max_tokens
        self.response_reserve = int(max_tokens * response_reserve_ratio)
        self.input_budget = max_tokens - self.response_reserve
        self.model = model
        self._ollama_url = ollama_url or ""
        self._summarizer = summarizer
        self._summarization_model = summarization_model

    def _summarize_message(self, content: str, max_length: int) -> str:
        """Summarize long content. Uses ConversationSummarizer if available."""
        if len(content) <= max_length:
            return content
        target_chars = max(int(len(content) * 0.25), 200)
        if self._summarizer:
            return self._summarizer.summarize_message(content, target_chars)
        try:
            from .summarizer import ConversationSummarizer
            s = ConversationSummarizer(model=self._summarization_model, ollama_url=self._ollama_url or None)
            return s.summarize_message(content, target_chars)
        except Exception as e:
            log.warning("Summarization error: %s", e)
            return content[:target_chars] + "..."

    def process(
        self,
        messages: list[dict],
        system_prompt: str = "",
    ) -> tuple[list[dict], str]:
        """
        Process messages and system prompt to fit within budget.
        Returns (processed_messages, system_prompt).
        """
        if not messages:
            return [], system_prompt

        sys_tokens = TokenCounter.count(system_prompt, self.model)
        budget = self.input_budget - sys_tokens - 50

        if budget < 200:
            return messages[:1] if messages else [], system_prompt

        def msg_tokens(m: dict) -> int:
            return TokenCounter.count(_get_text_content(m), self.model) + 4

        chunks = []
        i = 0
        while i < len(messages):
            m = messages[i]
            if m.get("tool_calls") and i + 1 < len(messages) and messages[i + 1].get("role") == "tool_results":
                chunks.append([m, messages[i + 1]])
                i += 2
            else:
                chunks.append([m])
                i += 1

        if len(chunks) <= 4:
            return messages, system_prompt

        priority_chunks = chunks[-4:]
        middle_chunks = chunks[:-4]

        def chunk_tokens(ch):
            return sum(msg_tokens(m) for m in ch)

        priority_tokens = sum(chunk_tokens(c) for c in priority_chunks)
        remaining_budget = budget - priority_tokens

        if remaining_budget < 100:
            out = []
            for c in priority_chunks:
                out.extend(c)
            return out, system_prompt

        result_chunks = []
        dropped_count = 0
        summarized_block = []
        dropped_messages = []
        used = 0

        for ch in reversed(middle_chunks):
            tok = chunk_tokens(ch)
            if used + tok <= remaining_budget:
                result_chunks.insert(0, ch)
                used += tok
            else:
                if len(ch) == 1:
                    content = _get_text_content(ch[0])
                    if content and tok > remaining_budget // 2:
                        summary = self._summarize_message(content, remaining_budget // 4)
                        summarized_block.append(
                            {"role": "user", "content": f"[Summarized]: {summary}"}
                        )
                        used += TokenCounter.count(summary, self.model) + 20
                        if used > remaining_budget:
                            break
                    else:
                        dropped_count += 1
                        dropped_messages.extend(ch)
                else:
                    dropped_count += len(ch)
                    dropped_messages.extend(ch)

        if dropped_messages:
            try:
                from .summarizer import ConversationSummarizer
                s = self._summarizer or ConversationSummarizer(
                    model=self._summarization_model, ollama_url=self._ollama_url or None
                )
                facts = s.extract_key_facts(dropped_messages)
                if facts:
                    memory_block = "[Memory from earlier messages: " + "; ".join(facts[:10]) + "]"
                    system_prompt = f"{memory_block}\n\n{system_prompt}"
            except Exception as e:
                log.debug("Key facts extraction skipped: %s", e)

        result = []
        if dropped_count > 0:
            result.append({
                "role": "user",
                "content": f"[{dropped_count} earlier messages omitted to fit context]",
            })
        for ch in result_chunks:
            result.extend(ch)
        for ch in priority_chunks:
            result.extend(ch)
        result = summarized_block + result
        return result, system_prompt


def apply_smart_context(
    messages: list[dict],
    system_prompt: str,
    max_tokens: int,
    model: str = "",
    ollama_url: Optional[str] = None,
    summarization_model: str = "llama3.2:3b",
) -> tuple[list[dict], str]:
    """
    Apply smart context window management.
    Returns (processed_messages, system_prompt).
    """
    mgr = ContextWindowManager(
        max_tokens=max_tokens,
        model=model,
        ollama_url=ollama_url,
        summarization_model=summarization_model,
    )
    return mgr.process(messages, system_prompt)
