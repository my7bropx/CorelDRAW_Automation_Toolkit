from typing import List, Tuple

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget


class Sidebar(QWidget):
    tool_selected = pyqtSignal(str)

    def __init__(self, items: List[Tuple[str, str]], parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Tools")
        title_font = QFont(title.font())
        title_font.setPointSize(max(title_font.pointSize(), 11))
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.list_widget, 1)

        for key, label in items:
            item = QListWidgetItem(label)
            item.setData(256, key)
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _on_current_changed(self, current, previous):
        if current is None:
            return
        self.tool_selected.emit(current.data(256))
