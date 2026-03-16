from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QTextEdit, QComboBox, QScrollArea,
    QFrame, QSplitter, QMessageBox, QStackedWidget
)
from PyQt5.QtCore import Qt, pyqtSignal
from ..core.workflow import Workflow, WorkflowNode, WorkflowManager, WorkflowExecutor
from ..utils.constants import RECOMMENDED_MODELS, DEFAULT_MODEL

class NodeEditor(QFrame):
    removed = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, node):
        super().__init__()
        self.node = node
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            NodeEditor {
                background: #252526;
                border: 1px solid #333;
                border-radius: 8px;
                margin-bottom: 10px;
            }
        """)
        layout = QVBoxLayout(self)
        
        # Header: Name + Remove
        header = QHBoxLayout()
        self.name_edit = QLineEdit(self.node.name)
        self.name_edit.setPlaceholderText("Step Name (e.g. Researcher)")
        self.name_edit.setStyleSheet("background: #1e1e1e; font-weight: bold;")
        self.name_edit.textChanged.connect(self._on_changed)
        header.addWidget(self.name_edit)
        
        remove_btn = QPushButton("✕")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet("background: transparent; color: #888; font-weight: bold; border: none;")
        remove_btn.clicked.connect(self.removed.emit)
        header.addWidget(remove_btn)
        layout.addLayout(header)
        
        # Model Selection
        self.model_combo = QComboBox()
        self.model_combo.addItems([DEFAULT_MODEL] + RECOMMENDED_MODELS)
        if self.node.model in [DEFAULT_MODEL] + RECOMMENDED_MODELS:
            self.model_combo.setCurrentText(self.node.model)
        else:
            self.model_combo.addItem(self.node.model)
            self.model_combo.setCurrentText(self.node.model)
        self.model_combo.currentTextChanged.connect(self._on_changed)
        layout.addWidget(QLabel("Model:"))
        layout.addWidget(self.model_combo)
        
        # Prompt Template
        self.prompt_edit = QTextEdit(self.node.prompt_template)
        self.prompt_edit.setPlaceholderText("Enter prompt template... Use {{last}} or {{Step Name}} for variables.")
        self.prompt_edit.setStyleSheet("background: #1e1e1e;")
        self.prompt_edit.setFixedHeight(100)
        self.prompt_edit.textChanged.connect(self._on_changed)
        layout.addWidget(QLabel("Prompt Template:"))
        layout.addWidget(self.prompt_edit)

    def _on_changed(self):
        self.node.name = self.name_edit.text()
        self.node.model = self.model_combo.currentText()
        self.node.prompt_template = self.prompt_edit.toPlainText()
        self.changed.emit()

class WorkflowSidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = WorkflowManager()
        self.current_workflow = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Splitter between list and editor
        self.splitter = QSplitter(Qt.Vertical)
        
        # --- Upper part: List of Workflows ---
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("WORKFLOWS"))
        add_btn = QPushButton("+ New")
        add_btn.clicked.connect(self._create_new)
        header.addWidget(add_btn)
        list_layout.addLayout(header)
        
        self.wf_list = QListWidget()
        self.wf_list.itemClicked.connect(self._on_wf_selected)
        list_layout.addWidget(self.wf_list)
        
        self.splitter.addWidget(list_container)
        
        # --- Lower part: Editor ---
        self.editor_stack = QStackedWidget()
        
        # Empty State
        empty_label = QLabel("Select or create a workflow to edit")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet("color: #666;")
        self.editor_stack.addWidget(empty_label)
        
        # Active Editor
        self.editor_pane = QWidget()
        editor_layout = QVBoxLayout(self.editor_pane)
        
        self.wf_name_edit = QLineEdit()
        self.wf_name_edit.setPlaceholderText("Workflow Name")
        self.wf_name_edit.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.wf_name_edit.textChanged.connect(self._update_current_name)
        editor_layout.addWidget(self.wf_name_edit)
        
        self.nodes_area = QScrollArea()
        self.nodes_area.setWidgetResizable(True)
        self.nodes_container = QWidget()
        self.nodes_layout = QVBoxLayout(self.nodes_container)
        self.nodes_layout.setAlignment(Qt.AlignTop)
        self.nodes_area.setWidget(self.nodes_container)
        editor_layout.addWidget(self.nodes_area)
        
        btn_layout = QHBoxLayout()
        add_step_btn = QPushButton("+ Add Step")
        add_step_btn.clicked.connect(self._add_step)
        btn_layout.addWidget(add_step_btn)
        
        run_btn = QPushButton("▶ Run")
        run_btn.setStyleSheet("background: #007acc; color: white; font-weight: bold;")
        run_btn.clicked.connect(self._run_workflow)
        btn_layout.addWidget(run_btn)
        
        delete_wf_btn = QPushButton("Delete")
        delete_wf_btn.clicked.connect(self._delete_current)
        btn_layout.addWidget(delete_wf_btn)
        
        editor_layout.addLayout(btn_layout)
        
        self.editor_stack.addWidget(self.editor_pane)
        self.splitter.addWidget(self.editor_stack)
        
        layout.addWidget(self.splitter)
        self.refresh()

    def refresh(self):
        self.wf_list.clear()
        for wf in self.manager.workflows:
            item = QListWidgetItem(wf.name)
            item.setData(Qt.UserRole, wf.id)
            self.wf_list.addItem(item)

        if self.wf_list.count() == 0:
            item = QListWidgetItem("No workflows yet. Click 'New Workflow' to create one.")
            item.setFlags(Qt.NoItemFlags)
            self.wf_list.addItem(item)

    def _create_new(self):
        wf = Workflow("Unnamed Workflow")
        self.manager.add_workflow(wf)
        self.refresh()
        # Select it
        for i in range(self.wf_list.count()):
            if self.wf_list.item(i).data(Qt.UserRole) == wf.id:
                self.wf_list.setCurrentRow(i)
                self._on_wf_selected(self.wf_list.item(i))
                break

    def _on_wf_selected(self, item):
        wf_id = item.data(Qt.UserRole)
        self.current_workflow = next((w for w in self.manager.workflows if w.id == wf_id), None)
        if self.current_workflow:
            self.editor_stack.setCurrentIndex(1)
            self.wf_name_edit.setText(self.current_workflow.name)
            self._render_nodes()
        else:
            self.editor_stack.setCurrentIndex(0)

    def _update_current_name(self, name):
        if self.current_workflow:
            self.current_workflow.name = name
            self.manager.save()
            # Update list text without full refresh to avoid losing selection
            item = self.wf_list.currentItem()
            if item:
                item.setText(name)

    def _render_nodes(self):
        # Clear nodes layout
        while self.nodes_layout.count():
            child = self.nodes_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        for node in self.current_workflow.nodes:
            editor = NodeEditor(node)
            editor.removed.connect(lambda n=node: self._remove_step(n))
            editor.changed.connect(self.manager.save)
            self.nodes_layout.addWidget(editor)

    def _add_step(self):
        if not self.current_workflow: return
        node = WorkflowNode()
        self.current_workflow.nodes.append(node)
        self.manager.save()
        self._render_nodes()

    def _remove_step(self, node):
        self.current_workflow.nodes.remove(node)
        self.manager.save()
        self._render_nodes()

    def _delete_current(self):
        if not self.current_workflow: return
        res = QMessageBox.question(self, "Delete Workflow", f"Delete '{self.current_workflow.name}'?")
        if res == QMessageBox.Yes:
            self.manager.remove_workflow(self.current_workflow.id)
            self.current_workflow = None
            self.editor_stack.setCurrentIndex(0)
            self.refresh()

    def _run_workflow(self):
        if not self.current_workflow or not self.current_workflow.nodes:
            return
        
        from .main import MainWindow
        main_win = self.window()
        if not isinstance(main_win, MainWindow):
            return
            
        main_win.status_label.setText(f"Running workflow: {self.current_workflow.name}")
        
        self.executor = WorkflowExecutor(self.current_workflow, None)
        self.executor.node_started.connect(lambda idx, name: main_win.status_label.setText(f"Workflow: {name}..."))
        self.executor.workflow_finished.connect(lambda output: self._on_workflow_done(main_win, output))
        self.executor.node_error.connect(lambda idx, err: QMessageBox.critical(self, "Workflow Error", err))
        self.executor.start()

    def _on_workflow_done(self, main_win, output):
        main_win.status_label.setText("Workflow finished")
        # Optional: Inject final output into chat
        main_win._send_message(f"Workflow completed. Final output:\n\n{output}", bypass_rag=True)
