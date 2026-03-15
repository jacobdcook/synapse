# Theme definitions for Synapse AI

THEMES = {
    "One Dark": {
        "bg": "#282c34",
        "fg": "#abb2bf",
        "sidebar_bg": "#21252b",
        "header_bg": "#21252b",
        "accent": "#61afef",
        "input_bg": "#21252b",
        "border": "#181a1f",
        "qss": """
            QWidget { background-color: #282c34; color: #abb2bf; }
            QMainWindow, QWidget#central { background-color: #282c34; color: #abb2bf; }
            QLabel { color: #d7dce5; }
            QTreeWidget, QListWidget, QMenu {
                background-color: #21252b;
                border: 1px solid #181a1f;
                color: #d7dce5;
            }
            QTabWidget::pane { border: 1px solid #181a1f; background: #282c34; }
            QTabBar::tab { background: #21252b; color: #c7ced9; padding: 10px; border-right: 1px solid #181a1f; }
            QTabBar::tab:selected { background: #282c34; color: #ffffff; }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #21252b;
                border: 1px solid #181a1f;
                color: #e6eaf1;
                selection-background-color: #61afef;
                selection-color: #0f1114;
            }
            QComboBox {
                background-color: #21252b;
                color: #ffffff;
                border: 1px solid #4b5263;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QComboBox:focus { border: 1px solid #61afef; }
            QComboBox::drop-down { border: none; width: 22px; background: #2c313c; }
            QComboBox::down-arrow { image: none; }
            QComboBox QAbstractItemView {
                background-color: #21252b;
                color: #ffffff;
                border: 1px solid #3e4451;
                selection-background-color: #61afef;
                selection-color: #11151c;
                outline: none;
            }
            QPushButton {
                background-color: #3e4451;
                color: #f4f7fb;
                border: 1px solid #4b5263;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #4b5263; }
            QPushButton:checked { background-color: #61afef; color: #11151c; border: 1px solid #61afef; }
            QStatusBar, QToolBar { background-color: #21252b; color: #d7dce5; }
        """
    },
    "Monokai": {
        "bg": "#272822",
        "fg": "#f8f8f2",
        "sidebar_bg": "#1e1f1c",
        "header_bg": "#1e1f1c",
        "accent": "#a6e22e",
        "input_bg": "#1e1f1c",
        "border": "#000000",
        "qss": """
            QWidget { background-color: #272822; color: #f8f8f2; }
            QMainWindow, QWidget#central { background-color: #272822; color: #f8f8f2; }
            QLabel { color: #f8f8f2; }
            QTreeWidget, QListWidget, QMenu {
                background-color: #1e1f1c;
                border: 1px solid #000000;
                color: #f8f8f2;
            }
            QTabWidget::pane { border: 1px solid #000000; background: #272822; }
            QTabBar::tab { background: #1e1f1c; color: #f8f8f2; padding: 10px; border-right: 1px solid #000000; }
            QTabBar::tab:selected { background: #272822; color: #ffffff; }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #1e1f1c;
                border: 1px solid #000000;
                color: #f8f8f2;
                selection-background-color: #a6e22e;
                selection-color: #111;
            }
            QComboBox {
                background-color: #1e1f1c;
                color: #ffffff;
                border: 1px solid #49483e;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QComboBox:focus { border: 1px solid #a6e22e; }
            QComboBox::drop-down { border: none; width: 22px; background: #2d2f2b; }
            QComboBox::down-arrow { image: none; }
            QComboBox QAbstractItemView {
                background-color: #1e1f1c;
                color: #ffffff;
                border: 1px solid #3e3d32;
                selection-background-color: #a6e22e;
                selection-color: #111;
                outline: none;
            }
            QPushButton {
                background-color: #3e3d32;
                color: #f8f8f2;
                border: 1px solid #49483e;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #49483e; }
            QPushButton:checked { background-color: #a6e22e; color: #111; border: 1px solid #a6e22e; }
            QStatusBar, QToolBar { background-color: #1e1f1c; color: #f8f8f2; }
        """
    },
    "Github Dark": {
        "bg": "#0d1117",
        "fg": "#c9d1d9",
        "sidebar_bg": "#010409",
        "header_bg": "#161b22",
        "accent": "#2f81f7",
        "input_bg": "#0d1117",
        "border": "#30363d",
        "qss": """
            QWidget { background-color: #0d1117; color: #c9d1d9; }
            QMainWindow, QWidget#central { background-color: #0d1117; color: #c9d1d9; }
            QLabel { color: #e6edf3; }
            QTreeWidget, QListWidget, QMenu {
                background-color: #010409;
                border: 1px solid #30363d;
                color: #e6edf3;
            }
            QTabWidget::pane { border: 1px solid #30363d; background: #0d1117; }
            QTabBar::tab { background: #010409; color: #c9d1d9; padding: 10px; border-right: 1px solid #30363d; }
            QTabBar::tab:selected { background: #0d1117; color: #ffffff; }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #010409;
                border: 1px solid #30363d;
                color: #e6edf3;
                selection-background-color: #2f81f7;
                selection-color: #ffffff;
            }
            QComboBox {
                background-color: #161b22;
                color: #ffffff;
                border: 1px solid #484f58;
                padding: 4px 10px;
                border-radius: 6px;
            }
            QComboBox:focus { border: 1px solid #2f81f7; }
            QComboBox::drop-down { border: none; width: 22px; background: #21262d; }
            QComboBox::down-arrow { image: none; }
            QComboBox QAbstractItemView {
                background-color: #161b22;
                color: #ffffff;
                border: 1px solid #30363d;
                selection-background-color: #2f81f7;
                selection-color: #ffffff;
                outline: none;
            }
            QPushButton {
                background-color: #21262d;
                color: #f0f6fc;
                border: 1px solid #30363d;
                padding: 5px 15px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #30363d; }
            QPushButton:checked { background-color: #2f81f7; color: #ffffff; border: 1px solid #2f81f7; }
            QStatusBar, QToolBar { background-color: #161b22; color: #e6edf3; }
        """
    }
}
