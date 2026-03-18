import logging
from typing import List, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QStyle, QToolBar, QAction, QTabWidget
)
from PyQt5.QtCore import Qt, pyqtSignal

log = logging.getLogger(__name__)

class PullRequestSidebar(QWidget):
    pr_selected = pyqtSignal(dict)
    issue_selected = pyqtSignal(dict)
    refresh_requested = pyqtSignal()
    checkout_requested = pyqtSignal(str) # branch/pr_number

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QToolBar()
        refresh_action = QAction("🔄", self)
        refresh_action.setToolTip("Refresh PRs & Issues")
        refresh_action.triggered.connect(self.refresh_requested.emit)
        toolbar.addAction(refresh_action)
        layout.addWidget(toolbar)

        # Tabs for PRs and Issues
        self.tabs = QTabWidget()
        
        # PR Tree
        self.pr_tree = QTreeWidget()
        self.pr_tree.setHeaderLabels(["#", "Title", "Author"])
        self.pr_tree.setColumnWidth(0, 50)
        self.pr_tree.setColumnWidth(1, 150)
        self.pr_tree.itemDoubleClicked.connect(self._on_pr_double_clicked)
        self.tabs.addTab(self.pr_tree, "Pull Requests")

        # Issue Tree
        self.issue_tree = QTreeWidget()
        self.issue_tree.setHeaderLabels(["#", "Title", "Author"])
        self.issue_tree.setColumnWidth(0, 50)
        self.issue_tree.setColumnWidth(1, 150)
        self.tabs.addTab(self.issue_tree, "Issues")

        layout.addWidget(self.tabs)

        # Summary
        self.status_label = QLabel("No remote data")
        self.status_label.setStyleSheet("color: #8b949e; padding: 5px;")
        layout.addWidget(self.status_label)

    def set_prs(self, prs: List[Dict[str, Any]]):
        self.pr_tree.clear()
        for pr in prs:
            item = QTreeWidgetItem(self.pr_tree, [
                str(pr.get("number")),
                pr.get("title"),
                pr.get("author")
            ])
            item.setData(0, Qt.UserRole, pr)
        self.status_label.setText(f"Found {len(prs)} PRs")

    def set_issues(self, issues: List[Dict[str, Any]]):
        self.issue_tree.clear()
        for issue in issues:
            item = QTreeWidgetItem(self.issue_tree, [
                str(issue.get("number")),
                issue.get("title"),
                issue.get("author")
            ])
            item.setData(0, Qt.UserRole, issue)

    def _on_pr_double_clicked(self, item, column):
        pr_data = item.data(0, Qt.UserRole)
        if pr_data:
            self.pr_selected.emit(pr_data)

    def apply_theme(self, theme):
        bg = theme.get("sidebar_bg", "#1e1e1e")
        fg = theme.get("fg", "#e6edf3")
        border = theme.get("border", "#30363d")
        self.pr_tree.setStyleSheet(f"QTreeWidget {{ background: {bg}; color: {fg}; border: none; }}")
        self.issue_tree.setStyleSheet(f"QTreeWidget {{ background: {bg}; color: {fg}; border: none; }}")
        self.tabs.setStyleSheet(f"QTabWidget::pane {{ border: 1px solid {border}; }}")
