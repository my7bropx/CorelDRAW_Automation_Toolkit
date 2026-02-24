"""
Rhinestone Engine
Core algorithms for rhinestone design automation.
"""

import logging
import math
import random
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from PIL import Image

from ...core.corel_interface import (
    corel, Point, BoundingBox, NoSelectionError
)

logger = logging.getLogger(__name__)


# Standard rhinestone sizes (diameter in mm)
STONE_SIZES = {
    'SS2': 0.8,
    'SS3': 1.0,
    'SS4': 1.2,
    'SS5': 1.5,
    'SS6': 2.0,
    'SS8': 2.4,
    'SS10': 2.8,
    'SS12': 3.1,
    'SS14': 3.5,
    'SS16': 3.9,
    'SS18': 4.3,
    'SS20': 4.7,
    'SS30': 6.3,
    'SS34': 7.1,
    'SS40': 8.4,
    'SS48': 11.0,
}


class PatternType(Enum):
    """Rhinestone fill pattern types - Hexagonal Grid and Random Fill only."""
    HEXAGONAL = "hexagonal"
    RANDOM = "random"


@dataclass
class RhinestonePlacement:
    """Represents a single rhinestone placement."""
    x: float
    y: float
    stone_size: str
    rotation: float = 0.0
    color: str = ""
    element_index: Optional[int] = None
    diameter: Optional[float] = None


@dataclass
class RhinestoneSettings:
    """Settings for rhinestone filling."""
    stone_size: str = "SS10"
    stone_sizes: List[str] = None  # Multiple sizes for mixed fills
    size_distribution: List[float] = None  # Percentage for each size
    pattern: PatternType = PatternType.HEXAGONAL
    density: float = 0.85
    spacing: float = 0.0  # Additional spacing in mm
    min_gap: float = 0.5
    gap_optimization: bool = True
    rotation: float = 0.0
    random_rotation: bool = False
    outline_offset: float = 0.0
    fill_interior: bool = True
    use_selected_shapes: bool = True  # Use shapes as they are (don't resize)
    use_element_size: bool = True  # Use selected element size for spacing
    remove_overlaps: bool = True  # Post-process to remove overlaps
    
    def __post_init__(self):
        if self.stone_sizes is None:
            self.stone_sizes = [self.stone_size]
        if self.size_distribution is None:
            self.size_distribution = [1.0] * len(self.stone_sizes)


class RhinestoneEngine:
    """Engine for rhinestone design operations."""

    def __init__(self):
        self._placements: List[RhinestonePlacement] = []
        self._stone_count = 0

    @property
    def placements(self) -> List[RhinestonePlacement]:
        """Get list of stone placements."""
        return self._placements

    @property
    def stone_count(self) -> int:
        """Get total stone count."""
        return self._stone_count

    def clear(self):
        """Clear all placements."""
        self._placements.clear()
        self._stone_count = 0

    def get_stone_diameter(self, stone_size: str) -> float:
        """Get diameter in mm for a stone size."""
        return STONE_SIZES.get(stone_size, 2.8)

    def get_random_stone_size(self, settings: RhinestoneSettings) -> str:
        """Get a random stone size based on distribution."""
        if not settings.stone_sizes or len(settings.stone_sizes) == 1:
            return settings.stone_sizes[0] if settings.stone_sizes else settings.stone_size
        
        # Normalize distribution
        total = sum(settings.size_distribution)
        if total == 0:
            return settings.stone_sizes[0]
        
        # Random selection based on distribution
        r = random.random() * total
        cumulative = 0
        
        for i, size in enumerate(settings.stone_sizes):
            cumulative += settings.size_distribution[i]
            if r <= cumulative:
                return size
        
        return settings.stone_sizes[-1]

    def _get_element_diameters(self, element_shapes) -> List[float]:
        """Get effective diameters (mm) from selected element shapes."""
        if not element_shapes:
            return []
        diameters = []
        for shape in element_shapes:
            try:
                w = getattr(shape, 'SizeWidth', 0) or 0
                h = getattr(shape, 'SizeHeight', 0) or 0
                d = (w + h) / 2 if (w > 0 or h > 0) else 0
                if d > 0:
                    diameters.append(d)
            except Exception:
                continue
        return diameters

    def _average_diameter_from_settings(self, settings: RhinestoneSettings) -> float:
        """Weighted average diameter from stone size list."""
        if not settings or not settings.stone_sizes:
            return 0.0
        weights = settings.size_distribution or [1.0] * len(settings.stone_sizes)
        total = sum(weights) or 1.0
        acc = 0.0
        for size, w in zip(settings.stone_sizes, weights):
            acc += self.get_stone_diameter(size) * w
        return acc / total

    def _nearest_stone_size(self, diameter: float) -> str:
        """Find nearest standard stone size name for a given diameter."""
        if diameter <= 0:
            return "SS10"
        best_name = None
        best_diff = None
        for name, size in STONE_SIZES.items():
            diff = abs(size - diameter)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best_name = name
        return best_name or "SS10"

    def _remove_overlaps(
        self,
        placements: List[RhinestonePlacement],
        min_gap: float,
    ) -> List[RhinestonePlacement]:
        """Remove overlapping placements using a spatial hash (VBA-style overlap pass)."""
        if not placements:
            return placements
        # Determine cell size from maximum diameter
        max_diameter = 0.0
        for p in placements:
            d = p.diameter if p.diameter else self.get_stone_diameter(p.stone_size)
            if d > max_diameter:
                max_diameter = d
        cell_size = max_diameter + max(min_gap, 0.0)
        if cell_size <= 0:
            return placements

        grid: Dict[Tuple[int, int], List[int]] = {}
        kept: List[RhinestonePlacement] = []

        def _cell_key(x: float, y: float) -> Tuple[int, int]:
            return (int(x // cell_size), int(y // cell_size))

        for p in placements:
            d = p.diameter if p.diameter else self.get_stone_diameter(p.stone_size)
            r = d / 2
            cx, cy = _cell_key(p.x, p.y)
            overlap = False
            for gx in (cx - 1, cx, cx + 1):
                for gy in (cy - 1, cy, cy + 1):
                    for idx in grid.get((gx, gy), []):
                        other = kept[idx]
                        od = other.diameter if other.diameter else self.get_stone_diameter(other.stone_size)
                        min_dist = (d + od) / 2 + min_gap
                        dx = p.x - other.x
                        dy = p.y - other.y
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

    def calculate_hexagonal_grid(
        self,
        bounds,
        stone_size: str,
        density: float,
        min_gap: float,
        settings: RhinestoneSettings = None,
        rows: int = None,
        cols: int = None,
        stagger: bool = True,
        stagger_amount: float = 50,
        rotation: float = 0,
        offset_x: float = 0,
        offset_y: float = 0,
        edge_margin: float = 1.0,
        clip_to_container: bool = True,
        center_grid: bool = True,
        horizontal_spacing: float = 0,
        vertical_spacing: float = 0,
        scale_factor: float = 1.0,
        container_shape=None,
        element_shapes=None
    ) -> List[RhinestonePlacement]:
        """
        Calculate hexagonal grid pattern for filling an area.
        This is the most efficient pattern for rhinestones.
        
        Args:
            bounds: Bounding box of the container
            stone_size: Size code (e.g., 'SS10')
            density: Fill density (0.1 to 1.0)
            min_gap: Minimum gap between stones
            settings: RhinestoneSettings object with additional options
            rows: Number of rows (None for auto-calculate)
            cols: Number of columns (None for auto-calculate)
            stagger: Enable stagger for honeycomb pattern
            stagger_amount: Stagger percentage (50% = perfect honeycomb)
            rotation: Grid rotation in degrees
            offset_x: Horizontal offset from container edge
            offset_y: Vertical offset from container edge
            edge_margin: Margin from container edges
            clip_to_container: Only place stones within container bounds
            center_grid: Center the grid pattern in container
            horizontal_spacing: Additional horizontal spacing between stones
            vertical_spacing: Additional vertical spacing between stones
            scale_factor: Overall spacing scale factor (1.0 = normal)
            container_shape: CorelDRAW shape object for boundary checking
        """
        placements = []
        density = max(0.1, min(float(density or 1.0), 1.0))
        
        # Get bounding box values
        if hasattr(bounds, 'x'):
            orig_min_x, orig_min_y = bounds.x, bounds.y
            orig_width, orig_height = bounds.width, bounds.height
        else:
            orig_min_x, orig_min_y = bounds[0], bounds[1]
            orig_width, orig_height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        
        # Apply edge margin
        min_x = orig_min_x + edge_margin
        min_y = orig_min_y + edge_margin
        width = max(0, orig_width - 2 * edge_margin)
        height = max(0, orig_height - 2 * edge_margin)
        
        # Apply offset
        min_x += offset_x
        min_y += offset_y
        
        stone_diameter = self.get_stone_diameter(stone_size)
        element_diameters = []
        if settings and settings.use_selected_shapes:
            element_diameters = self._get_element_diameters(element_shapes)
        if element_diameters and settings and settings.use_element_size:
            avg_element_diameter = sum(element_diameters) / len(element_diameters)
            diameter = max(stone_diameter, avg_element_diameter) if stone_diameter > 0 else avg_element_diameter
        elif settings and settings.stone_sizes and len(settings.stone_sizes) > 1:
            diameter = self._average_diameter_from_settings(settings)
        else:
            diameter = stone_diameter
        radius = diameter / 2
        
        # Calculate base spacing with scale factor
        base_spacing = diameter + min_gap
        if settings and settings.spacing > 0:
            base_spacing += settings.spacing
        base_spacing *= scale_factor

        # Apply spacing adjustments
        h_spacing = base_spacing + horizontal_spacing
        row_height = (base_spacing * math.sqrt(3) / 2) + vertical_spacing

        # Adjust spacing for density (lower density -> larger spacing)
        effective_h_spacing = h_spacing / density
        effective_row_height = row_height / density
        
        # Calculate rows and columns if not provided
        if rows is None:
            rows = int(height / effective_row_height) + 2  # Extra rows for centering
        if cols is None:
            cols = int(width / effective_h_spacing) + 2  # Extra columns for centering
        
        # Calculate grid dimensions for centering
        stagger_offset = effective_h_spacing * (stagger_amount / 100) if stagger else 0
        grid_width = (cols - 1) * effective_h_spacing + stagger_offset
        grid_height = (rows - 1) * effective_row_height
        
        # Calculate centering offsets
        if center_grid:
            center_offset_x = (width - grid_width) / 2
            center_offset_y = (height - grid_height) / 2
        else:
            center_offset_x = 0
            center_offset_y = 0
        
        # Apply rotation
        rotation_rad = math.radians(rotation)
        
        # Container bounds for clipping
        container_min_x = orig_min_x + edge_margin
        container_max_x = orig_min_x + orig_width - edge_margin
        container_min_y = orig_min_y + edge_margin
        container_max_y = orig_min_y + orig_height - edge_margin
        
        # Center of container for rotation
        center_x = orig_min_x + orig_width / 2
        center_y = orig_min_y + orig_height / 2
        
        for row in range(rows):
            # Calculate stagger offset for honeycomb pattern
            if stagger:
                stagger_offset = (row % 2) * effective_h_spacing * (stagger_amount / 100)
            else:
                stagger_offset = 0
            
            base_y = min_y + center_offset_y + row * effective_row_height
            
            for col in range(cols):
                base_x = min_x + center_offset_x + col * effective_h_spacing + stagger_offset
                
                # Apply rotation around container center
                if rotation != 0:
                    dx = base_x - center_x
                    dy = base_y - center_y
                    x = center_x + dx * math.cos(rotation_rad) - dy * math.sin(rotation_rad)
                    y = center_y + dx * math.sin(rotation_rad) + dy * math.cos(rotation_rad)
                else:
                    x = base_x
                    y = base_y
                
                # Determine actual stone size or element diameter
                actual_size = stone_size
                element_index = None
                if element_diameters:
                    element_index = len(placements) % len(element_diameters)
                    actual_diameter = element_diameters[element_index]
                    actual_size = self._nearest_stone_size(actual_diameter)
                else:
                    if settings and len(settings.stone_sizes) > 1:
                        actual_size = self.get_random_stone_size(settings)
                    actual_diameter = self.get_stone_diameter(actual_size)
                stone_radius = actual_diameter / 2

                # Clip to container bounds if enabled
                if clip_to_container:
                    # First, clip to bounding box
                    if (x - stone_radius < container_min_x or
                        x + stone_radius > container_max_x or
                        y - stone_radius < container_min_y or
                        y + stone_radius > container_max_y):
                        continue
                    # Then, clip to actual shape if provided
                    if container_shape and not corel.is_point_in_shape(x, y, container_shape):
                        continue
                
                # Check collision if gap optimization is enabled (skip if we do post-process)
                can_place = True
                if settings and settings.gap_optimization and not settings.remove_overlaps:
                    for p in placements:
                        pd = p.diameter if p.diameter else self.get_stone_diameter(p.stone_size)
                        dist = math.sqrt((x - p.x) ** 2 + (y - p.y) ** 2)
                        min_dist = (actual_diameter + pd) / 2 + min_gap
                        if dist < min_dist:
                            can_place = False
                            break

                if can_place:
                    final_rotation = 0
                    if settings and settings.random_rotation:
                        final_rotation = random.uniform(0, 360)
                    elif settings:
                        final_rotation = settings.rotation
                    
                    placements.append(RhinestonePlacement(
                        x=x,
                        y=y,
                        stone_size=actual_size,
                        rotation=final_rotation,
                        element_index=element_index,
                        diameter=actual_diameter
                    ))

        if settings and settings.remove_overlaps:
            placements = self._remove_overlaps(placements, min_gap)

        self._placements = placements
        self._stone_count = len(placements)
        return placements

    def calculate_square_grid(
        self,
        bounds: BoundingBox,
        stone_size: str,
        density: float,
        min_gap: float
    ) -> List[RhinestonePlacement]:
        """Calculate square grid pattern."""
        placements = []
        
        diameter = self.get_stone_diameter(stone_size)
        spacing = diameter + min_gap
        
        # Adjust for density
        effective_spacing = spacing / density
        
        min_x, min_y = bounds.x, bounds.y
        max_x, max_y = bounds.x + bounds.width, bounds.y + bounds.height
        
        y = min_y
        while y < max_y:
            x = min_x
            while x < max_x:
                if self._is_point_in_shape(x, y):
                    placements.append(RhinestonePlacement(
                        x=x,
                        y=y,
                        stone_size=stone_size
                    ))
                x += effective_spacing
            y += effective_spacing
        
        self._placements = placements
        self._stone_count = len(placements)
        return placements

    def calculate_circular_grid(
        self,
        bounds: BoundingBox,
        stone_size: str,
        density: float,
        min_gap: float
    ) -> List[RhinestonePlacement]:
        """Calculate circular/radial pattern from center."""
        placements = []
        
        diameter = self.get_stone_diameter(stone_size)
        spacing = diameter + min_gap
        effective_spacing = spacing / density
        
        cx = bounds.x + bounds.width / 2
        cy = bounds.y + bounds.height / 2
        max_radius = min(bounds.width, bounds.height) / 2
        
        radius = 0
        angle = 0
        
        while radius < max_radius:
            num_stones = max(1, int(2 * math.pi * radius / effective_spacing))
            
            for i in range(num_stones):
                angle = (2 * math.pi * i) / num_stones
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                
                if self._is_point_in_shape(x, y):
                    placements.append(RhinestonePlacement(
                        x=x,
                        y=y,
                        stone_size=stone_size,
                        rotation=math.degrees(angle)
                    ))
            
            radius += effective_spacing
        
        self._placements = placements
        self._stone_count = len(placements)
        return placements

    def calculate_outline(
        self,
        bounds: BoundingBox,
        stone_size: str,
        offset: float,
        min_gap: float
    ) -> List[RhinestonePlacement]:
        """Calculate outline pattern along shape boundary."""
        placements = []
        
        diameter = self.get_stone_diameter(stone_size)
        spacing = diameter + min_gap
        
        # Get curve points from CorelDRAW
        if not corel.is_connected:
            logger.warning("Not connected to CorelDRAW")
            return placements
        
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                logger.warning("No selection for outline")
                return placements
            
            shape = selection.Item(1)
            
            # Get curve segments
            curve_points = self._get_curve_points(shape, spacing)
            
            for point in curve_points:
                placements.append(RhinestonePlacement(
                    x=point[0],
                    y=point[1],
                    stone_size=stone_size
                ))
                
        except Exception as e:
            logger.error(f"Error calculating outline: {e}")
        
        self._placements = placements
        self._stone_count = len(placements)
        return placements

    def calculate_random_scatter(
        self,
        bounds,
        stone_size: str,
        density: float,
        min_gap: float,
        settings: RhinestoneSettings = None,
        count: int = None,
        seed: int = None,
        random_density: float = None,
        element_shapes=None,
        container_shape=None
    ) -> List[RhinestonePlacement]:
        """Calculate random scatter pattern."""
        placements = []
        
        # Set random seed if provided
        if seed is not None:
            random.seed(seed)
        
        # Get bounding box values
        if hasattr(bounds, 'x'):
            min_x, min_y = bounds.x, bounds.y
            width, height = bounds.width, bounds.height
        else:
            min_x, min_y = bounds[0], bounds[1]
            width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        
        stone_diameter = self.get_stone_diameter(stone_size)
        element_diameters = []
        if settings and settings.use_selected_shapes:
            element_diameters = self._get_element_diameters(element_shapes)
        if element_diameters and settings and settings.use_element_size:
            avg_element_diameter = sum(element_diameters) / len(element_diameters)
            diameter = max(stone_diameter, avg_element_diameter) if stone_diameter > 0 else avg_element_diameter
        elif settings and settings.stone_sizes and len(settings.stone_sizes) > 1:
            diameter = self._average_diameter_from_settings(settings)
        else:
            diameter = stone_diameter
        area = width * height
        stone_area = math.pi * (diameter / 2) ** 2
        
        # Use provided density or settings density
        eff_density = random_density if random_density is not None else density
        
        # Calculate max stones based on area and density
        if count is not None:
            max_stones = count
        else:
            max_stones = int((area * eff_density) / stone_area)
        max_stones = min(max_stones, 10000)  # Cap at 10000
        
        # Spatial hash for faster overlap checks
        max_diameter = max(element_diameters) if element_diameters else diameter
        cell_size = max_diameter + max(min_gap, 0.0)
        grid: Dict[Tuple[int, int], List[int]] = {}

        def _cell_key(px: float, py: float) -> Tuple[int, int]:
            return (int(px // cell_size), int(py // cell_size))

        attempts = 0
        max_attempts = max_stones * 10

        while len(placements) < max_stones and attempts < max_attempts:
            x = random.uniform(min_x, min_x + width)
            y = random.uniform(min_y, min_y + height)

            actual_size = stone_size
            element_index = None
            if element_diameters:
                element_index = len(placements) % len(element_diameters)
                actual_diameter = element_diameters[element_index]
                actual_size = self._nearest_stone_size(actual_diameter)
            else:
                if settings and len(settings.stone_sizes) > 1:
                    actual_size = self.get_random_stone_size(settings)
                actual_diameter = self.get_stone_diameter(actual_size)

            # Check minimum distance from other placements
            too_close = False
            if container_shape and not corel.is_point_in_shape(x, y, container_shape):
                too_close = True
            if cell_size > 0:
                cx, cy = _cell_key(x, y)
                for gx in (cx - 1, cx, cx + 1):
                    for gy in (cy - 1, cy, cy + 1):
                        for idx in grid.get((gx, gy), []):
                            p = placements[idx]
                            pd = p.diameter if p.diameter else self.get_stone_diameter(p.stone_size)
                            min_dist = (actual_diameter + pd) / 2 + min_gap
                            dx = x - p.x
                            dy = y - p.y
                            if (dx * dx + dy * dy) < (min_dist * min_dist):
                                too_close = True
                                break
                        if too_close:
                            break
                    if too_close:
                        break

            if not too_close:
                final_rotation = 0
                if settings and settings.random_rotation:
                    final_rotation = random.uniform(0, 360)
                elif settings:
                    final_rotation = settings.rotation

                placements.append(RhinestonePlacement(
                    x=x,
                    y=y,
                    stone_size=actual_size,
                    rotation=final_rotation,
                    element_index=element_index,
                    diameter=actual_diameter
                ))
                if cell_size > 0:
                    grid.setdefault(_cell_key(x, y), []).append(len(placements) - 1)

            attempts += 1
        
        if settings and settings.remove_overlaps:
            placements = self._remove_overlaps(placements, min_gap)

        self._placements = placements
        self._stone_count = len(placements)
        return placements

    def calculate_pixel_grid(
        self,
        bounds,
        stone_size: str,
        density: float,
        min_gap: float,
        settings=None
    ) -> List[RhinestonePlacement]:
        """
        Calculate pixel-art style grid pattern.
        Uniformly sized nodes in symmetrical grid layout.
        Like Minecraft pixel art but with circles/stones.
        """
        placements = []
        
        # Get bounds
        try:
            min_x = bounds.x
            min_y = bounds.y
            width = bounds.width
            height = bounds.height
        except:
            return placements
        
        diameter = self.get_stone_diameter(stone_size)
        spacing = diameter + min_gap
        
        # Adjust for density (lower density = larger gaps)
        if density < 1.0:
            spacing = spacing / density
        
        # Calculate grid points
        start_x = min_x + spacing / 2
        start_y = min_y + spacing / 2
        
        x = start_x
        row = 0
        
        while x < min_x + width:
            y = start_y
            
            while y < min_y + height:
                # Check bounds
                if x >= min_x and x <= min_x + width and y >= min_y and y <= min_y + height:
                    # Random rotation for pixel-art effect (optional)
                    rotation = 0
                    if settings and settings.random_rotation:
                        rotation = random.choice([0, 90, 180, 270])
                    elif settings:
                        rotation = settings.rotation
                    
                    placements.append(RhinestonePlacement(
                        x=x,
                        y=y,
                        stone_size=stone_size,
                        rotation=rotation
                    ))
                
                y += spacing
            
            # Offset every other row for brick/pixel effect
            if row % 2 == 1:
                x += spacing / 2
                # Check if still in bounds
                if x > min_x + width:
                    break
            
            x += spacing
            row += 1
        
        self._placements = placements
        self._stone_count = len(placements)
        return placements

    def calculate_image_map(
        self,
        image_path: Path,
        bounds,
        settings: RhinestoneSettings,
        threshold: float = 0.5,
        invert: bool = False,
        alpha_threshold: float = 0.1,
        keep_aspect: bool = True,
        size_mode: str = "primary",
    ) -> List[RhinestonePlacement]:
        """Convert an image into stone placements within bounds."""
        placements: List[RhinestonePlacement] = []

        if not image_path or not image_path.exists():
            logger.warning("Image path not found for image mapping")
            return placements

        try:
            img = Image.open(image_path).convert("RGBA")
        except Exception as e:
            logger.error(f"Failed to open image: {e}")
            return placements

        img_w, img_h = img.size
        if img_w <= 0 or img_h <= 0:
            return placements

        try:
            min_x = bounds.x
            min_y = bounds.y
            out_w = bounds.width
            out_h = bounds.height
        except Exception:
            return placements

        if out_w <= 0 or out_h <= 0:
            return placements

        scale_x = out_w / img_w
        scale_y = out_h / img_h

        if keep_aspect:
            scale = min(scale_x, scale_y)
            render_w = img_w * scale
            render_h = img_h * scale
            pad_x = (out_w - render_w) / 2
            pad_y = (out_h - render_h) / 2
            mm_per_px_x = scale
            mm_per_px_y = scale
        else:
            render_w = out_w
            render_h = out_h
            pad_x = 0
            pad_y = 0
            mm_per_px_x = scale_x
            mm_per_px_y = scale_y

        # Determine base spacing from stone sizes
        if settings and settings.stone_sizes and len(settings.stone_sizes) > 1:
            base_diameter = self._average_diameter_from_settings(settings)
        else:
            base_diameter = self.get_stone_diameter(settings.stone_size)

        base_spacing = max(base_diameter + settings.min_gap + settings.spacing, 0.1)
        density = settings.density if settings and settings.density > 0 else 1.0
        spacing = base_spacing / max(density, 0.1)

        # Determine size order for brightness mapping
        size_order = []
        if settings and settings.stone_sizes:
            size_order = sorted(settings.stone_sizes, key=self.get_stone_diameter)

        pixels = img.load()

        start_x = min_x + pad_x + spacing / 2
        start_y = min_y + pad_y + spacing / 2

        y = start_y
        while y < min_y + pad_y + render_h:
            x = start_x
            while x < min_x + pad_x + render_w:
                px = int((x - min_x - pad_x) / mm_per_px_x) if mm_per_px_x > 0 else 0
                py = int((y - min_y - pad_y) / mm_per_px_y) if mm_per_px_y > 0 else 0

                if 0 <= px < img_w and 0 <= py < img_h:
                    r, g, b, a = pixels[px, py]
                    alpha = a / 255.0
                    if alpha_threshold > 0 and alpha < alpha_threshold:
                        x += spacing
                        continue

                    brightness = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
                    place = brightness >= threshold if invert else brightness <= threshold

                    if place:
                        if size_mode == "brightness" and len(size_order) > 1:
                            idx = int((1.0 - brightness) * (len(size_order) - 1) + 0.5)
                            idx = max(0, min(len(size_order) - 1, idx))
                            size_name = size_order[idx]
                        else:
                            size_name = settings.stone_size

                        diameter = self.get_stone_diameter(size_name)
                        placements.append(RhinestonePlacement(
                            x=x,
                            y=y,
                            stone_size=size_name,
                            rotation=settings.rotation if settings else 0.0,
                            diameter=diameter,
                        ))

                x += spacing
            y += spacing

        if settings and settings.remove_overlaps:
            placements = self._remove_overlaps(placements, settings.min_gap)

        self._placements = placements
        self._stone_count = len(placements)
        return placements

    def _is_point_in_shape(self, x: float, y: float) -> bool:
        """Check if a point is inside the selected shape."""
        if not corel.is_connected:
            return True  # Assume inside if not connected
        
        try:
            # Use CorelDRAW's geometry check
            return corel.is_point_in_shape(x, y)
        except Exception:
            return True  # Default to inside

    def _get_curve_points(self, shape, spacing: float) -> List[Tuple[float, float]]:
        """Extract points along a curve/path."""
        points = []
        
        try:
            # Get curve geometry
            curve = shape.ConvertToCurve()
            if curve:
                # Get nodes and extract positions
                nodes = curve.Nodes
                for i in range(nodes.Count):
                    node = nodes.Item(i + 1)
                    if node:
                        point = node.Point
                        points.append((point.x, point.y))
                        
        except Exception as e:
            logger.error(f"Error getting curve points: {e}")
        
        return points

    def place_stones_in_coreldraw(self, settings: RhinestoneSettings, element_shapes=None, bounds=None):
        """
        Place the calculated stones in CorelDRAW inside the container bounds.
        
        Args:
            settings: RhinestoneSettings object
            element_shapes: List of element shapes to use as templates
            bounds: Container bounds for positioning
        """
        if not corel.is_connected:
            logger.warning("Not connected to CorelDRAW")
            return []
        
        if not self._placements:
            logger.warning("No placements to place")
            return []
        
        placed_shapes = []
        
        try:
            with corel.optimization_mode(), corel.command_group("Rhinestone Fill"):
                # Use provided element shapes or get source stone
                source_shapes = element_shapes if element_shapes else []

                # If no element shapes provided, create a circle as fallback
                if not source_shapes:
                    source_shape = self._get_source_stone_shape(settings.stone_size)
                    if source_shape:
                        source_shapes = [source_shape]

                if not source_shapes:
                    logger.error("No source shapes available")
                    return []

                # Get element dimensions for accurate placement
                element_dims = []
                for shape in source_shapes:
                    try:
                        w = getattr(shape, 'SizeWidth', 0) or 0
                        h = getattr(shape, 'SizeHeight', 0) or 0
                        cx = getattr(shape, 'CenterX', 0) or 0
                        cy = getattr(shape, 'CenterY', 0) or 0
                        element_dims.append({'width': w, 'height': h, 'cx': cx, 'cy': cy})
                    except:
                        element_dims.append({'width': 0, 'height': 0, 'cx': 0, 'cy': 0})

                # Place each stone at calculated positions inside container
                for i, placement in enumerate(self._placements):
                    try:
                        # Use element index if provided, otherwise cycle
                        if placement.element_index is not None:
                            source_idx = placement.element_index % len(source_shapes)
                        else:
                            source_idx = i % len(source_shapes)
                        source = source_shapes[source_idx]
                        dims = element_dims[source_idx]

                        # Clone the source shape
                        new_shape = source.Duplicate()

                        desired_diameter = placement.diameter or self.get_stone_diameter(placement.stone_size)
                        base_size = (dims['width'] + dims['height']) / 2 if (dims['width'] > 0 or dims['height'] > 0) else 0
                        if desired_diameter > 0 and base_size > 0:
                            try:
                                new_shape.SizeWidth = desired_diameter
                                new_shape.SizeHeight = desired_diameter
                            except Exception:
                                try:
                                    scale_factor = desired_diameter / base_size
                                    new_shape.ScaleX = scale_factor
                                    new_shape.ScaleY = scale_factor
                                except Exception:
                                    pass

                        # Calculate offset from original position to target position
                        try:
                            cx = getattr(new_shape, 'CenterX', 0) or dims['cx']
                            cy = getattr(new_shape, 'CenterY', 0) or dims['cy']
                            dx = placement.x - cx
                            dy = placement.y - cy
                            new_shape.Move(dx, dy)
                        except Exception:
                            try:
                                new_shape.CenterX = placement.x
                                new_shape.CenterY = placement.y
                            except Exception:
                                new_shape.Move(placement.x, placement.y)

                        # Apply rotation if needed
                        if placement.rotation != 0:
                            new_shape.Rotate(placement.rotation)

                        placed_shapes.append(new_shape)

                    except Exception as e:
                        logger.error(f"Error placing stone {i}: {e}")

                # Group all placed stones for easier management
                if len(placed_shapes) > 1:
                    shapes = corel.app.CreateShapeRange()
                    for shape in placed_shapes:
                        shapes.Add(shape)
                    try:
                        shapes.Group()
                    except Exception as e:
                        logger.warning(f"Could not group shapes: {e}")

            logger.info(f"Placed {len(placed_shapes)} rhinestones inside container")

        except Exception as e:
            logger.error(f"Error placing stones: {e}")
        
        return placed_shapes

    def _get_source_stone_shape(self, stone_size: str):
        """Get or create a stone shape to use as template."""
        # In a full implementation, this would check for an existing
        # stone in the document or create a new circle
        if not corel.is_connected:
            return None
        
        try:
            # Create a circle of the appropriate size
            diameter = self.get_stone_diameter(stone_size)
            
            # For now, try to get selection as source
            selection = corel.get_selection()
            if selection.Count > 0:
                return selection.Item(1)
            
            # Create a new circle as fallback
            try:
                doc = corel.active_document
            except Exception:
                doc = None
            if doc:
                return doc.ActiveLayer.CreateCircle(0, 0, diameter / 2)
                
        except Exception as e:
            logger.error(f"Error getting source shape: {e}")
        
        return None

    def export_cut_file(
        self,
        filepath: Path,
        format: str = "csv"
    ) -> bool:
        """
        Export stone positions to a cut file.
        
        Supported formats:
        - csv: Simple CSV with x, y, size
        - gds: GD&T format for machines
        - json: JSON for software integration
        """
        if not self._placements:
            logger.warning("No placements to export")
            return False
        
        try:
            if format == "csv":
                return self._export_csv(filepath)
            elif format == "json":
                return self._export_json(filepath)
            elif format == "gds":
                return self._export_gds(filepath)
            else:
                logger.error(f"Unknown export format: {format}")
                return False
                
        except Exception as e:
            logger.error(f"Error exporting cut file: {e}")
            return False

    def _export_csv(self, filepath: Path) -> bool:
        """Export to CSV format."""
        with open(filepath, 'w') as f:
            f.write("Index,X,Y,Stone Size,Rotation\n")
            for i, p in enumerate(self._placements):
                f.write(f"{i+1},{p.x:.3f},{p.y:.3f},{p.stone_size},{p.rotation:.1f}\n")
        
        logger.info(f"Exported {len(self._placements)} stones to {filepath}")
        return True

    def _export_json(self, filepath: Path) -> bool:
        """Export to JSON format."""
        import json
        
        data = {
            "stone_count": self._stone_count,
            "stones": [
                {
                    "index": i + 1,
                    "x": p.x,
                    "y": p.y,
                    "size": p.stone_size,
                    "rotation": p.rotation
                }
                for i, p in enumerate(self._placements)
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported {len(self._placements)} stones to {filepath}")
        return True

    def _export_gds(self, filepath: Path) -> bool:
        """Export to GD&T (Gessmann) format for stone setting machines."""
        with open(filepath, 'w') as f:
            f.write("# Rhinestone Placement Data\n")
            f.write(f"# Total Stones: {self._stone_count}\n")
            f.write("# Format: X Y Size Rotation\n")
            f.write("#\n")
            
            for p in self._placements:
                diameter = p.diameter if p.diameter else self.get_stone_diameter(p.stone_size)
                f.write(f"{p.x:.3f} {p.y:.3f} {diameter:.2f} {p.rotation:.1f}\n")
        
        logger.info(f"Exported {len(self._placements)} stones to {filepath}")
        return True

    def generate_template(
        self,
        filepath: Path,
        page_width: float = 210.0,
        page_height: float = 297.0,
        show_labels: bool = True
    ) -> bool:
        """
        Generate a printable template PDF showing stone positions.
        """
        try:
            # Create a simple template in CorelDRAW
            if not corel.is_connected:
                logger.warning("Not connected to CorelDRAW")
                return False
            
            doc = corel.get_active_document()
            if not doc:
                logger.warning("No active document")
                return False
            
            # Create template page
            page = doc.Pages.Add()
            
            # Draw circles at each stone position
            layer = page.Layers.Add()
            layer.Name = "Stone Template"
            
            for p in self._placements:
                diameter = self.get_stone_diameter(p.stone_size)
                
                # Create circle
                circle = layer.CreateCircle(p.x, p.y, diameter / 2)
                
                # Add outline
                circle.OutlineWidth = 0.2
                
                if show_labels:
                    # Add text label with stone size
                    text = layer.CreateText(p.stone_size, p.x, p.y - diameter)
                    text.Size = 2
            
            # Save as template
            doc.SaveAs(str(filepath))
            
            logger.info(f"Generated template at {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating template: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the current design."""
        size_counts = {}
        for p in self._placements:
            size_counts[p.stone_size] = size_counts.get(p.stone_size, 0) + 1
        
        return {
            "total_stones": self._stone_count,
            "size_distribution": size_counts,
            "coverage_area": self._estimate_coverage()
        }

    def _estimate_coverage(self) -> float:
        """Estimate the coverage area in square mm."""
        total = 0.0
        for p in self._placements:
            diameter = p.diameter if p.diameter else self.get_stone_diameter(p.stone_size)
            area = math.pi * (diameter / 2) ** 2
            total += area
        return total
