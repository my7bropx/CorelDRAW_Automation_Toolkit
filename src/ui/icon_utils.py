"""
Shared icon utilities.
"""

from pathlib import Path
from typing import Dict

from PyQt5.QtWidgets import QPushButton, QWidget
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize


def _icons_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources" / "icons"


def icon_path(name: str) -> Path:
    return _icons_dir() / name


def load_icon(name: str) -> QIcon:
    path = icon_path(name)
    if path.exists():
        return QIcon(str(path))
    return QIcon()


def _normalize_text(text: str) -> str:
    return text.replace("&", "").replace("...", "").strip().lower()


def apply_button_icons(
    root: QWidget,
    icon_map: Dict[str, str],
    default_icon: str = "action.png",
    size: QSize = QSize(16, 16),
) -> None:
    for btn in root.findChildren(QPushButton):
        if not btn.icon().isNull():
            continue
        key = _normalize_text(btn.text())
        icon_name = icon_map.get(key, default_icon)
        icon = load_icon(icon_name)
        if not icon.isNull():
            btn.setIcon(icon)
            btn.setIconSize(size)
