import uuid
import logging
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, 
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QInputDialog, QFileDialog,
    QFrame, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QIcon, QFont
from ..utils.constants import relative_time, DEFAULT_FOLDERS, TAG_COLORS
from ..core.renderer import ChatRenderer

log = logging.getLogger(__name__)

class TagChip(QPushButton):
    """A small clickable tag chip for the filter bar."""
    clicked_tag = pyqtSignal(str)

    def __init__(self, tag, color="#555", parent=None):
        super().__init__(f"#{tag}", parent)
        self.tag = tag
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background: #1e1e1e;
                color: {color};
                border: 1px solid {color}44;
                border-radius: 10px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #2a2a2a;
                border: 1px solid {color}aa;
            }}
            QPushButton:checked {{
                background: {color};
                color: #000;
                border: 1px solid {color};
            }}
        """)
        self.clicked.connect(lambda: self.clicked_tag.emit(self.tag))

class SidebarWidget(QWidget):
    conversation_selected = pyqtSignal(str)
    new_chat_requested = pyqtSignal()

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        self.setMinimumWidth(240)
        self.setMaximumWidth(400)
        self._filter_tag = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # New Chat Button
        self.new_btn = QPushButton("+ New Chat")
        self.new_btn.setObjectName("newChatBtn")
        self.new_btn.setFixedHeight(40)
        self.new_btn.setCursor(Qt.PointingHandCursor)
        self.new_btn.clicked.connect(self.new_chat_requested.emit)
        layout.addWidget(self.new_btn)

        # Search Bar
        search_container = QWidget()
        search_layout = QVBoxLayout(search_container)
        search_layout.setContentsMargins(10, 8, 10, 8)
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search chats or tags...")
        self.search_field.setClearButtonEnabled(True)
        self.search_field.setFixedHeight(30)
        self.search_field.setObjectName("sidebarSearch")
        self.search_field.textChanged.connect(self._filter)
        search_layout.addWidget(self.search_field)
        layout.addWidget(search_container)

        # Tag Filter Bar
        self.tag_scroll = QScrollArea()
        self.tag_scroll.setFixedHeight(38)
        self.tag_scroll.setWidgetResizable(True)
        self.tag_scroll.setFrameShape(QFrame.NoFrame)
        self.tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.tag_container = QWidget()
        self.tag_layout = QHBoxLayout(self.tag_container)
        self.tag_layout.setContentsMargins(10, 2, 10, 8)
        self.tag_layout.setSpacing(6)
        self.tag_scroll.setWidget(self.tag_container)
        layout.addWidget(self.tag_scroll)

        # Tree View for Folders and Chats
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDragDropMode(QTreeWidget.InternalMove)
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.setAnimated(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree.currentItemChanged.connect(self._on_select)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        
        # Tree Styling
        self.tree.setStyleSheet("""
            QTreeWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QTreeWidget::item {
                padding: 6px 4px;
                border-radius: 4px;
                margin: 1px 6px;
                color: #ccc;
            }
            QTreeWidget::item:hover {
                background: #2a2d2e;
            }
            QTreeWidget::item:selected {
                background: #37373d;
                color: #fff;
            }
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                image: url(n/a); /* Hide default arrows if needed, or use custom */
            }
        """)
        
        layout.addWidget(self.tree)

        self._all_convos = []
        self._folder_items = {}

    def apply_theme(self, theme):
        bg = theme.get("sidebar_bg", "#1e1e1e")
        fg = theme.get("fg", "#ccc")
        border = theme.get("border", "#1e1e1e")
        accent = theme.get("accent", "#58a6ff")
        hover = theme.get("input_bg", "#2a2d2e")
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 6px 4px;
                border-radius: 4px;
                margin: 1px 6px;
                color: {fg};
            }}
            QTreeWidget::item:hover {{
                background: {hover};
            }}
            QTreeWidget::item:selected {{
                background: {border};
                color: {accent};
            }}
        """)

    def refresh(self, select_id=None):
        self._all_convos = self.store.list_conversations()
        self._update_tags()
        filtered = self._filter_convos(self.search_field.text())
        self._populate(filtered, select_id)

    def _update_tags(self):
        # Clear existing tag chips
        while self.tag_layout.count():
            item = self.tag_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        all_tags = set()
        for c in self._all_convos:
            for t in c.get("tags", []):
                all_tags.add(t)
        
        if not all_tags:
            self.tag_scroll.hide()
            return
        
        self.tag_scroll.show()
        for tag in sorted(list(all_tags)):
            color = TAG_COLORS.get(tag.lower(), "#888")
            chip = TagChip(tag, color)
            if tag == self._filter_tag:
                chip.setChecked(True)
            chip.clicked_tag.connect(self._toggle_tag_filter)
            self.tag_layout.addWidget(chip)
        self.tag_layout.addStretch()

    def _toggle_tag_filter(self, tag):
        self._filter_tag = tag if self._filter_tag != tag else None
        self.refresh()

    def _filter_convos(self, text):
        query = text.strip().lower()
        results = self._all_convos
        
        if self._filter_tag:
            results = [c for c in results if self._filter_tag in c.get("tags", [])]
        
        if query:
            results = [c for c in results if query in c["title"].lower() or any(query in t.lower() for t in c.get("tags", []))]
        
        return results

    def _populate(self, convos, select_id=None):
        self.tree.blockSignals(True)
        self.tree.clear()
        self._folder_items = {}

        # 1. Create Folder Structure (Always show DEFAULT_FOLDERS)
        all_folders = sorted(list(set(DEFAULT_FOLDERS + [c.get("folder", "General") for c in convos])))
        
        for f_name in all_folders:
            f_item = QTreeWidgetItem(self.tree)
            f_item.setText(0, f_name.upper())
            f_item.setData(0, Qt.UserRole, "folder")
            f_item.setForeground(0, QColor("#666"))
            # Custom font for folders
            font = QFont()
            font.setBold(True)
            font.setPointSize(8)
            f_item.setFont(0, font)
            f_item.setExpanded(True)
            self._folder_items[f_name] = f_item

        # 2. Add Chats to Folders
        # Sort so pinned are at the top within each folder
        sorted_convos = sorted(convos, key=lambda x: (not x.get("pinned", False), x.get("updated_at", "")), reverse=True)

        for c in sorted_convos:
            f_name = c.get("folder", "General")
            parent = self._folder_items.get(f_name, self._folder_items["General"])
            self._add_chat_item(parent, c, select_id)

        self.tree.blockSignals(False)

    def _add_chat_item(self, parent, c, select_id=None):
        rel = relative_time(c.get("updated_at", ""))
        is_pinned = c.get("pinned", False)
        prefix = "📌 " if is_pinned else ""
        display = f"{prefix}{c['title']}"
        
        # Show mini tags in title if they exist
        tags = c.get("tags", [])
        if tags:
            tag_str = " ".join([f"#{t}" for t in tags[:2]])
            display += f"  <font color='#555' size='2'>{tag_str}</font>"

        item = QTreeWidgetItem(parent)
        item.setText(0, display)
        item.setData(0, Qt.UserRole, c["id"])
        item.setData(0, Qt.UserRole + 1, c["title"])
        item.setData(0, Qt.UserRole + 2, is_pinned)
        
        if rel:
            item.setToolTip(0, f"Model: {c['model']}\nLast active: {rel}")
        
        if select_id and c["id"] == select_id:
            self.tree.setCurrentItem(item)
            item.parent().setExpanded(True)

    def _filter(self, text):
        self.refresh()

    def _on_select(self, current, _previous):
        if current and current.data(0, Qt.UserRole) != "folder":
            conv_id = current.data(0, Qt.UserRole)
            self.conversation_selected.emit(conv_id)

    def _on_double_click(self, item, column):
        if not item or item.data(0, Qt.UserRole) == "folder":
            return
        
        conv_id = item.data(0, Qt.UserRole)
        old_title = item.data(0, Qt.UserRole + 1) or item.text(0)
        new_name, ok = QInputDialog.getText(self, "Rename Chat", "New title:", text=old_title)
        if ok and new_name.strip():
            conv = self.store.load(conv_id)
            if conv:
                conv["title"] = new_name.strip()
                self.store.save(conv)
                self.refresh(select_id=conv_id)

    def _context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item: return

        menu = QMenu(self)
        if item.data(0, Qt.UserRole) == "folder":
            f_name = item.text(0).title()
            menu.addAction(f"Folder: {f_name}").setEnabled(False)
            # Future: Rename/Delete custom folders
        else:
            conv_id = item.data(0, Qt.UserRole)
            title = item.data(0, Qt.UserRole + 1)
            is_pinned = item.data(0, Qt.UserRole + 2)

            pin_act = menu.addAction("Unpin" if is_pinned else "Pin")
            rename_act = menu.addAction("Rename")
            duplicate_act = menu.addAction("Duplicate")
            
            # Move Menu
            move_menu = menu.addMenu("Move to Folder")
            for f in DEFAULT_FOLDERS:
                move_menu.addAction(f).setData(f)
            
            tags_act = menu.addAction("Edit Tags")
            delete_act = menu.addAction("Delete")
            menu.addSeparator()
            export_md = menu.addAction("Export as Markdown")
            export_html = menu.addAction("Export as HTML")
            
            action = menu.exec_(self.tree.mapToGlobal(pos))
            if not action: return

            if action == pin_act:
                conv = self.store.load(conv_id)
                if conv:
                    conv["pinned"] = not is_pinned
                    self.store.save(conv)
                    self.refresh(select_id=conv_id)
            elif action == rename_act:
                self._on_double_click(item, 0)
            elif action == duplicate_act:
                self._duplicate_chat(conv_id)
            elif action.parent() == move_menu:
                self.store.move_to_folder(conv_id, action.data())
                self.refresh(select_id=conv_id)
            elif action == tags_act:
                self._edit_tags(conv_id)
            elif action == delete_act:
                self._delete_chat(conv_id, title)
            elif action == export_md:
                self._export_markdown(conv_id)
            elif action == export_html:
                self._export_html(conv_id)

    def _duplicate_chat(self, conv_id):
        conv = self.store.load(conv_id)
        if not conv:
            return
        try:
            import copy
            new_conv = copy.deepcopy(conv)
            new_conv["id"] = str(uuid.uuid4())
            new_conv["title"] += " (copy)"
            new_conv["updated_at"] = datetime.now().isoformat()
            self.store.save(new_conv)
            self.refresh(select_id=new_conv["id"])
        except Exception as e:
            log.error(f"Failed to duplicate chat: {e}")

    def _edit_tags(self, conv_id):
        conv = self.store.load(conv_id)
        if conv:
            current = ", ".join(conv.get("tags", []))
            new_tags, ok = QInputDialog.getText(self, "Edit Tags", "Tags (comma-separated):", text=current)
            if ok:
                tags = [t.strip().lstrip("#") for t in new_tags.split(",") if t.strip()]
                conv["tags"] = tags
                self.store.save(conv)
                self.refresh(select_id=conv_id)

    def _delete_chat(self, conv_id, title):
        if QMessageBox.question(self, "Delete Chat", f"Are you sure you want to delete '{title}'?") == QMessageBox.Yes:
            self.store.delete(conv_id)
            self.refresh()
            self.new_chat_requested.emit()

    def dropEvent(self, event):
        item = self.tree.itemAt(event.pos())
        if item and item.data(0, Qt.UserRole) == "folder":
            folder_name = item.text(0).title()
            dragged = self.tree.currentItem()
            if dragged and dragged.data(0, Qt.UserRole) != "folder":
                conv_id = dragged.data(0, Qt.UserRole)
                self.store.move_to_folder(conv_id, folder_name)
                self.refresh(select_id=conv_id)
                event.accept()
                return
        super().dropEvent(event)

    def _export_markdown(self, conv_id):
        conv = self.store.load(conv_id)
        if not conv: return
        path, _ = QFileDialog.getSaveFileName(self, "Export Conversation", f"{conv['title']}.md", "Markdown (*.md)")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"# {conv['title']}\n\n")
                    f.write(f"*Model: {conv.get('model', 'Unknown')}*\n")
                    created = conv.get('created_at', '')
                    f.write(f"*Date: {created[:10] if created else 'Unknown'}*\n\n---\n\n")
                    for msg in conv.get("messages", []):
                        role = msg.get("role", "unknown").upper()
                        content = msg.get('content', '')
                        f.write(f"### {role}\n{content}\n")
                        images = msg.get("images", [])
                        if images:
                            f.write(f"\n*[{len(images)} image(s) attached]*\n")
                        files = msg.get("attached_files", [])
                        for af in files:
                            f.write(f"\n**Attached: {af.get('name', 'file')}**\n```\n{af.get('content', '')[:500]}\n```\n")
                        f.write("\n---\n\n")
            except OSError as e:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Export Error", f"Failed to write file: {e}")

    def _export_html(self, conv_id):
        conv = self.store.load(conv_id)
        if not conv: return
        path, _ = QFileDialog.getSaveFileName(self, "Export as HTML", f"{conv['title']}.html", "HTML (*.html)")
        if not path: return
        try:
            renderer = ChatRenderer()
            html = renderer.build_html(conv.get("messages", []), [])
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
        except OSError as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Export Error", f"Failed to write file: {e}")
