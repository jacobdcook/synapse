#!/usr/bin/env python3
"""
Automated screenshot tool for Synapse.
Launches the app, navigates features, captures screenshots for GitHub.
"""
import sys
import os
import shutil
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QTimer, QSize
from PyQt5.QtGui import QPixmap

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
CONV_DIR = Path.home() / ".local" / "share" / "synapse" / "conversations"
SETTINGS_FILE = Path.home() / ".local" / "share" / "synapse" / "settings.json"

_backup_convs = []

def backup_conversations():
    global _backup_convs
    _backup_convs = []
    if CONV_DIR.exists():
        for f in CONV_DIR.glob("*.json"):
            _backup_convs.append((f.name, f.read_text()))

def restore_conversations():
    if CONV_DIR.exists():
        for f in CONV_DIR.glob("*.json"):
            f.unlink()
    for name, content in _backup_convs:
        (CONV_DIR / name).write_text(content)

def clear_conversations():
    if CONV_DIR.exists():
        for f in CONV_DIR.glob("*.json"):
            f.unlink()

def save_screenshot(widget, name, region=None):
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    if region:
        pixmap = widget.grab(region)
    else:
        pixmap = widget.grab()
    filepath = SCREENSHOT_DIR / f"{name}.png"
    pixmap.save(str(filepath), "PNG")
    print(f"  -> Saved: {filepath}")

def inject_demo_messages(window):
    conv = window.current_conv
    if not conv:
        return
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    conv["messages"] = [
        {
            "role": "user",
            "content": "Can you explain how Python decorators work and show me an example?",
            "timestamp": now,
            "id": "demo-u1",
            "parent_id": None,
        },
        {
            "role": "assistant",
            "content": (
                "A **decorator** is a function that wraps another function to extend its behavior "
                "without modifying it directly.\n\n"
                "Here's a simple timing decorator:\n\n"
                "```python\n"
                "import time\n\n"
                "def timer(func):\n"
                "    def wrapper(*args, **kwargs):\n"
                "        start = time.perf_counter()\n"
                "        result = func(*args, **kwargs)\n"
                "        elapsed = time.perf_counter() - start\n"
                "        print(f\"{func.__name__} took {elapsed:.4f}s\")\n"
                "        return result\n"
                "    return wrapper\n\n"
                "@timer\n"
                "def fetch_data(url):\n"
                "    # simulate network request\n"
                "    time.sleep(0.5)\n"
                "    return {\"status\": \"ok\"}\n\n"
                "fetch_data(\"https://api.example.com\")\n"
                "# Output: fetch_data took 0.5012s\n"
                "```\n\n"
                "The `@timer` syntax is equivalent to `fetch_data = timer(fetch_data)`. "
                "When you call `fetch_data()`, it actually calls `wrapper()`, which times the original function.\n\n"
                "Common real-world decorators include `@staticmethod`, `@property`, `@functools.lru_cache`, "
                "and Flask's `@app.route`."
            ),
            "timestamp": now,
            "model": "llama3.2:3b",
            "duration_ms": 2340,
            "tokens": 187,
            "id": "demo-a1",
            "parent_id": "demo-u1",
        },
    ]
    conv["title"] = "Python Decorators"
    conv["history"] = list(conv["messages"])

def run_screenshots():
    import logging
    logging.basicConfig(level=logging.WARNING)

    app = QApplication(sys.argv)
    app.setApplicationName("Synapse")

    from synapse.utils.constants import DARK_THEME_QSS
    app.setStyleSheet(DARK_THEME_QSS)

    backup_conversations()
    clear_conversations()

    if SETTINGS_FILE.exists():
        settings = json.loads(SETTINGS_FILE.read_text())
    else:
        settings = {}
    settings["onboarding_complete"] = True
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))

    from synapse.ui.main import MainWindow
    window = MainWindow()
    window.resize(1920, 1080)
    window.show()
    screen = app.primaryScreen().geometry()
    x = (screen.width() - 1920) // 2
    y = (screen.height() - 1080) // 2
    window.move(x, y)

    step = [0]
    total_steps = 24

    def next_step():
        try:
            _do_step(step[0])
        except Exception as e:
            print(f"  !! Step {step[0]} failed: {e}")
            import traceback
            traceback.print_exc()
        step[0] += 1
        if step[0] <= total_steps:
            QTimer.singleShot(800, next_step)
        else:
            print("\nAll screenshots captured!")
            restore_conversations()
            QTimer.singleShot(500, app.quit)

    def _do_step(s):
        if s == 0:
            print("[1] Welcome screen...")
            window._on_activity_changed(1)
            window._render_chat()
            QApplication.processEvents()

        elif s == 1:
            save_screenshot(window, "01_welcome")

        elif s == 2:
            print("[2] Chat conversation...")
            inject_demo_messages(window)
            window.title_label.setText("Python Decorators")
            tab_idx = window.chat_tabs.currentIndex()
            if tab_idx >= 0:
                window.chat_tabs.setTabText(tab_idx, "Python Decorators")
            window._render_chat()
            QApplication.processEvents()

        elif s == 3:
            save_screenshot(window, "02_chat")

        elif s == 4:
            print("[3] Model Manager...")
            window._on_activity_changed(2)
            QApplication.processEvents()

        elif s == 5:
            save_screenshot(window, "03_models")

        elif s == 6:
            print("[4] Template Library...")
            window._on_activity_changed(6)
            QApplication.processEvents()

        elif s == 7:
            save_screenshot(window, "04_templates")

        elif s == 8:
            print("[5] Analytics Dashboard...")
            window._on_activity_changed(7)
            QApplication.processEvents()

        elif s == 9:
            save_screenshot(window, "05_analytics")

        elif s == 10:
            print("[6] Image Generation...")
            window._on_activity_changed(10)
            QApplication.processEvents()

        elif s == 11:
            save_screenshot(window, "06_image_gen")

        elif s == 12:
            print("[7] Settings Dialog...")
            from synapse.ui.settings_dialog import SettingsDialog
            dlg = SettingsDialog(window.settings_data, window)
            dlg.resize(800, 650)
            dlg.show()
            QApplication.processEvents()
            save_screenshot(dlg, "07_settings")
            dlg.close()

        elif s == 13:
            print("[8] Onboarding Wizard...")
            from synapse.ui.onboarding import OnboardingWizard
            wiz = OnboardingWizard(window)
            wiz.show()
            QApplication.processEvents()
            save_screenshot(wiz, "08_onboarding")
            wiz.close()

        elif s == 14:
            print("[9] Bookmarks Panel...")
            window._on_activity_changed(12)
            QApplication.processEvents()

        elif s == 15:
            save_screenshot(window, "09_bookmarks")

        elif s == 16:
            print("[10] Workflows Panel...")
            window._on_activity_changed(11)
            QApplication.processEvents()

        elif s == 17:
            save_screenshot(window, "10_workflows")

        elif s == 18:
            print("[11] Model Arena...")
            try:
                models = [window.model_combo.itemText(i) for i in range(window.model_combo.count())]
                if len(models) >= 2:
                    from synapse.ui.arena_dialog import ArenaDialog
                    dlg = ArenaDialog(models, window.settings_data, window)
                    dlg.show()
                    QApplication.processEvents()
                    save_screenshot(dlg, "11_arena")
                    dlg.close()
                else:
                    print("    (skipped - need 2+ models)")
            except Exception as e:
                print(f"    Arena error: {e}")

        elif s == 19:
            print("[12] Prompt Lab...")
            try:
                models = [window.model_combo.itemText(i) for i in range(window.model_combo.count())]
                from synapse.ui.prompt_lab import PromptLab
                dlg = PromptLab(models, window.settings_data, window)
                dlg.show()
                QApplication.processEvents()
                save_screenshot(dlg, "12_prompt_lab")
                dlg.close()
            except Exception as e:
                print(f"    Prompt Lab error: {e}")

        elif s == 20:
            print("[13] Playground...")
            try:
                models = [window.model_combo.itemText(i) for i in range(window.model_combo.count())]
                from synapse.ui.playground import PlaygroundPanel
                dlg = PlaygroundPanel(models, window.settings_data, window)
                dlg.show()
                QApplication.processEvents()
                save_screenshot(dlg, "13_playground")
                dlg.close()
            except Exception as e:
                print(f"    Playground error: {e}")

        elif s == 21:
            print("[14] Branch Tree...")
            window._on_activity_changed(8)
            QApplication.processEvents()

        elif s == 22:
            save_screenshot(window, "14_branch_tree")

        elif s == 23:
            print("[15] Knowledge/RAG...")
            window._on_activity_changed(5)
            QApplication.processEvents()

        elif s == 24:
            save_screenshot(window, "15_knowledge")
            window._on_activity_changed(1)
            QApplication.processEvents()

    print(f"Screenshots will be saved to: {SCREENSHOT_DIR}/\n")
    QTimer.singleShot(3000, next_step)
    app.exec_()

if __name__ == "__main__":
    run_screenshots()
