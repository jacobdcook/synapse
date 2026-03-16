import re
from pathlib import Path

LANG_EXTENSIONS = {
    "python": ".py", "python3": ".py", "py": ".py",
    "javascript": ".js", "js": ".js", "jsx": ".jsx", "tsx": ".tsx",
    "typescript": ".ts", "ts": ".ts",
    "html": ".html", "css": ".css", "scss": ".scss",
    "java": ".java", "cpp": ".cpp", "c": ".c", "h": ".h",
    "go": ".go", "rust": ".rs", "ruby": ".rb",
    "bash": ".sh", "sh": ".sh", "shell": ".sh",
    "sql": ".sql", "json": ".json", "yaml": ".yml", "yml": ".yml",
    "xml": ".xml", "markdown": ".md", "md": ".md",
    "dockerfile": "Dockerfile", "makefile": "Makefile",
    "toml": ".toml", "ini": ".ini", "cfg": ".cfg",
    "r": ".r", "swift": ".swift", "kotlin": ".kt",
    "php": ".php", "lua": ".lua", "perl": ".pl",
}


class CodeExtractor:
    @staticmethod
    def extract_blocks(messages):
        blocks = []
        for i, msg in enumerate(messages):
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            for m in re.finditer(r'```([\w+#.-]*)\n?(.*?)\n?```', content, re.DOTALL):
                lang = m.group(1).lower() or "text"
                code = m.group(2)
                blocks.append((lang, code, i))
        return blocks

    @staticmethod
    def generate_filename(lang, code, index):
        ext = LANG_EXTENSIONS.get(lang, ".txt")

        if lang in ("python", "python3", "py"):
            m = re.search(r'^(?:class|def)\s+(\w+)', code, re.MULTILINE)
            if m:
                return f"{m.group(1).lower()}{ext}"
        elif lang in ("javascript", "js", "typescript", "ts", "jsx", "tsx"):
            m = re.search(r'(?:export\s+default\s+)?(?:function|class|const)\s+(\w+)', code)
            if m:
                return f"{m.group(1)}{ext}"
        elif lang in ("html",):
            title_m = re.search(r'<title>(.*?)</title>', code, re.IGNORECASE)
            if title_m:
                name = re.sub(r'[^\w]', '_', title_m.group(1).lower())
                return f"{name}{ext}"
        elif lang in ("dockerfile",):
            return "Dockerfile"
        elif lang in ("makefile",):
            return "Makefile"

        return f"code_{index:02d}{ext}"

    @staticmethod
    def extract_to_directory(messages, target_dir):
        target = Path(target_dir)
        target.mkdir(parents=True, exist_ok=True)

        blocks = CodeExtractor.extract_blocks(messages)
        results = []
        used_names = set()

        for i, (lang, code, msg_idx) in enumerate(blocks):
            name = CodeExtractor.generate_filename(lang, code, i)
            if name in used_names:
                stem = Path(name).stem
                suffix = Path(name).suffix
                name = f"{stem}_{i}{suffix}"
            used_names.add(name)

            filepath = target / name
            filepath.write_text(code)
            results.append((name, lang, code.count('\n') + 1))

        return results
