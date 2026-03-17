from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox
)
from PyQt5.QtCore import Qt

class TableEditorDialog(QDialog):
    def __init__(self, table_markdown="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Markdown Table Editor")
        self.resize(800, 600)
        self.initial_md = table_markdown
        self._setup_ui()
        if table_markdown:
            self._load_markdown(table_markdown)
        else:
            self._init_empty()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        add_row_btn = QPushButton("Add Row")
        add_row_btn.clicked.connect(self._add_row)
        toolbar.addWidget(add_row_btn)

        add_col_btn = QPushButton("Add Column")
        add_col_btn.clicked.connect(self._add_column)
        toolbar.addWidget(add_col_btn)

        del_row_btn = QPushButton("Delete Row")
        del_row_btn.clicked.connect(self._delete_row)
        toolbar.addWidget(del_row_btn)

        del_col_btn = QPushButton("Delete Col")
        del_col_btn.clicked.connect(self._delete_column)
        toolbar.addWidget(del_col_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        # Bottom Buttons
        bottom = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        bottom.addWidget(cancel_btn)

        save_btn = QPushButton("Insert Table")
        save_btn.setStyleSheet("background: #238636; color: white; font-weight: bold;")
        save_btn.clicked.connect(self.accept)
        bottom.addWidget(save_btn)

        layout.addLayout(bottom)

    def _init_empty(self):
        self.table.setColumnCount(3)
        self.table.setRowCount(2)
        self.table.setHorizontalHeaderLabels(["Header 1", "Header 2", "Header 3"])

    def _load_markdown(self, md):
        lines = [l.strip() for l in md.split("\n") if l.strip().startswith("|")]
        if len(lines) < 2:
            self._init_empty()
            return

        # Parse headers
        headers = [c.strip() for c in lines[0].split("|") if c.strip()]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        # Skip separator line (e.g., |---|---|)
        data_lines = lines[2:]
        self.table.setRowCount(len(data_lines))

        for r_idx, line in enumerate(data_lines):
            cols = [c.strip() for c in line.split("|") if c.strip()]
            for c_idx in range(self.table.columnCount()):
                val = cols[c_idx] if c_idx < len(cols) else ""
                self.table.setItem(r_idx, c_idx, QTableWidgetItem(val))

    def get_markdown(self):
        cols = self.table.columnCount()
        rows = self.table.rowCount()

        headers = []
        for c in range(cols):
            headers.append(self.table.horizontalHeaderItem(c).text() if self.table.horizontalHeaderItem(c) else f"Col {c+1}")

        md = "| " + " | ".join(headers) + " |\n"
        md += "| " + " | ".join(["---"] * cols) + " |\n"

        for r in range(rows):
            row_vals = []
            for c in range(cols):
                item = self.table.item(r, c)
                row_vals.append(item.text() if item else "")
            md += "| " + " | ".join(row_vals) + " |\n"

        return md

    def _add_row(self):
        self.table.insertRow(self.table.rowCount())

    def _add_column(self):
        self.table.insertColumn(self.table.columnCount())

    def _delete_row(self):
        curr = self.table.currentRow()
        if curr >= 0:
            self.table.removeRow(curr)

    def _delete_column(self):
        curr = self.table.currentColumn()
        if curr >= 0:
            self.table.removeColumn(curr)

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        fg = theme.get("fg", "#e6edf3")
        input_bg = theme.get("input_bg", "#0d1117")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#238636")
        self.setStyleSheet(f"""
            QDialog {{ background: {bg}; color: {fg}; }}
            QTableWidget {{ background: {input_bg}; color: {fg}; gridline-color: {border}; }}
            QHeaderView::section {{ background: {bg}; color: {fg}; border: 1px solid {border}; padding: 4px; }}
            QPushButton {{ background: {border}; color: {fg}; border: none; padding: 6px 12px; border-radius: 4px; }}
            QPushButton:hover {{ background: {input_bg}; }}
        """)
