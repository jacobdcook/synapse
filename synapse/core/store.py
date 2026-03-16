import json
import os
import uuid
import logging
import tempfile
import sqlite3
from datetime import datetime, timezone
from ..utils.constants import CONV_DIR, CONFIG_DIR, DEFAULT_MODEL, DEFAULT_SYSTEM_PROMPT

log = logging.getLogger(__name__)

_INDEX_DB = CONFIG_DIR / "conversations.db"


def _get_index_db():
    db = sqlite3.connect(str(_INDEX_DB), check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'Untitled',
            model TEXT NOT NULL DEFAULT '',
            folder TEXT NOT NULL DEFAULT 'General',
            tags TEXT NOT NULL DEFAULT '[]',
            pinned INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT '',
            message_count INTEGER NOT NULL DEFAULT 0,
            preview TEXT NOT NULL DEFAULT ''
        )
    """)
    db.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS conv_fts
        USING fts5(id, title, tags, preview, content='conversations', content_rowid='rowid')
    """)
    db.commit()
    return db


class ConversationStore:
    def __init__(self):
        CONV_DIR.mkdir(parents=True, exist_ok=True)
        self._db = _get_index_db()
        self._ensure_index()

    def _ensure_index(self):
        """Rebuild index from JSON files if empty or stale."""
        row = self._db.execute("SELECT COUNT(*) FROM conversations").fetchone()
        json_count = len(list(CONV_DIR.glob("*.json")))
        if row[0] == 0 and json_count > 0:
            log.info(f"Building conversation index from {json_count} files...")
            self._rebuild_index()

    def _rebuild_index(self):
        for f in CONV_DIR.glob("*.json"):
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                self._index_conversation(data)
            except Exception as e:
                log.warning(f"Skipping {f.name} during index rebuild: {e}")
        self._db.commit()

    def _index_conversation(self, conv):
        msgs = conv.get("messages", [])
        if not msgs and conv.get("title") == "New Chat":
            return
        preview = ""
        for m in msgs[:3]:
            preview += m.get("content", "")[:200] + " "
        tags_json = json.dumps(conv.get("tags", []))
        self._db.execute("""
            INSERT OR REPLACE INTO conversations (id, title, model, folder, tags, pinned, updated_at, message_count, preview)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conv["id"],
            conv.get("title", "Untitled"),
            conv.get("model", DEFAULT_MODEL),
            conv.get("folder", "General"),
            tags_json,
            1 if conv.get("pinned") else 0,
            conv.get("updated_at", ""),
            len(msgs),
            preview.strip()[:500]
        ))
        try:
            self._db.execute("INSERT OR REPLACE INTO conv_fts(id, title, tags, preview) VALUES (?, ?, ?, ?)",
                             (conv["id"], conv.get("title", ""), " ".join(conv.get("tags", [])), preview.strip()[:500]))
        except Exception:
            pass

    def list_conversations(self):
        try:
            rows = self._db.execute(
                "SELECT id, title, model, folder, tags, pinned, updated_at FROM conversations ORDER BY pinned DESC, updated_at DESC"
            ).fetchall()
            if not rows:
                return self._list_from_disk()
            return [
                {
                    "id": r[0], "title": r[1], "model": r[2], "folder": r[3],
                    "tags": json.loads(r[4]) if r[4] else [], "pinned": bool(r[5]),
                    "updated_at": r[6]
                }
                for r in rows
            ]
        except Exception as e:
            log.warning(f"Index query failed, falling back to disk: {e}")
            return self._list_from_disk()

    def _list_from_disk(self):
        convos = []
        for f in CONV_DIR.glob("*.json"):
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
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
        pinned = [c for c in convos if c.get("pinned")]
        unpinned = [c for c in convos if not c.get("pinned")]
        pinned.sort(key=lambda c: c["updated_at"], reverse=True)
        unpinned.sort(key=lambda c: c["updated_at"], reverse=True)
        return pinned + unpinned

    def load(self, conv_id):
        path = CONV_DIR / f"{conv_id}.json"
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                log.error(f"Corrupted conversation file {conv_id}: {e}")
        return None

    def save(self, conversation):
        if not conversation.get("messages") and conversation.get("title") == "New Chat":
            log.debug(f"Skipping save for empty conversation {conversation['id']}")
            return

        conversation["updated_at"] = datetime.now(timezone.utc).isoformat()
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

        try:
            self._index_conversation(conversation)
            self._db.commit()
        except Exception as e:
            log.debug(f"Index update failed (non-critical): {e}")

    def delete(self, conv_id):
        path = CONV_DIR / f"{conv_id}.json"
        if path.exists():
            path.unlink()
        try:
            self._db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            self._db.execute("DELETE FROM conv_fts WHERE id = ?", (conv_id,))
            self._db.commit()
        except Exception as e:
            log.debug(f"Index delete failed (non-critical): {e}")

    def search(self, query):
        query_lower = query.strip().lower()
        if not query_lower:
            return self.list_conversations()
        try:
            fts_query = " OR ".join(f'"{w}"' for w in query_lower.split() if w)
            rows = self._db.execute(
                "SELECT c.id, c.title, c.model, c.folder, c.tags, c.pinned, c.updated_at "
                "FROM conv_fts f JOIN conversations c ON f.id = c.id "
                "WHERE conv_fts MATCH ? ORDER BY c.updated_at DESC LIMIT 50",
                (fts_query,)
            ).fetchall()
            if rows:
                return [
                    {
                        "id": r[0], "title": r[1], "model": r[2], "folder": r[3],
                        "tags": json.loads(r[4]) if r[4] else [], "pinned": bool(r[5]),
                        "updated_at": r[6]
                    }
                    for r in rows
                ]
        except Exception as e:
            log.debug(f"FTS search failed, falling back: {e}")

        results = []
        for c in self.list_conversations():
            if query_lower in c["title"].lower():
                results.append(c)
                continue
            tags = c.get("tags", [])
            if any(query_lower.lstrip("#") in t.lower() for t in tags):
                results.append(c)
                continue
            full = self.load(c["id"])
            if full:
                for msg in full.get("messages", []):
                    if query_lower in msg.get("content", "").lower():
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
        "history": [],
        "pinned": False,
        "folder": "General",
        "tags": [],
    }
