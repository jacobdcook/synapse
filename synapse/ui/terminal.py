import os
import subprocess
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QLineEdit, QHBoxLayout, QLabel
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QTextCharFormat

log = logging.getLogger(__name__)


class CommandRunner(QThread):
    output_ready = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, command, cwd=None):
        super().__init__()
        self.command = command
        self.cwd = cwd

    def run(self):
        try:
            import shlex
            proc = subprocess.Popen(
                shlex.split(self.command),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.cwd,
            )
            for line in proc.stdout:
                self.output_ready.emit(line)
            proc.wait()
            self.finished_signal.emit(proc.returncode)
        except FileNotFoundError:
            self.output_ready.emit(f"Command not found: {self.command.split()[0]}\n")
            self.finished_signal.emit(127)
        except Exception as e:
            self.output_ready.emit(f"Error: {e}\n")
            self.finished_signal.emit(1)


class TerminalWidget(QWidget):
    def __init__(self, workspace_dir=None, parent=None):
        super().__init__(parent)
        self._cwd = str(workspace_dir) if workspace_dir else str(Path.home())
        self._runner = None
        self._history = []
        self._history_idx = -1
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setFixedHeight(28)
        header.setStyleSheet("background: #1e1e1e; border-bottom: 1px solid #333;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 0, 8, 0)
        self.cwd_label = QLabel(self._cwd)
        self.cwd_label.setStyleSheet("color: #4fc3f7; font-size: 11px; font-family: monospace;")
        h_layout.addWidget(self.cwd_label)
        h_layout.addStretch()
        layout.addWidget(header)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("JetBrains Mono", 11))
        self.output.setStyleSheet(
            "background: #0d1117; color: #e6edf3; border: none; padding: 4px;"
        )
        self.output.setMaximumBlockCount(5000)
        layout.addWidget(self.output)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(4, 2, 4, 4)
        self.prompt_label = QLabel("$")
        self.prompt_label.setStyleSheet("color: #7ee787; font-family: monospace; font-weight: bold;")
        input_row.addWidget(self.prompt_label)

        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("JetBrains Mono", 11))
        self.input_line.setStyleSheet(
            "background: #161b22; color: #e6edf3; border: 1px solid #30363d; "
            "border-radius: 4px; padding: 4px;"
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
                    self.output.appendPlainText(f"Changed to {self._cwd}")
                else:
                    self.output.appendPlainText(f"Not a directory: {target}")
            except Exception as e:
                self.output.appendPlainText(f"Error: {e}")
            return

        if cmd == "clear":
            self.output.clear()
            return

        self.input_line.setEnabled(False)
        self._runner = CommandRunner(cmd, self._cwd)
        self._runner.output_ready.connect(self._on_output)
        self._runner.finished_signal.connect(self._on_finished)
        self._runner.start()

    def _on_output(self, text):
        self.output.insertPlainText(text)
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())

    def _on_finished(self, code):
        if code != 0:
            self.output.appendPlainText(f"[exit {code}]")
        self.output.appendPlainText("")
        self.input_line.setEnabled(True)
        self.input_line.setFocus()

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
