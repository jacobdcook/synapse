import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QScrollArea, QPushButton, QProgressBar, QTableWidget,
    QTableWidgetItem, QCheckBox, QGroupBox, QFormLayout,
    QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont

log = logging.getLogger(__name__)

class FineTuningPanel(QWidget):
    """Activity panel for local LLM fine-tuning and LoRA management."""
    
    def __init__(self, lora_manager, parent=None):
        super().__init__(parent)
        self.lora_manager = lora_manager
        self._setup_ui()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header
        header = QLabel("Local Fine-tuning Studio")
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #e6edf3;")
        layout.addWidget(header)

        subtitle = QLabel("Turn your chat history into personalized LoRA adapters for local models.")
        subtitle.setStyleSheet("color: #8b949e; font-size: 14px;")
        layout.addWidget(subtitle)

        # Main Splitter Area (Horizontal)
        content = QHBoxLayout()
        
        # Left: Dataset Builder
        dataset_group = QGroupBox("1. Dataset Preparation")
        dataset_layout = QVBoxLayout(dataset_group)
        
        self.conv_table = QTableWidget()
        self.conv_table.setColumnCount(3)
        self.conv_table.setHorizontalHeaderLabels(["", "Conversation Title", "Messages"])
        self.conv_table.horizontalHeader().setStretchLastSection(True)
        self.conv_table.setStyleSheet("background: #0d1117; border: 1px solid #30363d;")
        dataset_layout.addWidget(self.conv_table)
        
        export_row = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Alpaca", "ShareGPT"])
        export_row.addWidget(QLabel("Format:"))
        export_row.addWidget(self.format_combo)
        
        prep_btn = QPushButton("Prepare JSONL Dataset")
        prep_btn.setStyleSheet("background: #238636; color: white; border-radius: 4px; padding: 8px; font-weight: bold;")
        prep_btn.clicked.connect(self._prepare_dataset)
        export_row.addWidget(prep_btn)
        dataset_layout.addLayout(export_row)
        
        content.addWidget(dataset_group, 3)

        # Right: Training Parameters
        params_group = QGroupBox("2. LoRA Parameters")
        params_layout = QFormLayout(params_group)
        
        self.rank_spin = QSpinBox()
        self.rank_spin.setRange(4, 128)
        self.rank_spin.setValue(16)
        params_layout.addRow("LoRA Rank (r):", self.rank_spin)
        
        self.alpha_spin = QSpinBox()
        self.alpha_spin.setRange(8, 256)
        self.alpha_spin.setValue(32)
        params_layout.addRow("LoRA Alpha:", self.alpha_spin)
        
        self.lr_spin = QDoubleSpinBox()
        self.lr_spin.setRange(0.00001, 0.01)
        self.lr_spin.setDecimals(5)
        self.lr_spin.setValue(0.0002)
        params_layout.addRow("Learning Rate:", self.lr_spin)
        
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1, 100)
        self.epochs_spin.setValue(3)
        params_layout.addRow("Epochs:", self.epochs_spin)
        
        self.base_model_input = QLineEdit()
        self.base_model_input.setPlaceholderText("e.g., llama3:8b")
        params_layout.addRow("Base Model:", self.base_model_input)
        
        train_btn = QPushButton("\U0001f525 Start Training")
        train_btn.setStyleSheet("background: #d73a49; color: white; border-radius: 4px; padding: 12px; font-weight: bold; margin-top: 20px;")
        train_btn.clicked.connect(self._start_training)
        params_layout.addRow(train_btn)
        
        content.addWidget(params_group, 2)
        
        layout.addLayout(content)
        
        # Progress Log
        self.log_area = QFrame()
        self.log_area.setStyleSheet("background: #0d1117; border: 1px solid #30363d; border-radius: 8px;")
        log_layout = QVBoxLayout(self.log_area)
        self.log_label = QLabel("Ready to build dataset...")
        self.log_label.setStyleSheet("color: #8b949e; font-family: monospace;")
        log_layout.addWidget(self.log_label)
        
        self.progress = QProgressBar()
        self.progress.setFixedHeight(4)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("QProgressBar::chunk { background: #58a6ff; }")
        log_layout.addWidget(self.progress)
        
        layout.addWidget(self.log_area)
        
        layout.addStretch()

    def refresh(self):
        """Load conversations into the table."""
        convs = self.lora_manager.store.list_conversations()
        self.conv_table.setRowCount(len(convs))
        
        for i, c in enumerate(convs):
            check = QCheckBox()
            self.conv_table.setCellWidget(i, 0, check)
            
            self.conv_table.setItem(i, 1, QTableWidgetItem(c["title"]))
            
            # Load full content to get message count (or use stats if available)
            count = c.get("stats", {}).get("message_count", 0)
            self.conv_table.setItem(i, 2, QTableWidgetItem(str(count)))

    def _prepare_dataset(self):
        selected_ids = []
        for i in range(self.conv_table.rowCount()):
            check = self.conv_table.cellWidget(i, 0)
            if check.isChecked():
                # We need the ID. Let's re-list or store it in the item
                convs = self.lora_manager.store.list_conversations()
                selected_ids.append(convs[i]["id"])
        
        if not selected_ids:
            QMessageBox.warning(self, "No Selection", "Please select at least one conversation.")
            return
            
        self.log_label.setText("Preparing dataset...")
        self.progress.setValue(30)
        
        path, count = self.lora_manager.prepare_dataset(
            selected_ids, 
            format=self.format_combo.currentText().lower()
        )
        
        if path:
            self.progress.setValue(100)
            self.log_label.setText(f"SUCCESS: Exported {count} pairs to {path}")
            self.current_dataset_path = path # Store for training
        else:
            self.log_label.setText("ERROR: Failed to export dataset.")

    def _start_training(self):
        if not hasattr(self, "current_dataset_path"):
            QMessageBox.warning(self, "Missing Dataset", "Please prepare a dataset first.")
            return
            
        config = {
            "rank": self.rank_spin.value(),
            "alpha": self.alpha_spin.value(),
            "lr": self.lr_spin.value(),
            "epochs": self.epochs_spin.value()
        }
        
        cmd = self.lora_manager.get_training_command(
            self.base_model_input.text() or "base_model",
            self.current_dataset_path,
            config
        )
        
        msg = f"In a real deployment, this would trigger a training script:\n\n{cmd}"
        QMessageBox.information(self, "Training Initiated", msg)
        self.log_label.setText("TRAINING MOCKED: Integration with local training script required.")
