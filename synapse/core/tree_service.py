import logging

log = logging.getLogger(__name__)

class TreeExportService:
    """Converts a flat conversation history into a hierarchy for D3.js."""
    
    @staticmethod
    def get_tree_data(conversation):
        """
        Transforms conversation history into a nested dict:
        {
          "id": "...",
          "name": "...",
          "role": "...",
          "children": [...]
        }
        """
        history = conversation.get("history", [])
        if not history:
            return {}

        # Map by ID for quick lookup
        nodes = {}
        for msg in history:
            # Create node with essential display data
            content = msg.get("content", "")
            # Truncate content for label
            label = content[:40] + "..." if len(content) > 40 else content
            if not label.strip():
                label = f"[{msg.get('role', 'unknown')}]"
                
            nodes[msg["id"]] = {
                "id": msg["id"],
                "name": label,
                "role": msg.get("role", "user"),
                "children": []
            }

        root = None
        for msg in history:
            node = nodes[msg["id"]]
            parent_id = msg.get("parent_id")
            
            if parent_id and parent_id in nodes:
                nodes[parent_id]["children"].append(node)
            else:
                # If no parent, it's a root (usually the first message)
                # In case of multiple roots, we'll return the first one found
                if not root:
                    root = node
                else:
                    # In some cases we might have multiple roots if history is complex
                    # but usually it's a single start. For safety, we'll keep the first.
                    pass
        
        return root or {}
