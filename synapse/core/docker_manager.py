import logging
import subprocess
import json
import threading
from typing import List, Dict, Any, Optional
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

log = logging.getLogger(__name__)

class DockerManager(QObject):
    containers_updated = pyqtSignal(list)
    images_updated = pyqtSignal(list)
    volumes_updated = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    logs_received = pyqtSignal(str, str) # container_id, logs

    def __init__(self, workspace_root: str, parent=None):
        super().__init__(parent)
        self.workspace_root = workspace_root
        self.polling_timer = QTimer(self)
        self.polling_timer.timeout.connect(self.refresh_all)
        self.polling_timer.start(5000) # Poll every 5 seconds

    def _run_command(self, args: List[str]) -> Optional[str]:
        try:
            result = subprocess.run(
                ["docker"] + args,
                capture_output=True,
                text=True,
                check=True,
                cwd=self.workspace_root
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            error_msg = f"Docker command failed: {e.stderr}"
            log.error(error_msg)
            self.error_occurred.emit(error_msg)
            return None
        except FileNotFoundError:
            self.error_occurred.emit("Docker CLI not found. Please install Docker.")
            return None

    def refresh_all(self):
        threading.Thread(target=self._refresh_thread, daemon=True).start()

    def _refresh_thread(self):
        self._refresh_containers()
        self._refresh_images()
        self._refresh_volumes()

    def _refresh_containers(self):
        output = self._run_command(["ps", "-a", "--format", "{{json .}}"])
        if output:
            containers = []
            for line in output.strip().split('\n'):
                if line:
                    try:
                        containers.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            self.containers_updated.emit(containers)

    def _refresh_images(self):
        output = self._run_command(["images", "--format", "{{json .}}"])
        if output:
            images = []
            for line in output.strip().split('\n'):
                if line:
                    try:
                        images.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            self.images_updated.emit(images)

    def _refresh_volumes(self):
        output = self._run_command(["volume", "ls", "--format", "{{json .}}"])
        if output:
            volumes = []
            for line in output.strip().split('\n'):
                if line:
                    try:
                        volumes.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            self.volumes_updated.emit(volumes)

    def start_container(self, container_id: str):
        self._run_command(["start", container_id])
        self.refresh_all()

    def stop_container(self, container_id: str):
        self._run_command(["stop", container_id])
        self.refresh_all()

    def remove_container(self, container_id: str):
        self._run_command(["rm", "-f", container_id])
        self.refresh_all()

    def fetch_logs(self, container_id: str, tail: int = 100):
        output = self._run_command(["logs", "--tail", str(tail), container_id])
        if output:
            self.logs_received.emit(container_id, output)

    def get_devcontainer_config(self) -> Optional[Dict[str, Any]]:
        import os
        config_path = os.path.join(self.workspace_root, ".devcontainer", "devcontainer.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    # Basic JSON cleaning (removing comments if any, simple regex hack)
                    content = f.read()
                    import re
                    content = re.sub(r'//.*', '', content)
                    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
                    return json.loads(content)
            except Exception as e:
                log.error(f"Error reading devcontainer.json: {e}")
        return None
