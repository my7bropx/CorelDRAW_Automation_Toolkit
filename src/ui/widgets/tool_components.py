from typing import Iterable, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ToolHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        title_font = QFont(self.title_label.font())
        title_font.setPointSize(max(title_font.pointSize(), 14))
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setWordWrap(True)
        subtitle_font = QFont(self.subtitle_label.font())
        subtitle_font.setPointSize(max(8, subtitle_font.pointSize() - 1))
        self.subtitle_label.setFont(subtitle_font)
        self.subtitle_label.setVisible(bool(subtitle))
        layout.addWidget(self.subtitle_label)


class SettingsGroup(QGroupBox):
    def __init__(self, title: str = "", parent=None):
        super().__init__(title, parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.form = QFormLayout(self)
        self.form.setContentsMargins(12, 12, 12, 12)
        self.form.setHorizontalSpacing(16)
        self.form.setVerticalSpacing(8)

    def add_row(self, label: str, widget: QWidget) -> None:
        self.form.addRow(label, widget)

    def add_full_row(self, widget: QWidget) -> None:
        self.form.addRow(widget)


class ActionBar(QWidget):
    preview_clicked = pyqtSignal()
    apply_clicked = pyqtSignal()
    clear_clicked = pyqtSignal()
    export_clicked = pyqtSignal()

    def __init__(
        self,
        preview_text: str = "Preview",
        apply_text: str = "Apply",
        clear_text: str = "Clear",
        export_text: str = "Export",
        parent=None,
    ):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.preview_btn = QPushButton(preview_text)
        self.preview_btn.setProperty("primary", True)
        self.preview_btn.setToolTip("Generate a preview so you can inspect the result before applying changes.")
        self.preview_btn.clicked.connect(self.preview_clicked.emit)
        layout.addWidget(self.preview_btn)

        self.apply_btn = QPushButton(apply_text)
        self.apply_btn.setProperty("accent", True)
        self.apply_btn.setToolTip("Run the main operation and write the current result to output.")
        self.apply_btn.clicked.connect(self.apply_clicked.emit)
        layout.addWidget(self.apply_btn)

        self.export_btn = QPushButton(export_text)
        self.export_btn.setToolTip("Export or refresh the current result without changing unrelated settings.")
        self.export_btn.clicked.connect(self.export_clicked.emit)
        layout.addWidget(self.export_btn)

        self.clear_btn = QPushButton(clear_text)
        self.clear_btn.setToolTip("Clear the current result or reset this part of the workflow.")
        self.clear_btn.clicked.connect(self.clear_clicked.emit)
        layout.addWidget(self.clear_btn)

        for button in (self.preview_btn, self.apply_btn, self.export_btn, self.clear_btn):
            button.setMinimumHeight(38)


class InfoPanel(QWidget):
    def __init__(self, title: str, sections: Optional[Iterable[Tuple[str, List[Tuple[str, QWidget]]]]] = None, parent=None):
        super().__init__(parent)
        self._groups = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_font = QFont(title_label.font())
        title_font.setPointSize(max(title_font.pointSize(), 11))
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        if sections:
            for section_title, rows in sections:
                group = self.add_section(section_title)
                for row_label, widget in rows:
                    group.add_row(row_label, widget)

        layout.addStretch()

    def add_section(self, title: str) -> SettingsGroup:
        group = SettingsGroup(title)
        self.layout().insertWidget(self.layout().count() - 1, group)
        self._groups[title] = group
        return group


class FormCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(14, 14, 14, 14)
        self.layout_.setSpacing(12)

    def add_widget(self, widget: QWidget) -> None:
        self.layout_.addWidget(widget)
