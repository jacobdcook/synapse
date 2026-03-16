import os
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QScrollArea, QFrame, QGridLayout, QSpinBox,
    QDoubleSpinBox, QComboBox, QFileDialog, QDialog, QTextEdit
)

class LogViewerDialog(QDialog):
    def __init__(self, backend_id, logs, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Logs: {backend_id.upper()}")
        self.resize(800, 600)
        self.setStyleSheet("background: #0d1117; color: #e6edf3;")
        
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(logs)
        self.text_edit.setStyleSheet("font-family: monospace; font-size: 12px; background: #161b22; border: 1px solid #30363d;")
        layout.addWidget(self.text_edit)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("background: #21262d; border: 1px solid #30363d; padding: 5px;")
        layout.addWidget(close_btn)

class ImageGenSidebar(QWidget):
    generation_requested = pyqtSignal(str, dict) # provider, params
    image_selected = pyqtSignal(str) # filepath

    def __init__(self, backend_manager=None, parent=None):
        super().__init__(parent)
        self.backend_manager = backend_manager
        self._setup_ui()
        self.history = []
        
        if self.backend_manager:
            self.backend_manager.status_changed.connect(self._update_status)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Title
        title = QLabel("Image Generation")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e6edf3;")
        layout.addWidget(title)

        # Settings Group
        settings_frame = QFrame()
        settings_frame.setStyleSheet("background: #1e1f23; border-radius: 8px; border: 1px solid #30363d;")
        settings_layout = QVBoxLayout(settings_frame)
        
        # Provider
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("Backend:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["Stable Diffusion", "ComfyUI", "OpenAI DALL-E 3", "Hugging Face"])
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)
        settings_layout.addLayout(provider_layout)

        # Status Label and Quick Controls
        status_row = QHBoxLayout()
        self.status_label = QLabel("Backend Status: Unknown")
        self.status_label.setStyleSheet("font-size: 11px; color: #8b949e;")
        status_row.addWidget(self.status_label)
        
        self.quick_start_btn = QPushButton("Start")
        self.quick_start_btn.setFixedWidth(60)
        self.quick_start_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                font-size: 10px;
                padding: 2px 5px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #2ea043; }
        """)
        self.quick_start_btn.clicked.connect(self._on_quick_start_clicked)
        self.quick_start_btn.hide()
        status_row.addWidget(self.quick_start_btn)

        self.view_logs_btn = QPushButton("Show Logs")
        self.view_logs_btn.setFixedWidth(80)
        self.view_logs_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #c9d1d9;
                font-size: 10px;
                padding: 2px 5px;
                border-radius: 4px;
                border: 1px solid #30363d;
            }
            QPushButton:hover { background-color: #30363d; }
        """)
        self.view_logs_btn.clicked.connect(self._on_view_logs_clicked)
        self.view_logs_btn.hide()
        status_row.addWidget(self.view_logs_btn)
        
        settings_layout.addLayout(status_row)

        # Prompt
        settings_layout.addWidget(QLabel("Prompt:"))
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Describe the image...")
        self.prompt_input.setStyleSheet("background: #0d1117; border: 1px solid #30363d; padding: 5px;")
        settings_layout.addWidget(self.prompt_input)

        # Negative Prompt
        settings_layout.addWidget(QLabel("Negative Prompt:"))
        self.neg_prompt_input = QLineEdit()
        self.neg_prompt_input.setPlaceholderText("Things to avoid...")
        self.neg_prompt_input.setStyleSheet("background: #0d1117; border: 1px solid #30363d; padding: 5px;")
        settings_layout.addWidget(self.neg_prompt_input)

        # Simple Params
        params_grid = QGridLayout()
        
        params_grid.addWidget(QLabel("Steps:"), 0, 0)
        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(1, 150)
        self.steps_spin.setValue(20)
        params_grid.addWidget(self.steps_spin, 0, 1)

        params_grid.addWidget(QLabel("CFG:"), 1, 0)
        self.cfg_spin = QDoubleSpinBox()
        self.cfg_spin.setRange(1.0, 30.0)
        self.cfg_spin.setValue(7.0)
        params_grid.addWidget(self.cfg_spin, 1, 1)

        settings_layout.addLayout(params_grid)

        self.gen_btn = QPushButton("Generate Image")
        self.gen_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2ea043; }
        """)
        self.gen_btn.clicked.connect(self._on_gen_clicked)
        settings_layout.addWidget(self.gen_btn)

        layout.addWidget(settings_frame)

        # Gallery
        layout.addWidget(QLabel("Recent Results:"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        
        self.gallery_widget = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_widget)
        self.gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_layout.setSpacing(5)
        self.gallery_layout.setAlignment(Qt.AlignTop)

        self.scroll.setWidget(self.gallery_widget)
        layout.addWidget(self.scroll, 1)

        self._update_status()

    def _on_view_logs_clicked(self):
        if not self.backend_manager:
            return
            
        provider = self.provider_combo.currentText()
        backend_id = None
        if provider == "Stable Diffusion": backend_id = "sd"
        elif provider == "ComfyUI": backend_id = "comfy"
        
        if not backend_id:
            return
            
        logs = self.backend_manager.get_logs(backend_id)
        if not logs:
            logs = "No logs recorded yet for this session."
            
        dialog = LogViewerDialog(backend_id, logs, self)
        dialog.exec_()

    def _on_provider_changed(self):
        self._update_status()

    def _update_status(self, bid=None, status=None):
        provider = self.provider_combo.currentText()
        backend_id = None
        if provider == "Stable Diffusion": backend_id = "sd"
        elif provider == "ComfyUI": backend_id = "comfy"
        
        if not backend_id:
            self.status_label.setText("Cloud Backend (Online)")
            self.status_label.setStyleSheet("font-size: 11px; color: #7ee787;")
            return

        if self.backend_manager:
            status = self.backend_manager.get_status(backend_id)
            status_text = {
                "not_installed": "Not Installed",
                "installing": "Installing...",
                "stopped": "Stopped",
                "starting": "Starting...",
                "running": "Online",
                "error": "Error"
            }.get(status, status.title())
            
            self.status_label.setText(f"Local Backend: {status_text}")
            
            colors = {
                "running": "#7ee787",
                "error": "#f85149",
                "starting": "#e3b341",
                "installing": "#58a6ff"
            }
            color = colors.get(status, "#8b949e")
            self.status_label.setStyleSheet(f"font-size: 11px; color: {color};")
            
            # Show/Hide Quick Start Button
            if status == "stopped":
                self.quick_start_btn.setText("Start")
                self.quick_start_btn.show()
                self.quick_start_btn.setEnabled(True)
            elif status == "running":
                self.quick_start_btn.setText("Stop")
                self.quick_start_btn.show()
                self.quick_start_btn.setEnabled(True)
            elif status in ["starting", "installing"]:
                self.quick_start_btn.setText(status.title())
                self.quick_start_btn.show()
                self.quick_start_btn.setEnabled(False)
            else:
                self.quick_start_btn.hide()

            # Always show logs button if we have backend manager
            self.view_logs_btn.show()

    def _on_quick_start_clicked(self):
        if not self.backend_manager:
            return
            
        provider = self.provider_combo.currentText()
        backend_id = None
        if provider == "Stable Diffusion": backend_id = "sd"
        elif provider == "ComfyUI": backend_id = "comfy"
        
        if not backend_id:
            return
            
        status = self.backend_manager.get_status(backend_id)
        if status == "stopped":
            self.backend_manager.start(backend_id)
        elif status == "running":
            self.backend_manager.stop(backend_id)

    def _on_gen_clicked(self):
        providers = ["sd", "comfy", "openai", "hf"]
        provider = providers[self.provider_combo.currentIndex()]
        params = {
            "prompt": self.prompt_input.text(),
            "negative_prompt": self.neg_prompt_input.text(),
            "steps": self.steps_spin.value(),
            "cfg_scale": self.cfg_spin.value()
        }
        self.gen_btn.setEnabled(False)
        self.gen_btn.setText("Generating...")
        self.generation_requested.emit(provider, params)

    def add_to_gallery(self, filepath):
        self.gen_btn.setEnabled(True)
        self.gen_btn.setText("Generate Image")
        
        if not os.path.exists(filepath):
            return

        row = len(self.history) // 2
        col = len(self.history) % 2
        
        thumb = QLabel()
        pixmap = QPixmap(filepath).scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        thumb.setPixmap(pixmap)
        thumb.setToolTip(filepath)
        thumb.setStyleSheet("border: 1px solid #30363d; border-radius: 4px;")
        thumb.setCursor(Qt.PointingHandCursor)
        thumb.mousePressEvent = lambda e: self.image_selected.emit(filepath)
        
        self.gallery_layout.addWidget(thumb, row, col)
        self.history.append(filepath)

    def refresh(self):
        from ..core.image_gen import GEN_DIR
        while self.gallery_layout.count():
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.history.clear()
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            for filepath in sorted(GEN_DIR.glob(ext), key=lambda p: p.stat().st_mtime, reverse=True):
                self._add_image(str(filepath))

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        fg = theme.get("fg", "#e6edf3")
        sidebar_bg = theme.get("sidebar_bg", "#1e1f23")
        input_bg = theme.get("input_bg", "#0d1117")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#58a6ff")

        for lbl in self.findChildren(QLabel):
            if lbl.text() == "Image Generation":
                lbl.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {fg};")

        for frame in self.findChildren(QFrame):
            if frame.parent() is self:
                frame.setStyleSheet(f"background: {sidebar_bg}; border-radius: 8px; border: 1px solid {border};")

        self.prompt_input.setStyleSheet(f"background: {input_bg}; border: 1px solid {border}; padding: 5px; color: {fg};")
        self.neg_prompt_input.setStyleSheet(f"background: {input_bg}; border: 1px solid {border}; padding: 5px; color: {fg};")
        self.scroll.setStyleSheet("background: transparent; border: none;")

        self.gen_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 6px;
            }}
            QPushButton:hover {{ background-color: {accent}; }}
        """)
