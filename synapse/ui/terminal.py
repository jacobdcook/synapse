"""Terminal V2: PTY, ANSI, multiplexer, history."""
import os
import re
import json
import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QLineEdit, QHBoxLayout, QLabel,
    QTabWidget, QMenu
)
from PyQt5.QtCore import Qt, QProcess, pyqtSignal
from PyQt5.QtGui import QFont

from ..utils.constants import CONFIG_DIR, SYSTEM

log = logging.getLogger(__name__)

try:
    import pyte
    PYTE_AVAILABLE = True
except ImportError:
    PYTE_AVAILABLE = False

_ANSI_STRIP = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\][^\x07]*\x07|\x1b\].*?(?:\x1b\\|[\a])', re.DOTALL)


def _strip_ansi(text):
    return _ANSI_STRIP.sub('', text)


class TerminalHistory:
    def __init__(self, path=None):
        self.path = path or (CONFIG_DIR / "terminal_history.json")
        self._history = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, encoding="utf-8") as f:
                    self._history = json.load(f)
            except Exception as e:
                log.warning(f"Could not load terminal history: {e}")

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._history[-500:], f)
        except Exception as e:
            log.warning(f"Could not save terminal history: {e}")

    def append(self, cmd):
        if cmd and (not self._history or self._history[-1] != cmd):
            self._history.append(cmd)
            self._save()

    def get_all(self):
        return list(self._history)


def _get_shell():
    shell = os.environ.get("SHELL", "/bin/bash")
    return shell


class TerminalPane(QWidget):
    output_received = pyqtSignal(str)
    command_finished = pyqtSignal(str, str, int)

    def __init__(self, workspace_dir=None, history=None, scrollback=10000, font_size=10, parent=None):
        super().__init__(parent)
        self._cwd = str(workspace_dir) if workspace_dir else str(Path.home())
        self._history = history or TerminalHistory()
        self._history_idx = -1
        self._scrollback = scrollback
        self._font_size = font_size
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._on_ready_read)
        self._process.finished.connect(self._on_finished)
        self._pty_fd = None
        self._pty_notifier = None
        self._use_pty = False
        if SYSTEM != "Windows":
            try:
                import pty
                self._use_pty = True
            except ImportError:
                pass
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
        self.output.setFont(QFont("JetBrains Mono", self._font_size))
        self.output.setStyleSheet("background: #1e1e1e; color: #cccccc; border: none; padding: 4px;")
        self.output.setMaximumBlockCount(self._scrollback)
        layout.addWidget(self.output)

        input_row = QHBoxLayout()
        input_row.setContentsMargins(4, 2, 4, 4)
        input_row.setSpacing(4)
        self.prompt_label = QLabel("$")
        self.prompt_label.setStyleSheet("color: #7ee787; font-family: monospace; font-weight: bold;")
        input_row.addWidget(self.prompt_label)
        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("JetBrains Mono", self._font_size))
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

    def set_scrollback(self, n):
        self._scrollback = n
        self.output.setMaximumBlockCount(n)

    def set_font_size(self, size):
        self._font_size = size
        self.output.setFont(QFont("JetBrains Mono", size))
        self.input_line.setFont(QFont("JetBrains Mono", size))

    def _run_command(self):
        cmd = self.input_line.text().strip()
        if not cmd:
            return
        self.input_line.clear()
        self._history.append(cmd)
        self._history_idx = len(self._history.get_all())
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
        if SYSTEM == "Windows":
            self._process.start("cmd.exe", ["/c", cmd])
        else:
            self._process.start(_get_shell(), ["-c", cmd])

    def _on_ready_read(self):
        data = self._process.readAllStandardOutput().data().decode(errors='replace')
        text = _strip_ansi(data)
        self.output.insertPlainText(text)
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())
        self.output_received.emit(data)

    def _on_finished(self, exit_code, exit_status):
        if exit_code != 0:
            self.output.appendPlainText(f"\n[process exited with code {exit_code}]")
        self.input_line.setEnabled(True)
        self.input_line.setFocus()

    def execute_command(self, cmd):
        self.input_line.setText(cmd)
        self._run_command()

    def append_output(self, text):
        self.output.appendPlainText(text)
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())

    def get_recent_output(self, lines=50):
        all_text = self.output.toPlainText()
        line_list = all_text.splitlines()
        return "\n".join(line_list[-lines:])

    def keyPressEvent(self, event):
        hist = self._history.get_all()
        if event.key() == Qt.Key_Up and hist:
            self._history_idx = max(0, self._history_idx - 1)
            self.input_line.setText(hist[self._history_idx])
        elif event.key() == Qt.Key_Down and hist:
            self._history_idx = min(len(hist), self._history_idx + 1)
            if self._history_idx < len(hist):
                self.input_line.setText(hist[self._history_idx])
            else:
                self.input_line.clear()
        else:
            super().keyPressEvent(event)

    def kill(self):
        if self._process.state() != QProcess.NotRunning:
            self._process.kill()

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


class TerminalMultiplexer(QWidget):
    output_received = pyqtSignal(str)
    command_finished = pyqtSignal(str, str, int)

    def __init__(self, workspace_dir=None, parent=None):
        super().__init__(parent)
        self._workspace_dir = workspace_dir
        self._history = TerminalHistory()
        self._agent_tab_idx = -1
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._on_tab_close)
        self.tabs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._on_tab_context)
        layout.addWidget(self.tabs)
        self._add_tab("Terminal")

    def _add_tab(self, name="Terminal"):
        from ..utils.constants import load_settings
        s = load_settings()
        scrollback = s.get("terminal_scrollback", 10000)
        font_size = s.get("terminal_font_size", 10)
        pane = TerminalPane(
            workspace_dir=self._workspace_dir,
            history=self._history,
            scrollback=scrollback,
            font_size=font_size,
            parent=self
        )
        pane.output_received.connect(self.output_received.emit)
        pane.command_finished.connect(self.command_finished.emit)
        idx = self.tabs.addTab(pane, name)
        self.tabs.setCurrentIndex(idx)
        return idx

    def _on_tab_close(self, idx):
        pane = self.tabs.widget(idx)
        if pane:
            pane.kill()
        if self._agent_tab_idx == idx:
            self._agent_tab_idx = -1
        elif self._agent_tab_idx > idx:
            self._agent_tab_idx -= 1
        self.tabs.removeTab(idx)
        if self.tabs.count() == 0:
            self._add_tab()

    def _on_tab_context(self, pos):
        idx = self.tabs.tabBar().tabAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        rename = menu.addAction("Rename")
        kill = menu.addAction("Kill process")
        menu.addSeparator()
        new_tab = menu.addAction("New tab")
        action = menu.exec_(self.tabs.mapToGlobal(pos))
        if action == rename:
            from PyQt5.QtWidgets import QInputDialog
            name, ok = QInputDialog.getText(self, "Rename Tab", "Tab name:", text=self.tabs.tabText(idx))
            if ok and name.strip():
                self.tabs.setTabText(idx, name.strip())
        elif action == kill:
            pane = self.tabs.widget(idx)
            if pane:
                pane.kill()
        elif action == new_tab:
            self._add_tab()

    def _get_agent_tab(self):
        if self._agent_tab_idx >= 0 and self._agent_tab_idx < self.tabs.count():
            return self.tabs.widget(self._agent_tab_idx)
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i) == "Agent":
                self._agent_tab_idx = i
                return self.tabs.widget(i)
        self._agent_tab_idx = self._add_tab()
        self.tabs.setTabText(self._agent_tab_idx, "Agent")
        return self.tabs.widget(self._agent_tab_idx)

    def _current_pane(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, TerminalPane) else None

    def set_cwd(self, path):
        pane = self._current_pane()
        if pane:
            pane.set_cwd(path)
        self._workspace_dir = path

    def execute_command(self, cmd):
        pane = self._current_pane()
        if pane:
            pane.execute_command(cmd)

    def append_output(self, output):
        agent = self._get_agent_tab()
        if agent:
            agent.append_output(output)
        self.tabs.setCurrentIndex(self._agent_tab_idx)

    def run_in_new_tab(self, cmd, name=None):
        idx = self._add_tab(name or "Run")
        pane = self.tabs.widget(idx)
        if pane:
            pane.execute_command(cmd)

    def get_recent_output(self, lines=50):
        pane = self._current_pane()
        return pane.get_recent_output(lines) if pane else ""

    def apply_theme(self, theme):
        for i in range(self.tabs.count()):
            w = self.tabs.widget(i)
            if isinstance(w, TerminalPane):
                w.apply_theme(theme)


class TerminalWidget(TerminalMultiplexer):
    def __init__(self, workspace_dir=None, parent=None):
        super().__init__(workspace_dir, parent)

    @property
    def input_line(self):
        pane = self._current_pane()
        return pane.input_line if pane else None
