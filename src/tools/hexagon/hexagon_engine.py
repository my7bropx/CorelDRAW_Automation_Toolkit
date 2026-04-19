"""
Hexagon design engine for rhinestone layout work.
"""

import json
import logging
import math
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ...core.corel_interface import BoundingBox, CurveSegment, Point, corel

logger = logging.getLogger(__name__)


STONE_SIZES: Dict[str, float] = {
    "SS2": 0.80,
    "SS3": 1.00,
    "SS4": 1.20,
    "SS5": 1.50,
    "SS6": 2.00,
    "SS8": 2.40,
    "SS10": 2.80,
    "SS12": 3.10,
    "SS14": 3.50,
    "SS16": 3.90,
    "SS18": 4.30,
    "SS20": 4.70,
    "SS30": 6.30,
    "SS34": 7.10,
    "SS40": 8.40,
    "SS48": 11.00,
}

DEFAULT_FIT_FACTOR = 0.93
FIT_FACTOR_MIN = 0.85
FIT_FACTOR_MAX = 0.99


class CollisionAction(Enum):
    REMOVE_SECOND = "remove_second"
    MERGE_MIDPOINT = "merge_midpoint"
    SHRINK_BOTH = "shrink_both"
    HIGHLIGHT = "highlight"


class PathDistribution(Enum):
    FIXED_PITCH = "fixed_pitch"
    DISTRIBUTE = "distribute"
    FIT_EXACT = "fit_exact"


class HoneycombOrigin(Enum):
    CENTER = "center"
    TOP_LEFT = "top_left"
    BOTTOM_LEFT = "bottom_left"


class OutputMode(Enum):
    PREVIEW_ONLY = "preview_only"
    EXPORT_ONLY = "export_only"
    COREL_RENDER = "corel_render"


@dataclass
class HexStone:
    x: float
    y: float
    template_r: float
    physical_r: float
    stone_size: str = "SS10"
    rotation: float = 0.0
    overlap_flag: bool = False

    @property
    def template_diameter(self) -> float:
        return self.template_r * 2.0

    @property
    def physical_diameter(self) -> float:
        return self.physical_r * 2.0

    def distance_to(self, other: "HexStone") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def overlaps(self, other: "HexStone", gap: float = 0.0) -> bool:
        return self.distance_to(other) < (self.physical_r + other.physical_r + gap)


@dataclass
class HexSettings:
    stone_size: str = "SS10"
    custom_diameter: float = 2.80
    fit_factor: float = DEFAULT_FIT_FACTOR
    min_gap: float = 0.20
    path_distribution: PathDistribution = PathDistribution.DISTRIBUTE
    path_start_padding: float = 0.0
    path_end_padding: float = 0.0
    path_rotate_to_tangent: bool = True
    path_extra_gap: float = 0.0
    hatch_origin: HoneycombOrigin = HoneycombOrigin.CENTER
    hatch_row_angle: float = 0.0
    hatch_edge_margin: float = 0.0
    hatch_stagger_pct: float = 50.0
    hatch_clip_to_shape: bool = True
    collision_action: CollisionAction = CollisionAction.REMOVE_SECOND
    collision_gap: float = 0.0
    shrink_min_factor: float = 0.60
    group_output: bool = True
    layer_name: str = "Rhinestones"
    output_mode: OutputMode = OutputMode.COREL_RENDER
    fast_output_threshold: int = 5000
    progress_updates: int = 200

    def physical_diameter(self) -> float:
        if self.stone_size == "custom":
            return max(0.1, float(self.custom_diameter))
        return float(STONE_SIZES.get(self.stone_size, STONE_SIZES["SS10"]))

    def physical_radius(self) -> float:
        return self.physical_diameter() / 2.0

    def normalized_fit_factor(self) -> float:
        return min(max(float(self.fit_factor), FIT_FACTOR_MIN), FIT_FACTOR_MAX)

    def template_diameter(self) -> float:
        return self.physical_diameter() * self.normalized_fit_factor()

    def template_radius(self) -> float:
        return self.template_diameter() / 2.0

    def pitch(self) -> float:
        return self.physical_diameter() + max(0.0, float(self.min_gap))

    def path_pitch(self) -> float:
        return self.physical_diameter() + max(0.0, float(self.min_gap)) + max(0.0, float(self.path_extra_gap))


class HexagonEngine:
    def __init__(self) -> None:
        self._last_stones: List[HexStone] = []
        self._placed_shapes: List[Any] = []

    def clear(self) -> None:
        self._last_stones.clear()
        self._placed_shapes.clear()

    def make_stone(self, x: float, y: float, settings: HexSettings, rotation: float = 0.0) -> HexStone:
        return HexStone(
            x=x,
            y=y,
            template_r=settings.template_radius(),
            physical_r=settings.physical_radius(),
            stone_size=settings.stone_size,
            rotation=rotation,
        )

    def get_template_diameter_for_size(self, stone_size: str, fit_factor: float = DEFAULT_FIT_FACTOR) -> float:
        physical = STONE_SIZES.get(stone_size, STONE_SIZES["SS10"])
        fit = min(max(float(fit_factor), FIT_FACTOR_MIN), FIT_FACTOR_MAX)
        return physical * fit

    def size_table(self, fit_factor: float = DEFAULT_FIT_FACTOR) -> Dict[str, Dict[str, float]]:
        fit = min(max(float(fit_factor), FIT_FACTOR_MIN), FIT_FACTOR_MAX)
        result: Dict[str, Dict[str, float]] = {}
        for code, physical in STONE_SIZES.items():
            template = physical * fit
            result[code] = {
                "physical_mm": round(physical, 4),
                "template_mm": round(template, 4),
                "reduction_mm": round(physical - template, 4),
            }
        return result

    def _progress(self, callback, current: int, total: int) -> None:
        if callback:
            callback(current, total)

    def _progress_stride(self, total: int, updates: int = 200) -> int:
        """Throttle progress callbacks to avoid UI/COM overhead on large jobs."""
        return max(1, total // max(1, updates))

    def _resolve_output_mode(self, settings: HexSettings, total: int, element_shape: Any = None) -> OutputMode:
        """Return the configured planner/render mode."""
        return settings.output_mode

    def _make_template_key(self, value: float) -> float:
        """Round template cache keys to avoid floating-point noise."""
        return round(float(value), 4)

    def _build_circle_templates(self, layer, stones: List[HexStone]) -> Dict[Tuple[bool, float], Any]:
        """Create reusable centered circle templates keyed by highlight flag and diameter."""
        templates: Dict[Tuple[bool, float], Any] = {}
        for stone in stones:
            key = (bool(stone.overlap_flag), self._make_template_key(stone.template_diameter))
            if key in templates:
                continue
            templates[key] = corel.create_circle_template(
                layer,
                diameter_mm=stone.template_diameter,
                outline_width_mm=0.10,
                outline_rgb=(255, 0, 0) if stone.overlap_flag else (0, 0, 0),
                no_fill=True,
            )
        return templates

    def _build_element_templates(self, layer, stones: List[HexStone], element_shape: Any) -> Dict[float, Any]:
        """Create centered, resized element templates keyed by diameter."""
        templates: Dict[float, Any] = {}
        for stone in stones:
            key = self._make_template_key(stone.template_diameter)
            if key in templates:
                continue
            template = corel.duplicate_shape(element_shape)
            try:
                template.MoveToLayer(layer)
            except Exception:
                pass
            corel.resize_shape(template, stone.template_diameter, stone.template_diameter, keep_center=True)
            corel.center_shape_at_origin(template)
            templates[key] = template
        return templates

    def _cleanup_templates(self, templates: Dict[Any, Any]) -> None:
        """Delete temporary template shapes used only for fast duplication."""
        for template in templates.values():
            try:
                template.Delete()
            except Exception:
                pass

    def _place_fast_circles(
        self,
        layer,
        stones: List[HexStone],
        settings: HexSettings,
        progress_callback=None,
        cancel_callback=None,
    ) -> List[Any]:
        """Fast circle output path for large jobs with reduced COM chatter."""
        created: List[Any] = []
        total = len(stones)
        stride = self._progress_stride(total, settings.progress_updates)
        outline_width = 0.10

        logger.info("Hexagon fast circle placement start: stones=%s stride=%s", total, stride)

        for index, stone in enumerate(stones, start=1):
            if cancel_callback and cancel_callback():
                logger.info("Hexagon fast circle placement cancelled after %s shape(s).", index - 1)
                break

            shape = corel.create_ellipse(layer, stone.x, stone.y, stone.template_r, stone.template_r)
            try:
                corel.set_shape_no_fill(shape)
                corel.set_shape_outline(
                    shape,
                    width_mm=outline_width,
                    color_rgb=(255, 0, 0) if stone.overlap_flag else (0, 0, 0),
                )
            except Exception as exc:
                logger.debug("Hexagon fast circle style skipped for stone %s: %s", index, exc)

            created.append(shape)

            if index % stride == 0 or index == total:
                self._progress(progress_callback, index, total)

        return created

    def _place_fast_elements(
        self,
        layer,
        stones: List[HexStone],
        settings: HexSettings,
        element_shape: Any,
        progress_callback=None,
        cancel_callback=None,
    ) -> List[Any]:
        """Fast path for custom element shapes using cached normalized templates."""
        created: List[Any] = []
        templates = self._build_element_templates(layer, stones, element_shape)
        total = len(stones)
        stride = self._progress_stride(total, settings.progress_updates)

        try:
            for index, stone in enumerate(stones, start=1):
                if cancel_callback and cancel_callback():
                    break
                key = self._make_template_key(stone.template_diameter)
                shape = corel.duplicate_centered_template(templates[key], stone.x, stone.y, rotation=stone.rotation)
                created.append(shape)
                if index % stride == 0 or index == total:
                    self._progress(progress_callback, index, total)
        finally:
            self._cleanup_templates(templates)

        return created

    def _place_legacy(
        self,
        layer,
        stones: List[HexStone],
        settings: HexSettings,
        progress_callback=None,
        cancel_callback=None,
        element_shape: Any = None,
    ) -> List[Any]:
        """Original per-stone placement path kept for backward compatibility."""
        created: List[Any] = []
        total = len(stones)
        stride = self._progress_stride(total, settings.progress_updates)

        for index, stone in enumerate(stones, start=1):
            if cancel_callback and cancel_callback():
                break
            radius = stone.template_r
            if element_shape is not None:
                shape = corel.duplicate_shape(element_shape)
                diameter = radius * 2.0
                corel.resize_shape(shape, diameter, diameter, keep_center=True)
                center = corel.get_shape_center(shape)
                corel.move_shape_by(shape, stone.x - center.x, stone.y - center.y)
                if stone.rotation:
                    corel.rotate_shape(shape, stone.rotation, stone.x, stone.y)
                try:
                    shape.MoveToLayer(layer)
                except Exception:
                    pass
            else:
                shape = corel.create_ellipse(layer, stone.x, stone.y, radius, radius)
                corel.set_shape_no_fill(shape)
                corel.set_shape_outline(
                    shape,
                    width_mm=0.10,
                    color_rgb=(255, 0, 0) if stone.overlap_flag else (0, 0, 0),
                )
            created.append(shape)
            if index % stride == 0 or index == total:
                self._progress(progress_callback, index, total)

        return created

    def _curve_samples(self, usable_length: float, settings: HexSettings) -> List[float]:
        if usable_length <= 0.0001:
            return [0.0] if usable_length >= 0 else []

        pitch = max(0.001, settings.path_pitch())
        if settings.path_distribution == PathDistribution.FIXED_PITCH:
            values: List[float] = []
            current = 0.0
            while current <= usable_length + 1e-9:
                values.append(current)
                current += pitch
            return values or [0.0]

        if settings.path_distribution == PathDistribution.FIT_EXACT:
            count = max(2, int(round(usable_length / pitch)) + 1)
        else:
            count = max(2, int(math.floor(usable_length / pitch)) + 1)

        step = usable_length / (count - 1)
        return [index * step for index in range(count)]

    def path_blend(self, curve_segments: List[CurveSegment], settings: HexSettings, progress_callback=None, cancel_callback=None) -> List[HexStone]:
        if not curve_segments:
            return []

        total_length = corel.get_curve_total_length(curve_segments)
        start_padding = max(0.0, settings.path_start_padding)
        end_padding = max(0.0, settings.path_end_padding)
        usable_length = max(0.0, total_length - start_padding - end_padding)
        distances = self._curve_samples(usable_length, settings)

        stones: List[HexStone] = []
        for index, offset in enumerate(distances, start=1):
            if cancel_callback and cancel_callback():
                break
            point, tangent = corel.get_point_on_curve(curve_segments, start_padding + offset)
            rotation = tangent if settings.path_rotate_to_tangent else 0.0
            stones.append(self.make_stone(point.x, point.y, settings, rotation))
            self._progress(progress_callback, index, len(distances))

        stones = self.resolve_collisions(stones, settings)
        self._last_stones = stones
        return stones

    def _fill_bounds(self, bounds: BoundingBox, settings: HexSettings) -> Optional[BoundingBox]:
        inset = max(0.0, settings.hatch_edge_margin)
        left = bounds.left + inset
        bottom = bounds.bottom + inset
        right = bounds.right - inset
        top = bounds.top - inset
        if right <= left or top <= bottom:
            return None
        return BoundingBox(left=left, bottom=bottom, right=right, top=top)

    def _grid_origin(self, bounds: BoundingBox, settings: HexSettings) -> Tuple[float, float]:
        if settings.hatch_origin == HoneycombOrigin.TOP_LEFT:
            return bounds.left, bounds.top
        if settings.hatch_origin == HoneycombOrigin.BOTTOM_LEFT:
            return bounds.left, bounds.bottom
        center = bounds.center
        return center.x, center.y

    def _point_line_distance(self, point: Point, start: Point, end: Point) -> float:
        """Return the perpendicular distance from a point to the infinite line through a segment."""
        dx = end.x - start.x
        dy = end.y - start.y
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            return point.distance_to(start)
        return abs((dy * point.x) - (dx * point.y) + (end.x * start.y) - (end.y * start.x)) / length

    def _flatten_bezier_segment(
        self,
        start: Point,
        control1: Point,
        control2: Point,
        end: Point,
        tolerance: float,
        depth: int = 0,
        max_depth: int = 12,
    ) -> List[Point]:
        """Adaptively flatten a cubic Bezier into line segments."""
        if depth >= max_depth:
            return [start, end]

        flatness = max(
            self._point_line_distance(control1, start, end),
            self._point_line_distance(control2, start, end),
        )
        if flatness <= tolerance:
            return [start, end]

        p01 = Point((start.x + control1.x) / 2.0, (start.y + control1.y) / 2.0)
        p12 = Point((control1.x + control2.x) / 2.0, (control1.y + control2.y) / 2.0)
        p23 = Point((control2.x + end.x) / 2.0, (control2.y + end.y) / 2.0)
        p012 = Point((p01.x + p12.x) / 2.0, (p01.y + p12.y) / 2.0)
        p123 = Point((p12.x + p23.x) / 2.0, (p12.y + p23.y) / 2.0)
        midpoint = Point((p012.x + p123.x) / 2.0, (p012.y + p123.y) / 2.0)

        left = self._flatten_bezier_segment(start, p01, p012, midpoint, tolerance, depth + 1, max_depth)
        right = self._flatten_bezier_segment(midpoint, p123, p23, end, tolerance, depth + 1, max_depth)
        return left[:-1] + right

    def _segment_polyline(self, segment: CurveSegment, tolerance: float = 0.15) -> List[Point]:
        """Approximate a curve segment as a polyline using adaptive flattening."""
        if not segment.is_bezier or not segment.control1 or not segment.control2:
            return [segment.start, segment.end]

        return self._flatten_bezier_segment(
            segment.start,
            segment.control1,
            segment.control2,
            segment.end,
            max(0.01, tolerance),
        )

    def _flatten_contour(self, contour: List[CurveSegment], tolerance: float = 0.15) -> List[Point]:
        """Flatten one closed contour into a cleaned point loop."""
        points: List[Point] = []
        for segment in contour or []:
            polyline = self._segment_polyline(segment, tolerance=tolerance)
            if points and polyline:
                polyline = polyline[1:]
            points.extend(polyline)
        return self._normalize_contour(points)

    def _normalize_contour(self, contour: List[Point]) -> List[Point]:
        """Clean a contour and ensure it is explicitly closed."""
        cleaned: List[Point] = []
        for point in contour:
            if not cleaned or abs(cleaned[-1].x - point.x) > 1e-9 or abs(cleaned[-1].y - point.y) > 1e-9:
                cleaned.append(point)

        if len(cleaned) < 3:
            return []

        first = cleaned[0]
        last = cleaned[-1]
        if abs(first.x - last.x) > 1e-9 or abs(first.y - last.y) > 1e-9:
            cleaned.append(Point(first.x, first.y))

        return cleaned

    def _world_to_local(self, x: float, y: float, origin_x: float, origin_y: float, angle_rad: float) -> Point:
        """Transform a world-space point into row-aligned local space."""
        dx = x - origin_x
        dy = y - origin_y
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return Point(
            x=(dx * cos_a) + (dy * sin_a),
            y=(-dx * sin_a) + (dy * cos_a),
        )

    def _local_to_world(self, x: float, y: float, origin_x: float, origin_y: float, angle_rad: float) -> Point:
        """Transform a local row-aligned point back into world space."""
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        return Point(
            x=origin_x + (x * cos_a) - (y * sin_a),
            y=origin_y + (x * sin_a) + (y * cos_a),
        )

    def _contours_bounds(self, contours: List[List[Point]]) -> BoundingBox:
        """Return the bounding box of all contour points."""
        xs = [point.x for contour in contours for point in contour]
        ys = [point.y for contour in contours for point in contour]
        return BoundingBox(left=min(xs), bottom=min(ys), right=max(xs), top=max(ys))

    def _contour_row_intersections(self, y: float, contours: List[List[Point]]) -> List[float]:
        """Collect x intersections for a horizontal scanline across all contours."""
        intersections: List[float] = []
        for contour in contours:
            if len(contour) < 4:
                continue
            previous = contour[-1]
            for current in contour:
                if (current.y > y) != (previous.y > y):
                    denominator = previous.y - current.y
                    if abs(denominator) >= 1e-9:
                        x = current.x + ((y - current.y) * (previous.x - current.x) / denominator)
                        intersections.append(x)
                previous = current
        intersections.sort()
        return intersections

    def _row_spans_from_contours(self, y: float, contours: List[List[Point]]) -> List[Tuple[float, float]]:
        """Build even-odd interior spans from all contour intersections for one row."""
        intersections = self._contour_row_intersections(y, contours)
        spans: List[Tuple[float, float]] = []
        for index in range(0, len(intersections) - 1, 2):
            left = intersections[index]
            right = intersections[index + 1]
            if right - left > 1e-9:
                spans.append((left, right))
        return spans

    def _point_in_contours(self, x: float, y: float, contours: List[List[Point]]) -> bool:
        """Even-odd point-in-contours check supporting holes and multiple subpaths."""
        intersections = self._contour_row_intersections(y, contours)
        crossings = sum(1 for boundary_x in intersections if x < boundary_x)
        return (crossings % 2) == 1

    def _distance_point_to_segment(self, px: float, py: float, start: Point, end: Point) -> float:
        """Return the shortest distance from a point to a line segment."""
        dx = end.x - start.x
        dy = end.y - start.y
        length_sq = (dx * dx) + (dy * dy)
        if length_sq <= 1e-12:
            return math.hypot(px - start.x, py - start.y)

        t = ((px - start.x) * dx + (py - start.y) * dy) / length_sq
        t = max(0.0, min(1.0, t))
        closest_x = start.x + (t * dx)
        closest_y = start.y + (t * dy)
        return math.hypot(px - closest_x, py - closest_y)

    def _distance_to_contours(self, x: float, y: float, contours: List[List[Point]]) -> float:
        """Return the minimum distance from a point to any contour edge."""
        if not contours:
            return 0.0

        min_distance = float("inf")
        for contour in contours:
            if len(contour) < 2:
                continue
            previous = contour[-1]
            for current in contour:
                min_distance = min(min_distance, self._distance_point_to_segment(x, y, previous, current))
                previous = current
        return min_distance if min_distance != float("inf") else 0.0

    def _stone_fully_inside_contours(self, x: float, y: float, inset: float, contours: List[List[Point]]) -> bool:
        """Check whether a stone remains inside the contour network with the required inset."""
        if not self._point_in_contours(x, y, contours):
            return False
        return self._distance_to_contours(x, y, contours) + 1e-6 >= inset

    def _span_grid_points(
        self,
        left: float,
        right: float,
        pitch: float,
        row_anchor: float,
        inset: float,
        radius: float,
    ) -> List[float]:
        """Return deterministic row positions that stay inside one interior span."""
        usable_left = left + inset
        usable_right = right - inset
        usable_width = usable_right - usable_left
        if usable_width < -1e-9:
            return []

        if usable_width + 1e-9 < (radius * 2.0):
            return []

        first_index = int(math.ceil((usable_left - row_anchor) / pitch))
        last_index = int(math.floor((usable_right - row_anchor) / pitch))

        if first_index > last_index:
            center = (usable_left + usable_right) / 2.0
            return [center] if usable_left <= center <= usable_right else []

        positions = [row_anchor + (index * pitch) for index in range(first_index, last_index + 1)]
        if not positions:
            return []

        desired_center = (usable_left + usable_right) / 2.0
        current_center = (positions[0] + positions[-1]) / 2.0
        shift = desired_center - current_center
        shift = max(-(pitch / 2.0), min(pitch / 2.0, shift))
        shifted = [position + shift for position in positions]

        if shifted[0] < usable_left:
            shifted = [position + (usable_left - shifted[0]) for position in shifted]
        if shifted[-1] > usable_right:
            shifted = [position - (shifted[-1] - usable_right) for position in shifted]

        return [position for position in shifted if usable_left <= position <= usable_right]

    def _prepare_flattened_contours(
        self,
        clip_contours: Optional[List[List[CurveSegment]]] = None,
        clip_segments: Optional[List[CurveSegment]] = None,
        tolerance: float = 0.15,
    ) -> List[List[Point]]:
        """Convert arbitrary closed contour input into flattened closed point loops."""
        source_contours = clip_contours or ([clip_segments] if clip_segments else [])
        contours: List[List[Point]] = []

        for index, contour_segments in enumerate(source_contours, start=1):
            contour = self._flatten_contour(contour_segments or [], tolerance=tolerance)
            if not contour:
                logger.warning("Hexagon contour %s flattened to no usable points.", index)
                continue
            if len(contour) < 4:
                raise ValueError(f"Contour {index} is too small for fill processing.")
            contours.append(contour)

        if not contours:
            raise ValueError("No valid closed contours were supplied for hatch fill.")

        return contours

    def _row_anchor_for_origin(self, local_bounds: BoundingBox, settings: HexSettings, pitch: float) -> float:
        """Return a deterministic lattice anchor for row placement."""
        if settings.hatch_origin == HoneycombOrigin.TOP_LEFT:
            return local_bounds.left
        if settings.hatch_origin == HoneycombOrigin.BOTTOM_LEFT:
            return local_bounds.left
        return (local_bounds.left + local_bounds.right) / 2.0

    def honeycomb_fill(
        self,
        container_bounds: BoundingBox,
        settings: HexSettings,
        clip_segments: Optional[List[CurveSegment]] = None,
        clip_contours: Optional[List[List[CurveSegment]]] = None,
        container_shape: Any = None,
        progress_callback=None,
        cancel_callback=None,
    ) -> List[HexStone]:
        pitch = settings.pitch()
        row_height = pitch * math.sqrt(3.0) / 2.0
        if pitch <= 0.0 or row_height <= 0.0:
            raise ValueError("Hexagon hatch fill requires a positive pitch and row height.")

        has_contours = bool(clip_contours) or bool(clip_segments)
        has_shape_fallback = container_shape is not None and corel.is_connected

        if not has_contours and not has_shape_fallback:
            raise ValueError(
                "Hexagon hatch fill requires either closed container contours "
                "(clip_contours / clip_segments) or a container_shape for per-stone clipping."
            )

        if not has_contours:
            # No curve geometry available — fall back to bounding-box grid with
            # corel.is_point_in_shape per stone. Slower but always correct.
            logger.warning(
                "honeycomb_fill: no contours available — using corel.is_point_in_shape "
                "fallback (this is slower; fix get_curve_subpaths to restore fast path)."
            )
            return self._honeycomb_fill_bbox_clip(
                container_bounds, settings, container_shape, progress_callback, cancel_callback
            )


        tolerance = max(0.02, settings.physical_radius() / 8.0)
        contours = self._prepare_flattened_contours(
            clip_contours=clip_contours,
            clip_segments=clip_segments,
            tolerance=tolerance,
        )
        if not contours:
            raise ValueError("No valid closed contours were available for hatch fill.")

        contour_bounds = self._contours_bounds(contours)
        origin_x, origin_y = self._grid_origin(contour_bounds, settings)
        angle_rad = math.radians(settings.hatch_row_angle)
        stagger = pitch * (settings.hatch_stagger_pct / 100.0)
        boundary_inset = settings.physical_radius() + max(0.0, settings.hatch_edge_margin)

        local_contours = [
            [self._world_to_local(point.x, point.y, origin_x, origin_y, angle_rad) for point in contour]
            for contour in contours
        ]
        local_bounds = self._contours_bounds(local_contours)
        lattice_anchor = self._row_anchor_for_origin(local_bounds, settings, pitch)

        min_row = int(math.floor((local_bounds.bottom - boundary_inset) / row_height)) - 1
        max_row = int(math.ceil((local_bounds.top + boundary_inset) / row_height)) + 1
        total_rows = max(0, max_row - min_row + 1)

        candidate_count = 0
        kept_count = 0
        rejected_by_boundary = 0
        total_spans = 0
        stones: List[HexStone] = []

        logger.info(
            "Hexagon interior hatch start: contours=%s contour_points=%s tolerance=%.4f bounds=(%.3f, %.3f, %.3f, %.3f) pitch=%.3f row_height=%.3f angle=%.3f inset=%.3f rows=%s",
            len(contours),
            sum(len(contour) for contour in contours),
            tolerance,
            contour_bounds.left,
            contour_bounds.bottom,
            contour_bounds.right,
            contour_bounds.top,
            pitch,
            row_height,
            settings.hatch_row_angle,
            boundary_inset,
            total_rows,
        )

        for row_progress, row_number in enumerate(range(min_row, max_row + 1), start=1):
            if cancel_callback and cancel_callback():
                logger.info("Hexagon hatch fill cancelled after %s row(s).", row_progress - 1)
                break

            local_y = row_number * row_height
            spans = self._row_spans_from_contours(local_y, local_contours)
            span_count = len(spans)
            total_spans += span_count
            row_anchor = lattice_anchor + (stagger if row_number % 2 else 0.0)

            logger.debug(
                "Hexagon hatch row=%s local_y=%.3f spans=%s row_anchor=%.3f",
                row_number,
                local_y,
                span_count,
                row_anchor,
            )

            if span_count == 0:
                self._progress(progress_callback, row_progress, total_rows)
                continue

            for left, right in spans:
                local_x_values = self._span_grid_points(
                    left,
                    right,
                    pitch,
                    row_anchor,
                    boundary_inset,
                    settings.physical_radius(),
                )
                for local_x in local_x_values:
                    candidate_count += 1
                    if not self._stone_fully_inside_contours(local_x, local_y, boundary_inset, local_contours):
                        rejected_by_boundary += 1
                        continue

                    world_point = self._local_to_world(local_x, local_y, origin_x, origin_y, angle_rad)
                    stones.append(self.make_stone(world_point.x, world_point.y, settings))
                    kept_count += 1

            self._progress(progress_callback, row_progress, total_rows)

        logger.info(
            "Hexagon interior hatch result: rows=%s spans=%s candidates=%s kept=%s rejected_by_boundary=%s",
            total_rows,
            total_spans,
            candidate_count,
            kept_count,
            rejected_by_boundary,
        )

        stones = self.resolve_collisions(stones, settings)
        self._last_stones = stones
        return stones


    def _honeycomb_fill_bbox_clip(
        self,
        container_bounds: BoundingBox,
        settings: HexSettings,
        container_shape: Any,
        progress_callback=None,
        cancel_callback=None,
    ) -> List[HexStone]:
        """
        Fallback hatch fill: bounding-box candidate grid clipped via corel.is_point_in_shape.

        Used automatically when no curve contours are available (e.g. when
        corel.get_curve_subpaths is not implemented or returns nothing).
        Slower than the span-based contour path but always produces correct results
        because CorelDRAW itself evaluates containment.
        """
        fill_bounds = self._fill_bounds(container_bounds, settings)
        if fill_bounds is None:
            return []

        pitch = settings.pitch()
        row_height = pitch * math.sqrt(3.0) / 2.0
        stagger = pitch * (settings.hatch_stagger_pct / 100.0)
        angle_rad = math.radians(settings.hatch_row_angle)
        origin_x, origin_y = self._grid_origin(fill_bounds, settings)

        diagonal = math.hypot(fill_bounds.width, fill_bounds.height)
        extra_cols = int(math.ceil(diagonal / pitch)) + 2
        extra_rows = int(math.ceil(diagonal / row_height)) + 2

        candidates: List[Tuple[float, float]] = []
        for row in range(-extra_rows, extra_rows + 1):
            row_offset = stagger if row % 2 else 0.0
            for col in range(-extra_cols, extra_cols + 1):
                local_x = col * pitch + row_offset
                local_y = row * row_height
                if angle_rad:
                    rx = local_x * math.cos(angle_rad) - local_y * math.sin(angle_rad)
                    ry = local_x * math.sin(angle_rad) + local_y * math.cos(angle_rad)
                else:
                    rx, ry = local_x, local_y
                world_x = origin_x + rx
                world_y = origin_y + ry
                if (fill_bounds.left <= world_x <= fill_bounds.right
                        and fill_bounds.bottom <= world_y <= fill_bounds.top):
                    candidates.append((world_x, world_y))

        stones: List[HexStone] = []
        total = len(candidates)
        stride = self._progress_stride(total, settings.progress_updates)

        logger.info(
            "Hexagon bbox-clip fallback start: candidates=%s container_shape=%s",
            total,
            getattr(container_shape, "Name", repr(container_shape)),
        )

        for index, (x, y) in enumerate(candidates, start=1):
            if cancel_callback and cancel_callback():
                logger.info("Hexagon bbox-clip fallback cancelled after %s stone(s).", index - 1)
                break
            try:
                inside = corel.is_point_in_shape(x, y, container_shape)
            except Exception as exc:
                logger.debug("is_point_in_shape failed at (%.3f, %.3f): %s — including stone.", x, y, exc)
                inside = True  # include on API failure; better too many than too few
            if inside:
                stones.append(self.make_stone(x, y, settings))
            if index % stride == 0 or index == total:
                self._progress(progress_callback, index, total)

        logger.info("Hexagon bbox-clip fallback result: placed=%s / candidates=%s", len(stones), total)

        stones = self.resolve_collisions(stones, settings)
        self._last_stones = stones
        return stones

    def find_overlaps(self, stones: List[HexStone], settings: HexSettings) -> List[Tuple[int, int]]:
        if not stones:
            return []

        cell = max(stone.physical_diameter for stone in stones) + max(0.0, settings.collision_gap) + 0.001
        grid: Dict[Tuple[int, int], List[int]] = {}

        def key(x: float, y: float) -> Tuple[int, int]:
            return (int(math.floor(x / cell)), int(math.floor(y / cell)))

        for index, stone in enumerate(stones):
            grid.setdefault(key(stone.x, stone.y), []).append(index)

        overlaps: List[Tuple[int, int]] = []
        for index, stone in enumerate(stones):
            gx, gy = key(stone.x, stone.y)
            for nx in range(gx - 1, gx + 2):
                for ny in range(gy - 1, gy + 2):
                    for other in grid.get((nx, ny), []):
                        if other <= index:
                            continue
                        if stone.overlaps(stones[other], settings.collision_gap):
                            overlaps.append((index, other))
        return overlaps

    def resolve_collisions(self, stones: List[HexStone], settings: HexSettings) -> List[HexStone]:
        if not stones:
            return stones

        pairs = self.find_overlaps(stones, settings)
        if not pairs:
            return stones

        action = settings.collision_action
        if action == CollisionAction.HIGHLIGHT:
            flagged = {index for pair in pairs for index in pair}
            for index in flagged:
                stones[index].overlap_flag = True
            return stones

        if action == CollisionAction.REMOVE_SECOND:
            removed = set()
            for first, second in pairs:
                if first not in removed:
                    removed.add(second)
            return [stone for index, stone in enumerate(stones) if index not in removed]

        if action == CollisionAction.MERGE_MIDPOINT:
            parent = list(range(len(stones)))

            def find(index: int) -> int:
                while parent[index] != index:
                    parent[index] = parent[parent[index]]
                    index = parent[index]
                return index

            def union(left: int, right: int) -> None:
                root_left = find(left)
                root_right = find(right)
                if root_left != root_right:
                    parent[root_right] = root_left

            for first, second in pairs:
                union(first, second)

            groups: Dict[int, List[int]] = {}
            for index in range(len(stones)):
                groups.setdefault(find(index), []).append(index)

            merged: List[HexStone] = []
            for members in groups.values():
                if len(members) == 1:
                    merged.append(stones[members[0]])
                    continue
                avg_x = sum(stones[index].x for index in members) / len(members)
                avg_y = sum(stones[index].y for index in members) / len(members)
                template_r = max(stones[index].template_r for index in members)
                physical_r = max(stones[index].physical_r for index in members)
                rotation = sum(stones[index].rotation for index in members) / len(members)
                merged.append(
                    HexStone(
                        x=avg_x,
                        y=avg_y,
                        template_r=template_r,
                        physical_r=physical_r,
                        stone_size=stones[members[0]].stone_size,
                        rotation=rotation,
                    )
                )
            return merged

        if action == CollisionAction.SHRINK_BOTH:
            updated = [
                HexStone(
                    x=stone.x,
                    y=stone.y,
                    template_r=stone.template_r,
                    physical_r=stone.physical_r,
                    stone_size=stone.stone_size,
                    rotation=stone.rotation,
                    overlap_flag=stone.overlap_flag,
                )
                for stone in stones
            ]
            for first, second in pairs:
                left = updated[first]
                right = updated[second]
                distance = left.distance_to(right)
                target = left.physical_r + right.physical_r + settings.collision_gap
                overlap = target - distance
                if overlap <= 0:
                    continue
                reduction = overlap / 2.0
                min_left = stones[first].template_r * settings.shrink_min_factor
                min_right = stones[second].template_r * settings.shrink_min_factor
                left.template_r = max(min_left, left.template_r - reduction)
                right.template_r = max(min_right, right.template_r - reduction)
            return updated

        return stones

    def _serialize_style(self, settings: HexSettings) -> Dict[str, Any]:
        """Build the render style contract shared with the Corel macro."""
        return {
            "fill_color": [255, 0, 0],
            "outline": False,
            "outline_color": [0, 0, 0],
            "outline_width_mm": 0.10,
            "group_output": bool(settings.group_output),
            "layer_name": settings.layer_name or "Rhinestones",
        }

    def build_render_payload(self, stones: List[HexStone], settings: HexSettings, mode: str = "circle") -> Dict[str, Any]:
        """Build the planner -> renderer payload without touching CorelDRAW."""
        bounds = None
        if stones:
            min_x = min(stone.x - stone.template_r for stone in stones)
            min_y = min(stone.y - stone.template_r for stone in stones)
            max_x = max(stone.x + stone.template_r for stone in stones)
            max_y = max(stone.y + stone.template_r for stone in stones)
            bounds = {
                "left": round(min_x, 4),
                "bottom": round(min_y, 4),
                "right": round(max_x, 4),
                "top": round(max_y, 4),
                "width": round(max_x - min_x, 4),
                "height": round(max_y - min_y, 4),
            }

        payload = {
            "units": "mm",
            "mode": mode,
            "stones": [
                {
                    "x": round(stone.x, 4),
                    "y": round(stone.y, 4),
                    "r": round(stone.template_r, 4),
                    "rot": round(stone.rotation, 4),
                }
                for stone in stones
            ],
            "style": self._serialize_style(settings),
            "meta": {
                "stone_count": len(stones),
                "template_diameter_mm": round(settings.template_diameter(), 4),
                "physical_diameter_mm": round(settings.physical_diameter(), 4),
                "pitch_mm": round(settings.pitch(), 4),
                "fast_threshold": int(settings.fast_output_threshold),
            },
            "bounds": bounds,
        }
        return payload

    def export_render_payload(
        self,
        stones: List[HexStone],
        settings: HexSettings,
        output_path: Optional[Path] = None,
        mode: str = "circle",
    ) -> str:
        """Write the render payload to disk in one O(n) JSON export step."""
        payload = self.build_render_payload(stones, settings, mode=mode)
        if output_path is None:
            handle = tempfile.NamedTemporaryFile(
                prefix="coreldraw_hexagon_",
                suffix=".json",
                delete=False,
            )
            output_path = Path(handle.name)
            handle.close()
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as file_handle:
            json.dump(payload, file_handle, separators=(",", ":"))

        logger.info(
            "Hexagon render payload exported: stones=%s path=%s mode=%s",
            len(stones),
            output_path,
            mode,
        )
        return str(output_path)

    def place_in_coreldraw(
        self,
        stones: List[HexStone],
        settings: HexSettings,
        progress_callback=None,
        cancel_callback=None,
        element_shape: Any = None,
    ) -> Dict[str, Any]:
        if not stones:
            logger.warning("Hexagon place_in_coreldraw called with no stones.")
            return {"mode": settings.output_mode.value, "stone_count": 0, "json_path": "", "rendered": False}

        total = len(stones)
        output_mode = self._resolve_output_mode(settings, total, element_shape=element_shape)
        render_mode = "element" if element_shape is not None else "circle"
        json_path = self.export_render_payload(stones, settings, mode=render_mode)

        result = {
            "mode": output_mode.value,
            "stone_count": total,
            "json_path": json_path,
            "rendered": False,
        }

        if progress_callback:
            progress_callback(total, total)

        if output_mode == OutputMode.PREVIEW_ONLY:
            logger.info("Hexagon output mode PREVIEW_ONLY; payload exported to %s", json_path)
            return result

        if output_mode == OutputMode.EXPORT_ONLY:
            logger.info("Hexagon output mode EXPORT_ONLY; payload exported to %s", json_path)
            return result

        if not corel.is_connected:
            raise RuntimeError("CorelDRAW is not connected.")

        if not corel.get_active_document():
            raise RuntimeError("No active CorelDRAW document is available.")

        try:
            macro_result = corel.run_macro("RenderRhinestonesFromJSON", json_path)
            result["rendered"] = True
            result["macro_result"] = macro_result
            result["render_method"] = "macro"
            try:
                corel.refresh()
            except Exception as refresh_exc:
                logger.warning("Hexagon macro refresh failed: %s", refresh_exc)
            logger.info(
                "Hexagon renderer dispatched to Corel macro: stones=%s json_path=%s",
                total,
                json_path,
            )
        except Exception as exc:
            logger.warning(
                "Hexagon macro renderer unavailable, falling back to internal Corel placement: %s",
                exc,
            )
            document = corel.get_active_document()
            layer = self._get_or_create_layer(document, settings.layer_name)
            with corel.optimization_mode(), corel.command_group("Hexagon Design"):
                if element_shape is not None:
                    created = self._place_fast_elements(
                        layer,
                        stones,
                        settings,
                        element_shape,
                        progress_callback=progress_callback,
                        cancel_callback=cancel_callback,
                    )
                else:
                    created = self._place_fast_circles(
                        layer,
                        stones,
                        settings,
                        progress_callback=progress_callback,
                        cancel_callback=cancel_callback,
                    )
                if settings.group_output and len(created) > 1:
                    try:
                        shape_range = corel.app.CreateShapeRange()
                        for shape in created:
                            shape_range.Add(shape)
                        shape_range.Group()
                    except Exception as group_exc:
                        logger.warning("Hexagon fallback grouping failed: %s", group_exc)
            try:
                corel.refresh()
            except Exception as refresh_exc:
                logger.warning("Hexagon fallback refresh failed: %s", refresh_exc)
            self._placed_shapes = created
            result["rendered"] = True
            result["render_method"] = "fallback_internal"
            result["macro_error"] = str(exc)
            result["created_count"] = len(created)
            logger.info(
                "Hexagon fallback renderer completed: stones=%s created=%s json_path=%s",
                total,
                len(created),
                json_path,
            )
        return result

    def get_statistics(self, stones: Optional[List[HexStone]] = None) -> Dict[str, Any]:
        current = self._last_stones if stones is None else stones
        if not current:
            return {"count": 0, "coverage_mm2": 0.0, "overlap_count": 0}
        coverage = sum(math.pi * stone.template_r * stone.template_r for stone in current)
        overlaps = sum(1 for stone in current if stone.overlap_flag)
        return {"count": len(current), "coverage_mm2": round(coverage, 2), "overlap_count": overlaps}

    @staticmethod
    def _get_or_create_layer(document: Any, layer_name: str):
        try:
            page = document.ActivePage
            for index in range(1, page.Layers.Count + 1):
                layer = page.Layers.Item(index)
                if layer.Name == layer_name:
                    return layer
        except Exception:
            pass
        try:
            page = document.ActivePage
            layer = page.Layers.Add(layer_name)
            logger.info("Created CorelDRAW layer '%s' for Hexagon output.", layer_name)
            return layer
        except Exception:
            logger.warning("Could not create layer '%s'. Falling back to the active layer.", layer_name)
            try:
                return document.ActiveLayer
            except Exception:
                return document.ActivePage.Layers.Item(1)
