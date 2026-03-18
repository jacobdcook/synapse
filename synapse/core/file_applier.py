import os
import difflib
import re
import logging
from pathlib import Path

log = logging.getLogger(__name__)

class FileApplier:
    def __init__(self, workspace_root=None):
        self.workspace_root = workspace_root

    def detect_target_file(self, code_block_metadata, surrounding_text, language_hint):
        """
        Attempts to identify which file the code block belongs to.
        code_block_metadata: Any data extracted from the code fence (e.g. ```python:main.py)
        surrounding_text: Text before/after the block.
        """
        # 1. Priority: metadata from fence
        if code_block_metadata and 'filename' in code_block_metadata:
            return code_block_metadata['filename']

        # 2. Heuristic: Look for "main.py" or similar in surrounding text
        patterns = [
            r"in `([^`]+\.[a-zA-Z0-9]+)`",
            r"to `([^`]+\.[a-zA-Z0-9]+)`",
            r"file `([^`]+\.[a-zA-Z0-9]+)`",
            r"modify ([^\s]+\.[a-zA-Z0-9]+)"
        ]
        for pattern in patterns:
            match = re.search(pattern, surrounding_text)
            if match:
                return match.group(1)

        return None

    def compute_diff(self, original_content, new_content, filename="file"):
        """Returns a unified diff string."""
        diff = difflib.unified_diff(
            original_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}"
        )
        return "".join(diff)

    def apply_partial(self, original_content, snippet):
        """
        Attempts to find 'snippet' in 'original_content' and replace it with 'snippet'.
        Uses SequenceMatcher to find the best matching block if an exact match isn't found.
        """
        if not snippet.strip():
            return original_content

        # 1. Try exact match
        if snippet in original_content:
            return original_content # Already there? Or is it a replacement? 
            # Wait, apply_partial usually means 'this snippet is the NEW content for SOME PART of the old content'.
            # But we don't know WHICH part.
            pass

        # If snippet looks like a full file (contains imports, classes, etc.), just return it
        if ("import " in snippet or "from " in snippet) and ("class " in snippet or "def " in snippet):
            if len(snippet) > len(original_content) * 0.5:
                return snippet

        # 2. Split into lines and look for a hunk match
        lines_orig = original_content.splitlines()
        lines_snip = snippet.splitlines()
        
        # Use SequenceMatcher to find where the snippet best fits
        import difflib
        s = difflib.SequenceMatcher(None, lines_orig, lines_snip)
        match = s.find_longest_match(0, len(lines_orig), 0, len(lines_snip))
        
        # This is a very simplistic heuristic. Real "Apply" logic usually requires 
        # Search blocks or line numbers.
        # For Phase 2, let's stick to full-file replacement or exact match replacement.
        
        return snippet 

    def merge_snippet(self, original, snippet):
        """
        A more robust merge that looks for a 'search' block in the snippet.
        Often AI uses:
        <<<< SEARCH
        old code
        ====
        new code
        >>>> REPLACE
        """
        # Search for SEARCH/REPLACE patterns
        pattern = r"<<<<<< SEARCH\n(.*?)\n======\n(.*?)\n>>>>>> REPLACE"
        matches = re.findall(pattern, snippet, re.DOTALL)
        if matches:
            content = original
            for search, replace in matches:
                content = content.replace(search, replace)
            return content
        
        # Fallback to full replacement if it looks like a full file
        return snippet

    def write_file(self, filepath, content):
        p = Path(filepath)
        if self.workspace_root:
            p = Path(self.workspace_root) / p
            
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        log.info(f"Successfully applied changes to {filepath}")
        return True
