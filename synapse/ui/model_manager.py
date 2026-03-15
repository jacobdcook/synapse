import json
import subprocess
import urllib.request
import urllib.error
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QProgressBar, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from ..utils.constants import get_ollama_url, RECOMMENDED_MODELS

log = logging.getLogger(__name__)


class ModelPullWorker(QThread):
    progress = pyqtSignal(str, int)  # status, percent
    finished = pyqtSignal(bool, str)  # success, message

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            payload = json.dumps({"name": self.model_name, "stream": True}).encode()
            req = urllib.request.Request(
                f"{get_ollama_url()}/api/pull",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3600) as resp:
                for line in resp:
                    try:
                        chunk = json.loads(line.decode().strip())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    status = chunk.get("status", "")
                    total = chunk.get("total", 0)
                    completed = chunk.get("completed", 0)
                    pct = int(completed / total * 100) if total > 0 else 0
                    self.progress.emit(status, pct)
            self.finished.emit(True, f"Successfully pulled {self.model_name}")
        except Exception as e:
            self.finished.emit(False, str(e))


class ModelManagerPanel(QWidget):
    models_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pull_worker = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QLabel("Model Manager")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Installed models
        installed_group = QGroupBox("Installed Models")
        installed_layout = QVBoxLayout(installed_group)
        self.model_list = QListWidget()
        self.model_list.setContextMenuPolicy(Qt.CustomContextMenu)
        installed_layout.addWidget(self.model_list)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.refresh_btn)

        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self._delete_model)
        btn_row.addWidget(self.delete_btn)
        installed_layout.addLayout(btn_row)
        layout.addWidget(installed_group)

        # Pull model
        pull_group = QGroupBox("Pull Model")
        pull_layout = QVBoxLayout(pull_group)

        pull_row = QHBoxLayout()
        self.pull_input = QLineEdit()
        self.pull_input.setPlaceholderText("Model name (e.g. llama3.2:3b)")
        pull_row.addWidget(self.pull_input)
        self.pull_btn = QPushButton("Pull")
        self.pull_btn.clicked.connect(self._pull_model)
        pull_row.addWidget(self.pull_btn)
        pull_layout.addLayout(pull_row)

        self.pull_progress = QProgressBar()
        self.pull_progress.setVisible(False)
        pull_layout.addWidget(self.pull_progress)

        self.pull_status = QLabel("")
        self.pull_status.setStyleSheet("color: #8b949e; font-size: 11px;")
        pull_layout.addWidget(self.pull_status)
        layout.addWidget(pull_group)

        # Recommended
        rec_group = QGroupBox("Recommended Models")
        rec_layout = QVBoxLayout(rec_group)
        self.rec_list = QListWidget()
        for rm in RECOMMENDED_MODELS:
            item = QListWidgetItem(f"{rm['name']}  ({rm['size_gb']} GB) - {rm['desc']}")
            item.setData(Qt.UserRole, rm["name"])
            self.rec_list.addItem(item)
        self.rec_list.itemDoubleClicked.connect(self._pull_recommended)
        rec_layout.addWidget(self.rec_list)
        layout.addWidget(rec_group)

        layout.addStretch()

    def refresh(self):
        self.model_list.clear()
        try:
            req = urllib.request.Request(f"{get_ollama_url()}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                for m in data.get("models", []):
                    name = m["name"]
                    size_gb = m.get("size", 0) / (1024 ** 3)
                    item = QListWidgetItem(f"{name}  ({size_gb:.1f} GB)")
                    item.setData(Qt.UserRole, name)
                    self.model_list.addItem(item)
        except Exception as e:
            log.warning(f"Failed to load models: {e}")

    def _delete_model(self):
        item = self.model_list.currentItem()
        if not item:
            return
        name = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Delete Model", f"Delete {name}?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        try:
            payload = json.dumps({"name": name}).encode()
            req = urllib.request.Request(
                f"{get_ollama_url()}/api/delete",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="DELETE"
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
            self.refresh()
            self.models_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete: {e}")

    def _pull_model(self):
        name = self.pull_input.text().strip()
        if not name:
            return
        self._start_pull(name)

    def _pull_recommended(self, item):
        name = item.data(Qt.UserRole)
        if name:
            self._start_pull(name)

    def _start_pull(self, name):
        if self._pull_worker and self._pull_worker.isRunning():
            return
        self.pull_btn.setEnabled(False)
        self.pull_progress.setVisible(True)
        self.pull_progress.setValue(0)
        self.pull_status.setText(f"Pulling {name}...")

        self._pull_worker = ModelPullWorker(name)
        self._pull_worker.progress.connect(self._on_pull_progress)
        self._pull_worker.finished.connect(self._on_pull_finished)
        self._pull_worker.start()

    def _on_pull_progress(self, status, pct):
        self.pull_progress.setValue(pct)
        self.pull_status.setText(status)

    def _on_pull_finished(self, success, message):
        self.pull_btn.setEnabled(True)
        self.pull_progress.setVisible(False)
        self.pull_status.setText(message)
        if success:
            self.refresh()
            self.models_changed.emit()
