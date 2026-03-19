"""Parallel tool execution with dependency analysis."""
import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from PyQt5.QtCore import QObject, pyqtSignal

log = logging.getLogger(__name__)

PARALLELIZABLE = {"read_file", "web_search", "scrape_url", "execute_python"}
TIMEOUT_CALL = 30
TIMEOUT_BATCH = 60


def _args_hash(args):
    return hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest()[:16]


class ToolOrchestrator(QObject):
    def __init__(self, execute_fn, parallelizable=None):
        super().__init__()
        self.execute_fn = execute_fn
        self.parallelizable = parallelizable or PARALLELIZABLE

    def execute_batch(self, tool_calls, get_parallelizable=None):
        get_parallelizable = get_parallelizable or (lambda n: n in self.parallelizable)
        if len(tool_calls) <= 1:
            results = []
            for tc in tool_calls:
                name = tc.get("function", {}).get("name", "")
                args = tc.get("function", {}).get("arguments", {})
                try:
                    r = self.execute_fn(name, args)
                    results.append({"tool_call_id": tc.get("id", ""), "name": name, "content": str(r)})
                except Exception as e:
                    results.append({"tool_call_id": tc.get("id", ""), "name": name, "content": f"Error: {e}"})
            return results

        parallel = [(i, tc) for i, tc in enumerate(tool_calls) if get_parallelizable(tc.get("function", {}).get("name", ""))]
        sequential = [(i, tc) for i, tc in enumerate(tool_calls) if not get_parallelizable(tc.get("function", {}).get("name", ""))]

        results = [None] * len(tool_calls)

        if parallel:
            with ThreadPoolExecutor(max_workers=min(len(parallel), 4)) as ex:
                futures = {}
                for i, tc in parallel:
                    name = tc.get("function", {}).get("name", "")
                    args = tc.get("function", {}).get("arguments", {})
                    fut = ex.submit(self._run_one, name, args, tc.get("id", ""))
                    futures[fut] = (i, name)

                try:
                    for fut in futures:
                        idx, name = futures[fut]
                        try:
                            r = fut.result(timeout=TIMEOUT_CALL)
                            results[idx] = r
                        except FuturesTimeoutError:
                            results[idx] = {"tool_call_id": "", "name": name, "content": "Error: Timeout"}
                except Exception as e:
                    log.warning(f"Parallel batch error: {e}")

        for i, tc in sequential:
            name = tc.get("function", {}).get("name", "")
            args = tc.get("function", {}).get("arguments", {})
            try:
                r = self._run_one(name, args, tc.get("id", ""))
                results[i] = r
            except Exception as e:
                results[i] = {"tool_call_id": tc.get("id", ""), "name": name, "content": f"Error: {e}"}

        return [r for r in results if r is not None]

    def _run_one(self, name, args, call_id):
        r = self.execute_fn(name, args)
        return {"tool_call_id": call_id, "name": name, "content": str(r)}
