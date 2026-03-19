import logging
import queue
import re
import hashlib
import json
import time
from PyQt5.QtCore import QThread, pyqtSignal, Qt

log = logging.getLogger(__name__)

def _elapsed(t0):
    return time.time() - t0

class AgenticLoop(QThread):
    token_received = pyqtSignal(str)
    tool_executing = pyqtSignal(str, dict)
    tool_result = pyqtSignal(str, str)
    run_command_output = pyqtSignal(str)
    iteration_complete = pyqtSignal(int, str)
    finished = pyqtSignal(str, list, dict)
    error_occurred = pyqtSignal(str)
    permission_requested = pyqtSignal(str, str, dict, int)
    plan_created = pyqtSignal(str)
    reflection = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)

    def __init__(self, model, messages, system_prompt, tools, agent, mcp_manager,
                 settings, gen_params, max_iterations=15):
        super().__init__()
        self.model = model
        self.messages = list(messages)  # Copy
        self.system_prompt = system_prompt
        self.tools = tools
        self.agent = agent
        self.mcp_manager = mcp_manager
        self.settings = settings
        self.gen_params = gen_params
        self.max_iterations = max_iterations
        self._stop = False
        self._permission_responses = {}
        self._iteration = 0
        self._plan = []
        self._last_tool_hash = None
        self._consecutive_duplicates = 0
        self._consecutive_failures = 0

        # Tools that are always auto-approved (read-only)
        self.auto_approve = {
            "read_file", "web_search", "scrape_url",
            "execute_python", "run_test"
        }
        # Tools that need user approval (destructive)
        self.needs_approval = {
            "write_file", "run_command", "git_commit"
        }

    def stop(self):
        self._stop = True

    def approve_tool(self, request_id, approved):
        self._permission_responses[request_id] = approved

    def run(self):
        """Main agentic loop — runs in background thread."""
        t_loop_start = time.time()
        log.info("[AGENTIC] run() started (model=%s, messages=%d, tools=%d)", self.model, len(self.messages), len(self.tools or []))
        try:
            from .api import WorkerFactory

            all_text = ""

            first_user = next((m.get("content", "") for m in self.messages if m.get("role") == "user"), "")
            needs_plan = len(first_user) > 500 or any(k in first_user.lower() for k in ["refactor", "build", "implement", "fix all"])
            if needs_plan and "create" not in first_user.lower()[:100]:
                log.info("[AGENTIC] planning step starting (elapsed=%.1fs)", _elapsed(t_loop_start))
                plan_prompt = "Break this task into numbered steps. Reply with only the steps, one per line."
                plan_msgs = self.messages + [{"role": "user", "content": plan_prompt}]
                plan_worker = WorkerFactory(self.model, plan_msgs, self.system_prompt, self.gen_params, settings=self.settings, tools=[])
                plan_q = queue.Queue()
                plan_worker.response_finished.connect(lambda t, s: plan_q.put(("ok", t, s)), Qt.DirectConnection)
                plan_worker.error_occurred.connect(lambda e: plan_q.put(("err", e, {})), Qt.DirectConnection)
                plan_worker.start()
                try:
                    pt, ptxt, _ = plan_q.get(timeout=60)
                    log.info("[AGENTIC] planning done (elapsed=%.1fs, pt=%s)", _elapsed(t_loop_start), pt)
                    if pt == "ok" and ptxt:
                        self._plan = [l.strip() for l in ptxt.split("\n") if re.match(r"^\d+[\.\)]\s", l.strip())]
                        if self._plan:
                            self.plan_created.emit("\n".join(self._plan))
                except queue.Empty:
                    log.warning("[AGENTIC] planning timed out (60s)")
                except Exception as e:
                    log.warning("[AGENTIC] planning failed: %s", e)
            else:
                log.info("[AGENTIC] planning skipped (elapsed=%.1fs)", _elapsed(t_loop_start))

            for iteration in range(self.max_iterations):
                t_iter = time.time()
                log.info("[AGENTIC] iteration %d/%d start (elapsed=%.1fs)", iteration + 1, self.max_iterations, _elapsed(t_loop_start))
                if self._stop:
                    break

                self._iteration = iteration
                if iteration > 0 and iteration % 3 == 0:
                    log.info("[AGENTIC] reflection step (elapsed=%.1fs)", _elapsed(t_loop_start))
                    self.messages.append({"role": "user", "content": "Review progress. What's done? Remaining? Issues?"})
                    reflect_worker = WorkerFactory(self.model, self.messages, self.system_prompt, self.gen_params, settings=self.settings, tools=[])
                    rq = queue.Queue()
                    reflect_worker.response_finished.connect(lambda t, s: rq.put(("ok", t)), Qt.DirectConnection)
                    reflect_worker.error_occurred.connect(lambda e: rq.put(("err", e)), Qt.DirectConnection)
                    reflect_worker.start()
                    try:
                        rt, rtxt = rq.get(timeout=30)
                        if rt == "ok" and rtxt:
                            self.reflection.emit(rtxt[:500])
                            self.messages.append({"role": "assistant", "content": rtxt})
                    except (queue.Empty, Exception):
                        pass

                result_q = queue.Queue()
                tool_calls_q = queue.Queue()
                tokens_buf = []

                worker = WorkerFactory(
                    self.model, self.messages, self.system_prompt,
                    self.gen_params, settings=self.settings, tools=self.tools
                )
                worker.token_received.connect(lambda t: (tokens_buf.append(t), self.token_received.emit(t)), Qt.DirectConnection)
                worker.tool_calls_received.connect(lambda tc: tool_calls_q.put(tc), Qt.DirectConnection)
                worker.response_finished.connect(lambda text, stats: result_q.put(("done", text, stats)), Qt.DirectConnection)
                worker.error_occurred.connect(lambda err: result_q.put(("error", err, {})), Qt.DirectConnection)

                log.info("[AGENTIC] worker started, blocking on result_q.get(300s) (elapsed=%.1fs)", _elapsed(t_loop_start))
                worker.start()

                try:
                    res = result_q.get(timeout=300)
                except queue.Empty:
                    log.warning("[AGENTIC] TIMEOUT result_q.get(300s) (elapsed=%.1fs)", _elapsed(t_loop_start))
                    self.error_occurred.emit("Model generation timed out.")
                    return

                wait_sec = _elapsed(t_iter)
                result_type, result_data, stats = res
                log.info("[AGENTIC] result_q.get returned type=%s (wait=%.1fs, elapsed=%.1fs)", result_type, wait_sec, _elapsed(t_loop_start))

                if result_type == "error":
                    log.warning("[AGENTIC] error from worker: %s", (result_data or "")[:200])
                    self.error_occurred.emit(result_data)
                    return

                full_text = result_data
                all_text = full_text

                if tool_calls_q.empty():
                    self.messages.append({"role": "assistant", "content": full_text})
                    log.info("[AGENTIC] no tool calls, emitting finished (elapsed=%.1fs, final_msg_len=%d)", _elapsed(t_loop_start), len(full_text))
                    self.finished.emit(full_text, self.messages, stats)
                    return

                tool_calls = tool_calls_q.get()
                log.info("[AGENTIC] got %d tool call(s): %s (elapsed=%.1fs)", len(tool_calls), [c.get("function", {}).get("name") for c in tool_calls], _elapsed(t_loop_start))

                # Add assistant message with tool calls to history
                self.messages.append({
                    "role": "assistant",
                    "content": full_text,
                    "tool_calls": tool_calls
                })

                tool_results_list = []
                for i, call in enumerate(tool_calls):
                    if self._stop: break
                    name = call.get("function", {}).get("name", "")
                    args = call.get("function", {}).get("arguments", {})
                    thash = hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:12]
                    if self._last_tool_hash == (name, thash):
                        self._consecutive_duplicates += 1
                        if self._consecutive_duplicates >= 2:
                            self.messages.append({"role": "user", "content": "You called the same tool with same args twice. Try a different approach."})
                    else:
                        self._consecutive_duplicates = 0
                    self._last_tool_hash = (name, thash)

                    if self._plan:
                        step_desc = self._plan[min(i, len(self._plan) - 1)] if self._plan else ""
                        self.progress.emit(i + 1, len(tool_calls), step_desc)

                    self.tool_executing.emit(name, args)
                    log.info("[AGENTIC] executing tool %s (elapsed=%.1fs)", name, _elapsed(t_loop_start))

                    try:
                        if name.startswith("mcp__"):
                            result = self.mcp_manager.execute_tool(name, args)
                        else:
                            result = self.agent.execute(name, args)
                        self._consecutive_failures = 0
                    except Exception as e:
                        result = f"Error executing tool {name}: {str(e)}"
                        self._consecutive_failures += 1
                        log.warning("[AGENTIC] tool %s failed: %s", name, e)
                        if self._consecutive_failures >= 3:
                            self.messages.append({"role": "user", "content": "Stop and explain what's going wrong."})

                    result_str = str(result)
                    log.info("[AGENTIC] tool %s done (elapsed=%.1fs)", name, _elapsed(t_loop_start))
                    self.tool_result.emit(name, result_str[:500])
                    if name == "run_command":
                        self.run_command_output.emit(result_str)
                    tool_results_list.append({
                        "tool_call_id": call.get("id", ""),
                        "name": name,
                        "content": str(result)
                    })

                # Add tool results to messages
                self.messages.append({
                    "role": "tool_results",
                    "content": tool_results_list
                })

                self.iteration_complete.emit(iteration + 1, f"Executed {len(tool_calls)} tools")
                log.info("[AGENTIC] iteration %d complete, %d tools (elapsed=%.1fs)", iteration + 1, len(tool_calls), _elapsed(t_loop_start))
                time.sleep(0.1)

            log.info("[AGENTIC] max iterations reached, emitting finished (elapsed=%.1fs)", _elapsed(t_loop_start))
            self.finished.emit(all_text, self.messages, {"max_iterations": True})

        except Exception as e:
            log.error("[AGENTIC] loop exception (elapsed=%.1fs): %s", _elapsed(t_loop_start), e, exc_info=True)
            self.error_occurred.emit(str(e))
