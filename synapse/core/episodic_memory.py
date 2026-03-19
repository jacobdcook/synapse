"""Episodic memory: conversation turn summaries for retrieval and patterns."""
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)

_local = threading.local()


def _get_conn(db_path):
    path_str = str(db_path)
    if not hasattr(_local, "conns"):
        _local.conns = {}
    if path_str not in _local.conns:
        try:
            _local.conns[path_str] = sqlite3.connect(path_str, check_same_thread=False)
            _local.conns[path_str].execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError as e:
            log.warning(f"Episodic DB connection failed: {e}")
            return None
    return _local.conns[path_str]


class EpisodicMemory:
    def __init__(self, db_path=None):
        self.db_path = db_path or (CONFIG_DIR / "episodic.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        conn = _get_conn(self.db_path)
        if not conn:
            return
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    role TEXT NOT NULL,
                    topic TEXT NOT NULL DEFAULT '',
                    key_facts TEXT NOT NULL DEFAULT '[]',
                    outcome TEXT NOT NULL DEFAULT '',
                    tools_used TEXT NOT NULL DEFAULT '[]',
                    sentiment TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_conv ON episodes(conversation_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_ts ON episodes(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ep_topic ON episodes(topic)")
            try:
                conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts
                    USING fts5(topic, outcome, content='episodes', content_rowid='id')
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
                        INSERT INTO episodes_fts(rowid, topic, outcome) VALUES (new.id, new.topic, new.outcome);
                    END
                """)
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS episodes_ad AFTER DELETE ON episodes BEGIN
                        INSERT INTO episodes_fts(episodes_fts, rowid, topic, outcome) VALUES ('delete', old.id, old.topic, old.outcome);
                    END
                """)
            except sqlite3.OperationalError:
                pass
            conn.commit()
        except sqlite3.OperationalError as e:
            log.warning(f"Episodic schema init failed: {e}")

    def log_episode(self, conv_id, turn_idx, role, topic, key_facts=None, outcome="", tools_used=None, sentiment=""):
        conn = _get_conn(self.db_path)
        if not conn:
            return
        key_facts = key_facts or []
        tools_used = tools_used or []
        ts = datetime.now(timezone.utc).isoformat()
        try:
            conn.execute("""
                INSERT INTO episodes (conversation_id, turn_index, timestamp, role, topic, key_facts, outcome, tools_used, sentiment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (conv_id, turn_idx, ts, role, topic[:500], json.dumps(key_facts), outcome[:2000], json.dumps(tools_used), sentiment[:100]))
            conn.commit()
        except sqlite3.OperationalError as e:
            log.warning(f"Episodic log failed: {e}")

    def query_recent(self, conv_id=None, limit=20):
        conn = _get_conn(self.db_path)
        if not conn:
            return []
        try:
            if conv_id:
                rows = conn.execute("""
                    SELECT id, conversation_id, turn_index, timestamp, role, topic, key_facts, outcome, tools_used, sentiment
                    FROM episodes WHERE conversation_id = ? ORDER BY turn_index DESC LIMIT ?
                """, (conv_id, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT id, conversation_id, turn_index, timestamp, role, topic, key_facts, outcome, tools_used, sentiment
                    FROM episodes ORDER BY timestamp DESC LIMIT ?
                """, (limit,)).fetchall()
            return [{"id": r[0], "conversation_id": r[1], "turn_index": r[2], "timestamp": r[3], "role": r[4],
                    "topic": r[5], "key_facts": json.loads(r[6]) if r[6] else [], "outcome": r[7],
                    "tools_used": json.loads(r[8]) if r[8] else [], "sentiment": r[9]} for r in rows]
        except (sqlite3.OperationalError, json.JSONDecodeError) as e:
            log.warning(f"Episodic query_recent failed: {e}")
            return []

    def query_by_topic(self, keywords, limit=10):
        conn = _get_conn(self.db_path)
        if not conn:
            return []
        try:
            fts = "episodes_fts"
            tokens = [k for k in keywords.split()[:5] if k and not k.startswith("-")]
            fts_query = " OR ".join(f'"{k}"' for k in tokens) if tokens else ""
            rows = []
            if fts_query:
                try:
                    rows = conn.execute("SELECT rowid FROM " + fts + " WHERE " + fts + " MATCH ? LIMIT ?",
                                        (fts_query, limit)).fetchall()
                except sqlite3.OperationalError:
                    pass
            if not rows:
                pattern = "%" + keywords.strip()[:50] + "%"
                rows = conn.execute("""
                    SELECT id FROM episodes WHERE topic LIKE ? OR outcome LIKE ? ORDER BY timestamp DESC LIMIT ?
                """, (pattern, pattern, limit)).fetchall()
                ids = [r[0] for r in rows]
            else:
                ids = [r[0] for r in rows]
            if not ids:
                return []
            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(f"""
                SELECT id, conversation_id, turn_index, timestamp, role, topic, key_facts, outcome, tools_used, sentiment
                FROM episodes WHERE id IN ({placeholders}) ORDER BY timestamp DESC
            """, ids).fetchall()
            return [{"id": r[0], "conversation_id": r[1], "turn_index": r[2], "timestamp": r[3], "role": r[4],
                    "topic": r[5], "key_facts": json.loads(r[6]) if r[6] else [], "outcome": r[7],
                    "tools_used": json.loads(r[8]) if r[8] else [], "sentiment": r[9]} for r in rows]
        except sqlite3.OperationalError as e:
            log.warning(f"Episodic query_by_topic failed: {e}")
            return []

    def get_conversation_summary(self, conv_id):
        episodes = self.query_recent(conv_id=conv_id, limit=20)
        if not episodes:
            return ""
        topics = []
        tools = set()
        for e in reversed(episodes):
            if e.get("topic"):
                topics.append(e["topic"][:80])
            for t in e.get("tools_used", []):
                tools.add(str(t))
        summary = f"Conversation covered: {', '.join(topics[:5])}. " if topics else ""
        if tools:
            summary += f"Tools used: {', '.join(list(tools)[:5])}."
        return summary.strip() or "No summary available."

    def get_user_patterns(self):
        conn = _get_conn(self.db_path)
        if not conn:
            return {"topics": [], "preferred_tools": [], "frustrations": []}
        try:
            rows = conn.execute("SELECT topic, outcome, tools_used, sentiment FROM episodes").fetchall()
            topics = {}
            tools = {}
            frustrations = []
            for r in rows:
                t = (r[0] or "").strip()
                if t:
                    topics[t[:60]] = topics.get(t[:60], 0) + 1
                for tool in json.loads(r[2] or "[]"):
                    tools[tool] = tools.get(tool, 0) + 1
                if (r[3] or "").lower() in ("frustrated", "negative", "confused"):
                    frustrations.append((r[1] or "")[:100])
            top_topics = sorted(topics.items(), key=lambda x: -x[1])[:10]
            top_tools = sorted(tools.items(), key=lambda x: -x[1])[:10]
            return {"topics": [t[0] for t in top_topics], "preferred_tools": [t[0] for t in top_tools],
                    "frustrations": frustrations[-20:]}
        except (sqlite3.OperationalError, json.JSONDecodeError) as e:
            log.warning(f"Episodic get_user_patterns failed: {e}")
            return {"topics": [], "preferred_tools": [], "frustrations": []}

    def cleanup(self, days=90):
        conn = _get_conn(self.db_path)
        if not conn:
            return
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            conn.execute("DELETE FROM episodes WHERE timestamp < ?", (cutoff,))
            conn.commit()
        except sqlite3.OperationalError as e:
            log.warning(f"Episodic cleanup failed: {e}")

    def clear_all(self):
        conn = _get_conn(self.db_path)
        if not conn:
            return
        try:
            conn.execute("DELETE FROM episodes")
            conn.commit()
        except sqlite3.OperationalError as e:
            log.warning(f"Episodic clear failed: {e}")
