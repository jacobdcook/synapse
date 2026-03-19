"""Shortcut management with conflict detection."""
import logging
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut

log = logging.getLogger(__name__)

DEFAULT_SHORTCUTS = {
    "palette": "Ctrl+K",
    "new_chat": "Ctrl+N",
    "close_tab": "Ctrl+W",
    "next_tab": "Ctrl+Tab",
    "prev_tab": "Ctrl+Shift+Tab",
    "send": "Ctrl+Enter",
    "send_agentic": "Ctrl+Shift+Enter",
    "toggle_sidebar": "Ctrl+/",
    "clear": "Ctrl+L",
    "regenerate": "Ctrl+R",
    "cancel": "Escape",
}


class ShortcutManager:
    def __init__(self):
        self._shortcuts = {}
        self._actions = {}

    def register(self, action_id, key_sequence, callback, widget):
        key = QKeySequence(key_sequence)
        if action_id in self._shortcuts:
            self._shortcuts[action_id].setEnabled(False)
            self._shortcuts[action_id].deleteLater()
        s = QShortcut(key, widget)
        s.activated.connect(callback)
        self._shortcuts[action_id] = s
        self._actions[action_id] = key_sequence
        return s

    def get_conflicts(self):
        seen = {}
        conflicts = []
        for aid, seq in self._actions.items():
            if seq in seen:
                conflicts.append((aid, seen[seq]))
            else:
                seen[seq] = aid
        return conflicts

    def get_all(self):
        return dict(self._actions)
