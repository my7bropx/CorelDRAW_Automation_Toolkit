import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw
from PyQt5.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

Color = Tuple[int, int, int]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreviewBatch:
    color: Color
    diameter_mm: float
    centers_mm: np.ndarray

    @property
    def count(self) -> int:
        return int(self.centers_mm.shape[0])


@dataclass
class PreviewScene:
    width_mm: float
    height_mm: float
    background_rgb: Color
    batches: List[PreviewBatch]
    stone_count: int
    render_profile: str
    cache_key: str = ""


@dataclass
class ImagePreview:
    image: Image.Image
    width_mm: float
    height_mm: float
    background_rgb: Color
    render_profile: str
    cache_key: str = ""


class PreviewRenderer:
    """Build preview scene data and bitmap exports without Corel writes."""

    def build_scene(
        self,
        stones: Sequence,
        width_mm: float,
        height_mm: float,
        background_rgb: Color = (78, 78, 78),
        render_profile: str = "settled",
        cache_key: str = "",
    ) -> PreviewScene:
        grouped: Dict[Tuple[Color, float], List[Tuple[float, float]]] = {}
        for stone in stones:
            key = (
                tuple(int(channel) for channel in stone.rgb),
                round(float(stone.diameter_mm), 4),
            )
            grouped.setdefault(key, []).append((float(stone.x_mm), float(stone.y_mm)))

        batches = [
            PreviewBatch(
                color=rgb,
                diameter_mm=diameter,
                centers_mm=np.asarray(points, dtype=np.float32),
            )
            for (rgb, diameter), points in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))
        ]
        return PreviewScene(
            width_mm=float(width_mm),
            height_mm=float(height_mm),
            background_rgb=background_rgb,
            batches=batches,
            stone_count=sum(batch.count for batch in batches),
            render_profile=render_profile,
            cache_key=cache_key,
        )

    def render_stones(
        self,
        stones: Sequence,
        width_mm: float,
        height_mm: float,
        ppm: int,
        background_rgb: Color = (78, 78, 78),
        render_profile: str = "settled",
        cache_key: str = "",
    ) -> Tuple[Image.Image, PreviewScene]:
        scene = self.build_scene(
            stones,
            width_mm,
            height_mm,
            background_rgb=background_rgb,
            render_profile=render_profile,
            cache_key=cache_key,
        )
        width_px = max(1, int(round(width_mm * ppm)))
        height_px = max(1, int(round(height_mm * ppm)))
        image = Image.new("RGB", (width_px, height_px), background_rgb)
        draw = ImageDraw.Draw(image)
        for batch in scene.batches:
            radius = max(1.0, float(batch.diameter_mm) * ppm / 2.0)
            fill = tuple(int(channel) for channel in batch.color)
            for center_x, center_y in batch.centers_mm:
                cx = float(center_x) * ppm
                cy = float(center_y) * ppm
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=fill)
        return image, scene


class PointillizerPreviewCanvas(QWidget):
    """Batched preview surface with cached raster layers and cheap redraw."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene: Optional[PreviewScene] = None
        self._image_preview: Optional[ImagePreview] = None
        self._status_text = "No preview generated"
        self._fit_size = QSize()
        self._layer_cache: Dict[Tuple[str, int, int, int], QPixmap] = {}
        self._image_cache: Dict[Tuple[str, int, int], QPixmap] = {}
        self._brush_cache: Dict[Color, QColor] = {}
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._dragging = False
        self._last_pos = QPoint()
        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.timeout.connect(self.update)
        self._last_update_request = 0.0
        self._latest_paint_ms = 0.0
        self._latest_layer_build_ms = 0.0
        self._slow_paint_count = 0
        self._slow_layer_count = 0
        self.setMinimumHeight(320)
        self.setMouseTracking(True)

    def _request_redraw(self, immediate: bool = False) -> None:
        now = time.perf_counter()
        if immediate or (now - self._last_update_request) >= (1.0 / 60.0):
            self._last_update_request = now
            self._redraw_timer.stop()
            self.update()
            return
        delay_ms = max(1, int(round(((1.0 / 60.0) - (now - self._last_update_request)) * 1000.0)))
        if not self._redraw_timer.isActive():
            self._redraw_timer.start(delay_ms)

    def clear_scene(self, message: str = "No preview generated") -> None:
        self._scene = None
        self._image_preview = None
        self._status_text = message
        self._layer_cache.clear()
        self._image_cache.clear()
        self._fit_size = QSize()
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._request_redraw(immediate=True)

    def set_scene(self, scene: PreviewScene, status_text: str = "") -> None:
        self._scene = scene
        self._image_preview = None
        self._status_text = status_text or f"{scene.render_profile.title()} preview"
        self._layer_cache.clear()
        self._image_cache.clear()
        self._fit_size = QSize()
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._request_redraw(immediate=True)

    def set_image_preview(
        self,
        image: Image.Image,
        width_mm: float,
        height_mm: float,
        *,
        background_rgb: Color = (26, 30, 36),
        render_profile: str = "structural",
        status_text: str = "",
        cache_key: str = "",
    ) -> None:
        self._scene = None
        self._image_preview = ImagePreview(
            image=image.copy(),
            width_mm=float(width_mm),
            height_mm=float(height_mm),
            background_rgb=background_rgb,
            render_profile=render_profile,
            cache_key=cache_key,
        )
        self._status_text = status_text or f"{render_profile.title()} preview"
        self._layer_cache.clear()
        self._image_cache.clear()
        self._fit_size = QSize()
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._request_redraw(immediate=True)

    def wheelEvent(self, event):  # noqa: N802
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else (1.0 / 1.1)
            self._zoom = max(0.2, min(8.0, self._zoom * factor))
            self._request_redraw()
            event.accept()
            return
        event.ignore()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self._scene is not None:
            self._dragging = True
            self._last_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._dragging:
            delta = event.pos() - self._last_pos
            self._last_pos = event.pos()
            self._pan += QPointF(float(delta.x()), float(delta.y()))
            self._request_redraw()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._request_redraw(immediate=True)
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):  # noqa: N802
        self._fit_size = QSize()
        self._layer_cache.clear()
        self._image_cache.clear()
        super().resizeEvent(event)

    def _fit_scene_size(self) -> QSize:
        preview_width = 0.0
        preview_height = 0.0
        if self._scene is not None:
            preview_width = self._scene.width_mm
            preview_height = self._scene.height_mm
        elif self._image_preview is not None:
            preview_width = self._image_preview.width_mm
            preview_height = self._image_preview.height_mm
        else:
            return QSize()
        if self._fit_size.isValid() and not self._fit_size.isEmpty():
            return self._fit_size
        content = self.rect().adjusted(12, 12, -12, -12)
        if content.width() <= 0 or content.height() <= 0:
            return QSize()
        scale = min(
            content.width() / max(1e-6, preview_width),
            content.height() / max(1e-6, preview_height),
        )
        self._fit_size = QSize(
            max(1, int(round(preview_width * scale))),
            max(1, int(round(preview_height * scale))),
        )
        return self._fit_size

    def _batch_brush(self, color: Color) -> QColor:
        brush = self._brush_cache.get(color)
        if brush is None:
            brush = QColor(*color)
            self._brush_cache[color] = brush
        return brush

    def _build_layer_pixmap(self, scene: PreviewScene, batch_index: int, fit_size: QSize) -> QPixmap:
        batch = scene.batches[batch_index]
        cache_id = scene.cache_key or f"{scene.render_profile}:{scene.stone_count}"
        layer_key = (cache_id, batch_index, fit_size.width(), fit_size.height())
        cached = self._layer_cache.get(layer_key)
        if cached is not None:
            return cached

        start = time.perf_counter()
        image = QImage(fit_size, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(Qt.NoPen))
        painter.setBrush(self._batch_brush(batch.color))

        scale_x = fit_size.width() / max(1e-6, scene.width_mm)
        scale_y = fit_size.height() / max(1e-6, scene.height_mm)
        radius = max(0.6, (batch.diameter_mm / 2.0) * min(scale_x, scale_y))
        path = QPainterPath()
        for center_x, center_y in batch.centers_mm:
            px = float(center_x) * scale_x
            py = float(center_y) * scale_y
            path.addEllipse(QRectF(px - radius, py - radius, radius * 2.0, radius * 2.0))
        painter.drawPath(path)
        painter.end()

        pixmap = QPixmap.fromImage(image)
        self._layer_cache[layer_key] = pixmap
        elapsed = (time.perf_counter() - start) * 1000.0
        self._latest_layer_build_ms = elapsed
        if elapsed > 12.0:
            self._slow_layer_count += 1
            logger.info(
                "preview layer rasterized slowly profile=%s batch=%s stones=%s size=%sx%s in %.2fms",
                scene.render_profile,
                batch_index,
                batch.count,
                fit_size.width(),
                fit_size.height(),
                elapsed,
            )
        return pixmap

    def _build_image_pixmap(self, preview: ImagePreview, fit_size: QSize) -> QPixmap:
        cache_id = preview.cache_key or f"{preview.render_profile}:{preview.image.size[0]}x{preview.image.size[1]}"
        cache_key = (cache_id, fit_size.width(), fit_size.height())
        cached = self._image_cache.get(cache_key)
        if cached is not None:
            return cached

        start = time.perf_counter()
        image = preview.image.convert("RGBA")
        image = image.resize((max(1, fit_size.width()), max(1, fit_size.height())), Image.Resampling.LANCZOS)
        qimage = QImage(image.tobytes("raw", "RGBA"), image.width, image.height, QImage.Format_RGBA8888).copy()
        pixmap = QPixmap.fromImage(qimage)
        self._image_cache[cache_key] = pixmap
        elapsed = (time.perf_counter() - start) * 1000.0
        self._latest_layer_build_ms = elapsed
        if elapsed > 12.0:
            self._slow_layer_count += 1
            logger.info(
                "preview image rasterized slowly profile=%s size=%sx%s in %.2fms",
                preview.render_profile,
                fit_size.width(),
                fit_size.height(),
                elapsed,
            )
        return pixmap

    def paintEvent(self, event):  # noqa: N802
        start = time.perf_counter()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor(15, 21, 29))

        if self._scene is None and self._image_preview is None:
            painter.setPen(QColor(160, 168, 180))
            painter.drawText(self.rect(), Qt.AlignCenter, self._status_text)
            painter.end()
            return

        fit_size = self._fit_scene_size()
        if fit_size.isEmpty():
            painter.end()
            return

        draw_width = fit_size.width() * self._zoom
        draw_height = fit_size.height() * self._zoom
        base_rect = QRectF(0.0, 0.0, draw_width, draw_height)
        base_rect.moveCenter(self.rect().center())
        base_rect.translate(self._pan)

        if self._scene is not None:
            scene = self._scene
            painter.fillRect(base_rect, QColor(*scene.background_rgb))
            for index in range(len(scene.batches)):
                layer = self._build_layer_pixmap(scene, index, fit_size)
                painter.drawPixmap(base_rect, layer, QRectF(0.0, 0.0, fit_size.width(), fit_size.height()))
            caption = f"{self._status_text} | stones: {scene.stone_count} | zoom: {self._zoom:.2f}x"
        else:
            preview = self._image_preview
            painter.fillRect(base_rect, QColor(*preview.background_rgb))
            layer = self._build_image_pixmap(preview, fit_size)
            painter.drawPixmap(base_rect, layer, QRectF(0.0, 0.0, fit_size.width(), fit_size.height()))
            caption = f"{self._status_text} | zoom: {self._zoom:.2f}x"

        painter.setPen(QColor(170, 180, 192))
        painter.drawText(
            self.rect().adjusted(10, 8, -10, -8),
            Qt.AlignTop | Qt.AlignLeft,
            caption,
        )
        painter.end()
        elapsed = (time.perf_counter() - start) * 1000.0
        self._latest_paint_ms = elapsed
        if elapsed > 16.0:
            self._slow_paint_count += 1
            profile = self._scene.render_profile if self._scene is not None else self._image_preview.render_profile
            stone_count = self._scene.stone_count if self._scene is not None else 0
            logger.info("preview paint slow profile=%s elapsed=%.2fms stones=%s", profile, elapsed, stone_count)

    def performance_snapshot(self) -> Dict[str, float]:
        return {
            "latest_paint_ms": float(self._latest_paint_ms),
            "latest_layer_build_ms": float(self._latest_layer_build_ms),
            "slow_paint_count": float(self._slow_paint_count),
            "slow_layer_count": float(self._slow_layer_count),
        }
