"""
Connection Indicator Widget
Visual indicator for CorelDRAW connection status.
"""

from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QBrush, QPen


class ConnectionIndicator(QWidget):
    """A visual indicator showing CorelDRAW connection status."""

    def __init__(self, parent=None):
        """Initialize the connection indicator."""
        super().__init__(parent)
        self._connected = False
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # LED indicator
        self.led = LEDWidget()
        layout.addWidget(self.led)

        # Status text
        self.status_label = QLabel("Disconnected")
        layout.addWidget(self.status_label)

        self.setFixedWidth(150)

    def set_connected(self, connected: bool):
        """Set the connection status."""
        self._connected = connected
        self.led.set_on(connected)
        self.status_label.setText("Connected" if connected else "Disconnected")

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected


class LEDWidget(QWidget):
    """A simple LED indicator widget."""

    def __init__(self, parent=None):
        """Initialize the LED widget."""
        super().__init__(parent)
        self._on = False
        self._on_color = QColor(0, 200, 0)  # Green
        self._off_color = QColor(150, 0, 0)  # Red
        self.setFixedSize(16, 16)

    def set_on(self, on: bool):
        """Set LED on/off state."""
        self._on = on
        self.update()

    def paintEvent(self, event):
        """Paint the LED."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw LED circle
        color = self._on_color if self._on else self._off_color
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(150), 1))
        painter.drawEllipse(2, 2, 12, 12)

        # Add highlight for 3D effect
        if self._on:
            highlight = QColor(255, 255, 255, 100)
            painter.setBrush(QBrush(highlight))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(4, 4, 6, 6)
