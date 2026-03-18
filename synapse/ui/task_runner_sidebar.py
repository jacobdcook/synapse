import logging
from typing import List, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QStyle, QProgressBar, QToolBar, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal

log = logging.getLogger(__name__)

class TaskRunnerSidebar(QWidget):
    run_task_requested = pyqtSignal(str) # task_id
    stop_task_requested = pyqtSignal(str) # task_id
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.task_states = {} # task_id -> {item, status}

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header/Toolbar
        toolbar = QToolBar()
        from PyQt5.QtCore import QSize
        toolbar.setIconSize(QSize(20, 20))
        
        refresh_action = QAction("🔄", self)
        refresh_action.setToolTip("Refresh Tasks")
        refresh_action.triggered.connect(self.refresh_requested.emit)
        toolbar.addAction(refresh_action)
        
        layout.addWidget(toolbar)

        # Task Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Task", "Status"])
        self.tree.setColumnWidth(0, 150)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        # History/Recent area (Placeholder for now)
        self.status_label = QLabel("No tasks running")
        self.status_label.setStyleSheet("color: #8b949e; padding: 5px;")
        layout.addWidget(self.status_label)

    def update_tasks(self, tasks: List[Dict[str, Any]]):
        self.tree.clear()
        self.task_states = {}
        
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
        self.tree.setStyleSheet(f"""
            QTreeWidget {{ background: {bg}; color: {fg}; border: none; }}
            QHeaderView::section {{ background: {bg}; color: {fg}; border: 1px solid {border}; }}
        """)
