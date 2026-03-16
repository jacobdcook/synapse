import logging
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QRubberBand
from PyQt5.QtCore import Qt, QPoint, QRect, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QColor, QCursor, QGuiApplication

log = logging.getLogger(__name__)

class ScreenCaptureWidget(QWidget):
    """
    A full-screen overlay for selecting a region to capture.
    """
    screenshot_captured = pyqtSignal(QPixmap)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowState(Qt.WindowFullScreen)
        self.setCursor(QCursor(Qt.CrossCursor))
        
        # Capture the whole screen first
        screen = QGuiApplication.primaryScreen()
        self.full_pixmap = screen.grabWindow(0)
        
        self.origin = QPoint()
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        painter = QPainter(self)
        # Draw the original screenshot with a dark overlay
        painter.drawPixmap(0, 0, self.full_pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if not self.rubber_band.isHidden():
            # Clear the rubber band area to show the original screen clearly
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(self.rubber_band.geometry(), Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if not self.origin.isNull():
            self.rubber_band.setGeometry(QRect(self.origin, event.pos()).normalized())
            self.update() # Trigger repaint to show clear area

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            rect = self.rubber_band.geometry()
            self.rubber_band.hide()
            self.hide()
            
            if rect.width() > 5 and rect.height() > 5:
                # Use device pixel ratio for high DPI screens
                dpr = QGuiApplication.primaryScreen().devicePixelRatio()
                capture_rect = QRect(
                    int(rect.x() * dpr),
                    int(rect.y() * dpr),
                    int(rect.width() * dpr),
                    int(rect.height() * dpr)
                )
                captured = self.full_pixmap.copy(rect) # full_pixmap is already grabWindow(0)
                self.screenshot_captured.emit(captured)
            
            self.deleteLater()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            self.deleteLater()
