import logging
import queue
from PyQt5.QtCore import QThread, pyqtSignal

log = logging.getLogger(__name__)

class AgenticLoop(QThread):
    """
    Agentic loop controller. Runs tool calls in a loop until the model
    stops requesting tools or hits the iteration limit.
    """
    # Signals
    token_received = pyqtSignal(str)           # Streaming tokens from model
    tool_executing = pyqtSignal(str, dict)     # tool_name, args — for progress UI
    tool_result = pyqtSignal(str, str)         # tool_name, result — for display
    iteration_complete = pyqtSignal(int, str)  # iteration_number, summary
    finished = pyqtSignal(str, list, dict)     # final_text, all_messages, stats
    error_occurred = pyqtSignal(str)
    permission_requested = pyqtSignal(str, str, dict, int)  # tool_name, description, args, request_id

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
        self._permission_responses = {}  # request_id -> bool
        self._iteration = 0

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
        try:
            from .api import WorkerFactory
            import time

            all_text = ""

            for iteration in range(self.max_iterations):
                if self._stop:
                    break

                self._iteration = iteration

                # Create a synchronous communication layer for the worker
                result_q = queue.Queue()
                tool_calls_q = queue.Queue()
                tokens_buf = []

                worker = WorkerFactory(
                    self.model, self.messages, self.system_prompt,
                    self.gen_params, settings=self.settings, tools=self.tools
                )

                # Connect signals
                worker.token_received.connect(lambda t: (tokens_buf.append(t), self.token_received.emit(t)))
                worker.tool_calls_received.connect(lambda tc: tool_calls_q.put(tc))
                worker.response_finished.connect(lambda text, stats: result_q.put(("done", text, stats)))
                worker.error_occurred.connect(lambda err: result_q.put(("error", err, {})))
                
                # Start worker in its own thread (it inherits QThread)
                worker.start()

                # Wait for completion (with timeout)
                try:
                    res = result_q.get(timeout=300)
                except queue.Empty:
                    self.error_occurred.emit("Model generation timed out.")
                    return

                result_type, result_data, stats = res

                if result_type == "error":
                    self.error_occurred.emit(result_data)
                    return

                full_text = result_data
                all_text = full_text

                # Check if model made tool calls
                if tool_calls_q.empty():
                    # No tool calls — model is done, agentic loop ends
                    self.finished.emit(full_text, self.messages, stats)
                    return

                # Process tool calls
                tool_calls = tool_calls_q.get()

                # Add assistant message with tool calls to history
                self.messages.append({
                    "role": "assistant",
                    "content": full_text,
                    "tool_calls": tool_calls
                })

                # Execute each tool call
                tool_results_list = []
                for call in tool_calls:
                    if self._stop: break
                    
                    name = call.get("function", {}).get("name", "")
                    args = call.get("function", {}).get("arguments", {})

                    self.tool_executing.emit(name, args)

                    # Execute via agent or MCP
                    try:
                        if name.startswith("mcp__"):
                            result = self.mcp_manager.execute_tool(name, args)
                        else:
                            result = self.agent.execute(name, args)
                    except Exception as e:
                        result = f"Error executing tool {name}: {str(e)}"

                    self.tool_result.emit(name, str(result)[:500])
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

                # Small delay to prevent tight loops
                time.sleep(0.1)

            # Hit max iterations
            self.finished.emit(all_text, self.messages, {"max_iterations": True})

        except Exception as e:
            log.error(f"Agentic loop error: {e}")
            self.error_occurred.emit(str(e))
