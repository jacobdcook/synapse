import logging
from typing import List, Optional
from .api import get_embeddings

log = logging.getLogger(__name__)

class Embedder:
    """Provides high-level access to code/text embeddings via Ollama."""
    
    def __init__(self, model: str = "nomic-embed-text"):
        self.model = model

    def embed_text(self, text: str) -> List[float]:
        """Generates a single embedding vector for the given text."""
        if not text.strip():
            return []
        
        # We reuse the existing implementation in api.py
        return get_embeddings(text, model=self.model)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embedding vectors for a batch of texts.
        Ollama's /api/embeddings is usually single-shot, so we loop for now.
        """
        results = []
        for i, text in enumerate(texts):
            if i > 0 and i % 10 == 0:
                log.debug(f"Embedding batch progress: {i}/{len(texts)}")
            results.append(self.embed_text(text))
        return results
