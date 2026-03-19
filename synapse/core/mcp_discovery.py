"""MCP package discovery and server verification."""
import logging
import subprocess
import time

log = logging.getLogger(__name__)


def scan_system():
    found = []
    for cmd in ["npx", "uvx", "pip"]:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
            found.append(cmd)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return found


def verify_server(cmd, args, timeout=10):
    try:
        proc = subprocess.Popen(
            [cmd] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        time.sleep(2)
        proc.terminate()
        proc.wait(timeout=5)
        return True
    except Exception as e:
        log.warning(f"Server verify failed: {e}")
        return False


def auto_configure(candidates):
    configured = []
    for c in candidates:
        if c.get("cmd") and verify_server(c["cmd"], c.get("args", [])):
            configured.append(c)
    return configured
