import math
from typing import List, Sequence, Tuple

import numpy as np


def _base_ranges(width_mm: float, height_mm: float, diameter_mm: float, gap_mm: float, edge_margin_mm: float) -> Tuple[float, float, float, float, float]:
    pitch = float(diameter_mm) + max(0.0, float(gap_mm))
    radius = float(diameter_mm) / 2.0
    margin = max(0.0, float(edge_margin_mm)) + radius
    min_x = margin
    min_y = margin
    max_x = float(width_mm) - margin
    max_y = float(height_mm) - margin
    return min_x, min_y, max_x, max_y, pitch


def generate_candidate_points(
    width_mm: float,
    height_mm: float,
    diameter_mm: float,
    gap_mm: float,
    edge_margin_mm: float,
    layout: str,
    jitter_mm: float = 0.0,
    seed: int = 0,
) -> np.ndarray:
    """Generate candidate stone centers with vectorized grid construction."""
    min_x, min_y, max_x, max_y, pitch = _base_ranges(width_mm, height_mm, diameter_mm, gap_mm, edge_margin_mm)
    if min_x >= max_x or min_y >= max_y or pitch <= 0:
        return np.empty((0, 2), dtype=np.float32)

    rng = np.random.default_rng(seed)
    jitter = max(0.0, float(jitter_mm))

    if layout == "grid":
        xs = np.arange(min_x, max_x + 1e-9, pitch, dtype=np.float32)
        ys = np.arange(min_y, max_y + 1e-9, pitch, dtype=np.float32)
        gx, gy = np.meshgrid(xs, ys)
        points = np.column_stack((gx.ravel(), gy.ravel()))
    elif layout == "staggered":
        ys = np.arange(min_y, max_y + 1e-9, pitch, dtype=np.float32)
        rows: List[np.ndarray] = []
        for row_index, y in enumerate(ys):
            start_x = min_x + (pitch / 2.0 if row_index % 2 else 0.0)
            xs = np.arange(start_x, max_x + 1e-9, pitch, dtype=np.float32)
            if xs.size:
                rows.append(np.column_stack((xs, np.full(xs.shape, y, dtype=np.float32))))
        points = np.vstack(rows) if rows else np.empty((0, 2), dtype=np.float32)
    elif layout == "random":
        cols = max(1, int(math.floor((max_x - min_x) / pitch)))
        rows = max(1, int(math.floor((max_y - min_y) / pitch)))
        count = max(1, cols * rows)
        xs = rng.uniform(min_x, max_x, size=count).astype(np.float32)
        ys = rng.uniform(min_y, max_y, size=count).astype(np.float32)
        points = np.column_stack((xs, ys))
    elif layout == "spiral":
        max_radius = min((max_x - min_x), (max_y - min_y)) / 2.0
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        turns = max(3, int(max_radius / max(0.01, pitch)))
        theta = np.linspace(0.0, turns * 2.0 * math.pi, num=max(64, turns * 32), dtype=np.float32)
        radius = np.linspace(0.0, max_radius, num=theta.size, dtype=np.float32)
        xs = center_x + (np.cos(theta) * radius)
        ys = center_y + (np.sin(theta) * radius)
        points = np.column_stack((xs, ys))
    elif layout in ("custom", "contour"):
        row_h = pitch * 0.9
        xs = np.arange(min_x, max_x + 1e-9, pitch, dtype=np.float32)
        ys = np.arange(min_y, max_y + 1e-9, row_h, dtype=np.float32)
        gx, gy = np.meshgrid(xs, ys)
        points = np.column_stack((gx.ravel(), gy.ravel()))
        if points.size:
            points[:, 0] += rng.uniform(-pitch * 0.35, pitch * 0.35, size=points.shape[0]).astype(np.float32)
            points[:, 1] += rng.uniform(-row_h * 0.35, row_h * 0.35, size=points.shape[0]).astype(np.float32)
    else:
        row_h = pitch * math.sqrt(3.0) / 2.0
        ys = np.arange(min_y, max_y + 1e-9, row_h, dtype=np.float32)
        rows = []
        for row_index, y in enumerate(ys):
            start_x = min_x + (pitch / 2.0 if row_index % 2 else 0.0)
            xs = np.arange(start_x, max_x + 1e-9, pitch, dtype=np.float32)
            if xs.size:
                rows.append(np.column_stack((xs, np.full(xs.shape, y, dtype=np.float32))))
        points = np.vstack(rows) if rows else np.empty((0, 2), dtype=np.float32)

    if jitter > 0.0 and points.size:
        points[:, 0] += rng.uniform(-jitter, jitter, size=points.shape[0]).astype(np.float32)
        points[:, 1] += rng.uniform(-jitter, jitter, size=points.shape[0]).astype(np.float32)

    return points
