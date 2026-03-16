from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QFrame
from PyQt5.QtCore import Qt

class PlanPanel(QWidget):
    """
    Displays the current agentic plan/task list.
    Updated via the update_plan tool.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title = QLabel("AGENTIC PLAN")
        title.setStyleSheet("font-weight: bold; color: #858585; font-size: 11px;")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
                outline: none;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2d2d2d;
                color: #cccccc;
            }
            QListWidget::item:selected {
                background: #3d3d3d;
                color: #ffffff;
            }
        """)
        layout.addWidget(self.list_widget)

        # Empty state
        self.empty_label = QLabel("No active plan.\nThe AI will generate a plan when starting a complex task.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("color: #555; font-style: italic; margin-top: 20px;")
        layout.addWidget(self.empty_label)
        self.empty_label.hide()
        
        if self.list_widget.count() == 0:
            self.empty_label.show()

    def set_plan(self, steps):
        self.list_widget.clear()
        if not steps:
            self.empty_label.show()
            return
        
        self.empty_label.hide()
        for i, step in enumerate(steps):
            # Simple heuristic: if step starts with [x] or is "Done:", it's completed
            is_done = step.lower().startswith("[x]") or step.lower().startswith("done:")
            clean_step = step
            if is_done:
                clean_step = step.split("]", 1)[-1].strip() if "]" in step else step.split(":", 1)[-1].strip()
            
            display_text = f"{i+1}. {clean_step}"
            item = QListWidgetItem(display_text)
            if is_done:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                item.setForeground(Qt.gray)
            else:
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
            
            self.list_widget.addItem(item)
