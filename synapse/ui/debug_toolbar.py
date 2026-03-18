from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QToolBar, QAction
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

class DebugToolbar(QToolBar):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    step_over_requested = pyqtSignal()
    step_into_requested = pyqtSignal()
    step_out_requested = pyqtSignal()
    continue_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Debug")
        self.setMovable(False)
        self.setFloatable(False)
        self.setOrientation(Qt.Horizontal)
        self.setIconSize(parent.iconSize() if parent else (24, 24))

        # Use UTF-8 characters if icons aren't available
        self.start_action = self.addAction("\u25b6", self.start_requested.emit)
        self.start_action.setToolTip("Start Debugging (F5)")
        
        self.continue_action = self.addAction("\u25b6", self.continue_requested.emit)
        self.continue_action.setToolTip("Continue (F5)")
        self.continue_action.setVisible(False)

        self.pause_action = self.addAction("\u23f8", self.pause_requested.emit)
        self.pause_action.setToolTip("Pause")
        self.pause_action.setVisible(False)

        self.addSeparator()

        self.step_over_action = self.addAction("\u2935", self.step_over_requested.emit)
        self.step_over_action.setToolTip("Step Over (F10)")

        self.step_into_action = self.addAction("\u21e2", self.step_into_requested.emit)
        self.step_into_action.setToolTip("Step Into (F11)")

        self.step_out_action = self.addAction("\u21e0", self.step_out_requested.emit)
        self.step_out_action.setToolTip("Step Out (Shift+F11)")

        self.addSeparator()

        self.stop_action = self.addAction("\u23f9", self.stop_requested.emit)
        self.stop_action.setToolTip("Stop Debugging (Shift+F5)")
        
        self.setEnabled(True)
        self._set_session_active(False)

    def _set_session_active(self, active):
        self.start_action.setVisible(not active)
        self.continue_action.setVisible(active)
        self.pause_action.setVisible(active)
        self.step_over_action.setEnabled(active)
        self.step_into_action.setEnabled(active)
        self.step_out_action.setEnabled(active)
        self.stop_action.setEnabled(active)
