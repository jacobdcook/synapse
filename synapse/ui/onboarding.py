import json
import os
import logging
import urllib.request
import urllib.error
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QStackedWidget, QWidget,
    QLabel, QPushButton, QProgressBar, QFileDialog, QLineEdit,
    QFrame, QGridLayout, QScrollArea
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QFont, QPixmap, QIcon

from ..utils.constants import (
    APP_NAME, APP_VERSION, RECOMMENDED_MODELS, get_ollama_url,
    load_settings, save_settings
)
from .model_manager import ModelPullWorker

log = logging.getLogger(__name__)

class OnboardingWizard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setFixedSize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                color: #e6edf3;
            }
            QLabel { color: #e6edf3; }
            QPushButton {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px 16px;
                color: #c9d1d9;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #8b949e;
            }
            QPushButton#nextBtn {
                background-color: #238636;
                border-color: #2ea043;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#nextBtn:hover {
                background-color: #2ea043;
            }
            QLineEdit {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px;
                color: #e6edf3;
            }
            QProgressBar {
                border: 1px solid #30363d;
                border-radius: 4px;
                text-align: center;
                background: #161b22;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #238636;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Header Image/Logo area
        self.header = QFrame()
        self.header.setFixedHeight(120)
        self.header.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a1b26, stop:1 #0d1117); border-bottom: 1px solid #30363d;")
        header_layout = QVBoxLayout(self.header)
        self.logo_label = QLabel(APP_NAME)
        self.logo_label.setStyleSheet("font-size: 32px; font-weight: bold; color: #58a6ff;")
        self.logo_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(self.logo_label)
        self.layout.addWidget(self.header)

        # Stack for steps
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)

        # Bottom nav
        self.nav = QFrame()
        self.nav.setFixedHeight(60)
        self.nav.setStyleSheet("border-top: 1px solid #30363d; background: #0d1117;")
        nav_layout = QHBoxLayout(self.nav)
        nav_layout.setContentsMargins(20, 0, 20, 0)

        self.skip_btn = QPushButton("Skip Wizard")
        self.skip_btn.clicked.connect(self.reject)
        nav_layout.addWidget(self.skip_btn)

        nav_layout.addStretch()

        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(self._prev_step)
        nav_layout.addWidget(self.back_btn)

        self.next_btn = QPushButton("Next")
        self.next_btn.setObjectName("nextBtn")
        self.next_btn.clicked.connect(self._next_step)
        nav_layout.addWidget(self.next_btn)

        self.layout.addWidget(self.nav)

        # Build steps
        self._setup_steps()
        self._update_nav()

    def _setup_steps(self):
        # 1. Welcome
        self.stack.addWidget(self._create_welcome_page())
        # 2. Ollama Check
        self.stack.addWidget(self._create_ollama_page())
        # 3. Model Pull
        self.stack.addWidget(self._create_model_page())
        # 4. Workspace Path
        self.stack.addWidget(self._create_workspace_page())
        # 5. API Keys (optional pre-setup)
        self.stack.addWidget(self._create_api_page())
        # 6. Final
        self.stack.addWidget(self._create_final_page())

    def _create_welcome_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Welcome to the Future of Coding")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        title.setWordWrap(True)
        layout.addWidget(title)

        sub = QLabel(f"{APP_NAME} is your personal AI-powered agentic IDE. Let's get you set up in less than a minute.")
        sub.setStyleSheet("font-size: 14px; color: #8b949e; margin-top: 10px;")
        sub.setWordWrap(True)
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        layout.addStretch()
        return page

    def _create_ollama_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Connect to Ollama Engine")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        self.ollama_status = QLabel("Checking connection...")
        self.ollama_status.setStyleSheet("color: #8b949e; margin: 20px 0;")
        layout.addWidget(self.ollama_status)

        self.ollama_retry = QPushButton("Retry Connection")
        self.ollama_retry.clicked.connect(self._check_ollama)
        self.ollama_retry.hide()
        layout.addWidget(self.ollama_retry)

        layout.addStretch()

        # Start check automatically when page shown
        QTimer.singleShot(500, self._check_ollama)
        return page

    def _create_model_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Choose a Starting Model")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        self.model_grid = QGridLayout(scroll_content)
        self.model_grid.setSpacing(10)
        
        # Add 4 simplified model cards
        for i, rm in enumerate(RECOMMENDED_MODELS[:4]):
            card = QFrame()
            card.setStyleSheet("background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px;")
            cl = QVBoxLayout(card)
            cl.addWidget(QLabel(f"<b>{rm['name'].split(':')[0]}</b>"))
            cl.addWidget(QLabel(f"<span style='font-size:10px; color:#8b949e;'>{rm['desc']}</span>"))
            btn = QPushButton("Pull This")
            btn.clicked.connect(lambda checked, name=rm['name']: self._pull_model(name))
            cl.addWidget(btn)
            self.model_grid.addWidget(card, i // 2, i % 2)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self.pull_bar = QProgressBar()
        self.pull_bar.hide()
        layout.addWidget(self.pull_bar)

        self.pull_label = QLabel("")
        self.pull_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self.pull_label)

        return page

    def _create_workspace_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Select Workspace")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        desc = QLabel("Set the default directory where Synapse will look for your projects.")
        desc.setStyleSheet("color: #8b949e; margin-bottom: 20px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        row = QHBoxLayout()
        self.path_edit = QLineEdit(str(Path.home() / "SynapseProjects"))
        row.addWidget(self.path_edit)
        
        pick_btn = QPushButton("Browse...")
        pick_btn.clicked.connect(self._pick_path)
        row.addWidget(pick_btn)
        layout.addLayout(row)

        layout.addStretch()
        return page

    def _create_api_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("Cloud API Connections (Optional)")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        layout.addWidget(QLabel("OpenAI API Key:"))
        self.openai_key = QLineEdit()
        self.openai_key.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.openai_key)

        layout.addWidget(QLabel("Anthropic API Key:"))
        self.anthropic_key = QLineEdit()
        self.anthropic_key.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.anthropic_key)

        layout.addStretch()
        return page

    def _create_final_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("You're All Set!")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(title)

        sub = QLabel("Explore the sidebar to manage your models, projects, and templates.\nClick the microphone to use voice controls.")
        sub.setStyleSheet("font-size: 14px; color: #8b949e; margin: 20px 0;")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        layout.addStretch()
        return page

    def _check_ollama(self):
        self.ollama_status.setText("Checking for local Ollama engine...")
        try:
            req = urllib.request.Request(f"{get_ollama_url()}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                self.ollama_status.setText("✅ Found Ollama engine running on localhost.")
                self.ollama_status.setStyleSheet("color: #3fb950; font-weight: bold;")
                self.ollama_retry.hide()
                # Auto-advance if found? No, let user read and click next.
        except Exception:
            self.ollama_status.setText("❌ Ollama not found. Ensure it is installed and running.")
            self.ollama_status.setStyleSheet("color: #f85149; font-weight: bold;")
            self.ollama_retry.show()

    def _pull_model(self, name):
        self.pull_bar.show()
        self.pull_label.setText(f"Starting download of {name}...")
        self.pull_worker = ModelPullWorker(name)
        self.pull_worker.progress.connect(lambda s, p: (self.pull_bar.setValue(p), self.pull_label.setText(s)))
        self.pull_worker.finished.connect(self._on_pull_finished)
        self.pull_worker.start()

    def _on_pull_finished(self, success, msg):
        if success:
            self.pull_label.setText("✅ Download Complete!")
            self.pull_bar.setValue(100)
            # Short delay then next?
            QTimer.singleShot(1000, self._next_step)
        else:
            self.pull_label.setText(f"❌ Error: {msg}")

    def _pick_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Projects Parent Directory", self.path_edit.text())
        if path:
            self.path_edit.setText(path)

    def _next_step(self):
        if self.stack.currentIndex() < self.stack.count() - 1:
            self.stack.setCurrentIndex(self.stack.currentIndex() + 1)
            self._update_nav()
        else:
            self._finish()

    def _prev_step(self):
        if self.stack.currentIndex() > 0:
            self.stack.setCurrentIndex(self.stack.currentIndex() - 1)
            self._update_nav()

    def _update_nav(self):
        idx = self.stack.currentIndex()
        self.back_btn.setEnabled(idx > 0)
        self.next_btn.setText("Finish" if idx == self.stack.count() - 1 else "Next")
        self.skip_btn.setVisible(idx == 0)

    def _finish(self):
        # Save settings
        s = load_settings()
        s["onboarding_complete"] = True
        s["workspace_dir"] = self.path_edit.text()
        if self.openai_key.text(): s["openai_key"] = self.openai_key.text()
        if self.anthropic_key.text(): s["anthropic_key"] = self.anthropic_key.text()
        save_settings(s)
        self.accept()
