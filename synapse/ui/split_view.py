import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
    QComboBox, QLabel, QPushButton, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEngineView

from .chat_page import ChatPage

log = logging.getLogger(__name__)

class ChatPane(QWidget):
    """A single chat panel within the SplitView."""
    action_requested = pyqtSignal(str, object) # action, index/data
    model_changed = pyqtSignal(str)
    voted = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Header for model selection
        self.header = QWidget()
        self.header.setObjectName("paneHeader")
        self.header.setStyleSheet("""
            #paneHeader { background: #252526; border-bottom: 1px solid #333; }
        """)
        h_layout = QHBoxLayout(self.header)
        h_layout.setContentsMargins(8, 4, 8, 4)

        self.model_combo = QComboBox()
        self.model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.model_combo.currentTextChanged.connect(self.model_changed.emit)
        h_layout.addWidget(self.model_combo)

        self.best_btn = QPushButton("\u2605 Best") # Star icon
        self.best_btn.setCheckable(True)
        self.best_btn.setFixedSize(60, 24)
        self.best_btn.setStyleSheet("""
            QPushButton { background: #2d2d2d; color: #888; border-radius: 4px; font-size: 11px; }
            QPushButton:checked { background: #264f78; color: #4fc3f7; }
        """)
        self.best_btn.clicked.connect(lambda: self.voted.emit(0)) # Emit generic vote signal
        h_layout.addWidget(self.best_btn)

        self.layout.addWidget(self.header)

        # Web view with ChatPage for action:// link interception
        self.view = QWebEngineView()
        self._page = ChatPage(self.view)
        self._page.action_requested.connect(self.action_requested.emit)
        self.view.setPage(self._page)
        self.layout.addWidget(self.view)

    def set_models(self, models, current=None):
        self.model_combo.clear()
        self.model_combo.addItems(models)
        if current:
            self.model_combo.setCurrentText(current)

class SplitViewWidget(QSplitter):
    """Manages multiple ChatPanes in a split layout."""
    action_requested = pyqtSignal(int, str, object) # pane_index, action, msg_index/data
    voted = pyqtSignal(int, int) # pane_index, msg_index

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setHandleWidth(2)
        self.panes = []
        self._available_models = []

    def set_available_models(self, models):
        self._available_models = models

    def set_panes(self, model_list):
        # Clear existing
        for p in self.panes:
            p.setParent(None)
            p.deleteLater()
        self.panes = []
        
        # Add new
        for m in model_list:
            self.add_pane(self._available_models, m)

    def add_pane(self, models, current_model=None):
        if len(self.panes) >= 4:
            return
        
        pane = ChatPane(self)
        pane.set_models(models, current_model)
        idx = len(self.panes)
        pane.action_requested.connect(lambda a, i, p=idx: self.action_requested.emit(p, a, i))
        pane.voted.connect(lambda i, p=idx: self.voted.emit(p, i))
        
        self.addWidget(pane)
        self.panes.append(pane)
        return pane

    def remove_pane(self, index):
        if len(self.panes) <= 1:
            return
        pane = self.panes.pop(index)
        pane.deleteLater()

    def get_pane(self, index):
        if 0 <= index < len(self.panes):
            return self.panes[index]
        return None
