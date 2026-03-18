import os
import logging
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from .lsp_client import LSPClient

log = logging.getLogger(__name__)

# Default language server configurations
DEFAULT_LSP_CONFIGS = {
    "python": {
        "command": "pyright-langserver",
        "args": ["--stdio"],
        "trigger_chars": ["."]
    },
    "rust": {
        "command": "rust-analyzer",
        "args": [],
        "trigger_chars": [".", ":"]
    },
    "javascript": {
        "command": "typescript-language-server",
        "args": ["--stdio"],
        "trigger_chars": ["."]
    }
}

class LSPManager(QObject):
    """
    High-level manager for multiple LSP clients.
    Handles document syncing and coordinates requests.
    """
    diagnostics_received = pyqtSignal(str, list) # file_uri, diagnostics

    def __init__(self, workspace_root=None):
        super().__init__()
        self.workspace_root = workspace_root
        self._clients = {} # lang -> LSPClient
        self._document_versions = {} # uri -> version_int

    def get_client(self, lang):
        """Returns or starts an LSP client for the given language."""
        if lang in self._clients:
            return self._clients[lang]

        if lang not in DEFAULT_LSP_CONFIGS:
            return None

        cfg = DEFAULT_LSP_CONFIGS[lang]
        client = LSPClient(cfg["command"], cfg["args"])
        client.notification_received.connect(self._handle_notification)
        
        if client.start():
            # Mandatory initialization
            root_uri = f"file://{os.path.abspath(self.workspace_root)}" if self.workspace_root else None
            client.send_request("initialize", {
                "processId": os.getpid(),
                "rootUri": root_uri,
                "capabilities": {
                    "textDocument": {
                        "publishDiagnostics": {"relatedInformation": True},
                        "completion": {"completionItem": {"snippetSupport": True}}
                    }
                }
            })
            client.send_notification("initialized", {})
            self._clients[lang] = client
            log.info(f"Initialized LSP for {lang}")
            return client
        
        return None

    def did_open(self, filepath, lang, text):
        """Notifies the LSP that a document has been opened."""
        client = self.get_client(lang)
        if not client: return

        uri = Path(filepath).as_uri()
        self._document_versions[uri] = 1
        client.send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": lang,
                "version": 1,
                "text": text
            }
        })

    def did_change(self, filepath, lang, text):
        """Notifies the LSP that a document has changed (full text sync for simplicity)."""
        client = self.get_client(lang)
        if not client: return

        uri = Path(filepath).as_uri()
        version = self._document_versions.get(uri, 0) + 1
        self._document_versions[uri] = version
        
        client.send_notification("textDocument/didChange", {
            "textDocument": {"uri": uri, "version": version},
            "contentChanges": [{"text": text}]
        })

    def request_hover(self, filepath, lang, line, column):
        """Requests hover information for a specific position."""
        client = self.get_client(lang)
        if not client: return None
        
        uri = Path(filepath).as_uri()
        return client.send_request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column}
        })

    def request_definition(self, filepath, lang, line, column):
        """Requests definition location for a specific position."""
        client = self.get_client(lang)
        if not client: return None
        
        uri = Path(filepath).as_uri()
        return client.send_request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": column}
        })

    def _handle_notification(self, method, params):
        """Handles notifications from LSP clients (e.g. diagnostics)."""
        if method == "textDocument/publishDiagnostics":
            uri = params.get("uri")
            diagnostics = params.get("diagnostics", [])
            self.diagnostics_received.emit(uri, diagnostics)

    def shutdown(self):
        """Shuts down all active LSP servers."""
        for client in self._clients.values():
            client.send_request("shutdown")
            client.send_notification("exit")
            client.stop()
        self._servers = {}
