#!/usr/bin/env python3
"""Delete Synapse conversations with title 'New Chat' (empty/untitled)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from synapse.utils.constants import CONV_DIR

def main():
    deleted = 0
    for f in CONV_DIR.glob("*.json"):
        try:
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("title") == "New Chat" and not data.get("messages", []):
                f.unlink()
                deleted += 1
                print(f"Deleted {f.name}")
        except (json.JSONDecodeError, OSError) as e:
            print(f"Skipped {f.name}: {e}", file=sys.stderr)
    print(f"Cleared {deleted} 'New Chat' conversation(s)")

if __name__ == "__main__":
    main()
