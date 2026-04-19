import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw

from ...core.corel_interface import BoundingBox, Point
from ..common import CacheManager, PreviewRenderer, ToolController, generate_candidate_points

logger = logging.getLogger(__name__)

Color = Tuple[int, int, int]


@dataclass(frozen=True)
class PatternPath:
    points: Tuple[Tuple[float, float], ...]
    closed: bool = False
    name: str = "path"


@dataclass(frozen=True)
class PatternStone:
    x_mm: float
    y_mm: float
    diameter_mm: float
    color_name: str
    rgb: Color
    pattern_layer: str

    @property
    def radius_mm(self) -> float:
        return self.diameter_mm / 2.0


@dataclass
class PatternFillConfig:
    width_mm: float
    height_mm: float
    stone_diameter_mm: float = 2.8
    spacing_mm: float = 0.2
    offset_mm: float = 3.0
    offset_count: int = 2
    line_offset_mm: float = 0.0
    edge_margin_mm: float = 0.2
    fill_layout: str = "hex"
    ray_count: int = 24
    ray_angle_start_deg: float = 0.0
    ray_angle_end_deg: float = 360.0
    ray_center_mode: str = "bounds_center"
    ray_center_x_mm: float = 0.0
    ray_center_y_mm: float = 0.0
    preview_ppm: int = 6
    seed: int = 12
    enable_curve: bool = True
    enable_offsets: bool = False
    enable_rays: bool = False
    enable_fill: bool = True
    enable_boundary: bool = True
    color_mode: str = "per_layer"
    single_color_name: str = "crystal"
    single_color_rgb: Color = (239, 239, 239)
    palette: Dict[str, Color] = field(default_factory=lambda: {
        "crystal": (239, 239, 239),
        "jet": (18, 18, 18),
        "sapphire": (44, 82, 205),
        "aquamarine": (60, 201, 214),
        "hyacinth": (220, 88, 62),
        "citrine": (239, 199, 58),
        "emerald": (67, 186, 92),
        "rose": (219, 125, 191),
    })


@dataclass
class PatternFillResult:
    stones: List[PatternStone]
    preview_image: Image.Image
    preview_scene: object
    width_mm: float
    height_mm: float
    per_color: Dict[str, int]
    per_layer: Dict[str, int]
    timings: Dict[str, float]
    cache_key: str


class PatternFillEngine:
    def __init__(self) -> None:
        self._cache = CacheManager()
        self._controller = ToolController(self._cache)
        self._preview_renderer = PreviewRenderer()

    def build_cache_key(self, bounds: BoundingBox, paths: Sequence[PatternPath], config: PatternFillConfig) -> str:
        return self._cache.build_key(
            "pattern_fill",
            {
                "bounds": {
                    "width": round(float(bounds.width), 4),
                    "height": round(float(bounds.height), 4),
                },
                "paths": [
                    {
                        "closed": path.closed,
                        "name": path.name,
                        "points": [(round(x, 4), round(y, 4)) for x, y in path.points],
                    }
                    for path in paths
                ],
                "config": {key: value for key, value in vars(config).items() if key != "palette"},
            },
        )

    def _localize_paths(self, bounds: BoundingBox, paths: Sequence[PatternPath]) -> Tuple[BoundingBox, List[PatternPath]]:
        local_bounds = BoundingBox(0.0, 0.0, float(bounds.width), float(bounds.height))
        local_paths = [
            PatternPath(
                points=tuple((float(x - bounds.left), float(y - bounds.bottom)) for x, y in path.points),
                closed=bool(path.closed),
                name=path.name,
            )
            for path in paths
        ]
        return local_bounds, local_paths

    @staticmethod
    def _disk_offsets(radius_px: int) -> np.ndarray:
        radius_px = max(0, int(radius_px))
        rr = np.arange(-radius_px, radius_px + 1)
        gx, gy = np.meshgrid(rr, rr)
        return np.column_stack((gy[(gx * gx + gy * gy) <= (radius_px * radius_px)], gx[(gx * gx + gy * gy) <= (radius_px * radius_px)])).astype(np.int16)

    def _build_closed_mask(self, bounds: BoundingBox, paths: Sequence[PatternPath], ppm: int) -> np.ndarray:
        width_px = max(1, int(round(bounds.width * ppm)))
        height_px = max(1, int(round(bounds.height * ppm)))
        image = Image.new("L", (width_px, height_px), 0)
        draw = ImageDraw.Draw(image)
        has_closed = False
        for path in paths:
            if not path.closed or len(path.points) < 3:
                continue
            has_closed = True
            polygon = [((x - bounds.left) * ppm, (y - bounds.bottom) * ppm) for x, y in path.points]
            draw.polygon(polygon, fill=255)
        if not has_closed:
            return np.ones((height_px, width_px), dtype=bool)
        return np.array(image) >= 128

    def _build_safe_center_mask(self, allowed_mask: np.ndarray, radius_mm: float, ppm: int) -> np.ndarray:
        allowed_mask = np.asarray(allowed_mask, dtype=bool)
        radius_px = max(0, int(math.ceil(radius_mm * ppm)))
        offsets = self._disk_offsets(radius_px)
        safe = np.zeros_like(allowed_mask, dtype=bool)
        y_start = radius_px
        y_end = max(radius_px, allowed_mask.shape[0] - radius_px)
        x_start = radius_px
        x_end = max(radius_px, allowed_mask.shape[1] - radius_px)
        if y_end <= y_start or x_end <= x_start:
            return safe
        interior = np.ones((y_end - y_start, x_end - x_start), dtype=bool)
        for dy, dx in offsets:
            interior &= allowed_mask[y_start + int(dy):y_end + int(dy), x_start + int(dx):x_end + int(dx)]
        safe[y_start:y_end, x_start:x_end] = interior
        return safe

    def _can_place(self, occupancy: np.ndarray, px: int, py: int, radius_px: int) -> bool:
        offsets = self._disk_offsets(radius_px)
        ys = py + offsets[:, 0]
        xs = px + offsets[:, 1]
        valid = (ys >= 0) & (xs >= 0) & (ys < occupancy.shape[0]) & (xs < occupancy.shape[1])
        return not bool(occupancy[ys[valid], xs[valid]].any())

    def _mark_occupancy(self, occupancy: np.ndarray, px: int, py: int, radius_px: int) -> None:
        offsets = self._disk_offsets(radius_px)
        ys = py + offsets[:, 0]
        xs = px + offsets[:, 1]
        valid = (ys >= 0) & (xs >= 0) & (ys < occupancy.shape[0]) & (xs < occupancy.shape[1])
        occupancy[ys[valid], xs[valid]] = True

    def _sample_polyline(self, path: PatternPath, spacing: float, start_offset: float = 0.0) -> np.ndarray:
        if len(path.points) < 2:
            return np.empty((0, 4), dtype=np.float32)
        pts = np.asarray(path.points, dtype=np.float32)
        if path.closed and not np.allclose(pts[0], pts[-1]):
            pts = np.vstack((pts, pts[0]))
        segments = pts[1:] - pts[:-1]
        lengths = np.linalg.norm(segments, axis=1)
        cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
        total = float(cumulative[-1])
        if total <= 1e-6:
            return np.empty((0, 4), dtype=np.float32)
        samples = np.arange(max(0.0, start_offset), total + 1e-6, max(0.1, spacing), dtype=np.float32)
        rows = []
        seg_index = 0
        for distance in samples:
            while seg_index < len(lengths) - 1 and cumulative[seg_index + 1] < distance:
                seg_index += 1
            seg_length = max(1e-6, lengths[seg_index])
            local_t = (distance - cumulative[seg_index]) / seg_length
            start = pts[seg_index]
            tangent = segments[seg_index] / seg_length
            point = start + (segments[seg_index] * local_t)
            rows.append((point[0], point[1], tangent[0], tangent[1]))
        return np.asarray(rows, dtype=np.float32)

    def _resolve_color(self, layer_name: str, layer_index: int, config: PatternFillConfig) -> Tuple[str, Color]:
        if config.color_mode == "single":
            return config.single_color_name, config.single_color_rgb
        palette_items = list(config.palette.items())
        if not palette_items:
            return "crystal", (239, 239, 239)
        if config.color_mode == "per_rule":
            key = layer_name.split("_", 1)[0]
            index = abs(hash(key)) % len(palette_items)
        else:
            index = layer_index % len(palette_items)
        return palette_items[index]

    def _append_stones(
        self,
        placements: np.ndarray,
        layer_name: str,
        layer_index: int,
        bounds: BoundingBox,
        safe_mask: np.ndarray,
        occupancy: np.ndarray,
        config: PatternFillConfig,
        stones: List[PatternStone],
    ) -> int:
        placed = 0
        color_name, rgb = self._resolve_color(layer_name, layer_index, config)
        radius_mm = config.stone_diameter_mm / 2.0
        collision_radius_px = max(1, int(math.ceil((radius_mm + (config.spacing_mm / 2.0)) * config.preview_ppm)))
        for row in placements:
            x_mm = float(row[0])
            y_mm = float(row[1])
            px = int(round((x_mm - bounds.left) * config.preview_ppm))
            py = int(round((y_mm - bounds.bottom) * config.preview_ppm))
            if px < 0 or py < 0 or py >= safe_mask.shape[0] or px >= safe_mask.shape[1]:
                continue
            if not safe_mask[py, px]:
                continue
            if not self._can_place(occupancy, px, py, collision_radius_px):
                continue
            stones.append(
                PatternStone(
                    x_mm=x_mm,
                    y_mm=y_mm,
                    diameter_mm=config.stone_diameter_mm,
                    color_name=color_name,
                    rgb=rgb,
                    pattern_layer=layer_name,
                )
            )
            self._mark_occupancy(occupancy, px, py, collision_radius_px)
            placed += 1
        return placed

    def _generate_curve_layer(self, paths: Sequence[PatternPath], config: PatternFillConfig) -> Dict[str, np.ndarray]:
        layers: Dict[str, np.ndarray] = {}
        spacing = max(0.2, config.stone_diameter_mm + config.spacing_mm)
        for path_index, path in enumerate(paths):
            if config.enable_curve:
                layers[f"curve_{path_index + 1}"] = self._sample_polyline(path, spacing, start_offset=config.line_offset_mm)
            if config.enable_offsets:
                base = self._sample_polyline(path, spacing, start_offset=config.line_offset_mm)
                for offset_index in range(1, max(0, config.offset_count) + 1):
                    if base.size == 0:
                        continue
                    offset_distance = config.offset_mm * offset_index
                    shifted = base.copy()
                    normals = np.column_stack((-base[:, 3], base[:, 2]))
                    shifted[:, 0:2] += normals * offset_distance
                    layers[f"offset_{path_index + 1}_{offset_index}"] = shifted
        return layers

    def _generate_boundary_layer(self, paths: Sequence[PatternPath], config: PatternFillConfig) -> Dict[str, np.ndarray]:
        layers: Dict[str, np.ndarray] = {}
        if not config.enable_boundary:
            return layers
        spacing = max(0.2, config.stone_diameter_mm + config.spacing_mm)
        for path_index, path in enumerate(paths):
            if path.closed:
                layers[f"boundary_{path_index + 1}"] = self._sample_polyline(path, spacing, start_offset=0.0)
        return layers

    def _generate_fill_layer(self, bounds: BoundingBox, config: PatternFillConfig) -> Dict[str, np.ndarray]:
        if not config.enable_fill:
            return {}
        points = generate_candidate_points(
            bounds.width,
            bounds.height,
            config.stone_diameter_mm,
            config.spacing_mm,
            config.edge_margin_mm,
            config.fill_layout,
            jitter_mm=0.0,
            seed=config.seed,
        )
        if points.size == 0:
            return {}
        tangent = np.zeros((points.shape[0], 2), dtype=np.float32)
        return {"fill": np.column_stack((points, tangent))}

    def _generate_ray_layer(self, bounds: BoundingBox, safe_mask: np.ndarray, config: PatternFillConfig) -> Dict[str, np.ndarray]:
        if not config.enable_rays:
            return {}
        center_x = bounds.center.x if config.ray_center_mode == "bounds_center" else config.ray_center_x_mm
        center_y = bounds.center.y if config.ray_center_mode == "bounds_center" else config.ray_center_y_mm
        spacing = max(0.2, config.stone_diameter_mm + config.spacing_mm)
        max_length = max(bounds.width, bounds.height) * 1.5
        layers: Dict[str, np.ndarray] = {}
        for ray_index, angle_deg in enumerate(np.linspace(config.ray_angle_start_deg, config.ray_angle_end_deg, num=max(1, config.ray_count), endpoint=False)):
            radians = math.radians(float(angle_deg))
            direction = np.asarray((math.cos(radians), math.sin(radians)), dtype=np.float32)
            samples = []
            distance = 0.0
            while distance <= max_length:
                x_mm = center_x + (direction[0] * distance)
                y_mm = center_y + (direction[1] * distance)
                px = int(round(x_mm * config.preview_ppm))
                py = int(round(y_mm * config.preview_ppm))
                if 0 <= px < safe_mask.shape[1] and 0 <= py < safe_mask.shape[0] and safe_mask[py, px]:
                    samples.append((x_mm, y_mm, direction[0], direction[1]))
                elif distance > config.stone_diameter_mm:
                    break
                distance += spacing
            if samples:
                layers[f"ray_{ray_index + 1}"] = np.asarray(samples, dtype=np.float32)
        return layers

    def generate(
        self,
        bounds: BoundingBox,
        paths: Sequence[PatternPath],
        config: PatternFillConfig,
        progress_controller=None,
    ) -> PatternFillResult:
        local_bounds, local_paths = self._localize_paths(bounds, paths)
        cache_key = self.build_cache_key(local_bounds, local_paths, config)
        cached = self._controller.preview_result(cache_key)
        if cached is not None:
            return cached

        timings: Dict[str, float] = {}

        def timed(name: str, fn):
            import time

            start = time.perf_counter()
            result = fn()
            timings[name] = time.perf_counter() - start
            logger.info("pattern fill stage=%s elapsed=%.4fs", name, timings[name])
            return result

        if progress_controller:
            progress_controller.start_phase("Preparing vector geometry", total=6, current=0, force=True)

        safe_mask = timed("mask_build", lambda: self._build_closed_mask(local_bounds, local_paths, config.preview_ppm))
        if progress_controller:
            progress_controller.update(1, 6, force=True)
        radius_mm = (config.stone_diameter_mm / 2.0) + config.edge_margin_mm
        safe_centers = timed("safe_mask", lambda: self._build_safe_center_mask(safe_mask, radius_mm, config.preview_ppm))
        if progress_controller:
            progress_controller.update(2, 6, force=True)
        curve_layers = timed("curve_generation", lambda: self._generate_curve_layer(local_paths, config))
        boundary_layers = timed("boundary_generation", lambda: self._generate_boundary_layer(local_paths, config))
        fill_layers = timed("fill_generation", lambda: self._generate_fill_layer(local_bounds, config))
        ray_layers = timed("ray_generation", lambda: self._generate_ray_layer(local_bounds, safe_centers, config))
        if progress_controller:
            progress_controller.update(3, 6, force=True)

        occupancy = np.zeros_like(safe_centers, dtype=bool)
        stones: List[PatternStone] = []
        per_layer: Dict[str, int] = {}
        layer_index = 0
        for layer_name, placements in {**boundary_layers, **curve_layers, **fill_layers, **ray_layers}.items():
            placed = self._append_stones(placements, layer_name, layer_index, local_bounds, safe_centers, occupancy, config, stones)
            per_layer[layer_name] = placed
            layer_index += 1
        if progress_controller:
            progress_controller.update(5, 6, force=True)

        per_color: Dict[str, int] = {}
        for stone in stones:
            per_color[stone.color_name] = per_color.get(stone.color_name, 0) + 1

        preview_image, preview_scene = timed(
            "preview_render",
            lambda: self._preview_renderer.render_stones(
                stones,
                local_bounds.width,
                local_bounds.height,
                config.preview_ppm,
                background_rgb=(78, 78, 78),
                render_profile="pattern_fill",
                cache_key=cache_key,
            ),
        )
        if progress_controller:
            progress_controller.update(6, 6, force=True)
        timings["total"] = sum(value for key, value in timings.items() if key != "total")
        result = PatternFillResult(
            stones=stones,
            preview_image=preview_image,
            preview_scene=preview_scene,
            width_mm=local_bounds.width,
            height_mm=local_bounds.height,
            per_color=per_color,
            per_layer=per_layer,
            timings=timings,
            cache_key=cache_key,
        )
        return self._controller.set_preview_result(cache_key, result)
