import os
import json
import logging
import fnmatch
try:
    import numpy as np
except ImportError:
    np = None
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal
from .api import get_embeddings

log = logging.getLogger(__name__)

def chunk_text(text, chunk_size=1500, overlap=200):
    """Split text into overlapping chunks for better context preservation."""
    chunks = []
    if not text:
        return chunks
    
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
        if end >= len(text):
            break
    return chunks

def cosine_similarity(v1, v2):
    """Calculate cosine similarity between two vectors."""
    if v1 is None or v2 is None or len(v1) == 0 or len(v2) == 0:
        return 0.0
    v1 = np.array(v1)
    v2 = np.array(v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return np.dot(v1, v2) / (norm1 * norm2)

class WorkspaceIndexer(QThread):
    indexing_progress = pyqtSignal(int, int) # current, total
    indexing_complete = pyqtSignal(dict) # the index
    
    def __init__(self, workspace_dir):
        super().__init__()
        self.workspace_dir = Path(workspace_dir)
        self.ignore_patterns = [
            '.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env',
            '*.pyc', '*.pyo', '*.so', '*.dll', '*.exe', '*.bin',
            '.DS_Store', 'Thumbs.db', '.idea', '.vscode', '.ollama'
        ]
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        if not self.workspace_dir.exists():
            return
            
        index = {}
        files_to_index = []
        
        for root, dirs, files in os.walk(self.workspace_dir):
            if self._stop_flag: break
            
            # Filter directories
            dirs[:] = [d for d in dirs if not self._is_ignored(d)]
            
            for file in files:
                if self._is_ignored(file):
                    continue
                files_to_index.append(Path(root) / file)
        
        total = len(files_to_index)
        for i, file_path in enumerate(files_to_index):
            if self._stop_flag: break
            
            try:
                # Only index text files
                content = file_path.read_text(errors='replace')
                rel_path = str(file_path.relative_to(self.workspace_dir))
                
                # Chunk the content
                chunks = chunk_text(content)
                file_chunks = []
                
                for chunk_idx, chunk in enumerate(chunks[:20]): # Limit chunks per file
                    if self._stop_flag: break
                    embedding = get_embeddings(chunk)
                    if embedding:
                        file_chunks.append({
                            "text": chunk,
                            "embedding": embedding,
                            "index": chunk_idx
                        })
                
                index[rel_path] = {
                    "name": file_path.name,
                    "chunks": file_chunks,
                    "size": file_path.stat().st_size
                }
            except Exception as e:
                log.warning(f"Failed to index {file_path}: {e}")
            
            self.indexing_progress.emit(i + 1, total)
        
        self.indexing_complete.emit(index)

    def _is_ignored(self, name):
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

def search_index(index, query, top_k=5):
    """Search the vector index using cosine similarity."""
    query_embedding = get_embeddings(query)
    if not query_embedding:
        # Fallback to simple keyword search if embedding fails
        results = []
        query = query.lower()
        for rel_path, data in index.items():
            if query in rel_path.lower() or query in data["name"].lower():
                results.append({"path": rel_path, "name": data["name"], "score": 1.0})
        return results[:top_k]

    all_results = []
    for rel_path, data in index.items():
        for chunk in data.get("chunks", []):
            score = cosine_similarity(query_embedding, chunk["embedding"])
            if score > 0.3: # Threshold
                all_results.append({
                    "path": rel_path,
                    "name": data["name"],
                    "content": chunk["text"],
                    "score": float(score)
                })
    
    # Sort by score and take top_k
    all_results.sort(key=lambda x: x["score"], reverse=True)
    
    # Deduplicate by path (take best chunk per file)
    seen_paths = set()
    deduped = []
    for res in all_results:
        if res["path"] not in seen_paths:
            deduped.append(res)
            seen_paths.add(res["path"])
        if len(deduped) >= top_k:
            break
            
    return deduped
