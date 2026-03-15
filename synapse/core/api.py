import json
import urllib.request
import urllib.error
import logging
from PyQt5.QtCore import QThread, pyqtSignal
from ..utils.constants import get_ollama_url

log = logging.getLogger(__name__)

ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


def _request_json(path, payload=None, timeout=10):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{get_ollama_url()}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8", errors="replace"))


def get_loaded_models():
    try:
        data = _request_json("/api/ps", timeout=5)
        return [m.get("name") for m in data.get("models", []) if m.get("name")]
    except Exception as e:
        log.warning(f"Unable to inspect loaded Ollama models: {e}")
        return []

def unload_model(model_name):
    try:
        _request_json("/api/generate", {"model": model_name, "keep_alive": 0}, timeout=10)
        log.info(f"Unloaded Ollama model: {model_name}")
    except Exception as e:
        log.warning(f"Failed to unload model '{model_name}': {e}")


def unload_all_models(except_model=None):
    loaded = get_loaded_models()
    for model_name in loaded:
        if except_model and model_name == except_model:
            continue
        unload_model(model_name)
    return loaded

class OllamaWorker(QThread):
    token_received = pyqtSignal(str)
    response_finished = pyqtSignal(str, dict)
    error_occurred = pyqtSignal(str)

    tool_calls_received = pyqtSignal(list)
    _models_without_tool_support = set()

    def __init__(self, model, messages, system_prompt="", gen_params=None, tools=None):
        super().__init__()
        self.model = model
        self.messages = messages
        self.system_prompt = system_prompt
        self.gen_params = gen_params or {}
        self.tools = tools
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def _prune_messages(self, messages, max_tokens=3500):
        # Very crude estimation: 1 word = 1.3 tokens average
        current_tokens = 0
        pruned = []
        # Keep system prompt if it exists (handled separately in run)
        # Iterate backwards to keep newest messages
        for msg in reversed(messages):
            tokens = len(msg.get("content", "").split()) * 1.5
            if current_tokens + tokens < max_tokens:
                pruned.insert(0, msg)
                current_tokens += tokens
            else:
                break
        return pruned

    def run(self):
        try_tools = (
            isinstance(self.tools, list)
            and len(self.tools) > 0
            and self.model not in self._models_without_tool_support
        )
        retried_after_unload = False
        try:
            self._execute_request(use_tools=try_tools)
        except Exception as e:
            err_text = str(e)
            if try_tools and ("does not support tools" in err_text.lower() or "400" in err_text):
                if "does not support tools" in err_text.lower():
                    self._models_without_tool_support.add(self.model)
                log.warning(f"Model '{self.model}' does not support tools; retrying without tools")
                try:
                    self._execute_request(use_tools=False)
                    return
                except Exception as inner_e:
                    err_text = str(inner_e)

            needs_memory_retry = (
                "500" in err_text
                or "unable to load" in err_text.lower()
                or "resource limitations" in err_text.lower()
                or "model failed to load" in err_text.lower()
            )
            if needs_memory_retry and not retried_after_unload:
                retried_after_unload = True
                try:
                    unloaded = unload_all_models(except_model=None)
                    if unloaded:
                        log.warning(f"Model load failed; unloaded Ollama models and retrying once: {', '.join(unloaded)}")
                    else:
                        log.warning("Model load failed; no loaded Ollama models found, retrying once anyway")
                    self._execute_request(use_tools=False)
                    return
                except Exception as retry_e:
                    err_text = str(retry_e)

            if needs_memory_retry:
                err_text += (
                    "\n\nSynapse already tried unloading Ollama memory and retrying once."
                    "\nIf this still fails, the selected model is likely too large for the current load path,"
                    " the model blob is corrupted, or Ollama itself cannot initialize that quant on this machine."
                    "\nTry a smaller model first, or re-pull this model."
                )
            
            log.error(f"Worker task failed: {err_text}")
            self.error_occurred.emit(err_text)

    def _execute_request(self, use_tools=True):
        try:
            api_messages = []
            if self.system_prompt:
                api_messages.append({"role": "system", "content": self.system_prompt})
            
            # Prune messages to fit context
            max_ctx = self.gen_params.get("num_ctx", 4096)
            pruned_history = self._prune_messages(self.messages, max_tokens=max_ctx - 1000)
            
            for msg in pruned_history:
                role = msg.get("role")
                if role == "tool_results":
                    # Internal UI role; fan out to Ollama-compatible tool messages.
                    for result in msg.get("tool_results", []):
                        api_messages.append({
                            "role": "tool",
                            "content": str(result.get("content", "")),
                            "tool_call_id": result.get("id")
                        })
                    continue

                if role not in ALLOWED_ROLES:
                    continue

                entry = {
                    "role": role,
                    "content": str(msg.get("content", "")),
                }
                if msg.get("images"):
                    entry["images"] = msg["images"]
                if msg.get("tool_calls"):
                    entry["tool_calls"] = msg["tool_calls"]
                api_messages.append(entry)

            payload = {"model": self.model, "messages": api_messages, "stream": True}
            if use_tools and isinstance(self.tools, list) and len(self.tools) > 0:
                payload["tools"] = self.tools
            
            if self.gen_params:
                opts = {}
                for k in ("temperature", "top_p", "num_ctx"):
                    if k in self.gen_params:
                        opts[k] = self.gen_params[k]
                if opts:
                    payload["options"] = opts

            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{get_ollama_url()}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
            )

            full_text = ""
            stats = {}
            tool_calls = []
            
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    if self._stop_flag:
                        break
                    try:
                        chunk = json.loads(line.decode().strip())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    
                    if "message" in chunk:
                        msg_chunk = chunk["message"]
                        if "content" in msg_chunk:
                            token = msg_chunk["content"]
                            full_text += token
                            self.token_received.emit(token)
                        
                        if "tool_calls" in msg_chunk:
                            tool_calls.extend(msg_chunk["tool_calls"])
                    
                    if chunk.get("done"):
                        stats = {
                            "total_duration": chunk.get("total_duration", 0),
                            "eval_count": chunk.get("eval_count", 0),
                            "eval_duration": chunk.get("eval_duration", 0),
                        }
            
            if tool_calls:
                self.tool_calls_received.emit(tool_calls)
                if not full_text.strip():
                    # Tool-only turn: UI handles continuation after executing tools.
                    return
            
            log.info(f"Response complete: {stats.get('eval_count', 0)} tokens")
            self.response_finished.emit(full_text, stats)
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            message = f"HTTP {e.code} {e.reason}"
            if body:
                message = f"{message}: {body}"
            log.error(f"Ollama HTTP error: {message}")
            raise RuntimeError(message) from e
        except urllib.error.URLError as e:
            message = f"Ollama connection error: {e.reason}"
            log.error(message)
            raise RuntimeError(message) from e
        except Exception as e:
            log.error(f"Ollama error: {e}")
            raise e


class TitleWorker(QThread):
    title_ready = pyqtSignal(str, str)  # conv_id, title

    def __init__(self, model, conv_id, messages):
        super().__init__()
        self.model = model
        self.conv_id = conv_id
        self.messages = messages

    def run(self):
        try:
            summary_msgs = list(self.messages)[:4]
            summary_msgs.append({
                "role": "user",
                "content": "Summarize this conversation in 3-5 words for a title. Reply with ONLY the title, nothing else."
            })
            payload = json.dumps({
                "model": self.model,
                "messages": [{"role": m["role"], "content": m.get("content", "")} for m in summary_msgs if m.get("role") in ALLOWED_ROLES],
                "stream": False,
                "options": {"temperature": 0.3, "num_ctx": 1024}
            }).encode()
            req = urllib.request.Request(
                f"{get_ollama_url()}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                title = data.get("message", {}).get("content", "").strip().strip('"').strip("'")
                if title and len(title) < 80:
                    self.title_ready.emit(self.conv_id, title)
        except Exception as e:
            log.warning(f"Auto-title failed: {e}")


class ConnectionChecker(QThread):
    status_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._running = True

    def run(self):
        while self._running:
            try:
                req = urllib.request.Request(f"{get_ollama_url()}/api/tags")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    resp.read()
                self.status_changed.emit(True)
            except Exception:
                self.status_changed.emit(False)
            self.sleep(10) # Check every 10s for better responsiveness

    def stop(self):
        self._running = False


class ModelLoader(QThread):
    models_loaded = pyqtSignal(list)

    def run(self):
        try:
            req = urllib.request.Request(f"{get_ollama_url()}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                models.sort()
                self.models_loaded.emit(models)
        except Exception:
            self.models_loaded.emit(["llama3.2:3b"])
