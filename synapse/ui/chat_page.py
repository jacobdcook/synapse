from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWebEngineWidgets import QWebEnginePage

class ChatPage(QWebEnginePage):
    action_requested = pyqtSignal(str, object) # action, data (can be int index or complex str)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        url_str = url.toString()
        if url_str.startswith("action://"):
            parts = url_str.replace("action://", "").split("/")
            action = parts[0] if parts else ""
            
            # Data can be an index or a more complex string like "idx/subaction"
            data = "/".join(parts[1:]) if len(parts) > 1 else -1
            
            # Try to convert to int if it's just a number
            try:
                if isinstance(data, str) and data.isdigit():
                    data = int(data)
            except (ValueError, TypeError):
                pass

            self.action_requested.emit(action, data)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)
