import logging
import webbrowser
from typing import List, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QTabWidget, QTextEdit, QMenu, QAction,
    QHBoxLayout
)
from PyQt5.QtCore import Qt, pyqtSignal

log = logging.getLogger(__name__)

class DockerSidebar(QWidget):
    start_requested = pyqtSignal(str)
    stop_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str)
    view_logs_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Error state (shown when Docker not found)
        self.error_widget = QWidget()
        error_layout = QVBoxLayout(self.error_widget)
        error_layout.setContentsMargins(20, 40, 20, 20)
        self.error_icon = QLabel("Docker Not Found")
        self.error_icon.setAlignment(Qt.AlignCenter)
        self.error_icon.setStyleSheet("font-size: 16px; font-weight: bold;")
        error_layout.addWidget(self.error_icon)
        self.error_msg = QLabel("Docker CLI is not installed or not in PATH.")
        self.error_msg.setAlignment(Qt.AlignCenter)
        self.error_msg.setWordWrap(True)
        error_layout.addWidget(self.error_msg)
        error_layout.addSpacing(16)
        install_btn = QPushButton("Install Docker")
        install_btn.clicked.connect(lambda: webbrowser.open("https://docs.docker.com/get-docker/"))
        error_layout.addWidget(install_btn)
        retry_btn = QPushButton("Retry Detection")
        retry_btn.clicked.connect(self.refresh_requested.emit)
        error_layout.addWidget(retry_btn)
        error_layout.addStretch()
        self.error_widget.hide()
        layout.addWidget(self.error_widget)

        self.tabs = QTabWidget()

        # Containers
        self.container_tree = QTreeWidget()
        self.container_tree.setHeaderLabels(["Name", "Status", "ID"])
        self.container_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.container_tree.customContextMenuRequested.connect(self._show_container_menu)
        self.tabs.addTab(self.container_tree, "Containers")

        # Images
        self.image_tree = QTreeWidget()
        self.image_tree.setHeaderLabels(["Repository", "Tag", "ID"])
        self.tabs.addTab(self.image_tree, "Images")

        # Volumes
        self.volume_tree = QTreeWidget()
        self.volume_tree.setHeaderLabels(["Driver", "Name"])
        self.tabs.addTab(self.volume_tree, "Volumes")

        # Logs
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.tabs.addTab(self.log_view, "Logs")

        layout.addWidget(self.tabs)

        # Controls
        controls = QWidget()
        controls_layout = QVBoxLayout(controls)
        self.refresh_btn = QPushButton("Refresh All")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        controls_layout.addWidget(self.refresh_btn)
        layout.addWidget(controls)

    def show_error(self, message):
        self.error_msg.setText(message)
        self.error_widget.show()
        self.tabs.hide()
        self.refresh_btn.parentWidget().hide()

    def hide_error(self):
        self.error_widget.hide()
        self.tabs.show()
        self.refresh_btn.parentWidget().show()

    def update_containers(self, containers: List[Dict[str, Any]]):
        self.hide_error()
        self.container_tree.clear()
        for c in containers:
            item = QTreeWidgetItem(self.container_tree, [
                c.get("Names", "N/A"),
                c.get("Status", "N/A"),
                c.get("ID", "N/A")
            ])
            item.setData(0, Qt.UserRole, c)

    def update_images(self, images: List[Dict[str, Any]]):
        self.image_tree.clear()
        for img in images:
            item = QTreeWidgetItem(self.image_tree, [
                img.get("Repository", "N/A"),
                img.get("Tag", "N/A"),
                img.get("ID", "N/A")
            ])

    def update_volumes(self, volumes: List[Dict[str, Any]]):
        self.volume_tree.clear()
        for v in volumes:
            item = QTreeWidgetItem(self.volume_tree, [
                v.get("Driver", "N/A"),
                v.get("Name", "N/A")
            ])

    def append_logs(self, container_id: str, logs: str):
        self.log_view.clear()
        self.log_view.setPlainText(logs)
        self.tabs.setCurrentWidget(self.log_view)

    def _show_container_menu(self, pos):
        item = self.container_tree.itemAt(pos)
        if not item:
            return

        container = item.data(0, Qt.UserRole)
        cid = container.get("ID")
        status = container.get("Status", "").lower()

        menu = QMenu()
        if "up" in status:
            stop_action = menu.addAction("Stop")
            stop_action.triggered.connect(lambda: self.stop_requested.emit(cid))
        else:
            start_action = menu.addAction("Start")
            start_action.triggered.connect(lambda: self.start_requested.emit(cid))

        logs_action = menu.addAction("View Logs")
        logs_action.triggered.connect(lambda: self.view_logs_requested.emit(cid))

        remove_action = menu.addAction("Remove")
        remove_action.triggered.connect(lambda: self.remove_requested.emit(cid))

        menu.exec_(self.container_tree.viewport().mapToGlobal(pos))

    def apply_theme(self, theme):
        bg = theme.get("sidebar_bg", "#1e1e1e")
        fg = theme.get("fg", "#e6edf3")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#58a6ff")
        input_bg = theme.get("input_bg", "#1e1e1e")
        tree_style = f"QTreeWidget {{ background: {bg}; color: {fg}; border: none; }}"
        self.container_tree.setStyleSheet(tree_style)
        self.image_tree.setStyleSheet(tree_style)
        self.volume_tree.setStyleSheet(tree_style)
        self.log_view.setStyleSheet(f"font-family: 'Courier New'; background: {input_bg}; color: {fg};")
        self.error_icon.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {fg};")
        self.error_msg.setStyleSheet(f"color: {fg};")
        self.setStyleSheet(f"background-color: {bg};")
