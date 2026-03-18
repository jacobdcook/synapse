import os
import logging
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)

class ProjectRulesManager:
    """Manages project-specific rules and instructions (e.g., .synapserc, .cursorrules)."""
    
    RULE_FILES = [
        ".synapserc",
        ".synapse/rules.md",
        ".cursorrules",
        "instructions.md"
    ]

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.rules: List[str] = []
        self.load_rules()

    def load_rules(self):
        """Discovers and loads rule files from the workspace root."""
        self.rules = []
        for file_name in self.RULE_FILES:
            rule_path = self.workspace_root / file_name
            if rule_path.exists() and rule_path.is_file():
                try:
                    content = rule_path.read_text(errors='replace').strip()
                    if content:
                        self.rules.append(f"--- Rules from {file_name} ---\n{content}")
                        log.info(f"Loaded project rules from {file_name}")
                except Exception as e:
                    log.error(f"Failed to load rules from {file_name}: {e}")

    def get_system_instructions(self) -> str:
        """Returns the combined rules formatted for system prompt injection."""
        if not self.rules:
            return ""
        
        combined = "\n\n".join(self.rules)
        return f"\n\n### PROJECT-SPECIFIC RULES AND INSTRUCTIONS\n{combined}\n"

    def get_ignore_patterns(self) -> List[str]:
        """Returns extra ignore patterns defined in rules (placeholder for now)."""
        return []
