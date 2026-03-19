"""Branch dropdown selector and New Branch button."""
import logging
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QComboBox, QPushButton, QMessageBox
)
from PyQt5.QtCore import pyqtSignal

log = logging.getLogger(__name__)


class BranchNavigator(QWidget):
    branch_changed = pyqtSignal(str)
    new_branch_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.combo = QComboBox()
        self.combo.setMinimumWidth(120)
        self.combo.setStyleSheet(
            "QComboBox { background: #2d2d2d; color: #ccc; border: 1px solid #444; "
            "border-radius: 4px; padding: 4px 8px; font-size: 11px; }"
        )
        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        layout.addWidget(self.combo)

        self.new_btn = QPushButton("New Branch")
        self.new_btn.setStyleSheet(
            "QPushButton { background: #333; color: #ccc; padding: 4px 10px; "
            "border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { background: #444; }"
        )
        self.new_btn.clicked.connect(self._on_new_branch)
        layout.addWidget(self.new_btn)

        self._conv = None
        self._block_signal = False

    def set_conversation(self, conv):
        self._conv = conv
        self._block_signal = True
        self.combo.clear()
        if not conv:
            self._block_signal = False
            return
        branches = conv.get("branches", {"main": {"name": "Main"}})
        current = conv.get("current_branch", "main")
        for bid, b in branches.items():
            self.combo.addItem(b.get("name", bid), bid)
        idx = self.combo.findData(current)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        self._block_signal = False

    def _on_combo_changed(self, idx):
        if self._block_signal or idx < 0 or not self._conv:
            return
        bid = self.combo.itemData(idx)
        if bid and bid != self._conv.get("current_branch"):
            self.branch_changed.emit(bid)

    def _on_new_branch(self):
        if not self._conv:
            return
        from PyQt5.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "New Branch", "Branch name:", text="Branch")
        if ok and name.strip():
            self.new_branch_requested.emit(name.strip())
