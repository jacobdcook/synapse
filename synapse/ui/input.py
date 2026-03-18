import base64
import os
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QPlainTextEdit,
    QLineEdit, QLabel, QSizePolicy, QFileDialog, QFrame, QApplication,
    QListWidget, QListWidgetItem, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray, QBuffer, QIODevice, QRect
from PyQt5.QtGui import QPixmap, QKeyEvent, QPainter, QColor, QBrush, QPen
from ..utils.constants import IMAGE_EXTENSIONS, TEXT_EXTENSIONS
from ..utils.variables import VariableResolver

log = logging.getLogger(__name__)

from PyQt5.QtWidgets import QDialog, QFormLayout, QDialogButtonBox

class VariableDialog(QDialog):
    """Dialog to fill in custom {{variables}} from the prompt."""
    def __init__(self, variables, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fill Variables")
        self.setMinimumWidth(350)
        
        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.inputs = {}
        
        for var in sorted(list(variables)):
            edit = QLineEdit()
            self.form.addRow(f"{var}:", edit)
            self.inputs[var] = edit
            
        layout.addLayout(self.form)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_values(self):
        return {var: edit.text() for var, edit in self.inputs.items()}


class _FileCompleter(QListWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMaximumHeight(200)
        self.setStyleSheet(
            "QListWidget { background: #252526; color: #cccccc; border: 1px solid #454545; "
            "font-family: 'Segoe UI', sans-serif; font-size: 11px; outline: none; }"
            "QListWidget::item { padding: 4px 8px; border-bottom: 1px solid #333333; }"
            "QListWidget::item:selected { background: #094771; color: white; }"
            "QListWidget::item:hover { background: #2a2d2e; }"
        )
        self.itemActivated.connect(self._on_activated)
        self._all_files = []
        self._icons = {
            "folder": "\ud83d\udcc1",
            "file": "\ud83d\udcc4",
            "python": "\ud83d\udc0d",
            "markdown": "\ud83d\udcd1"
        }

    def set_files(self, file_list):
        self._all_files = sorted(file_list)

    def show_completions(self, prefix, pos):
        self.clear()
        prefix_lower = prefix.lower()
        
        # Special mentions
        specials = ["terminal"]
        matched_specials = [s for s in specials if prefix_lower in s]
        
        # File matches
        matched_files = [f for f in self._all_files if prefix_lower in f.lower()][:20]
        matches = matched_specials + matched_files
        
        if not matches:
            self.hide()
            return
            
        for f in matches:
            if f == "terminal":
                icon = "\ud83d\udda5"
            elif "." not in f: icon = self._icons["folder"]
            elif f.endswith(".py"): icon = self._icons["python"]
            elif f.endswith(".md"): icon = self._icons["markdown"]
            else: icon = self._icons["file"]
            
            item = QListWidgetItem(f"{icon}  {f}")
            item.setData(Qt.UserRole, f)
            self.addItem(item)
            
        self.setCurrentRow(0)
        
        # Calculate height based on items
        h = min(200, self.count() * 26 + 4)
        self.resize(300, h)
        
        # Position above or below cursor depending on space
        self.move(pos.x(), pos.y() - h - 5)
        self.show()

    def _on_activated(self, item):
        self.file_selected.emit(item.data(Qt.UserRole))
        self.hide()

    def select_current(self):
        current = self.currentItem()
        if current:
            self.file_selected.emit(current.data(Qt.UserRole))
        self.hide()

    def move_selection(self, direction):
        row = self.currentRow() + direction
        if 0 <= row < self.count():
            self.setCurrentRow(row)


class _SlashCompleter(QListWidget):
    command_selected = pyqtSignal(str)

    COMMANDS = [
        ("/clear", "Start a new chat session"),
        ("/model", "Switch the active AI model"),
        ("/system", "Edit the hidden system prompt"),
        ("/search", "Semantic search across workspace"),
        ("/summarize", "Summarize current thread to save context"),
        ("/replay", "Playback previous session steps"),
        ("/export", "Export chat as MD, HTML, or JSON"),
        ("/stats", "Show token and message statistics"),
        ("/mcp", "Manage Model Context Protocol servers"),
        ("/rag", "Toggle RAG (Knowledge Retrieval)"),
        ("/memory", "Manage AI's long-term memory"),
        ("/diff", "View changes in the active file"),
        ("/file", "Open a specific file in the editor"),
        ("/terminal", "Focus the integrated terminal"),
        ("/help", "Show all commands and shortcuts"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setMaximumHeight(250)
        self.setStyleSheet(
            "QListWidget { background: #252526; color: #cccccc; border: 1px solid #454545; "
            "font-family: 'Segoe UI', sans-serif; font-size: 11px; outline: none; }"
            "QListWidget::item { padding: 6px 10px; border-bottom: 1px solid #333333; }"
            "QListWidget::item:selected { background: #094771; color: white; }"
            "QListWidget::item:hover { background: #2a2d2e; }"
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
        # Position above cursor
        self.move(pos.x(), pos.y() - h - 5)
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


class AudioVisualizer(QWidget):
    """A simple pulsating waveform visualizer for mic input."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self._level = 0.0
        self._bars = [0.0] * 20
        self.hide()

    def set_level(self, level):
        self._level = level
        # Shift bars and add new value with some randomness for 'life'
        import random
        self._bars.pop(0)
        self._bars.append(level + random.uniform(0, 0.05))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        spacing = 4
        bar_width = (self.width() - (len(self._bars) * spacing)) / len(self._bars)
        
        for i, val in enumerate(self._bars):
            h = max(2, val * self.height())
            y = (self.height() - h) / 2
            x = i * (bar_width + spacing)
            
            # Use accent-like color (blue-ish)
            color = QColor("#58a6ff")
            # Fade out older bars
            alpha = int(255 * (i / len(self._bars)))
            color.setAlpha(alpha)
            
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRect(int(x), int(y), int(bar_width), int(h)), 2, 2)


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
            elif event.modifiers() & Qt.ControlModifier:
                self._submit()
                return
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
            if self._completer_visible: self.completer_dismiss.emit()
            return
        # Must be at start of block or preceded by space
        if at_pos > 0 and text[at_pos - 1] not in (' ', '\t'):
            if self._completer_visible: self.completer_dismiss.emit()
            return
        prefix = text[at_pos + 1:col]
        if ' ' in prefix:
            if self._completer_visible: self.completer_dismiss.emit()
            return
        rect = self.cursorRect()
        global_pos = self.mapToGlobal(rect.topLeft()) # Use topLeft for better alignment with "above cursor" move
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
        global_pos = self.mapToGlobal(rect.topLeft())
        self.slash_requested.emit(prefix, global_pos)


class _QueueDisplay(QWidget):
    """Shows queued messages as dismissible chips above the input."""
    remove_requested = pyqtSignal(int)
    force_send_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(48, 0, 48, 0)
        self._layout.setSpacing(3)
        self.hide()

    def update_queue(self, queue):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not queue:
            self.hide()
            return
        for i, entry in enumerate(queue):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            num_label = QLabel(f"#{i+1}")
            num_label.setStyleSheet("color: #888; font-size: 10px; min-width: 20px;")
            row_layout.addWidget(num_label)
            preview = entry["text"][:80] + ("..." if len(entry["text"]) > 80 else "")
            text_label = QLabel(preview)
            text_label.setStyleSheet(
                "color: #ccc; font-size: 11px; background: #2a2d32; border-radius: 4px; "
                "padding: 3px 8px; border-left: 2px solid #4fc3f7;"
            )
            text_label.setWordWrap(False)
            row_layout.addWidget(text_label, stretch=1)
            close_btn = QPushButton("\u00d7")
            close_btn.setFixedSize(18, 18)
            close_btn.setStyleSheet(
                "QPushButton { color: #888; background: transparent; border: none; font-size: 12px; }"
                "QPushButton:hover { color: #ff6b6b; }"
            )
            idx = i
            close_btn.clicked.connect(lambda checked, x=idx: self.remove_requested.emit(x))
            row_layout.addWidget(close_btn)
            self._layout.addWidget(row)
        self.show()


class InputWidget(QWidget):
    message_submitted = pyqtSignal(str, list, list)  # text, images, file_attachments
    search_toggled = pyqtSignal(bool)
    voice_toggled = pyqtSignal(bool)
    mic_triggered = pyqtSignal(bool) # True = start, False = stop
    hands_free_toggled = pyqtSignal(bool)
    sync_toggled = pyqtSignal(bool)
    force_send_requested = pyqtSignal()  # stop current generation, send next queued

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attached_images = []
        self._attached_files = []
        self._workspace_files = []
        self._streaming = False
        self._message_queue = []  # list of {"text": str, "images": list, "files": list}
        self.resolver = VariableResolver()

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

        self._queue_display = _QueueDisplay()
        self._queue_display.remove_requested.connect(self._remove_from_queue)
        self._queue_display.force_send_requested.connect(self.force_send_requested.emit)
        outer_layout.addWidget(self._queue_display)

        self.visualizer = AudioVisualizer()
        self.visualizer.hide()
        outer_layout.addWidget(self.visualizer)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.attach_btn = QPushButton("+")
        self.attach_btn.setObjectName("attachBtn")
        self.attach_btn.setToolTip("Attach image or file (drag & drop also works)")
        self.attach_btn.clicked.connect(self._pick_file)
        input_row.addWidget(self.attach_btn, alignment=Qt.AlignBottom)

        self.agent_mode_btn = QPushButton("⚡")
        self.agent_mode_btn.setCheckable(True)
        self.agent_mode_btn.setToolTip("Agent Mode: AI autonomously uses tools in a loop")
        self.agent_mode_btn.setFixedSize(32, 32)
        self.agent_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #444;
                border-radius: 6px;
                font-size: 16px;
                color: #888;
            }
            QPushButton:hover {
                background-color: #333;
            }
            QPushButton:checked {
                background-color: #f1c40f;
                color: #2c3e50;
                border: 1px solid #f1c40f;
            }
        """)
        input_row.addWidget(self.agent_mode_btn, alignment=Qt.AlignBottom)

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

        self.web_search_btn = QPushButton("\ud83c\udf10") # Globe icon
        self.web_search_btn.setObjectName("webSearchBtn")
        self.web_search_btn.setCheckable(True)
        self.web_search_btn.setToolTip("Search Web (Grounding)")
        self.web_search_btn.setFixedSize(36, 36)
        self.web_search_btn.setStyleSheet(
            "QPushButton { background: #2d2d2d; color: #888; border: none; border-radius: 6px; font-size: 18px; }"
            "QPushButton:checked { background: #264f78; color: #4fc3f7; }"
            "QPushButton:hover { background: #3d3d3d; }"
        )
        self.web_search_btn.clicked.connect(lambda checked: self.search_toggled.emit(checked))
        input_row.addWidget(self.web_search_btn, alignment=Qt.AlignBottom)

        self.mic_btn = QPushButton("\ud83c\udf99\ufe0f") # Mic icon
        self.mic_btn.setObjectName("micBtn")
        self.mic_btn.setCheckable(True)
        self.mic_btn.setToolTip("Voice Input (Record)")
        self.mic_btn.setFixedSize(36, 36)
        self.mic_btn.setStyleSheet(
            "QPushButton { background: #2d2d2d; color: #888; border: none; border-radius: 6px; font-size: 18px; }"
            "QPushButton:checked { background: #c0392b; color: white; }"
            "QPushButton:hover { background: #3d3d3d; }"
        )
        self.mic_btn.clicked.connect(self._on_mic_clicked)
        self.mic_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mic_btn.customContextMenuRequested.connect(self._on_mic_context_menu)
        input_row.addWidget(self.mic_btn, alignment=Qt.AlignBottom)

        self.voice_btn = QPushButton("\ud83d\udd0a") # Speaker icon
        self.voice_btn.setObjectName("voiceBtn")
        self.voice_btn.setCheckable(True)
        self.voice_btn.setToolTip("Auto-Read Responses")
        self.voice_btn.setFixedSize(36, 36)
        self.voice_btn.setStyleSheet(
            "QPushButton { background: #2d2d2d; color: #888; border: none; border-radius: 6px; font-size: 18px; }"
            "QPushButton:checked { background: #264f78; color: #4fc3f7; }"
            "QPushButton:hover { background: #3d3d3d; }"
        )
        self.voice_btn.clicked.connect(lambda checked: self.voice_toggled.emit(checked))
        input_row.addWidget(self.voice_btn, alignment=Qt.AlignBottom)

        self.sync_btn = QPushButton("\u21c4") # Sync icon
        self.sync_btn.setObjectName("syncBtn")
        self.sync_btn.setCheckable(True)
        self.sync_btn.setToolTip("Sync Input (Send to all splits)")
        self.sync_btn.setFixedSize(36, 36)
        self.sync_btn.setStyleSheet("""
            QPushButton { background: #2d2d2d; color: #888; border: none; border-radius: 6px; font-size: 18px; }
            QPushButton:checked { background: #264f78; color: #4fc3f7; }
            QPushButton:hover { background: #3d3d3d; }
        """)
        self.sync_btn.clicked.connect(self.sync_toggled.emit)
        input_row.addWidget(self.sync_btn, alignment=Qt.AlignBottom)

        self.force_btn = QPushButton("\u21e7")
        self.force_btn.setObjectName("forceBtn")
        self.force_btn.setToolTip("Force send — stops current generation and sends this message")
        self.force_btn.setFixedSize(36, 36)
        self.force_btn.setStyleSheet(
            "QPushButton { background: #c0392b; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; }"
            "QPushButton:hover { background: #e74c3c; }"
        )
        self.force_btn.hide()
        self.force_btn.clicked.connect(self._force_send)
        input_row.addWidget(self.force_btn, alignment=Qt.AlignBottom)

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
        
        if not (text or images or files):
            return

        # Handle Variables (F8)
        all_vars = self.resolver.find_variables(text)
        built_ins = set(self.resolver.get_built_in_vars().keys())
        user_vars_needed = all_vars - built_ins
        
        user_vals = {}
        if user_vars_needed:
            dlg = VariableDialog(user_vars_needed, self)
            if dlg.exec_() == QDialog.Accepted:
                user_vals = dlg.get_values()
            else:
                return # User cancelled

        text = self.resolver.resolve_all(text, user_vals)

        if self._streaming:
            self._message_queue.append({"text": text, "images": images, "files": files})
            self.text_edit.clear()
            self._clear_attachments()
            self._queue_display.update_queue(self._message_queue)
        else:
            self.message_submitted.emit(text, images, files)
            self.text_edit.clear()
            self._clear_attachments()

    def _force_send(self):
        text = self.text_edit.toPlainText().strip()
        images = [img[1] for img in self._attached_images]
        files = list(self._attached_files)
        if text or images or files:
            self._message_queue.insert(0, {"text": text, "images": images, "files": files})
            self.text_edit.clear()
            self._clear_attachments()
            self._queue_display.update_queue(self._message_queue)
        if self._message_queue:
            self.force_send_requested.emit()

    def _remove_from_queue(self, index):
        if 0 <= index < len(self._message_queue):
            self._message_queue.pop(index)
            self._queue_display.update_queue(self._message_queue)

    def pop_queued_message(self):
        if self._message_queue:
            msg = self._message_queue.pop(0)
            self._queue_display.update_queue(self._message_queue)
            return msg
        return None

    def clear_queue(self):
        self._message_queue.clear()
        self._queue_display.update_queue(self._message_queue)

    def has_queued(self):
        return len(self._message_queue) > 0

    def set_streaming(self, streaming):
        self._streaming = streaming
        self.send_btn.setVisible(not streaming)
        self.stop_btn.setVisible(streaming)
        self.attach_btn.setEnabled(not streaming)
        self.web_search_btn.setEnabled(not streaming)
        self.mic_btn.setEnabled(not streaming)
        self.force_btn.setVisible(streaming)
        if streaming:
            self.text_edit.setPlaceholderText("Type to queue next message... (Enter to queue, force-send button to interrupt)")
        else:
            self.text_edit.setPlaceholderText("Type a message... (Enter to send, Shift+Enter for new line, @ to mention file)")
            self._queue_display.update_queue(self._message_queue)

    def _on_mic_clicked(self, checked):
        if not hasattr(self, "_hands_free"): self._hands_free = False
        if checked:
            self.visualizer.show()
            self.mic_btn.setToolTip("Stop Recording")
            self.mic_btn.setStyleSheet(
                f"QPushButton {{ background: {'#264f78' if self._hands_free else '#c0392b'}; color: white; border: none; border-radius: 6px; font-size: 18px; }}"
            )
            self.text_edit.setPlaceholderText("Recording... Click mic again to stop.")
        else:
            self.visualizer.hide()
            self.mic_btn.setToolTip("Voice Input (Record)")
            self.mic_btn.setStyleSheet(
                "QPushButton { background: #2d2d2d; color: #888; border: none; border-radius: 6px; font-size: 18px; }"
                "QPushButton:hover { background: #3d3d3d; }"
            )
            self.text_edit.setPlaceholderText("Type a message... (Enter to send, Shift+Enter for new line, @ to mention file)")
        self.mic_triggered.emit(checked)

    def _on_mic_context_menu(self, pos):
        from PyQt5.QtWidgets import QMenu, QAction
        menu = QMenu(self)
        hands_free_act = QAction("Hands-free Mode", self, checkable=True)
        # Use a local attribute to track hands-free state if not already in MainWindow
        if not hasattr(self, "_hands_free"): self._hands_free = False
        hands_free_act.setChecked(self._hands_free)
        
        def toggle(checked):
            self._hands_free = checked
            self.hands_free_toggled.emit(checked)
            if checked:
                self.mic_btn.setToolTip("Hands-free Mode (Active)")
            else:
                self.mic_btn.setToolTip("Voice Input (Record)")

        hands_free_act.toggled.connect(toggle)
        menu.addAction(hands_free_act)
        menu.exec_(self.mic_btn.mapToGlobal(pos))

    def append_text(self, text):
        self.text_edit.appendPlainText(text)
        self.text_edit.setFocus()

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
            file_size = os.path.getsize(filepath)
            lower = filepath.lower()
            if lower.endswith(IMAGE_EXTENSIONS):
                if file_size > 10 * 1024 * 1024:
                    log.warning(f"Skipping oversized image ({file_size // 1024 // 1024}MB): {filepath}")
                    return
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

    def add_image_pixmap(self, pixmap, filename="screenshot.png"):
        if pixmap.isNull():
            return
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        pixmap.save(buf, "PNG")
        b64 = base64.b64encode(ba.data()).decode()
        self._attached_images.append((filename, b64))
        self._update_preview()

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
            cursor.beginEditBlock()
            cursor.movePosition(cursor.StartOfBlock)
            cursor.movePosition(cursor.Right, cursor.MoveAnchor, at_pos)
            cursor.movePosition(cursor.Right, cursor.KeepAnchor, col - at_pos)
            cursor.insertText(f"@{filename} ")
            cursor.endEditBlock()
        self.text_edit.setFocus()

    def _insert_slash_command(self, command):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.StartOfBlock)
        cursor.movePosition(cursor.EndOfBlock, cursor.KeepAnchor)
        cursor.insertText(command)
        self.text_edit.setFocus()
        self._submit()

    def update_mic_level(self, level):
        self.visualizer.set_level(level)

    def apply_theme(self, theme):
        bg = theme.get("input_bg", "#2d2d2d")
        border = theme.get("border", "#3e3e3e")
        accent = theme.get("accent", "#58a6ff")
        fg = theme.get("fg", "#888")
        btn_style = (
            f"QPushButton {{ background: {bg}; color: {fg}; border: none; border-radius: 6px; font-size: 18px; }}"
            f"QPushButton:checked {{ background: {accent}; color: white; }}"
            f"QPushButton:hover {{ background: {border}; }}"
        )
        for btn in (self.web_search_btn, self.mic_btn, self.voice_btn, self.sync_btn):
            btn.setStyleSheet(btn_style)
