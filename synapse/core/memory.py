import json
import logging
from pathlib import Path
from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)

class MemoryManager:
    """
    Manages long-term persistent memory (Fact Store) for Synapse.
    Stores user preferences, project details, and learned facts.
    """
    def __init__(self):
        self.memory_file = CONFIG_DIR / "memory.json"
        self.memory = self._load()

    def _load(self):
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                log.error(f"Failed to load memory: {e}")
        return {
            "facts": [],        # General observations
            "preferences": {},  # Explicit user settings/likes
            "projects": {}      # Per-project metadata
        }

    def save(self):
        try:
            with open(self.memory_file, "w") as f:
                json.dump(self.memory, f, indent=4)
        except Exception as e:
            log.error(f"Failed to save memory: {e}")

    def add_fact(self, fact):
        if fact not in self.memory["facts"]:
            self.memory["facts"].append(fact)
            self.save()
            return True
        return False

    def update_preference(self, key, value):
        self.memory["preferences"][key] = value
        self.save()

    def get_context_string(self):
        """Returns a formatted string of known facts for the system prompt."""
        lines = ["KNOWN FACTS & PREFERENCES:"]
        for fact in self.memory["facts"]:
            lines.append(f"- {fact}")
        for k, v in self.memory["preferences"].items():
            lines.append(f"- {k}: {v}")
        
        if len(lines) == 1:
            return "" # No memory yet
        return "\n".join(lines)

    def clear(self):
        self.memory = {"facts": [], "preferences": {}, "projects": {}}
        self.save()
