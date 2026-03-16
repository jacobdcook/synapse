import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QScrollArea, QPushButton, QProgressBar, QMenu, QAction,
    QDialog, QLineEdit, QTextEdit, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QFont

from ..core.task_manager import TODO, DOING, DONE

log = logging.getLogger(__name__)

class TaskCard(QFrame):
    """A card representing a single task on the board."""
    status_changed = pyqtSignal(str, str) # task_id, new_status
    delete_requested = pyqtSignal(str)
    agent_assigned = pyqtSignal(str, str) # task_id, agent_id
    
    def __init__(self, task, agent_manager=None, parent=None):
        super().__init__(parent)
        self.task = task
        self.agent_manager = agent_manager
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("TaskCard")
        # Premium styling
        self.setStyleSheet("""
            #TaskCard {
                background: #1c2128;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
            #TaskCard:hover {
                border-color: #58a6ff;
                background: #21262d;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Priority Badge
        p_color = "#8b949e"
        if self.task.get("priority") == "High": p_color = "#f85149"
        elif self.task.get("priority") == "Medium": p_color = "#e3b341"
        
        priority_label = QLabel(self.task.get("priority", "Medium").upper())
        priority_label.setStyleSheet(f"color: {p_color}; font-size: 9px; font-weight: bold;")
        layout.addWidget(priority_label)

        # Title
        title = QLabel(self.task.get("title", "Untitled"))
        title.setWordWrap(True)
        title.setStyleSheet("font-weight: bold; font-size: 13px; color: #e6edf3;")
        layout.addWidget(title)

        # Description (truncated)
        desc_text = self.task.get("description", "")
        if len(desc_text) > 80: desc_text = desc_text[:77] + "..."
        if desc_text:
            desc = QLabel(desc_text)
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #8b949e; font-size: 11px;")
            layout.addWidget(desc)

        # Agent/Model Info
        if self.task.get("agent_id"):
            agent_info = QLabel(f"\U0001f916 {self.task['agent_id']}")
            agent_info.setStyleSheet("color: #bc8cff; font-size: 11px; font-style: italic;")
            layout.addWidget(agent_info)

        # Progress
        if self.task.get("status") == DOING:
            prog = QProgressBar()
            prog.setValue(self.task.get("progress", 0))
            prog.setFixedHeight(4)
            prog.setTextVisible(False)
            prog.setStyleSheet("""
                QProgressBar { background: #21262d; border: none; border-radius: 2px; }
                QProgressBar::chunk { background: #2ea043; border-radius: 2px; }
            """)
            layout.addWidget(prog)

        # Context Menu Trigger
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)

    def _show_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #161b22; border: 1px solid #30363d; color: #e6edf3; }
            QMenu::item:selected { background: #1f6feb; }
        """)
        
        # Move actions
        if self.task["status"] != TODO:
            act_todo = QAction("Move to Todo", self)
            act_todo.triggered.connect(lambda: self.status_changed.emit(self.task["id"], TODO))
            menu.addAction(act_todo)
            
        if self.task["status"] != DOING:
            act_doing = QAction("Move to Doing", self)
            act_doing.triggered.connect(lambda: self.status_changed.emit(self.task["id"], DOING))
            menu.addAction(act_doing)
            
        if self.task["status"] != DONE:
            act_done = QAction("Move to Done", self)
            act_done.triggered.connect(lambda: self.status_changed.emit(self.task["id"], DONE))
            menu.addAction(act_done)
            
        if self.agent_manager:
            assign_menu = menu.addMenu("\U0001f916 Assign Agent")
            assign_menu.setStyleSheet("""
                QMenu { background: #161b22; border: 1px solid #30363d; color: #e6edf3; }
                QMenu::item:selected { background: #238636; }
            """)
            
            # None option
            none_act = QAction("None (Manual)", self)
            none_act.triggered.connect(lambda: self.agent_assigned.emit(self.task["id"], None))
            assign_menu.addAction(none_act)
            assign_menu.addSeparator()

            for agent in self.agent_manager.list_agents():
                act = QAction(f"{agent.icon} {agent.name}", self)
                # Create a closure for the agent_id
                act.triggered.connect(lambda checked, aid=agent.id: self.agent_assigned.emit(self.task["id"], aid))
                assign_menu.addAction(act)

        menu.addSeparator()
        
        act_del = QAction("Delete Task", self)
        act_del.triggered.connect(lambda: self.delete_requested.emit(self.task["id"]))
        menu.addAction(act_del)
        
        menu.exec_(self.mapToGlobal(pos))

class TaskDialog(QDialog):
    """Dialog for creating/editing tasks."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Task")
        self.setFixedWidth(400)
        self.setStyleSheet("background: #161b22; color: #e6edf3;")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        layout.addWidget(QLabel("Task Title"))
        self.title_input = QLineEdit()
        self.title_input.setStyleSheet("background: #0d1117; border: 1px solid #30363d; border-radius: 4px; padding: 6px;")
        layout.addWidget(self.title_input)
        
        layout.addWidget(QLabel("Description"))
        self.desc_input = QTextEdit()
        self.desc_input.setFixedHeight(100)
        self.desc_input.setStyleSheet("background: #0d1117; border: 1px solid #30363d; border-radius: 4px; padding: 6px;")
        layout.addWidget(self.desc_input)
        
        priority_layout = QHBoxLayout()
        priority_layout.addWidget(QLabel("Priority"))
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["Low", "Medium", "High"])
        self.priority_combo.setCurrentText("Medium")
        self.priority_combo.setStyleSheet("background: #0d1117; border: 1px solid #30363d; padding: 4px;")
        priority_layout.addWidget(self.priority_combo)
        layout.addLayout(priority_layout)
        
        btns = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Create Task")
        save_btn.setStyleSheet("background: #238636; color: white; border: none; padding: 8px; border-radius: 4px; font-weight: bold;")
        save_btn.clicked.connect(self.accept)
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

class TaskBoardPanel(QWidget):
    """The main Kanban board interface."""
    
    execution_requested = pyqtSignal(dict) # task data
    
    def __init__(self, task_manager, agent_manager=None, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.agent_manager = agent_manager
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet("background: #161b22; border-bottom: 1px solid #30363d;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 12, 16, 12)

        title_v = QVBoxLayout()
        title = QLabel("Delegative Board")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #e6edf3;")
        title_v.addWidget(title)
        
        subtitle = QLabel("Agentic Task Orchestration")
        subtitle.setStyleSheet("color: #8b949e; font-size: 11px;")
        title_v.addWidget(subtitle)
        h_layout.addLayout(title_v)

        h_layout.addStretch()
        
        add_btn = QPushButton("+ New Task")
        add_btn.setStyleSheet("""
            QPushButton { 
                background: #238636; color: white; border-radius: 6px; 
                padding: 6px 12px; font-weight: bold; border: none;
            }
            QPushButton:hover { background: #2ea043; }
        """)
        add_btn.clicked.connect(self._on_add_clicked)
        h_layout.addWidget(add_btn)

        main_layout.addWidget(header)

        # Columns Container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: #0d1117;")
        
        scroll_widget = QWidget()
        self.columns_layout = QHBoxLayout(scroll_widget)
        self.columns_layout.setContentsMargins(12, 12, 12, 12)
        self.columns_layout.setSpacing(12)

        # Todo Column
        self.todo_col = self._create_column("TODO", "#8b949e")
        # Doing Column
        self.doing_col = self._create_column("IN PROGRESS", "#e3b341")
        # Done Column
        self.done_col = self._create_column("COMPLETED", "#2ea043")

        self.columns_layout.addWidget(self.todo_col["frame"])
        self.columns_layout.addWidget(self.doing_col["frame"])
        self.columns_layout.addWidget(self.done_col["frame"])

        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)

    def _create_column(self, title, color):
        frame = QFrame()
        frame.setFixedWidth(300)
        frame.setStyleSheet(f"""
            QFrame {{ 
                background: #161b22; border: 1px solid #30363d; border-radius: 10px;
            }}
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        header = QLabel(title)
        header.setStyleSheet(f"color: {color}; font-weight: 800; font-size: 11px; margin: 4px;")
        layout.addWidget(header)

        # Container for task cards
        cards_container = QFrame()
        cards_container.setStyleSheet("background: transparent; border: none;")
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(8)
        cards_layout.addStretch() # Push cards to top
        
        layout.addWidget(cards_container)
        
        return {"frame": frame, "layout": cards_layout, "title": title}

    def refresh(self):
        # Clear existing cards
        self._clear_layout(self.todo_col["layout"])
        self._clear_layout(self.doing_col["layout"])
        self._clear_layout(self.done_col["layout"])

        # Add cards
        for task in self.task_manager.tasks:
            card = TaskCard(task, self.agent_manager)
            card.status_changed.connect(self._on_status_changed)
            card.delete_requested.connect(self._on_delete_requested)
            card.agent_assigned.connect(self._on_agent_assigned)
            
            status = task.get("status", TODO)
            if status == TODO:
                self.todo_col["layout"].insertWidget(self.todo_col["layout"].count() - 1, card)
            elif status == DOING:
                self.doing_col["layout"].insertWidget(self.doing_col["layout"].count() - 1, card)
            elif status == DONE:
                self.done_col["layout"].insertWidget(self.done_col["layout"].count() - 1, card)

    def _clear_layout(self, layout):
        while layout.count() > 1: # Keep the stretch
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    @pyqtSlot(str, str)
    def _on_status_changed(self, task_id, new_status):
        task = self.task_manager.move_task(task_id, new_status)
        if new_status == DOING and task and task.get("agent_id"):
            log.info(f"Triggering execution for task {task_id} with agent {task['agent_id']}")
            self.execution_requested.emit(task)
        self.refresh()

    @pyqtSlot(str)
    def _on_delete_requested(self, task_id):
        self.task_manager.delete_task(task_id)
        self.refresh()

    @pyqtSlot(str, str)
    def _on_agent_assigned(self, task_id, agent_id):
        self.task_manager.update_task(task_id, agent_id=agent_id)
        self.refresh()

    def _on_add_clicked(self):
        dial = TaskDialog(self)
        if dial.exec_():
            self.task_manager.add_task(
                dial.title_input.text(),
                dial.desc_input.toPlainText(),
                priority=dial.priority_combo.currentText()
            )
            self.refresh()
