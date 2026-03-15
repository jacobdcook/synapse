import re
from PyQt5.QtWidgets import (
    QPlainTextEdit, QWidget, QTextEdit, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QCheckBox, QShortcut
)
from PyQt5.QtCore import QSize, Qt, pyqtSignal, QRegularExpression
from PyQt5.QtGui import (
    QColor, QTextCharFormat, QFont, QSyntaxHighlighter,
    QPainter, QKeySequence
)


LANG_RULES = {
    "python": {
        "keywords": r'\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield|True|False|None|self)\b',
        "strings": r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')',
        "comments": r'(#[^\n]*)',
        "numbers": r'\b(\d+\.?\d*(?:e[+-]?\d+)?)\b',
        "functions": r'\b(\w+)(?=\s*\()',
        "decorators": r'(@\w+)',
    },
    "javascript": {
        "keywords": r'\b(break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|finally|for|function|if|import|in|instanceof|let|new|of|return|super|switch|this|throw|try|typeof|var|void|while|with|yield|true|false|null|undefined|async|await|from)\b',
        "strings": r'(`[\s\S]*?`|"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')',
        "comments": r'(//[^\n]*|/\*[\s\S]*?\*/)',
        "numbers": r'\b(\d+\.?\d*(?:e[+-]?\d+)?)\b',
        "functions": r'\b(\w+)(?=\s*\()',
    },
    "rust": {
        "keywords": r'\b(as|async|await|break|const|continue|crate|dyn|else|enum|extern|false|fn|for|if|impl|in|let|loop|match|mod|move|mut|pub|ref|return|self|Self|static|struct|super|trait|true|type|unsafe|use|where|while)\b',
        "strings": r'("(?:[^"\\]|\\.)*")',
        "comments": r'(//[^\n]*|/\*[\s\S]*?\*/)',
        "numbers": r'\b(\d+\.?\d*(?:e[+-]?\d+)?)\b',
        "functions": r'\b(\w+)(?=\s*\()',
    },
    "go": {
        "keywords": r'\b(break|case|chan|const|continue|default|defer|else|fallthrough|for|func|go|goto|if|import|interface|map|package|range|return|select|struct|switch|type|var|true|false|nil)\b',
        "strings": r'(`[^`]*`|"(?:[^"\\]|\\.)*")',
        "comments": r'(//[^\n]*|/\*[\s\S]*?\*/)',
        "numbers": r'\b(\d+\.?\d*(?:e[+-]?\d+)?)\b',
        "functions": r'\b(\w+)(?=\s*\()',
    },
}

EXT_TO_LANG = {
    '.py': 'python', '.pyw': 'python',
    '.js': 'javascript', '.jsx': 'javascript', '.ts': 'javascript', '.tsx': 'javascript', '.mjs': 'javascript',
    '.rs': 'rust',
    '.go': 'go',
    '.c': 'javascript', '.cpp': 'javascript', '.h': 'javascript', '.hpp': 'javascript',
    '.java': 'javascript', '.kt': 'javascript', '.cs': 'javascript',
    '.rb': 'python', '.php': 'javascript',
    '.sh': 'python', '.bash': 'python', '.zsh': 'python',
}

COLORS = {
    "keyword": "#c678dd",
    "string": "#98c379",
    "comment": "#5c6370",
    "number": "#d19a66",
    "function": "#61afef",
    "decorator": "#e5c07b",
}


class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, parent, lang="python"):
        super().__init__(parent)
        self._rules = []
        rules_def = LANG_RULES.get(lang, LANG_RULES["python"])

        for key in ("comments", "strings", "keywords", "numbers", "functions", "decorators"):
            pattern = rules_def.get(key)
            if pattern:
                fmt = QTextCharFormat()
                color = COLORS.get(key.rstrip("s"), COLORS.get(key, "#abb2bf"))
                fmt.setForeground(QColor(color))
                if key == "keywords":
                    fmt.setFontWeight(QFont.Bold)
                if key == "comments":
                    fmt.setFontItalic(True)
                self._rules.append((re.compile(pattern), fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start = match.start(1) if match.lastindex else match.start()
                length = len(match.group(1) if match.lastindex else match.group())
                self.setFormat(start, length, fmt)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_paint(event)


class FindReplaceBar(QWidget):
    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find...")
        self.find_input.setMaximumWidth(200)
        self.find_input.returnPressed.connect(self._find_next)
        layout.addWidget(self.find_input)

        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace...")
        self.replace_input.setMaximumWidth(200)
        layout.addWidget(self.replace_input)

        self.case_check = QCheckBox("Aa")
        self.case_check.setToolTip("Match case")
        layout.addWidget(self.case_check)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color: #8b949e; font-size: 11px; min-width: 50px;")
        layout.addWidget(self.count_label)

        prev_btn = QPushButton("\u2191")
        prev_btn.setFixedSize(24, 24)
        prev_btn.clicked.connect(self._find_prev)
        layout.addWidget(prev_btn)

        next_btn = QPushButton("\u2193")
        next_btn.setFixedSize(24, 24)
        next_btn.clicked.connect(self._find_next)
        layout.addWidget(next_btn)

        replace_btn = QPushButton("Replace")
        replace_btn.clicked.connect(self._replace_one)
        layout.addWidget(replace_btn)

        replace_all_btn = QPushButton("All")
        replace_all_btn.clicked.connect(self._replace_all)
        layout.addWidget(replace_all_btn)

        close_btn = QPushButton("\u00d7")
        close_btn.setFixedSize(24, 24)
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)

        layout.addStretch()
        self.hide()

    def show_bar(self):
        self.show()
        self.find_input.setFocus()
        self.find_input.selectAll()

    def _find_flags(self):
        from PyQt5.QtGui import QTextDocument
        flags = QTextDocument.FindFlags()
        if self.case_check.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        return flags

    def _find_next(self):
        text = self.find_input.text()
        if not text:
            return
        found = self.editor.find(text, self._find_flags())
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.Start)
            self.editor.setTextCursor(cursor)
            self.editor.find(text, self._find_flags())
        self._update_count(text)

    def _find_prev(self):
        from PyQt5.QtGui import QTextDocument
        text = self.find_input.text()
        if not text:
            return
        flags = self._find_flags() | QTextDocument.FindBackward
        found = self.editor.find(text, flags)
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(cursor.End)
            self.editor.setTextCursor(cursor)
            self.editor.find(text, flags)
        self._update_count(text)

    def _update_count(self, text):
        content = self.editor.toPlainText()
        if self.case_check.isChecked():
            count = content.count(text)
        else:
            count = content.lower().count(text.lower())
        self.count_label.setText(f"{count} found")

    def _replace_one(self):
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.insertText(self.replace_input.text())
        self._find_next()

    def _replace_all(self):
        text = self.find_input.text()
        replacement = self.replace_input.text()
        if not text:
            return
        content = self.editor.toPlainText()
        if self.case_check.isChecked():
            new_content = content.replace(text, replacement)
        else:
            new_content = re.sub(re.escape(text), replacement, content, flags=re.IGNORECASE)
        if new_content != content:
            self.editor.setPlainText(new_content)
            self.count_label.setText("All replaced")


class CodeEditor(QPlainTextEdit):
    cursor_changed = pyqtSignal(int, int)
    content_modified = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_area = LineNumberArea(self)
        self._highlighter = None
        self._original_text = ""

        font = QFont("JetBrains Mono", 12)
        font.setStyleHint(QFont.Monospace)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(' ') * 4)

        self.blockCountChanged.connect(self._update_line_width)
        self.updateRequest.connect(self._update_line_area)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.textChanged.connect(self._on_text_changed)
        self._update_line_width()

    def set_language(self, lang):
        if self._highlighter:
            self._highlighter.setDocument(None)
        self._highlighter = SyntaxHighlighter(self.document(), lang)

    def set_language_from_filename(self, filename):
        import os
        ext = os.path.splitext(filename)[1].lower()
        lang = EXT_TO_LANG.get(ext)
        if lang:
            self.set_language(lang)

    def mark_saved(self):
        self._original_text = self.toPlainText()

    def is_modified(self):
        return self.toPlainText() != self._original_text

    def _on_text_changed(self):
        if self.is_modified():
            self.content_modified.emit()

    def _on_cursor_position_changed(self):
        cursor = self.textCursor()
        self.cursor_changed.emit(cursor.blockNumber() + 1, cursor.columnNumber() + 1)

    def line_number_width(self):
        digits = max(1, len(str(self.blockCount())))
        return 10 + self.fontMetrics().horizontalAdvance('9') * digits

    def _update_line_width(self):
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_line_area(self, rect, dy):
        if dy:
            self.line_area.scroll(0, dy)
        else:
            self.line_area.update(0, rect.y(), self.line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_area.setGeometry(cr.left(), cr.top(), self.line_number_width(), cr.height())

    def line_number_paint(self, event):
        painter = QPainter(self.line_area)
        painter.fillRect(event.rect(), QColor("#1e1e1e"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        current_block = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#e6edf3") if block_number == current_block else QColor("#505050"))
                painter.drawText(0, top, self.line_area.width() - 4,
                                 self.fontMetrics().height(), Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1
        painter.end()

    def _highlight_current_line(self):
        selections = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#2a2d2e"))
            sel.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            selections.append(sel)
        self.setExtraSelections(selections)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            self.textCursor().insertText("    ")
            return
        if event.key() == Qt.Key_Backtab:
            cursor = self.textCursor()
            cursor.movePosition(cursor.StartOfBlock, cursor.KeepAnchor)
            text = cursor.selectedText()
            if text.startswith("    "):
                cursor.insertText(text[4:])
            return
        super().keyPressEvent(event)
