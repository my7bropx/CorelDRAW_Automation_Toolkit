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

        # Get element sizes
        elem_sizes = []
        for elem in self._fill_elements:
            bounds = corel.get_shape_bounds(elem)
            size = max(bounds.width, bounds.height)
            elem_sizes.append(size)

        # Filter out collisions
        filtered = [placements[0]]

        for i in range(1, len(placements)):
            current = placements[i]
            prev = filtered[-1]

            # Get sizes
            current_size = elem_sizes[current.element_index] * current.scale
            prev_size = elem_sizes[prev.element_index] * prev.scale

            # Check distance
            min_distance = (current_size + prev_size) / 2
            actual_distance = prev.position.distance_to(current.position)

            if actual_distance >= min_distance * 0.9:  # 90% threshold
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

        cell_size = max_size
        grid: Dict[Tuple[int, int], List[int]] = {}
        kept: List[PlacementPoint] = []

        def _cell_key(p: Point) -> Tuple[int, int]:
            return (int(p.x // cell_size), int(p.y // cell_size))

        for p in placements:
            size = elem_sizes[p.element_index] * p.scale
            cx, cy = _cell_key(p.position)
            overlap = False
            for gx in (cx - 1, cx, cx + 1):
                for gy in (cy - 1, cy, cy + 1):
                    for idx in grid.get((gx, gy), []):
                        other = kept[idx]
                        other_size = elem_sizes[other.element_index] * other.scale
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

    def execute_fill(self, placements: List[PlacementPoint] = None,
                    settings: FillSettings = None) -> List[Any]:
        """
        Execute the fill operation in CorelDRAW.

        Args:
            placements: Pre-calculated placements (optional).
            settings: Fill settings (required if placements not provided).

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

        try:
            with corel.optimization_mode(), corel.command_group("Curve Fill"):
                created_shapes = []

                for i, placement in enumerate(placements):
                    # Get the element to duplicate
                    element = self._fill_elements[placement.element_index]

                    # Duplicate element
                    new_shape = corel.duplicate_shape(element)

                    # Apply transformations
                    # 1. Scale if needed
                    if placement.scale != 1.0:
                        corel.scale_shape(new_shape, placement.scale)

                    # 2. Move to position
                    center = corel.get_shape_center(new_shape)
                    offset_x = placement.position.x - center.x
                    offset_y = placement.position.y - center.y
                    new_shape.Move(offset_x, offset_y)

                    # 3. Rotate
                    if placement.rotation != 0:
                        corel.rotate_shape(
                            new_shape,
                            placement.rotation,
                            placement.position.x,
                            placement.position.y
                        )

                    created_shapes.append(new_shape)

                    # Report progress
                    if (i + 1) % 10 == 0:
                        logger.debug(f"Placed {i + 1}/{len(placements)} elements")

                self._placed_elements = created_shapes
                logger.info(f"Successfully placed {len(created_shapes)} elements.")

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
                # Remove excess elements
                for i in range(new_count, current_count):
                    corel.delete_shape(self._placed_elements[i])
                self._placed_elements = self._placed_elements[:new_count]

            else:
                # Add more elements - recalculate placements
                settings = self._last_settings
                settings.element_count = new_count
                new_placements = self.calculate_placements(settings)

                # Remove old elements
                for shape in self._placed_elements:
                    corel.delete_shape(shape)

                # Create new elements
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
