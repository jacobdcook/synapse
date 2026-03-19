"""MCP health monitoring."""
import logging
import time
from PyQt5.QtCore import QObject, QTimer, pyqtSignal

log = logging.getLogger(__name__)


class MCPHealthMonitor(QObject):
    server_unhealthy = pyqtSignal(str, str)
    server_recovered = pyqtSignal(str)

    def __init__(self, ping_fn, interval_ms=300000):
        super().__init__()
        self.ping_fn = ping_fn
        self._servers = {}
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_all)
        self._timer.start(interval_ms)

    def register_server(self, name, config):
        self._servers[name] = {"config": config, "latency": None, "errors": 0, "healthy": True}

    def _check_all(self):
        for name, data in self._servers.items():
            start = time.time()
            try:
                self.ping_fn(name, data["config"])
                latency = (time.time() - start) * 1000
                data["latency"] = latency
                if data["errors"] > 0:
                    data["errors"] = 0
                    if not data["healthy"]:
                        data["healthy"] = True
                        self.server_recovered.emit(name)
                data["healthy"] = True
            except Exception as e:
                data["errors"] = data.get("errors", 0) + 1
                if data["healthy"]:
                    data["healthy"] = False
                    self.server_unhealthy.emit(name, str(e))

    def get_health_report(self):
        return {n: {"latency": d.get("latency"), "healthy": d.get("healthy", True), "errors": d.get("errors", 0)}
                for n, d in self._servers.items()}
