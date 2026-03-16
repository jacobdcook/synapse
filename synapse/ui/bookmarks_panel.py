import json
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QHBoxLayout, QFrame
)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QColor
from ..utils.constants import CONV_DIR

log = logging.getLogger(__name__)

class BookmarksPanel(QWidget):
    bookmark_selected = pyqtSignal(str, str) # conv_id, message_id

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("Message Bookmarks")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #58a6ff;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget { background: transparent; border: none; }
            QListWidget::item { 
                background: #21262d; 
                border-radius: 6px; 
                margin-bottom: 8px; 
                padding: 10px;
                color: #c9d1d9;
            }
            QListWidget::item:selected { background: #30363d; border: 1px solid #58a6ff; }
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

    def refresh(self):
        self.list_widget.clear()
        
        # Scan all conversations for bookmarks
        for f in CONV_DIR.glob("*.json"):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                    conv_id = data.get("id")
                    conv_title = data.get("title", "Untitled")
                    
                    for msg in data.get("messages", []):
                        if msg.get("bookmarked"):
                            self._add_bookmark_item(conv_id, conv_title, msg)
            except Exception as e:
                log.warning(f"Failed to load bookmarks from {f.name}: {e}")
                continue

        if self.list_widget.count() == 0:
            item = QListWidgetItem("No bookmarks yet. Click the bookmark icon on any message.")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor("#484f58"))
            self.list_widget.addItem(item)

    def _add_bookmark_item(self, conv_id, conv_title, msg):
        item = QListWidgetItem()
        widget = QWidget()
        w_layout = QVBoxLayout(widget)
        w_layout.setContentsMargins(5, 5, 5, 5)

        head_layout = QHBoxLayout()
        source_label = QLabel(f"In: {conv_title}")
        source_label.setStyleSheet("color: #8b949e; font-size: 10px;")
        head_layout.addWidget(source_label)
        head_layout.addStretch()
        w_layout.addLayout(head_layout)

        content = str(msg.get("content", ""))
        snippet = content[:100] + "..." if len(content) > 100 else content
        content_label = QLabel(snippet)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("font-size: 12px;")
        w_layout.addWidget(content_label)

        item.setSizeHint(widget.sizeHint())
        item.setData(Qt.UserRole, (conv_id, msg.get("id")))
        
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def _on_item_clicked(self, item):
        conv_id, msg_id = item.data(Qt.UserRole)
        self.bookmark_selected.emit(conv_id, msg_id)

    def apply_theme(self, theme):
        accent = theme.get("accent", "#58a6ff")
        bg = theme.get("sidebar_bg", "#21262d")
        fg = theme.get("fg", "#c9d1d9")
        border = theme.get("border", "#30363d")
        self.list_widget.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none; }}
            QListWidget::item {{
                background: {bg};
                border-radius: 6px;
                margin-bottom: 8px;
                padding: 10px;
                color: {fg};
            }}
            QListWidget::item:selected {{ background: {border}; border: 1px solid {accent}; }}
        """)
