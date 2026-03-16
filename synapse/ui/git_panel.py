import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QPushButton, QPlainTextEdit, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from ..core.git import (
    is_git_repo, git_branch, git_status, git_diff,
    git_log, git_commit, GitStatusWorker
)

log = logging.getLogger(__name__)


class GitPanel(QWidget):
    status_changed = pyqtSignal(str, int)  # branch, changed_count

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workspace_dir = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel("Source Control")
        header.setStyleSheet("font-weight: bold; font-size: 13px; color: #e6edf3; padding: 4px;")
        layout.addWidget(header)

        self.branch_label = QLabel("No repository")
        self.branch_label.setStyleSheet("color: #8b949e; font-size: 11px; padding: 2px 4px;")
        layout.addWidget(self.branch_label)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_tree = QTreeWidget()
        self.status_tree.setHeaderHidden(True)
        self.status_tree.setStyleSheet("QTreeWidget { background: #1e1e1e; border: 1px solid #333; color: #e6edf3; }")
        self.status_tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.status_tree)

        self.diff_view = QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setMaximumHeight(200)
        self.diff_view.setStyleSheet(
            "background: #0d1117; color: #e6edf3; border: 1px solid #333; font-family: monospace; font-size: 11px;"
        )
        layout.addWidget(self.diff_view)

        commit_label = QLabel("Commit Message:")
        commit_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(commit_label)

        self.commit_input = QLineEdit()
        self.commit_input.setPlaceholderText("Enter commit message...")
        self.commit_input.setStyleSheet(
            "background: #161b22; color: #e6edf3; border: 1px solid #30363d; "
            "border-radius: 4px; padding: 4px;"
        )
        layout.addWidget(self.commit_input)

        commit_btn = QPushButton("Commit All")
        commit_btn.clicked.connect(self._do_commit)
        layout.addWidget(commit_btn)

        log_label = QLabel("Recent Commits:")
        log_label.setStyleSheet("color: #8b949e; font-size: 11px; padding-top: 4px;")
        layout.addWidget(log_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        self.log_view.setStyleSheet(
            "background: #0d1117; color: #e6edf3; border: 1px solid #333; font-family: monospace; font-size: 11px;"
        )
        layout.addWidget(self.log_view)

        layout.addStretch()

    def set_workspace(self, path):
        self._workspace_dir = path
        self.refresh()

    def refresh(self):
        if not self._workspace_dir or not is_git_repo(self._workspace_dir):
            self.branch_label.setText("Not a git repository")
            self.status_tree.clear()
            self.log_view.clear()
            self.diff_view.clear()
            return

        self._worker = GitStatusWorker(self._workspace_dir)
        self._worker.status_ready.connect(self._on_status_ready)
        self._worker.start()

        log_text = git_log(self._workspace_dir, 15)
        self.log_view.setPlainText(log_text)

    def _on_status_ready(self, branch, entries):
        self.branch_label.setText(f"\u2387 {branch}")
        self.status_tree.clear()

        status_labels = {
            "M": "Modified", "A": "Added", "D": "Deleted",
            "R": "Renamed", "??": "Untracked", "UU": "Conflict"
        }
        status_colors = {
            "M": "#e5c07b", "A": "#98c379", "D": "#e06c75",
            "R": "#61afef", "??": "#5c6370", "UU": "#d19a66"
        }

        for entry in entries:
            s = entry["status"]
            label = status_labels.get(s, s)
            color = status_colors.get(s, "#abb2bf")
            item = QTreeWidgetItem(self.status_tree, [f"[{label}] {entry['file']}"])
            item.setForeground(0, __import__("PyQt5").QtGui.QColor(color))
            item.setData(0, Qt.UserRole, entry["file"])

        self.status_changed.emit(branch, len(entries))

    def _on_item_clicked(self, item, col):
        filepath = item.data(0, Qt.UserRole)
        if filepath and self._workspace_dir:
            diff = git_diff(self._workspace_dir, filepath)
            self.diff_view.setPlainText(diff if diff else "(no diff available)")

    def _do_commit(self):
        msg = self.commit_input.text().strip()
        if not msg:
            return
        if not self._workspace_dir:
            return
        result = git_commit(self._workspace_dir, msg)
        self.diff_view.setPlainText(result)
        self.commit_input.clear()
        self.refresh()

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        fg = theme.get("fg", "#e6edf3")
        sidebar_bg = theme.get("sidebar_bg", "#1e1f23")
        header_bg = theme.get("header_bg", "#161b22")
        accent = theme.get("accent", "#58a6ff")
        input_bg = theme.get("input_bg", "#0d1117")
        border = theme.get("border", "#30363d")
        muted = "#8b949e"

        for lbl in self.findChildren(QLabel):
            text = lbl.text()
            if text == "Source Control":
                lbl.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {fg}; padding: 4px;")
            elif text in ("Commit Message:", "Recent Commits:"):
                lbl.setStyleSheet(f"color: {muted}; font-size: 11px;")

        self.branch_label.setStyleSheet(f"color: {muted}; font-size: 11px; padding: 2px 4px;")

        self.status_tree.setStyleSheet(
            f"QTreeWidget {{ background: {sidebar_bg}; border: 1px solid {border}; color: {fg}; }}"
        )
        self.diff_view.setStyleSheet(
            f"background: {input_bg}; color: {fg}; border: 1px solid {border}; font-family: monospace; font-size: 11px;"
        )
        self.log_view.setStyleSheet(
            f"background: {input_bg}; color: {fg}; border: 1px solid {border}; font-family: monospace; font-size: 11px;"
        )
        self.commit_input.setStyleSheet(
            f"background: {header_bg}; color: {fg}; border: 1px solid {border}; "
            f"border-radius: 4px; padding: 4px;"
        )
