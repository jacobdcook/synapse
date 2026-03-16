import json
import logging
import urllib.request
import urllib.error
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
from PyQt5.QtGui import QFont, QColor, QPalette, QDesktopServices
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QProgressBar, QMessageBox, QGroupBox, QScrollArea, QFrame, QGridLayout,
    QTabWidget, QMenu, QAction
)

from ..utils.constants import get_ollama_url, RECOMMENDED_MODELS
from ..core.hf_api import HuggingFaceAPI

log = logging.getLogger(__name__)


class HFSearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, query):
        super().__init__()
        self.query = query

    def run(self):
        try:
            results = HuggingFaceAPI.search_models(self.query)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class ModelCard(QFrame):
    pull_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    benchmark_requested = pyqtSignal(str)

    def __init__(self, name, size_gb=0, desc="", tags=None, is_installed=False, parent=None):
        super().__init__(parent)
        self.name = name
        self.tags = tags or []
        self._setup_ui(name, size_gb, desc, is_installed)

    def _setup_ui(self, name, size_gb, desc, is_installed):
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedSize(280, 200)
        self.setStyleSheet("""
            ModelCard {
                background-color: #1e1f23;
                border: 1px solid #30363d;
                border-radius: 12px;
            }
            ModelCard:hover {
                border-color: #58a6ff;
                background-color: #252a30;
            }
            .tag {
                background-color: #21262d;
                color: #8b949e;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: bold;
            }
            .tag-fast { color: #3fb950; background-color: rgba(63, 185, 80, 0.1); }
            .tag-coding { color: #bc8cff; background-color: rgba(188, 140, 255, 0.1); }
            .tag-reasoning { color: #d29922; background-color: rgba(210, 153, 34, 0.1); }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header = QHBoxLayout()
        title = QLabel(name.split(":")[0])
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #e6edf3;")
        header.addWidget(title)
        
        if size_gb > 0:
            size_label = QLabel(f"{size_gb:.1f}GB")
            size_label.setStyleSheet("color: #8b949e; font-size: 11px;")
            header.addWidget(size_label, 0, Qt.AlignRight)
        layout.addLayout(header)

        # Tags
        tag_layout = QHBoxLayout()
        tag_layout.setSpacing(4)
        for tag in self.tags:
            t_label = QLabel(tag.upper())
            t_label.setProperty("class", "tag")
            t_label.setStyleSheet(self._get_tag_style(tag))
            tag_layout.addWidget(t_label)
        tag_layout.addStretch()
        layout.addLayout(tag_layout)

        # Description
        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        desc_label.setFixedHeight(40)
        layout.addWidget(desc_label)
        layout.addStretch()

        # Footer Actions
        actions = QHBoxLayout()
        if is_installed:
            bench_btn = QPushButton("Benchmark")
            bench_btn.setCursor(Qt.PointingHandCursor)
            bench_btn.setStyleSheet("background: #30363d; border: 1px solid #484f58; color: #c9d1d9; font-size: 10px; padding: 3px 8px; border-radius: 4px;")
            bench_btn.clicked.connect(lambda: self.benchmark_requested.emit(self.name))
            actions.addWidget(bench_btn)
            
            del_btn = QPushButton("Delete")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet("background: transparent; border: none; color: #f85149; font-size: 10px;")
            del_btn.clicked.connect(lambda: self.delete_requested.emit(self.name))
            actions.addWidget(del_btn)
            
            status = QLabel("READY")
            status.setStyleSheet("color: #3fb950; font-weight: bold; font-size: 10px;")
            actions.addWidget(status, 1, Qt.AlignRight)
        else:
            get_btn = QPushButton("Pull Model")
            get_btn.setCursor(Qt.PointingHandCursor)
            get_btn.setStyleSheet("""
                QPushButton {
                    background-color: #238636;
                    color: white;
                    border-radius: 6px;
                    padding: 4px 12px;
                    font-weight: bold;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #2ea043; }
            """)
            get_btn.clicked.connect(lambda: self.pull_requested.emit(self.name))
            actions.addWidget(get_btn, 1, Qt.AlignRight)
        
        layout.addLayout(actions)

    def _get_tag_style(self, tag):
        base = "border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold; "
        if "fast" in tag.lower(): return base + "color: #3fb950; background-color: rgba(63, 185, 80, 0.1);"
        if "coding" in tag.lower(): return base + "color: #bc8cff; background-color: rgba(188, 140, 255, 0.1);"
        if "reasoning" in tag.lower(): return base + "color: #d29922; background-color: rgba(210, 153, 34, 0.1);"
        return base + "background-color: #21262d; color: #8b949e;"

class HFModelCard(QFrame):
    def __init__(self, model_data):
        super().__init__()
        self.data = model_data
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedSize(280, 220)
        self.setStyleSheet("""
            HFModelCard {
                background-color: #1e1f23;
                border: 1px solid #30363d;
                border-radius: 12px;
            }
            HFModelCard:hover {
                border-color: #58a6ff;
                background-color: #252a30;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # Author and Name
        author = QLabel(self.data.get("author", "unknown"))
        author.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(author)

        name = QLabel(self.data.get("id", "").split("/")[-1])
        name.setStyleSheet("font-weight: bold; font-size: 14px; color: #e6edf3;")
        name.setWordWrap(True)
        layout.addWidget(name)

        # Stats Row
        stats = QHBoxLayout()
        downloads = QLabel(f"↓ {self._format_count(self.data.get('downloads', 0))}")
        downloads.setStyleSheet("color: #8b949e; font-size: 11px;")
        likes = QLabel(f"♥ {self._format_count(self.data.get('likes', 0))}")
        likes.setStyleSheet("color: #8b949e; font-size: 11px;")
        stats.addWidget(downloads)
        stats.addWidget(likes)
        stats.addStretch()
        layout.addLayout(stats)

        # Pipeline Tag
        p_tag = self.data.get("pipeline_tag", "unknown")
        pt_label = QLabel(p_tag.upper())
        pt_label.setStyleSheet("""
            background-color: rgba(88, 166, 255, 0.1);
            color: #58a6ff;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 9px;
            font-weight: bold;
        """)
        layout.addWidget(pt_label, 0, Qt.AlignLeft)

        layout.addStretch()

        # Actions
        actions = QHBoxLayout()
        hf_btn = QPushButton("View on HF")
        hf_btn.setCursor(Qt.PointingHandCursor)
        hf_btn.setStyleSheet("background: #30363d; border: 1px solid #484f58; color: #c9d1d9; font-size: 10px; padding: 4px 10px; border-radius: 6px;")
        hf_btn.clicked.connect(self._open_hf)
        actions.addWidget(hf_btn)

        copy_btn = QPushButton("Copy ID")
        copy_btn.setStyleSheet("background: transparent; border: none; color: #8b949e; font-size: 10px;")
        copy_btn.clicked.connect(self._copy_id)
        actions.addWidget(copy_btn)
        
        layout.addLayout(actions)

    def _format_count(self, n):
        if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
        if n >= 1_000: return f"{n/1_000:.1f}k"
        return str(n)

    def _open_hf(self):
        url = f"https://huggingface.co/{self.data['id']}"
        QDesktopServices.openUrl(QUrl(url))

    def _copy_id(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(self.data["id"])

    def _get_tag_style(self, tag):
        base = "border-radius: 4px; padding: 2px 6px; font-size: 10px; font-weight: bold; "
        if "Fast" in tag: return base + "color: #3fb950; background-color: rgba(63, 185, 80, 0.1);"
        if "Coding" in tag: return base + "color: #bc8cff; background-color: rgba(188, 140, 255, 0.1);"
        if "Reasoning" in tag: return base + "color: #d29922; background-color: rgba(210, 153, 34, 0.1);"
        return base + "background-color: #21262d; color: #8b949e;"


class BenchmarkWorker(QThread):
    finished = pyqtSignal(float)  # tokens/sec

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        import time
        try:
            prompt = "Write a short poem about space."
            payload = json.dumps({
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 100}
            }).encode()
            
            start = time.time()
            req = urllib.request.Request(
                f"{get_ollama_url()}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                duration = time.time() - start
                eval_count = data.get("eval_count", 0)
                # If Ollama doesn't return count, estimate from text length
                if eval_count == 0:
                    text = data.get("response", "")
                    eval_count = len(text.split()) * 1.3
                
                tps = eval_count / duration if duration > 0 else 0
                self.finished.emit(float(tps))
        except Exception as e:
            log.error(f"Benchmark failed: {e}")
            self.finished.emit(0.0)


class ModelPullWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, model_name):
        super().__init__()
        self.model_name = model_name

    def run(self):
        try:
            payload = json.dumps({"name": self.model_name, "stream": True}).encode()
            req = urllib.request.Request(
                f"{get_ollama_url()}/api/pull",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=3600) as resp:
                for line in resp:
                    try:
                        chunk = json.loads(line.decode().strip())
                    except: continue
                    status = chunk.get("status", "")
                    total = chunk.get("total", 0)
                    completed = chunk.get("completed", 0)
                    pct = int(completed / total * 100) if total > 0 else 0
                    self.progress.emit(status, pct)
            self.finished.emit(True, f"Successfully pulled {self.model_name}")
        except Exception as e:
            self.finished.emit(False, str(e))


class ModelManagerPanel(QWidget):
    models_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pull_worker = None
        self._installed_models = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border-top: 1px solid #30363d; background: transparent; }
            QTabBar::tab {
                background: transparent;
                color: #8b949e;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                color: #e6edf3;
                border-bottom: 2px solid #58a6ff;
            }
            QTabBar::tab:hover { color: #ffffff; }
        """)
        self.main_layout.addWidget(self.tabs)

        # Tab 1: Ollama Library
        self.ollama_tab = QWidget()
        self.tabs.addTab(self.ollama_tab, "Ollama Library")
        self._setup_ollama_ui()

        # Tab 2: HF Discovery
        self.hf_tab = QWidget()
        self.tabs.addTab(self.hf_tab, "HuggingFace Discovery")
        self._setup_hf_ui()

    def _setup_ollama_ui(self):
        layout = QVBoxLayout(self.ollama_tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header with Search & Refresh
        header_row = QHBoxLayout()
        title = QLabel("Model Discovery")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e6edf3;")
        header_row.addWidget(title)
        
        header_row.addStretch()
        
        self.pull_input = QLineEdit()
        self.pull_input.setPlaceholderText("Find on Ollama...")
        self.pull_input.setFixedWidth(200)
        self.pull_input.setStyleSheet("padding: 5px; border-radius: 6px;")
        header_row.addWidget(self.pull_input)
        
        self.pull_btn = QPushButton("Pull")
        self.pull_btn.clicked.connect(self._pull_manual)
        header_row.addWidget(self.pull_btn)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        header_row.addWidget(self.refresh_btn)
        
        layout.addLayout(header_row)

        # Progress / Status
        self.pull_progress = QProgressBar()
        self.pull_progress.setFixedHeight(4)
        self.pull_progress.setTextVisible(False)
        self.pull_progress.setVisible(False)
        layout.addWidget(self.pull_progress)
        
        self.pull_status = QLabel("")
        self.pull_status.setStyleSheet("color: #8b949e; font-size: 11px;")
        layout.addWidget(self.pull_status)

        # Scrollable Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        
        self.scroll_content = QWidget()
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setSpacing(15)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

    def _setup_hf_ui(self):
        layout = QVBoxLayout(self.hf_tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        header = QHBoxLayout()
        title = QLabel("Explore the Hub")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #e6edf3;")
        header.addWidget(title)
        
        header.addStretch()
        
        self.hf_search_input = QLineEdit()
        self.hf_search_input.setPlaceholderText("Search HuggingFace Hub...")
        self.hf_search_input.setFixedWidth(300)
        self.hf_search_input.setStyleSheet("padding: 6px; border-radius: 6px;")
        self.hf_search_input.returnPressed.connect(self._search_hf)
        header.addWidget(self.hf_search_input)
        
        hf_search_btn = QPushButton("Search")
        hf_search_btn.clicked.connect(self._search_hf)
        header.addWidget(hf_search_btn)
        
        layout.addLayout(header)

        self.hf_scroll = QScrollArea()
        self.hf_scroll.setWidgetResizable(True)
        self.hf_scroll.setFrameShape(QFrame.NoFrame)
        self.hf_scroll.setStyleSheet("background: transparent;")
        
        self.hf_content = QWidget()
        self.hf_grid = QGridLayout(self.hf_content)
        self.hf_grid.setSpacing(15)
        self.hf_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        
        self.hf_scroll.setWidget(self.hf_content)
        layout.addWidget(self.hf_scroll)

    def _search_hf(self):
        query = self.hf_search_input.text().strip()
        while self.hf_grid.count():
            item = self.hf_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        loading = QLabel("Searching HuggingFace Hub...")
        loading.setStyleSheet("color: #8b949e;")
        self.hf_grid.addWidget(loading, 0, 0)

        self._hf_worker = HFSearchWorker(query)
        self._hf_worker.results_ready.connect(self._on_hf_results)
        self._hf_worker.error.connect(lambda e: self._on_hf_results([]))
        self._hf_worker.start()

    def _on_hf_results(self, results):
        while self.hf_grid.count():
            item = self.hf_grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        row, col = 0, 0
        max_cols = 3
        for m_data in results[:12]:
            card = HFModelCard(m_data)
            self.hf_grid.addWidget(card, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        if not results:
            empty = QLabel("No models found.")
            empty.setStyleSheet("color: #8b949e; font-style: italic;")
            self.hf_grid.addWidget(empty, 0, 0)

    def refresh(self):
        # 1. Fetch installed models
        self._installed_models = []
        try:
            req = urllib.request.Request(f"{get_ollama_url()}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
                for m in data.get("models", []):
                    self._installed_models.append(m["name"])
        except Exception as e:
            log.warning(f"Failed to fetch tags: {e}")

        # 2. Clear grid
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 3. Populate grid
        # Add Recommended Cards
        row, col = 0, 0
        max_cols = 3
        
        for rm in RECOMMENDED_MODELS:
            is_installed = any(rm["name"] in m or m in rm["name"] for m in self._installed_models)
            tags = []
            if "Fast" in rm["desc"]: tags.append("Fast")
            if "Coding" in rm["desc"] or "Coder" in rm["name"]: tags.append("Coding")
            if "Reasoning" in rm["desc"] or "r1" in rm["name"]: tags.append("Reasoning")
            
            card = ModelCard(rm["name"], rm["size_gb"], rm["desc"], tags, is_installed)
            card.pull_requested.connect(self._start_pull)
            card.delete_requested.connect(self._delete_model)
            card.benchmark_requested.connect(self._run_benchmark)
            self.grid.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def _pull_manual(self):
        name = self.pull_input.text().strip()
        if name: self._start_pull(name)

    def _delete_model(self, name):
        reply = QMessageBox.question(self, "Delete Model", f"Remove {name}?", QMessageBox.Yes|QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                payload = json.dumps({"name": name}).encode()
                req = urllib.request.Request(f"{get_ollama_url()}/api/delete", data=payload, headers={"Content-Type": "application/json"}, method="DELETE")
                urllib.request.urlopen(req, timeout=10).read()
                self.refresh()
                self.models_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _run_benchmark(self, name):
        self.pull_progress.setVisible(True)
        self.pull_progress.setMaximum(0) # Busy indicator
        self.pull_status.setText(f"Benchmarking hardware for {name}...")
        
        self._bench_worker = BenchmarkWorker(name)
        self._bench_worker.finished.connect(lambda tps: self._on_bench_finished(name, tps))
        self._bench_worker.start()

    def _on_bench_finished(self, name, tps):
        self.pull_progress.setVisible(False)
        self.pull_progress.setMaximum(100)
        if tps > 0:
            QMessageBox.information(self, "Benchmark Result", f"Model: {name}\nSpeed: {tps:.1f} tokens/sec")
        else:
            QMessageBox.warning(self, "Benchmark Failed", "Could not complete performance test.")

    def _start_pull(self, name):
        if self._pull_worker and self._pull_worker.isRunning(): return
        self.pull_progress.setVisible(True)
        self.pull_status.setText(f"Preparing to pull {name}...")
        self._pull_worker = ModelPullWorker(name)
        self._pull_worker.progress.connect(lambda s, p: (self.pull_progress.setValue(p), self.pull_status.setText(s)))
        self._pull_worker.finished.connect(self._on_pull_finished)
        self._pull_worker.start()

    def _on_pull_finished(self, success, msg):
        self.pull_progress.setVisible(False)
        self.pull_status.setText(msg)
        if success:
            self.refresh()
            self.models_changed.emit()
