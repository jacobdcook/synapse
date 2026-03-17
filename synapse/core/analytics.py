import json
import logging
import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from ..utils.constants import CONFIG_DIR

log = logging.getLogger(__name__)

ANALYTICS_FILE = CONFIG_DIR / "analytics_v1.json"

class AnalyticsManager:
    def __init__(self):
        self.logs = []
        self._load()

    def _load(self):
        try:
            if ANALYTICS_FILE.exists():
                with open(ANALYTICS_FILE, "r") as f:
                    self.logs = json.load(f)
                self._prune()
        except Exception as e:
            log.error(f"Failed to load analytics: {e}")
            self.logs = []

    def _prune(self, max_days=90):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_days)).isoformat()
        before = len(self.logs)
        self.logs = [l for l in self.logs if l.get("timestamp", "") >= cutoff]
        pruned = before - len(self.logs)
        if pruned > 0:
            log.info(f"Pruned {pruned} analytics entries older than {max_days} days")
            self._save()

    def _save(self):
        try:
            ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=str(ANALYTICS_FILE.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self.logs, f, indent=2)
                os.replace(tmp_path, str(ANALYTICS_FILE))
            except Exception:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            log.error(f"Failed to save analytics: {e}")

    def log_usage(self, model, provider, input_tokens, output_tokens, duration_ms):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "duration_ms": duration_ms
        }
        self.logs.append(entry)
        self._save()
        log.info(f"Logged analytics: {model} ({provider}) - {input_tokens} in, {output_tokens} out")

    def get_stats(self):
        # Basic aggregation for the UI
        total_input = sum(l.get("input_tokens", 0) for l in self.logs)
        total_output = sum(l.get("output_tokens", 0) for l in self.logs)
        
        # Group by model
        by_model = {}
        for l in self.logs:
            m = l.get("model", "unknown")
            by_model[m] = by_model.get(m, 0) + l.get("input_tokens", 0) + l.get("output_tokens", 0)
            
        return {
            "total_input": total_input,
            "total_output": total_output,
            "total_tokens": total_input + total_output,
            "by_model": by_model,
            "count": len(self.logs)
        }

# Global instance
analytics_manager = AnalyticsManager()
