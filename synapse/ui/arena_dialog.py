import json
import random
import logging
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel,
    QPushButton, QComboBox, QSplitter, QWidget, QFrame
)
from PyQt5.QtCore import Qt
from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)

ELO_FILE = CONFIG_DIR / "arena_elo.json"


class ArenaDialog(QDialog):
    """Blind A/B model comparison with ELO tracking."""

    def __init__(self, models, settings_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Model Arena")
        self.resize(1100, 700)
        self.settings_data = settings_data
        self.models = models
        self.model_a = None
        self.model_b = None
        self.responses = {}
        self._workers = []
        self.elo = self._load_elo()

        self.setStyleSheet("""
            QDialog { background: #1a1b1e; }
            QTextEdit { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; border-radius: 6px; padding: 8px; }
            QLabel { color: #8b949e; }
            QPushButton { background: #238636; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; }
            QPushButton:hover { background: #2ea043; }
            QPushButton:disabled { background: #21262d; color: #484f58; }
            QPushButton#vote_btn { background: #1f6feb; }
            QPushButton#vote_btn:hover { background: #388bfd; }
            QFrame { background: #161b22; border: 1px solid #30363d; border-radius: 8px; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Prompt
        layout.addWidget(QLabel("Enter a prompt to test:"))
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Type your prompt here...")
        self.prompt_input.setMaximumHeight(80)
        layout.addWidget(self.prompt_input)

        self.battle_btn = QPushButton("Battle!")
        self.battle_btn.clicked.connect(self._start)
        layout.addWidget(self.battle_btn)

        # Side-by-side responses
        splitter = QSplitter(Qt.Horizontal)
        self.panel_a = self._make_panel("Model A")
        self.panel_b = self._make_panel("Model B")
        splitter.addWidget(self.panel_a["frame"])
        splitter.addWidget(self.panel_b["frame"])
        layout.addWidget(splitter, 1)

        # Voting
        self.vote_row = QHBoxLayout()
        self.btn_a_wins = QPushButton("A is Better")
        self.btn_a_wins.setObjectName("vote_btn")
        self.btn_a_wins.clicked.connect(lambda: self._vote("a"))
        self.btn_tie = QPushButton("Tie")
        self.btn_tie.setObjectName("vote_btn")
        self.btn_tie.clicked.connect(lambda: self._vote("tie"))
        self.btn_b_wins = QPushButton("B is Better")
        self.btn_b_wins.setObjectName("vote_btn")
        self.btn_b_wins.clicked.connect(lambda: self._vote("b"))
        for btn in (self.btn_a_wins, self.btn_tie, self.btn_b_wins):
            btn.setEnabled(False)
            self.vote_row.addWidget(btn)
        layout.addLayout(self.vote_row)

        # ELO display
        self.elo_label = QLabel(self._format_elo())
        self.elo_label.setStyleSheet("color: #58a6ff; font-size: 11px;")
        layout.addWidget(self.elo_label)

    def _make_panel(self, title):
        frame = QFrame()
        lay = QVBoxLayout(frame)
        label = QLabel(title)
        label.setStyleSheet("font-weight: bold; font-size: 13px; color: #e6edf3;")
        lay.addWidget(label)
        text = QTextEdit()
        text.setReadOnly(True)
        lay.addWidget(text)
        return {"frame": frame, "label": label, "text": text, "buf": ""}

    def _start(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt or len(self.models) < 2:
            return

        self.battle_btn.setEnabled(False)
        self.battle_btn.setText("Running...")
        for btn in (self.btn_a_wins, self.btn_tie, self.btn_b_wins):
            btn.setEnabled(False)

        self.panel_a["text"].clear()
        self.panel_b["text"].clear()
        self.panel_a["label"].setText("Model A")
        self.panel_b["label"].setText("Model B")
        self.panel_a["buf"] = ""
        self.panel_b["buf"] = ""
        self.responses = {}

        pool = list(dict.fromkeys(self.models))
        if len(pool) < 2:
            return
        random.shuffle(pool)
        self.model_a = pool[0]
        self.model_b = pool[1]

        from ..core.api import WorkerFactory
        from ..utils.constants import DEFAULT_GEN_PARAMS
        messages = [{"role": "user", "content": prompt}]

        for model, panel in [(self.model_a, self.panel_a), (self.model_b, self.panel_b)]:
            worker = WorkerFactory(model, messages, "", DEFAULT_GEN_PARAMS, self.settings_data)
            worker.token_received.connect(lambda tok, p=panel: self._stream(p, tok))
            worker.response_finished.connect(lambda text, stats, m=model: self._done(m, text))
            worker.error_occurred.connect(lambda err, p=panel: p["text"].setPlainText(f"Error: {err}"))
            worker.start()
            self._workers.append(worker)

    def _stream(self, panel, token):
        panel["buf"] += token
        panel["text"].setPlainText(panel["buf"])

    def _done(self, model, text):
        self.responses[model] = text
        if len(self.responses) >= 2:
            self.battle_btn.setEnabled(True)
            self.battle_btn.setText("Battle!")
            for btn in (self.btn_a_wins, self.btn_tie, self.btn_b_wins):
                btn.setEnabled(True)

    def _vote(self, winner):
        K = 32
        ra = self.elo.get(self.model_a, 1200)
        rb = self.elo.get(self.model_b, 1200)
        ea = 1 / (1 + 10 ** ((rb - ra) / 400))
        eb = 1 / (1 + 10 ** ((ra - rb) / 400))

        if winner == "a":
            sa, sb = 1, 0
        elif winner == "b":
            sa, sb = 0, 1
        else:
            sa, sb = 0.5, 0.5

        self.elo[self.model_a] = round(ra + K * (sa - ea))
        self.elo[self.model_b] = round(rb + K * (sb - eb))
        self._save_elo()

        # Reveal models
        self.panel_a["label"].setText(f"Model A: {self.model_a}")
        self.panel_b["label"].setText(f"Model B: {self.model_b}")
        self.elo_label.setText(self._format_elo())
        for btn in (self.btn_a_wins, self.btn_tie, self.btn_b_wins):
            btn.setEnabled(False)

    def _load_elo(self):
        try:
            if ELO_FILE.exists():
                return json.loads(ELO_FILE.read_text())
        except Exception as e:
            log.warning(f"Failed to load ELO ratings: {e}")
        return {}

    def _save_elo(self):
        try:
            ELO_FILE.write_text(json.dumps(self.elo, indent=2))
        except Exception as e:
            log.warning(f"Failed to save ELO ratings: {e}")

    def _format_elo(self):
        if not self.elo:
            return "No ELO ratings yet. Run some battles!"
        sorted_models = sorted(self.elo.items(), key=lambda x: x[1], reverse=True)
        parts = [f"{name}: {elo}" for name, elo in sorted_models[:8]]
        return "ELO Rankings: " + " | ".join(parts)

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        input_bg = theme.get("input_bg", "#0d1117")
        fg = theme.get("fg", "#e6edf3")
        border = theme.get("border", "#30363d")
        accent = theme.get("accent", "#238636")
        self.setStyleSheet(f"""
            QDialog {{ background: {bg}; }}
            QTextEdit {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; border-radius: 6px; padding: 8px; }}
            QLabel {{ color: {fg}; }}
            QPushButton {{ background: {accent}; color: white; border: none; padding: 8px 16px; border-radius: 6px; font-weight: bold; }}
            QPushButton:hover {{ background: {accent}; }}
            QPushButton:disabled {{ background: {border}; color: #484f58; }}
            QFrame {{ background: {input_bg}; border: 1px solid {border}; border-radius: 8px; }}
        """)
