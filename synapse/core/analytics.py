"""Analytics: usage tracking and cost estimation."""
__all__ = ["AnalyticsManager", "analytics_manager"]

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
        total_input = sum(l.get("input_tokens", 0) for l in self.logs)
        total_output = sum(l.get("output_tokens", 0) for l in self.logs)
        by_model = {}
        for l in self.logs:
            m = l.get("model", "unknown")
            by_model[m] = by_model.get(m, 0) + l.get("input_tokens", 0) + l.get("output_tokens", 0)
        return {
            "total_input": total_input,
            "total_output": total_output,
            "total_tokens": total_input + total_output,
            "by_model": by_model,
            "count": len(self.logs),
        }

    def get_messages_per_day(self, days=30):
        from collections import defaultdict
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        by_day = defaultdict(int)
        for l in self.logs:
            ts = l.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt >= cutoff:
                        by_day[dt.date().isoformat()] += 1
                except (ValueError, TypeError):
                    pass
        return dict(by_day)

    def estimate_cost(self):
        from ..utils.constants import MODEL_PRICES
        total = 0.0
        for l in self.logs:
            model = l.get("model", "")
            prices = MODEL_PRICES.get(model, {})
            in_p = prices.get("input", 0) or 0
            out_p = prices.get("output", 0) or 0
            total += (l.get("input_tokens", 0) / 1e6 * in_p) + (l.get("output_tokens", 0) / 1e6 * out_p)
        return total

# Global instance
analytics_manager = AnalyticsManager()
