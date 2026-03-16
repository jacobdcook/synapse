import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QDateTimeEdit, QListWidget, QListWidgetItem,
    QFrame, QMessageBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QDateTime
from ..core.scheduler import scheduler

log = logging.getLogger(__name__)

class ScheduleSidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        title = QLabel("Scheduled Tasks")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #cccccc; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # New Task Form
        form = QFrame()
        form.setStyleSheet("background-color: #2d2d2d; border-radius: 4px; padding: 10px;")
        form_layout = QVBoxLayout(form)
        
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Task prompt...")
        self.prompt_input.setStyleSheet("background: #3c3c3c; border: 1px solid #454545; color: white;")
        form_layout.addWidget(QLabel("Prompt:"))
        form_layout.addWidget(self.prompt_input)
        
        self.model_combo = QComboBox()
        self.model_combo.setStyleSheet("background: #3c3c3c; border: 1px solid #454545; color: white;")
        form_layout.addWidget(QLabel("Model:"))
        form_layout.addWidget(self.model_combo)

        self.time_input = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.time_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.time_input.setStyleSheet("background: #3c3c3c; color: white;")
        form_layout.addWidget(QLabel("Schedule Time:"))
        form_layout.addWidget(self.time_input)

        add_btn = QPushButton("Schedule Task")
        add_btn.setStyleSheet("background: #0e639c; color: white; padding: 5px; font-weight: bold;")
        add_btn.clicked.connect(self._add_task)
        form_layout.addWidget(add_btn)
        
        layout.addWidget(form)
        
        # Task List
        layout.addWidget(QLabel("Pending Tasks:"))
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("background: #252526; border: none; color: #cccccc;")
        layout.addWidget(self.list_widget)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

    def _add_task(self):
        prompt = self.prompt_input.text()
        if not prompt:
            QMessageBox.warning(self, "Error", "Prompt cannot be empty")
            return
            
        time_iso = self.time_input.dateTime().toPyDateTime().isoformat()
        # In a real app we'd need model and conv_id from main window
        # For now, we'll use placeholders or the current context
        model = self.model_combo.currentText() or "default"
        scheduler.add_task(prompt, model, "default", time_iso)
        self.prompt_input.clear()
        self.refresh()

    def set_models(self, models):
        current = self.model_combo.currentText()
        self.model_combo.clear()
        self.model_combo.addItems(models)
        if current:
            idx = self.model_combo.findText(current)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)

    def refresh(self):
        self.list_widget.clear()
        for task in scheduler.tasks:
            status = task.get('status', 'pending').upper()
            sched = task.get('schedule_time', '')[:16]
            prompt = task.get('prompt', '')[:40]
            model = task.get('model', '')
            text = f"[{status}] {sched} ({model})\n{prompt}"
            item = QListWidgetItem(text)
            self.list_widget.addItem(item)
