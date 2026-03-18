from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLabel, QProgressBar, QToolBar, QAction
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QColor

class TestSidebar(QWidget):
    run_all_requested = pyqtSignal()
    run_selected_requested = pyqtSignal(list)
    run_coverage_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._test_items = {} # nodeid -> QTreeWidgetItem

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QToolBar()
        from PyQt5.QtCore import QSize
        toolbar.setIconSize(QSize(20, 20))
        
        self.run_all_action = toolbar.addAction("\u25b6\u25b6", self.run_all_requested.emit)
        self.run_all_action.setToolTip("Run All Tests")

        self.run_coverage_action = toolbar.addAction("\U0001f3af", self.run_coverage_requested.emit)
        self.run_coverage_action.setToolTip("Run Tests with Coverage")
        
        self.refresh_action = toolbar.addAction("\u21bb", self.refresh_requested.emit)
        self.refresh_action.setToolTip("Refresh Test Discovery")

        layout.addWidget(toolbar)

        # Progress / Stats
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.stats_label = QLabel("No tests discovered")
        self.stats_label.setContentsMargins(10, 5, 10, 5)
        layout.addWidget(self.stats_label)

        # Test Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setColumnCount(1)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

    def set_tests(self, test_nodeids):
        self.tree.clear()
        self._test_items = {}
        
        # Build hierarchy from nodeids (e.g., tests/test_file.py::TestClass::test_method)
        for nodeid in test_nodeids:
            parts = nodeid.split("::")
            parent = self.tree.invisibleRootItem()
            
            # First part is file path
            file_path = parts[0]
            # Classes and methods...
            current_path = ""
            for i, part in enumerate(parts):
                if current_path:
                    current_path += "::" + part
                else:
                    current_path = part
                
                if current_path in self._test_items:
                    parent = self._test_items[current_path]
                else:
                    item = QTreeWidgetItem(parent, [part])
                    item.setData(0, Qt.UserRole, current_path)
                    self._test_items[current_path] = item
                    parent = item
            
        self.stats_label.setText(f"Discovered {len(test_nodeids)} tests")
        self.tree.expandAll()

    def update_test_result(self, nodeid, status):
        if nodeid in self._test_items:
            item = self._test_items[nodeid]
            if status == "PASSED":
                item.setForeground(0, QColor("#3fb950")) # Green
                item.setText(0, item.text(0).split("  ")[0] + "  \u2714")
            elif status == "FAILED":
                item.setForeground(0, QColor("#f85149")) # Red
                item.setText(0, item.text(0).split("  ")[0] + "  \u2718")
            elif status == "SKIPPED":
                item.setForeground(0, QColor("#8b949e")) # Gray
                item.setText(0, item.text(0).split("  ")[0] + "  \u26a0")

    def _on_item_double_clicked(self, item, col):
        nodeid = item.data(0, Qt.UserRole)
        if nodeid:
            self.run_selected_requested.emit([nodeid])

    def apply_theme(self, theme):
        bg = theme.get("sidebar_bg", "#1e1e1e")
        fg = theme.get("fg", "#e6edf3")
        border = theme.get("border", "#30363d")
        self.setStyleSheet(f"background-color: {bg};")
        self.tree.setStyleSheet(f"QTreeWidget {{ background: {bg}; color: {fg}; border: none; }}")
        self.stats_label.setStyleSheet(f"color: {fg}; margin: 5px 10px;")
