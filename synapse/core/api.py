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

def get_embeddings(text, model="nomic-embed-text"):
    """Fetch embeddings for a given text using Ollama."""
    try:
        # Limit text length to avoid context window issues during embedding
        # nomic-embed-text usually handles around 8k, but let's be safe
        truncated_text = text[:32000]
        payload = {"model": model, "prompt": truncated_text}
        resp = _request_json("/api/embeddings", payload, timeout=30)
        return resp.get("embedding", [])
    except Exception as e:
        log.warning(f"Failed to get embeddings for model '{model}': {e}")
        return []

class BaseAIWorker(QThread):
    token_received = pyqtSignal(str)
    response_finished = pyqtSignal(str, dict)
    error_occurred = pyqtSignal(str)
    tool_calls_received = pyqtSignal(list)

    def __init__(self, model, messages, system_prompt="", gen_params=None, tools=None, api_key=None):
        super().__init__()
        self.model = model
        self.messages = messages
        self.system_prompt = system_prompt
        self.gen_params = gen_params or {}
        self.tools = tools
        self.api_key = api_key
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def _prune_messages(self, messages, max_tokens=3500):
        # Very crude estimation: 1 word = 1.3 tokens average
        current_tokens = 0
        pruned = []
        for msg in reversed(messages):
            tokens = len(msg.get("content", "").split()) * 1.5
            if current_tokens + tokens < max_tokens:
                pruned.insert(0, msg)
                current_tokens += tokens
            else:
                break
        return pruned

    def run(self):
        raise NotImplementedError("Subclasses must implement run()")

class OllamaWorker(BaseAIWorker):
    _models_without_tool_support = set()

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
            
            max_ctx = self.gen_params.get("num_ctx", 4096)
            pruned_history = self._prune_messages(self.messages, max_tokens=max_ctx - 1000)
            
            for msg in pruned_history:
                role = msg.get("role")
                if role == "tool_results":
                    for result in msg.get("tool_results", []):
                        api_messages.append({"role": "tool", "content": str(result.get("content", "")), "tool_call_id": result.get("id")})
                    continue
                if role not in ALLOWED_ROLES: continue
                entry = {"role": role, "content": str(msg.get("content", ""))}
                if msg.get("images"): entry["images"] = msg["images"]
                if msg.get("tool_calls"): entry["tool_calls"] = msg["tool_calls"]
                api_messages.append(entry)

            payload = {"model": self.model, "messages": api_messages, "stream": True}
            if use_tools and isinstance(self.tools, list) and len(self.tools) > 0:
                payload["tools"] = self.tools
            
            if self.gen_params:
                opts = {k: self.gen_params[k] for k in ("temperature", "top_p", "num_ctx") if k in self.gen_params}
                if opts: payload["options"] = opts

            data = json.dumps(payload).encode()
            req = urllib.request.Request(f"{get_ollama_url()}/api/chat", data=data, headers={"Content-Type": "application/json"})

            full_text = ""
            stats = {}
            tool_calls = []
            
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    if self._stop_flag: break
                    try:
                        chunk = json.loads(line.decode().strip())
                    except (json.JSONDecodeError, UnicodeDecodeError): continue
                    
                    if "message" in chunk:
                        msg_chunk = chunk["message"]
                        if "content" in msg_chunk:
                            token = msg_chunk["content"]; full_text += token; self.token_received.emit(token)
                        if "tool_calls" in msg_chunk: tool_calls.extend(msg_chunk["tool_calls"])
                    
                    if chunk.get("done"):
                        stats = {
                            "total_duration": chunk.get("total_duration", 0),
                            "eval_count": chunk.get("eval_count", 0),
                            "eval_duration": chunk.get("eval_duration", 0),
                            "prompt_eval_count": chunk.get("prompt_eval_count", 0)
                        }
            
            if tool_calls:
                self.tool_calls_received.emit(tool_calls)
                if not full_text.strip(): return
            
            self.response_finished.emit(full_text, stats)
        except Exception as e:
            log.error(f"Ollama error: {e}")
            raise e

class OpenAIWorker(BaseAIWorker):
    def run(self):
        try:
            api_messages = []
            if self.system_prompt:
                api_messages.append({"role": "system", "content": self.system_prompt})
            
            pruned_history = self._prune_messages(self.messages, max_tokens=128000)
            for msg in pruned_history:
                role = msg.get("role")
                if role == "tool_results":
                    for result in msg.get("tool_results", []):
                        api_messages.append({"role": "tool", "content": str(result.get("content", "")), "tool_call_id": result.get("id")})
                    continue
                if role not in ALLOWED_ROLES: continue
                entry = {"role": role, "content": str(msg.get("content", ""))}
                if msg.get("tool_calls"): entry["tool_calls"] = msg["tool_calls"]
                api_messages.append(entry)

            payload = {"model": self.model, "messages": api_messages, "stream": True, "stream_options": {"include_usage": True}}
            if self.tools: payload["tools"] = self.tools
            if "temperature" in self.gen_params: payload["temperature"] = self.gen_params["temperature"]

            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
            )

            full_text = ""
            tool_calls_map = {} # id -> {function: {name: "", arguments: ""}}
            usage = {}

            with urllib.request.urlopen(req, timeout=60) as resp:
                for line in resp:
                    if self._stop_flag: break
                    line = line.decode().strip()
                    if not line.startswith("data: "): continue
                    if line == "data: [DONE]": break
                    
                    try:
                        chunk = json.loads(line[6:])
                        if "usage" in chunk and chunk["usage"]:
                            usage = chunk["usage"]
                        
                        choices = chunk.get("choices", [])
                        if not choices: continue
                        delta = choices[0].get("delta", {})
                        
                        if "content" in delta and delta["content"]:
                            token = delta["content"]
                            full_text += token
                            self.token_received.emit(token)
                        
                        if "tool_calls" in delta:
                            for tc in delta["tool_calls"]:
                                idx = tc.get("index", 0)
                                if idx not in tool_calls_map:
                                    tool_calls_map[idx] = {"id": tc.get("id"), "type": "function", "function": {"name": "", "arguments": ""}}
                                
                                if "id" in tc: tool_calls_map[idx]["id"] = tc["id"]
                                if "function" in tc:
                                    if "name" in tc["function"]: tool_calls_map[idx]["function"]["name"] += tc["function"]["name"]
                                    if "arguments" in tc["function"]: tool_calls_map[idx]["function"]["arguments"] += tc["function"]["arguments"]
                    except Exception: continue

            if tool_calls_map:
                tool_calls = list(tool_calls_map.values())
                self.tool_calls_received.emit(tool_calls)
                if not full_text.strip(): return

            stats = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            }
            self.response_finished.emit(full_text, stats)
        except Exception as e:
            self.error_occurred.emit(str(e))

class AnthropicWorker(BaseAIWorker):
    def run(self):
        try:
            api_messages = []
            anthropic_system = self.system_prompt or ""
            
            pruned_history = self._prune_messages(self.messages, max_tokens=200000)
            for msg in pruned_history:
                role = msg.get("role")
                if role == "system":
                    anthropic_system += "\n" + msg.get("content", "")
                    continue
                if role == "tool_results":
                    api_messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": r.get("id"),
                            "content": str(r.get("content", ""))
                        } for r in msg.get("tool_results", [])]
                    })
                    continue
                
                content = msg.get("content", "")
                if msg.get("tool_calls"):
                    content_list = [{"type": "text", "text": content}] if content else []
                    for tc in msg["tool_calls"]:
                        try:
                            args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                            content_list.append({
                                "type": "tool_use",
                                "id": tc.get("id"),
                                "name": tc["function"]["name"],
                                "input": args
                            })
                        except: continue
                    api_messages.append({"role": "assistant" if role == "assistant" else "user", "content": content_list})
                else:
                    api_messages.append({"role": "assistant" if role == "assistant" else "user", "content": content})

            payload = {
                "model": self.model, 
                "messages": api_messages, 
                "system": anthropic_system,
                "max_tokens": 4096,
                "stream": True
            }
            if self.tools:
                payload["tools"] = [{
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters", {})
                } for t in self.tools]

            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01"
                }
            )

            full_text = ""
            current_tool_id = None
            current_tool_name = None
            current_tool_input = ""
            tool_calls = []
            usage = {"input_tokens": 0, "output_tokens": 0}

            with urllib.request.urlopen(req, timeout=60) as resp:
                for line in resp:
                    if self._stop_flag: break
                    line = line.decode().strip()
                    if not line.startswith("data: "): continue
                    try:
                        chunk = json.loads(line[6:])
                        ctype = chunk.get("type")
                        
                        if ctype == "message_start":
                            if "message" in chunk and "usage" in chunk["message"]:
                                usage["input_tokens"] += chunk["message"]["usage"].get("input_tokens", 0)
                                usage["output_tokens"] += chunk["message"]["usage"].get("output_tokens", 0)
                        
                        if ctype == "message_delta":
                            if "usage" in chunk:
                                usage["output_tokens"] += chunk.get("usage", {}).get("output_tokens", 0)

                        if ctype == "content_block_start":
                            block = chunk.get("content_block", {})
                            if block.get("type") == "tool_use":
                                current_tool_id = block.get("id")
                                current_tool_name = block.get("name")
                                current_tool_input = ""
                                
                        if ctype == "content_block_delta":
                            delta = chunk.get("delta", {})
                            if delta.get("type") == "text_delta":
                                token = delta.get("text", "")
                                full_text += token
                                self.token_received.emit(token)
                            elif delta.get("type") == "input_json_delta":
                                current_tool_input += delta.get("partial_json", "")
                                
                        if ctype == "content_block_stop":
                            if current_tool_id:
                                tool_calls.append({
                                    "id": current_tool_id,
                                    "type": "function",
                                    "function": {"name": current_tool_name, "arguments": current_tool_input}
                                })
                                current_tool_id = None
                    except Exception: continue

            if tool_calls:
                self.tool_calls_received.emit(tool_calls)
                if not full_text.strip(): return

            stats = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0)
            }
            self.response_finished.emit(full_text, stats)
        except Exception as e:
            self.error_occurred.emit(str(e))

def WorkerFactory(model, messages, system_prompt="", gen_params=None, tools=None, settings=None):
    settings = settings or {}
    if model.startswith("gpt-") or model.startswith("o1-"):
        return OpenAIWorker(model, messages, system_prompt, gen_params, tools, settings.get("openai_key"))
    elif model.startswith("claude-"):
        return AnthropicWorker(model, messages, system_prompt, gen_params, tools, settings.get("anthropic_key"))
    else:
        return OllamaWorker(model, messages, system_prompt, gen_params, tools)


class TitleWorker(QThread):
    title_ready = pyqtSignal(str, str)

    def __init__(self, model, conv_id, messages, settings=None):
        super().__init__()
        self.model = model
        self.conv_id = conv_id
        self.messages = messages
        self.settings = settings or {}

    def run(self):
        try:
            summary_msgs = list(self.messages)[:4]
            summary_msgs.append({
                "role": "user",
                "content": "Summarize this conversation in 3-5 words for a title. Reply with ONLY the title, nothing else."
            })
            
            # Use WorkerFactory to create a non-streaming worker for title generation
            worker = WorkerFactory(
                self.model,
                summary_msgs,
                gen_params={"temperature": 0.3, "num_ctx": 1024},
                settings=self.settings
            )
            # Since we are already in a thread, we can't easily use signals.
            # We'll just borrow the run logic or refactor WorkerFactory to provide synchronous calls.
            # For now, let's just make it simple: if it's Ollama, use the existing logic.
            # If cloud, it's safer to just do a quick non-streaming hit.
            
            if self.model.startswith("gpt-") or self.model.startswith("o1-"):
                payload = {
                    "model": self.model,
                    "messages": [{"role": m["role"], "content": m.get("content", "")} for m in summary_msgs if m.get("role") in ALLOWED_ROLES],
                    "stream": False,
                    "temperature": 0.3
                }
                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.settings.get('openai_key')}"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    title = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip().strip('"').strip("'")
            elif self.model.startswith("claude-"):
                payload = {
                    "model": self.model,
                    "messages": [{"role": m["role"], "content": m.get("content", "")} for m in summary_msgs if m.get("role") in ALLOWED_ROLES and m["role"] != "system"],
                    "max_tokens": 100,
                    "stream": False,
                    "temperature": 0.3
                }
                system_msg = next((m["content"] for m in summary_msgs if m["role"] == "system"), "")
                if system_msg: payload["system"] = system_msg
                
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=json.dumps(payload).encode(),
                    headers={
                        "Content-Type": "application/json", 
                        "x-api-key": self.settings.get("anthropic_key"),
                        "anthropic-version": "2023-06-01"
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    title = data.get("content", [{}])[0].get("text", "").strip().strip('"').strip("'")
            else:
                payload = json.dumps({
                    "model": self.model,
                    "messages": [{"role": m["role"], "content": m.get("content", "")} for m in summary_msgs if m.get("role") in ALLOWED_ROLES],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_ctx": 1024}
                }).encode()
                req = urllib.request.Request(f"{get_ollama_url()}/api/chat", data=payload, headers={"Content-Type": "application/json"})
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
        cloud_models = [
            "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-preview", "o1-mini",
            "claude-3-5-sonnet-20240620", "claude-3-opus-20240229", "claude-3-haiku-20240307"
        ]
        try:
            req = urllib.request.Request(f"{get_ollama_url()}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                models.extend(cloud_models)
                models.sort()
                self.models_loaded.emit(models)
        except Exception:
            self.models_loaded.emit(cloud_models + ["llama3.2:3b"])
