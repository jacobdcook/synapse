import os
import subprocess
import platform
import shlex
import json
import logging
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSignal
from .memory import MemoryManager
from .code_executor import CodeExecutor

log = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name, func, description, parameters):
        self._tools[name] = {
            "function": func,
            "description": description,
            "parameters": parameters
        }

    def get_tool_definitions(self):
        definitions = []
        for name, tool in self._tools.items():
            definitions.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
        return definitions

    def execute(self, name, arguments):
        if name not in self._tools:
            return None

        try:
            return self._tools[name]["function"](**arguments)
        except Exception as e:
            return f"Error executing '{name}': {str(e)}"

class ToolExecutor(QObject):
    approval_requested = pyqtSignal(str, dict) # tool_name, arguments
    execution_finished = pyqtSignal(str) # result
    plan_updated = pyqtSignal(list) # current plan steps

    def __init__(self, workspace_dir=None):
        super().__init__()
        self.workspace_dir = Path(workspace_dir) if workspace_dir else None
        self.registry = ToolRegistry()
        self.memory = MemoryManager()
        self.code_executor = CodeExecutor(workspace_dir)
        self._setup_default_tools()

    def _setup_default_tools(self):
        self.registry.register(
            "read_file",
            self._read_file,
            "Read the contents of a file in the workspace.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the file."}
                },
                "required": ["path"]
            }
        )
        self.registry.register(
            "write_file",
            self._write_file,
            "Write or overwrite a file in the workspace.",
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the file."},
                    "content": {"type": "string", "description": "Content to write."}
                },
                "required": ["path", "content"]
            }
        )
        self.registry.register(
            "run_command",
            self._run_command,
            "Run a terminal command. Use with caution.",
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run."}
                },
                "required": ["command"]
            }
        )
        self.registry.register(
            "web_search",
            self._web_search,
            "Search the internet using DuckDuckGo.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"]
            }
        )
        self.registry.register(
            "scrape_url",
            self._scrape_url,
            "Read the text content of a website.",
            {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to scrape."}
                },
                "required": ["url"]
            }
        )
        self.registry.register(
            "remember_fact",
            self._remember_fact,
            "Save a fact about the user or project to long-term memory.",
            {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The fact to remember."}
                },
                "required": ["fact"]
            }
        )
        self.registry.register(
            "update_preference",
            self._update_preference,
            "Update a user preference in long-term memory.",
            {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The preference key (e.g. 'theme', 'code_style')."},
                    "value": {"type": "string", "description": "The preference value."}
                },
                "required": ["key", "value"]
            }
        )
        self.registry.register(
            "update_plan",
            self._update_plan,
            "Update the internal multi-step plan for the current task.",
            {
                "type": "object",
                "properties": {
                    "plan": {"type": "array", "items": {"type": "string"}, "description": "List of steps in the plan."}
                },
                "required": ["plan"]
            }
        )
        self.registry.register(
            "run_test",
            self._run_test,
            "Run a test command (e.g. pytest, npm test) and get formatted feedback.",
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The test command to run."},
                    "framework": {"type": "string", "description": "The test framework used (optional)."}
                },
                "required": ["command"]
            }
        )
        self.registry.register(
            "generate_image",
            self._generate_image,
            "Generate an image using Stable Diffusion or ComfyUI. Returns the file path of the generated image.",
            {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Text description of the image to generate."},
                    "negative_prompt": {"type": "string", "description": "Things to avoid in the image."},
                    "width": {"type": "integer", "description": "Image width in pixels (default 512)."},
                    "height": {"type": "integer", "description": "Image height in pixels (default 512)."},
                    "steps": {"type": "integer", "description": "Number of diffusion steps (default 20)."},
                    "cfg_scale": {"type": "number", "description": "CFG guidance scale (default 7)."}
                },
                "required": ["prompt"]
            }
        )
        self.registry.register(
            "execute_python",
            self._execute_python,
            "Run Python code and get the output. Supports matplotlib plots which are returned as base64 images.",
            {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "The Python code to execute."}
                },
                "required": ["code"]
            }
        )

    def _validate_path(self, path):
        if not self.workspace_dir:
            return None, "Error: No workspace open."
        if os.path.isabs(path):
            return None, f"Error: Absolute paths are not allowed. Use a relative path within the workspace."
        full_path = (self.workspace_dir / path).resolve()
        ws_resolved = self.workspace_dir.resolve()
        try:
            full_path.relative_to(ws_resolved)
        except ValueError:
            return None, f"Error: Path '{path}' escapes workspace boundary."
        return full_path, None

    def _read_file(self, path):
        full_path, err = self._validate_path(path)
        if err:
            return err
        try:
            return full_path.read_text(errors='replace')
        except Exception as e:
            return f"Error reading file {path}: {e}"

    def _write_file(self, path, content):
        full_path, err = self._validate_path(path)
        if err:
            return err
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            return f"Successfully wrote {path}"
        except Exception as e:
            return f"Error writing file {path}: {e}"

    def _run_command(self, command):
        try:
            # Use platform-aware shlex splitting
            use_posix = (os.name == 'posix')
            args = shlex.split(command, posix=use_posix)
            
            # On Windows, some commands need shell=True to find builtins
            is_windows = (os.name == 'nt')
            
            result = subprocess.run(
                args, capture_output=True, text=True,
                cwd=str(self.workspace_dir) if self.workspace_dir else None,
                timeout=60,
                shell=is_windows
            )
            output = result.stdout
            if result.stderr:
                output += "\nErrors:\n" + result.stderr
            return f"Exit code {result.returncode}\nOutput:\n{output}"
        except Exception as e:
            return f"Error running command: {e}"

    def _web_search(self, query):
        import requests
        from bs4 import BeautifulSoup
        try:
            url = f"https://html.duckduckgo.com/html/?q={query}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for entry in soup.find_all("div", class_="result")[:5]:
                title_tag = entry.find("a", class_="result__a")
                snippet_tag = entry.find("a", class_="result__snippet")
                if title_tag:
                    results.append({
                        "title": title_tag.get_text(),
                        "url": title_tag["href"],
                        "snippet": snippet_tag.get_text() if snippet_tag else ""
                    })
            
            if not results:
                return "No search results found."
            
            output = "Top Search Results:\n"
            for i, r in enumerate(results, 1):
                output += f"{i}. {r['title']}\n   URL: {r['url']}\n   Snippet: {r['snippet']}\n"
            return output
        except Exception as e:
            return f"Search error: {str(e)}"

    def _scrape_url(self, url):
        import requests
        from bs4 import BeautifulSoup
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Remove scripts, styles, etc.
            for tag in soup(["script", "style", "meta", "noscript", "header", "footer", "nav"]):
                tag.decompose()
            
            text = soup.get_text(separator="\n")
            # Clean up whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            cleaned_text = "\n".join(lines)
            
            # Limit output to first 10,000 characters
            if len(cleaned_text) > 10000:
                cleaned_text = cleaned_text[:10000] + "\n... (truncated)"
                
            return f"Content of {url}:\n\n{cleaned_text}"
        except Exception as e:
            return f"Scraping error: {str(e)}"

    def _remember_fact(self, fact):
        added = self.memory.add_fact(fact)
        return f"Successfully remembered: {fact}" if added else "Fact already known."

    def _update_preference(self, key, value):
        self.memory.update_preference(key, value)
        return f"Updated preference: {key} = {value}"

    def _update_plan(self, plan):
        # This will be used by the UI to render a progress bar or checklist
        self.plan_updated.emit(plan)
        plan_str = "\n".join(f"- {step}" for step in plan)
        return f"Plan updated:\n{plan_str}"

    def _run_test(self, command, framework=None):
        """Specialized command runner for tests with better feedback."""
        res = self._run_command(command)
        if "Exit code 0" in res:
            return f"Tests passed!\n{res}"
        else:
            return f"Tests failed. Please analyze the output and fix the errors:\n{res}"

    def _generate_image(self, prompt, negative_prompt="", width=512, height=512, steps=20, cfg_scale=7):
        """Generate an image using local Stable Diffusion or ComfyUI."""
        from .image_gen import ImageGenWorker
        params = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "seed": -1,
        }
        # Try SD first, fall back to ComfyUI
        worker = ImageGenWorker("sd", params)
        try:
            result = worker._run_sd()
        except Exception as sd_err:
            try:
                result = worker._run_comfy()
            except Exception as comfy_err:
                return f"Image generation failed. SD error: {sd_err}. ComfyUI error: {comfy_err}"

        if result.get("success"):
            return f"Image generated successfully!\nSaved to: {result['path']}\n![Generated Image](file://{result['path']})"
        return f"Image generation failed: {result.get('error', 'Unknown error')}"

    def _execute_python(self, code):
        """Execute Python code and return results including images."""
        res = self.code_executor.execute_python(code)
        
        output = f"Exit code {res['exit_code']}\n"
        if res['stdout']:
            output += f"STDOUT:\n{res['stdout']}\n"
        if res['stderr']:
            output += f"STDERR:\n{res['stderr']}\n"
            
        if res['images']:
            output += f"\nGenerated {len(res['images'])} plots:\n"
            for i, img_b64 in enumerate(res['images']):
                output += f"![Plot {i}](data:image/png;base64,{img_b64})\n"
                
        return output.strip() or "Execution finished with no output."

    def request_approval(self, name, arguments):
        # In a real app, this would show a dialog.
        # For now, we signal it.
        self.approval_requested.emit(name, arguments)
