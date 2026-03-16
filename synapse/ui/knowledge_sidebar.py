import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal

log = logging.getLogger(__name__)

class KnowledgeSidebar(QWidget):
    reindex_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(350)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("KNOWLEDGE")
        title.setObjectName("sidebarTitle")
        title.setStyleSheet("font-weight: bold; color: #858585; text-transform: uppercase;")
        layout.addWidget(title)

        # Stats Card
        self.stats_card = QFrame()
        self.stats_card.setFrameShape(QFrame.StyledPanel)
        self.stats_card.setStyleSheet("background-color: #2d2d2d; border-radius: 4px; border: 1px solid #3e3e3e;")
        stats_layout = QVBoxLayout(self.stats_card)
        stats_layout.setContentsMargins(10, 10, 10, 10)
        
        self.file_count_lb = QLabel("Files Indexed: 0")
        self.chunk_count_lb = QLabel("Total Chunks: 0")
        self.vector_status_lb = QLabel("Engine: nomic-embed-text")
        
        for lb in [self.file_count_lb, self.chunk_count_lb, self.vector_status_lb]:
            lb.setStyleSheet("color: #cccccc; font-size: 12px;")
            stats_layout.addWidget(lb)
        
        layout.addWidget(self.stats_card)

        # Actions
        self.reindex_btn = QPushButton("\u21bb Re-index Workspace")
        self.reindex_btn.setStyleSheet("""
            QPushButton {
                background-color: #3e3e42;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4e4e52;
            }
        """)
        self.reindex_btn.clicked.connect(self.reindex_requested.emit)
        layout.addWidget(self.reindex_btn)

        layout.addStretch()

        help_text = QLabel(
            "RAG is active.\n\n"
            "Use '@' in chat to mention specific files.\n\n"
            "Synapse will automatically search your workspace to provide relevant context for your questions."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666666; font-size: 11px; font-style: italic;")
        layout.addWidget(help_text)

    def update_stats(self, index):
        if not index:
            self.file_count_lb.setText("Files Indexed: 0")
            self.chunk_count_lb.setText("Total Chunks: 0")
            return

        file_count = len(index)
        chunk_count = sum(len(data.get("chunks", [])) for data in index.values())
        
        self.file_count_lb.setText(f"Files Indexed: {file_count}")
        self.chunk_count_lb.setText(f"Total Chunks: {chunk_count}")
