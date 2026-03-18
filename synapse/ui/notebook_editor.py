import logging
from typing import List, Dict, Any, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QTextEdit, QPushButton, QLabel, QFrame, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal
from ..core.notebook_manager import NotebookCell, NotebookManager

log = logging.getLogger(__name__)

class CellWidget(QFrame):
    run_requested = pyqtSignal(str) # cell_id

    def __init__(self, cell: NotebookCell, parent=None):
        super().__init__(parent)
        self.cell = cell
        self.setFrameShape(QFrame.StyledPanel)
        self.setLineWidth(1)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QHBoxLayout()
        self.count_label = QLabel(f"[{self.cell.execution_count or ' '}]")
        self.type_label = QLabel(self.cell.type.upper())
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(lambda: self.run_requested.emit(self.cell.id))
        
        header.addWidget(self.count_label)
        header.addWidget(self.type_label)
        header.addStretch()
        header.addWidget(self.run_btn)
        layout.addLayout(header)

        # Editor
        self.editor = QTextEdit()
        self.editor.setPlainText(self.cell.source)
        self.editor.setAcceptRichText(False)
        self.editor.setStyleSheet("font-family: 'Courier New'; background: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.editor)

        # Output
        self.output_area = QLabel()
        self.output_area.setWordWrap(True)
        self.output_area.setStyleSheet("background: #000; color: #fff; padding: 5px;")
        self.output_area.hide()
        layout.addWidget(self.output_area)

    def update_output(self, text: str):
        self.output_area.setText(text)
        self.output_area.show()

    def set_execution_count(self, count: int):
        self.count_label.setText(f"[{count}]")

class NotebookEditor(QWidget):
    def __init__(self, manager: NotebookManager, filepath: str, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.filepath = filepath
        self.cells: List[CellWidget] = []
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.add_cell_btn = QPushButton("+ Code")
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_data)
        toolbar.addWidget(self.add_cell_btn)
        toolbar.addWidget(self.save_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.cell_layout = QVBoxLayout(self.container)
        self.cell_layout.addStretch()
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

    def _load_data(self):
        notebook_cells = self.manager.load_notebook(self.filepath)
        for c in notebook_cells:
            widget = CellWidget(c)
            widget.run_requested.connect(self._on_run_cell)
            self.cell_layout.insertWidget(self.cell_layout.count() - 1, widget)
            self.cells.append(widget)

    def _save_data(self):
        # Update cell sources from widgets
        updated_cells = []
        for w in self.cells:
            w.cell.source = w.editor.toPlainText()
            updated_cells.append(w.cell)
        self.manager.save_notebook(self.filepath, updated_cells)
        log.info(f"Notebook saved to {self.filepath}")

    def _on_run_cell(self, cell_id):
        # Find cell widget
        widget = next((w for w in self.cells if w.cell.id == cell_id), None)
        if widget:
            code = widget.editor.toPlainText()
            self.manager.kernel.execute(cell_id, code)
            widget.update_output("Executing...")

    def update_cell_output(self, cell_id: str, text: str):
        widget = next((w for w in self.cells if w.cell.id == cell_id), None)
        if widget:
            widget.update_output(text)

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1e1e1e")
        fg = theme.get("fg", "#d4d4d4")
        self.setStyleSheet(f"background: {bg}; color: {fg};")
