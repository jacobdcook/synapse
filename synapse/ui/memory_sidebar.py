"""Episodic memory sidebar: recent episodes, search, user patterns."""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QFrame, QScrollArea
)
from PyQt5.QtCore import Qt

log = logging.getLogger(__name__)


class MemorySidebar(QWidget):
    def __init__(self, episodic_memory, parent=None):
        super().__init__(parent)
        self.episodic = episodic_memory
        self.setMinimumWidth(220)
        self.setMaximumWidth(350)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("EPISODIC MEMORY")
        title.setObjectName("sidebarTitle")
        title.setStyleSheet("font-weight: bold; color: #858585; text-transform: uppercase;")
        layout.addWidget(title)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by topic...")
        self.search_edit.setStyleSheet(
            "QLineEdit { background: #2d2d2d; color: #ccc; border: 1px solid #444; "
            "border-radius: 4px; padding: 6px; font-size: 12px; }"
        )
        self.search_edit.returnPressed.connect(self._on_search)
        layout.addWidget(self.search_edit)

        search_btn = QPushButton("Search")
        search_btn.setStyleSheet("QPushButton { background: #333; color: #ccc; padding: 6px 12px; border-radius: 4px; }")
        search_btn.clicked.connect(self._on_search)
        layout.addWidget(search_btn)

        recent_label = QLabel("Recent Episodes")
        recent_label.setStyleSheet("font-weight: bold; color: #858585; font-size: 10px; margin-top: 8px;")
        layout.addWidget(recent_label)

        self.episode_list = QListWidget()
        self.episode_list.setStyleSheet("""
            QListWidget { background: #1e1e1e; border: 1px solid #333; border-radius: 4px; color: #bbb; font-size: 11px; }
            QListWidget::item { padding: 4px; }
            QListWidget::item:hover { background: #2a2d2e; }
        """)
        self.episode_list.setMaximumHeight(180)
        layout.addWidget(self.episode_list)

        patterns_label = QLabel("User Patterns")
        patterns_label.setStyleSheet("font-weight: bold; color: #858585; font-size: 10px; margin-top: 8px;")
        layout.addWidget(patterns_label)

        self.patterns_frame = QFrame()
        self.patterns_frame.setStyleSheet("background: #2d2d2d; border-radius: 4px; padding: 8px; border: 1px solid #3e3e3e;")
        patterns_layout = QVBoxLayout(self.patterns_frame)
        patterns_layout.setContentsMargins(8, 8, 8, 8)
        self.patterns_text = QLabel("No patterns yet.")
        self.patterns_text.setWordWrap(True)
        self.patterns_text.setStyleSheet("color: #8b949e; font-size: 11px;")
        patterns_layout.addWidget(self.patterns_text)
        layout.addWidget(self.patterns_frame)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("Clear Memory")
        clear_btn.setStyleSheet("QPushButton { background: #c0392b; color: white; padding: 6px 12px; border-radius: 4px; }")
        clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(clear_btn)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setStyleSheet("QPushButton { background: #333; color: #ccc; padding: 6px 12px; border-radius: 4px; }")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)
        layout.addLayout(btn_row)

        layout.addStretch()
        self._refresh()

    def _on_search(self):
        q = self.search_edit.text().strip()
        if not q:
            self._refresh()
            return
        episodes = self.episodic.query_by_topic(q, limit=15)
        self.episode_list.clear()
        for e in episodes:
            topic = (e.get("topic") or "")[:60]
            outcome = (e.get("outcome") or "")[:80]
            item = QListWidgetItem(f"{topic}\n{outcome}...")
            item.setData(Qt.UserRole, e)
            self.episode_list.addItem(item)

    def _refresh(self):
        self.episode_list.clear()
        episodes = self.episodic.query_recent(limit=30)
        by_conv = {}
        for e in episodes:
            cid = e.get("conversation_id", "")
            if cid not in by_conv:
                by_conv[cid] = []
            by_conv[cid].append(e)
        for cid, eps in list(by_conv.items())[:10]:
            for e in sorted(eps, key=lambda x: -x.get("turn_index", 0))[:3]:
                topic = (e.get("topic") or "No topic")[:50]
                item = QListWidgetItem(f"[{cid[:8]}...] {topic}")
                item.setData(Qt.UserRole, e)
                self.episode_list.addItem(item)
        patterns = self.episodic.get_user_patterns()
        lines = []
        if patterns.get("topics"):
            lines.append("Topics: " + ", ".join(patterns["topics"][:5]))
        if patterns.get("preferred_tools"):
            lines.append("Tools: " + ", ".join(patterns["preferred_tools"][:5]))
        if patterns.get("frustrations"):
            lines.append(f"Frustrations: {len(patterns['frustrations'])} noted")
        self.patterns_text.setText("\n".join(lines) if lines else "No patterns yet.")

    def _on_clear(self):
        reply = QMessageBox.question(
            self, "Clear Episodic Memory",
            "Delete all episodic memories? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.episodic.clear_all()
            self._refresh()
