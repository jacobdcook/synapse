import os
import re
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QTreeWidget, QTreeWidgetItem, QCheckBox, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

log = logging.getLogger(__name__)

SKIP_DIRS = {'.git', '__pycache__', 'node_modules', 'venv', '.venv', '.tox', 'dist', 'build'}
MAX_FILE_SIZE = 1_000_000
TEXT_EXTENSIONS = ('.py', '.js', '.ts', '.jsx', '.tsx', '.md', '.txt', '.json', '.yaml', '.yml', '.html', '.css', '.sh')


def search_workspace_sync(workspace, query, use_regex=False, case_sensitive=False, file_type=None, limit=100):
    """Synchronous workspace text search. Returns list of (rel_path, line_num, line_text)."""
    workspace = Path(workspace)
    if not workspace.exists():
        return []
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        pat = re.compile(query if use_regex else re.escape(query), flags)
    except re.error:
        return []
    results = []
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            fpath = Path(root) / fname
            if file_type and fpath.suffix.lower() != file_type:
                continue
            if fpath.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if fpath.stat().st_size > MAX_FILE_SIZE:
                continue
            try:
                for i, line in enumerate(fpath.read_text(errors='replace').splitlines(), 1):
                    if pat.search(line):
                        rel = str(fpath.relative_to(workspace))
                        results.append((rel, i, line.strip()[:300]))
                        if len(results) >= limit:
                            return results
            except (OSError, UnicodeDecodeError):
                pass
    return results


class SearchWorker(QThread):
    result_found = pyqtSignal(str, int, str)  # filepath, line_num, line_text
    search_done = pyqtSignal(int)

    def __init__(self, workspace, pattern, case_sensitive=False, use_regex=False):
        super().__init__()
        self.workspace = Path(workspace)
        self.pattern = pattern
        self.case_sensitive = case_sensitive
        self.use_regex = use_regex
        self._count = 0

    def run(self):
        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            if self.use_regex:
                compiled = re.compile(self.pattern, flags)
            else:
                compiled = re.compile(re.escape(self.pattern), flags)
        except re.error:
            self.search_done.emit(0)
            return

        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for fname in files:
                fpath = Path(root) / fname
                if fpath.stat().st_size > MAX_FILE_SIZE:
                    continue
                try:
                    with open(fpath, 'r', errors='replace') as f:
                        for i, line in enumerate(f, 1):
                            if compiled.search(line):
                                rel = str(fpath.relative_to(self.workspace))
                                self.result_found.emit(rel, i, line.rstrip()[:200])
                                self._count += 1
                                if self._count >= 500:
                                    self.search_done.emit(self._count)
                                    return
                except (OSError, UnicodeDecodeError) as e:
                    log.warning(f"Search file read error: {e}")
        self.search_done.emit(self._count)


class WorkspaceSearchDialog(QDialog):
    file_requested = pyqtSignal(str, int)  # filepath, line

    def __init__(self, workspace_dir, parent=None):
        super().__init__(parent)
        self.workspace_dir = workspace_dir
        self._worker = None
        self.setWindowTitle("Search & Replace in Workspace")
        self.setMinimumSize(700, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.returnPressed.connect(self._do_search)
        search_row.addWidget(self.search_input)

        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with...")
        search_row.addWidget(self.replace_input)
        layout.addLayout(search_row)

        opts_row = QHBoxLayout()
        self.case_check = QCheckBox("Case sensitive")
        opts_row.addWidget(self.case_check)
        self.regex_check = QCheckBox("Regex")
        opts_row.addWidget(self.regex_check)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._do_search)
        opts_row.addWidget(search_btn)

        replace_btn = QPushButton("Replace All")
        replace_btn.clicked.connect(self._do_replace_all)
        opts_row.addWidget(replace_btn)

        opts_row.addStretch()
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #8b949e;")
        opts_row.addWidget(self.count_label)
        layout.addLayout(opts_row)

        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["File", "Line", "Content"])
        self.results_tree.setColumnWidth(0, 250)
        self.results_tree.setColumnWidth(1, 50)
        self.results_tree.itemDoubleClicked.connect(self._on_result_clicked)
        layout.addWidget(self.results_tree)

    def _do_search(self):
        pattern = self.search_input.text()
        if not pattern or not self.workspace_dir:
            return
        self.results_tree.clear()
        self.count_label.setText("Searching...")
        self._worker = SearchWorker(
            self.workspace_dir, pattern,
            self.case_check.isChecked(), self.regex_check.isChecked()
        )
        self._worker.result_found.connect(self._on_result)
        self._worker.search_done.connect(self._on_search_done)
        self._worker.start()

    def _on_result(self, filepath, line_num, line_text):
        item = QTreeWidgetItem(self.results_tree, [filepath, str(line_num), line_text])
        item.setData(0, Qt.UserRole, filepath)
        item.setData(1, Qt.UserRole, line_num)

    def _on_search_done(self, count):
        self.count_label.setText(f"{count} matches found")

    def _on_result_clicked(self, item, col):
        filepath = item.data(0, Qt.UserRole)
        line = item.data(1, Qt.UserRole) or 1
        if filepath:
            full_path = str(Path(self.workspace_dir) / filepath)
            self.file_requested.emit(full_path, line)

    def _do_replace_all(self):
        pattern = self.search_input.text()
        replacement = self.replace_input.text()
        if not pattern or not self.workspace_dir:
            return

        count = self.results_tree.topLevelItemCount()
        if count == 0:
            return

        reply = QMessageBox.question(
            self, "Confirm Replace All",
            f"Replace {count} occurrences across all matching files?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        flags = 0 if self.case_check.isChecked() else re.IGNORECASE
        if self.regex_check.isChecked():
            compiled = re.compile(pattern, flags)
        else:
            compiled = re.compile(re.escape(pattern), flags)

        affected_files = set()
        for i in range(count):
            item = self.results_tree.topLevelItem(i)
            affected_files.add(item.data(0, Qt.UserRole))

        replaced = 0
        for rel_path in affected_files:
            full_path = Path(self.workspace_dir) / rel_path
            try:
                content = full_path.read_text(errors='replace')
                new_content, n = compiled.subn(replacement, content)
                if n > 0:
                    full_path.write_text(new_content)
                    replaced += n
            except OSError as e:
                log.warning(f"Replace file error: {e}")

        self.count_label.setText(f"Replaced {replaced} occurrences in {len(affected_files)} files")
        self._do_search()

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        fg = theme.get("fg", "#e6edf3")
        input_bg = theme.get("input_bg", "#0d1117")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#58a6ff")
        muted = "#8b949e"

        self.setStyleSheet(f"background: {bg};")
        self.search_input.setStyleSheet(
            f"background: {input_bg}; color: {fg}; border: 1px solid {border}; padding: 4px;"
        )
        self.replace_input.setStyleSheet(
            f"background: {input_bg}; color: {fg}; border: 1px solid {border}; padding: 4px;"
        )
        self.count_label.setStyleSheet(f"color: {muted};")
        self.results_tree.setStyleSheet(
            f"QTreeWidget {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; }}"
            f"QTreeWidget::item:selected {{ background: {accent}; color: white; }}"
        )
