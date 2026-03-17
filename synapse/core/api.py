import json
import re
import socket
import urllib.request
import urllib.error
import logging
import time
from PyQt5.QtCore import QThread, pyqtSignal
from ..utils.constants import get_ollama_url

log = logging.getLogger(__name__)

ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


def _request_json(path, payload=None, timeout=10, retries=2):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
    for attempt in range(retries + 1):
        try:
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
        except (socket.timeout, ConnectionResetError, urllib.error.URLError) as e:
            if attempt < retries:
                delay = min(1 * (2 ** attempt), 5)
                log.debug(f"Ollama request retry {attempt+1}/{retries}: {e}")
                time.sleep(delay)
                continue
            raise


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
    truncated = pyqtSignal()

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

    @staticmethod
    def _classify_error(e):
        """Classify an exception into a user-friendly message."""
        err_str = str(e).lower()
        if isinstance(e, urllib.error.HTTPError):
            code = e.code
            if code == 401:
                return "Authentication failed — check your API key in Settings."
            elif code == 403:
                return "Access denied — your API key may lack permissions for this model."
            elif code == 429:
                return "Rate limited — too many requests. Wait a moment and try again."
            elif code == 404:
                return f"Model not found — verify the model name is correct."
            elif 500 <= code < 600:
                return f"Server error ({code}) — the API provider is having issues. Try again shortly."
            return f"HTTP {code}: {e.reason}"
        elif isinstance(e, urllib.error.URLError):
            if "connection refused" in err_str:
                return "Connection refused — is the server running? Check Settings > Ollama URL."
            elif "name or service not known" in err_str or "nodename nor servname" in err_str:
                return "DNS lookup failed — check your internet connection."
            return f"Network error: {e.reason}"
        elif isinstance(e, socket.timeout):
            return "Request timed out — the model may be overloaded or the server is slow."
        elif isinstance(e, ConnectionResetError):
            return "Connection reset — the server closed the connection unexpectedly."
        return str(e)

    @staticmethod
    def _is_transient(e):
        """Check if an error is transient and worth retrying."""
        if isinstance(e, urllib.error.HTTPError):
            return e.code in (429, 502, 503, 504)
        if isinstance(e, (socket.timeout, ConnectionResetError, ConnectionError)):
            return True
        if isinstance(e, urllib.error.URLError):
            reason = str(e.reason).lower()
            return "temporary" in reason or "timed out" in reason
        return False

    def _run_with_retry(self, fn, max_retries=2):
        """Run fn() with retry on transient errors (429, 502-504, timeout)."""
        for attempt in range(max_retries + 1):
            try:
                return fn()
            except Exception as e:
                if attempt < max_retries and self._is_transient(e) and not self._stop_flag:
                    delay = min(1 * (3 ** attempt), 10)
                    log.warning(f"Transient error (attempt {attempt+1}/{max_retries+1}), retrying in {delay}s: {e}")
                    time.sleep(delay)
                    continue
                raise

    def _prune_messages(self, messages, max_tokens=3500):
        """
        Prunes messages to fit within max_tokens.
        Strategy: Keep the first 2 messages and as many recent messages as possible.
        Tool call/result pairs are kept together to avoid breaking the chain.
        """
        if not messages:
            return []

        def est_tokens(msg):
            return len(str(msg.get("content", "")).split()) * 1.5 + 20

        # Group messages into atomic chunks (tool_calls + tool_results stay together)
        chunks = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            if msg.get("tool_calls") and i + 1 < len(messages) and messages[i + 1].get("role") == "tool_results":
                chunks.append([msg, messages[i + 1]])
                i += 2
            else:
                chunks.append([msg])
                i += 1

        first_few = chunks[:2] if len(chunks) > 2 else []
        remaining = chunks[2:] if len(chunks) > 2 else chunks

        first_few_tokens = sum(est_tokens(m) for chunk in first_few for m in chunk)
        budget = max_tokens - first_few_tokens - 100

        if budget < 500:
            budget = max_tokens - 100
            first_few = []
            remaining = chunks

        pruned_recent = []
        current_tokens = 0
        for chunk in reversed(remaining):
            tokens = sum(est_tokens(m) for m in chunk)
            if current_tokens + tokens < budget:
                pruned_recent.insert(0, chunk)
                current_tokens += tokens
            else:
                break

        result = []
        for chunk in first_few + pruned_recent:
            result.extend(chunk)
        return result

    def run(self):
        raise NotImplementedError("Subclasses must implement run()")

    def _is_truncated(self, text, finish_reason):
        """Check if response was cut off."""
        if finish_reason == "length":
            return True
        # Heuristic: ends mid-word or mid-sentence for substantial responses
        stripped = text.rstrip()
        if stripped and stripped[-1] not in '.!?"\')]}':
            if len(stripped) > 100:
                return True
        return False

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
            
            # For connection errors, provide actionable message
            if isinstance(e, (urllib.error.URLError, socket.timeout, ConnectionError)):
                err_text = self._classify_error(e)

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
                            delay = self.gen_params.get("streaming_delay", 0.0)
                            if delay > 0: time.sleep(delay)
                        if "tool_calls" in msg_chunk: tool_calls.extend(msg_chunk["tool_calls"])
                    
                    if chunk.get("done"):
                        stats = {
                            "total_duration": chunk.get("total_duration", 0),
                            "eval_count": chunk.get("eval_count", 0),
                            "eval_duration": chunk.get("eval_duration", 0),
                            "prompt_eval_count": chunk.get("prompt_eval_count", 0)
                        }
                        if chunk.get("done_reason") == "length" or self._is_truncated(full_text, chunk.get("done_reason")):
                            self.truncated.emit()
            
            if tool_calls:
                self.tool_calls_received.emit(tool_calls)
                if not full_text.strip(): return
            
            self.response_finished.emit(full_text, stats)
        except Exception as e:
            log.error(f"Ollama error: {e}")
            raise e

class OpenAIWorker(BaseAIWorker):
    def run(self):
        def _execute():
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
            tool_calls_map = {}
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
                        
                        if choices[0].get("finish_reason") == "length" or self._is_truncated(full_text, choices[0].get("finish_reason")):
                            self.truncated.emit()
                    except Exception as e:
                        log.debug(f"Stream chunk parse error: {e}")
                        continue

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

        try:
            self._run_with_retry(_execute)
        except Exception as e:
            self.error_occurred.emit(self._classify_error(e))

class OpenRouterWorker(OpenAIWorker):
    def run(self):
        def _execute():
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

            payload = {
                "model": self.model,
                "messages": api_messages,
                "stream": True,
            }
            if self.tools: payload["tools"] = self.tools
            if "temperature" in self.gen_params: payload["temperature"] = self.gen_params["temperature"]

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(payload).encode(),
                headers={
                    "Content-Type": "application/json", 
                    "Authorization": f"Bearer {self.api_key}",
                    "HTTP-Referer": "https://github.com/jacobdcook/synapse",
                    "X-Title": "Synapse Desktop"
                }
            )

            full_text = ""
            tool_calls_map = {}
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
                        
                        if choices[0].get("finish_reason") == "length" or self._is_truncated(full_text, choices[0].get("finish_reason")):
                            self.truncated.emit()
                    except Exception as e:
                        log.debug(f"Stream chunk parse error: {e}")
                        continue

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

        try:
            self._run_with_retry(_execute)
        except Exception as e:
            self.error_occurred.emit(self._classify_error(e))

class AnthropicWorker(BaseAIWorker):
    def run(self):
        def _execute():
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
                        except (KeyError, json.JSONDecodeError): continue
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
                                if token: 
                                    full_text += token
                                    self.token_received.emit(token)
                                    delay = self.gen_params.get("streaming_delay", 0.0)
                                    if delay > 0: time.sleep(delay)
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
                        
                        if chunk.get("delta", {}).get("stop_reason") == "max_tokens" or (ctype == "message_stop" and self._is_truncated(full_text, chunk.get("message", {}).get("stop_reason"))):
                            self.truncated.emit()
                    except Exception as e:
                        log.debug(f"Stream chunk parse error: {e}")
                        continue

            if tool_calls:
                self.tool_calls_received.emit(tool_calls)
                if not full_text.strip(): return

            stats = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0)
            }
            self.response_finished.emit(full_text, stats)

        try:
            self._run_with_retry(_execute)
        except Exception as e:
            self.error_occurred.emit(self._classify_error(e))

def WorkerFactory(model, messages, system_prompt="", gen_params=None, tools=None, settings=None):
    settings = settings or {}
    if model.startswith("gpt-") or model.startswith("o1-"):
        return OpenAIWorker(model, messages, system_prompt, gen_params, tools, settings.get("openai_key"))
    elif model.startswith("claude-"):
        return AnthropicWorker(model, messages, system_prompt, gen_params, tools, settings.get("anthropic_key"))
    elif "/" in model and ":" not in model: # OpenRouter models usually have 'provider/name'
        return OpenRouterWorker(model, messages, system_prompt, gen_params, tools, settings.get("openrouter_key"))
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

            # Strip thinking tags from models that use them (qwen3, deepseek, etc.)
            if title:
                title = re.sub(r'<think>.*?</think>', '', title, flags=re.DOTALL).strip()
                title = title.strip('"').strip("'").strip()
                # Truncate overly long titles
                if len(title) >= 80:
                    title = title[:77] + "..."

            if title:
                self.title_ready.emit(self.conv_id, title)
                return
            elif self.model.startswith("claude-") or ("/" in self.model and ":" not in self.model):
                # OpenRouter fallback or Claude
                payload = {
                    "model": self.model,
                    "messages": [{"role": m["role"], "content": m.get("content", "")} for m in summary_msgs if m.get("role") in ALLOWED_ROLES and m["role"] != "system"],
                    "stream": False,
                    "temperature": 0.3
                }
                if "/" in self.model: # OpenRouter
                    url = "https://openrouter.ai/api/v1/chat/completions"
                    key = self.settings.get("openrouter_key")
                else: # Anthropic
                    url = "https://api.anthropic.com/v1/messages"
                    key = self.settings.get("anthropic_key")
                    payload["max_tokens"] = 100
                    system_msg = next((m["content"] for m in summary_msgs if m["role"] == "system"), "")
                    if system_msg: payload["system"] = system_msg

                headers = {"Content-Type": "application/json"}
                if "/" in self.model: headers["Authorization"] = f"Bearer {key}"
                else:
                    headers["x-api-key"] = key
                    headers["anthropic-version"] = "2023-06-01"

                req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)

                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    if "/" in self.model:
                        title = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip().strip('"').strip("'")
                    else:
                        title = data.get("content", [{}])[0].get("text", "").strip().strip('"').strip("'")

                if title:
                    if len(title) >= 80:
                        title = title[:77] + "..."
                    self.title_ready.emit(self.conv_id, title)
                    return

        except Exception as e:
            log.warning(f"Auto-title API failed: {e}")

        # Fallback: use first few words of the user's first message
        try:
            user_msg = next((m.get("content", "") for m in self.messages if m.get("role") == "user"), "")
            if user_msg:
                words = user_msg.split()[:6]
                fallback = " ".join(words)
                if len(fallback) > 50:
                    fallback = fallback[:47] + "..."
                if fallback:
                    self.title_ready.emit(self.conv_id, fallback)
        except Exception:
            pass


class SummaryWorker(QThread):
    summary_ready = pyqtSignal(str, str)

    def __init__(self, model, conv_id, messages, settings=None):
        super().__init__()
        self.model = model
        self.conv_id = conv_id
        self.messages = messages
        self.settings = settings or {}

    def run(self):
        try:
            # Prepare summary prompt
            summary_msgs = [
                {"role": "system", "content": "You are a helpful assistant. Provide a concise, 1-2 sentence executive summary of this conversation so far. Focus on the main topic and any decisions made."},
            ]
            # Include a representative sample of the conversation
            if len(self.messages) > 10:
                summary_msgs.extend(list(self.messages)[:4])
                summary_msgs.append({"role": "user", "content": "... [middle of conversation omitted] ..."})
                summary_msgs.extend(list(self.messages)[-4:])
            else:
                summary_msgs.extend(self.messages)
            
            summary_msgs.append({"role": "user", "content": "GENERATE SUMMARY NOW."})

            # Use WorkerFactory to create a non-streaming worker logic (simpler via direct call)
            if self.model.startswith("gpt-"):
                payload = {
                    "model": self.model,
                    "messages": [{"role": m["role"], "content": str(m.get("content", ""))} for m in summary_msgs if m.get("role") in ALLOWED_ROLES],
                    "stream": False,
                    "temperature": 0.5
                }
                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.settings.get('openai_key')}"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                    summary = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            elif self.model.startswith("claude-"):
                # Simplified Claude hit
                payload = {
                    "model": self.model,
                    "messages": [{"role": m["role"], "content": str(m.get("content", ""))} for m in summary_msgs if m.get("role") in ALLOWED_ROLES and m["role"] != "system"],
                    "max_tokens": 300,
                    "stream": False,
                    "temperature": 0.5
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
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())
                    summary = data.get("content", [{}])[0].get("text", "").strip()
            else:
                # Ollama fallback
                payload = json.dumps({
                    "model": self.model,
                    "messages": [{"role": m["role"], "content": str(m.get("content", ""))} for m in summary_msgs if m.get("role") in ALLOWED_ROLES],
                    "stream": False,
                    "options": {"temperature": 0.5, "num_ctx": 4096}
                }).encode()
                req = urllib.request.Request(f"{get_ollama_url()}/api/chat", data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
                    summary = data.get("message", {}).get("content", "").strip()

            if summary:
                self.summary_ready.emit(self.conv_id, summary)

        except Exception as e:
            log.warning(f"Auto-summary failed: {e}")


class YouTubeWorker(QThread):
    finished = pyqtSignal(str, dict, str) # transcript, metadata, error

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            from ..utils.youtube_handler import YouTubeHandler
            transcript, metadata = YouTubeHandler.get_transcript(self.url)
            if transcript:
                self.finished.emit(transcript, metadata, "")
            else:
                self.finished.emit("", {}, metadata or "Unknown error")
        except Exception as e:
            self.finished.emit("", {}, str(e))


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
        
        # Load settings to check for OpenRouter key
        from ..utils.constants import load_settings
        settings = load_settings()
        or_key = settings.get("openrouter_key")
        
        if or_key:
            try:
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/models",
                    headers={"Authorization": f"Bearer {or_key}"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read())
                    or_models = [m["id"] for m in data.get("data", [])]
                    cloud_models.extend(or_models)
            except Exception as e:
                log.warning(f"Failed to fetch OpenRouter models: {e}")

        try:
            req = urllib.request.Request(f"{get_ollama_url()}/api/tags")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
                models.extend(cloud_models)
                # Deduplicate and sort
                models = sorted(list(set(models)))
                self.models_loaded.emit(models)
        except Exception:
            self.models_loaded.emit(sorted(list(set(cloud_models + ["llama3.2:3b"]))))
