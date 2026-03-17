import os
import sys
import signal
import subprocess
import tempfile
import base64
from pathlib import Path
import logging
from datetime import datetime

log = logging.getLogger(__name__)

class CodeExecutor:
    """
    Executes Python code in a sandboxed-ish subprocess and captures output/plots.
    """
    def __init__(self, workspace_dir=None):
        self.workspace_dir = Path(workspace_dir) if workspace_dir else Path.cwd()
        self.temp_dir = Path(tempfile.gettempdir()) / "synapse_code_exec"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def execute_python(self, code):
        """
        Runs Python code and returns a dict with stdout, stderr, exit_code, and list of image b64s.
        """
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        run_dir = self.temp_dir / session_id
        run_dir.mkdir()

        # Wrap code to capture matplotlib plots
        wrapped_code = self._wrap_code(code, run_dir)
        code_path = run_dir / "script.py"
        code_path.write_text(wrapped_code)

        try:
            result = subprocess.run(
                [sys.executable, str(code_path)],
                capture_output=True,
                text=True,
                cwd=str(self.workspace_dir),
                timeout=30,
                start_new_session=True
            )

            # Collect any generated images
            images = []
            for img_path in sorted(run_dir.glob("plot_*.png")):
                try:
                    data = base64.b64encode(img_path.read_bytes()).decode('utf-8')
                    images.append(data)
                except Exception as e:
                    log.error(f"Failed to read generated image {img_path}: {e}")

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
                "images": images
            }

        except subprocess.TimeoutExpired as e:
            try:
                os.killpg(os.getpgid(e.args[0].pid if hasattr(e, 'args') and e.args else 0), signal.SIGKILL)
            except (ProcessLookupError, OSError, AttributeError):
                pass
            return {
                "stdout": "",
                "stderr": "Execution timed out (30s limit).",
                "exit_code": -1,
                "images": []
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "exit_code": -1,
                "images": []
            }

    def _wrap_code(self, code, run_dir):
        """
        Injects logic to handle matplotlib plots without a GUI.
        """
        run_dir_repr = repr(str(run_dir))
        ws_dir_repr = repr(str(self.workspace_dir))
        prefix = f"""
import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

_run_dir = {run_dir_repr}
_original_show = plt.show
def _intercepted_show(*args, **kwargs):
    fig_count = len(plt.get_fignums())
    if fig_count > 0:
        for i in plt.get_fignums():
            plt.figure(i).savefig(os.path.join(_run_dir, f'plot_{{i}}_{{len(os.listdir(_run_dir))}}.png'))
    plt.close('all')

plt.show = _intercepted_show

sys.path.insert(0, {ws_dir_repr})
"""
        # Append auto-save for any remaining figures at the end
        suffix = f"""
# Auto-save any figures left open
_intercepted_show()
"""
        return prefix + "\n" + code + "\n" + suffix
