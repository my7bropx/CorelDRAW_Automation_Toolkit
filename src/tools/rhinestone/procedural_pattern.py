"""
Procedural Pattern System
Generates geometric motifs on a lattice and rasterizes to hexagonal grid.
"""

import math
import random
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict


class ColorRole(Enum):
    """Color roles for pattern visualization."""
    PRIMARY = "red"      
    ACCENT = "green"    
    CONNECTOR = "yellow" 
    BACKGROUND = "black"  
    BOUNDARY = "white"   


@dataclass
class Point2D:
    """2D point."""
    x: float
    y: float
    
    def distance_to(self, other: 'Point2D') -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)


@dataclass
class ProceduralPatternSettings:
    """Settings for procedural pattern generation."""
    lattice_spacing: float = 10.0
    lattice_rows: int = 10
    lattice_cols: int = 10
    
    cluster_radius: float = 3.0
    cluster_density: float = 0.8
    accent_probability: float = 0.3
    connector_length: float = 4.0
    connector_angle: float = 45.0
    
    hex_cell_size: float = 1.0
    hex_smooth_radius: float = 0
    
    symmetry: str = "none"
    rotation: float = 0.0
    noise_level: float = 0.0
    
    output_width: int = 100
    output_height: int = 100


def hex_to_pixel(row: int, col: int, cell_size: float) -> Tuple[float, float]:
    """Convert hex grid coordinates to pixel coordinates."""
    if row % 2 == 1:
        x = col * cell_size * 1.5
    else:
        x = col * cell_size * 1.5 + cell_size * 0.75
    y = row * cell_size * math.sqrt(3)
    return (x, y)


def pixel_to_hex(x: float, y: float, cell_size: float) -> Tuple[int, int]:
    """Convert pixel coordinates to hex grid coordinates."""
    row = int(round(y / (cell_size * math.sqrt(3))))
    if row % 2 == 0:
        col = int(round(x / (cell_size * 1.5)))
    else:
        col = int(round((x - cell_size * 0.75) / (cell_size * 1.5)))
    return (row, col)


class GeometricMotif:
    """Represents a geometric motif (cluster + accent + connectors)."""
    
    def __init__(self, center: Point2D, settings: ProceduralPatternSettings):
        self.center = center
        self.settings = settings
        self.has_accent = random.random() < settings.accent_probability
        self.nodes: List[Point2D] = []
        self.connectors: List[Tuple[Point2D, Point2D]] = []
        self._generate()
    
    def _generate(self):
        """Generate the motif components."""
        s = self.settings
        r = s.cluster_radius
        
        # Generate cluster nodes (circular arrangement)
        num_nodes = max(4, int(r * 2))
        for i in range(num_nodes):
            angle = (2 * math.pi * i) / num_nodes
            x = self.center.x + r * 0.5 * math.cos(angle)
            y = self.center.y + r * 0.5 * math.sin(angle)
            self.nodes.append(Point2D(x, y))
        
        # Add accent at center
        if self.has_accent:
            self.nodes.append(Point2D(self.center.x, self.center.y))
        
        # Generate diagonal connectors
        if s.connector_length > 0:
            angle_rad = math.radians(s.connector_angle)
            half_len = s.connector_length * 0.4
            for dx, dy in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                end_x = self.center.x + half_len * dx
                end_y = self.center.y + half_len * dy
                self.connectors.append((
                    Point2D(self.center.x, self.center.y),
                    Point2D(end_x, end_y)
                ))


class ProceduralPatternGenerator:
    """
    Generates procedural patterns on a lattice and rasterizes to hex grid.
    """
    
    def __init__(self, settings: ProceduralPatternSettings = None):
        self.settings = settings or ProceduralPatternSettings()
        self.lattice_points: List[Point2D] = []
        self.motifs: List[GeometricMotif] = []
        self.hex_grid: Dict[Tuple[int, int], ColorRole] = {}
        self.bounds = None
    
    def generate(self) -> Dict[Tuple[int, int], ColorRole]:
        """Generate the complete pattern."""
        self._generate_lattice()
        self._generate_motifs()
        
        if self.settings.symmetry != "none":
            self._apply_symmetry()
        
        self._rasterize_to_hex()
        
        if self.settings.noise_level > 0:
            self._apply_noise()
        
        if self.settings.hex_smooth_radius > 0:
            self._smooth_output()
        
        return self.hex_grid
    
    def _generate_lattice(self):
        """Generate base lattice points."""
        s = self.settings
        self.lattice_points = []
        
        for row in range(s.lattice_rows):
            for col in range(s.lattice_cols):
                x = col * s.lattice_spacing
                y = row * s.lattice_spacing * 0.866  # hex vertical spacing
                
                # Stagger every other row
                if row % 2 == 1:
                    x += s.lattice_spacing * 0.5
                
                # Apply rotation
                if s.rotation != 0:
                    cx = s.lattice_spacing * s.lattice_cols / 2
                    cy = s.lattice_spacing * s.lattice_rows * 0.866 / 2
                    angle_rad = math.radians(s.rotation)
                    x_new = cx + (x - cx) * math.cos(angle_rad) - (y - cy) * math.sin(angle_rad)
                    y_new = cy + (x - cx) * math.sin(angle_rad) + (y - cy) * math.cos(angle_rad)
                    x, y = x_new, y_new
                
                self.lattice_points.append(Point2D(x, y))
        
        if self.lattice_points:
            xs = [p.x for p in self.lattice_points]
            ys = [p.y for p in self.lattice_points]
            self.bounds = (min(xs), min(ys), max(xs), max(ys))
    
    def _generate_motifs(self):
        """Generate geometric motifs at lattice points."""
        self.motifs = []
        
        for point in self.lattice_points:
            if random.random() < self.settings.cluster_density:
                motif = GeometricMotif(point, self.settings)
                self.motifs.append(motif)
    
    def _apply_symmetry(self):
        """Apply symmetry transformations."""
        s = self.settings
        if not self.bounds:
            return
        
        cx = (self.bounds[0] + self.bounds[2]) / 2
        cy = (self.bounds[1] + self.bounds[3]) / 2
        
        new_motifs = []
        
        for motif in self.motifs:
            new_motifs.append(motif)
            
            if s.symmetry in ("horizontal", "both"):
                new_center = Point2D(2 * cx - motif.center.x, motif.center.y)
                new_motifs.append(GeometricMotif(new_center, self.settings))
            
            if s.symmetry in ("vertical", "both"):
                new_center = Point2D(motif.center.x, 2 * cy - motif.center.y)
                new_motifs.append(GeometricMotif(new_center, self.settings))
            
            if s.symmetry == "both" and len(new_motifs) > 2:
                new_center = Point2D(2 * cx - motif.center.x, 2 * cy - motif.center.y)
                new_motifs.append(GeometricMotif(new_center, self.settings))
        
        self.motifs = new_motifs
    
    def _rasterize_to_hex(self):
        """Rasterize motifs to hexagonal grid with PROPER color assignment."""
        s = self.settings
        self.hex_grid = {}
        
        # Collect points by type separately
        primary_points = []
        accent_points = []
        connector_points = []
        
        for motif in self.motifs:
            # PRIMARY nodes first (cluster perimeter)
            for node in motif.nodes:
                if node != motif.center or not motif.has_accent:
                    primary_points.append(node)
            
            # ACCENT point at center (if exists)
            if motif.has_accent:
                accent_points.append(motif.center)
            
            # CONNECTOR points (sparse - only at endpoints)
            for start, end in motif.connectors:
                connector_points.append(start)  # Start point
                connector_points.append(end)    # End point
        
        # Add in CORRECT order: PRIMARY first, then ACCENT, then CONNECTOR
        # This ensures PRIMARY becomes the base fill color
        
        for point in primary_points:
            hex_pos = pixel_to_hex(point.x, point.y, s.hex_cell_size)
            self.hex_grid[hex_pos] = ColorRole.PRIMARY
        
        for point in accent_points:
            hex_pos = pixel_to_hex(point.x, point.y, s.hex_cell_size)
            self.hex_grid[hex_pos] = ColorRole.ACCENT
        
        for point in connector_points:
            hex_pos = pixel_to_hex(point.x, point.y, s.hex_cell_size)
            self.hex_grid[hex_pos] = ColorRole.CONNECTOR
        
        # Fill in neighbors to create connected pattern
        self._fill_neighbors()
    
    def _fill_neighbors(self):
        """Fill in gaps between colored hex cells."""
        s = self.settings
        filled = dict(self.hex_grid)
        
        # For each filled cell, check if neighbors need filling
        for (row, col), color in list(self.hex_grid.items()):
            # Get neighbors
            if row % 2 == 0:
                neighbor_offsets = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)]
            else:
                neighbor_offsets = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0), (1, 1)]
            
            for dr, dc in neighbor_offsets:
                nr, nc = row + dr, col + dc
                if (nr, nc) not in filled:
                    # Check distance to original points
                    nx, ny = hex_to_pixel(nr, nc, s.hex_cell_size)
                    
                    # Find closest PRIMARY or ACCENT point (not connector)
                    closest_dist = float('inf')
                    closest_color = ColorRole.PRIMARY  # Default to PRIMARY
                    
                    for (orow, ocol), ocolor in self.hex_grid.items():
                        # Skip connectors for filling - they should be sparse
                        if ocolor == ColorRole.CONNECTOR:
                            continue
                        ox, oy = hex_to_pixel(orow, ocol, s.hex_cell_size)
                        dist = math.sqrt((nx - ox)**2 + (ny - oy)**2)
                        if dist < closest_dist:
                            closest_dist = dist
                            closest_color = ocolor
                    
                    # Fill if close enough
                    if closest_dist < s.hex_cell_size * 3.0:
                        filled[(nr, nc)] = closest_color
        
        self.hex_grid = filled
    
    def _apply_noise(self):
        """Add random noise to the pattern."""
        s = self.settings
        if s.noise_level <= 0:
            return
        
        num_noise = int(s.noise_level * len(self.hex_grid) * 0.1)
        
        # Get extents
        rows = [r for r, c in self.hex_grid.keys()]
        cols = [c for r, c in self.hex_grid.keys()]
        min_row, max_row = min(rows), max(rows)
        min_col, max_col = min(cols), max(cols)
        
        for _ in range(num_noise):
            row = random.randint(min_row - 2, max_row + 2)
            col = random.randint(min_col - 2, max_col + 2)
            
            # Random color from available
            colors = list(ColorRole)
            noise_color = random.choice(colors)
            self.hex_grid[(row, col)] = noise_color
    
    def _smooth_output(self):
        """Apply smoothing to reduce noise while preserving structure."""
        # This would be used if we wanted smoothing
        pass  # Disabled for now to preserve color roles
    
    def get_color_grid(self):
        """Get the pattern as a color grid."""
        s = self.settings
        
        color_map = {
            ColorRole.PRIMARY: (255, 50, 50),      # Red
            ColorRole.ACCENT: (50, 255, 50),       # Green  
            ColorRole.CONNECTOR: (255, 255, 50),   # Yellow
            ColorRole.BACKGROUND: (20, 20, 20),    # Dark
            ColorRole.BOUNDARY: (255, 255, 255),  # White
        }
        
        if not self.hex_grid:
            return [[(20, 20, 20) for _ in range(s.output_width)] for _ in range(s.output_height)]
        
        rows = [r for r, c in self.hex_grid.keys()]
        cols = [c for r, c in self.hex_grid.keys()]
        min_row, max_row = min(rows), max(rows)
        min_col, max_col = min(cols), max(cols)
        
        grid_height = max_row - min_row + 1
        grid_width = max_col - min_col + 1
        
        scale_y = s.output_height / grid_height if grid_height > 1 else 1
        scale_x = s.output_width / grid_width if grid_width > 1 else 1
        
        image = [[color_map[ColorRole.BACKGROUND] for _ in range(s.output_width)] for _ in range(s.output_height)]
        
        for (r, c), color in self.hex_grid.items():
            out_r = int((r - min_row) * scale_y)
            out_c = int((c - min_col) * scale_x)
            
            if 0 <= out_r < s.output_height and 0 <= out_c < s.output_width:
                image[out_r][out_c] = color_map.get(color, (20, 20, 20))
        
        return image
    
    def get_stone_placements(self) -> List[Tuple[int, int, float]]:
        """Get stone placements as (row, col, size_factor) tuples."""
        placements = []
        
        size_map = {
            ColorRole.PRIMARY: 1.0,
            ColorRole.ACCENT: 0.8,
            ColorRole.CONNECTOR: 0.6,
            ColorRole.BACKGROUND: 0,
            ColorRole.BOUNDARY: 0.4,
        }
        
        for (row, col), color in self.hex_grid.items():
            size_factor = size_map.get(color, 0)
            if size_factor > 0:
                placements.append((row, col, size_factor))
        
        return placements


def create_procedural_pattern(
    lattice_spacing: float = 10.0,
    cluster_radius: float = 3.0,
    cluster_density: float = 0.8,
    accent_probability: float = 0.3,
    connector_length: float = 4.0,
    rows: int = 10,
    cols: int = 10,
    symmetry: str = "none",
    noise_level: float = 0.0,
    output_size: Tuple[int, int] = (100, 100),
):
    """Convenience function to create a procedural pattern."""
    settings = ProceduralPatternSettings(
        lattice_spacing=lattice_spacing,
        lattice_rows=rows,
        lattice_cols=cols,
        cluster_radius=cluster_radius,
        cluster_density=cluster_density,
        accent_probability=accent_probability,
        connector_length=connector_length,
        symmetry=symmetry,
        noise_level=noise_level,
        output_width=output_size[0],
        output_height=output_size[1],
    )
    
    generator = ProceduralPatternGenerator(settings)
    generator.generate()
    
    return generator.get_color_grid()


if __name__ == "__main__":
    import numpy as np
    
    pattern = create_procedural_pattern(
        lattice_spacing=12.0,
        cluster_radius=3.5,
        cluster_density=0.9,
        accent_probability=0.35,
        connector_length=4.5,
        rows=8,
        cols=8,
        symmetry="both",
        noise_level=0.05,
        output_size=(160, 160),
    )
    
    print(f"Pattern grid size: {len(pattern)}x{len(pattern[0])}")
    
    # Count colors
    counts = defaultdict(int)
    for row in pattern:
        for color in row:
            if color == (255, 50, 50):
                counts['PRIMARY (Red)'] += 1
            elif color == (50, 255, 50):
                counts['ACCENT (Green)'] += 1
            elif color == (255, 255, 50):
                counts['CONNECTOR (Yellow)'] += 1
            elif color == (255, 255, 255):
                counts['BOUNDARY (White)'] += 1
            else:
                counts['BACKGROUND (Black)'] += 1
    
    for role, count in sorted(counts.items()):
        print(f"  {role}: {count}")
