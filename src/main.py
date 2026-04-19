"""
CorelDRAW Automation Toolkit
Main application entry point.
"""

import sys
import logging
import time
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter

from src.ui.theme_manager import ThemeManager


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
    import os
    import ctypes
    
    # Force DPI awareness for Windows
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.kernel32.SetProcessDPIAware()
        except Exception:
            pass
    
    # Set Qt scaling environment variables BEFORE QApplication
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
    os.environ['QT_SCALE_FACTOR_ROUNDING_POLICY'] = 'RoundPreferFloor'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_USE_NATIVE_DIALOGS'] = '1'
    
    # Disable OpenGL to avoid scaling issues
    os.environ['QT_OPENGL'] = 'software'
    
    # Enable High DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, False)
    
    # Create app
    app = QApplication(sys.argv)
    app.setApplicationName("CorelDRAW Automation Toolkit")
    app.setApplicationVersion("0.1.0-beta")
    app.setOrganizationName("CorelDRAW Automation")
    app.setOrganizationDomain("coreldraw-automation.com")
    
    # Calculate proper font size based on DPI
    screen = app.primaryScreen()
    if screen:
        dpi = screen.logicalDotsPerInch()
        # Scale font: 9pt at 96 DPI, scale proportionally
        font_scale = max(0.75, min(1.25, dpi / 96.0))
        base_font_size = 9 * font_scale
    else:
        base_font_size = 9
    
    # Set font with calculated size
    font = app.font()
    font.setPointSize(max(8, int(base_font_size)))
    app.setFont(font)

    # Global exception handler
    def exception_hook(exc_type, exc_value, exc_traceback):
        import traceback as tb
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger = logging.getLogger("CorelDRAW_Automation_Toolkit")
        logger.critical("Uncaught exception: %s", "".join(tb.format_exception(exc_type, exc_value, exc_traceback)))
        log_dir = os.path.join(os.environ.get('APPDATA', ''), 'CorelDRAW_Automation_Toolkit', 'logs')
        crash_file = os.path.join(log_dir, f"crash_{int(time.time())}.log")
        try:
            os.makedirs(log_dir, exist_ok=True)
            with open(crash_file, 'w') as f:
                f.write("".join(tb.format_exception(exc_type, exc_value, exc_traceback)))
        except:
            pass
    
    sys.excepthook = exception_hook

    # Load config
    from src.config import config
    config.app.theme = "system"
    
    # Setup logging
    log_dir = config.logs_directory
    logger = setup_logging(log_dir)
    logger.info("Application starting...")

    theme_manager = ThemeManager(app)
    theme_manager.apply_system_theme()
    app.theme_manager = theme_manager

    # Set application icon
    try:
        icon_path = Path(__file__).parent / "resources" / "icons" / "app_icon.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
    except Exception as e:
        logger.warning(f"Could not load icon: {e}")

    # Show splash/loading screen
    from PyQt5.QtGui import QColor

    palette = app.palette()
    splash_bg = palette.color(palette.Window)
    splash_fg = palette.color(palette.WindowText)
    splash_accent = palette.color(palette.Highlight)

    # Create simple splash using the active system palette
    splash_pix = QPixmap(400, 200)
    splash_pix.fill(splash_bg)
    
    # Draw text on splash
    painter = QPainter(splash_pix)
    painter.setPen(splash_fg)
    painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
    painter.drawText(0, 80, 400, 60, int(Qt.AlignCenter), "CorelDRAW Automation Toolkit")
    painter.setFont(QFont("Segoe UI", 11))
    painter.setPen(splash_accent)
    painter.drawText(0, 120, 400, 40, int(Qt.AlignCenter), "Loading...")
    painter.end()
    
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint)
    splash.show()
    app.processEvents()

    # Create and show main window
    try:
        from src.ui.main_window import MainWindow
        window = MainWindow()
        splash.finish(window)
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
