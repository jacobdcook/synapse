import logging
import math
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QScrollArea
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QBrush, QPolygon

log = logging.getLogger(__name__)

class BranchTreeNode:
    def __init__(self, msg_id, role, content, parent_id=None):
        self.id = msg_id
        self.role = role
        self.content = content[:50] + "..." if len(content) > 50 else content
        self.parent_id = parent_id
        self.children = []
        self.x = 0
        self.y = 0
        self.level = 0

class TreeWidget(QWidget):
    node_selected = pyqtSignal(str) # msg_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.nodes = {} # id -> BranchTreeNode
        self.root = None
        self.active_id = None
        self.setMouseTracking(True)
        self.setMinimumSize(400, 600)
        self.node_rects = {} # id -> QRect

    def set_data(self, history, active_id):
        self.nodes = {}
        self.active_id = active_id
        
        # Build tree structure
        for msg in history:
            m_id = msg.get("id")
            if not m_id: continue
            node = BranchTreeNode(m_id, msg.get("role", "system"), msg.get("content", ""), msg.get("parent_id"))
            self.nodes[m_id] = node

        # Connect children
        for m_id, node in self.nodes.items():
            if node.parent_id and node.parent_id in self.nodes:
                self.nodes[node.parent_id].children.append(node)
            elif not node.parent_id:
                self.root = node

        self._layout_tree()
        self.update()

    def _layout_tree(self):
        if not self.root: return
        
        # Simple vertical layout
        self._assign_levels(self.root, 0)
        
        # Width per level
        level_counts = {}
        self._count_levels(self.root, level_counts)
        
        max_level = max(level_counts.keys()) if level_counts else 0
        max_width = max(level_counts.values()) if level_counts else 0
        
        self.setMinimumHeight((max_level + 1) * 80 + 100)
        self.setMinimumWidth(max_width * 150 + 100)
        
        # Position nodes
        current_offset = {} # level -> count
        self._position_nodes(self.root, current_offset)

    def _assign_levels(self, node, level):
        node.level = level
        for child in node.children:
            self._assign_levels(child, level + 1)

    def _count_levels(self, node, counts):
        counts[node.level] = counts.get(node.level, 0) + 1
        for child in node.children:
            self._count_levels(child, counts)

    def _position_nodes(self, node, level_offsets):
        idx = level_offsets.get(node.level, 0)
        node.x = 50 + idx * 150
        node.y = 50 + node.level * 80
        level_offsets[node.level] = idx + 1
        
        for child in node.children:
            self._position_nodes(child, level_offsets)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if not self.root:
            painter.setPen(QColor("#858585"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No conversation history.")
            return

        # Draw connections
        pen = QPen(QColor("#404040"), 2)
        painter.setPen(pen)
        for node in self.nodes.values():
            for child in node.children:
                painter.drawLine(node.x + 40, node.y + 20, child.x + 40, child.y + 20)

        # Draw nodes
        self.node_rects = {}
        for m_id, node in self.nodes.items():
            rect = QRect(node.x, node.y, 80, 40)
            self.node_rects[m_id] = rect
            
            # Highlight active branch path or just the active node
            is_active = (m_id == self.active_id)
            
            bg_color = QColor("#2d2d2d")
            if is_active:
                bg_color = QColor("#0e639c")
            elif node.role == "user":
                bg_color = QColor("#3c3c3c")
            
            painter.setBrush(QBrush(bg_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 8, 8)
            
            painter.setPen(QColor("#cccccc"))
            painter.setFont(QFont("Segoe UI", 8))
            label = node.role.capitalize()
            painter.drawText(rect, Qt.AlignCenter, label)

    def mousePressEvent(self, event):
        for m_id, rect in self.node_rects.items():
            if rect.contains(event.pos()):
                self.node_selected.emit(m_id)
                self.update()
                break

class BranchTreeSidebar(QWidget):
    branch_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("Conversation Tree")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #cccccc; margin-bottom: 10px;")
        layout.addWidget(title)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("background-color: #252526;")
        
        self.tree_widget = TreeWidget()
        self.tree_widget.node_selected.connect(self.branch_requested.emit)
        self.scroll.setWidget(self.tree_widget)
        
        layout.addWidget(self.scroll)

    def refresh(self, history, active_id):
        self.tree_widget.set_data(history, active_id)

    def apply_theme(self, theme):
        fg = theme.get("fg", "#ccc")
        sidebar_bg = theme.get("sidebar_bg", "#1e1e1e")
        self.scroll.setStyleSheet(f"background-color: {sidebar_bg};")
