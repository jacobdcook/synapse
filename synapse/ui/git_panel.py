import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QPushButton, QPlainTextEdit, QLineEdit,
    QComboBox, QCheckBox, QGroupBox, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from ..core.git import (
    is_git_repo, git_branch, git_status, git_diff,
    git_log, git_commit, GitStatusWorker,
    stage_file, unstage_file, get_file_diff,
    git_branches, git_switch_branch, git_create_branch, git_delete_branch,
    stash_save, stash_pop, stash_list
)

log = logging.getLogger(__name__)


class GitPanel(QWidget):
    status_changed = pyqtSignal(str, int)
    explain_diff_requested = pyqtSignal(str)
    review_changes_requested = pyqtSignal(str)

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

        branch_row = QHBoxLayout()
        branch_row.addWidget(QLabel("Branch:"))
        self.branch_combo = QComboBox()
        self.branch_combo.setMinimumWidth(150)
        self.branch_combo.currentTextChanged.connect(self._on_branch_switch)
        branch_row.addWidget(self.branch_combo)
        new_branch_btn = QPushButton("New")
        new_branch_btn.clicked.connect(self._create_branch)
        branch_row.addWidget(new_branch_btn)
        branch_row.addStretch()
        layout.addLayout(branch_row)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.status_tree = QTreeWidget()
        self.status_tree.setHeaderLabels(["File", "Status"])
        self.status_tree.setColumnWidth(0, 250)
        self.status_tree.setStyleSheet("QTreeWidget { background: #1e1e1e; border: 1px solid #333; color: #e6edf3; }")
        self.status_tree.itemClicked.connect(self._on_item_clicked)
        self.status_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.status_tree)

        stage_btn = QPushButton("Stage Selected")
        stage_btn.clicked.connect(self._stage_selected)
        unstage_btn = QPushButton("Unstage Selected")
        unstage_btn.clicked.connect(self._unstage_selected)
        stage_row = QHBoxLayout()
        stage_row.addWidget(stage_btn)
        stage_row.addWidget(unstage_btn)
        stage_row.addStretch()
        layout.addLayout(stage_row)

        self.diff_view = QPlainTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setMaximumHeight(200)
        self.diff_view.setStyleSheet(
            "background: #0d1117; color: #e6edf3; border: 1px solid #333; font-family: monospace; font-size: 11px;"
        )
        layout.addWidget(self.diff_view)

        diff_btn_row = QHBoxLayout()
        explain_btn = QPushButton("Explain diff")
        explain_btn.clicked.connect(lambda: self.explain_diff_requested.emit(self.diff_view.toPlainText()))
        review_btn = QPushButton("Review changes")
        review_btn.clicked.connect(self._emit_review_changes)
        diff_btn_row.addWidget(explain_btn)
        diff_btn_row.addWidget(review_btn)
        diff_btn_row.addStretch()
        layout.addLayout(diff_btn_row)

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

        stash_group = QGroupBox("Stash")
        stash_layout = QVBoxLayout(stash_group)
        self.stash_combo = QComboBox()
        self.stash_combo.setMinimumWidth(200)
        stash_layout.addWidget(self.stash_combo)
        stash_btn_row = QHBoxLayout()
        stash_save_btn = QPushButton("Stash")
        stash_save_btn.clicked.connect(self._do_stash_save)
        stash_pop_btn = QPushButton("Pop")
        stash_pop_btn.clicked.connect(self._do_stash_pop)
        stash_btn_row.addWidget(stash_save_btn)
        stash_btn_row.addWidget(stash_pop_btn)
        stash_btn_row.addStretch()
        stash_layout.addLayout(stash_btn_row)
        layout.addWidget(stash_group)

        layout.addStretch()

    def set_workspace(self, path):
        self._workspace_dir = path
        self.refresh()

    def refresh(self):
        if not self._workspace_dir or not is_git_repo(self._workspace_dir):
            self.branch_combo.clear()
            self.branch_combo.addItem("Not a git repository")
            self.status_tree.clear()
            self.log_view.clear()
            self.diff_view.clear()
            self.stash_combo.clear()
            return

        if self._worker and self._worker.isRunning():
            self._worker.wait(2000)
        self._worker = GitStatusWorker(self._workspace_dir)
        self._worker.status_ready.connect(self._on_status_ready)
        self._worker.start()

        log_text = git_log(self._workspace_dir, 15)
        self.log_view.setPlainText(log_text)

    def _on_status_ready(self, branch, entries):
        self.status_tree.clear()
        self.branch_combo.blockSignals(True)
        self.branch_combo.clear()
        try:
            for b in git_branches(self._workspace_dir):
                self.branch_combo.addItem(b["name"])
                if b.get("current"):
                    self.branch_combo.setCurrentText(b["name"])
        except Exception:
            pass
        self.branch_combo.blockSignals(False)

        self.stash_combo.clear()
        try:
            for s in stash_list(self._workspace_dir):
                self.stash_combo.addItem(s["message"] or s["ref"], s["ref"])
        except Exception:
            pass

        def _status_ind(st):
            if not st:
                return "?"
            st = st.strip() or st
            if "?" in st:
                return "?"
            if "M" in st or "m" in st:
                return "M"
            if "A" in st:
                return "A"
            if "D" in st:
                return "D"
            return "?"

        for entry in entries:
            ind = _status_ind(entry.get("status", ""))
            item = QTreeWidgetItem(self.status_tree, [entry["file"], ind])
            item.setData(0, Qt.UserRole, entry["file"])
            item.setData(0, Qt.UserRole + 1, entry.get("status", ""))
        self.status_changed.emit(branch, len(entries))

    def _on_branch_switch(self, name):
        if not name or not self._workspace_dir or self.branch_combo.signalsBlocked():
            return
        if git_switch_branch(self._workspace_dir, name):
            self.refresh()

    def _create_branch(self):
        name, ok = QInputDialog.getText(self, "New Branch", "Branch name:")
        if ok and name and self._workspace_dir:
            if git_create_branch(self._workspace_dir, name):
                self.refresh()

    def _stage_selected(self):
        for item in self.status_tree.selectedItems():
            fp = item.data(0, Qt.UserRole)
            if fp and self._workspace_dir and stage_file(self._workspace_dir, fp):
                self.refresh()
                break

    def _unstage_selected(self):
        for item in self.status_tree.selectedItems():
            fp = item.data(0, Qt.UserRole)
            if fp and self._workspace_dir and unstage_file(self._workspace_dir, fp):
                self.refresh()
                break

    def _on_item_double_clicked(self, item, col):
        fp = item.data(0, Qt.UserRole)
        if fp and self._workspace_dir and hasattr(self, "file_requested"):
            from pathlib import Path
            self.file_requested.emit(str(Path(self._workspace_dir) / fp), 1)

    def _do_stash_save(self):
        msg, ok = QInputDialog.getText(self, "Stash", "Message (optional):")
        if self._workspace_dir and stash_save(self._workspace_dir, msg if ok else ""):
            self.refresh()

    def _do_stash_pop(self):
        if self._workspace_dir:
            ok, out = stash_pop(self._workspace_dir)
            self.diff_view.setPlainText(out)
            self.refresh()

    def _emit_review_changes(self):
        if not self._workspace_dir:
            return
        try:
            r = __import__("subprocess").run(
                ["git", "diff", "--cached"], capture_output=True, text=True,
                cwd=str(self._workspace_dir), timeout=10
            )
            self.review_changes_requested.emit(r.stdout if r.returncode == 0 else "")
        except Exception:
            self.review_changes_requested.emit("")

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

        self.branch_combo.setStyleSheet(f"color: {fg}; background: {input_bg}; border: 1px solid {border};")

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
