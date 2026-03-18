from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSizePolicy
from PyQt5.QtCore import Qt, pyqtSignal


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

        self._add_action("\u2630", 0, "Explorer")       # ☰ hamburger
        self._add_action("\u2709", 1, "Chat")            # ✉ envelope
        self._add_action("\u2b07", 2, "Models")          # ⬇ down arrow
        self._add_action("\u2611", 3, "Plan")            # ☑ ballot box
        self._add_action("\u2756", 4, "Git")             # ❖ diamond
        self._add_action("\u2605", 5, "Knowledge")       # ★ star
        self._add_action("\u270f", 6, "Templates")       # ✏ pencil
        self._add_action("\u2261", 7, "Analytics")       # ≡ triple bar
        self._add_action("\u2387", 8, "Branch Tree")     # ⎇ branch
        self._add_action("\u23f0", 9, "Schedules")       # ⏰ alarm clock
        self._add_action("\u25d0", 10, "Image Generation") # ◐ circle half
        self._add_action("\u21c4", 11, "Workflows")      # ⇄ arrows
        self._add_action("\u2661", 12, "Bookmarks")      # ♡ heart
        self._add_action("\u2692", 13, "Agent Forge")    # ⚒ hammer+pick
        self._add_action("\u2302", 14, "Marketplace")    # ⌂ house
        self._add_action("\u2637", 15, "Delegative Board") # ☷ trigram
        self._add_action("\u2318", 16, "Fine-tuning Studio") # ⌘ command/tuning
        self._add_action("\u2620", 17, "Debugger")       # ☠ skull (bug hunting)
        self._add_action("\u2714", 18, "Testing")        # ✔ check mark
        self._add_action("\u25b6", 19, "Tasks")          # ▶ play
        self._add_action("\u2588", 22, "REPL")           # █ terminal block
        self._add_action("\u2B29", 23, "Extensions")     # ⬩ small diamond

        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.spacer)

        settings_btn = QPushButton("\u2699")
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
        # Insert before the spacer
        count = self.layout().count()
        btn = self._add_action(icon, index, tooltip)
        # Move it to the position before spacer (count - 2)
        # Actually _add_action adds to the end, which is after settings_btn.
        # We need to insert it correctly.
        self.layout().removeWidget(btn)
        self.layout().insertWidget(count - 2, btn)
        return btn

    def _add_action(self, icon, index, tooltip):
        btn = QPushButton(icon)
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

        if index == 1:
            btn.setChecked(True)

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
