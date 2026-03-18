from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QFontDatabase


def _emoji_font(size=18):
    """Build a font that can render emoji on any platform."""
    candidates = [
        "Noto Color Emoji",
        "Segoe UI Emoji",      # Windows
        "Apple Color Emoji",   # macOS
        "Symbola",
        "Noto Emoji",
    ]
    for name in candidates:
        fid = QFontDatabase().font(name, "", size)
        if fid.family().lower().replace(" ", "") != "":
            f = QFont(name, size)
            f.setStyleStrategy(QFont.PreferAntialias)
            return f
    return QFont("Sans", size)


class ActivityBar(QWidget):
    activity_changed = pyqtSignal(int)
    settings_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(48)
        self.setStyleSheet("background-color: #333333; border-right: 1px solid #1e1e1e;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(4)

        self.buttons = []
        self._icon_font = _emoji_font(18)

        self._add_action("\U0001f4c2", 0, "Explorer")          # 📂 folder
        self._add_action("\U0001f4ac", 1, "Chat")              # 💬 speech bubble
        self._add_action("\U0001f916", 2, "Models")            # 🤖 robot
        self._add_action("\U0001f4cb", 3, "Plan")              # 📋 clipboard
        self._add_action("\U0001f500", 4, "Git")               # 🔀 merge arrows
        self._add_action("\U0001f9e0", 5, "Knowledge")         # 🧠 brain
        self._add_action("\U0001f4dd", 6, "Templates")         # 📝 memo
        self._add_action("\U0001f4ca", 7, "Analytics")         # 📊 bar chart
        self._add_action("\U0001f333", 8, "Branch Tree")       # 🌳 tree
        self._add_action("\u23f0", 9, "Schedules")             # ⏰ alarm clock
        self._add_action("\U0001f3a8", 10, "Image Generation") # 🎨 palette
        self._add_action("\U0001f504", 11, "Workflows")        # 🔄 cycle arrows
        self._add_action("\U0001f516", 12, "Bookmarks")        # 🔖 bookmark
        self._add_action("\u2692\uFE0F", 13, "Agent Forge")    # ⚒️ hammer+pick
        self._add_action("\U0001f6d2", 14, "Marketplace")      # 🛒 shopping cart
        self._add_action("\U0001f4cc", 15, "Delegative Board") # 📌 pushpin
        self._add_action("\U0001f3af", 16, "Fine-tuning Studio") # 🎯 bullseye
        self._add_action("\U0001f41e", 17, "Debugger")         # 🐞 ladybug
        self._add_action("\u2705", 18, "Testing")              # ✅ check box
        self._add_action("\u25b6\uFE0F", 19, "Tasks")          # ▶️ play button
        self._add_action("\U0001f4bb", 22, "REPL")             # 💻 laptop
        self._add_action("\U0001f9e9", 23, "Extensions")       # 🧩 puzzle piece

        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.spacer)

        settings_btn = QPushButton("\u2699\uFE0F")  # ⚙️
        settings_btn.setFont(self._icon_font)
        settings_btn.setFixedSize(48, 48)
        settings_btn.setToolTip("Settings")
        settings_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 20px; color: #858585; }"
            "QPushButton:hover { color: #ffffff; }"
        )
        settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(settings_btn)

    def add_activity(self, icon, index, tooltip):
        """Public API for adding new activities dynamically (e.g., from plugins)."""
        count = self.layout().count()
        btn = self._add_action(icon, index, tooltip)
        self.layout().removeWidget(btn)
        self.layout().insertWidget(count - 2, btn)
        return btn

    def _add_action(self, icon, index, tooltip):
        btn = QPushButton(icon)
        btn.setFont(self._icon_font)
        btn.setFixedSize(48, 48)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 20px; color: #858585; }"
            "QPushButton:hover { color: #ffffff; }"
            "QPushButton:checked { color: #ffffff; border-left: 2px solid #ffffff; }"
        )
        btn.clicked.connect(lambda: self._on_btn_clicked(index))
        self.layout().addWidget(btn)
        self.buttons.append(btn)
        return btn

    def _on_btn_clicked(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.activity_changed.emit(index)

    def apply_theme(self, theme):
        bg = theme.get("sidebar_bg", "#333333")
        border = theme.get("border", "#1e1e1e")
        accent = theme.get("accent", "#ffffff")
        fg = theme.get("fg", "#858585")
        self.setStyleSheet(
            f"background-color: {bg}; border-right: 1px solid {border};"
            f" QToolTip {{ background-color: {bg}; color: {accent}; border: 1px solid {border}; padding: 4px; }}"
        )
        btn_style = (
            f"QPushButton {{ background: transparent; border: none; font-size: 20px; color: {fg}; }}"
            f"QPushButton:hover {{ color: {accent}; }}"
            f"QPushButton:checked {{ color: {accent}; border-left: 2px solid {accent}; }}"
        )
        for btn in self.buttons:
            btn.setStyleSheet(btn_style)
        settings_btn = self.layout().itemAt(self.layout().count() - 1).widget()
        if settings_btn:
            settings_btn.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; font-size: 20px; color: {fg}; }}"
                f"QPushButton:hover {{ color: {accent}; }}"
            )
