from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRect, QPoint
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QPainterPath, QPolygon


def _draw_icon(draw_fn, color="#858585", size=22):
    """Create a QIcon by calling draw_fn(painter, rect, color)."""
    px = QPixmap(size, size)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.5)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    draw_fn(p, QRect(1, 1, size - 2, size - 2), QColor(color))
    p.end()
    return QIcon(px)


# --- Icon drawing functions ---

def _draw_explorer(p, r, c):
    # Folder
    p.drawRect(r.x()+2, r.y()+5, r.width()-4, r.height()-7)
    p.drawLine(r.x()+2, r.y()+5, r.x()+6, r.y()+5)
    p.drawLine(r.x()+6, r.y()+5, r.x()+8, r.y()+2)
    p.drawLine(r.x()+8, r.y()+2, r.x()+14, r.y()+2)
    p.drawLine(r.x()+14, r.y()+2, r.x()+14, r.y()+5)

def _draw_chat(p, r, c):
    path = QPainterPath()
    path.addRoundedRect(r.x()+1, r.y()+1, r.width()-2, r.height()-6, 3, 3)
    p.drawPath(path)
    # Tail
    p.drawLine(r.x()+5, r.bottom()-4, r.x()+2, r.bottom())
    p.drawLine(r.x()+2, r.bottom(), r.x()+9, r.bottom()-4)
    # Dots
    y = r.center().y() - 1
    for x in [r.center().x()-4, r.center().x(), r.center().x()+4]:
        p.setBrush(c)
        p.drawEllipse(QPoint(x, y), 1, 1)
    p.setBrush(Qt.NoBrush)

def _draw_models(p, r, c):
    # CPU/chip
    p.drawRect(r.x()+5, r.y()+5, r.width()-10, r.height()-10)
    # Pins
    for i in range(3):
        off = 7 + i * 3
        p.drawLine(r.x()+off, r.y()+2, r.x()+off, r.y()+5)
        p.drawLine(r.x()+off, r.bottom()-4, r.x()+off, r.bottom()-1)
        p.drawLine(r.x()+2, r.y()+off, r.x()+5, r.y()+off)
        p.drawLine(r.right()-4, r.y()+off, r.right()-1, r.y()+off)

def _draw_plan(p, r, c):
    # Clipboard
    p.drawRect(r.x()+3, r.y()+3, r.width()-6, r.height()-4)
    p.drawRect(r.x()+7, r.y()+1, 6, 3)
    # Check
    p.drawLine(r.x()+7, r.y()+11, r.x()+9, r.y()+13)
    p.drawLine(r.x()+9, r.y()+13, r.x()+14, r.y()+8)

def _draw_git(p, r, c):
    # Branch
    cx, cy = r.center().x(), r.center().y()
    p.drawEllipse(QPoint(cx-4, cy-5), 2, 2)
    p.drawEllipse(QPoint(cx+4, cy-5), 2, 2)
    p.drawEllipse(QPoint(cx-4, cy+6), 2, 2)
    p.drawLine(cx-4, cy-3, cx-4, cy+4)
    p.drawLine(cx+4, cy-3, cx+4, cy)
    path = QPainterPath()
    path.moveTo(cx+4, cy)
    path.quadTo(cx+4, cy+3, cx-4, cy+4)
    p.drawPath(path)

def _draw_knowledge(p, r, c):
    # Open book
    cx = r.center().x()
    p.drawLine(cx, r.y()+3, cx, r.bottom()-2)
    path1 = QPainterPath()
    path1.moveTo(cx, r.y()+3)
    path1.quadTo(cx-5, r.y()+1, r.x()+2, r.y()+3)
    path1.lineTo(r.x()+2, r.bottom()-2)
    path1.quadTo(cx-5, r.bottom()-4, cx, r.bottom()-2)
    p.drawPath(path1)
    path2 = QPainterPath()
    path2.moveTo(cx, r.y()+3)
    path2.quadTo(cx+5, r.y()+1, r.right()-2, r.y()+3)
    path2.lineTo(r.right()-2, r.bottom()-2)
    path2.quadTo(cx+5, r.bottom()-4, cx, r.bottom()-2)
    p.drawPath(path2)

def _draw_templates(p, r, c):
    # Layout grid
    p.drawRect(r.x()+2, r.y()+2, r.width()-4, r.height()-4)
    p.drawLine(r.x()+2, r.y()+7, r.right()-2, r.y()+7)
    p.drawLine(r.x()+8, r.y()+7, r.x()+8, r.bottom()-2)

def _draw_analytics(p, r, c):
    # Bar chart
    bw = 3
    p.setBrush(c)
    p.drawRect(r.x()+3, r.y()+12, bw, 6)
    p.drawRect(r.x()+8, r.y()+6, bw, 12)
    p.drawRect(r.x()+13, r.y()+3, bw, 15)
    p.setBrush(Qt.NoBrush)

def _draw_branch_tree(p, r, c):
    cx = r.center().x()
    p.drawLine(cx-4, r.y()+3, cx-4, r.bottom()-3)
    p.drawEllipse(QPoint(cx-4, r.y()+3), 2, 2)
    p.drawEllipse(QPoint(cx-4, r.bottom()-3), 2, 2)
    p.drawEllipse(QPoint(cx+5, r.y()+8), 2, 2)
    path = QPainterPath()
    path.moveTo(cx+5, r.y()+10)
    path.quadTo(cx+5, r.bottom()-3, cx-4, r.bottom()-3)
    p.drawPath(path)

def _draw_schedules(p, r, c):
    # Clock
    cx, cy = r.center().x(), r.center().y()
    p.drawEllipse(QPoint(cx, cy), 8, 8)
    p.drawLine(cx, cy, cx, cy-5)
    p.drawLine(cx, cy, cx+4, cy+2)

def _draw_image_gen(p, r, c):
    # Image frame
    p.drawRect(r.x()+2, r.y()+2, r.width()-4, r.height()-4)
    # Sun
    p.drawEllipse(QPoint(r.x()+7, r.y()+7), 2, 2)
    # Mountain
    p.drawLine(r.x()+2, r.bottom()-4, r.x()+8, r.y()+10)
    p.drawLine(r.x()+8, r.y()+10, r.x()+12, r.y()+13)
    p.drawLine(r.x()+12, r.y()+13, r.x()+15, r.y()+10)
    p.drawLine(r.x()+15, r.y()+10, r.right()-2, r.bottom()-4)

def _draw_workflows(p, r, c):
    # Arrows cycling
    cx, cy = r.center().x(), r.center().y()
    p.drawArc(r.x()+3, r.y()+3, r.width()-6, r.height()-6, 30*16, 300*16)
    # Arrow head
    p.drawLine(r.x()+13, r.y()+3, r.x()+16, r.y()+5)
    p.drawLine(r.x()+16, r.y()+5, r.x()+13, r.y()+7)

def _draw_bookmarks(p, r, c):
    # Bookmark ribbon
    poly = QPolygon([
        QPoint(r.x()+4, r.y()+2),
        QPoint(r.right()-4, r.y()+2),
        QPoint(r.right()-4, r.bottom()-2),
        QPoint(r.center().x(), r.bottom()-6),
        QPoint(r.x()+4, r.bottom()-2),
    ])
    p.drawPolygon(poly)

def _draw_agent_forge(p, r, c):
    # Wrench
    p.drawLine(r.x()+4, r.bottom()-4, r.right()-6, r.y()+4)
    p.drawEllipse(QPoint(r.right()-5, r.y()+5), 4, 4)
    # Handle
    p.drawRect(r.x()+2, r.bottom()-6, 4, 4)

def _draw_marketplace(p, r, c):
    # Shopping bag
    p.drawRect(r.x()+4, r.y()+7, r.width()-8, r.height()-9)
    path = QPainterPath()
    path.moveTo(r.x()+7, r.y()+7)
    path.quadTo(r.x()+7, r.y()+2, r.center().x(), r.y()+2)
    path.quadTo(r.right()-7, r.y()+2, r.right()-7, r.y()+7)
    p.drawPath(path)

def _draw_delegative(p, r, c):
    # Kanban board (3 columns)
    p.drawRect(r.x()+2, r.y()+2, r.width()-4, r.height()-4)
    third = (r.width()-4) // 3
    p.drawLine(r.x()+2+third, r.y()+2, r.x()+2+third, r.bottom()-2)
    p.drawLine(r.x()+2+2*third, r.y()+2, r.x()+2+2*third, r.bottom()-2)
    # Cards
    p.setBrush(c)
    p.drawRect(r.x()+4, r.y()+5, third-3, 3)
    p.drawRect(r.x()+4, r.y()+10, third-3, 3)
    p.drawRect(r.x()+4+third, r.y()+5, third-3, 3)
    p.drawRect(r.x()+4+2*third, r.y()+5, third-3, 3)
    p.drawRect(r.x()+4+2*third, r.y()+10, third-3, 3)
    p.drawRect(r.x()+4+2*third, r.y()+15, third-3, 3)
    p.setBrush(Qt.NoBrush)

def _draw_fine_tuning(p, r, c):
    # Sliders
    for i, (x, knob_y) in enumerate([(r.x()+5, 8), (r.center().x(), 13), (r.right()-5, 6)]):
        p.drawLine(x, r.y()+3, x, r.bottom()-3)
        p.setBrush(c)
        p.drawEllipse(QPoint(x, r.y()+knob_y), 2, 2)
        p.setBrush(Qt.NoBrush)

def _draw_debugger(p, r, c):
    # Bug
    cx, cy = r.center().x(), r.center().y()
    p.drawEllipse(QPoint(cx, cy-3), 3, 2)  # Head
    p.drawEllipse(QPoint(cx, cy+3), 5, 5)  # Body
    # Legs
    for dy in [-1, 2, 5]:
        p.drawLine(cx-5, cy+dy, cx-8, cy+dy-2)
        p.drawLine(cx+5, cy+dy, cx+8, cy+dy-2)
    # Antennae
    p.drawLine(cx-2, cy-5, cx-4, cy-8)
    p.drawLine(cx+2, cy-5, cx+4, cy-8)

def _draw_testing(p, r, c):
    # Flask/beaker
    p.drawLine(r.x()+7, r.y()+2, r.x()+13, r.y()+2)
    p.drawLine(r.x()+8, r.y()+2, r.x()+8, r.y()+8)
    p.drawLine(r.x()+12, r.y()+2, r.x()+12, r.y()+8)
    p.drawLine(r.x()+8, r.y()+8, r.x()+4, r.bottom()-3)
    p.drawLine(r.x()+12, r.y()+8, r.x()+16, r.bottom()-3)
    p.drawLine(r.x()+4, r.bottom()-3, r.x()+16, r.bottom()-3)

def _draw_tasks(p, r, c):
    # Play triangle
    poly = QPolygon([
        QPoint(r.x()+6, r.y()+3),
        QPoint(r.right()-4, r.center().y()),
        QPoint(r.x()+6, r.bottom()-3),
    ])
    p.drawPolygon(poly)

def _draw_repl(p, r, c):
    # Terminal prompt
    p.drawLine(r.x()+4, r.y()+6, r.x()+9, r.center().y())
    p.drawLine(r.x()+9, r.center().y(), r.x()+4, r.bottom()-6)
    p.drawLine(r.x()+11, r.bottom()-5, r.right()-4, r.bottom()-5)

def _draw_memory(p, r, c):
    cx, cy = r.center().x(), r.center().y()
    p.drawEllipse(QPoint(cx-4, cy-4), 3, 3)
    p.drawEllipse(QPoint(cx+4, cy-4), 3, 3)
    p.drawEllipse(QPoint(cx, cy+5), 3, 3)
    p.drawLine(cx-4, cy-1, cx+4, cy-1)
    p.drawLine(cx-2, cy+2, cx+2, cy+2)

def _draw_extensions(p, r, c):
    # Puzzle piece
    s = 4
    cx, cy = r.center().x(), r.center().y()
    # Main body
    p.drawRect(r.x()+3, r.y()+3, r.width()-6, r.height()-6)
    # Top nub
    p.setBrush(c)
    p.drawEllipse(QPoint(cx, r.y()+3), s//2, s//2)
    # Right nub
    p.drawEllipse(QPoint(r.right()-3, cy), s//2, s//2)
    p.setBrush(Qt.NoBrush)

def _draw_docker(p, r, c):
    p.drawRect(r.x()+4, r.y()+6, 6, 5)
    p.drawRect(r.x()+11, r.y()+6, 6, 5)
    p.drawRect(r.x()+4, r.y()+12, 6, 5)
    p.drawRect(r.x()+11, r.y()+12, 6, 5)

def _draw_problems(p, r, c):
    p.drawEllipse(QPoint(r.center().x()-4, r.center().y()-2), 3, 3)
    p.drawLine(r.center().x()-1, r.center().y()+2, r.center().x()-1, r.bottom()-4)
    p.drawLine(r.center().x()-1, r.bottom()-4, r.center().x()-4, r.bottom()-4)
    p.drawLine(r.center().x()-1, r.bottom()-4, r.center().x()+2, r.bottom()-4)

def _draw_settings(p, r, c):
    cx, cy = r.center().x(), r.center().y()
    p.drawEllipse(QPoint(cx, cy), 3, 3)
    # Gear teeth
    import math
    for i in range(6):
        angle = i * 60 * math.pi / 180
        x1 = cx + int(5 * math.cos(angle))
        y1 = cy + int(5 * math.sin(angle))
        x2 = cx + int(8 * math.cos(angle))
        y2 = cy + int(8 * math.sin(angle))
        pen = p.pen()
        pen.setWidthF(2.5)
        p.setPen(pen)
        p.drawLine(x1, y1, x2, y2)
        pen.setWidthF(1.5)
        p.setPen(pen)


# Map names to draw functions
DRAW_FNS = {
    "explorer": _draw_explorer, "chat": _draw_chat, "models": _draw_models,
    "problems": _draw_problems, "docker": _draw_docker,
    "plan": _draw_plan, "git": _draw_git, "knowledge": _draw_knowledge,
    "memory": _draw_memory,
    "templates": _draw_templates, "analytics": _draw_analytics,
    "branch_tree": _draw_branch_tree, "schedules": _draw_schedules,
    "image_gen": _draw_image_gen, "workflows": _draw_workflows,
    "bookmarks": _draw_bookmarks, "agent_forge": _draw_agent_forge,
    "marketplace": _draw_marketplace, "delegative": _draw_delegative,
    "fine_tuning": _draw_fine_tuning, "debugger": _draw_debugger,
    "testing": _draw_testing, "tasks": _draw_tasks, "repl": _draw_repl,
    "extensions": _draw_extensions, "settings": _draw_settings,
}

ICON_MAP = {
    0: "explorer", 1: "chat", 2: "models", 3: "plan", 4: "git",
    5: "knowledge", 6: "templates", 7: "analytics", 8: "branch_tree",
    9: "schedules", 10: "image_gen", 11: "workflows", 12: "bookmarks",
    13: "agent_forge", 14: "marketplace", 15: "delegative",
    16: "fine_tuning", 17: "debugger", 18: "testing", 19: "tasks",
    20: "memory", 21: "docker", 22: "repl", 23: "extensions", 24: "problems",
}

TOOLTIP_MAP = {
    0: "Explorer", 1: "Chat", 2: "Models", 3: "Plan", 4: "Git",
    5: "Knowledge", 6: "Templates", 7: "Analytics", 8: "Branch Tree",
    9: "Schedules", 10: "Image Generation", 11: "Workflows", 12: "Bookmarks",
    13: "Agent Forge", 14: "Marketplace", 15: "Delegative Board",
    16: "Fine-tuning Studio", 17: "Debugger", 18: "Testing", 19: "Tasks",
    20: "Episodic Memory", 21: "Docker", 22: "REPL", 23: "Extensions", 24: "Problems",
}


def _make_icon(name, color, size=22):
    fn = DRAW_FNS.get(name)
    if not fn:
        px = QPixmap(size, size)
        px.fill(Qt.transparent)
        return QIcon(px)
    return _draw_icon(fn, color, size)


class ActivityBar(QWidget):
    activity_changed = pyqtSignal(int)
    settings_requested = pyqtSignal()

    BUTTON_SIZE = 48
    ICON_SIZE = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(52)
        self.setStyleSheet("background-color: #333333; border-right: 1px solid #1e1e1e;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(1)

        self.buttons = []
        self._button_indices = []
        self._fg = "#858585"
        self._accent = "#ffffff"

        for index in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]:
            name = ICON_MAP.get(index, "explorer")
            tooltip = TOOLTIP_MAP.get(index, name)
            self._add_action(name, index, tooltip)

        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.spacer)

        self.settings_btn = QPushButton()
        self.settings_btn.setIcon(_make_icon("settings", self._fg, self.ICON_SIZE))
        self.settings_btn.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        self.settings_btn.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.setStyleSheet(self._btn_style())
        self.settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_btn, alignment=Qt.AlignHCenter)

    def add_activity(self, icon, index, tooltip):
        count = self.layout().count()
        btn = self._add_action(icon if icon in DRAW_FNS else "explorer", index, tooltip)
        self.layout().removeWidget(btn)
        self.layout().insertWidget(count - 2, btn)
        return btn

    def _add_action(self, icon_name, index, tooltip):
        btn = QPushButton()
        btn.setIcon(_make_icon(icon_name, self._fg, self.ICON_SIZE))
        btn.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        btn.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setProperty("icon_name", icon_name)
        btn.setStyleSheet(self._btn_style())
        btn.clicked.connect(lambda: self._on_btn_clicked(index))
        self.layout().addWidget(btn, alignment=Qt.AlignHCenter)
        self.buttons.append(btn)
        self._button_indices.append(index)
        return btn

    def _btn_style(self):
        return (
            f"QPushButton {{ background: transparent; border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.08); }}"
            f"QPushButton:checked {{ background: rgba(255,255,255,0.12); border-left: 3px solid {self._accent}; }}"
        )

    def _on_btn_clicked(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(self._button_indices[i] == index)
        self.activity_changed.emit(index)
        self._recolor_icons()

    def _recolor_icons(self):
        for btn in self.buttons:
            icon_name = btn.property("icon_name")
            if icon_name:
                color = self._accent if btn.isChecked() else self._fg
                btn.setIcon(_make_icon(icon_name, color, self.ICON_SIZE))

    def apply_theme(self, theme):
        bg = theme.get("sidebar_bg", "#333333")
        border = theme.get("border", "#1e1e1e")
        self._accent = theme.get("accent", "#ffffff")
        self._fg = theme.get("fg", "#858585")
        self.setStyleSheet(
            f"background-color: {bg}; border-right: 1px solid {border};"
            f" QToolTip {{ background-color: {bg}; color: {self._accent}; border: 1px solid {border}; padding: 4px; }}"
        )
        style = self._btn_style()
        for btn in self.buttons:
            btn.setStyleSheet(style)
        self.settings_btn.setStyleSheet(style)
        self._recolor_icons()
        self.settings_btn.setIcon(_make_icon("settings", self._fg, self.ICON_SIZE))
