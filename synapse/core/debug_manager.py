import sys
import json
import queue
import logging
import subprocess
import time
import os
import socket
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Set
from PyQt5.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

class DAPClient(QObject):
    """
    Handles Debug Adapter Protocol (DAP) over TCP.
    """
    event_received = pyqtSignal(str, dict) # event, body
    stopped = pyqtSignal(dict) # reason, threadId, etc.
    output = pyqtSignal(str, str) # category, output
    
    def __init__(self):
        super().__init__()
        self.sock: Optional[socket.socket] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._pending = {} # id -> queue.Queue
        self._next_id = 1
        self._lock = threading.Lock()
        self.is_connected = False

    def connect(self, host="127.0.0.1", port=5678, timeout=10):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                self.sock = socket.create_connection((host, port), timeout=2)
                self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
                self._reader_thread.start()
                self.is_connected = True
                log.info(f"Connected to DAP server at {host}:{port}")
                return True
            except (ConnectionRefusedError, socket.timeout):
                time.sleep(0.5)
        return False

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None
        self.is_connected = False

    def send_request(self, command, arguments=None, timeout=5):
        if not self.is_connected: return None
        
        req_id = self._next_id
        with self._lock: self._next_id += 1
        
        q = queue.Queue()
        self._pending[req_id] = q
        
        msg = {
            "type": "request",
            "seq": req_id,
            "command": command,
            "arguments": arguments or {}
        }
        
        try:
            body = json.dumps(msg).encode("utf-8")
            header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            with self._lock:
                self.sock.sendall(header + body)
            return q.get(timeout=timeout)
        except Exception as e:
            log.error(f"DAP request error ({command}): {e}")
            return None
        finally:
            with self._lock: self._pending.pop(req_id, None)

    def _read_loop(self):
        buffer = b""
        try:
            while self.sock:
                chunk = self.sock.recv(4096)
                if not chunk: break
                buffer += chunk
                
                while b"Content-Length:" in buffer and b"\r\n\r\n" in buffer:
                    try:
                        header_end = buffer.find(b"\r\n\r\n")
                        header = buffer[:header_end].decode("ascii")
                        content_length = int(header.split("Content-Length:")[1].split("\r\n")[0].strip())
                        
                        total_needed = header_end + 4 + content_length
                        if len(buffer) < total_needed: break
                        
                        body = buffer[header_end+4:total_needed]
                        buffer = buffer[total_needed:]
                        
                        msg = json.loads(body.decode("utf-8"))
                        self._handle_msg(msg)
                    except Exception as e:
                        log.error(f"DAP parse error: {e}")
                        break
        except Exception as e:
            log.debug(f"DAP reader loop stopped: {e}")
        finally:
            self.is_connected = False

    def _handle_msg(self, msg):
        msg_type = msg.get("type")
        if msg_type == "response":
            req_id = msg.get("request_seq")
            with self._lock:
                if req_id in self._pending:
                    self._pending[req_id].put(msg)
        elif msg_type == "event":
            event = msg.get("event")
            body = msg.get("body", {})
            if event == "stopped":
                self.stopped.emit(body)
            elif event == "output":
                self.output.emit(body.get("category", "console"), body.get("output", ""))
            self.event_received.emit(event, body)

class DebugManager(QObject):
    """
    High-level manager for debug sessions.
    """
    session_started = pyqtSignal()
    session_stopped = pyqtSignal()
    paused = pyqtSignal(str, int, list) # file, line, variables
    continued = pyqtSignal()
    variables_updated = pyqtSignal(list)
    stack_updated = pyqtSignal(list)
    breakpoints_updated = pyqtSignal(dict)  # file -> set of lines
    output_received = pyqtSignal(str, str)
    
    def __init__(self, workspace_dir=None):
        super().__init__()
        self.workspace_dir = workspace_dir
        self.client = DAPClient()
        self.client.stopped.connect(self._on_stopped)
        self.client.output.connect(self.output_received.emit)
        self.current_process: Optional[subprocess.Popen] = None
        self.breakpoints: Dict[str, Set[int]] = {} # file -> set of lines

    def start_debug(self, file_path, args=None):
        import debugpy
        port = 5678
        
        # Launch the script with debugpy
        cmd = [
            sys.executable,
            "-m", "debugpy",
            "--listen", f"127.0.0.1:{port}",
            "--wait-for-client",
            file_path
        ] + (args or [])
        
        try:
            self.current_process = subprocess.Popen(
                cmd,
                cwd=self.workspace_dir,
                env={**os.environ, "PYTHONPATH": self.workspace_dir or "."}
            )
            
            if self.client.connect(port=port):
                # Initialize DAP session
                self.client.send_request("initialize", {
                    "adapterID": "synapse-debug",
                    "linesStartAt1": True,
                    "columnsStartAt1": True,
                    "pathFormat": "path"
                })
                
                # Set existing breakpoints
                self._sync_breakpoints()
                
                # Configuration done
                self.client.send_request("configurationDone")
                
                # Launch/Attach (already launched, so just attach)
                self.client.send_request("attach", {
                    "name": "Synapse Attach",
                    "type": "python",
                    "request": "attach",
                    "connect": {"host": "127.0.0.1", "port": port}
                })
                
                self.session_started.emit()
                return True
        except Exception as e:
            log.error(f"Failed to start debug session: {e}")
        return False

    def stop_debug(self):
        if self.client.is_connected:
            self.client.send_request("disconnect", {"restart": False, "terminateDebuggee": True})
            self.client.disconnect()
        if self.current_process:
            self.current_process.terminate()
            self.current_process = None
        self.session_stopped.emit()

    def add_breakpoint(self, file_path, line):
        abs_path = os.path.abspath(file_path)
        if abs_path not in self.breakpoints:
            self.breakpoints[abs_path] = set()
        self.breakpoints[abs_path].add(line)
        if self.client.is_connected:
            self._set_breakpoints_for_file(abs_path)
        self.breakpoints_updated.emit(dict(self.breakpoints))

    def remove_breakpoint(self, file_path, line):
        abs_path = os.path.abspath(file_path)
        if abs_path in self.breakpoints:
            self.breakpoints[abs_path].discard(line)
            if not self.breakpoints[abs_path]:
                del self.breakpoints[abs_path]
        if self.client.is_connected:
            self._set_breakpoints_for_file(abs_path)
        self.breakpoints_updated.emit(dict(self.breakpoints))

    def clear_breakpoints(self):
        self.breakpoints.clear()
        self.breakpoints_updated.emit(dict(self.breakpoints))

    def toggle_breakpoint(self, file_path, line):
        abs_path = os.path.abspath(file_path)
        if abs_path not in self.breakpoints:
            self.breakpoints[abs_path] = set()
        
        lines = self.breakpoints[abs_path]
        if line in lines:
            lines.remove(line)
        else:
            lines.add(line)
            
        if self.client.is_connected:
            self._set_breakpoints_for_file(abs_path)
        return line in lines

    def step_over(self):
        self.client.send_request("next", {"threadId": 1})

    def step_into(self):
        self.client.send_request("stepIn", {"threadId": 1})

    def step_out(self):
        self.client.send_request("stepOut", {"threadId": 1})

    def continue_exec(self):
        self.client.send_request("continue", {"threadId": 1})
        self.continued.emit()

    def _sync_breakpoints(self):
        for file_path in self.breakpoints:
            self._set_breakpoints_for_file(file_path)

    def _set_breakpoints_for_file(self, file_path):
        lines = list(self.breakpoints.get(file_path, []))
        dap_breakpoints = [{"line": l} for l in lines]
        self.client.send_request("setBreakpoints", {
            "source": {"path": file_path},
            "breakpoints": dap_breakpoints
        })

    def _on_stopped(self, body):
        thread_id = body.get("threadId", 1)
        # Get stack trace to find current file/line
        stack = self.client.send_request("stackTrace", {"threadId": thread_id})
        if stack and stack.get("success"):
            frames = stack["body"].get("stackFrames", [])
            if frames:
                frame = frames[0]
                file_path = frame.get("source", {}).get("path")
                line = frame.get("line")
                
                # Get variables for this frame
                variables = self._get_variables(frame.get("id"))
                self.paused.emit(file_path, line, variables)
                self.variables_updated.emit(variables)
                self.stack_updated.emit(frames)

    def _get_variables(self, frame_id):
        scopes = self.client.send_request("scopes", {"frameId": frame_id})
        all_vars = []
        if scopes and scopes.get("success"):
            for scope in scopes["body"].get("scopes", []):
                vars_res = self.client.send_request("variables", {"variablesReference": scope.get("variablesReference")})
                if vars_res and vars_res.get("success"):
                    all_vars.extend(vars_res["body"].get("variables", []))
        return all_vars
