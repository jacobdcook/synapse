import os
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QTabWidget, QFileDialog, QPlainTextEdit, QPushButton, QLabel,
    QShortcut, QSplitter, QMenu, QToolButton
)
from PyQt5.QtCore import Qt, pyqtSignal, QFileSystemWatcher
from PyQt5.QtGui import QKeySequence
from .editor import CodeEditor, FindReplaceBar
from .markdown_preview import MarkdownPreview

log = logging.getLogger(__name__)


class WorkspacePanel(QWidget):
    file_selected = pyqtSignal(str)
    workspace_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._workspace_dir = None
        self._recent_projects = []
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self.refresh)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Folder")
        open_btn.clicked.connect(self._pick_folder)
        btn_row.addWidget(open_btn)
        self.recent_btn = QToolButton()
        self.recent_btn.setText("Recent")
        self.recent_btn.setPopupMode(QToolButton.InstantPopup)
        self.recent_btn.setMenu(QMenu(self))
        btn_row.addWidget(self.recent_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Open Workspace Folder")
        if path:
            self.set_workspace(path)

    def set_workspace(self, path):
        if self._workspace_dir:
            self.watcher.removePath(str(self._workspace_dir))
        self._workspace_dir = Path(path)
        if self._workspace_dir.exists():
            self.watcher.addPath(str(self._workspace_dir))
        self._add_to_recent(str(path))
        self.refresh()
        self.workspace_changed.emit(str(self._workspace_dir))

    def set_recent_projects(self, projects):
        self._recent_projects = list(projects or [])
        self._update_recent_menu()

    def _add_to_recent(self, path):
        if path in self._recent_projects:
            self._recent_projects.remove(path)
        self._recent_projects.insert(0, path)
        self._recent_projects = self._recent_projects[:10]
        self._update_recent_menu()

    def get_recent_projects(self):
        return self._recent_projects

    def _update_recent_menu(self):
        menu = self.recent_btn.menu()
        menu.clear()
        for p in self._recent_projects:
            name = Path(p).name
            action = menu.addAction(f"{name}  ({p})")
            action.setData(p)
            action.triggered.connect(lambda checked, path=p: self.set_workspace(path))

    def get_workspace_dir(self):
        return self._workspace_dir

    def refresh(self):
        self.tree.clear()
        if not self._workspace_dir or not self._workspace_dir.exists():
            return
        root_item = QTreeWidgetItem(self.tree, [self._workspace_dir.name])
        root_item.setData(0, Qt.UserRole, str(self._workspace_dir))
        self._populate_tree(self._workspace_dir, root_item)
        root_item.setExpanded(True)

    def _populate_tree(self, path, parent_item):
        try:
            entries = sorted(list(path.iterdir()), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                if entry.name.startswith('.') and entry.name != '.env':
                    continue
                if entry.name in ('__pycache__', 'node_modules', 'venv', '.venv', '.git'):
                    continue
                item = QTreeWidgetItem(parent_item, [entry.name])
                item.setData(0, Qt.UserRole, str(entry))
                if entry.is_dir():
                    self._populate_tree(entry, item)
        except PermissionError:
            pass

    def _on_item_double_clicked(self, item, col):
        path = item.data(0, Qt.UserRole)
        if path and Path(path).is_file():
            self.file_selected.emit(path)


class EditorTabs(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.tabCloseRequested.connect(self.close_tab)
        self._find_bars = {}

    def open_file(self, filepath):
        filepath = str(filepath)
        for i in range(self.count()):
            if self.widget(i).property("filepath") == filepath:
                self.setCurrentIndex(i)
                return self._get_editor(i)

        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            container = QWidget()
            container.setProperty("filepath", filepath)
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            editor = CodeEditor()
            editor.setPlainText(content)
            editor.mark_saved()
            editor.set_language_from_filename(filepath)
            editor.content_modified.connect(lambda fp=filepath: self._on_modified(fp))

            find_bar = FindReplaceBar(editor)
            layout.addWidget(find_bar)

            is_md = filepath.lower().endswith(('.md', '.markdown'))
            if is_md:
                splitter = QSplitter(Qt.Horizontal)
                splitter.addWidget(editor)
                preview = MarkdownPreview()
                preview.update_preview(content)
                splitter.addWidget(preview)
                splitter.setSizes([500, 500])
                layout.addWidget(splitter)
                editor.textChanged.connect(lambda e=editor, p=preview: p.update_preview(e.toPlainText()))
            else:
                layout.addWidget(editor)

            name = Path(filepath).name
            idx = self.addTab(container, name)
            self.setTabToolTip(idx, filepath)
            self.setCurrentIndex(idx)
            self._find_bars[filepath] = find_bar

            find_shortcut = QShortcut(QKeySequence("Ctrl+F"), container)
            find_shortcut.activated.connect(find_bar.show_bar)

            return editor
        except Exception as e:
            log.error(f"Failed to open file {filepath}: {e}")
            return None

    def _get_editor(self, index):
        container = self.widget(index)
        if container:
            return container.findChild(CodeEditor)
        return None

    def _on_modified(self, filepath):
        for i in range(self.count()):
            if self.widget(i).property("filepath") == filepath:
                name = Path(filepath).name
                current_text = self.tabText(i)
                if not current_text.endswith(" *"):
                    self.setTabText(i, name + " *")
                break

    def close_tab(self, index):
        editor = self._get_editor(index)
        if editor and editor.is_modified():
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                f"Save changes to {self.tabText(index).rstrip(' *')}?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if reply == QMessageBox.Save:
                self.save_tab(index)
            elif reply == QMessageBox.Cancel:
                return
        filepath = self.widget(index).property("filepath")
        self._find_bars.pop(filepath, None)
        self.removeTab(index)

    def save_current(self):
        return self.save_tab(self.currentIndex())

    def save_tab(self, index):
        editor = self._get_editor(index)
        if not editor:
            return False

        container = self.widget(index)
        filepath = container.property("filepath") if container else None
        if not filepath:
            filepath, _ = QFileDialog.getSaveFileName(self, "Save File As")
            if not filepath:
                return False
            if container:
                container.setProperty("filepath", filepath)
            self.setTabText(index, Path(filepath).name)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(editor.toPlainText())
            editor.mark_saved()
            name = Path(filepath).name
            self.setTabText(index, name)
            return True
        except Exception as e:
            log.error(f"Failed to save file {filepath}: {e}")
            return False
