import os
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt5.QtCore import QThread, pyqtSignal
from .embeddings import Embedder

log = logging.getLogger(__name__)

class SemanticIndexer:
    """Manages a local vector index for semantic search across the codebase."""
    
    def __init__(self, workspace_root: str, index_file: str = "semantic_index.json"):
        self.workspace_root = Path(workspace_root)
        self.index_path = self.workspace_root / ".synapse" / index_file
        self.embedder = Embedder()
        self.index: Dict[str, Any] = {}
        self._load_index()

    def _load_index(self):
        """Loads the index from disk if it exists."""
        if self.index_path.exists():
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    self.index = json.load(f)
                log.info(f"Loaded semantic index from {self.index_path}")
            except Exception as e:
                log.error(f"Failed to load semantic index: {e}")
                self.index = {}

    def save_index(self):
        """Saves the current index to disk."""
        try:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(self.index, f)
            log.info(f"Saved semantic index to {self.index_path}")
        except Exception as e:
            log.error(f"Failed to save semantic index: {e}")

    def index_file(self, rel_path: str, content: str):
        """Chunks and indexes a single file."""
        if not content.strip():
            return

        # Simple line-based chunking for now
        lines = content.splitlines()
        chunks = []
        chunk_size = 50  # lines per chunk
        overlap = 10
        
        for i in range(0, len(lines), chunk_size - overlap):
            chunk_lines = lines[i:i + chunk_size]
            chunk_text = "\n".join(chunk_lines)
            if len(chunk_text.strip()) < 50: # Skip tiny chunks
                continue
            
            embedding = self.embedder.embed_text(chunk_text)
            if embedding:
                chunks.append({
                    "text": chunk_text,
                    "embedding": embedding,
                    "line_start": i + 1,
                    "line_end": i + len(chunk_lines)
                })
            
            if i + chunk_size >= len(lines):
                break

        if chunks:
            self.index[rel_path] = {
                "chunks": chunks,
                "mtime": os.path.getmtime(self.workspace_root / rel_path)
            }

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Performs a semantic search using cosine similarity."""
        query_embedding = self.embedder.embed_text(query)
        if not query_embedding:
            return []

        results = []
        q_vec = np.array(query_embedding)
        norm_q = np.linalg.norm(q_vec)
        
        if norm_q == 0:
            return []

        for rel_path, data in self.index.items():
            for chunk in data.get("chunks", []):
                chunk_vec = np.array(chunk["embedding"])
                norm_c = np.linalg.norm(chunk_vec)
                
                if norm_c == 0:
                    continue
                
                score = np.dot(q_vec, chunk_vec) / (norm_q * norm_c)
                if score > 0.4:  # Threshold
                    results.append({
                        "path": rel_path,
                        "text": chunk["text"],
                        "score": float(score),
                        "line_start": chunk["line_start"],
                        "line_end": chunk["line_end"]
                    })

        # Sort by score and deduplicate by file (keeping best chunk)
        results.sort(key=lambda x: x["score"], reverse=True)
        
        final_results = []
        seen_paths = set()
        for res in results:
            if res["path"] not in seen_paths:
                final_results.append(res)
                seen_paths.add(res["path"])
            if len(final_results) >= top_k:
                break
                
        return final_results

class SemanticWorkspaceIndexer(QThread):
    """Background thread to index the entire workspace semantically."""
    progress = pyqtSignal(int, int) # current, total
    finished = pyqtSignal(dict)
    
    def __init__(self, workspace_root: str, semantic_indexer: SemanticIndexer):
        super().__init__()
        self.workspace_root = Path(workspace_root)
        self.semantic_indexer = semantic_indexer
        self.ignore_patterns = [
            '.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env',
            '*.pyc', '*.pyo', '*.so', '*.dll', '*.exe', '*.bin',
            '.DS_Store', 'Thumbs.db', '.idea', '.vscode', '.ollama', '.synapse'
        ]
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        files_to_index = []
        import fnmatch
        
        for root, dirs, files in os.walk(self.workspace_root):
            if self._stop_flag: break
            
            # Filter directories
            dirs_to_keep = [d for d in dirs if not self._is_ignored(d)]
            dirs.clear()
            dirs.extend(dirs_to_keep)
            
            for file in files:
                if self._is_ignored(file):
                    continue
                files_to_index.append(Path(root) / file)
        
        total = len(files_to_index)
        supported_ext = {'.py', '.js', '.ts', '.tsx', '.jsx', '.md', '.txt', '.html', '.css'}
        
        for i, file_path in enumerate(files_to_index):
            if self._stop_flag: break
            
            if file_path.suffix.lower() in supported_ext:
                try:
                    rel_path = str(file_path.relative_to(self.workspace_root))
                    content = file_path.read_text(errors='replace')
                    if content.strip():
                        self.semantic_indexer.index_file(rel_path, content)
                except Exception as e:
                    log.warning(f"Failed to index {file_path}: {e}")
            
            self.progress.emit(i + 1, total)
        
        self.semantic_indexer.save_index()
        self.finished.emit(self.semantic_indexer.index)

    def _is_ignored(self, name):
        import fnmatch
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False
