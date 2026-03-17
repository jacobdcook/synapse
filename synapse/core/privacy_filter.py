import re
import logging

log = logging.getLogger(__name__)

class PrivacyFilter:
    """Detects and masks PII / Sensitive data using regex patterns."""
    
    PATTERNS = {
        "EMAIL": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "IPV4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "API_KEY_GENERIC": r"\b[a-zA-Z0-9]{32,256}\b", # Most API keys are 32+ chars
        "OPENAI_KEY": r"sk-[a-zA-Z0-9]{48}",
        "AWS_KEY": r"AKIA[A-Z0-9]{16}",
        "PHONE": r"\b(?:\+?\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d{4}[- ]?){3}\d{4}\b"
    }

    def __init__(self, enabled=True):
        self.enabled = enabled

    def mask(self, text):
        if not self.enabled or not text:
            return text
        
        redacted_count = 0
        masked_text = text
        
        for name, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, masked_text)
            if matches:
                redacted_count += len(matches)
                # Replace with [REDACTED_TYPE]
                masked_text = re.sub(pattern, f"[REDACTED_{name}]", masked_text)
        
        if redacted_count > 0:
            log.info(f"PrivacyFilter redacted {redacted_count} items from message.")
            
        return masked_text

    def get_redaction_report(self, text):
        """Returns a list of detected sensitive types without masking."""
        detected = []
        for name, pattern in self.PATTERNS.items():
            if re.search(pattern, text):
                detected.append(name)
        return detected
