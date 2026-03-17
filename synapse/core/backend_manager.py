import os
import subprocess
import threading
import time
import logging
import shutil
import platform
import socket
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from ..utils.constants import CONFIG_DIR, DEFAULT_SD_URL, DEFAULT_COMFYUI_URL

log = logging.getLogger(__name__)

BACKENDS_DIR = CONFIG_DIR / "backends"
BACKENDS_DIR.mkdir(parents=True, exist_ok=True)

class BackendManager(QObject):
    status_changed = pyqtSignal(str, str)  # backend_id, status
    install_progress = pyqtSignal(str, float, str)  # backend_id, progress (0-100), message
    log_received = pyqtSignal(str, str)  # backend_id, log_line

    def __init__(self):
        super().__init__()
        self.processes = {}  # backend_id -> subprocess.Popen
        self.statuses = {
            "sd": "stopped",
            "comfy": "stopped"
        }
        self.installing = set()
        self.logs = {
            "sd": [],
            "comfy": []
        }
        
        # Check if backends are already installed
        self._check_installed()

    def _check_installed(self):
        if (BACKENDS_DIR / "stable-diffusion-webui-forge").exists():
            self.statuses["sd"] = "stopped"
        else:
            self.statuses["sd"] = "not_installed"
            
        if (BACKENDS_DIR / "ComfyUI").exists():
            self.statuses["comfy"] = "stopped"
        else:
            self.statuses["comfy"] = "not_installed"

    def get_status(self, backend_id):
        return self.statuses.get(backend_id, "unknown")

    def get_logs(self, backend_id):
        return "\n".join(self.logs.get(backend_id, []))

    def install(self, backend_id):
        if backend_id in self.installing:
            return
        
        self.installing.add(backend_id)
        self.status_changed.emit(backend_id, "installing")
        
        thread = threading.Thread(target=self._run_install, args=(backend_id,), daemon=True)
        thread.start()

    def _run_install(self, backend_id):
        try:
            if backend_id == "sd":
                self._install_sd()
            elif backend_id == "comfy":
                self._install_comfy()
            
            self.statuses[backend_id] = "stopped"
            self.install_progress.emit(backend_id, 100, "Installation complete")
            self.status_changed.emit(backend_id, "stopped")
        except Exception as e:
            log.error(f"Installation failed for {backend_id}: {e}")
            self.statuses[backend_id] = "not_installed"
            self.install_progress.emit(backend_id, 0, f"Error: {str(e)}")
            self.status_changed.emit(backend_id, "not_installed")
        finally:
            if backend_id in self.installing:
                self.installing.remove(backend_id)

    def _install_sd(self):
        repo_url = "https://github.com/lllyasviel/stable-diffusion-webui-forge.git"
        target_dir = BACKENDS_DIR / "stable-diffusion-webui-forge"
        
        self.install_progress.emit("sd", 10, "Cloning Stable Diffusion Forge...")
        subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True)
        
        self.install_progress.emit("sd", 40, "Creating virtual environment...")
        venv_dir = target_dir / "venv"
        subprocess.run(["python3", "-m", "venv", str(venv_dir)], check=True)
        
        self.install_progress.emit("sd", 60, "Installing dependencies (this may take several minutes)...")
        # In SD Forge, usually running webui.sh handles the rest, but we might want to pre-install some bits
        # or just let the first run handle it. For now, let's mark it as done after cloning.
        # Actually, let's try to install base requirements.
        pip_path = venv_dir / "bin" / "pip"
        subprocess.run([str(pip_path), "install", "--upgrade", "pip"], check=True)
        
    def _install_comfy(self):
        repo_url = "https://github.com/comfyanonymous/ComfyUI.git"
        target_dir = BACKENDS_DIR / "ComfyUI"
        
        self.install_progress.emit("comfy", 10, "Cloning ComfyUI...")
        subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True)
        
        self.install_progress.emit("comfy", 40, "Creating virtual environment...")
        venv_dir = target_dir / "venv"
        subprocess.run(["python3", "-m", "venv", str(venv_dir)], check=True)
        
        self.install_progress.emit("comfy", 60, "Installing dependencies...")
        pip_path = venv_dir / "bin" / "pip"
        requirements = target_dir / "requirements.txt"
        subprocess.run([str(pip_path), "install", "-r", str(requirements)], check=True)

    def start(self, backend_id):
        if self.get_status(backend_id) == "running":
            return
            
        try:
            if backend_id == "sd":
                self._kill_on_port(7860)
                self._start_sd()
            elif backend_id == "comfy":
                self._kill_on_port(8188)
                self._start_comfy()
            
            self.statuses[backend_id] = "starting"
            self.status_changed.emit(backend_id, "starting")
            
            # Start a monitoring thread
            threading.Thread(target=self._monitor_process, args=(backend_id,), daemon=True).start()
            
        except Exception as e:
            log.error(f"Failed to start {backend_id}: {e}")
            self.status_changed.emit(backend_id, "error")

    def _start_sd(self):
        target_dir = BACKENDS_DIR / "stable-diffusion-webui-forge"
        python_exe = target_dir / "venv" / "bin" / "python3"
        launch_py = target_dir / "launch.py"
        
        # Add --api and --listen to ensure it works with Synapse
        # We also need --skip-python-version-check because Ubuntu 24.04 uses Python 3.12
        args = [str(python_exe), str(launch_py), "--api", "--listen", "--port", "7860", "--skip-python-version-check"]
        
        env = os.environ.copy()
        # Set some common env vars for SD
        env["PYTHONPATH"] = str(target_dir)
        
        self.processes["sd"] = subprocess.Popen(
            args, cwd=str(target_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
            text=True, env=env, bufsize=1
        )

    def _start_comfy(self):
        target_dir = BACKENDS_DIR / "ComfyUI"
        python_exe = target_dir / "venv" / "bin" / "python3"
        script = target_dir / "main.py"
        
        args = [str(python_exe), str(script), "--listen", "127.0.0.1", "--port", "8188"]
        
        self.processes["comfy"] = subprocess.Popen(
            args, cwd=str(target_dir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
            text=True, bufsize=1
        )

    def _kill_on_port(self, port):
        """Kills any process listening on the given port (cross-platform)."""
        system = platform.system()
        try:
            if system == "Windows":
                out = subprocess.check_output(
                    ["netstat", "-ano", "-p", "TCP"], text=True, timeout=5
                )
                for line in out.splitlines():
                    if f":{port}" in line and "LISTENING" in line:
                        pid = line.strip().split()[-1]
                        try:
                            subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, timeout=5)
                        except Exception:
                            pass
            else:
                out = subprocess.check_output(["lsof", "-t", f"-i:{port}"], text=True, timeout=5).strip()
                if out:
                    for pid in out.split():
                        os.kill(int(pid), 9)
            time.sleep(1)
        except Exception:
            try:
                if system != "Windows":
                    subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True, timeout=5)
                    time.sleep(1)
            except Exception:
                log.warning(f"Could not kill process on port {port}")

    def stop(self, backend_id):
        proc = self.processes.get(backend_id)
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            
            if backend_id in self.processes:
                del self.processes[backend_id]
            self.statuses[backend_id] = "stopped"
            self.status_changed.emit(backend_id, "stopped")

    def _monitor_process(self, backend_id):
        proc = self.processes.get(backend_id)
        if not proc:
            return

        for line in proc.stdout:
            decoded_line = line.strip()
            self.log_received.emit(backend_id, decoded_line)
            
            # Store in buffer
            if backend_id in self.logs:
                self.logs[backend_id].append(decoded_line)
                if len(self.logs[backend_id]) > 500: # Increase for better debugging
                    self.logs[backend_id].pop(0)

            # Simple check for ready state
            if backend_id == "sd" and "Model loaded in" in decoded_line:
                self.statuses[backend_id] = "running"
                self.status_changed.emit(backend_id, "running")
            elif backend_id == "comfy" and "To see the GUI go to" in decoded_line:
                self.statuses[backend_id] = "running"
                self.status_changed.emit(backend_id, "running")

        retcode = proc.wait()
        log.info(f"Backend {backend_id} exited with code {retcode}")
        if backend_id in self.processes:
            del self.processes[backend_id]
        
        self.statuses[backend_id] = "stopped"
        self.status_changed.emit(backend_id, "stopped")

    def __del__(self):
        for bid in list(self.processes.keys()):
            self.stop(bid)
