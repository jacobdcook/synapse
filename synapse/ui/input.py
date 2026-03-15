import base64
import os
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit,
    QLabel, QSizePolicy, QFileDialog, QFrame, QApplication,
    QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray, QBuffer, QIODevice
from PyQt5.QtGui import QPixmap, QKeyEvent
from ..utils.constants import IMAGE_EXTENSIONS, TEXT_EXTENSIONS

log = logging.getLogger(__name__)


class _FileCompleter(QListWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMaximumHeight(200)
        self.setStyleSheet(
            "QListWidget { background: #1e1e1e; color: #e6edf3; border: 1px solid #444; "
            "font-family: monospace; font-size: 12px; }"
            "QListWidget::item:selected { background: #264f78; }"
        )
        self.itemActivated.connect(self._on_activated)
        self._all_files = []

    def set_files(self, file_list):
        self._all_files = sorted(file_list)

    def show_completions(self, prefix, pos):
        self.clear()
        prefix_lower = prefix.lower()
        matches = [f for f in self._all_files if prefix_lower in f.lower()][:20]
        if not matches:
            self.hide()
            return
        for f in matches:
            self.addItem(QListWidgetItem(f))
        self.setCurrentRow(0)
        self.move(pos)
        self.show()

    def _on_activated(self, item):
        self.file_selected.emit(item.text())
        self.hide()

    def select_current(self):
        current = self.currentItem()
        if current:
            self.file_selected.emit(current.text())
        self.hide()

    def move_selection(self, direction):
        row = self.currentRow() + direction
        if 0 <= row < self.count():
            self.setCurrentRow(row)


class _SlashCompleter(QListWidget):
    command_selected = pyqtSignal(str)

    COMMANDS = [
        ("/clear", "Start a new chat"),
        ("/model", "Switch model"),
        ("/system", "Edit system prompt"),
        ("/search", "Search workspace"),
        ("/summarize", "Summarize to free context"),
        ("/export", "Export conversation (md|html|json|pdf)"),
        ("/stats", "Show conversation stats"),
        ("/mcp", "Show/toggle MCP servers"),
        ("/help", "Show all commands & shortcuts"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMaximumHeight(250)
        self.setStyleSheet(
            "QListWidget { background: #1e1e1e; color: #e6edf3; border: 1px solid #444; "
            "font-family: monospace; font-size: 12px; }"
            "QListWidget::item:selected { background: #264f78; }"
            "QListWidget::item { padding: 4px 8px; }"
        )
        self.itemActivated.connect(self._on_activated)

    def show_completions(self, prefix, pos):
        self.clear()
        prefix_lower = prefix.lower()
        matches = [(cmd, desc) for cmd, desc in self.COMMANDS if prefix_lower in cmd.lower()]
        if not matches:
            self.hide()
            return
        for cmd, desc in matches:
            item = QListWidgetItem(f"{cmd}  —  {desc}")
            item.setData(Qt.UserRole, cmd)
            self.addItem(item)
        self.setCurrentRow(0)
        h = min(250, len(matches) * 28 + 4)
        self.resize(350, h)
        self.move(pos.x(), pos.y() - h)
        self.show()

    def _on_activated(self, item):
        self.command_selected.emit(item.data(Qt.UserRole))
        self.hide()

    def select_current(self):
        current = self.currentItem()
        if current:
            self.command_selected.emit(current.data(Qt.UserRole))
        self.hide()

    def move_selection(self, direction):
        row = self.currentRow() + direction
        if 0 <= row < self.count():
            self.setCurrentRow(row)


class _ChatTextEdit(QPlainTextEdit):
    """QPlainTextEdit that sends on Enter and inserts newline on Shift+Enter."""
    at_mention_requested = pyqtSignal(str, object)  # prefix, cursor_rect
    slash_requested = pyqtSignal(str, object)  # prefix, cursor_rect
    completer_navigate = pyqtSignal(int)  # +1 down, -1 up
    completer_accept = pyqtSignal()
    completer_dismiss = pyqtSignal()

    def __init__(self, submit_callback, parent=None):
        super().__init__(parent)
        self._submit = submit_callback
        self._completer_visible = False

    def set_completer_visible(self, visible):
        self._completer_visible = visible

    def keyPressEvent(self, event):
        if self._completer_visible:
            if event.key() == Qt.Key_Escape:
                self.completer_dismiss.emit()
                return
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.completer_accept.emit()
                return
            if event.key() == Qt.Key_Up:
                self.completer_navigate.emit(-1)
                return
            if event.key() == Qt.Key_Down:
                self.completer_navigate.emit(1)
                return
            if event.key() == Qt.Key_Tab:
                self.completer_accept.emit()
                return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self._submit()
                return
        super().keyPressEvent(event)
        if event.text() or event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            self._check_at_mention()
            self._check_slash()

    def _check_at_mention(self):
        cursor = self.textCursor()
        text = cursor.block().text()
        col = cursor.positionInBlock()
        at_pos = text.rfind("@", 0, col)
        if at_pos < 0:
            return
        if at_pos > 0 and text[at_pos - 1] not in (' ', '\t', ''):
            return
        prefix = text[at_pos + 1:col]
        if ' ' in prefix:
            return
        rect = self.cursorRect()
        global_pos = self.mapToGlobal(rect.bottomLeft())
        self.at_mention_requested.emit(prefix, global_pos)

    def _check_slash(self):
        cursor = self.textCursor()
        text = cursor.block().text()
        col = cursor.positionInBlock()
        if not text.startswith("/") or ' ' in text[:col]:
            if self._completer_visible:
                self.completer_dismiss.emit()
            return
        prefix = text[:col]
        rect = self.cursorRect()
        global_pos = self.mapToGlobal(rect.bottomLeft())
        self.slash_requested.emit(prefix, global_pos)


class InputWidget(QWidget):
    message_submitted = pyqtSignal(str, list, list)  # text, images, file_attachments

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attached_images = []
        self._attached_files = []
        self._workspace_files = []

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 4, 12, 12)
        outer_layout.setSpacing(4)

        self.preview_area = QWidget()
        self.preview_layout = QHBoxLayout(self.preview_area)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.setSpacing(6)
        self.preview_layout.addStretch()
        self.preview_area.hide()
        outer_layout.addWidget(self.preview_area)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.attach_btn = QPushButton("+")
        self.attach_btn.setObjectName("attachBtn")
        self.attach_btn.setToolTip("Attach image or file (drag & drop also works)")
        self.attach_btn.clicked.connect(self._pick_file)
        input_row.addWidget(self.attach_btn, alignment=Qt.AlignBottom)

        self.text_edit = _ChatTextEdit(self._submit)
        self.text_edit.setPlaceholderText("Type a message... (Enter to send, Shift+Enter for new line, @ to mention file)")
        self.text_edit.setMaximumHeight(150)
        self.text_edit.setMinimumHeight(44)
        self.text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.text_edit.textChanged.connect(self._auto_resize)
        self.text_edit.at_mention_requested.connect(self._on_at_mention)
        input_row.addWidget(self.text_edit)

        self._file_completer = _FileCompleter()
        self._file_completer.file_selected.connect(self._insert_file_mention)
        self._file_completer.file_selected.connect(self._hide_completers)

        self._slash_completer = _SlashCompleter()
        self._slash_completer.command_selected.connect(self._insert_slash_command)
        self._slash_completer.command_selected.connect(self._hide_completers)
        self.text_edit.slash_requested.connect(self._on_slash_requested)

        self._active_completer = None
        self.text_edit.completer_navigate.connect(self._on_completer_navigate)
        self.text_edit.completer_accept.connect(self._on_completer_accept)
        self.text_edit.completer_dismiss.connect(self._hide_completers)

        self.send_btn = QPushButton("\u2191")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setToolTip("Send (Enter)")
        self.send_btn.clicked.connect(self._submit)
        input_row.addWidget(self.send_btn, alignment=Qt.AlignBottom)

        self.stop_btn = QPushButton("\u25a0")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setToolTip("Stop generating")
        self.stop_btn.setFixedSize(36, 36)
        self.stop_btn.hide()
        input_row.addWidget(self.stop_btn, alignment=Qt.AlignBottom)

        outer_layout.addLayout(input_row)

        self.char_count_label = QLabel("0 chars | 0 words")
        self.char_count_label.setStyleSheet("color: #555; font-size: 10px; padding-left: 48px;")
        self.text_edit.textChanged.connect(self._update_char_count)
        outer_layout.addWidget(self.char_count_label)

        self.setAcceptDrops(True)

    def _auto_resize(self):
        doc = self.text_edit.document()
        line_count = max(1, doc.blockCount())
        line_height = self.text_edit.fontMetrics().lineSpacing()
        new_height = min(150, max(44, line_count * line_height + 20))
        self.text_edit.setFixedHeight(new_height)

    def _update_char_count(self):
        text = self.text_edit.toPlainText()
        chars = len(text)
        words = len(text.split()) if text.strip() else 0
        self.char_count_label.setText(f"{chars} chars | {words} words")

    def _submit(self):
        text = self.text_edit.toPlainText().strip()
        images = [img[1] for img in self._attached_images]
        files = list(self._attached_files)
        if text or images or files:
            self.message_submitted.emit(text, images, files)
            self.text_edit.clear()
            self._clear_attachments()

    def set_streaming(self, streaming):
        self.send_btn.setVisible(not streaming)
        self.stop_btn.setVisible(streaming)
        self.attach_btn.setEnabled(not streaming)

    def focus_input(self):
        self.text_edit.setFocus()

    def _pick_file(self):
        all_ext = " ".join(f"*{e}" for e in IMAGE_EXTENSIONS + TEXT_EXTENSIONS)
        img_ext = " ".join(f"*{e}" for e in IMAGE_EXTENSIONS)
        txt_ext = " ".join(f"*{e}" for e in TEXT_EXTENSIONS)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Attach Files", "",
            f"All supported ({all_ext});;Images ({img_ext});;Text files ({txt_ext})"
        )
        for path in paths:
            self._add_file(path)

    def _add_file(self, filepath):
        try:
            lower = filepath.lower()
            if lower.endswith(IMAGE_EXTENSIONS):
                with open(filepath, 'rb') as f:
                    data = base64.b64encode(f.read()).decode()
                self._attached_images.append((filepath, data))
            elif lower.endswith(TEXT_EXTENSIONS) or not os.path.splitext(lower)[1]:
                with open(filepath, 'r', errors='replace') as f:
                    content = f.read(500_000)
                name = Path(filepath).name
                self._attached_files.append({"name": name, "content": content})
            self._update_preview()
        except (OSError, IOError):
            pass

    def paste_image_from_clipboard(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime.hasImage():
            image = clipboard.image()
            if image.isNull():
                return False
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QIODevice.WriteOnly)
            image.save(buf, "PNG")
            b64 = base64.b64encode(ba.data()).decode()
            self._attached_images.append(("clipboard.png", b64))
            self._update_preview()
            return True
        return False

    def _remove_attachment(self, att_type, index):
        if att_type == "image" and 0 <= index < len(self._attached_images):
            self._attached_images.pop(index)
        elif att_type == "file" and 0 <= index < len(self._attached_files):
            self._attached_files.pop(index)
        self._update_preview()

    def _update_preview(self):
        while self.preview_layout.count() > 1:
            item = self.preview_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        pos = 0
        for i, (filepath, b64_data) in enumerate(self._attached_images):
            frame = QFrame()
            frame.setStyleSheet("background: #2d2d2d; border-radius: 6px; padding: 2px;")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(4, 4, 4, 4)
            frame_layout.setSpacing(2)

            thumb = QLabel()
            pixmap = QPixmap(filepath)
            if not pixmap.isNull():
                thumb.setPixmap(pixmap.scaled(60, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                thumb.setText(Path(filepath).name[:12])
                thumb.setStyleSheet("color: #aaa; font-size: 10px;")
            frame_layout.addWidget(thumb, alignment=Qt.AlignCenter)

            close_btn = QPushButton("\u00d7")
            close_btn.setObjectName("previewCloseBtn")
            idx = i
            close_btn.clicked.connect(lambda checked, x=idx: self._remove_attachment("image", x))
            frame_layout.addWidget(close_btn, alignment=Qt.AlignCenter)

            self.preview_layout.insertWidget(pos, frame)
            pos += 1

        for i, af in enumerate(self._attached_files):
            frame = QFrame()
            frame.setStyleSheet("background: #2d2d2d; border-radius: 6px; padding: 2px;")
            frame_layout = QVBoxLayout(frame)
            frame_layout.setContentsMargins(4, 4, 4, 4)
            frame_layout.setSpacing(2)

            name_label = QLabel(af["name"][:15])
            name_label.setStyleSheet("color: #4fc3f7; font-size: 10px;")
            frame_layout.addWidget(name_label, alignment=Qt.AlignCenter)

            size_label = QLabel(f"{len(af['content']):,} chars")
            size_label.setStyleSheet("color: #888; font-size: 9px;")
            frame_layout.addWidget(size_label, alignment=Qt.AlignCenter)

            close_btn = QPushButton("\u00d7")
            close_btn.setObjectName("previewCloseBtn")
            idx = i
            close_btn.clicked.connect(lambda checked, x=idx: self._remove_attachment("file", x))
            frame_layout.addWidget(close_btn, alignment=Qt.AlignCenter)

            self.preview_layout.insertWidget(pos, frame)
            pos += 1

        has_attachments = len(self._attached_images) > 0 or len(self._attached_files) > 0
        self.preview_area.setVisible(has_attachments)

    def _clear_attachments(self):
        self._attached_images.clear()
        self._attached_files.clear()
        self._update_preview()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                path = url.toLocalFile().lower()
                if path.endswith(IMAGE_EXTENSIONS) or path.endswith(TEXT_EXTENSIONS):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            lower = filepath.lower()
            if lower.endswith(IMAGE_EXTENSIONS) or lower.endswith(TEXT_EXTENSIONS):
                self._add_file(filepath)

    def set_workspace_files(self, file_list):
        self._workspace_files = file_list
        self._file_completer.set_files(file_list)

    def _on_at_mention(self, prefix, global_pos):
        if not self._workspace_files:
            return
        self._active_completer = self._file_completer
        self.text_edit.set_completer_visible(True)
        self._file_completer.show_completions(prefix, global_pos)
        if not self._file_completer.isVisible():
            self._hide_completers()

    def _on_slash_requested(self, prefix, global_pos):
        self._active_completer = self._slash_completer
        self.text_edit.set_completer_visible(True)
        self._slash_completer.show_completions(prefix, global_pos)
        if not self._slash_completer.isVisible():
            self._hide_completers()

    def _hide_completers(self):
        self._file_completer.hide()
        self._slash_completer.hide()
        self._active_completer = None
        self.text_edit.set_completer_visible(False)

    def _on_completer_navigate(self, direction):
        if self._active_completer:
            self._active_completer.move_selection(direction)

    def _on_completer_accept(self):
        if self._active_completer:
            self._active_completer.select_current()

    def _insert_file_mention(self, filename):
        cursor = self.text_edit.textCursor()
        text = cursor.block().text()
        col = cursor.positionInBlock()
        at_pos = text.rfind("@", 0, col)
        if at_pos >= 0:
            cursor.movePosition(cursor.StartOfBlock)
            cursor.movePosition(cursor.Right, cursor.MoveAnchor, at_pos)
            cursor.movePosition(cursor.Right, cursor.KeepAnchor, col - at_pos)
            cursor.insertText(f"@{filename} ")
        self.text_edit.setFocus()

    def _insert_slash_command(self, command):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.StartOfBlock)
        cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)
        cursor.insertText(command)
        self.text_edit.setFocus()
        self._submit()
