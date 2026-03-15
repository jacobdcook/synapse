import uuid
import logging
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel, QListWidget,
    QListWidgetItem, QMenu, QMessageBox, QInputDialog, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from ..utils.constants import relative_time
from ..core.renderer import ChatRenderer

log = logging.getLogger(__name__)

class SidebarWidget(QWidget):
    conversation_selected = pyqtSignal(str)
    new_chat_requested = pyqtSignal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setMinimumWidth(200)
        self.setMaximumWidth(350)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.new_btn = QPushButton("+ New Chat")
        self.new_btn.setObjectName("newChatBtn")
        self.new_btn.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self.new_btn)

        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search conversations...")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.textChanged.connect(self._filter)
        layout.addWidget(self.search_field)

        self.pinned_label = QLabel("PINNED")
        self.pinned_label.setObjectName("sidebarTitle")
        self.pinned_label.hide()
        layout.addWidget(self.pinned_label)

        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._context_menu)
        self.list_widget.currentItemChanged.connect(self._on_select)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)

        self._all_convos = []

    def refresh(self, select_id=None):
        self._all_convos = self.store.list_conversations()
        self._populate(self._all_convos, select_id)

    def _populate(self, convos, select_id=None):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        pinned = [c for c in convos if c.get("pinned")]
        unpinned = [c for c in convos if not c.get("pinned")]
        self.pinned_label.setVisible(bool(pinned))

        if pinned:
            sep_item = QListWidgetItem("--- PINNED ---")
            sep_item.setFlags(Qt.NoItemFlags)
            sep_item.setForeground(QColor("#555"))
            self.list_widget.addItem(sep_item)

        for c in pinned:
            self._add_conv_item(c, select_id, is_pinned=True)

        if pinned and unpinned:
            sep_item = QListWidgetItem("--- RECENT ---")
            sep_item.setFlags(Qt.NoItemFlags)
            sep_item.setForeground(QColor("#555"))
            self.list_widget.addItem(sep_item)

        for c in unpinned:
            self._add_conv_item(c, select_id)

        self.list_widget.blockSignals(False)

    def _add_conv_item(self, c, select_id=None, is_pinned=False):
        rel = relative_time(c.get("updated_at", ""))
        prefix = "[*] " if is_pinned else ""
        display = f"{prefix}{c['title']}"
        tags = c.get("tags", [])
        if tags:
            display += f"  [{', '.join('#' + t for t in tags[:3])}]"
        if rel:
            display += f"  \u00b7  {rel}"
        item = QListWidgetItem(display)
        item.setData(Qt.UserRole, c["id"])
        item.setData(Qt.UserRole + 1, c["title"])
        item.setData(Qt.UserRole + 2, c.get("pinned", False))
        item.setToolTip(f"Model: {c['model']}\nUpdated: {c['updated_at'][:19]}")
        self.list_widget.addItem(item)
        if select_id and c["id"] == select_id:
            self.list_widget.setCurrentItem(item)

    def _filter(self, text):
        if not text.strip():
            self._populate(self._all_convos)
            return
        results = self.store.search(text.strip())
        self._populate(results)

    def _on_select(self, current, _previous):
        if current and current.data(Qt.UserRole):
            conv_id = current.data(Qt.UserRole)
            self.conversation_selected.emit(conv_id)

    def _on_double_click(self, item):
        if not item.data(Qt.UserRole):
            return
        conv_id = item.data(Qt.UserRole)
        old_title = item.data(Qt.UserRole + 1) or item.text()
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New title:", text=old_title
        )
        if ok and new_name.strip():
            conv = self.store.load(conv_id)
            if conv:
                conv["title"] = new_name.strip()
                self.store.save(conv)
                self.refresh(select_id=conv_id)

    def _context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item or not item.data(Qt.UserRole):
            return
        conv_id = item.data(Qt.UserRole)
        title = item.data(Qt.UserRole + 1) or item.text()
        is_pinned = item.data(Qt.UserRole + 2)

        menu = QMenu(self)
        pin_action = menu.addAction("Unpin" if is_pinned else "Pin")
        rename_action = menu.addAction("Rename")
        duplicate_action = menu.addAction("Duplicate")
        tags_action = menu.addAction("Edit Tags")
        delete_action = menu.addAction("Delete")
        menu.addSeparator()
        export_md_action = menu.addAction("Export as Markdown")
        export_html_action = menu.addAction("Export as HTML")
        action = menu.exec_(self.list_widget.mapToGlobal(pos))

        if action == pin_action:
            conv = self.store.load(conv_id)
            if conv:
                conv["pinned"] = not is_pinned
                self.store.save(conv)
                self.refresh(select_id=conv_id)

        elif action == rename_action:
            new_name, ok = QInputDialog.getText(
                self, "Rename", "New title:", text=title
            )
            if ok and new_name.strip():
                conv = self.store.load(conv_id)
                if conv:
                    conv["title"] = new_name.strip()
                    self.store.save(conv)
                    self.refresh(select_id=conv_id)

        elif action == duplicate_action:
            conv = self.store.load(conv_id)
            if conv:
                import copy
                new_conv = copy.deepcopy(conv)
                new_conv["id"] = str(uuid.uuid4())
                new_conv["title"] = conv.get("title", "Untitled") + " (copy)"
                new_conv["updated_at"] = datetime.now().isoformat()
                self.store.save(new_conv)
                self.refresh(select_id=new_conv["id"])

        elif action == tags_action:
            conv = self.store.load(conv_id)
            if conv:
                current_tags = ", ".join(conv.get("tags", []))
                new_tags, ok = QInputDialog.getText(
                    self, "Edit Tags", "Tags (comma-separated):", text=current_tags
                )
                if ok:
                    tags = [t.strip().lstrip("#") for t in new_tags.split(",") if t.strip()]
                    conv["tags"] = tags
                    self.store.save(conv)
                    self.refresh(select_id=conv_id)

        elif action == delete_action:
            reply = QMessageBox.question(
                self, "Delete", f'Delete "{title}"?',
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.store.delete(conv_id)
                self.refresh()
                self.new_chat_requested.emit()

        elif action == export_md_action:
            self._export_markdown(conv_id)

        elif action == export_html_action:
            self._export_html(conv_id)

    def _export_markdown(self, conv_id):
        conv = self.store.load(conv_id)
        if not conv:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Conversation",
            f"{conv['title']}.md", "Markdown (*.md)"
        )
        if path:
            with open(path, "w") as f:
                f.write(f"# {conv['title']}\n\n")
                f.write(f"Model: {conv['model']}\n")
                f.write(f"Date: {conv['created_at'][:10]}\n\n---\n\n")
                for msg in conv.get("messages", []):
                    role = "**You**" if msg["role"] == "user" else "**Assistant**"
                    f.write(f"{role}:\n\n{msg['content']}\n\n---\n\n")

    def _export_html(self, conv_id):
        conv = self.store.load(conv_id)
        if not conv:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export as HTML",
            f"{conv['title']}.html", "HTML (*.html)"
        )
        if not path:
            return
        renderer = ChatRenderer()
        html = renderer.build_html(conv.get("messages", []), conv.get("model", ""))
        with open(path, "w") as f:
            f.write(html)
