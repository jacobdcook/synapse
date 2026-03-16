import json
import os
import uuid
import logging
import tempfile
from datetime import datetime, timezone
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
                    # Skip empty "New Chat" entries to prevent clutter
                    messages = data.get("messages", [])
                    if not messages and data.get("title") == "New Chat":
                        continue
                        
                    convos.append({
                        "id": data["id"],
                        "title": data.get("title", "Untitled"),
                        "updated_at": data.get("updated_at", ""),
                        "model": data.get("model", DEFAULT_MODEL),
                        "pinned": data.get("pinned", False),
                        "tags": data.get("tags", []),
                        "folder": data.get("folder", "General"),
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
        # Don't save empty "New Chat" conversations
        if not conversation.get("messages") and conversation.get("title") == "New Chat":
            log.debug(f"Skipping save for empty conversation {conversation['id']}")
            return

        conversation["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Ensure all messages have IDs for branching
        total_tokens = 0
        if "messages" in conversation:
            if "history" not in conversation:
                conversation["history"] = []

            existing_ids = {m.get("id") for m in conversation["history"]}
            last_id = None
            for msg in conversation["messages"]:
                if "id" not in msg:
                    msg["id"] = str(uuid.uuid4())
                if "parent_id" not in msg:
                    msg["parent_id"] = last_id

                content = str(msg.get("content", ""))
                total_tokens += len(content.split()) * 1.5 + 20

                if msg["id"] not in existing_ids:
                    conversation["history"].append(msg)
                    existing_ids.add(msg["id"])

                last_id = msg["id"]
        
        conversation["stats"] = {
            "message_count": len(conversation.get("messages", [])),
            "total_tokens": int(total_tokens),
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
        path = CONV_DIR / f"{conversation['id']}.json"
        fd, tmp_path = tempfile.mkstemp(dir=str(CONV_DIR), suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(conversation, f, indent=2)
            os.replace(tmp_path, str(path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

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

    def move_to_folder(self, conv_id, folder_name):
        conv = self.load(conv_id)
        if conv:
            conv["folder"] = folder_name
            self.save(conv)
            return True
        return False

    def add_tag(self, conv_id, tag):
        conv = self.load(conv_id)
        if conv:
            tags = conv.get("tags", [])
            tag = tag.strip().lstrip("#")
            if tag and tag not in tags:
                tags.append(tag)
                conv["tags"] = tags
                self.save(conv)
                return True
        return False

def new_conversation(model=DEFAULT_MODEL, system_prompt=DEFAULT_SYSTEM_PROMPT):
    return {
        "id": str(uuid.uuid4()),
        "title": "New Chat",
        "model": model,
        "system_prompt": system_prompt,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "messages": [],
        "history": [], # To store all branched messages
        "pinned": False,
        "folder": "General",
        "tags": [],
    }
