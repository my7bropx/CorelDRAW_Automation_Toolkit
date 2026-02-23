"""
About Dialog
Information about the application.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QTextEdit
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap

from ..icon_utils import apply_button_icons


class AboutDialog(QDialog):
    """Dialog showing application information."""

    def __init__(self, parent=None):
        """Initialize the about dialog."""
        super().__init__(parent)
        self.setWindowTitle("About CorelDRAW Automation Toolkit")
        self.setFixedSize(500, 400)
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("CorelDRAW Automation Toolkit")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Version
        version_label = QLabel("Version 0.1.0-beta")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        # Tab widget for different info sections
        tabs = QTabWidget()

        # About tab
        about_widget = QWidget()
        about_layout = QVBoxLayout(about_widget)
        about_text = QLabel(
            "A comprehensive, professional-grade automation suite for "
            "CorelDRAW 2018 and later versions.\n\n"
            "Features:\n"
            "• Advanced Curve Filler with pattern support\n"
            "• Rhinestone Design Automation\n"
            "• Batch Processing System\n"
            "• Object Manipulation Tools\n"
            "• Typography Tools\n"
            "• Preset Management System\n"
            "• Modern PyQt5 Interface\n\n"
            "Designed for professional designers, rhinestone designers, "
            "print shops, sign makers, and CorelDRAW power users."
        )
        about_text.setWordWrap(True)
        about_text.setAlignment(Qt.AlignTop)
        about_layout.addWidget(about_text)
        tabs.addTab(about_widget, "About")

        # License tab
        license_widget = QWidget()
        license_layout = QVBoxLayout(license_widget)
        license_text = QTextEdit()
        license_text.setReadOnly(True)
        license_text.setPlainText(
            "MIT License\n\n"
            "Copyright (c) 2024 CorelDRAW Automation Team\n\n"
            "Permission is hereby granted, free of charge, to any person obtaining a copy "
            "of this software and associated documentation files (the \"Software\"), to deal "
            "in the Software without restriction, including without limitation the rights "
            "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell "
            "copies of the Software, and to permit persons to whom the Software is "
            "furnished to do so, subject to the following conditions:\n\n"
            "The above copyright notice and this permission notice shall be included in all "
            "copies or substantial portions of the Software.\n\n"
            "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR "
            "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, "
            "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE "
            "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER "
            "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, "
            "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE "
            "SOFTWARE."
        )
        license_layout.addWidget(license_text)
        tabs.addTab(license_widget, "License")

        # Credits tab
        credits_widget = QWidget()
        credits_layout = QVBoxLayout(credits_widget)
        credits_text = QLabel(
            "Developed with:\n\n"
            "• Python 3.x\n"
            "• PyQt5 for the user interface\n"
            "• pywin32 for CorelDRAW COM integration\n\n"
            "Special thanks to:\n"
            "• The CorelDRAW user community\n"
            "• Open source contributors\n"
            "• Beta testers and early adopters"
        )
        credits_text.setWordWrap(True)
        credits_text.setAlignment(Qt.AlignTop)
        credits_layout.addWidget(credits_text)
        tabs.addTab(credits_widget, "Credits")

        # System info tab
        system_widget = QWidget()
        system_layout = QVBoxLayout(system_widget)
        system_text = QLabel(
            "System Requirements:\n\n"
            "• Windows 10 or later\n"
            "• CorelDRAW 2018, 2019, 2020, 2021, 2022, 2023, or 2024\n"
            "• Python 3.8 or later (if running from source)\n"
            "• 4 GB RAM minimum\n"
            "• 100 MB disk space\n\n"
            "Recommended:\n"
            "• 8 GB RAM or more\n"
            "• SSD for better performance\n"
            "• High-DPI display support"
        )
        system_text.setWordWrap(True)
        system_text.setAlignment(Qt.AlignTop)
        system_layout.addWidget(system_text)
        tabs.addTab(system_widget, "System")

        layout.addWidget(tabs)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

        apply_button_icons(self, {"close": "clear.png"})
