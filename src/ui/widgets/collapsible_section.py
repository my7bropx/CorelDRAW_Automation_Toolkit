from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, title: str, content: QWidget = None, expanded: bool = True, parent=None):
        super().__init__(parent)
        self._expanded = expanded

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.toggle_button.clicked.connect(self._handle_toggle)
        button_font = QFont(self.toggle_button.font())
        button_font.setBold(True)
        self.toggle_button.setFont(button_font)
        self.toggle_button.setStyleSheet("""
            QToolButton {
                text-align: left;
                padding: 10px 12px;
                border: none;
            }
        """)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 10, 12, 12)
        self.content_layout.setSpacing(10)
        self.content_widget.setVisible(expanded)

        if content is not None:
            self.content_layout.addWidget(content)

        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_widget)


    def set_content(self, widget: QWidget) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            child = item.widget()
            if child:
                child.setParent(None)
        self.content_layout.addWidget(widget)

    def _handle_toggle(self, checked: bool) -> None:
        self._expanded = checked
        self.toggle_button.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        self.content_widget.setVisible(checked)
        self.toggled.emit(checked)
