import json
import uuid
import logging
from datetime import datetime
from ..utils.constants import CONV_DIR, DEFAULT_MODEL, DEFAULT_SYSTEM_PROMPT

log = logging.getLogger(__name__)

class ConversationStore:
    def __init__(self):
        CONV_DIR.mkdir(parents=True, exist_ok=True)

    def list_conversations(self):
        convos = []
        for f in CONV_DIR.glob("*.json"):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                    convos.append({
                        "id": data["id"],
                        "title": data.get("title", "Untitled"),
                        "updated_at": data.get("updated_at", ""),
                        "model": data.get("model", DEFAULT_MODEL),
                        "pinned": data.get("pinned", False),
                        "tags": data.get("tags", []),
                    })
            except (json.JSONDecodeError, KeyError) as e:
                log.warning(f"Skipping corrupted conversation file {f}: {e}")
                continue
        convos.sort(key=lambda c: (not c.get("pinned", False), c["updated_at"]), reverse=False)
        pinned = [c for c in convos if c.get("pinned")]
        unpinned = [c for c in convos if not c.get("pinned")]
        pinned.sort(key=lambda c: c["updated_at"], reverse=True)
        unpinned.sort(key=lambda c: c["updated_at"], reverse=True)
        return pinned + unpinned

    def load(self, conv_id):
        path = CONV_DIR / f"{conv_id}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    def save(self, conversation):
        conversation["updated_at"] = datetime.now().isoformat()
        path = CONV_DIR / f"{conversation['id']}.json"
        with open(path, "w") as f:
            json.dump(conversation, f, indent=2)

    def delete(self, conv_id):
        path = CONV_DIR / f"{conv_id}.json"
        if path.exists():
            path.unlink()

    def search(self, query):
        query = query.lower()
        results = []
        for c in self.list_conversations():
            if query in c["title"].lower():
                results.append(c)
                continue
            tags = c.get("tags", [])
            if any(query.lstrip("#") in t.lower() for t in tags):
                results.append(c)
                continue
            full = self.load(c["id"])
            if full:
                for msg in full.get("messages", []):
                    if query in msg.get("content", "").lower():
                        results.append(c)
                        break
        return results

def new_conversation(model=DEFAULT_MODEL, system_prompt=DEFAULT_SYSTEM_PROMPT):
    return {
        "id": str(uuid.uuid4()),
        "title": "New Chat",
        "model": model,
        "system_prompt": system_prompt,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "messages": [],
        "pinned": False,
    }
