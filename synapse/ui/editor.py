import re
import os
from typing import List, Dict, Any, Optional
from PyQt5.QtWidgets import (
    QPlainTextEdit, QWidget, QTextEdit, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QCheckBox, QShortcut
)
from PyQt5.QtCore import QSize, Qt, pyqtSignal, QRegularExpression, QTimer, QPoint
from PyQt5.QtGui import (
    QColor, QTextCharFormat, QFont, QSyntaxHighlighter,
    QPainter, QKeySequence, QTextCursor, QFontMetrics, QPolygon
)
from ..core.completion_provider import CompletionWorker


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

    def mousePressEvent(self, event):
        line = self.editor.cursorForPosition(event.pos()).blockNumber() + 1
        self.editor.toggle_breakpoint(line)


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
            cursor = self.editor.textCursor()
            cursor.beginEditBlock()
            cursor.select(cursor.Document)
            cursor.insertText(new_content)
            cursor.endEditBlock()
            self.count_label.setText("All replaced")


class AutocompleteManager(QWidget):
    """Coordinates ghost text completions for CodeEditor."""
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.ghost_text = ""
        self.worker: Optional[CompletionWorker] = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._request_completion)
        self.enabled = True

    def trigger(self):
        if not self.enabled: return
        self.ghost_text = ""
        self.timer.start(350) # Debounce 350ms

    def _request_completion(self):
        if self.worker:
            self.worker.terminate()
            self.worker = None

        cursor = self.editor.textCursor()
        doc = self.editor.toPlainText()
        pos = cursor.position()
        
        prefix = doc[:pos]
        suffix = doc[pos:]
        
        # Limit context to avoid heavy requests
        prefix = prefix[-2000:]
        suffix = suffix[:1000]

        model = "qwen2.5-coder:1.5b" # Default completion model
        self.worker = CompletionWorker(prefix, suffix, model=model)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_finished(self, text):
        if text:
            self.ghost_text = text
            self.editor.viewport().update()
        self.worker = None

    def accept(self):
        if self.ghost_text:
            cursor = self.editor.textCursor()
            cursor.insertText(self.ghost_text)
            self.ghost_text = ""
            self.editor.viewport().update()
            return True
        return False

    def clear(self):
        if self.ghost_text:
            self.ghost_text = ""
            self.editor.viewport().update()
            return True
        return False

    def paint_ghost_text(self, painter):
        if not self.ghost_text: return
        
        cursor = self.editor.textCursor()
        rect = self.editor.cursorRect(cursor)
        
        # Calculate exactly where to start painting
        # We need to account for scrolls
        x = rect.left()
        y = rect.top()
        
        painter.save()
        painter.setPen(QColor("#8b949e")) # Faint gray
        painter.setFont(self.editor.font())
        
        # Draw line by line if multi-line
        lines = self.ghost_text.split('\n')
        fh = self.editor.fontMetrics().height()
        for i, line in enumerate(lines):
            painter.drawText(x if i == 0 else self.editor.viewportMargins().left(), 
                             y + (i * fh), 
                             self.editor.viewport().width(), 
                             fh, 
                             Qt.AlignLeft, 
                             line)
        painter.restore()


class CodeEditor(QPlainTextEdit):
    cursor_changed = pyqtSignal(int, int)
    content_modified = pyqtSignal()
    request_lsp_hover = pyqtSignal(int, int) # line, column
    breakpoint_toggled = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.autocomplete = AutocompleteManager(self)
        self.line_area = LineNumberArea(self)
        self._highlighter: Optional[SyntaxHighlighter] = None
        self._original_text = ""
        self._lsp_manager: Optional[Any] = None # Avoid circular import
        self._filepath: Optional[str] = None
        self._lang: Optional[str] = None
        self._diagnostics: List[Dict[str, Any]] = []
        
        self.blockCountChanged.connect(self._update_line_width)
        self.updateRequest.connect(self._update_line_area)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.textChanged.connect(self._on_text_changed)

        self.breakpoints = set()
        self.execution_line = -1
        self.coverage_data = {} # {line_no: status}
        self._update_line_width()

    def set_lsp_manager(self, manager, filepath):
        self._lsp_manager = manager
        self._filepath = filepath
        self._lang = self._get_lang_from_ext(filepath)
        if self._lsp_manager and self._lang:
            self._lsp_manager.did_open(self._filepath, self._lang, self.toPlainText())

    def _get_lang_from_ext(self, filename):
        ext = os.path.splitext(filename)[1].lower()
        return EXT_TO_LANG.get(ext)

    def set_diagnostics(self, diagnostics):
        """Sets and renders LSP diagnostics (squiggles)."""
        self._diagnostics = diagnostics
        self._render_diagnostics()

    def _render_diagnostics(self):
        extra_selections = []
        
        # Current line highlight still needed
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            hl_color = getattr(self, '_current_line_bg', QColor("#2a2d2e"))
            sel.format.setBackground(hl_color)
            sel.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra_selections.append(sel)

        for diag in self._diagnostics:
            range_info = diag.get("range", {})
            start = range_info.get("start", {})
            end = range_info.get("end", {})
            
            cursor = self.textCursor()
            cursor.clearSelection()
            
            # Convert LSP line/char (0-indexed) to QTextCursor position
            # This is a bit expensive but necessary for squiggles
            pos_start = self.document().findBlockByLineNumber(start.get("line", 0)).position() + start.get("character", 0)
            pos_end = self.document().findBlockByLineNumber(end.get("line", 0)).position() + end.get("character", 0)
            
            cursor.setPosition(pos_start)
            cursor.setPosition(pos_end, QTextCursor.KeepAnchor)
            
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cursor
            
            severity = diag.get("severity", 1) # 1=Error, 2=Warning
            color = QColor("#f44336") if severity == 1 else QColor("#ff9800")
            
            fmt = QTextCharFormat()
            fmt.setUnderlineColor(color)
            fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            sel.format = fmt
            extra_selections.append(sel)
            
        self.setExtraSelections(extra_selections)

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
            if self._lsp_manager:
                self._lsp_timer.start(500) # Debounce 500ms
            self.autocomplete.trigger()

    def _sync_lsp(self):
        if self._lsp_manager and self._filepath and self._lang:
            self._lsp_manager.did_change(self._filepath, self._lang, self.toPlainText())

    def _on_cursor_position_changed(self):
        self._highlight_current_line()
        cursor = self.textCursor()
        self.cursor_changed.emit(cursor.blockNumber() + 1, cursor.columnNumber() + 1)

    def toggle_breakpoint(self, line):
        if line in self.breakpoints:
            self.breakpoints.remove(line)
        else:
            self.breakpoints.add(line)
        self.breakpoint_toggled.emit(line)
        self.line_area.update()

    def set_coverage(self, coverage_data):
        self.coverage_data = coverage_data
        self.line_area.update()

    def set_execution_line(self, line):
        self.execution_line = line
        self.line_area.update()
        if line > 0:
            block = self.document().findBlockByLineNumber(line - 1)
            cursor = self.textCursor()
            cursor.setPosition(block.position())
            self.setTextCursor(cursor)
        self._highlight_current_line()

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

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        self.autocomplete.paint_ghost_text(painter)
        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_area.setGeometry(cr.left(), cr.top(), self.line_number_width(), cr.height())

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            if self.autocomplete.accept():
                return
            self.textCursor().insertText("    ")
            return
        if event.key() == Qt.Key_Escape:
            if self.autocomplete.clear():
                return
        if event.key() == Qt.Key_Backtab:
            cursor = self.textCursor()
            cursor.movePosition(cursor.StartOfBlock, cursor.KeepAnchor)
            text = cursor.selectedText()
            if text.startswith("    "):
                cursor.insertText(text[4:])
            return
        super().keyPressEvent(event)

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        fg = theme.get("fg", "#e6edf3")
        input_bg = theme.get("input_bg", "#0d1117")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#58a6ff")
        sidebar_bg = theme.get("sidebar_bg", "#1e1f23")

        self.setStyleSheet(
            f"background: {input_bg}; color: {fg}; border: 1px solid {border};"
        )
        self._line_number_bg = QColor(sidebar_bg)
        self._line_number_fg = QColor(fg)
        self._line_number_dim = QColor(border)
        self._current_line_bg = QColor(sidebar_bg)
        self.viewport().update()
        self.line_area.update()

    def line_number_paint(self, event):
        painter = QPainter(self.line_area)
        bg_color = getattr(self, '_line_number_bg', QColor("#1e1e1e"))
        fg_color = getattr(self, '_line_number_fg', QColor("#e6edf3"))
        dim_color = getattr(self, '_line_number_dim', QColor("#505050"))
        painter.fillRect(event.rect(), bg_color)

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        current_block = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                line_num = block_number + 1
                
                # Draw Breakpoint
                if line_num in self.breakpoints:
                    painter.setBrush(QColor("#f44336"))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(5, top + 2, 12, 12)
                
                # Draw Execution Highlight (Yellow Arrow)
                if line_num == self.execution_line:
                    painter.setBrush(QColor("#e5c07b"))
                    painter.setPen(Qt.NoPen)
                    points = [
                        QPoint(2, top + 2),
                        QPoint(10, top + 8),
                        QPoint(2, top + 14)
                    ]
                    painter.drawPolygon(QPolygon(points))
                
                # Draw Coverage
                if line_num in self.coverage_data:
                    status = self.coverage_data[line_num]
                    color = QColor("#3fb950") if status == "covered" else QColor("#f85149")
                    painter.fillRect(self.line_area.width() - 4, top, 4, self.fontMetrics().height(), color)

                painter.setPen(fg_color if block_number == current_block else dim_color)
                painter.drawText(0, top, self.line_area.width() - 4,
                                 self.fontMetrics().height(), Qt.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1
        painter.end()

    def _highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            # Current editing line
            sel = QTextEdit.ExtraSelection()
            hl_color = getattr(self, '_current_line_bg', QColor("#2a2d2e"))
            sel.format.setBackground(hl_color)
            sel.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra_selections.append(sel)
            
        if self.execution_line > 0:
            # Execution line highlight
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#3e3e10")) # Dark yellow/brown
            sel.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            block = self.document().findBlockByLineNumber(self.execution_line - 1)
            cursor = self.textCursor()
            cursor.setPosition(block.position())
            sel.cursor = cursor
            extra_selections.append(sel)
            
        self.setExtraSelections(extra_selections)
