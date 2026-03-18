import os
import re
import logging
from pathlib import Path

log = logging.getLogger(__name__)

class ContextManager:
    """
    Handles detection and resolution of @-mentions in chat text.
    Mentions can be files, folders, or special keywords like @terminal.
    """
    
    MENTION_PATTERN = r'@([a-zA-Z0-9_\-\./]+)'

    def __init__(self, workspace_root=None):
        self.workspace_root = Path(workspace_root) if workspace_root else None

    def find_mentions(self, text):
        """Returns a list of unique @-mentions found in the text."""
        return list(set(re.findall(self.MENTION_PATTERN, text)))

    def resolve_context(self, text, terminal_output=None):
        """
        Scans text for mentions and returns a list of context snippets.
        Each snippet is a dict with 'type', 'name', and 'content'.
        """
        mentions = self.find_mentions(text)
        resolved = []
        
        for mention in mentions:
            if mention == "terminal" and terminal_output:
                resolved.append({
                    "type": "terminal",
                    "name": "terminal",
                    "content": terminal_output
                })
                continue
                
            ctx = self._resolve_single(mention)
            if ctx:
                resolved.append(ctx)
                
        return resolved

    def _resolve_single(self, mention):
        """Resolves a single mention to a context object."""
        if not self.workspace_root:
            return None
            
        # Try to find the file/folder relative to workspace
        target_path = self.workspace_root / mention
        
        if target_path.exists():
            if target_path.is_file():
                try:
                    content: str = target_path.read_text(errors='replace')
                    # Truncate if too large? 
                    # For now, let's include the whole file if it's reasonable
                    if len(content) > 50000:
                        content = content[:50000] + "\n... (truncated)"
                    return {
                        "type": "file",
                        "name": mention,
                        "path": str(target_path),
                        "content": content
                    }
                except Exception as e:
                    log.error(f"Failed to read mention {mention}: {e}")
            elif target_path.is_dir():
                try:
                    files: list[str] = os.listdir(target_path)
                    content = f"Folder content of {mention}:\n" + "\n".join(files[:50])
                    if len(files) > 50:
                        content += f"\n... and {len(files)-50} more files."
                    return {
                        "type": "folder",
                        "name": mention,
                        "path": str(target_path),
                        "content": content
                    }
                except Exception as e:
                    log.error(f"Failed to list folder mention {mention}: {e}")
                    
        return None

    def build_context_prompt(self, resolved_mentions):
        """Converts resolved mentions into a string to be prepended to the AI prompt."""
        if not resolved_mentions:
            return ""
            
        prompt = "\n--- RELEVANT CONTEXT ---\n"
        for ctx in resolved_mentions:
            if ctx['type'] == 'file':
                prompt += f"\nFile: {ctx['name']}\n```\n{ctx['content']}\n```\n"
            elif ctx['type'] == 'folder':
                prompt += f"\nFolder: {ctx['name']}\n{ctx['content']}\n"
            elif ctx['type'] == 'terminal':
                prompt += f"\nTerminal Output:\n```\n{ctx['content']}\n```\n"
        prompt += "--- END CONTEXT ---\n"
        return prompt
