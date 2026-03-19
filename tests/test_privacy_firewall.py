"""Tests for synapse.core.privacy_firewall."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_email_rule():
    from synapse.core.privacy_firewall import PrivacyFirewall
    fw = PrivacyFirewall(True)
    text, events = fw.mask("Contact test@example.com for help")
    assert "test@example.com" not in text
    assert "[EMAIL" in text or "REDACTED" in text
    assert len(events) >= 1


def test_aws_key_rule():
    from synapse.core.privacy_firewall import PrivacyFirewall
    fw = PrivacyFirewall(True)
    text, events = fw.mask("Key: AKIAIOSFODNN7EXAMPLE")
    assert "AKIAIOSFODNN7EXAMPLE" not in text


def test_no_original_in_events():
    from synapse.core.privacy_firewall import PrivacyFirewall, MaskEvent
    fw = PrivacyFirewall(True)
    _, events = fw.mask("test@example.com")
    for e in events:
        assert hasattr(e, "original_hash")
        assert hasattr(e, "rule_name")
        assert "example" not in str(e.original_hash).lower()
