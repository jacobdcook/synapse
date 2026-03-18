import logging
from typing import List, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QStyle, QProgressBar, QToolBar, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize

log = logging.getLogger(__name__)

class TaskRunnerSidebar(QWidget):
    run_task_requested = pyqtSignal(str)
    stop_task_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal()
    open_workspace_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.task_states = {}

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header/Toolbar
        toolbar = QToolBar()
        toolbar.setIconSize(QSize(20, 20))

        refresh_action = QAction("Refresh", self)
        refresh_action.setToolTip("Refresh Tasks")
        refresh_action.triggered.connect(self.refresh_requested.emit)
        toolbar.addAction(refresh_action)

        layout.addWidget(toolbar)

        # Empty state
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setContentsMargins(20, 40, 20, 20)
        self.empty_title = QLabel("No Tasks Detected")
        self.empty_title.setAlignment(Qt.AlignCenter)
        self.empty_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        empty_layout.addWidget(self.empty_title)
        self.empty_msg = QLabel(
            "Open a workspace with a Makefile, package.json, "
            "pyproject.toml, or Cargo.toml to see available tasks."
        )
        self.empty_msg.setAlignment(Qt.AlignCenter)
        self.empty_msg.setWordWrap(True)
        empty_layout.addWidget(self.empty_msg)
        empty_layout.addSpacing(16)
        open_ws_btn = QPushButton("Open Workspace")
        open_ws_btn.clicked.connect(self.open_workspace_requested.emit)
        empty_layout.addWidget(open_ws_btn)
        empty_layout.addStretch()
        layout.addWidget(self.empty_widget)

        # Task Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Task", "Status"])
        self.tree.setColumnWidth(0, 150)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.hide()
        layout.addWidget(self.tree)

        self.status_label = QLabel("No tasks running")
        self.status_label.setStyleSheet("padding: 5px;")
        layout.addWidget(self.status_label)

    def update_tasks(self, tasks: List[Dict[str, Any]]):
        self.tree.clear()
        self.task_states = {}

        if not tasks:
            self.empty_widget.show()
            self.tree.hide()
            return

        self.empty_widget.hide()
        self.tree.show()

        groups = {}
        for task in tasks:
            group_name = task.get("type", "custom").upper()
            if group_name not in groups:
                groups[group_name] = QTreeWidgetItem(self.tree, [group_name])
                groups[group_name].setExpanded(True)

            item = QTreeWidgetItem(groups[group_name], [task.get("name", "Unnamed"), "Idle"])
            item.setData(0, Qt.UserRole, task.get("id"))
            self.task_states[task.get("id")] = {"item": item, "status": "Idle"}

    def set_task_status(self, task_id: str, status: str):
        if task_id in self.task_states:
            item = self.task_states[task_id]["item"]
            item.setText(1, status)
            if status == "Running":
                item.setForeground(1, Qt.green)
            elif status == "Failed":
                item.setForeground(1, Qt.red)
            else:
                item.setData(1, Qt.ForegroundRole, None)

            self.task_states[task_id]["status"] = status
            self._update_summary()

    def _on_item_double_clicked(self, item, column):
        task_id = item.data(0, Qt.UserRole)
        if task_id:
            if self.task_states.get(task_id, {}).get("status") == "Running":
                self.stop_task_requested.emit(task_id)
            else:
                self.run_task_requested.emit(task_id)

    def _update_summary(self):
        running = [tid for tid, state in self.task_states.items() if state["status"] == "Running"]
        if running:
            self.status_label.setText(f"Running: {len(running)} task(s)")
        else:
            self.status_label.setText("No tasks running")

    def apply_theme(self, theme):
        bg = theme.get("sidebar_bg", "#1e1e1e")
        fg = theme.get("fg", "#e6edf3")
        border = theme.get("border", "#30363d")
        self.setStyleSheet(f"background-color: {bg};")
        self.tree.setStyleSheet(
            f"QTreeWidget {{ background: {bg}; color: {fg}; border: none; }}"
            f"QHeaderView::section {{ background: {bg}; color: {fg}; border: 1px solid {border}; }}"
        )
        self.status_label.setStyleSheet(f"color: {fg}; padding: 5px;")
        self.empty_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {fg};")
        self.empty_msg.setStyleSheet(f"color: {fg};")
