"""
Distribution Strategies for Rhinestone Placement
Modular algorithms for spatial distribution of stones.
"""

import math
import random
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional, Callable
from dataclasses import dataclass
from PIL import Image
import numpy as np


@dataclass
class PlacementCandidate:
    """A candidate position for stone placement."""
    x: float
    y: float
    size_factor: float = 1.0
    rotation: float = 0.0
    color: str = ""
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BoundingBox:
    """Simple bounding box for calculations."""
    def __init__(self, x: float, y: float, width: float, height: float):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.left = x
        self.right = x + width
        self.top = y + height
        self.bottom = y
        self.center_x = x + width / 2
        self.center_y = y + height / 2


class DistributionStrategy(ABC):
    """Base class for all distribution strategies."""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._seed = self.config.get('seed', 42)
        random.seed(self._seed)
    
    @abstractmethod
    def generate(self, bounds: BoundingBox, stone_diameter: float) -> List[PlacementCandidate]:
        """
        Generate placement candidates.
        
        Args:
            bounds: Bounding box of the container
            stone_diameter: Diameter of the stone in mm
            
        Returns:
            List of placement candidates
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return strategy name."""
        pass
    
    def _random_rotation(self, enabled: bool, base_rotation: float = 0) -> float:
        """Generate random rotation if enabled."""
        if enabled:
            return random.uniform(0, 360)
        return base_rotation


class HexagonalStrategy(DistributionStrategy):
    """Hexagonal close-packing distribution."""
    
    def get_name(self) -> str:
        return "hexagonal"
    
    def generate(self, bounds: BoundingBox, stone_diameter: float) -> List[PlacementCandidate]:
        candidates = []
        
        # Config with defaults
        rows = self.config.get('rows', None)
        cols = self.config.get('cols', None)
        stagger = self.config.get('stagger', True)
        stagger_amount = self.config.get('stagger_amount', 50)  # percentage
        rotation = self.config.get('rotation', 0)
        offset_x = self.config.get('offset_x', 0)
        offset_y = self.config.get('offset_y', 0)
        edge_margin = self.config.get('edge_margin', 1.0)
        center_grid = self.config.get('center_grid', True)
        horizontal_spacing = self.config.get('horizontal_spacing', 0)
        vertical_spacing = self.config.get('vertical_spacing', 0)
        scale_factor = self.config.get('scale_factor', 1.0)
        
        # Apply edge margin
        min_x = bounds.left + edge_margin + offset_x
        min_y = bounds.bottom + edge_margin + offset_y
        width = bounds.width - 2 * edge_margin
        height = bounds.height - 2 * edge_margin
        
        if width <= 0 or height <= 0:
            return candidates
        
        # Base spacing
        base_spacing = stone_diameter * scale_factor
        h_spacing = base_spacing + horizontal_spacing
        v_spacing = base_spacing * math.sqrt(3) / 2 + vertical_spacing
        
        if stagger:
            h_spacing *= (1 + stagger_amount / 100)
        
        # Calculate rows/cols if not provided
        if rows is None:
            rows = max(1, int(height / v_spacing))
        if cols is None:
            cols = max(1, int(width / h_spacing))
        
        # Center the grid
        if center_grid:
            grid_width = cols * h_spacing
            grid_height = rows * v_spacing
            min_x = bounds.center_x - grid_width / 2
            min_y = bounds.center_y - grid_height / 2
        
        # Generate grid
        for row in range(rows):
            for col in range(cols):
                x = min_x + col * h_spacing
                y = min_y + row * v_spacing
                
                # Apply stagger
                if stagger and row % 2 == 1:
                    x += h_spacing * (stagger_amount / 100)
                
                # Apply rotation
                if rotation != 0:
                    x, y = self._rotate_point(x, y, bounds.center_x, bounds.center_y, rotation)
                
                # Check bounds
                if bounds.left <= x <= bounds.right and bounds.bottom <= y <= bounds.top:
                    candidates.append(PlacementCandidate(
                        x=x, y=y,
                        rotation=self._random_rotation(self.config.get('random_rotation', False), rotation)
                    ))
        
        return candidates
    
    def _rotate_point(self, x: float, y: float, cx: float, cy: float, angle: float) -> Tuple[float, float]:
        """Rotate a point around a center."""
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        dx = x - cx
        dy = y - cy
        return (cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a)


class RandomStrategy(DistributionStrategy):
    """Random scatter (Poisson-like) distribution."""
    
    def get_name(self) -> str:
        return "random"
    
    def generate(self, bounds: BoundingBox, stone_diameter: float) -> List[PlacementCandidate]:
        candidates = []
        
        count = self.config.get('count', 100)
        seed = self.config.get('seed', random.randint(0, 10000))
        density = self.config.get('density', 0.8)  # occupancy ratio
        edge_margin = self.config.get('edge_margin', 1.0)
        
        random.seed(seed)
        
        # Calculate effective area
        width = bounds.width - 2 * edge_margin
        height = bounds.height - 2 * edge_margin
        
        if width <= 0 or height <= 0:
            return candidates
        
        # Adjust count based on density (occupancy)
        area = width * height
        stone_area = math.pi * (stone_diameter / 2) ** 2
        max_stones = int(area / stone_area * density)
        actual_count = min(count, max_stones)
        
        # Generate random positions
        for _ in range(actual_count * 3):  # Try more times for Poisson-like
            if len(candidates) >= actual_count:
                break
            
            x = bounds.left + edge_margin + random.uniform(0, width)
            y = bounds.bottom + edge_margin + random.uniform(0, height)
            
            # Check minimum distance
            min_dist = stone_diameter * 0.8
            too_close = False
            for c in candidates:
                dist = math.sqrt((c.x - x) ** 2 + (c.y - y) ** 2)
                if dist < min_dist:
                    too_close = True
                    break
            
            if not too_close:
                candidates.append(PlacementCandidate(
                    x=x, y=y,
                    rotation=self._random_rotation(self.config.get('random_rotation', False))
                ))
        
        return candidates


class CircularStrategy(DistributionStrategy):
    """Circular/radial distribution around center."""
    
    def get_name(self) -> str:
        return "circular"
    
    def generate(self, bounds: BoundingBox, stone_diameter: float) -> List[PlacementCandidate]:
        candidates = []
        
        rings = self.config.get('rings', 5)
        start_radius = self.config.get('start_radius', stone_diameter)
        ring_spacing = self.config.get('ring_spacing', stone_diameter * 1.2)
        stones_per_ring = self.config.get('stones_per_ring', 8)
        density = self.config.get('density', 0.85)
        rotation = self.config.get('rotation', 0)
        
        cx = bounds.center_x
        cy = bounds.center_y
        
        for ring in range(rings):
            radius = start_radius + ring * ring_spacing
            if radius > min(bounds.width, bounds.height) / 2:
                break
            
            # Number of stones in this ring
            count = max(3, int(stones_per_ring * (1 + ring * 0.3)))
            count = int(count * density)
            
            for i in range(count):
                angle = (2 * math.pi * i / count) + math.radians(rotation)
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                
                # Check bounds
                if bounds.left < x < bounds.right and bounds.bottom < y < bounds.top:
                    candidates.append(PlacementCandidate(
                        x=x, y=y,
                        rotation=self._random_rotation(self.config.get('random_rotation', False), rotation)
                    ))
        
        return candidates


class PixelGridStrategy(DistributionStrategy):
    """Pixel grid distribution - each pixel is a potential stone position."""
    
    def get_name(self) -> str:
        return "pixel_grid"
    
    def generate(self, bounds: BoundingBox, stone_diameter: float) -> List[PlacementCandidate]:
        candidates = []
        
        pixel_size = self.config.get('pixel_size', stone_diameter)
        threshold = self.config.get('threshold', 128)  # 0-255
        invert = self.config.get('invert', False)
        
        # Generate grid
        x = bounds.left
        col = 0
        while x < bounds.right:
            y = bounds.bottom
            row = 0
            while y < bounds.top:
                # Checkerboard pattern
                if (row + col) % 2 == 0:
                    candidates.append(PlacementCandidate(
                        x=x, y=y,
                        rotation=self._random_rotation(self.config.get('random_rotation', False))
                    ))
                y += pixel_size
                row += 1
            x += pixel_size
            col += 1
        
        return candidates


class ImageBasedStrategy(DistributionStrategy):
    """Image-based distribution - stones placed on bright/dark pixels."""
    
    def get_name(self) -> str:
        return "image"
    
    def generate(self, bounds: BoundingBox, stone_diameter: float) -> List[PlacementCandidate]:
        candidates = []
        
        image_path = self.config.get('image_path')
        if not image_path:
            return candidates
        
        threshold = self.config.get('threshold', 128)
        invert = self.config.get('invert', False)
        scale = self.config.get('scale', 1.0)
        
        try:
            img = Image.open(image_path).convert('L')
            img = img.resize((
                int(img.width * scale),
                int(img.height * scale)
            ))
            pixels = np.array(img)
            
            # Map to bounds
            width = bounds.width
            height = bounds.height
            pixel_width = width / img.width
            pixel_height = height / img.height
            
            for row in range(img.height):
                for col in range(img.width):
                    value = pixels[row, col]
                    
                    # Check threshold
                    if invert:
                        valid = value < threshold
                    else:
                        valid = value > threshold
                    
                    if valid:
                        x = bounds.left + col * pixel_width + pixel_width / 2
                        y = bounds.bottom + row * pixel_height + pixel_height / 2
                        
                        if bounds.left < x < bounds.right and bounds.bottom < y < bounds.top:
                            candidates.append(PlacementCandidate(
                                x=x, y=y,
                                rotation=self._random_rotation(self.config.get('random_rotation', False))
                            ))
                            
        except Exception as e:
            logging.warning(f"Failed to load image: {e}")
        
        return candidates


class ProceduralPatternStrategy(DistributionStrategy):
    """Procedural geometric pattern from the procedural_pattern module."""
    
    def get_name(self) -> str:
        return "procedural"
    
    def generate(self, bounds: BoundingBox, stone_diameter: float) -> List[PlacementCandidate]:
        # Import here to avoid circular imports
        from .procedural_pattern import ProceduralPatternGenerator, ProceduralPatternSettings
        
        candidates = []
        
        # Extract config
        settings = ProceduralPatternSettings(
            lattice_spacing=self.config.get('lattice_spacing', 12.0),
            lattice_rows=self.config.get('rows', 10),
            lattice_cols=self.config.get('cols', 10),
            cluster_radius=self.config.get('cluster_radius', 3.5),
            cluster_density=self.config.get('cluster_density', 0.85),
            accent_probability=self.config.get('accent_probability', 0.35),
            connector_length=self.config.get('connector_length', 4.5),
            symmetry=self.config.get('symmetry', 'both'),
            noise_level=self.config.get('noise_level', 0.05),
            output_width=int(bounds.width),
            output_height=int(bounds.height),
        )
        
        gen = ProceduralPatternGenerator(settings)
        gen.generate()
        
        placements = gen.get_stone_placements()
        
        # Convert hex positions to world coordinates
        for row, col, size_factor in placements:
            # Convert hex to pixel
            if row % 2 == 1:
                x = col * settings.lattice_spacing * 1.5
            else:
                x = col * settings.lattice_spacing * 1.5 + settings.lattice_spacing * 0.75
            y = row * settings.lattice_spacing * math.sqrt(3)
            
            # Scale to bounds
            scale_x = bounds.width / (settings.lattice_cols * settings.lattice_spacing)
            scale_y = bounds.height / (settings.lattice_rows * settings.lattice_spacing)
            
            x = bounds.left + x * scale_x
            y = bounds.bottom + y * scale_y
            
            if bounds.left < x < bounds.right and bounds.bottom < y < bounds.top:
                candidates.append(PlacementCandidate(
                    x=x, y=y,
                    size_factor=size_factor,
                    rotation=self._random_rotation(self.config.get('random_rotation', False))
                ))
        
        return candidates


class StrategyFactory:
    """Factory for creating distribution strategies."""
    
    _strategies = {
        'hexagonal': HexagonalStrategy,
        'random': RandomStrategy,
        'circular': CircularStrategy,
        'pixel_grid': PixelGridStrategy,
        'image': ImageBasedStrategy,
        'procedural': ProceduralPatternStrategy,
    }
    
    @classmethod
    def create(cls, strategy_name: str, config: Dict = None) -> DistributionStrategy:
        """Create a strategy by name."""
        strategy_class = cls._strategies.get(strategy_name.lower())
        if strategy_class is None:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        return strategy_class(config)
    
    @classmethod
    def register(cls, name: str, strategy_class: type):
        """Register a custom strategy."""
        cls._strategies[name.lower()] = strategy_class
    
    @classmethod
    def available_strategies(cls) -> List[str]:
        """Get list of available strategy names."""
        return list(cls._strategies.keys())


def create_strategy(strategy_name: str, config: Dict = None) -> DistributionStrategy:
    """Convenience function to create a strategy."""
    return StrategyFactory.create(strategy_name, config)
