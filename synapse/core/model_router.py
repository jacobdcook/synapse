"""Heuristic model routing by task type."""
import logging
import time
from ..utils.constants import get_ollama_url

log = logging.getLogger(__name__)

_CACHE = {}
_CACHE_TTL = 300


def classify_task(msg):
    t = (msg or "").lower()
    if any(k in t for k in ["refactor", "implement", "create", "build", "fix", "debug", "code", "function", "class"]):
        return "code"
    if any(k in t for k in ["analyze", "compare", "explain", "why", "how does"]):
        return "analysis"
    if any(k in t for k in ["write", "story", "poem", "creative"]):
        return "creative"
    if len(t) > 500:
        return "analysis"
    return "simple" if len(t) < 100 else "general"


def route(msg, context, settings):
    if not settings.get("model_router_enabled", False):
        return settings.get("default_model", "llama3.2:3b")
    cat = classify_task(msg)
    fast = settings.get("fast_model", "llama3.2:1b")
    code = settings.get("code_model", "qwen2.5-coder:7b")
    analysis = settings.get("analysis_model", "llama3.2:3b")
    creative = settings.get("creative_model", "llama3.2:3b")
    general = settings.get("default_model", "llama3.2:3b")
    return {"simple": fast, "code": code, "analysis": analysis, "creative": creative, "general": general}.get(cat, general)


def get_available_models():
    global _CACHE
    now = time.time()
    if _CACHE.get("ts", 0) + _CACHE_TTL > now:
        return _CACHE.get("models", [])
    try:
        import urllib.request
        url = f"{get_ollama_url()}/api/tags"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as r:
            data = __import__("json").loads(r.read().decode())
        models = [m["name"] for m in data.get("models", [])]
        _CACHE = {"models": models, "ts": now}
        return models
    except Exception as e:
        log.warning(f"Ollama models fetch failed: {e}")
        return _CACHE.get("models", [])
