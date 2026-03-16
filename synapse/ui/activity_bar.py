from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
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

        self._add_action("\u2630", 0, "Explorer")
        self._add_action("\u2709", 1, "Chat")
        self._add_action("\u2b07", 2, "Models")
        self._add_action("\U0001f4cb", 3, "Plan") # Clipboard icon
        self._add_action("\u2756", 4, "Git")
        self._add_action("\u26c4", 5, "Knowledge")
        self._add_action("\u270f", 6, "Templates") # Pencil icon
        self._add_action("\U0001f4ca", 7, "Analytics") # Bar chart icon
        self._add_action("\u22d4", 8, "Branch Tree")
        self._add_action("\U0001f552", 9, "Schedules")
        self._add_action("\U0001f3a8", 10, "Image Generation")

        layout.addStretch()

        settings_btn = QPushButton("\u2699")
        settings_btn.setFixedSize(48, 48)
        settings_btn.setToolTip("Settings")
        settings_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; font-size: 20px; color: #858585; }"
            "QPushButton:hover { color: #ffffff; }"
        )
        settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(settings_btn)

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

        if index == 1:
            btn.setChecked(True)

    def _on_btn_clicked(self, index):
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        self.activity_changed.emit(index)
