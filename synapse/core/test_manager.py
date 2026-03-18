import os
import json
import logging
import sys
from PyQt5.QtCore import QObject, pyqtSignal, QProcess

log = logging.getLogger(__name__)

class TestManager(QObject):
    discovery_done = pyqtSignal(list)
    test_result_ready = pyqtSignal(dict)
    test_session_finished = pyqtSignal(dict)
    coverage_updated = pyqtSignal(dict)

    def __init__(self, workspace_root=None):
        super().__init__()
        self.workspace_root = workspace_root
        self._process = QProcess()
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._current_op = None
        self._output_buffer = ""

    def discover_tests(self):
        if not self.workspace_root:
            return
        self._current_op = "discovery"
        self._output_buffer = ""
        # pytest --collect-only -q (quiet to make parsing easier)
        args = ["-m", "pytest", "--collect-only", "-q"]
        self._process.setWorkingDirectory(self.workspace_root)
        self._process.start(sys.executable, args)

    def run_tests(self, test_ids=None):
        if not self.workspace_root:
            return
        self._current_op = "run"
        self._output_buffer = ""
        args = ["-m", "pytest", "-v"] # verbose for per-test results
        if test_ids:
            args.extend(test_ids)
        
        self._process.setWorkingDirectory(self.workspace_root)
        self._process.start(sys.executable, args)

    def run_coverage(self):
        if not self.workspace_root:
            return
        self._current_op = "coverage"
        self._output_buffer = ""
        # Requires pytest-cov
        # We'll use --cov-report=json to get a machine readable file
        args = ["-m", "pytest", "--cov=.", "--cov-report=json:coverage.json"]
        self._process.setWorkingDirectory(self.workspace_root)
        self._process.start(sys.executable, args)

    def _on_stdout(self):
        data = self._process.readAllStandardOutput().data().decode()
        self._output_buffer += data
        if self._current_op == "run":
            # Try to parse line by line for live updates
            lines = self._output_buffer.split("\n")
            self._output_buffer = lines[-1]
            for line in lines[:-1]:
                self._parse_test_line(line)

    def _on_stderr(self):
        data = self._process.readAllStandardError().data().decode()
        if data:
            log.warning(f"Test Process Error: {data}")

    def _on_finished(self, exit_code, exit_status):
        if self._current_op == "discovery":
            tests = self._parse_discovery(self._output_buffer)
            self.discovery_done.emit(tests)
        elif self._current_op == "run":
            self.test_session_finished.emit({"exit_code": exit_code})
        elif self._current_op == "coverage":
            cov_data = self._parse_coverage()
            self.coverage_updated.emit(cov_data)
        self._current_op = None

    def _parse_discovery(self, output):
        tests = []
        for line in output.split("\n"):
            line = line.strip()
            if "::" in line: # pytest node id format
                tests.append(line)
        return tests

    def _parse_coverage(self):
        if not self.workspace_root: return {}
        cov_path = os.path.join(self.workspace_root, "coverage.json")
        if not os.path.exists(cov_path):
            log.warning(f"Coverage file not found at {cov_path}")
            return {}
        try:
            with open(cov_path, "r") as f:
                data = json.load(f)
            
            results = {}
            # coverage.json format varies by version, usually it's {"files": {"path": {"executed_lines": [], "missing_lines": []}}}
            files = data.get("files", {})
            for filepath, file_data in files.items():
                # Make path absolute if it isn't
                abs_path = filepath
                if not os.path.isabs(abs_path):
                    abs_path = os.path.join(self.workspace_root, abs_path)
                
                line_info = {}
                for l in file_data.get("executed_lines", []):
                    line_info[l] = "covered"
                for l in file_data.get("missing_lines", []):
                    line_info[l] = "missed"
                results[abs_path] = line_info
            return results
        except Exception as e:
            log.error(f"Error parsing coverage JSON: {e}")
            return {}

    def _parse_test_line(self, line):
        # Basic parsing for pytest -v output:
        # path/to/file.py::test_name PASSED [ 50%]
        if " PASSED " in line or " FAILED " in line or " SKIPPED " in line:
            parts = line.split()
            if len(parts) >= 2:
                nodeid = parts[0]
                status = parts[1]
                self.test_result_ready.emit({"nodeid": nodeid, "status": status})
