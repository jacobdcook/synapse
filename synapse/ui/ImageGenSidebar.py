import os
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QLineEdit, QScrollArea, QFrame, QGridLayout, QSpinBox,
    QDoubleSpinBox, QComboBox, QFileDialog
)

class ImageGenSidebar(QWidget):
    generation_requested = pyqtSignal(str, dict) # provider, params
    image_selected = pyqtSignal(str) # filepath

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.history = []

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
        self.provider_combo.addItems(["Stable Diffusion", "ComfyUI", "OpenAI DALL-E 3"])
        provider_layout.addWidget(self.provider_combo)
        settings_layout.addLayout(provider_layout)

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

    def _on_gen_clicked(self):
        providers = ["sd", "comfy", "openai"]
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
