"""
Icon audit utility for CorelDRAW Automation Toolkit.
Lists all QPushButton instances and their icon sizes.
Run in an environment with PyQt5 installed.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from PyQt5.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout, QGridLayout, QLabel, QScrollArea
from PyQt5.QtCore import Qt

from src.ui.main_window import MainWindow
from src.tools.curve_filler.curve_filler_widget import CurveFillerWidget
from src.tools.rhinestone.rhinestone_widget import RhinestoneWidget
from src.tools.batch_processor.batch_widget import BatchProcessorWidget
from src.tools.object_manipulation.object_tools_widget import ObjectToolsWidget
from src.tools.typography.typography_widget import TypographyWidget
from src.ui.widgets.preset_browser import PresetBrowser
from src.ui.dialogs.help_dialog import HelpDialog
from src.ui.dialogs.settings_dialog import SettingsDialog
from src.ui.dialogs.about_dialog import AboutDialog


def _norm(text: str) -> str:
    return text.replace("&", "").strip()


def audit_widget(widget, name: str) -> None:
    print(f"\n=== {name} ===")
    buttons = widget.findChildren(QPushButton)
    if not buttons:
        print("No QPushButton found.")
        return
    for btn in buttons:
        icon = btn.icon()
        size = btn.iconSize()
        text = _norm(btn.text())
        has_icon = "yes" if not icon.isNull() else "no"
        print(f"- {text or '<no text>'}: icon={has_icon} size={size.width()}x{size.height()}")


def main() -> int:
    app = QApplication(sys.argv)

    widgets = [
        (MainWindow(), "MainWindow"),
        (CurveFillerWidget(), "CurveFillerWidget"),
        (RhinestoneWidget(), "RhinestoneWidget"),
        (BatchProcessorWidget(), "BatchProcessorWidget"),
        (ObjectToolsWidget(), "ObjectToolsWidget"),
        (TypographyWidget(), "TypographyWidget"),
        (PresetBrowser(), "PresetBrowser"),
        (HelpDialog(), "HelpDialog"),
        (SettingsDialog(), "SettingsDialog"),
        (AboutDialog(), "AboutDialog"),
    ]

    for widget, name in widgets:
        audit_widget(widget, name)

    preview = QWidget()
    preview.setWindowTitle("Icon Preview")
    preview_layout = QVBoxLayout(preview)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    preview_layout.addWidget(scroll)

    grid_host = QWidget()
    grid = QGridLayout(grid_host)
    grid.setSpacing(8)
    scroll.setWidget(grid_host)

    row = 0
    col = 0
    max_cols = 3

    for widget, name in widgets:
        title = QLabel(name)
        title.setStyleSheet("font-weight: bold;")
        title.setAlignment(Qt.AlignLeft)
        grid.addWidget(title, row, 0, 1, max_cols)
        row += 1

        for btn in widget.findChildren(QPushButton):
            label = QLabel(btn.text() or "<no text>")
            label.setMinimumWidth(200)
            sample = QPushButton(btn.text())
            sample.setIcon(btn.icon())
            sample.setIconSize(btn.iconSize())
            sample.setEnabled(False)

            grid.addWidget(label, row, 0)
            grid.addWidget(sample, row, 1)
            size_label = QLabel(f"{btn.iconSize().width()}x{btn.iconSize().height()}")
            grid.addWidget(size_label, row, 2)

            row += 1

        row += 1

    preview.resize(900, 700)
    preview.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
