"""Problems panel: list LSP diagnostics, filter by severity, click to jump."""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QComboBox, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

log = logging.getLogger(__name__)

SEVERITY_LABELS = {1: "Error", 2: "Warning", 3: "Info", 4: "Hint"}
SEVERITY_COLORS = {1: "#f44336", 2: "#ff9800", 3: "#2196f3", 4: "#8b949e"}


class ProblemsPanel(QWidget):
    jump_requested = pyqtSignal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._diagnostics = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        header = QHBoxLayout()
        header.addWidget(QLabel("Problems"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Errors", "Warnings", "Info"])
        self.filter_combo.currentTextChanged.connect(self._refresh_list)
        header.addWidget(self.filter_combo)
        header.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear)
        header.addWidget(clear_btn)
        layout.addLayout(header)
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.setStyleSheet(
            "QListWidget { background: #1e1e1e; color: #e6edf3; border: 1px solid #333; }"
        )
        layout.addWidget(self.list_widget)

    def set_diagnostics(self, uri_to_diagnostics):
        self._diagnostics = dict(uri_to_diagnostics or {})
        self._refresh_list()

    def add_diagnostics(self, uri, diagnostics):
        self._diagnostics[uri] = list(diagnostics or [])
        self._refresh_list()

    def _refresh_list(self):
        self.list_widget.clear()
        filt = self.filter_combo.currentText()
        for uri, diags in self._diagnostics.items():
            path = uri.replace("file://", "")
            if path.startswith("//"):
                path = path[2:]
            for d in diags:
                sev = d.get("severity", 1)
                if filt == "Errors" and sev != 1:
                    continue
                if filt == "Warnings" and sev != 2:
                    continue
                if filt == "Info" and sev < 3:
                    continue
                msg = d.get("message", "")
                r = d.get("range", {})
                line = r.get("start", {}).get("line", 0) + 1
                col = r.get("start", {}).get("character", 0) + 1
                label = f"{path}:{line}:{col} [{SEVERITY_LABELS.get(sev, '?')}] {msg}"
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, (path, line, col))
                item.setForeground(QColor(SEVERITY_COLORS.get(sev, "#8b949e")))
                self.list_widget.addItem(item)

    def _on_item_clicked(self, item):
        path, line, col = item.data(Qt.UserRole)
        self.jump_requested.emit(path, line, col)

    def _on_clear(self):
        self._diagnostics.clear()
        self._refresh_list()
