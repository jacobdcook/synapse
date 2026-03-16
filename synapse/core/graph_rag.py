import json
import logging
import hashlib
from .api import _request_json
from .graph_store import GraphStore
from .symbol_extractor import PythonSymbolExtractor
from ..utils.constants import DEFAULT_MODEL

log = logging.getLogger(__name__)

class GraphRAGService:
    """Service to handle Graph Retrieval-Augmented Generation logic."""
    
    def __init__(self, model=DEFAULT_MODEL):
        self.model = model
        self.graph_store = GraphStore()

    def index_symbols(self, file_path, content):
        """Extract and store structural symbols from code."""
        extractor = PythonSymbolExtractor()
        symbols, relations = extractor.extract(file_path, content)
        
        # 1. Add symbols as nodes
        for sym in symbols:
            self.graph_store.add_node(
                node_id=sym["id"],
                node_type=sym["type"],
                name=sym["name"],
                content=sym["content"],
                metadata=sym["metadata"]
            )
            
        # 2. Add structural relations
        for src, tgt, rel in relations:
            self.graph_store.add_edge(src, tgt, rel)
            
        return len(symbols)

    def extract_knowledge(self, chunk_text):
        """Extract entities and relations from a text chunk using the LLM."""
        prompt = f"""
Extract key entities and their relationships from the FOLLOWING TEXT CHUNK.
Return ONLY a valid JSON object with the keys 'entities' and 'relations'.

Entities: A list of objects with 'id' (snake_case), 'type' (e.g., person, tech, concept, file, function), and 'name' (display name).
Relations: A list of objects with 'source' (entity id), 'target' (entity id), and 'type' (e.g., uses, part_of, related_to, implements).

TEXT CHUNK:
{chunk_text}

JSON RESULT:
"""
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        try:
            # Note: We use _request_json directly to avoid QThread issues in the indexer
            resp = _request_json("/api/generate", payload, timeout=120)
            raw_response = resp.get("response", "{}")
            return json.loads(raw_response)
        except Exception as e:
            log.warning(f"Knowledge extraction failed: {e}")
            return {"entities": [], "relations": []}

    def index_chunk(self, chunk_text, metadata=None):
        """Add a chunk to the graph and link it to extracted entities."""
        # 1. Generate unique chunk ID
        path = metadata.get("path", "unknown") if metadata else "unknown"
        idx = metadata.get("index", 0) if metadata else 0
        chunk_id = hashlib.sha256(f"{path}_{idx}".encode()).hexdigest()[:16]

        # 2. Add chunk node
        self.graph_store.add_node(
            node_id=chunk_id,
            node_type="chunk",
            name=f"Chunk {chunk_id}",
            content=chunk_text,
            metadata=metadata
        )
        
        # 3. Extract knowledge
        knowledge = self.extract_knowledge(chunk_text)
        
        # 4. Store entities and link to chunk
        for ent in knowledge.get("entities", []):
            ent_id = ent.get("id", "").strip().lower()
            if not ent_id: continue
            
            # Add or update entity node
            self.graph_store.add_node(
                node_id=ent_id,
                node_type=ent.get("type", "entity"),
                name=ent.get("name", ent_id),
                metadata={"source_file": path}
            )
            
            # Link chunk to entity
            self.graph_store.add_edge(chunk_id, ent_id, "mentions")
            
        # 5. Store inter-entity relations
        for rel in knowledge.get("relations", []):
            src = rel.get("source", "").strip().lower()
            tgt = rel.get("target", "").strip().lower()
            rtype = rel.get("type", "related_to")
            if src and tgt:
                self.graph_store.add_edge(src, tgt, rtype)
                
        return chunk_id

    def extract_query_entities(self, query):
        """Extract primary entities from a search query using api/chat with safety."""
        prompt = f"Identify 1-3 primary entities (technologies, components, concepts) in this query. Return as a JSON list of strings only. Query: {query}"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json"
        }
        try:
            # Shorter timeout for user-facing search queries
            resp = _request_json("/api/chat", payload, timeout=15)
            message = resp.get("message", {})
            raw_response = message.get("content", "")
            if not raw_response.strip():
                return self._fallback_extract_entities(query)
            data = json.loads(raw_response)
            if isinstance(data, dict):
                # Handle {"entities": [...]} or {"result": [...]}
                for key in ["entities", "result", "items"]:
                    if key in data and isinstance(data[key], list):
                        return data[key]
                return self._fallback_extract_entities(query)
            return data if isinstance(data, list) else self._fallback_extract_entities(query)
        except Exception as e:
            log.debug(f"Query entity extraction failed or timed out: {e}")
            return self._fallback_extract_entities(query)

    def _fallback_extract_entities(self, query):
        """Simple heuristic extraction when LLM fails."""
        # Extract capitalized words as potential entities
        words = query.split()
        potential = [w.strip("?,.!") for w in words if w[0].isupper()]
        return potential[:3]

    def search(self, query, vector_results, depth=1):
        """Hybrid search combining vector results with graph traversal."""
        # 1. Extract query entities
        q_entities = self.extract_query_entities(query)
        
        related_data = []
        seen_nodes = set()
        
        # 2. Traversal from query entities
        for ent_name in q_entities:
            matches = self.graph_store.query_entities(ent_name, limit=3)
            
            # Fallback for multi-word entities
            if not matches and " " in ent_name:
                for word in ent_name.split():
                    if len(word) > 3:
                        matches.extend(self.graph_store.query_entities(word, limit=1))
            
            for node in matches:
                if node["id"] not in seen_nodes:
                    related_data.append(node)
                    seen_nodes.add(node["id"])
                    
                    # Traversal
                    neighbors = self.graph_store.get_neighbors(node["id"], max_depth=depth)
                    for neighbor in neighbors:
                        if neighbor["id"] not in seen_nodes:
                            related_data.append(neighbor)
                            seen_nodes.add(neighbor["id"])

        # 3. Format results as context string
        if not related_data:
            return ""
            
        context = "The following relationships were found in the knowledge graph:\n"
        for item in related_data:
            itype = item.get("type", "unknown")
            name = item.get("name", "unknown")
            content = item.get("content", "")
            
            if itype == "chunk":
                context += f"- [File Content Chunk]: {name}\n"
            else:
                context += f"- [{itype.capitalize()}]: {name}"
                if content: context += f" - {content}"
                
                # Show active relations
                neighbors = self.graph_store.get_neighbors(item["id"], max_depth=1)
                for n in neighbors:
                    context += f"\n  └─ {n.get('relation', 'connected to')} -> {n.get('name')}"
                context += "\n"
                
        return context
