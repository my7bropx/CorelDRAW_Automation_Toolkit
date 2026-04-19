"""
Curve Filler Engine
Core algorithms for filling curves with elements.
"""

import logging
import math
import random
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

from ...core.corel_interface import (
    corel, Point, CurveSegment, BoundingBox,
    CorelDRAWError, NoSelectionError
)

logger = logging.getLogger(__name__)


class SpacingMode(Enum):
    """Spacing calculation modes."""
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    AUTO_FIT = "auto_fit"
    RANDOM = "random"
    FORMULA = "formula"


class AngleMode(Enum):
    """Element rotation modes."""
    FOLLOW_CURVE = "follow_curve"
    FIXED = "fixed"
    RANDOM = "random"
    INCREMENTAL = "incremental"
    PERPENDICULAR = "perpendicular"


class AlignmentMode(Enum):
    """Element alignment to curve."""
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"
    BASELINE = "baseline"


class PatternMode(Enum):
    """Element pattern modes."""
    SINGLE = "single"
    SEQUENCE = "sequence"
    RANDOM = "random"
    GRADIENT_SCALE = "gradient_scale"
    ALTERNATING = "alternating"


class DirectionMode(Enum):
    """Direction for placing elements around curve."""
    INSIDE = "inside"
    OUTSIDE = "outside"
    BOTH = "both"


class DepthMode(Enum):
    """Depth ordering - different sizes for each line."""
    NONE = "none"
    INCREASING = "increasing"  # Each line gets larger
    DECREASING = "decreasing"  # Each line gets smaller
    ALTERNATING = "alternating"  # Large, small, large, small


class FillType(Enum):
    """Type of fill operation."""
    ALONG_CURVE = "along_curve"
    GRID = "grid"
    PARALLEL_LINES = "parallel_lines"
    BITMAP = "bitmap"
    REPLACE_SHAPES = "replace_shapes"


class OverlapMode(Enum):
    """How to handle overlapping elements."""
    NONE = "none"
    REMOVE_DUPLICATES = "remove_duplicates"
    COLLISION_DETECT = "collision_detect"


class OutputMode(Enum):
    """Output pipeline modes for CorelDRAW placement."""
    AUTO = "auto"
    TEMPLATE_DUPLICATE = "template_duplicate"
    LEGACY = "legacy"
    PREVIEW_ONLY = "preview_only"


@dataclass
class FillSettings:
    """Settings for curve filling operation."""
    # Spacing settings
    spacing_mode: SpacingMode = SpacingMode.FIXED
    spacing_value: float = 10.0  # mm
    spacing_percentage: float = 100.0
    spacing_min: float = 5.0
    spacing_max: float = 20.0
    start_padding: float = 0.0
    end_padding: float = 0.0

    # Angle settings
    angle_mode: AngleMode = AngleMode.FOLLOW_CURVE
    fixed_angle: float = 0.0
    angle_min: float = 0.0
    angle_max: float = 360.0
    angle_increment: float = 15.0

    # Alignment settings
    alignment: AlignmentMode = AlignmentMode.CENTER
    offset_from_curve: float = 0.0

    # Element count (for auto-fit)
    element_count: int = 0  # 0 means calculate based on spacing

    # Pattern settings
    pattern_mode: PatternMode = PatternMode.SINGLE
    pattern_sequence: List[int] = field(default_factory=list)

    # Scale settings
    scale_mode: str = "uniform"  # uniform, gradient, random
    scale_factor: float = 1.0
    scale_start: float = 1.0
    scale_end: float = 1.0
    scale_min: float = 0.5
    scale_max: float = 1.5

    # Advanced settings
    collision_detection: bool = False
    use_element_size: bool = True
    remove_overlaps: bool = True
    mirror_elements: bool = False
    flip_alternate: bool = False
    smart_corners: bool = True
    distribute_evenly: bool = False
    
    # ====== NEW FEATURES ======
    
    # Fill type
    fill_type: FillType = FillType.ALONG_CURVE
    
    # Direction settings (Feature 1)
    direction: DirectionMode = DirectionMode.OUTSIDE
    depth_mode: DepthMode = DepthMode.NONE
    depth_lines: int = 1  # Number of parallel lines
    depth_spacing: float = 10.0  # Spacing between depth lines
    depth_scale_start: float = 1.0  # Scale for first line
    depth_scale_end: float = 1.0  # Scale for last line
    
    # Parallel/offset curves (Feature 2)
    parallel_offset: float = 0.0  # Offset distance
    parallel_count: int = 1  # Number of parallel curves
    
    # Grid settings (Feature 3)
    grid_enabled: bool = False
    grid_spacing_x: float = 10.0
    grid_spacing_y: float = 10.0
    grid_shift: float = 0.0  # Shift amount (like honeycomb)
    grid_rows: int = 10
    grid_cols: int = 10
    
    # Random fill fix (Feature 4)
    random_use_selected_only: bool = True
    
    # Bitmap fill (Feature 5)
    bitmap_width: int = 100
    bitmap_height: int = 100
    bitmap_element_size: float = 5.0
    
    # Shape replacement (Feature 7)
    replace_shapes_enabled: bool = False
    replacement_element_size: float = 5.0
    
    # Alignment (Feature 8)
    align_enabled: bool = False
    distribute_enabled: bool = False
    distribute_count: int = 5
    distribute_spacing: float = 10.0
    
    # Duplicate detection (Feature 9)
    duplicate_threshold: float = 1.0  # Distance threshold for duplicates
    duplicate_action: str = "select"  # select, delete, color
    
    # Overlap fix (Feature 6)
    overlap_mode: OverlapMode = OverlapMode.NONE
    
    # Multi-Resize for Regular Curves (Feature 11)
    multiresize_enabled: bool = False
    multiresize_min: float = 2.0
    multiresize_max: float = 8.0
    multiresize_count: int = 3
    multiresize_distribution: str = "random"  # random, gradient_up, gradient_down, alternating
    
    # Multi-Resize for Bitmap Fill (Feature 12)
    bitmap_multiresize_enabled: bool = False
    bitmap_multiresize_min: float = 2.0
    bitmap_multiresize_max: float = 8.0
    bitmap_multiresize_count: int = 3
    bitmap_multiresize_pattern: str = "random"  # random, checkerboard, gradient
    output_mode: OutputMode = OutputMode.AUTO
    fast_output_threshold: int = 5000
    progress_updates: int = 200


@dataclass
class PlacementPoint:
    """Represents where an element should be placed."""
    position: Point
    rotation: float = 0.0
    scale: float = 1.0
    element_index: int = 0


class CurveFillerEngine:
    """
    Core engine for filling curves with elements.
    Handles all placement calculations and transformations.
    """

    def __init__(self):
        """Initialize the curve filler engine."""
        self._curve_segments: List[CurveSegment] = []
        self._fill_elements = []
        self._container_shape = None
        self._placed_elements = []
        self._last_settings: Optional[FillSettings] = None

        logger.info("Curve filler engine initialized.")

    def _progress_stride(self, total: int, updates: int = 200) -> int:
        """Throttle progress callbacks to reduce UI and COM overhead."""
        return max(1, total // max(1, updates))

    def _resolve_output_mode(self, settings: Optional[FillSettings], total: int) -> OutputMode:
        """Select a placement mode while preserving explicit user choices."""
        if settings and settings.output_mode in (
            OutputMode.PREVIEW_ONLY,
            OutputMode.LEGACY,
            OutputMode.TEMPLATE_DUPLICATE,
        ):
            return settings.output_mode

        if total >= max(1, settings.fast_output_threshold if settings else 5000):
            logger.info(
                "Curve filler using cached template duplicate mode for %s placements.",
                total,
            )
        return OutputMode.TEMPLATE_DUPLICATE

    def _template_scale_key(self, scale: float) -> float:
        """Round scale keys to keep template caching efficient."""
        return round(float(scale), 4)

    def _build_template_cache(self, placements: List["PlacementPoint"]) -> Dict[Tuple[int, float], Any]:
        """Create centered reusable templates for each element/scale combination."""
        templates: Dict[Tuple[int, float], Any] = {}
        if not self._fill_elements:
            return templates

        count = len(self._fill_elements)
        required_keys = set()
        for placement in placements:
            element_index = placement.element_index % count if count > 0 else 0
            required_keys.add((element_index, self._template_scale_key(placement.scale)))

        for element_index, scale_key in required_keys:
            template = corel.duplicate_shape(self._fill_elements[element_index])
            if scale_key != 1.0:
                corel.scale_shape(template, scale_key)
            corel.center_shape_at_origin(template)
            templates[(element_index, scale_key)] = template

        return templates

    def _cleanup_template_cache(self, templates: Dict[Tuple[int, float], Any]) -> None:
        """Delete temporary template shapes after placement completes."""
        for template in templates.values():
            try:
                template.Delete()
            except Exception:
                pass

    def _execute_fill_fast(
        self,
        placements: List["PlacementPoint"],
        progress_callback=None,
        cancel_callback=None,
        progress_stride: int = 1,
    ) -> List[Any]:
        """Place elements using centered cached templates to minimize COM round trips."""
        created_shapes = []
        templates = self._build_template_cache(placements)
        total = len(placements)
        count = len(self._fill_elements)

        try:
            for index, placement in enumerate(placements, start=1):
                if cancel_callback and cancel_callback():
                    logger.info("Curve fill cancelled after %s of %s placements.", index - 1, total)
                    break

                element_index = placement.element_index % count if count > 0 else 0
                key = (element_index, self._template_scale_key(placement.scale))
                template = templates.get(key)
                if template is None:
                    logger.warning("Missing fast template for key %s, skipping placement %s.", key, index)
                    continue

                new_shape = corel.duplicate_centered_template(
                    template,
                    placement.position.x,
                    placement.position.y,
                    rotation=placement.rotation,
                )
                created_shapes.append(new_shape)

                if progress_callback and (index % progress_stride == 0 or index == total):
                    progress_callback(index, total)
                elif index % progress_stride == 0 or index == total:
                    logger.debug("Placed %s/%s elements", index, total)
        finally:
            self._cleanup_template_cache(templates)

        return created_shapes

    def _execute_fill_legacy(
        self,
        placements: List["PlacementPoint"],
        progress_callback=None,
        cancel_callback=None,
        progress_stride: int = 1,
    ) -> List[Any]:
        """Original per-placement duplication path kept for compatibility."""
        created_shapes = []
        total = len(placements)

        for index, placement in enumerate(placements, start=1):
            if cancel_callback and cancel_callback():
                logger.info("Curve fill cancelled after %s of %s placements.", index - 1, total)
                break

            count = len(self._fill_elements)
            safe_idx = placement.element_index % count if count > 0 else 0
            element = self._fill_elements[safe_idx]
            new_shape = corel.duplicate_shape(element)

            if placement.scale != 1.0:
                corel.scale_shape(new_shape, placement.scale)

            center = corel.get_shape_center(new_shape)
            corel.move_shape_by(
                new_shape,
                placement.position.x - center.x,
                placement.position.y - center.y,
            )

            if placement.rotation != 0:
                corel.rotate_shape(
                    new_shape,
                    placement.rotation,
                    placement.position.x,
                    placement.position.y,
                )

            created_shapes.append(new_shape)

            if progress_callback and (index % progress_stride == 0 or index == total):
                progress_callback(index, total)
            elif index % progress_stride == 0 or index == total:
                logger.debug("Placed %s/%s elements", index, total)

        return created_shapes

    def set_container(self, shape):
        """
        Set the container curve/shape to fill.

        Args:
            shape: CorelDRAW shape object (curve).
        """
        self._container_shape = shape
        self._curve_segments = corel.get_curve_path(shape)

        if not self._curve_segments:
            raise ValueError("Selected shape has no valid curve data.")

        total_length = corel.get_curve_total_length(self._curve_segments)
        logger.info(f"Container set. Total curve length: {total_length:.2f}")

    def set_fill_elements(self, shapes):
        """
        Set the elements to use for filling.

        Args:
            shapes: List or range of CorelDRAW shape objects.
        """
        self._fill_elements = []
        if hasattr(shapes, 'Count'):
            # COM object - use Item() method
            for i in range(shapes.Count):
                self._fill_elements.append(shapes.Item(i + 1))  # COM is 1-indexed
        else:
            # Regular Python list/tuple
            self._fill_elements = list(shapes)

        if not self._fill_elements:
            raise ValueError("No fill elements provided.")

        logger.info(f"Fill elements set. Count: {len(self._fill_elements)}")

    def calculate_placements(self, settings: FillSettings) -> List[PlacementPoint]:
        """
        Calculate all placement points for elements along the curve.

        Args:
            settings: FillSettings object with all parameters.

        Returns:
            List of PlacementPoint objects.
        """
        if not self._curve_segments:
            raise ValueError("No container curve set.")

        if not self._fill_elements:
            raise ValueError("No fill elements set.")

        # ── Input validation ──────────────────────────────────────────────────
        if settings.spacing_value <= 0 and settings.spacing_mode == SpacingMode.FIXED:
            logger.warning("spacing_value is <= 0 — clamping to 1.0 mm.")
            settings = __import__('dataclasses').replace(settings, spacing_value=1.0)
        if settings.spacing_min <= 0 and settings.spacing_mode == SpacingMode.RANDOM:
            logger.warning("spacing_min is <= 0 — clamping to 0.1 mm.")
            settings = __import__('dataclasses').replace(settings, spacing_min=0.1)
        if settings.start_padding < 0:
            settings = __import__('dataclasses').replace(settings, start_padding=0.0)
        if settings.end_padding < 0:
            settings = __import__('dataclasses').replace(settings, end_padding=0.0)

        self._last_settings = settings
        placements = []

        total_length = corel.get_curve_total_length(self._curve_segments)
        usable_length = total_length - settings.start_padding - settings.end_padding

        if usable_length <= 0:
            logger.warning("No usable length after padding.")
            return placements

        # Determine element positions
        positions = self._calculate_positions(settings, usable_length)

        # Calculate placement for each position
        current_angle = settings.fixed_angle
        current_scale = settings.scale_start

        for i, distance in enumerate(positions):
            actual_distance = settings.start_padding + distance

            # Get point and tangent on curve
            point, tangent = corel.get_point_on_curve(self._curve_segments, actual_distance)

            # Calculate rotation
            rotation = self._calculate_rotation(settings, tangent, i, current_angle)
            if settings.angle_mode == AngleMode.INCREMENTAL:
                current_angle += settings.angle_increment

            # Calculate scale
            scale = self._calculate_scale(settings, i, len(positions), current_scale)

            # Apply offset
            offset_point = self._apply_offset(point, tangent, settings)

            # Determine which element to use
            element_index = self._get_element_index(settings, i)

            placement = PlacementPoint(
                position=offset_point,
                rotation=rotation,
                scale=scale,
                element_index=element_index
            )
            placements.append(placement)

        # Apply collision detection if enabled
        if settings.collision_detection:
            placements = self._remove_collisions(placements)

        # Post-pass overlap removal (spatial hash)
        if settings.remove_overlaps:
            placements = self._remove_overlaps(placements)

        logger.info(f"Calculated {len(placements)} placement points.")
        return placements

    def _calculate_positions(self, settings: FillSettings, usable_length: float) -> List[float]:
        """Calculate positions along the curve where elements should be placed."""
        positions = []
        base_size = None
        if settings.use_element_size and self._fill_elements:
            sizes = []
            for elem in self._fill_elements:
                try:
                    bounds = corel.get_shape_bounds(elem)
                    sizes.append(max(bounds.width, bounds.height))
                except Exception:
                    continue
            if sizes:
                base_size = sum(sizes) / len(sizes)

        if settings.element_count > 0 and settings.spacing_mode != SpacingMode.RANDOM:
            # Use specified element count
            if settings.distribute_evenly and settings.element_count > 1:
                # Distribute evenly
                spacing = usable_length / (settings.element_count - 1)
                for i in range(settings.element_count):
                    positions.append(i * spacing)
            else:
                spacing = usable_length / settings.element_count
                for i in range(settings.element_count):
                    positions.append(i * spacing + spacing / 2)

        elif settings.spacing_mode == SpacingMode.FIXED:
            # Fixed spacing
            spacing = settings.spacing_value
            if base_size is not None:
                spacing = base_size + settings.spacing_value
            distance = 0.0
            while distance < usable_length:
                positions.append(distance)
                distance += spacing

        elif settings.spacing_mode == SpacingMode.PERCENTAGE:
            # Percentage-based spacing (relative to first element size)
            if self._fill_elements:
                if base_size is None:
                    elem_bounds = corel.get_shape_bounds(self._fill_elements[0])
                    base_spacing = max(elem_bounds.width, elem_bounds.height)
                else:
                    base_spacing = base_size
                spacing = base_spacing * (settings.spacing_percentage / 100.0)

                distance = 0.0
                while distance < usable_length:
                    positions.append(distance)
                    distance += spacing

        elif settings.spacing_mode == SpacingMode.AUTO_FIT:
            # Auto-fit: fill the entire curve length
            if settings.element_count > 0:
                count = settings.element_count
            else:
                # Estimate count based on element size
                if self._fill_elements:
                    if base_size is None:
                        elem_bounds = corel.get_shape_bounds(self._fill_elements[0])
                        elem_size = max(elem_bounds.width, elem_bounds.height)
                    else:
                        elem_size = base_size
                    count = max(1, int(usable_length / elem_size))
                else:
                    count = 10

            if count > 1:
                spacing = usable_length / (count - 1)
                for i in range(count):
                    positions.append(i * spacing)
            elif count == 1:
                positions.append(usable_length / 2)

        elif settings.spacing_mode == SpacingMode.RANDOM:
            # Random spacing
            distance = 0.0
            while distance < usable_length:
                positions.append(distance)
                spacing = random.uniform(settings.spacing_min, settings.spacing_max)
                distance += spacing

        return positions

    def _calculate_rotation(self, settings: FillSettings, tangent: float,
                           index: int, current_angle: float) -> float:
        """Calculate rotation angle for an element."""
        if settings.angle_mode == AngleMode.FOLLOW_CURVE:
            return tangent
        elif settings.angle_mode == AngleMode.FIXED:
            return settings.fixed_angle
        elif settings.angle_mode == AngleMode.RANDOM:
            return random.uniform(settings.angle_min, settings.angle_max)
        elif settings.angle_mode == AngleMode.INCREMENTAL:
            return current_angle
        elif settings.angle_mode == AngleMode.PERPENDICULAR:
            return tangent + 90.0
        else:
            return 0.0

    def _calculate_scale(self, settings: FillSettings, index: int,
                        total_count: int, current_scale: float) -> float:
        """Calculate scale factor for an element."""
        if settings.scale_mode == "uniform":
            return settings.scale_factor
        elif settings.scale_mode == "gradient":
            if total_count <= 1:
                return settings.scale_start
            t = index / (total_count - 1)
            return settings.scale_start + t * (settings.scale_end - settings.scale_start)
        elif settings.scale_mode == "random":
            return random.uniform(settings.scale_min, settings.scale_max)
        else:
            return 1.0

    def _apply_offset(self, point: Point, tangent: float, settings: FillSettings) -> Point:
        """Apply offset from curve based on alignment and offset settings."""
        if settings.offset_from_curve == 0:
            return point

        # Calculate perpendicular direction
        perp_angle = math.radians(tangent + 90)
        offset_x = settings.offset_from_curve * math.cos(perp_angle)
        offset_y = settings.offset_from_curve * math.sin(perp_angle)

        return Point(point.x + offset_x, point.y + offset_y)

    def _get_element_index(self, settings: FillSettings, placement_index: int) -> int:
        """Determine which fill element to use for a placement."""
        num_elements = len(self._fill_elements)

        if num_elements == 0:
            return 0

        if settings.pattern_mode == PatternMode.SINGLE:
            return 0
        elif settings.pattern_mode == PatternMode.SEQUENCE:
            if settings.pattern_sequence:
                seq_index = placement_index % len(settings.pattern_sequence)
                return settings.pattern_sequence[seq_index] % num_elements
            else:
                return placement_index % num_elements
        elif settings.pattern_mode == PatternMode.RANDOM:
            return random.randint(0, num_elements - 1)
        elif settings.pattern_mode == PatternMode.ALTERNATING:
            return placement_index % num_elements
        else:
            return 0

    def _remove_collisions(self, placements: List[PlacementPoint]) -> List[PlacementPoint]:
        """Remove placements that would cause element overlap."""
        if not placements or not self._fill_elements:
            return placements

        elem_sizes = []
        for elem in self._fill_elements:
            bounds = corel.get_shape_bounds(elem)
            size = max(bounds.width, bounds.height)
            elem_sizes.append(size)

        n_elems = len(elem_sizes)  # guard for index clamping
        filtered = [placements[0]]

        for i in range(1, len(placements)):
            current = placements[i]
            prev = filtered[-1]

            # ── Clamp element_index so it never goes out of range ─────────────
            cur_idx  = current.element_index % n_elems if n_elems > 0 else 0
            prev_idx = prev.element_index    % n_elems if n_elems > 0 else 0

            current_size = elem_sizes[cur_idx]  * current.scale
            prev_size    = elem_sizes[prev_idx] * prev.scale

            min_distance    = (current_size + prev_size) / 2
            actual_distance = prev.position.distance_to(current.position)

            if actual_distance >= min_distance * 0.9:
                filtered.append(current)

        logger.info(f"Collision detection removed {len(placements) - len(filtered)} placements.")
        return filtered

    def _remove_overlaps(self, placements: List[PlacementPoint]) -> List[PlacementPoint]:
        """Remove overlapping placements using a spatial hash."""
        if not placements or not self._fill_elements:
            return placements

        elem_sizes = []
        for elem in self._fill_elements:
            bounds = corel.get_shape_bounds(elem)
            elem_sizes.append(max(bounds.width, bounds.height))

        max_size = max(elem_sizes) if elem_sizes else 0.0
        if max_size <= 0:
            return placements

        n_elems = len(elem_sizes)  # guard for index clamping
        cell_size = max_size
        grid: Dict[Tuple[int, int], List[int]] = {}
        kept: List[PlacementPoint] = []

        def _cell_key(p: Point) -> Tuple[int, int]:
            return (int(p.x // cell_size), int(p.y // cell_size))

        for p in placements:
            # ── Clamp element_index so it never goes out of range ─────────────
            safe_idx = p.element_index % n_elems if n_elems > 0 else 0
            size = elem_sizes[safe_idx] * p.scale
            cx, cy = _cell_key(p.position)
            overlap = False
            for gx in (cx - 1, cx, cx + 1):
                for gy in (cy - 1, cy, cy + 1):
                    for idx in grid.get((gx, gy), []):
                        other = kept[idx]
                        other_safe_idx = other.element_index % n_elems if n_elems > 0 else 0
                        other_size = elem_sizes[other_safe_idx] * other.scale
                        min_dist = (size + other_size) / 2
                        dx = p.position.x - other.position.x
                        dy = p.position.y - other.position.y
                        if (dx * dx + dy * dy) < (min_dist * min_dist):
                            overlap = True
                            break
                    if overlap:
                        break
                if overlap:
                    break
            if overlap:
                continue
            grid.setdefault((cx, cy), []).append(len(kept))
            kept.append(p)

        return kept

    def apply_multiresize(self, placements: List[PlacementPoint], 
                          settings: FillSettings) -> List[PlacementPoint]:
        """Apply multi-resize scaling to placements based on distribution mode."""
        if not settings.multiresize_enabled or len(placements) == 0:
            return placements
            
        min_size = settings.multiresize_min
        max_size = settings.multiresize_max
        count = settings.multiresize_count
        distribution = settings.multiresize_distribution
        
        # ── Derive base_size from actual fill elements instead of hardcoding 5.0
        # The old hardcoded value caused all scale factors to be wrong whenever
        # elements weren't exactly 5 mm.
        base_size = 5.0  # safe default
        if self._fill_elements:
            try:
                sizes = []
                for elem in self._fill_elements:
                    bounds = corel.get_shape_bounds(elem)
                    s = max(bounds.width, bounds.height)
                    if s > 0:
                        sizes.append(s)
                if sizes:
                    base_size = sum(sizes) / len(sizes)
            except Exception:
                pass  # keep default 5.0 if shapes are unavailable
        
        scales = []
        if distribution == "random":
            for _ in range(len(placements)):
                size = random.uniform(min_size, max_size)
                scales.append(size / base_size)
        elif distribution == "gradient_up":
            for i, _ in enumerate(placements):
                t = i / max(1, len(placements) - 1)
                size = min_size + (max_size - min_size) * t
                scales.append(size / base_size)
        elif distribution == "gradient_down":
            for i, _ in enumerate(placements):
                t = i / max(1, len(placements) - 1)
                size = max_size - (max_size - min_size) * t
                scales.append(size / base_size)
        elif distribution == "alternating":
            for i, _ in enumerate(placements):
                idx = i % (count * 2)
                if idx < count:
                    size = min_size + (max_size - min_size) * (idx / max(1, count - 1))
                else:
                    size = max_size - (max_size - min_size) * ((idx - count) / max(1, count - 1))
                scales.append(size / base_size)
        
        for p, scale in zip(placements, scales):
            p.scale = scale
            
        return placements

    def execute_fill(self, placements: List[PlacementPoint] = None,
                    settings: FillSettings = None,
                    progress_callback=None,
                    cancel_callback=None) -> List[Any]:
        """
        Execute the fill operation in CorelDRAW.

        Args:
            placements:        Pre-calculated placements (optional).
            settings:          Fill settings (required if placements not provided).
            progress_callback: Optional callable(current, total) for UI progress bar.
            cancel_callback:   Optional callable() → bool; return True to abort early.

        Returns:
            List of created shape objects.
        """
        if placements is None:
            if settings is None:
                raise ValueError("Either placements or settings must be provided.")
            placements = self.calculate_placements(settings)

        if not placements:
            logger.warning("No placements to execute.")
            return []

        if settings and settings.multiresize_enabled:
            placements = self.apply_multiresize(placements, settings)

        total = len(placements)
        output_mode = self._resolve_output_mode(settings, total)
        progress_stride = self._progress_stride(total, settings.progress_updates if settings else 200)

        if output_mode == OutputMode.PREVIEW_ONLY:
            logger.info("Curve fill output skipped because preview-only mode is active.")
            return []

        try:
            with corel.optimization_mode(), corel.command_group("Curve Fill"):
                if output_mode == OutputMode.TEMPLATE_DUPLICATE:
                    created_shapes = self._execute_fill_fast(
                        placements,
                        progress_callback=progress_callback,
                        cancel_callback=cancel_callback,
                        progress_stride=progress_stride,
                    )
                    self._placed_elements = created_shapes
                    logger.info(
                        "Successfully placed %s elements using curve filler output mode '%s'.",
                        len(created_shapes),
                        output_mode.value,
                    )
                    return created_shapes

                created_shapes = []

                for i, placement in enumerate(placements):
                    # ── Honour cancellation ───────────────────────────────────
                    if cancel_callback and cancel_callback():
                        logger.info(f"Fill cancelled after {i} of {total} placements.")
                        break

                    # ── Clamp element_index — never let it exceed fill_elements length
                    n = len(self._fill_elements)
                    safe_idx = placement.element_index % n if n > 0 else 0
                    element = self._fill_elements[safe_idx]

                    # Duplicate element
                    new_shape = corel.duplicate_shape(element)

                    # 1. Scale if needed
                    if placement.scale != 1.0:
                        corel.scale_shape(new_shape, placement.scale)

                    # 2. Move to position
                    center = corel.get_shape_center(new_shape)
                    offset_x = placement.position.x - center.x
                    offset_y = placement.position.y - center.y
                    corel.move_shape_by(new_shape, offset_x, offset_y)

                    # 3. Rotate
                    if placement.rotation != 0:
                        corel.rotate_shape(
                            new_shape,
                            placement.rotation,
                            placement.position.x,
                            placement.position.y
                        )

                    created_shapes.append(new_shape)

                    # ── Report progress every 10 shapes ──────────────────────
                    if progress_callback and ((i + 1) % progress_stride == 0 or (i + 1) == total):
                        progress_callback(i + 1, total)
                    elif (i + 1) % progress_stride == 0 or (i + 1) == total:
                        logger.debug(f"Placed {i + 1}/{total} elements")

                # Final progress tick
                if progress_callback:
                    progress_callback(len(created_shapes), total)

                self._placed_elements = created_shapes
                logger.info(f"Successfully placed {len(created_shapes)} elements.")

        except Exception as e:
            logger.error(f"Fill operation failed: {e}")
            created_shapes = []
        
        return created_shapes

    def adjust_count(self, new_count: int):
        """
        Adjust the number of placed elements after filling.

        Args:
            new_count: Desired number of elements.
        """
        if not self._last_settings:
            raise ValueError("No fill operation has been performed yet.")

        if not self._placed_elements:
            logger.warning("No placed elements to adjust.")
            return

        current_count = len(self._placed_elements)

        if new_count == current_count:
            return

        corel.begin_command_group("Adjust Element Count")

        try:
            if new_count < current_count:
                # Remove excess elements from the end
                for i in range(new_count, current_count):
                    corel.delete_shape(self._placed_elements[i])
                self._placed_elements = self._placed_elements[:new_count]

            else:
                # Add more elements — recalculate with a NEW settings copy.
                # NEVER mutate self._last_settings directly: doing
                #   settings = self._last_settings
                #   settings.element_count = new_count
                # would permanently overwrite the stored settings so every
                # subsequent adjust_count call would start from the wrong count.
                from dataclasses import replace as dc_replace
                settings = dc_replace(self._last_settings, element_count=new_count)

                new_placements = self.calculate_placements(settings)

                # Remove old elements then create new set
                for shape in self._placed_elements:
                    corel.delete_shape(shape)

                self._placed_elements = self.execute_fill(new_placements, settings)

        finally:
            corel.end_command_group()

        logger.info(f"Element count adjusted from {current_count} to {new_count}")

    def group_placed_elements(self):
        """Group all placed elements."""
        if not self._placed_elements:
            return None

        # Create a shape range
        shapes = corel.app.CreateShapeRange()
        for shape in self._placed_elements:
            shapes.Add(shape)

        return corel.create_group(shapes)

    def select_placed_elements(self):
        """Select all placed elements."""
        if not self._placed_elements:
            return

        shapes = corel.app.CreateShapeRange()
        for shape in self._placed_elements:
            shapes.Add(shape)

        shapes.CreateSelection()

    def clear_placed_elements(self):
        """Remove all placed elements."""
        corel.begin_command_group("Clear Fill")

        try:
            for shape in self._placed_elements:
                corel.delete_shape(shape)
            self._placed_elements = []
        finally:
            corel.end_command_group()

        logger.info("All placed elements cleared.")

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the current fill operation."""
        stats = {
            'element_count': len(self._placed_elements),
            'curve_length': corel.get_curve_total_length(self._curve_segments) if self._curve_segments else 0,
            'fill_element_count': len(self._fill_elements),
        }

        if self._last_settings:
            stats['settings'] = {
                'spacing_mode': self._last_settings.spacing_mode.value,
                'angle_mode': self._last_settings.angle_mode.value,
            }

        return stats

    # ====== NEW FEATURE METHODS ======

    def calculate_direction_placements(self, settings: FillSettings) -> List[PlacementPoint]:
        """
        Feature 1: Calculate placements with direction (inside/outside/both) and depth ordering.
        """
        if not self._curve_segments or not self._fill_elements:
            return []

        placements = []
        
        # Determine number of lines based on direction mode
        if settings.direction == DirectionMode.BOTH:
            line_count = max(1, settings.depth_lines) * 2
        else:
            line_count = max(1, settings.depth_lines)

        # Calculate base positions first
        total_length = corel.get_curve_total_length(self._curve_segments)
        usable_length = total_length - settings.start_padding - settings.end_padding
        
        if usable_length <= 0:
            return []

        base_positions = self._calculate_positions(settings, usable_length)
        
        # Process each depth line
        for line_idx in range(line_count):
            # Determine direction sign for this line
            if settings.direction == DirectionMode.BOTH:
                # Even lines go outside (+), odd lines go inside (-)
                direction_sign = 1 if line_idx % 2 == 0 else -1
            elif settings.direction == DirectionMode.OUTSIDE:
                direction_sign = 1
            else:  # INSIDE
                direction_sign = -1

            # Calculate offset for this depth line
            line_offset = settings.depth_spacing * (line_idx // 2 + 1) * direction_sign
            
            # Calculate scale for this depth line based on depth mode
            if settings.depth_mode != DepthMode.NONE and settings.depth_lines > 1:
                depth_progress = line_idx / (line_count - 1) if line_count > 1 else 0
                if settings.depth_mode == DepthMode.INCREASING:
                    scale = settings.depth_scale_start + depth_progress * (settings.depth_scale_end - settings.depth_scale_start)
                elif settings.depth_mode == DepthMode.DECREASING:
                    scale = settings.depth_scale_start - depth_progress * (settings.depth_scale_start - settings.depth_scale_end)
                elif settings.depth_mode == DepthMode.ALTERNATING:
                    scale = settings.depth_scale_start if line_idx % 2 == 0 else settings.depth_scale_end
                else:
                    scale = settings.depth_scale_start
            else:
                scale = settings.depth_scale_start

            # Generate placements for this line
            for i, distance in enumerate(base_positions):
                actual_distance = settings.start_padding + distance
                point, tangent = corel.get_point_on_curve(self._curve_segments, actual_distance)
                
                # Apply offset perpendicular to curve
                perp_angle = math.radians(tangent + 90)
                offset_x = line_offset * math.cos(perp_angle)
                offset_y = line_offset * math.sin(perp_angle)
                
                position = Point(point.x + offset_x, point.y + offset_y)
                rotation = self._calculate_rotation(settings, tangent, i, settings.fixed_angle)
                
                # Apply depth scale
                element_scale = self._calculate_scale(settings, i, len(base_positions), settings.scale_start) * scale
                
                element_index = self._get_element_index(settings, i)
                
                placements.append(PlacementPoint(
                    position=position,
                    rotation=rotation,
                    scale=element_scale,
                    element_index=element_index
                ))

        # Apply collision/overlap removal if enabled
        if settings.overlap_mode != OverlapMode.NONE:
            placements = self._apply_overlap_removal(placements, settings)

        logger.info(f"Direction fill: {len(placements)} placements across {line_count} lines")
        return placements

    def calculate_parallel_curves(self, settings: FillSettings) -> List[PlacementPoint]:
        """
        Feature 2: Place stones on parallel/offset curves.
        """
        if not self._curve_segments or not self._fill_elements:
            return []

        placements = []
        total_length = corel.get_curve_total_length(self._curve_segments)
        usable_length = total_length - settings.start_padding - settings.end_padding
        
        if usable_length <= 0:
            return []

        base_positions = self._calculate_positions(settings, usable_length)
        
        # Create offset curves and place elements
        for offset_idx in range(settings.parallel_count):
            offset_distance = settings.parallel_offset * (offset_idx + 1)
            
            for i, distance in enumerate(base_positions):
                actual_distance = settings.start_padding + distance
                point, tangent = corel.get_point_on_curve(self._curve_segments, actual_distance)
                
                # Apply offset perpendicular to curve
                perp_angle = math.radians(tangent + 90)
                offset_x = offset_distance * math.cos(perp_angle)
                offset_y = offset_distance * math.sin(perp_angle)
                
                position = Point(point.x + offset_x, point.y + offset_y)
                rotation = self._calculate_rotation(settings, tangent, i, settings.fixed_angle)
                scale = self._calculate_scale(settings, i, len(base_positions), settings.scale_start)
                
                element_index = self._get_element_index(settings, i)
                
                placements.append(PlacementPoint(
                    position=position,
                    rotation=rotation,
                    scale=scale,
                    element_index=element_index
                ))

        return placements

    def calculate_grid_placements(self, settings: FillSettings, bounds: BoundingBox) -> List[PlacementPoint]:
        """
        Feature 3: Simple grid with optional shift (honeycomb pattern).
        """
        if not self._fill_elements:
            return []

        placements = []
        
        # Calculate grid bounds
        width = bounds.right - bounds.left
        height = bounds.top - bounds.bottom
        
        # Calculate center point
        center_x = (bounds.left + bounds.right) / 2
        center_y = (bounds.bottom + bounds.top) / 2
        
        # Grid with shift for honeycomb effect
        row_height = settings.grid_spacing_y * 0.866  # Hexagonal height
        col_width = settings.grid_spacing_x
        
        for row in range(settings.grid_rows):
            for col in range(settings.grid_cols):
                # Calculate base position
                x = bounds.left + col * col_width
                y = bounds.bottom + row * row_height
                
                # Apply shift to alternate rows
                if settings.grid_shift > 0 and row % 2 == 1:
                    x += settings.grid_shift * col_width
                
                # Check bounds
                if x < bounds.left or x > bounds.right or y < bounds.bottom or y > bounds.top:
                    continue
                
                position = Point(x, y)
                rotation = settings.fixed_angle
                scale = settings.scale_factor
                element_index = self._get_element_index(settings, row * settings.grid_cols + col)
                
                placements.append(PlacementPoint(
                    position=position,
                    rotation=rotation,
                    scale=scale,
                    element_index=element_index
                ))

        logger.info(f"Grid fill: {len(placements)} placements")
        return placements

    def calculate_bitmap_fill(self, settings: FillSettings, bounds: BoundingBox) -> List[PlacementPoint]:
        """
        Feature 5: Full fixed bitmap fill with selected sizes.
        """
        if not self._fill_elements:
            return []

        placements = []
        
        # Calculate element size
        elem_size = settings.bitmap_element_size
        
        # Fill the bounding box with elements in a grid pattern
        x = bounds.left
        y = bounds.bottom
        row = 0
        
        while y < bounds.top:
            while x < bounds.right:
                position = Point(x + elem_size/2, y + elem_size/2)
                
                # Check if within bounds
                if position.x <= bounds.right and position.y <= bounds.top:
                    rotation = settings.fixed_angle
                    scale = settings.scale_factor
                    element_index = self._get_element_index(settings, row)
                    
                    placements.append(PlacementPoint(
                        position=position,
                        rotation=rotation,
                        scale=scale,
                        element_index=element_index
                    ))
                
                x += elem_size
            
            y += elem_size
            x = bounds.left
            row += 1

        logger.info(f"Bitmap fill: {len(placements)} placements")
        
        if settings.bitmap_multiresize_enabled:
            placements = self._apply_bitmap_multiresize(placements, settings)
        
        return placements
    
    def _apply_bitmap_multiresize(self, placements: List[PlacementPoint], 
                                   settings: FillSettings) -> List[PlacementPoint]:
        """Apply multi-resize scaling to bitmap fill placements."""
        if not placements:
            return placements
            
        min_size = settings.bitmap_multiresize_min
        max_size = settings.bitmap_multiresize_max
        count    = settings.bitmap_multiresize_count
        pattern  = settings.bitmap_multiresize_pattern
        
        base_size = settings.bitmap_element_size if settings.bitmap_element_size > 0 else 1.0
        
        # Build the size-level scale table
        sizes = []
        for i in range(count):
            t = i / max(1, count - 1)
            size = min_size + (max_size - min_size) * t
            sizes.append(size / base_size)

        # ── Derive column count from the placements themselves ────────────────
        # settings.bitmap_width is a pixel dimension and must NOT be used here
        # as a mm-based column count — that produces completely wrong results.
        # Instead we estimate columns from the spacing: how many elements fit
        # across the bounding box of all placements.
        if placements:
            xs = [p.position.x for p in placements]
            x_span = max(xs) - min(xs) if len(xs) > 1 else base_size
            cols = max(1, round(x_span / base_size) + 1)
        else:
            cols = 1
        
        if pattern == "random":
            for i, p in enumerate(placements):
                p.scale = sizes[i % len(sizes)]
        elif pattern == "checkerboard":
            for i, p in enumerate(placements):
                row = i // cols
                col = i % cols
                p.scale = sizes[(row + col) % len(sizes)]
        elif pattern in ("gradient", "rows"):
            rows_total = max(1, math.ceil(len(placements) / cols))
            for i, p in enumerate(placements):
                row = i // cols
                t = row / max(1, rows_total - 1)
                idx = min(int(t * len(sizes)), len(sizes) - 1)
                p.scale = sizes[idx]
        elif pattern == "cols":
            for i, p in enumerate(placements):
                col = i % cols
                t = col / max(1, cols - 1)
                idx = min(int(t * len(sizes)), len(sizes) - 1)
                p.scale = sizes[idx]
        
        return placements

    def calculate_random_fill(self, settings: FillSettings) -> List[PlacementPoint]:
        """
        Feature 4: Fixed Random fill to use only selected elements.
        """
        if not self._fill_elements:
            return []

        # Use only the selected elements (self._fill_elements)
        return self.calculate_placements(settings)

    def detect_duplicates(self, placements: List[PlacementPoint], 
                          settings: FillSettings) -> Tuple[List[int], List[int]]:
        """
        Feature 9: Detect duplicate placements.
        
        Returns:
            Tuple of (duplicate_indices, unique_indices)
        """
        if not placements:
            return [], []

        threshold = settings.duplicate_threshold
        duplicate_indices = []
        unique_indices = []
        processed: List[Tuple[float, float]] = []

        for i, placement in enumerate(placements):
            is_duplicate = False
            
            for px, py in processed:
                dx = placement.position.x - px
                dy = placement.position.y - py
                distance = math.sqrt(dx*dx + dy*dy)
                
                if distance < threshold:
                    is_duplicate = True
                    break
            
            if is_duplicate:
                duplicate_indices.append(i)
            else:
                unique_indices.append(i)
                processed.append((placement.position.x, placement.position.y))

        logger.info(f"Duplicate detection: {len(unique_indices)} unique, {len(duplicate_indices)} duplicates")
        return duplicate_indices, unique_indices

    def handle_duplicates(self, placements: List[PlacementPoint], 
                         settings: FillSettings) -> List[PlacementPoint]:
        """
        Feature 9: Handle duplicates based on settings.
        """
        if settings.duplicate_action == "delete":
            _, unique_indices = self.detect_duplicates(placements, settings)
            return [placements[i] for i in unique_indices]
        
        # "select" or other - keep all
        return placements

    def _apply_overlap_removal(self, placements: List[PlacementPoint], 
                               settings: FillSettings) -> List[PlacementPoint]:
        """
        Feature 6: Fix stones overlapping using improved collision detection.
        """
        if settings.overlap_mode == OverlapMode.COLLISION_DETECT:
            return self._remove_collisions(placements)
        elif settings.overlap_mode == OverlapMode.REMOVE_DUPLICATES:
            return self._remove_overlaps(placements)
        
        return placements

    def align_distribute(self, elements: List, settings: FillSettings, 
                        along_curve: bool = True) -> List[PlacementPoint]:
        """
        Feature 8: Align and distribute stones along curve or without curve.
        """
        if not elements:
            return []

        placements = []

        if along_curve and self._curve_segments:
            # Along curve distribution
            total_length = corel.get_curve_total_length(self._curve_segments)
            
            if settings.distribute_enabled:
                # Evenly distribute
                spacing = total_length / (settings.distribute_count - 1) if settings.distribute_count > 1 else total_length
                
                for i in range(settings.distribute_count):
                    distance = i * spacing
                    point, tangent = corel.get_point_on_curve(self._curve_segments, distance)
                    
                    placements.append(PlacementPoint(
                        position=point,
                        rotation=tangent,
                        scale=1.0,
                        element_index=0
                    ))
        else:
            # Freeform distribution - distribute in a line
            if len(elements) < 2:
                return placements
            
            # Get bounds of elements
            bounds_list = []
            for elem in elements:
                b = corel.get_shape_bounds(elem)
                bounds_list.append(b)
            
            # Calculate start and end points
            start_x = min(b.left for b in bounds_list)
            end_x = max(b.right for b in bounds_list)
            center_y = sum(b.center.y for b in bounds_list) / len(bounds_list)
            
            spacing = (end_x - start_x) / (len(elements) - 1) if len(elements) > 1 else 0
            
            for i, elem in enumerate(elements):
                x = start_x + i * spacing
                placements.append(PlacementPoint(
                    position=Point(x, center_y),
                    rotation=0,
                    scale=1.0,
                    element_index=0
                ))

        return placements

    def replace_shapes_with_stones(self, shapes: List, settings: FillSettings) -> List[PlacementPoint]:
        """
        Feature 7: Replace shapes with stones of specified sizes.
        """
        if not shapes or not self._fill_elements:
            return []

        placements = []
        
        for i, shape in enumerate(shapes):
            bounds = corel.get_shape_bounds(shape)
            center = bounds.center
            
            # Calculate scale to match desired replacement size
            desired_size = settings.replacement_element_size
            current_size = max(bounds.width, bounds.height)
            scale = desired_size / current_size if current_size > 0 else 1.0
            
            element_index = self._get_element_index(settings, i)
            
            placements.append(PlacementPoint(
                position=center,
                rotation=0,
                scale=scale,
                element_index=element_index
            ))

        logger.info(f"Shape replacement: {len(placements)} placements")
        return placements

    def clever_trim(self, line1, line2) -> Optional[Point]:
        """
        Feature 10: Clever trim - find center line between two lines.
        
        Args:
            line1: First line (shape or curve)
            line2: Second line (shape or curve)
            
        Returns:
            Center point between the two lines
        """
        try:
            # Get both curves
            segments1 = corel.get_curve_path(line1)
            segments2 = corel.get_curve_path(line2)
            
            if not segments1 or not segments2:
                return None
            
            # Get start and end points from both lines
            start1, _ = corel.get_point_on_curve(segments1, 0)
            end1, _ = corel.get_point_on_curve(segments1, corel.get_curve_total_length(segments1))
            
            start2, _ = corel.get_point_on_curve(segments2, 0)
            end2, _ = corel.get_point_on_curve(segments2, corel.get_curve_total_length(segments2))
            
            # Calculate center points
            center_start = Point((start1.x + start2.x) / 2, (start1.y + start2.y) / 2)
            center_end = Point((end1.x + end2.x) / 2, (end1.y + end2.y) / 2)
            
            # Create the center line (for trimming)
            center_line = corel.create_line(center_start, center_end)
            
            return center_line
            
        except Exception as e:
            logger.error(f"Clever trim failed: {e}")
            return None

    def trim_to_center(self, shapes: List, reference_line) -> List:
        """
        Feature 10: Trim shapes to center of two lines.
        """
        try:
            # Get reference line segments
            ref_segments = corel.get_curve_path(reference_line)
            if not ref_segments:
                return shapes
            
            ref_length = corel.get_curve_total_length(ref_segments)
            
            trimmed = []
            
            for shape in shapes:
                bounds = corel.get_shape_bounds(shape)
                center = bounds.center
                
                # Find closest point on reference line
                closest_dist = float('inf')
                closest_point = None
                
                for t in [0, ref_length]:
                    pt, _ = corel.get_point_on_curve(ref_segments, t)
                    dist = center.distance_to(pt)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest_point = pt
                
                if closest_point:
                    # Move shape to center
                    offset_x = closest_point.x - center.x
                    offset_y = closest_point.y - center.y
                    corel.move_shape(shape, offset_x, offset_y)
                    trimmed.append(shape)
            
            return trimmed
            
        except Exception as e:
            logger.error(f"Trim to center failed: {e}")
            return shapes
