from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPainter, QColor, QFont, QLinearGradient
from ..core.analytics import analytics_manager
from ..utils.constants import MODEL_PRICES

class StatCard(QFrame):
    def __init__(self, title, value, subtext="", accent_color="#58a6ff"):
        super().__init__()
        self.setObjectName("StatCard")
        self.setStyleSheet(f"""
            #StatCard {{
                background: #1c2128;
                border: 1px solid #30363d;
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        
        title_hl = QLabel(title)
        title_hl.setStyleSheet("color: #8b949e; font-size: 11px; font-weight: 600; text-transform: uppercase;")
        
        self.value_lb = QLabel(value)
        self.value_lb.setStyleSheet(f"color: {accent_color}; font-size: 24px; font-weight: 700;")
        
        self.sub_lb = QLabel(subtext)
        self.sub_lb.setStyleSheet("color: #484f58; font-size: 11px;")
        
        layout.addWidget(title_hl)
        layout.addWidget(self.value_lb)
        layout.addWidget(self.sub_lb)

class ProgressBar(QWidget):
    def __init__(self, label, percentage, color="#58a6ff"):
        super().__init__()
        self.label = label
        self.percentage = percentage
        self.color = color
        self.setMinimumHeight(30)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        # Label
        p.setPen(QColor("#e6edf3"))
        p.setFont(QFont("Inter", 10))
        p.drawText(0, 12, self.label)
        
        # Track
        track_y = 18
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#30363d"))
        p.drawRoundedRect(0, track_y, self.width(), 6, 3, 3)
        
        # Progress
        if self.percentage > 0:
            p.setBrush(QColor(self.color))
            p.drawRoundedRect(0, track_y, int(self.width() * (self.percentage / 100)), 6, 3, 3)

class AnalyticsSidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.refresh()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 16, 16, 16)
        self.layout.setSpacing(16)
        
        header = QLabel("Usage Analytics")
        header.setStyleSheet("font-size: 18px; font-weight: 700; color: #e6edf3; margin-bottom: 8px;")
        self.layout.addWidget(header)
        
        # Scroll area for the rest
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        container = QWidget()
        self.scroll_layout = QVBoxLayout(container)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(16)
        
        # Cards
        self.token_card = StatCard("Total Tokens", "0", "All-time usage")
        self.cost_card = StatCard("Est. Cost", "$0.00", "Based on cloud pricing", "#7ee787")
        self.scroll_layout.addWidget(self.token_card)
        self.scroll_layout.addWidget(self.cost_card)
        
        # Model Breakdown
        self.breakdown_group = QFrame()
        self.breakdown_group.setStyleSheet("background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 12px;")
        self.breakdown_layout = QVBoxLayout(self.breakdown_group)
        
        breakdown_title = QLabel("Model Breakdown")
        breakdown_title.setStyleSheet("color: #e6edf3; font-weight: 600; margin-bottom: 8px;")
        self.breakdown_layout.addWidget(breakdown_title)
        
        self.scroll_layout.addWidget(self.breakdown_group)
        self.scroll_layout.addStretch()
        
        scroll.setWidget(container)
        self.layout.addWidget(scroll)

    def refresh(self):
        stats = analytics_manager.get_stats()
        
        # Update cards
        self.token_card.value_lb.setText(f"{stats['total_tokens']:,}")
        
        # Calculate cost
        total_cost = 0.0
        for log in analytics_manager.logs:
            model = log["model"]
            if model in MODEL_PRICES:
                price = MODEL_PRICES[model]
                in_cost = (log["input_tokens"] / 1_000_000) * price["input"]
                out_cost = (log["output_tokens"] / 1_000_000) * price["output"]
                total_cost += (in_cost + out_cost)
        
        self.cost_card.value_lb.setText(f"${total_cost:.2f}")
        
        # Update breakdown
        # Clear old widgets
        for i in reversed(range(1, self.breakdown_layout.count())):
            self.breakdown_layout.itemAt(i).widget().setParent(None)
            
        by_model = stats["by_model"]
        total = stats["total_tokens"] or 1
        
        # Sort by usage
        sorted_models = sorted(by_model.items(), key=lambda x: x[1], reverse=True)
        for model, count in sorted_models[:5]:
            pct = (count / total) * 100
            bar = ProgressBar(f"{model} ({count:,})", pct)
            self.breakdown_layout.addWidget(bar)
        
        if not sorted_models:
            empty = QLabel("No data yet")
            empty.setStyleSheet("color: #484f58; font-style: italic;")
            self.breakdown_layout.addWidget(empty)

    def apply_theme(self, theme):
        bg = theme.get("bg", "#1a1b1e")
        fg = theme.get("fg", "#e6edf3")
        sidebar_bg = theme.get("sidebar_bg", "#1e1f23")
        header_bg = theme.get("header_bg", "#161b22")
        accent = theme.get("accent", "#58a6ff")
        input_bg = theme.get("input_bg", "#0d1117")
        border = theme.get("border", "#30363d")
        muted = "#8b949e"

        for lbl in self.findChildren(QLabel):
            if lbl.text() == "Usage Analytics":
                lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {fg}; margin-bottom: 8px;")

        self.token_card.setStyleSheet(f"""
            #StatCard {{
                background: {sidebar_bg};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 16px;
            }}
        """)
        self.cost_card.setStyleSheet(f"""
            #StatCard {{
                background: {sidebar_bg};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 16px;
            }}
        """)

        self.breakdown_group.setStyleSheet(
            f"background: {header_bg}; border: 1px solid {border}; border-radius: 12px; padding: 12px;"
        )

        for lbl in self.breakdown_group.findChildren(QLabel):
            if lbl.text() == "Model Breakdown":
                lbl.setStyleSheet(f"color: {fg}; font-weight: 600; margin-bottom: 8px;")
