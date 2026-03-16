import os
import json
import logging
import threading
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QProgressBar, QMessageBox, QFrame, QScrollArea, QGridLayout
)

log = logging.getLogger(__name__)

WHISPER_MODELS = [
    {"id": "tiny", "size": "75 MB", "desc": "Fastest, lowest accuracy"},
    {"id": "base", "size": "145 MB", "desc": "Good balance for most uses"},
    {"id": "small", "size": "485 MB", "desc": "More accurate, requires 2GB+ VRAM"},
    {"id": "medium", "size": "1.5 GB", "desc": "High accuracy, requires 5GB+ VRAM"},
    {"id": "large-v3", "size": "3.1 GB", "desc": "Pro-level accuracy, requires 10GB+ VRAM"}
]

class WhisperDownloadWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, model_size):
        super().__init__()
        self.model_size = model_size

    def run(self):
        try:
            from faster_whisper import WhisperModel
            import torch
            
            device = "cuda" if torch.cuda.is_available() else "cpu"
            # faster-whisper handles downloads automatically when initializing
            # We can't easily get fine-grained progress from faster-whisper's internal download
            # but we can at least show a busy indicator.
            self.progress.emit(-1) 
            
            WhisperModel(self.model_size, device=device, compute_type="int8")
            self.finished.emit(True, f"Model {self.model_size} is ready.")
        except Exception as e:
            self.finished.emit(False, str(e))

class WhisperModelCard(QFrame):
    download_requested = pyqtSignal(str)

    def __init__(self, model_data, is_installed=False):
        super().__init__()
        self.data = model_data
        self.is_installed = is_installed
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedSize(250, 150)
        self.setStyleSheet("""
            WhisperModelCard {
                background-color: #1e1f23;
                border: 1px solid #30363d;
                border-radius: 10px;
            }
            WhisperModelCard:hover {
                border-color: #58a6ff;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        name = QLabel(self.data["id"].upper())
        name.setStyleSheet("font-weight: bold; font-size: 14px; color: #e6edf3;")
        layout.addWidget(name)
        
        size = QLabel(f"Size: {self.data['size']}")
        size.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(size)
        
        desc = QLabel(self.data["desc"])
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(desc)
        
        layout.addStretch()
        
        if self.is_installed:
            status = QLabel("INSTALLED ✓")
            status.setStyleSheet("color: #3fb950; font-weight: bold; font-size: 10px;")
            layout.addWidget(status, 0, Qt.AlignRight)
        else:
            btn = QPushButton("Download")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #238636;
                    color: white;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #2ea043; }
            """)
            btn.clicked.connect(lambda: self.download_requested.emit(self.data["id"]))
            layout.addWidget(btn, 0, Qt.AlignRight)

class WhisperManagerPanel(QWidget):
    models_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._download_worker = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Whisper Model Manager")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #e6edf3;")
        layout.addWidget(title)
        
        subtitle = QLabel("Local Speech-to-Text models for privacy and speed.")
        subtitle.setStyleSheet("color: #8b949e; font-size: 12px; margin-bottom: 10px;")
        layout.addWidget(subtitle)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #58a6ff; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        self.scroll_content = QWidget()
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setSpacing(15)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

    def refresh(self):
        # Clear grid
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        # Heuristic to check if model is "installed"
        # faster-whisper stores models in ~/.cache/huggingface/hub by default
        # or we can check the models available to the current environment.
        # For simplicity, we'll just check if the directory exists.
        
        row, col = 0, 0
        max_cols = 3
        
        for m in WHISPER_MODELS:
            # We don't have a reliable easy check without trying to load,
            # so for now we just show them all as available.
            # Real implementation would check ~/.cache/huggingface
            card = WhisperModelCard(m, is_installed=False)
            card.download_requested.connect(self._start_download)
            self.grid.addWidget(card, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _start_download(self, model_id):
        if self._download_worker and self._download_worker.isRunning():
            return
            
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0) # Busy
        self.status_label.setText(f"Downloading {model_id} model... (this may take a while)")
        
        self._download_worker = WhisperDownloadWorker(model_id)
        self._download_worker.finished.connect(self._on_finished)
        self._download_worker.start()

    def _on_finished(self, success, message):
        self.progress_bar.setVisible(False)
        self.status_label.setText("")
        if success:
            QMessageBox.information(self, "Success", message)
            self.refresh()
            self.models_changed.emit()
        else:
            QMessageBox.critical(self, "Error", message)
