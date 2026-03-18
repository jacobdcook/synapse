import json
import os
import subprocess
import threading
import queue
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, Union
from PyQt5.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

class LSPClient(QObject):
    """
    Low-level LSP client handling JSON-RPC over stdio.
    """
    notification_received = pyqtSignal(str, dict) # method, params
    error_occurred = pyqtSignal(str)

    def __init__(self, server_command, server_args=None, root_uri=None):
        super().__init__()
        self.server_command = server_command
        self.server_args = server_args or []
        self.root_uri = root_uri
        self._proc = None
        self._reader_thread = None
        self._pending = {} # id -> queue.Queue
        self._next_id = 1
        self._lock = threading.Lock()
        self.is_running = False

    def start(self):
        """Starts the language server process."""
        try:
            cmd = [self.server_command] + self.server_args
            log.info(f"Starting LSP server: {' '.join(cmd)}")
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False # Use bytes for Content-Length parsing
            )
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()
            self.is_running = True
            return True
        except Exception as e:
            log.error(f"Failed to start LSP server {self.server_command}: {e}")
            self.error_occurred.emit(str(e))
            return False

    def stop(self):
        """Stops the language server process."""
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
        self.is_running = False

    def send_request(self, method, params=None, timeout=10):
        """Sends a JSON-RPC request and waits for the response."""
        if not self.is_running:
            return None

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
            self._write_msg(msg)
            return q.get(timeout=timeout)
        except queue.Empty:
            log.warning(f"LSP request {method} (id={req_id}) timed out")
            return None
        finally:
            with self._lock:
                self._pending.pop(req_id, None)

    def send_notification(self, method, params=None):
        """Sends a JSON-RPC notification (no response expected)."""
        if not self.is_running:
            return
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        self._write_msg(msg)

    def _write_msg(self, msg):
        """Writes a message with Content-Length header to the server's stdin."""
        try:
            body = json.dumps(msg).encode("utf-8")
            header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            with self._lock:
                if self._proc and self._proc.stdin:
                    self._proc.stdin.write(header + body)
                    self._proc.stdin.flush()
        except Exception as e:
            log.error(f"LSP write error: {e}")
            self.is_running = False

    def _read_loop(self):
        """Reads responses and notifications from the server's stdout."""
        try:
            while self._proc and self._proc.stdout:
                # Read Headers
                line = self._proc.stdout.readline()
                if not line: break
                
                line = line.decode("ascii", errors="replace").strip()
                if not line.startswith("Content-Length:"): continue
                
                try:
                    content_length = int(line.split(":")[1].strip())
                except (IndexError, ValueError):
                    continue

                # Skip until \r\n\r\n (empty line)
                while True:
                    line = self._proc.stdout.readline().decode("ascii").strip()
                    if not line: break
                
                # Read Body
                body_bytes = self._proc.stdout.read(content_length)
                if len(body_bytes) < content_length:
                    log.warning("Short read from LSP server")
                    continue
                
                try:
                    msg = json.loads(body_bytes.decode("utf-8"))
                    self._handle_msg(msg)
                except json.JSONDecodeError as e:
                    log.error(f"Failed to parse LSP response: {e}")

        except Exception as e:
            if self.is_running:
                log.error(f"LSP reader loop error: {e}")
        finally:
            self.is_running = False

    def _handle_msg(self, msg):
        """Dispatches messages to pending requests or notification signals."""
        if "id" in msg:
            req_id = msg["id"]
            with self._lock:
                if req_id in self._pending:
                    self._pending[req_id].put(msg)
        elif "method" in msg:
            self.notification_received.emit(msg["method"], msg.get("params", {}))
