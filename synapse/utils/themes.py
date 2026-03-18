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
            QToolTip { background-color: #21252b; color: #d7dce5; border: 1px solid #181a1f; padding: 4px; }
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
            QToolTip { background-color: #1e1f1c; color: #f8f8f2; border: 1px solid #000000; padding: 4px; }
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
            QToolTip { background-color: #161b22; color: #e6edf3; border: 1px solid #30363d; padding: 4px; }
        """
    },
    "Synapse Glass": {
        "bg": "#0b0e14",
        "fg": "#e6edf3",
        "sidebar_bg": "#0d1117",
        "header_bg": "rgba(22, 27, 34, 0.8)",
        "accent": "#58a6ff",
        "input_bg": "rgba(13, 17, 23, 0.7)",
        "border": "#30363d",
        "qss": """
            QWidget { background-color: #0b0e14; color: #e6edf3; }
            QMainWindow, QWidget#central { background-color: #0b0e14; }
            
            /* Glassmorphism Effect for specific containers */
            QFrame#sidebar, QFrame#header {
                background-color: rgba(22, 27, 34, 0.7);
                border-right: 1px solid rgba(48, 54, 61, 0.5);
            }
            
            QLabel { color: #e6edf3; }
            
            QTreeWidget, QListWidget, QMenu {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
                color: #e6edf3;
            }
            
            QTabWidget::pane { border: 1px solid #30363d; background: #0b0e14; border-radius: 8px; }
            QTabBar::tab { 
                background: #0d1117; 
                color: #8b949e; 
                padding: 12px 20px; 
                border-top-left-radius: 8px; 
                border-top-right-radius: 8px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { 
                background: #161b22; 
                color: #58a6ff; 
                border-bottom: 2px solid #58a6ff;
            }
            
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: rgba(13, 17, 23, 0.8);
                border: 1px solid #30363d;
                border-radius: 10px;
                color: #e6edf3;
                selection-background-color: #58a6ff;
                padding: 8px;
            }
            QLineEdit:focus { border: 1px solid #58a6ff; }
            
            QPushButton {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover { 
                background-color: #30363d; 
                border-color: #8b949e;
            }
            QPushButton:pressed {
                background-color: #161b22;
            }
            QPushButton#accent {
                background-color: #238636;
                border-color: #2ea043;
            }
            
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #30363d;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #484f58;
            }
            
            QProgressBar::chunk {
                background-color: #238636;
                border-radius: 2px;
            }
            QToolTip { background-color: #161b22; color: #e6edf3; border: 1px solid #30363d; padding: 4px; }
        """
    },
    "Github Light": {
        "bg": "#ffffff",
        "fg": "#1f2328",
        "sidebar_bg": "#f6f8fa",
        "header_bg": "#f6f8fa",
        "accent": "#0969da",
        "input_bg": "#ffffff",
        "border": "#d1d9e0",
        "qss": """
            QWidget { background-color: #ffffff; color: #1f2328; }
            QMainWindow, QWidget#central { background-color: #ffffff; color: #1f2328; }
            QLabel { color: #1f2328; }
            QTreeWidget, QListWidget, QMenu {
                background-color: #f6f8fa;
                border: 1px solid #d1d9e0;
                color: #1f2328;
            }
            QTabWidget::pane { border: 1px solid #d1d9e0; background: #ffffff; }
            QTabBar::tab { background: #f6f8fa; color: #656d76; padding: 10px; border-right: 1px solid #d1d9e0; }
            QTabBar::tab:selected { background: #ffffff; color: #1f2328; border-bottom: 2px solid #0969da; }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #ffffff;
                border: 1px solid #d1d9e0;
                color: #1f2328;
                selection-background-color: #0969da;
                selection-color: #ffffff;
            }
            QComboBox {
                background-color: #f6f8fa;
                color: #1f2328;
                border: 1px solid #d1d9e0;
                padding: 4px 10px;
                border-radius: 6px;
            }
            QComboBox:focus { border: 1px solid #0969da; }
            QComboBox::drop-down { border: none; width: 22px; background: #eaeef2; }
            QComboBox::down-arrow { image: none; }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1f2328;
                border: 1px solid #d1d9e0;
                selection-background-color: #0969da;
                selection-color: #ffffff;
                outline: none;
            }
            QPushButton {
                background-color: #f6f8fa;
                color: #1f2328;
                border: 1px solid #d1d9e0;
                padding: 5px 15px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #eaeef2; }
            QPushButton:checked { background-color: #0969da; color: #ffffff; border: 1px solid #0969da; }
            QStatusBar, QToolBar { background-color: #f6f8fa; color: #1f2328; border-top: 1px solid #d1d9e0; }
            QScrollBar:vertical { border: none; background: #f6f8fa; width: 10px; }
            QScrollBar::handle:vertical { background: #d1d9e0; min-height: 20px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #afb8c1; }
            QToolTip { background-color: #ffffff; color: #1f2328; border: 1px solid #d1d9e0; padding: 4px; }
        """
    },
}

import os
import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

def load_external_themes():
    """Load additional themes from user config directory."""
    external_dir = Path.home() / ".local" / "share" / "synapse" / "themes"
    if not external_dir.exists():
        external_dir.mkdir(parents=True, exist_ok=True)
        return {}
        
    themes = {}
    for theme_file in external_dir.glob("*.json"):
        try:
            with open(theme_file, "r") as f:
                theme_data = json.load(f)
                theme_name = theme_data.get("name", theme_file.stem)
                themes[theme_name] = theme_data
        except Exception as e:
            log.warning(f"Failed to load theme {theme_file}: {e}")
            
    return themes

def get_all_themes():
    """Combines built-in themes with external ones."""
    all_themes = THEMES.copy()
    all_themes.update(load_external_themes())
    return all_themes
