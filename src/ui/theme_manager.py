import logging
import sys
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication, QStyleFactory, QWidget

logger = logging.getLogger(__name__)


class ThemeManager(QObject):
    theme_applied = pyqtSignal()

    def __init__(self, app: QApplication):
        super().__init__(app)
        self._app = app

    def apply_system_theme(self) -> None:
        style_name = self._preferred_style_name()
        if style_name:
            self._app.setStyle(style_name)
        palette = self._app.style().standardPalette()
        self._app.setPalette(palette)
        self._app.setStyleSheet(self._build_minimal_stylesheet(palette))
        self.theme_applied.emit()
        logger.info("system theme applied style=%s", style_name or self._app.style().objectName())

    def refresh(self, widget: Optional[QWidget] = None) -> None:
        self.apply_system_theme()
        target = widget or self._app.activeWindow()
        if target is not None:
            target.update()

    def _preferred_style_name(self) -> str:
        available = {name.lower(): name for name in QStyleFactory.keys()}
        if sys.platform.startswith("win"):
            for candidate in ("windowsvista", "windows"):
                if candidate in available:
                    return available[candidate]
        if sys.platform == "darwin" and "macintosh" in available:
            return available["macintosh"]
        return ""

    def _build_minimal_stylesheet(self, palette: QPalette) -> str:
        def rgba(color: QColor, alpha: int = 255) -> str:
            tinted = QColor(color)
            tinted.setAlpha(alpha)
            return tinted.name(QColor.HexArgb)

        window = palette.color(QPalette.Window)
        alternate = palette.color(QPalette.AlternateBase)
        button = palette.color(QPalette.Button)
        button_text = palette.color(QPalette.ButtonText)
        mid = palette.color(QPalette.Mid)
        highlight = palette.color(QPalette.Highlight)
        highlighted_text = palette.color(QPalette.HighlightedText)
        text = palette.color(QPalette.Text)
        tooltip_base = palette.color(QPalette.ToolTipBase)
        tooltip_text = palette.color(QPalette.ToolTipText)

        return f"""
        Sidebar {{
            border-right: 1px solid {rgba(mid)};
        }}
        Sidebar QListWidget {{
            border: none;
            outline: none;
        }}
        Sidebar QListWidget::item {{
            min-height: 24px;
            padding: 9px 12px;
            border-radius: 8px;
        }}
        Sidebar QListWidget::item:selected {{
            background: {rgba(highlight)};
            color: {rgba(highlighted_text)};
        }}
        Sidebar QListWidget::item:hover {{
            background: {rgba(alternate, 180)};
            color: {rgba(text)};
        }}
        CollapsibleSection {{
            border: 1px solid {rgba(mid)};
            border-radius: 8px;
        }}
        CollapsibleSection QToolButton {{
            text-align: left;
            padding: 10px 12px;
            font-weight: 600;
            border: none;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            background: {rgba(button)};
            color: {rgba(button_text)};
        }}
        CollapsibleSection QToolButton:hover {{
            background: {rgba(alternate)};
        }}
        QFrame#context_card {{
            background: {rgba(alternate)};
            border: 1px solid {rgba(mid)};
            border-radius: 8px;
        }}
        FormCard {{
            background: {rgba(window)};
            border: 1px solid {rgba(mid)};
            border-radius: 10px;
        }}
        PointillizerPreviewCanvas {{
            border: 1px solid {rgba(mid)};
            border-radius: 8px;
            background: {rgba(window)};
        }}
        QToolTip {{
            background: {rgba(tooltip_base)};
            color: {rgba(tooltip_text)};
            border: 1px solid {rgba(mid)};
            padding: 4px;
        }}
        """
