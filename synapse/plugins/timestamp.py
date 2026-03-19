"""Timestamp plugin: prepends timestamp on send, slash /time."""
from datetime import datetime, timezone
from ..core.plugins import SynapsePlugin


class TimestampPlugin(SynapsePlugin):
    name = "Timestamp"
    description = "Add timestamps to messages"

    def get_hooks(self):
        return {"on_message_send": self._on_send}

    def _on_send(self, text, **kwargs):
        ts = datetime.now(timezone.utc).strftime("%H:%M")
        return f"[{ts}] {text}"

    def get_slash_commands(self):
        return [{"name": "/time", "description": "Current time", "handler": self._time}]

    def _time(self, arg):
        return datetime.now(timezone.utc).isoformat()
