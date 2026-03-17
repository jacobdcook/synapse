import json
import os
import subprocess
import threading
import queue
import logging
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

log = logging.getLogger(__name__)


def _namespace(server_name, tool_name):
    """Convert server_name + tool_name to mcp__server__tool format."""
    safe_server = server_name.replace("-", "_").replace(" ", "_")
    return f"mcp__{safe_server}__{tool_name}"


def _denormalize(namespaced):
    """Extract server_name and tool_name from namespaced tool name."""
    parts = namespaced.split("__")
    if len(parts) == 3 and parts[0] == "mcp":
        return parts[1], parts[2]
    return None, None


def _mcp_tool_to_ollama(server_name, mcp_def):
    """Convert MCP tool definition to Ollama format."""
    return {
        "type": "function",
        "function": {
            "name": _namespace(server_name, mcp_def["name"]),
            "description": mcp_def.get("description", ""),
            "parameters": mcp_def.get("inputSchema", {"type": "object", "properties": {}})
        }
    }


class _StdioReaderThread(threading.Thread):
    """Reads JSON lines from subprocess stdout, dispatches to pending request queues."""

    def __init__(self, proc, on_line_callback, on_death_callback):
        super().__init__(daemon=True)
        self.proc = proc
        self.on_line_callback = on_line_callback
        self.on_death_callback = on_death_callback

    def run(self):
        """Read stdout lines and dispatch via callback."""
        try:
            while True:
                line = self.proc.stdout.readline()
                if not line:
                    break
                try:
                    self.on_line_callback(line)
                except Exception as e:
                    log.error(f"Error processing MCP line: {e}")
        except Exception as e:
            log.error(f"MCP reader thread error: {e}")
        finally:
            self.on_death_callback()


class MCPServerConnection(QObject):
    """Manages a single MCP server subprocess connection."""

    connected = pyqtSignal()
    disconnected = pyqtSignal(str)  # reason
    tools_ready = pyqtSignal(list)  # raw MCP tool definitions

    def __init__(self, config):
        super().__init__()
        self.name = config.get("name", "unknown")
        self.command = config.get("command", "")
        self.args = config.get("args", [])
        self.env = config.get("env", {})
        self.transport = config.get("transport", "stdio")
        self.enabled = config.get("enabled", True)

        self._proc = None
        self._reader_thread = None
        self._pending = {}  # request_id -> queue.Queue
        self._next_id = 1
        self._lock = threading.Lock()
        self.is_connected = False
        self._initialized = False
        self._tools_cache = []
        self._retry_count = 0
        self._max_retries = 3

    def connect(self):
        """Start the subprocess and initialize MCP handshake in a background thread."""
        if self.is_connected:
            return

        if not self.enabled:
            log.debug(f"MCP server {self.name} is disabled, skipping connect")
            return

        t = threading.Thread(target=self._connect_blocking, daemon=True)
        t.start()

    def _connect_blocking(self):
        """Blocking connect — runs in background thread so it won't freeze UI."""
        try:
            log.info(f"Connecting to MCP server: {self.name}")
            cmd = [self.command] + self.args
            proc_env = dict(os.environ)
            proc_env.update(self.env)
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=proc_env,
                text=False
            )

            self._reader_thread = _StdioReaderThread(
                self._proc,
                self._on_line,
                self._on_proc_death
            )
            self._reader_thread.start()

            import time
            time.sleep(1)

            try:
                result = self.send_request(
                    "initialize",
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "synapse",
                            "version": "3.0.0"
                        }
                    },
                    timeout=15
                )
                log.info(f"MCP server {self.name} initialized: {result.get('serverInfo', {})}")
                self._initialized = True
                self.is_connected = True
                self.connected.emit()

                tools_result = self.send_request("tools/list", {}, timeout=10)
                self._tools_cache = tools_result.get("tools", [])
                self.tools_ready.emit(self._tools_cache)
                self._retry_count = 0

            except Exception as e:
                log.error(f"MCP initialization failed for {self.name}: {e}")
                if self._proc:
                    try:
                        stderr_out = self._proc.stderr.read(2000) if self._proc.stderr else b""
                        if stderr_out:
                            log.error(f"MCP {self.name} stderr: {stderr_out.decode('utf-8', errors='replace')[:500]}")
                    except Exception as e:
                        log.debug(f"MCP {self.name} stderr read failed: {e}")
                    self._proc.terminate()
                    self._proc = None
                self._schedule_reconnect()

        except Exception as e:
            log.error(f"Failed to start MCP server {self.name}: {e}")
            self._schedule_reconnect()

    def disconnect(self):
        """Stop the subprocess."""
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
            self._proc = None

        self.is_connected = False
        self._initialized = False
        self._tools_cache = []
        self.disconnected.emit("disconnect called")

    def send_request(self, method, params=None, timeout=30):
        """Send a JSON-RPC request and block for response."""
        if not self._proc:
            raise RuntimeError(f"MCP server {self.name} is not connected")

        req_id = self._next_id
        with self._lock:
            self._next_id += 1

        q = queue.Queue()
        self._pending[req_id] = q

        try:
            msg = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params or {}
            }
            line = json.dumps(msg) + "\n"
            with self._lock:
                if not self._proc or not self._proc.stdin:
                    raise RuntimeError(f"MCP server not connected")
                self._proc.stdin.write(line.encode())
                self._proc.stdin.flush()

            result = q.get(timeout=timeout)

            if "error" in result:
                raise RuntimeError(f"MCP error: {result.get('error', {}).get('message', 'unknown')}")

            return result.get("result", {})

        except queue.Empty:
            raise RuntimeError(f"MCP request timeout for method {method}")
        finally:
            self._pending.pop(req_id, None)

    def _on_line(self, line_bytes):
        """Called by reader thread when a line is received."""
        try:
            line = line_bytes.decode('utf-8', errors='replace').strip()
            if not line:
                return

            msg = json.loads(line)
            req_id = msg.get("id")

            if req_id is not None and req_id in self._pending:
                self._pending[req_id].put(msg)
        except json.JSONDecodeError:
            log.warning(f"Failed to parse MCP response: {line_bytes}")
            for rid, q in list(self._pending.items()):
                q.put({"error": {"code": -32700, "message": "Parse error from server"}, "id": rid})

    def _on_proc_death(self):
        """Called by reader thread when process dies."""
        log.warning(f"MCP server {self.name} process died")
        self.is_connected = False
        self.disconnected.emit("process died")
        self._schedule_reconnect()

    def _schedule_reconnect(self):
        """Schedule a reconnect with exponential backoff."""
        if self._retry_count < self._max_retries:
            self._retry_count += 1
            delay = min(5000 * (2 ** (self._retry_count - 1)), 60000)
            log.info(f"Scheduling reconnect for {self.name} in {delay}ms (attempt {self._retry_count}/{self._max_retries})")
            QTimer.singleShot(delay, self.connect)
        else:
            log.error(f"Max reconnect attempts reached for {self.name}")


class MCPClientManager(QObject):
    """Manages all MCP server connections."""

    servers_changed = pyqtSignal()
    tool_list_updated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._servers = {}  # name -> MCPServerConnection
        self._tools_cache = {}  # namespaced_name -> {definition, server_name}

    def load_from_settings(self, settings):
        """Load MCP servers from settings and start/stop them accordingly."""
        new_configs = settings.get("mcp_servers", [])
        new_names = {cfg["name"] for cfg in new_configs}
        old_names = set(self._servers.keys())

        # Stop removed servers
        for name in old_names - new_names:
            self._servers[name].disconnect()
            del self._servers[name]
            log.info(f"Stopped MCP server: {name}")

        # Start new servers or update existing ones
        for cfg in new_configs:
            name = cfg["name"]
            if name not in self._servers:
                conn = MCPServerConnection(cfg)
                conn.tools_ready.connect(self._on_tools_ready)
                conn.connected.connect(self.servers_changed.emit)
                conn.disconnected.connect(self.servers_changed.emit)
                self._servers[name] = conn
                if cfg.get("enabled", True):
                    conn.connect()
            else:
                # Update existing server config if changed
                old = self._servers[name]
                if (old.command != cfg.get("command") or
                    old.args != cfg.get("args") or
                    old.enabled != cfg.get("enabled")):
                    old.disconnect()
                    old.command = cfg.get("command")
                    old.args = cfg.get("args")
                    old.enabled = cfg.get("enabled")
                    if cfg.get("enabled", True):
                        old.connect()

        self.servers_changed.emit()
        self._update_tools_cache()

    def shutdown_all(self):
        """Disconnect all servers (call on app close)."""
        for conn in self._servers.values():
            conn.disconnect()
        self._servers.clear()

    def get_tool_definitions(self):
        """Return Ollama-format tool definitions from all MCP servers."""
        return [t["definition"] for t in self._tools_cache.values()]

    def execute_tool(self, namespaced_name, args):
        """Execute a tool call and return the result string."""
        server_name, tool_name = _denormalize(namespaced_name)

        if server_name is None:
            return None  # Not an MCP tool

        if server_name not in self._servers:
            return f"MCP server '{server_name}' not found"

        conn = self._servers[server_name]
        if not conn.is_connected:
            return f"MCP server '{server_name}' is not connected"

        try:
            result = conn.send_request(
                "tools/call",
                {"name": tool_name, "arguments": args},
                timeout=30
            )

            # Extract text from content array
            parts = []
            for item in result.get("content", []):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))

            return "\n".join(parts) if parts else "(empty result)"

        except Exception as e:
            return f"MCP tool error: {e}"

    def get_server_statuses(self):
        """Return list of server status dicts for display."""
        return [
            {
                "name": conn.name,
                "connected": conn.is_connected,
                "enabled": conn.enabled,
                "tools_count": len(conn._tools_cache)
            }
            for conn in self._servers.values()
        ]

    def _on_tools_ready(self, mcp_defs):
        """Called when a server's tools list is fetched."""
        sender = self.sender()
        if isinstance(sender, MCPServerConnection):
            self._update_tools_cache()
            self.tool_list_updated.emit()

    def _update_tools_cache(self):
        """Rebuild the tools cache from all connected servers."""
        self._tools_cache.clear()
        for conn in self._servers.values():
            if conn.is_connected:
                for mcp_def in conn._tools_cache:
                    ollama_def = _mcp_tool_to_ollama(conn.name, mcp_def)
                    namespaced = ollama_def["function"]["name"]
                    self._tools_cache[namespaced] = {
                        "definition": ollama_def,
                        "server_name": conn.name
                    }
