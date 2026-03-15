import os
import json
import logging
import fnmatch
from pathlib import Path
from PyQt5.QtCore import QThread, pyqtSignal

log = logging.getLogger(__name__)

class WorkspaceIndexer(QThread):
    indexing_progress = pyqtSignal(int, int) # current, total
    indexing_complete = pyqtSignal(dict) # the index
    
    def __init__(self, workspace_dir):
        super().__init__()
        self.workspace_dir = Path(workspace_dir)
        self.ignore_patterns = [
            '.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env',
            '*.pyc', '*.pyo', '*.so', '*.dll', '*.exe', '*.bin',
            '.DS_Store', 'Thumbs.db', '.idea', '.vscode'
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
                # Keep it simple: store filename, relative path, and a snippet/full content
                rel_path = file_path.relative_to(self.workspace_dir)
                index[str(rel_path)] = {
                    "name": file_path.name,
                    "content": content[:50000], # Limit content size
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

def search_index(index, query):
    results = []
    query = query.lower()
    for rel_path, data in index.items():
        if query in data["name"].lower() or query in data.get("content", "").lower():
            results.append({
                "path": rel_path,
                "name": data["name"],
                "score": 1.0 # Simple binary score for now
            })
    return results
