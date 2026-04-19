"""
Fast preview widget for large hexagon/rhinestone jobs.
"""

import math
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QBrush
from PyQt5.QtWidgets import QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from ...core.corel_interface import BoundingBox


class _PreviewCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._stones: List[Dict[str, float]] = []
        self._bounds: Optional[BoundingBox] = None
        self._container_contours: List[List[QPointF]] = []
        self.setMinimumHeight(280)
        self.setAutoFillBackground(True)

    def set_preview_data(
        self,
        stones: List[Dict[str, float]],
        bounds: Optional[BoundingBox],
        contours: Optional[List[List[Any]]] = None,
    ) -> None:
        self._stones = stones
        self._bounds = bounds
        self._container_contours = []
        for contour in contours or []:
            qt_contour: List[QPointF] = []
            for point in contour:
                if hasattr(point, "x") and hasattr(point, "y"):
                    qt_contour.append(QPointF(float(point.x), float(point.y)))
            if qt_contour:
                self._container_contours.append(qt_contour)
        self.update()

    def clear_preview(self) -> None:
        self._stones = []
        self._bounds = None
        self._container_contours = []
        self.update()

    def _fit_transform(self, rect: QRectF):
        canvas_rect = self.rect().adjusted(12, 12, -12, -12)
        if rect.width() <= 0 or rect.height() <= 0 or canvas_rect.width() <= 0 or canvas_rect.height() <= 0:
            return 1.0, 0.0, 0.0
        scale = min(canvas_rect.width() / rect.width(), canvas_rect.height() / rect.height())
        offset_x = canvas_rect.left() + ((canvas_rect.width() - (rect.width() * scale)) / 2.0)
        offset_y = canvas_rect.top() + ((canvas_rect.height() - (rect.height() * scale)) / 2.0)
        return scale, offset_x, offset_y

    def _map_point(self, x: float, y: float, rect: QRectF, scale: float, offset_x: float, offset_y: float) -> QPointF:
        px = offset_x + ((x - rect.left()) * scale)
        py = offset_y + ((rect.bottom() - y) * scale)
        return QPointF(px, py)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor("#f6f7f9"))

        if not self._bounds:
            painter.setPen(QPen(QColor("#6b7280")))
            painter.drawText(self.rect(), Qt.AlignCenter, "No preview data")
            return

        rect = QRectF(self._bounds.left, self._bounds.bottom, self._bounds.width, self._bounds.height)
        scale, offset_x, offset_y = self._fit_transform(rect)

        contour_pen = QPen(QColor("#1f2937"))
        contour_pen.setWidth(1)
        painter.setPen(contour_pen)
        painter.setBrush(Qt.NoBrush)
        for contour in self._container_contours:
            if len(contour) < 2:
                continue
            for index in range(len(contour)):
                current = contour[index]
                previous = contour[index - 1]
                p1 = self._map_point(previous.x(), previous.y(), rect, scale, offset_x, offset_y)
                p2 = self._map_point(current.x(), current.y(), rect, scale, offset_x, offset_y)
                painter.drawLine(p1, p2)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#0ea5e9")))
        for stone in self._stones:
            center = self._map_point(stone["x"], stone["y"], rect, scale, offset_x, offset_y)
            radius = max(1.0, stone["r"] * scale)
            painter.drawEllipse(center, radius, radius)


class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        stats_group = QGroupBox("Preview Summary")
        stats_form = QFormLayout(stats_group)
        self.lbl_count = QLabel("0")
        self.lbl_bounds = QLabel("-")
        self.lbl_density = QLabel("-")
        stats_form.addRow("Stone count:", self.lbl_count)
        stats_form.addRow("Bounds:", self.lbl_bounds)
        stats_form.addRow("Density:", self.lbl_density)
        layout.addWidget(stats_group)

        self.canvas = _PreviewCanvas()
        layout.addWidget(self.canvas, 1)

    def set_preview(self, stones, contours=None) -> None:
        serialized: List[Dict[str, float]] = []
        bounds = None
        if stones:
            serialized = [
                {"x": float(stone.x), "y": float(stone.y), "r": float(stone.template_r)}
                for stone in stones
            ]
            min_x = min(stone["x"] - stone["r"] for stone in serialized)
            min_y = min(stone["y"] - stone["r"] for stone in serialized)
            max_x = max(stone["x"] + stone["r"] for stone in serialized)
            max_y = max(stone["y"] + stone["r"] for stone in serialized)
            bounds = BoundingBox(left=min_x, bottom=min_y, right=max_x, top=max_y)

        if bounds:
            area = max(bounds.width * bounds.height, 0.0)
            density = len(serialized) / area if area > 0 else 0.0
            self.lbl_bounds.setText(f"{bounds.width:.2f} x {bounds.height:.2f} mm")
            self.lbl_density.setText(f"{density:.4f} stones/mm^2")
        else:
            self.lbl_bounds.setText("-")
            self.lbl_density.setText("-")

        self.lbl_count.setText(str(len(serialized)))
        self.canvas.set_preview_data(serialized, bounds, contours=contours)

    def clear_preview(self) -> None:
        self.lbl_count.setText("0")
        self.lbl_bounds.setText("-")
        self.lbl_density.setText("-")
        self.canvas.clear_preview()
