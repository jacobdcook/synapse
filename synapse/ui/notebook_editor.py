import logging
from typing import List, Dict, Any, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
    QTextEdit, QPushButton, QLabel, QFrame, QSplitter, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from ..core.notebook_manager import NotebookCell, NotebookManager

log = logging.getLogger(__name__)

class CellWidget(QFrame):
    run_requested = pyqtSignal(str)
    add_above_requested = pyqtSignal(str)
    add_below_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    type_changed = pyqtSignal(str, str)

    def __init__(self, cell: NotebookCell, parent=None):
        super().__init__(parent)
        self.cell = cell
        self.setFrameShape(QFrame.StyledPanel)
        self.setLineWidth(1)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        header = QHBoxLayout()
        self.count_label = QLabel(f"[{self.cell.execution_count or ' '}]")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["code", "markdown"])
        self.type_combo.setCurrentText(self.cell.type)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(lambda: self.run_requested.emit(self.cell.id))
        add_above = QPushButton("+↑")
        add_above.setToolTip("Add above")
        add_above.clicked.connect(lambda: self.add_above_requested.emit(self.cell.id))
        add_below = QPushButton("+↓")
        add_below.setToolTip("Add below")
        add_below.clicked.connect(lambda: self.add_below_requested.emit(self.cell.id))
        del_btn = QPushButton("×")
        del_btn.setToolTip("Delete")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.cell.id))
        
        header.addWidget(self.count_label)
        header.addWidget(self.type_combo)
        header.addStretch()
        header.addWidget(add_above)
        header.addWidget(add_below)
        header.addWidget(self.run_btn)
        header.addWidget(del_btn)
        layout.addLayout(header)

    def _on_type_changed(self, t: str):
        self.cell.type = t
        self.type_changed.emit(self.cell.id, t)

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
        
        toolbar = QHBoxLayout()
        self.add_cell_btn = QPushButton("+ Code")
        self.add_md_btn = QPushButton("+ Markdown")
        self.save_btn = QPushButton("Save")
        self.run_all_btn = QPushButton("Run All")
        self.var_btn = QPushButton("Variables")
        self.save_btn.clicked.connect(self._save_data)
        self.run_all_btn.clicked.connect(self._run_all)
        self.var_btn.clicked.connect(self._show_variables)
        self.add_cell_btn.clicked.connect(lambda: self._add_cell("code"))
        self.add_md_btn.clicked.connect(lambda: self._add_cell("markdown"))
        toolbar.addWidget(self.add_cell_btn)
        toolbar.addWidget(self.add_md_btn)
        toolbar.addWidget(self.save_btn)
        toolbar.addWidget(self.run_all_btn)
        toolbar.addWidget(self.var_btn)
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

    def _add_cell(self, cell_type: str):
        import uuid
        c = NotebookCell(str(uuid.uuid4())[:8], cell_type, "")
        w = CellWidget(c)
        w.run_requested.connect(self._on_run_cell)
        w.add_above_requested.connect(self._on_add_above)
        w.add_below_requested.connect(self._on_add_below)
        w.delete_requested.connect(self._on_delete_cell)
        self.cell_layout.insertWidget(self.cell_layout.count() - 1, w)
        self.cells.append(w)

    def _insert_cell_at(self, idx: int, cell_type: str):
        import uuid
        c = NotebookCell(str(uuid.uuid4())[:8], cell_type, "")
        w = CellWidget(c)
        w.run_requested.connect(self._on_run_cell)
        w.add_above_requested.connect(self._on_add_above)
        w.add_below_requested.connect(self._on_add_below)
        w.delete_requested.connect(self._on_delete_cell)
        self.cell_layout.insertWidget(idx, w)
        self.cells.insert(idx, w)

    def _on_add_above(self, cell_id: str):
        idx = next((i for i, w in enumerate(self.cells) if w.cell.id == cell_id), -1)
        if idx >= 0:
            self._insert_cell_at(idx, "code")

    def _on_add_below(self, cell_id: str):
        idx = next((i for i, w in enumerate(self.cells) if w.cell.id == cell_id), -1)
        if idx >= 0:
            self._insert_cell_at(idx + 1, "code")

    def _on_delete_cell(self, cell_id: str):
        w = next((x for x in self.cells if x.cell.id == cell_id), None)
        if w and len(self.cells) > 1:
            self.cell_layout.removeWidget(w)
            self.cells.remove(w)
            w.deleteLater()

    def _load_data(self):
        notebook_cells = self.manager.load_notebook(self.filepath)
        for c in notebook_cells:
            widget = CellWidget(c)
            widget.run_requested.connect(self._on_run_cell)
            widget.add_above_requested.connect(self._on_add_above)
            widget.add_below_requested.connect(self._on_add_below)
            widget.delete_requested.connect(self._on_delete_cell)
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
        widget = next((w for w in self.cells if w.cell.id == cell_id), None)
        if widget:
            code = widget.editor.toPlainText()
            if widget.cell.type == "code":
                out, err, ok = self.manager.execute_cell_subprocess(code)
                text = out + (f"\n[stderr]\n{err}" if err else "")
                widget.update_output(text if text else "(no output)")
            else:
                widget.update_output("(markdown - no execution)")

    def _run_all(self):
        for w in self.cells:
            if w.cell.type == "code":
                self._on_run_cell(w.cell.id)

    def _show_variables(self):
        from PyQt5.QtWidgets import QDialog, QListWidget
        dlg = QDialog(self)
        dlg.setWindowTitle("Variable Inspector")
        layout = __import__("PyQt5.QtWidgets", fromlist=["QVBoxLayout"]).QVBoxLayout(dlg)
        lst = QListWidget()
        for k, v in self.manager.get_variable_inspector().items():
            lst.addItem(f"{k}: {v}")
        layout.addWidget(lst)
        dlg.exec_()

    def update_cell_output(self, cell_id: str, text: str):
        widget = next((w for w in self.cells if w.cell.id == cell_id), None)
        if widget:
            widget.update_output(text)

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1e1e1e")
        fg = theme.get("fg", "#d4d4d4")
        input_bg = theme.get("input_bg", "#1e1e1e")
        border = theme.get("border", "#30363d")
        self.setStyleSheet(f"background: {bg}; color: {fg};")
        for cell in self.cells:
            cell.editor.setStyleSheet(f"font-family: 'Courier New'; background: {input_bg}; color: {fg};")
            cell.output_area.setStyleSheet(f"background: {input_bg}; color: {fg}; padding: 5px;")
            cell.setStyleSheet(f"QFrame {{ border: 1px solid {border}; background: {bg}; }}")
