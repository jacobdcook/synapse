"""Voice panel with status, waveform placeholder, transcript, push-to-talk."""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame
from PyQt5.QtCore import pyqtSignal, Qt


class VoicePanel(QWidget):
    push_to_talk_requested = pyqtSignal(bool)
    mute_requested = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("font-size: 12px; color: #8b949e;")
        layout.addWidget(self.status_label)
        self.waveform_placeholder = QFrame()
        self.waveform_placeholder.setFixedHeight(40)
        self.waveform_placeholder.setStyleSheet("background: #161b22; border: 1px solid #30363d; border-radius: 4px;")
        layout.addWidget(self.waveform_placeholder)
        self.transcript_label = QLabel("")
        self.transcript_label.setWordWrap(True)
        self.transcript_label.setStyleSheet("font-size: 11px; color: #c9d1d9;")
        layout.addWidget(self.transcript_label)
        self.ptt_btn = QPushButton("Push to Talk")
        self.ptt_btn.setCheckable(True)
        self.ptt_btn.clicked.connect(lambda c: self.push_to_talk_requested.emit(c))
        layout.addWidget(self.ptt_btn)
        self.mute_btn = QPushButton("Mute")
        self.mute_btn.setCheckable(True)
        self.mute_btn.clicked.connect(lambda c: self.mute_requested.emit(c))
        layout.addWidget(self.mute_btn)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_transcript(self, text: str):
        self.transcript_label.setText(text)
