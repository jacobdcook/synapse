"""Privacy Firewall V2: rule-based masking with audit."""
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)


@dataclass
class PrivacyRule:
    name: str
    pattern: re.Pattern
    replacement: str
    enabled: bool = True
    category: str = "pii"
    severity: str = "high"


@dataclass
class MaskEvent:
    rule_name: str
    original_hash: str
    replacement: str


BUILTIN_RULES = [
    ("email", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_REDACTED]", "pii", "high"),
    ("phone", r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b", "[PHONE_REDACTED]", "pii", "high"),
    ("ssn", r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]", "pii", "critical"),
    ("credit_card", r"\b(?:\d{4}[- ]?){3}\d{4}\b", "[CC_REDACTED]", "financial", "critical"),
    ("aws_key", r"AKIA[A-Z0-9]{16}", "[AWS_KEY_REDACTED]", "api", "critical"),
    ("openai_key", r"sk-[a-zA-Z0-9]{48}", "[OPENAI_KEY_REDACTED]", "api", "critical"),
    ("github_token", r"ghp_[a-zA-Z0-9]{36}", "[GITHUB_TOKEN_REDACTED]", "api", "critical"),
    ("anthropic_key", r"sk-ant-[a-zA-Z0-9-]{95}", "[ANTHROPIC_KEY_REDACTED]", "api", "critical"),
    ("ipv4", r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[IP_REDACTED]", "network", "medium"),
    ("jwt", r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*", "[JWT_REDACTED]", "auth", "critical"),
]


class PrivacyFirewall:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.rules = []
        self._load_builtin()
        self._load_custom()
        self._stats = {}

    def _load_builtin(self):
        for name, pat, repl, cat, sev in BUILTIN_RULES:
            self.rules.append(PrivacyRule(name, re.compile(pat), repl, True, cat, sev))

    def _load_custom(self):
        p = CONFIG_DIR / "privacy_rules.json"
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text())
            for r in data.get("rules", []):
                if r.get("enabled", True):
                    self.rules.append(PrivacyRule(
                        r["name"], re.compile(r["pattern"]), r.get("replacement", "[REDACTED]"),
                        True, r.get("category", "custom"), r.get("severity", "medium")
                    ))
        except Exception as e:
            log.warning(f"Privacy rules load failed: {e}")

    def mask(self, text):
        if not self.enabled or not text:
            return text, []
        events = []
        result = text
        for rule in self.rules:
            if not rule.enabled:
                continue
            for m in rule.pattern.finditer(result):
                orig = m.group(0)
                h = hashlib.sha256(orig.encode()).hexdigest()
                events.append(MaskEvent(rule.name, h, rule.replacement))
                result = result[:m.start()] + rule.replacement + result[m.end():]
                self._stats[rule.name] = self._stats.get(rule.name, 0) + 1
        return result, events

    def get_stats(self):
        by_cat = {}
        for r in self.rules:
            by_cat[r.category] = by_cat.get(r.category, 0) + self._stats.get(r.name, 0)
        return {"by_rule": dict(self._stats), "by_category": by_cat}
