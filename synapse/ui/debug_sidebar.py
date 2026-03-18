import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
    QListWidget, QListWidgetItem, QLabel, QSplitter, 
    QHeaderView, QPushButton, QHBoxLayout
)
from PyQt5.QtCore import Qt, pyqtSignal

class DebugSidebar(QWidget):
    """
    Sidebar panel for debugger information (Variables, Stack, Breakpoints).
    """
    breakpoint_clicked = pyqtSignal(str, int) # file, line
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.splitter = QSplitter(Qt.Vertical)
        
        # Variables View
        self.vars_widget = QWidget()
        vars_layout = QVBoxLayout(self.vars_widget)
        vars_layout.setContentsMargins(5, 5, 5, 5)
        vars_layout.addWidget(QLabel("VARIABLES"))
        self.vars_tree = QTreeWidget()
        self.vars_tree.setHeaderLabels(["Name", "Value", "Type"])
        self.vars_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.vars_tree.setStyleSheet("QTreeWidget { background-color: #1e1e1e; border: none; color: #d4d4d4; }")
        vars_layout.addWidget(self.vars_tree)
        self.splitter.addWidget(self.vars_widget)
        
        # Call Stack View
        self.stack_widget = QWidget()
        stack_layout = QVBoxLayout(self.stack_widget)
        stack_layout.setContentsMargins(5, 5, 5, 5)
        stack_layout.addWidget(QLabel("CALL STACK"))
        self.stack_list = QListWidget()
        self.stack_list.setStyleSheet("QListWidget { background-color: #1e1e1e; border: none; color: #d4d4d4; }")
        stack_layout.addWidget(self.stack_list)
        self.splitter.addWidget(self.stack_widget)
        
        # Breakpoints View
        self.bp_widget = QWidget()
        bp_layout = QVBoxLayout(self.bp_widget)
        bp_layout.setContentsMargins(5, 5, 5, 5)
        bp_layout.addWidget(QLabel("BREAKPOINTS"))
        self.bp_list = QListWidget()
        self.bp_list.setStyleSheet("QListWidget { background-color: #1e1e1e; border: none; color: #d4d4d4; }")
        self.bp_list.itemDoubleClicked.connect(self._on_bp_double_clicked)
        bp_layout.addWidget(self.bp_list)
        self.splitter.addWidget(self.bp_widget)
        
        self.layout.addWidget(self.splitter)
        
        # Initial proportions
        self.splitter.setSizes([300, 200, 100])

    def set_variables(self, variables):
        self.update_variables(variables)

    def set_stack(self, frames):
        self.update_stack(frames)

    def set_breakpoints(self, breakpoints):
        self.update_breakpoints(breakpoints)

    def update_variables(self, variables):
        self.vars_tree.clear()
        for var in variables:
            name = var.get("name", "")
            value = var.get("value", "")
            vtype = var.get("type", "")
            
            item = QTreeWidgetItem([name, str(value), vtype])
            self.vars_tree.addTopLevelItem(item)

    def update_stack(self, frames):
        self.stack_list.clear()
        for frame in frames:
            name = frame.get("name", "")
            line = frame.get("line", "")
            file = os.path.basename(frame.get("source", {}).get("path", "unknown"))
            
            item = QListWidgetItem(f"{name} ({file}:{line})")
            self.stack_list.addItem(item)

    def update_breakpoints(self, breakpoints):
        # breakpoints: dict {abs_path: [lines]}
        self.bp_list.clear()
        for path, lines in breakpoints.items():
            filename = os.path.basename(path)
            for line in sorted(lines):
                item = QListWidgetItem(f"{filename} : {line}")
                item.setData(Qt.UserRole, (path, line))
                self.bp_list.addItem(item)

    def _on_bp_double_clicked(self, item):
        path, line = item.data(Qt.UserRole)
        self.breakpoint_clicked.emit(path, line)
