"""
Mathematical helper functions for geometry calculations.
"""

import math
from typing import Tuple, List


def lerp(a: float, b: float, t: float) -> float:
    """
    Linear interpolation between two values.

    Args:
        a: Start value.
        b: End value.
        t: Interpolation factor (0-1).

    Returns:
        Interpolated value.
    """
    return a + (b - a) * t


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value between min and max.

    Args:
        value: Value to clamp.
        min_val: Minimum value.
        max_val: Maximum value.

    Returns:
        Clamped value.
    """
    return max(min_val, min(max_val, value))


def normalize_angle(angle: float) -> float:
    """
    Normalize angle to 0-360 range.

    Args:
        angle: Angle in degrees.

    Returns:
        Normalized angle.
    """
    while angle < 0:
        angle += 360
    while angle >= 360:
        angle -= 360
    return angle


def deg_to_rad(degrees: float) -> float:
    """Convert degrees to radians."""
    return math.radians(degrees)


def rad_to_deg(radians: float) -> float:
    """Convert radians to degrees."""
    return math.degrees(radians)


def rotate_point(x: float, y: float, angle: float, cx: float = 0, cy: float = 0) -> Tuple[float, float]:
    """
    Rotate a point around a center.

    Args:
        x: Point X coordinate.
        y: Point Y coordinate.
        angle: Rotation angle in degrees.
        cx: Center X coordinate.
        cy: Center Y coordinate.

    Returns:
        Tuple of rotated (x, y) coordinates.
    """
    rad = math.radians(angle)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    # Translate to origin
    tx = x - cx
    ty = y - cy

    # Rotate
    rx = tx * cos_a - ty * sin_a
    ry = tx * sin_a + ty * cos_a

    # Translate back
    return (rx + cx, ry + cy)


def distance_2d(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate 2D distance between two points."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def angle_between_points(x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Calculate angle between two points in degrees.

    Returns angle from point 1 to point 2.
    """
    return math.degrees(math.atan2(y2 - y1, x2 - x1))


def perpendicular_angle(angle: float) -> float:
    """Get perpendicular angle (90 degrees rotated)."""
    return normalize_angle(angle + 90)


def midpoint(x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
    """Calculate midpoint between two points."""
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def bezier_point(t: float, p0: Tuple[float, float], p1: Tuple[float, float],
                 p2: Tuple[float, float], p3: Tuple[float, float]) -> Tuple[float, float]:
    """
    Calculate point on cubic Bezier curve.

    Args:
        t: Parameter (0-1).
        p0: Start point.
        p1: Control point 1.
        p2: Control point 2.
        p3: End point.

    Returns:
        Point on curve.
    """
    t2 = t * t
    t3 = t2 * t
    mt = 1 - t
    mt2 = mt * mt
    mt3 = mt2 * mt

    x = mt3 * p0[0] + 3 * mt2 * t * p1[0] + 3 * mt * t2 * p2[0] + t3 * p3[0]
    y = mt3 * p0[1] + 3 * mt2 * t * p1[1] + 3 * mt * t2 * p2[1] + t3 * p3[1]

    return (x, y)


def bezier_length(p0: Tuple[float, float], p1: Tuple[float, float],
                  p2: Tuple[float, float], p3: Tuple[float, float],
                  segments: int = 20) -> float:
    """
    Approximate length of cubic Bezier curve.

    Args:
        p0-p3: Control points.
        segments: Number of segments for approximation.

    Returns:
        Approximate curve length.
    """
    total = 0.0
    prev = p0

    for i in range(1, segments + 1):
        t = i / segments
        curr = bezier_point(t, p0, p1, p2, p3)
        total += distance_2d(prev[0], prev[1], curr[0], curr[1])
        prev = curr

    return total


def scale_point(x: float, y: float, scale_x: float, scale_y: float,
                cx: float = 0, cy: float = 0) -> Tuple[float, float]:
    """
    Scale a point relative to a center.

    Args:
        x, y: Point coordinates.
        scale_x, scale_y: Scale factors.
        cx, cy: Center of scaling.

    Returns:
        Scaled point coordinates.
    """
    return (cx + (x - cx) * scale_x, cy + (y - cy) * scale_y)


def is_point_in_polygon(x: float, y: float, polygon: List[Tuple[float, float]]) -> bool:
    """
    Check if point is inside polygon using ray casting algorithm.

    Args:
        x, y: Point to test.
        polygon: List of (x, y) vertices.

    Returns:
        True if point is inside polygon.
    """
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside
