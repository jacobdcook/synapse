import sqlite3
import json
import logging
from pathlib import Path
from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)

class GraphStore:
    """A simple persistent knowledge graph store using SQLite."""
    
    def __init__(self, db_path=None):
        if db_path is None:
            self.db_path = CONFIG_DIR / "knowledge_graph.db"
        else:
            self.db_path = Path(db_path)
            
        self._init_db()

    def _init_db(self):
        """Initialize tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS nodes (
                        id TEXT PRIMARY KEY,
                        type TEXT,
                        name TEXT,
                        content TEXT,
                        metadata TEXT
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS edges (
                        source TEXT,
                        target TEXT,
                        relation TEXT,
                        weight REAL,
                        PRIMARY KEY (source, target, relation),
                        FOREIGN KEY (source) REFERENCES nodes (id),
                        FOREIGN KEY (target) REFERENCES nodes (id)
                    )
                """)
                # Indexes for faster traversal
                conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target)")
                log.info(f"GraphStore initialized at {self.db_path}")
        except Exception as e:
            log.error(f"Failed to initialize GraphStore: {e}")

    def add_node(self, node_id, node_type, name, content="", metadata=None):
        """Add or update a node in the graph."""
        meta_json = json.dumps(metadata or {})
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO nodes (id, type, name, content, metadata) VALUES (?, ?, ?, ?, ?)",
                    (node_id, node_type, name, content, meta_json)
                )
        except Exception as e:
            log.error(f"Error adding node {node_id}: {e}")

    def add_edge(self, source_id, target_id, relation, weight=1.0):
        """Add or update a relationship between nodes."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO edges (source, target, relation, weight) VALUES (?, ?, ?, ?)",
                    (source_id, target_id, relation, weight)
                )
        except Exception as e:
            log.error(f"Error adding edge {source_id} -> {target_id}: {e}")

    def get_node(self, node_id):
        """Retrieve a single node by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "type": row[1],
                        "name": row[2],
                        "content": row[3],
                        "metadata": json.loads(row[4])
                    }
        except Exception as e:
            log.error(f"Error getting node {node_id}: {e}")
        return None

    def get_neighbors(self, node_id, max_depth=1):
        """Get nodes connected to the given node up to a certain depth (BFS)."""
        visited = {node_id}
        queue = [(node_id, 0)]
        results = []

        try:
            with sqlite3.connect(self.db_path) as conn:
                while queue:
                    current_id, depth = queue.pop(0)
                    if depth >= max_depth:
                        continue
                    
                    # Find all outgoing and incoming neighbors
                    cursor = conn.execute("""
                        SELECT target, relation, weight FROM edges WHERE source = ?
                        UNION
                        SELECT source, relation, weight FROM edges WHERE target = ?
                    """, (current_id, current_id))
                    
                    for neighbor_id, relation, weight in cursor.fetchall():
                        if neighbor_id not in visited:
                            visited.add(neighbor_id)
                            node_data = self.get_node(neighbor_id)
                            if node_data:
                                node_data["relation"] = relation
                                node_data["weight"] = weight
                                node_data["depth"] = depth + 1
                                results.append(node_data)
                                queue.append((neighbor_id, depth + 1))
        except Exception as e:
            log.error(f"Error traversing graph from {node_id}: {e}")
            
        return results

    def query_entities(self, query_text, limit=10):
        """Simple keyword search on node names and content."""
        search = f"%{query_text}%"
        results = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM nodes WHERE name LIKE ? OR content LIKE ? LIMIT ?",
                    (search, search, limit)
                )
                for row in cursor.fetchall():
                    results.append({
                        "id": row[0],
                        "type": row[1],
                        "name": row[2],
                        "content": row[3],
                        "metadata": json.loads(row[4])
                    })
        except Exception as e:
            log.error(f"Error searching nodes for '{query_text}': {e}")
        return results

    def clear(self):
        """Wipe the entire graph."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM edges")
                conn.execute("DELETE FROM nodes")
        except Exception as e:
            log.error(f"Error clearing GraphStore: {e}")
