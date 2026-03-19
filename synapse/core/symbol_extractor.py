import ast
import logging
from pathlib import Path

log = logging.getLogger(__name__)

class PythonSymbolExtractor:
    """Statically analyzes Python code to extract structural symbols and relationships."""
    
    def __init__(self):
        self.symbols = []
        self.relations = []
        self.current_file = ""

    def extract(self, file_path, content):
        """
        Parses Python content and returns a tuple of (symbols, relations).
        Symbols are dicts compatible with GraphStore.add_node.
        Relations are tuples (source, target, relation_type).
        """
        self.symbols = []
        self.relations = []
        self.current_file = str(file_path)
        
        try:
            tree = ast.parse(content)
            # Use module level as parent for top-level definitions
            file_node_id = f"file:{self.current_file}"
            self._visit_nodes(tree, file_node_id)
        except SyntaxError:
            # Common for non-Python files or Python 2 code if running in Python 3
            log.debug(f"Syntax error while parsing {file_path}")
        except Exception as e:
            log.error(f"Unexpected error extracting symbols from {file_path}: {e}")
            
        return self.symbols, self.relations

    def _visit_nodes(self, node, parent_id):
        """Recursive visitor that tracks scope/parentage."""
        
        if isinstance(node, ast.Module):
            for item in node.body:
                self._visit_nodes(item, parent_id)
                
        elif isinstance(node, ast.ClassDef):
            class_id = f"class:{self.current_file}:{node.name}"
            doc = ast.get_docstring(node) or ""
            
            self.symbols.append({
                "id": class_id,
                "type": "class",
                "name": node.name,
                "content": doc,
                "metadata": {
                    "file": self.current_file,
                    "lineno": node.lineno,
                    "bases": [self._get_source_segment(b) for b in node.bases]
                }
            })
            self.relations.append((parent_id, class_id, "defines"))
            
            # Recurse into class body to find methods
            for item in node.body:
                self._visit_nodes(item, class_id)
                
        elif isinstance(node, ast.FunctionDef):
            func_type = "method" if parent_id.startswith("class:") else "function"
            func_id = f"{func_type}:{self.current_file}:{node.name}"
            doc = ast.get_docstring(node) or ""
            
            self.symbols.append({
                "id": func_id,
                "type": func_type,
                "name": node.name,
                "content": doc,
                "metadata": {
                    "file": self.current_file,
                    "lineno": node.lineno,
                    "args": [arg.arg for arg in node.args.args]
                }
            })
            rel_type = "defines" if func_type == "method" else "contains"
            self.relations.append((parent_id, func_id, rel_type))
            
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imp_id = f"import:{self.current_file}:{alias.name}"
                self.symbols.append({
                    "id": imp_id,
                    "type": "import",
                    "name": alias.name,
                    "content": f"import {alias.name}",
                    "metadata": {"file": self.current_file, "lineno": node.lineno}
                })
                self.relations.append((parent_id, imp_id, "imports"))
                
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                full_name = f"{module}.{alias.name}"
                imp_id = f"import:{self.current_file}:{full_name}"
                self.symbols.append({
                    "id": imp_id,
                    "type": "import",
                    "name": full_name,
                    "content": f"from {module} import {alias.name}",
                    "metadata": {"file": self.current_file, "lineno": node.lineno}
                })
                self.relations.append((parent_id, imp_id, "imports"))

        # For structural blocks like If/Try, we don't index them as symbols, 
        # but we search within them for nested classes/functions.
        elif hasattr(node, "body") and isinstance(node.body, list):
            for item in node.body:
                self._visit_nodes(item, parent_id)

    def _get_source_segment(self, node):
        """Fallback for ast.unparse if not available."""
        try:
            return ast.unparse(node)
        except Exception as e:
            log.warning(f"ast.unparse failed: {e}")
            return "unknown"
