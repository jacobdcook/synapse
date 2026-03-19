"""Word count plugin: tool and slash /wc."""
from ..core.plugins import SynapsePlugin


class WordCountPlugin(SynapsePlugin):
    name = "Word Count"
    description = "Count words in text"

    def get_tools(self):
        return [{
            "name": "word_count",
            "description": "Count words in text",
            "handler": lambda text="": len(str(text).split()) if text else 0,
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
        }]

    def get_slash_commands(self):
        return [{"name": "/wc", "description": "Word count", "handler": self._wc}]

    def _wc(self, arg):
        return str(len(arg.split()) if arg else 0)
