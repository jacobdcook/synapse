from PyQt5 import QtWebEngineWidgets  # Must be imported before QApplication
import os
import sys
import logging
import logging.handlers
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox
from .utils.constants import APP_NAME, CONFIG_DIR

# Configure logging — use proper data directory with rotation
LOG_DIR = CONFIG_DIR
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_path = str(LOG_DIR / "synapse.log")

log_level = os.environ.get("SYNAPSE_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            log_path, maxBytes=2*1024*1024, backupCount=3  # 2MB per file, keep 3 backups
        )
    ]
)
log = logging.getLogger(__name__)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    try:
        from .utils.constants import load_settings, get_theme_qss
        settings = load_settings()
        theme_name = settings.get("theme", "One Dark")
        app.setStyleSheet(get_theme_qss(theme_name))
    except Exception as e:
        log.warning(f"Failed to load theme, using default: {e}")
        from .utils.constants import DARK_THEME_QSS
        app.setStyleSheet(DARK_THEME_QSS)

    try:
        from .ui.main import MainWindow
        log.info("Starting Synapse...")
        window = MainWindow()
        window.show()
        log.info("Synapse ready")
        sys.exit(app.exec_())
    except Exception as e:
        log.critical(f"Fatal error: {e}", exc_info=True)
        QMessageBox.critical(None, "Synapse Error", f"Failed to start:\n\n{e}\n\nCheck {log_path} for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
