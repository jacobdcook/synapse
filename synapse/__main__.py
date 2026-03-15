import sys
import logging
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from .ui.main import MainWindow
from .utils.constants import APP_NAME, DARK_THEME_QSS

# Configure logging
log_path = str(Path.home() / ".synapse.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_path)
    ]
)
log = logging.getLogger(__name__)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(DARK_THEME_QSS)

    log.info("Starting Synapse modular version...")
    window = MainWindow()
    window.show()
    log.info("Synapse ready")

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
