"""
CorelDRAW Automation Toolkit
Main application entry point.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon


def apply_theme(app: QApplication, theme_name: str):
    """Apply application theme."""
    if theme_name == "dark":
        # Gruvbox Dark theme colors
        bg = "#282828"
        bg_bright = "#3c3836"
        fg = "#ebdbb2"
        red = "#cc241d"
        green = "#98971a"
        yellow = "#d79921"
        blue = "#458588"
        aqua = "#689d6a"
        gray = "#928374"
        
        dark_style = f"""
        QMainWindow {{ background-color: {bg}; }}
        QWidget {{ background-color: {bg_bright}; color: {fg}; selection-background-color: {blue}; selection-color: {bg}; }}
        QMenuBar {{ background-color: {bg_bright}; color: {fg}; }}
        QMenuBar::item:selected {{ background-color: {blue}; }}
        QMenu {{ background-color: {bg_bright}; border: 1px solid {gray}; }}
        QMenu::item:selected {{ background-color: {blue}; }}
        QToolBar {{ background-color: {bg_bright}; border: none; spacing: 3px; }}
        QPushButton {{ background-color: {gray}; border: none; border-radius: 4px; padding: 6px 16px; color: {fg}; min-width: 80px; }}
        QPushButton:hover {{ background-color: {aqua}; }}
        QPushButton:pressed {{ background-color: {blue}; }}
        QPushButton:disabled {{ background-color: {bg}; color: {gray}; }}
        QTabWidget::pane {{ border: 1px solid {gray}; background-color: {bg}; }}
        QTabBar::tab {{ background-color: {bg}; color: {fg}; padding: 8px 16px; border: 1px solid {gray}; border-bottom: none; margin-right: 2px; }}
        QTabBar::tab:selected {{ background-color: {bg_bright}; border-bottom: 2px solid {red}; }}
        QTabBar::tab:hover {{ background-color: #504945; }}
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background-color: {bg}; color: {fg}; border: 1px solid {gray}; border-radius: 3px; padding: 4px; }}
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {blue}; }}
        QSlider::groove:horizontal {{ border: 1px solid {gray}; height: 6px; background-color: {bg}; border-radius: 3px; }}
        QSlider::handle:horizontal {{ background-color: {blue}; border: 1px solid {aqua}; width: 14px; margin: -4px 0; border-radius: 7px; }}
        QSlider::handle:horizontal:hover {{ background-color: {aqua}; }}
        QGroupBox {{ border: 1px solid {gray}; border-radius: 4px; margin-top: 8px; padding-top: 8px; color: {fg}; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {yellow}; }}
        QScrollBar:vertical {{ background-color: {bg}; width: 12px; margin: 0; }}
        QScrollBar::handle:vertical {{ background-color: {gray}; border-radius: 6px; min-height: 20px; }}
        QScrollBar::handle:vertical:hover {{ background-color: {aqua}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QStatusBar {{ background-color: {bg}; color: {fg}; }}
        QProgressBar {{ border: 1px solid {gray}; border-radius: 3px; text-align: center; background-color: {bg}; color: {fg}; }}
        QProgressBar::chunk {{ background-color: {green}; border-radius: 2px; }}
        QCheckBox {{ color: {fg}; spacing: 8px; }}
        QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {gray}; border-radius: 3px; background-color: {bg}; }}
        QCheckBox::indicator:checked {{ background-color: {blue}; border-color: {blue}; }}
        QLabel {{ color: {fg}; }}
        QToolTip {{ background-color: {bg_bright}; color: {fg}; border: 1px solid {gray}; padding: 4px; }}
        QDockWidget {{ color: {fg}; titlebar-close-icon: none; }}
        QDockWidget::title {{ background-color: {bg}; padding: 6px; }}
        QTreeView, QListView, QTableView {{ background-color: {bg}; alternate-background-color: {bg_bright}; border: 1px solid {gray}; color: {fg}; }}
        QTreeView::item:selected, QListView::item:selected, QTableView::item:selected {{ background-color: {blue}; color: {bg}; }}
        QHeaderView::section {{ background-color: {bg_bright}; color: {fg}; border: 1px solid {gray}; padding: 4px; }}
        """
        app.setStyleSheet(dark_style)
    else:
        app.setStyleSheet("")


def setup_logging(log_dir: Path):
    """Setup application logging."""
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("CorelDRAW_Automation_Toolkit")
    logger.setLevel(logging.INFO)
    
    # File handler
    log_file = log_dir / "app.log"
    handler = logging.FileHandler(log_file, encoding='utf-8')
    handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    logger.info("Logging initialized")
    
    return logger


def main():
    """Main application entry point."""
    # Enable High DPI
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # Create app
    app = QApplication(sys.argv)
    app.setApplicationName("CorelDRAW Automation Toolkit")
    app.setApplicationVersion("0.1.0-beta")
    app.setOrganizationName("CorelDRAW Automation")
    app.setOrganizationDomain("coreldraw-automation.com")

    # Set font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Load config
    from src.config import config
    config.app.theme = config.app.theme or "dark"
    
    # Setup logging
    log_dir = config.logs_directory
    logger = setup_logging(log_dir)
    logger.info("Application starting...")

    # Apply theme
    apply_theme(app, config.app.theme)

    # Set application icon
    try:
        icon_path = Path(__file__).parent / "resources" / "icons" / "app_icon.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
    except Exception as e:
        logger.warning(f"Could not load icon: {e}")

    # Create and show main window
    try:
        from src.ui.main_window import MainWindow
        window = MainWindow()
        window.show()

        # Install bundled macros after UI is visible (faster startup)
        def _install_macros_late():
            try:
                from src.core.macro_installer import install_macros_if_needed
                result = install_macros_if_needed(config)
                if not result.skipped:
                    logger.info(f"Installed macros: {result.installed} files")
            except Exception as e:
                logger.warning(f"Macro install skipped: {e}")

        QTimer.singleShot(250, _install_macros_late)
    except Exception as e:
        logger.error(f"Failed to create window: {e}")
        import traceback
        traceback.print_exc()
        return 1

    logger.info("Application started successfully")

    # Run
    exit_code = app.exec()
    logger.info(f"Application exiting with code {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
