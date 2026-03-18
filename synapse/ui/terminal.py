import os
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QLineEdit, QHBoxLayout, QLabel
)
from PyQt5.QtCore import Qt, QProcess, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

log = logging.getLogger(__name__)

class TerminalWidget(QWidget):
    def __init__(self, workspace_dir=None, parent=None):
        super().__init__(parent)
        self._cwd = str(workspace_dir) if workspace_dir else str(Path.home())
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_ready_read)
        self._process.finished.connect(self._on_finished)
        
        self._history = []
        self._history_idx = -1
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(28)
        header.setStyleSheet("background: #252526; border-bottom: 1px solid #333;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 0, 8, 0)
        
        self.cwd_label = QLabel(self._cwd)
        self.cwd_label.setStyleSheet("color: #4fc3f7; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
        h_layout.addWidget(self.cwd_label)
        h_layout.addStretch()
        
        layout.addWidget(header)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("JetBrains Mono", 10))
        self.output.setStyleSheet(
            "background: #1e1e1e; color: #cccccc; border: none; padding: 4px;"
        )
        self.output.setMaximumBlockCount(2000)
        layout.addWidget(self.output)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(4, 2, 4, 4)
        input_row.setSpacing(4)
        self.prompt_label = QLabel("$")
        self.prompt_label.setStyleSheet("color: #7ee787; font-family: monospace; font-weight: bold;")
        input_row.addWidget(self.prompt_label)

        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("JetBrains Mono", 10))
        self.input_line.setStyleSheet(
            "background: #2d2d2d; color: #ffffff; border: 1px solid #454545; "
            "border-radius: 2px; padding: 2px 4px;"
        )
        self.input_line.setPlaceholderText("Enter command...")
        self.input_line.returnPressed.connect(self._run_command)
        input_row.addWidget(self.input_line)
        layout.addLayout(input_row)

    def set_cwd(self, path):
        self._cwd = str(path)
        self.cwd_label.setText(self._cwd)

    def _run_command(self):
        cmd = self.input_line.text().strip()
        if not cmd:
            return
            
        self.input_line.clear()
        self._history.append(cmd)
        self._history_idx = len(self._history)

        self.output.appendPlainText(f"$ {cmd}")

        if cmd.startswith("cd "):
            target = cmd[3:].strip()
            new_path = Path(self._cwd) / target
            try:
                new_path = new_path.resolve()
                if new_path.is_dir():
                    self._cwd = str(new_path)
                    self.cwd_label.setText(self._cwd)
                    self.output.appendPlainText(f"[cwd: {self._cwd}]")
                else:
                    self.output.appendPlainText(f"Not a directory: {target}")
            except Exception as e:
                self.output.appendPlainText(f"Error: {e}")
            return

        if cmd == "clear":
            self.output.clear()
            return

        if self._process.state() != QProcess.NotRunning:
            self.output.appendPlainText("[a command is already running]")
            return

        self.input_line.setEnabled(False)
        self._process.setWorkingDirectory(self._cwd)
        
        from ..utils.constants import SYSTEM
        if SYSTEM == "Windows":
            self._process.start("cmd.exe", ["/c", cmd])
        else:
            # Using /bin/bash -c for better environment/alias support
            self._process.start("/bin/bash", ["-c", cmd])

    def _on_ready_read(self):
        data = self._process.readAllStandardOutput().data().decode(errors='replace')
        self.output.insertPlainText(data)
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())

    def _on_finished(self, exit_code, exit_status):
        if exit_code != 0:
            self.output.appendPlainText(f"\n[process exited with code {exit_code}]")
        self.input_line.setEnabled(True)
        self.input_line.setFocus()

    def get_recent_output(self, lines=50):
        """Returns the last N lines of terminal output for AI context."""
        all_text = self.output.toPlainText()
        line_list = all_text.splitlines()
        return "\n".join(line_list[-lines:])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up and self._history:
            self._history_idx = max(0, self._history_idx - 1)
            self.input_line.setText(self._history[self._history_idx])
        elif event.key() == Qt.Key_Down and self._history:
            self._history_idx = min(len(self._history), self._history_idx + 1)
            if self._history_idx < len(self._history):
                self.input_line.setText(self._history[self._history_idx])
            else:
                self.input_line.clear()
        else:
            super().keyPressEvent(event)

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1e1e1e")
        fg = theme.get("fg", "#cccccc")
        input_bg = theme.get("input_bg", "#2d2d2d")
        border = theme.get("border", "#454545")
        accent = theme.get("accent", "#4fc3f7")
        
        self.output.setStyleSheet(f"background: {bg}; color: {fg}; border: none; padding: 4px;")
        self.input_line.setStyleSheet(
            f"background: {input_bg}; color: #ffffff; border: 1px solid {border}; border-radius: 2px; padding: 2px 4px;"
        )
        self.cwd_label.setStyleSheet(f"color: {accent}; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
