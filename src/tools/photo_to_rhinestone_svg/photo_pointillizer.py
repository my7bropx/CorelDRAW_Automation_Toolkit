import hashlib
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import current_thread, main_thread
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

from ..common import (
    BackgroundMaskBuilder,
    BackgroundMaskSettings,
    CacheManager,
    ColorQuantizer,
    DecimationSettings,
    FinalRenderer,
    ImageSampler,
    PreviewRenderer,
    PreviewScene,
    ProgressController,
    SizeAssignmentSettings,
    StoneDecimator,
    StoneExporter,
    StoneSizeAssigner,
    ToolController,
    generate_candidate_points,
)

logger = logging.getLogger(__name__)

Color = Tuple[int, int, int]


@dataclass(frozen=True)
class Stone:
    x_mm: float
    y_mm: float
    diameter_mm: float
    color_name: str
    rgb: Color

    @property
    def radius_mm(self) -> float:
        return self.diameter_mm / 2.0


@dataclass
class PointillizerConfig:
    width_mm: float = 120.0
    height_mm: float = 120.0
    stone_diameter_mm: float = 2.8
    gap_mm: float = 0.2
    edge_margin_mm: float = 0.2
    jitter_mm: float = 0.0
    layout: str = "hex"
    sampling_mode: str = "average"
    brightness_only: bool = False
    brightness_invert: bool = False
    gamma: float = 1.0
    contrast: float = 1.0
    brightness: float = 1.0
    alpha_threshold: int = 8
    mask_threshold: int = 128
    preview_ppm: int = 6
    seed: int = 12
    palette_mode: str = "rhinestone"
    palette_name: str = "bright"
    preview_reduction_factor: float = 0.65
    preview_point_cap: int = 25000
    drag_preview_ppm: int = 3
    drag_preview_density_scale: float = 0.35
    drag_preview_point_cap: int = 2200
    drag_preview_detail_boost: float = 1.35
    settled_preview_density_scale: float = 0.7
    settled_preview_point_cap: int = 12000
    performance_mode: bool = True
    output_mode: str = "grouped_color"
    group_output: bool = True
    weld_by_color: bool = False
    export_background: bool = False
    debug_export: bool = False

    remove_background: bool = True
    use_source_alpha: bool = True
    auto_detect_background: bool = True
    background_rgb: Color = (78, 78, 78)
    background_tolerance: int = 28
    feather_px: int = 0
    keep_holes: bool = True

    target_density: float = 1.0
    preserve_edges_strength: float = 0.75
    detail_threshold: float = 0.18
    max_stone_count: int = 0

    size_mode: str = "single"
    allowed_sizes_mm: Tuple[float, ...] = (2.8,)
    edge_detail_sensitivity: float = 0.85
    minimum_spacing_mm: float = 0.2

    palettes: Dict[str, Dict[str, Color]] = field(default_factory=lambda: {
        "bright": {
            "black": (24, 24, 24),
            "blue": (60, 82, 220),
            "cyan": (64, 210, 245),
            "green": (67, 186, 92),
            "red": (222, 63, 60),
            "yellow": (242, 216, 52),
            "pink": (219, 125, 191),
            "white": (244, 244, 244),
        },
        "grayscale": {
            "black": (20, 20, 20),
            "charcoal": (70, 70, 70),
            "gray": (128, 128, 128),
            "silver": (188, 188, 188),
            "white": (245, 245, 245),
        },
        "rhinestone": {
            "jet": (18, 18, 18),
            "sapphire": (44, 82, 205),
            "aquamarine": (60, 201, 214),
            "hyacinth": (220, 88, 62),
            "citrine": (239, 199, 58),
            "crystal": (239, 239, 239),
        },
    })


@dataclass
class PointillizerResult:
    stones: List[Stone]
    width_mm: float
    height_mm: float
    per_color: Dict[str, int]
    preview_image: Image.Image
    timings: Dict[str, float]
    preview_mode: bool
    preview_profile: str
    cache_key: str
    stage_keys: Dict[str, str]
    output_mode: str
    preview_scene: Optional[PreviewScene] = None
    diagnostics: Dict[str, object] = field(default_factory=dict)


class PhotoPointillizerEngine:
    def __init__(self) -> None:
        self._sampler = ImageSampler()
        self._quantizer = ColorQuantizer()
        self._preview_renderer = PreviewRenderer()
        self._exporter = StoneExporter()
        self._mask_builder = BackgroundMaskBuilder()
        self._decimator = StoneDecimator()
        self._size_assigner = StoneSizeAssigner()
        self._cache = CacheManager()
        self._controller = ToolController(self._cache)

    def build_cache_key(
        self,
        photo_path: str,
        config: PointillizerConfig,
        transparent_png: Optional[str] = None,
        mask_path: Optional[str] = None,
        container_signature: str = "",
        preview_mode: bool = False,
        preview_profile: str = "settled",
    ) -> str:
        file_stamp = self._file_stamp(photo_path)
        overlay_stamp = self._file_stamp(transparent_png)
        mask_stamp = self._file_stamp(mask_path)
        config_payload = {
            key: value
            for key, value in vars(config).items()
            if key != "palettes"
        }
        if preview_mode:
            for preview_irrelevant in ("output_mode", "group_output", "weld_by_color", "export_background", "debug_export"):
                config_payload.pop(preview_irrelevant, None)

        payload = {
            "photo": photo_path,
            "photo_stamp": file_stamp,
            "transparent_png": transparent_png,
            "transparent_png_stamp": overlay_stamp,
            "mask_path": mask_path,
            "mask_stamp": mask_stamp,
            "container_signature": container_signature,
            "preview_mode": preview_mode,
            "preview_profile": preview_profile if preview_mode else "final",
            "config": config_payload,
        }
        return self._cache.build_key("pointillizer_result", payload)

    def _file_stamp(self, path: Optional[str]) -> str:
        if not path:
            return ""
        try:
            stat = Path(path).stat()
            return f"{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            return "missing"

    def _effective_config(self, config: PointillizerConfig, preview_mode: bool, preview_profile: str) -> PointillizerConfig:
        if not preview_mode:
            return config
        preview = PointillizerConfig(**vars(config))
        if preview_profile == "drag":
            preview.preview_ppm = max(2, min(config.preview_ppm, int(config.drag_preview_ppm)))
            preview.sampling_mode = "nearest"
            preview.target_density = min(config.target_density, max(0.18, config.target_density * config.drag_preview_density_scale))
            preview.detail_threshold = min(1.0, max(config.detail_threshold, config.detail_threshold * config.drag_preview_detail_boost))
            cap = int(config.drag_preview_point_cap)
            preview.max_stone_count = min(config.max_stone_count, cap) if config.max_stone_count else cap
            preview.size_mode = "single"
            preview.allowed_sizes_mm = (float(config.stone_diameter_mm),)
            if config.performance_mode:
                preview.preview_ppm = min(preview.preview_ppm, 2)
                preview.target_density = min(preview.target_density, 0.22)
                preview.max_stone_count = min(preview.max_stone_count, 1500) if preview.max_stone_count else 1500
        else:
            preview.preview_ppm = max(4, min(config.preview_ppm, int(round(config.preview_ppm * config.preview_reduction_factor)) or config.preview_ppm))
            preview.target_density = min(config.target_density, max(0.35, config.target_density * config.settled_preview_density_scale))
            cap = int(config.settled_preview_point_cap)
            preview.max_stone_count = min(config.max_stone_count, cap) if config.max_stone_count else cap
            if config.performance_mode and preview.size_mode != "single":
                preview.allowed_sizes_mm = tuple(sorted({min(config.allowed_sizes_mm), max(config.allowed_sizes_mm)}))
        return preview

    def _stage(self, timings: Dict[str, float], stage: str, func):
        start = time.perf_counter()
        result = func()
        timings[stage] = time.perf_counter() - start
        logger.info("stage %s finished in %.4fs", stage, timings[stage])
        return result

    def _stage_key(self, stage: str, payload: Dict[str, object]) -> str:
        return self._cache.build_key(stage, payload)

    def _throw_if_cancelled(self, progress: Optional[ProgressController]) -> None:
        if progress:
            progress.throw_if_cancelled()

    def _load_source(
        self,
        photo_path: str,
        config: PointillizerConfig,
        progress: Optional[ProgressController],
        stage_keys: Dict[str, str],
    ) -> np.ndarray:
        stage_key = self._stage_key("load_image", {
            "photo_path": photo_path,
            "photo_stamp": self._file_stamp(photo_path),
            "width_mm": config.width_mm,
            "height_mm": config.height_mm,
            "ppm": config.preview_ppm,
            "gamma": config.gamma,
            "contrast": config.contrast,
            "brightness": config.brightness,
        })
        stage_keys["load_image"] = stage_key
        cached = self._cache.get("load_image", stage_key)
        if cached is not None:
            return cached.copy()

        if progress:
            progress.start_phase("Loading image", total=1, current=0, force=True)
        rgba = self._sampler.fit_rgba(photo_path, config.width_mm, config.height_mm, config.preview_ppm)
        rgba = self._sampler.tone(rgba, config.gamma, config.contrast, config.brightness)
        if progress:
            progress.update(1, 1, force=True)
        return self._cache.set("load_image", stage_key, rgba).copy()

    def _build_mask(
        self,
        rgba: np.ndarray,
        config: PointillizerConfig,
        transparent_png: Optional[str],
        mask_path: Optional[str],
        progress: Optional[ProgressController],
        stage_keys: Dict[str, str],
    ) -> np.ndarray:
        settings = BackgroundMaskSettings(
            remove_background=config.remove_background,
            use_source_alpha=config.use_source_alpha,
            auto_detect=config.auto_detect_background,
            background_rgb=config.background_rgb,
            tolerance=config.background_tolerance,
            feather_px=config.feather_px,
            keep_holes=config.keep_holes,
            alpha_threshold=config.alpha_threshold,
            mask_threshold=config.mask_threshold,
        )
        stage_key = self._stage_key("background_mask", {
            "rgba_shape": rgba.shape,
            "settings": vars(settings),
            "transparent_png": transparent_png,
            "transparent_png_stamp": self._file_stamp(transparent_png),
            "mask_path": mask_path,
            "mask_stamp": self._file_stamp(mask_path),
        })
        stage_keys["background_mask"] = stage_key
        cached = self._cache.get("background_mask", stage_key)
        if cached is not None:
            return cached.copy()

        if progress:
            progress.start_phase("Removing background", total=1, current=0, force=True)
        mask = self._mask_builder.build_mask(rgba, settings, transparent_png=transparent_png, mask_path=mask_path)
        if progress:
            progress.update(1, 1, force=True)
        return self._cache.set("background_mask", stage_key, mask).copy()

    def _generate_layout(
        self,
        config: PointillizerConfig,
        progress: Optional[ProgressController],
        stage_keys: Dict[str, str],
    ) -> np.ndarray:
        base_diameter = min(config.allowed_sizes_mm) if config.size_mode != "single" and config.allowed_sizes_mm else config.stone_diameter_mm
        stage_key = self._stage_key("stone_layout", {
            "width_mm": config.width_mm,
            "height_mm": config.height_mm,
            "stone_diameter_mm": base_diameter,
            "gap_mm": config.gap_mm,
            "edge_margin_mm": config.edge_margin_mm,
            "jitter_mm": config.jitter_mm,
            "layout": config.layout,
            "seed": config.seed,
        })
        stage_keys["stone_layout"] = stage_key
        cached = self._cache.get("stone_layout", stage_key)
        if cached is not None:
            return cached.copy()

        if progress:
            progress.start_phase("Generating layout", total=1, current=0, force=True)
        points = generate_candidate_points(
            config.width_mm,
            config.height_mm,
            base_diameter,
            config.gap_mm,
            config.edge_margin_mm,
            config.layout,
            jitter_mm=config.jitter_mm,
            seed=config.seed,
        )
        if progress:
            progress.update(1, 1, force=True)
        return self._cache.set("stone_layout", stage_key, points).copy()

    def _filter_layout(
        self,
        points: np.ndarray,
        allowed_mask: np.ndarray,
        config: PointillizerConfig,
        inside_cb: Optional[Callable[[float, float, float], bool]],
        inside_mask: Optional[np.ndarray],
        progress: Optional[ProgressController],
        stage_keys: Dict[str, str],
    ) -> np.ndarray:
        stage_key = self._stage_key("layout_filter", {
            "layout_key": stage_keys.get("stone_layout"),
            "mask_key": stage_keys.get("background_mask"),
            "radius_mm": (config.stone_diameter_mm / 2.0) + config.edge_margin_mm,
            "inside_cb": bool(inside_cb),
            "inside_mask": bool(inside_mask is not None),
        })
        stage_keys["layout_filter"] = stage_key
        cached = self._cache.get("layout_filter", stage_key)
        if cached is not None:
            return cached.copy()

        filtered = self._sampler.filter_points(
            points,
            allowed_mask,
            (config.stone_diameter_mm / 2.0) + config.edge_margin_mm,
            config.preview_ppm,
            inside_cb=inside_cb,
            inside_mask=inside_mask,
            progress=progress,
        )
        return self._cache.set("layout_filter", stage_key, filtered).copy()

    def _decimate_layout(
        self,
        points: np.ndarray,
        rgba: np.ndarray,
        config: PointillizerConfig,
        progress: Optional[ProgressController],
        stage_keys: Dict[str, str],
    ) -> Tuple[np.ndarray, np.ndarray]:
        detail_map = self._decimator.build_detail_map(rgba)
        stage_keys["detail_map"] = self._stage_key("detail_map", {
            "load_key": stage_keys.get("load_image"),
        })
        stage_key = self._stage_key("decimation", {
            "layout_filter": stage_keys.get("layout_filter"),
            "target_density": config.target_density,
            "preserve_edges_strength": config.preserve_edges_strength,
            "detail_threshold": config.detail_threshold,
            "max_stone_count": config.max_stone_count,
            "seed": config.seed,
        })
        stage_keys["decimation"] = stage_key
        cached = self._cache.get("decimation", stage_key)
        if cached is not None:
            return cached.copy(), detail_map

        settings = DecimationSettings(
            target_density=config.target_density,
            preserve_edges_strength=config.preserve_edges_strength,
            detail_threshold=config.detail_threshold,
            max_stone_count=config.max_stone_count,
            seed=config.seed,
        )
        decimated = self._decimator.decimate(points, detail_map, config.preview_ppm, settings, progress=progress)
        return self._cache.set("decimation", stage_key, decimated).copy(), detail_map

    def _sample_colors(
        self,
        rgba: np.ndarray,
        points: np.ndarray,
        config: PointillizerConfig,
        progress: Optional[ProgressController],
        stage_keys: Dict[str, str],
    ) -> np.ndarray:
        sample_diameter = min(config.allowed_sizes_mm) if config.size_mode != "single" and config.allowed_sizes_mm else config.stone_diameter_mm
        stage_key = self._stage_key("image_sampling", {
            "load_key": stage_keys.get("load_image"),
            "decimation_key": stage_keys.get("decimation"),
            "stone_diameter_mm": sample_diameter,
            "ppm": config.preview_ppm,
            "sampling_mode": config.sampling_mode,
            "alpha_threshold": config.alpha_threshold,
        })
        stage_keys["image_sampling"] = stage_key
        cached = self._cache.get("image_sampling", stage_key)
        if cached is not None:
            return cached.copy()

        samples = self._sampler.sample_colors(
            rgba,
            points,
            sample_diameter / 2.0,
            config.preview_ppm,
            config.sampling_mode,
            config.alpha_threshold,
            progress=progress,
        )
        return self._cache.set("image_sampling", stage_key, samples).copy()

    def _map_colors(
        self,
        rgba: np.ndarray,
        samples: np.ndarray,
        config: PointillizerConfig,
        stage_keys: Dict[str, str],
    ) -> Tuple[np.ndarray, np.ndarray]:
        stage_key = self._stage_key("color_mapping", {
            "sampling_key": stage_keys.get("image_sampling"),
            "palette_mode": config.palette_mode,
            "palette_name": config.palette_name,
            "brightness_only": config.brightness_only,
            "brightness_invert": config.brightness_invert,
        })
        stage_keys["color_mapping"] = stage_key
        cached = self._cache.get("color_mapping", stage_key)
        if cached is not None:
            return cached[0].copy(), cached[1].copy()

        palette = config.palettes[config.palette_name]
        dominant = self._quantizer.dominant_name(rgba, palette)
        labels, colors = self._quantizer.map_samples(
            samples,
            palette,
            config.palette_mode,
            brightness_only=config.brightness_only,
            brightness_invert=config.brightness_invert,
            dominant=dominant,
        )
        self._cache.set("color_mapping", stage_key, (labels, colors))
        return labels.copy(), colors.copy()

    def _assign_sizes(
        self,
        points: np.ndarray,
        labels: np.ndarray,
        colors: np.ndarray,
        detail_map: np.ndarray,
        allowed_mask: np.ndarray,
        config: PointillizerConfig,
        progress: Optional[ProgressController],
        stage_keys: Dict[str, str],
        coverage_recovery: bool,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        stage_key = self._stage_key("size_assignment", {
            "layout_filter_key": stage_keys.get("layout_filter"),
            "decimation_key": stage_keys.get("decimation"),
            "color_key": stage_keys.get("color_mapping"),
            "point_count": int(points.shape[0]),
            "size_mode": config.size_mode,
            "allowed_sizes_mm": list(config.allowed_sizes_mm),
            "edge_detail_sensitivity": config.edge_detail_sensitivity,
            "minimum_spacing_mm": config.minimum_spacing_mm,
            "edge_margin_mm": config.edge_margin_mm,
            "coverage_recovery": coverage_recovery,
        })
        stage_keys["size_assignment"] = stage_key
        cached = self._cache.get("size_assignment", stage_key)
        if cached is not None:
            return (
                cached[0].copy(),
                cached[1].copy(),
                cached[2].copy(),
                cached[3].copy(),
            )

        settings = SizeAssignmentSettings(
            size_mode=config.size_mode,
            allowed_sizes_mm=config.allowed_sizes_mm,
            edge_detail_sensitivity=config.edge_detail_sensitivity,
            minimum_spacing_mm=config.minimum_spacing_mm,
            favor_large_in_flat_areas=True,
            edge_margin_mm=config.edge_margin_mm,
            coverage_recovery=coverage_recovery,
        )
        placed = self._size_assigner.place_stones(
            points,
            labels,
            colors,
            detail_map,
            allowed_mask,
            config.preview_ppm,
            settings,
            progress=progress,
        )
        self._cache.set("size_assignment", stage_key, placed)
        return (
            placed[0].copy(),
            placed[1].copy(),
            placed[2].copy(),
            placed[3].copy(),
        )

    def _build_stones(
        self,
        points: np.ndarray,
        labels: np.ndarray,
        colors: np.ndarray,
        sizes: np.ndarray,
    ) -> Tuple[List[Stone], Dict[str, int]]:
        stones: List[Stone] = []
        per_color: Dict[str, int] = {}
        for point, label, color, diameter in zip(points, labels, colors, sizes):
            stone = Stone(
                x_mm=float(point[0]),
                y_mm=float(point[1]),
                diameter_mm=float(diameter),
                color_name=str(label),
                rgb=(int(color[0]), int(color[1]), int(color[2])),
            )
            stones.append(stone)
            per_color[stone.color_name] = per_color.get(stone.color_name, 0) + 1
        return stones, per_color

    def _build_preview(
        self,
        stones: Sequence[Stone],
        config: PointillizerConfig,
        progress: Optional[ProgressController],
        stage_keys: Dict[str, str],
        preview_profile: str,
        cache_key: str,
    ) -> Tuple[Image.Image, PreviewScene]:
        stage_key = self._stage_key("preview_render", {
            "color_key": stage_keys.get("color_mapping"),
            "size_key": stage_keys.get("size_assignment"),
            "ppm": config.preview_ppm,
            "width_mm": config.width_mm,
            "height_mm": config.height_mm,
            "preview_profile": preview_profile,
        })
        stage_keys["preview_render"] = stage_key
        cached = self._cache.get("preview_render", stage_key)
        if cached is not None:
            cached_image, cached_scene = cached
            return cached_image.copy(), cached_scene

        if progress:
            progress.start_phase("Building preview", total=max(1, len(stones)), current=max(1, len(stones)), force=True)
        image, scene = self._preview_renderer.render_stones(
            stones,
            config.width_mm,
            config.height_mm,
            config.preview_ppm,
            background_rgb=config.background_rgb,
            render_profile=preview_profile,
            cache_key=cache_key,
        )
        if progress:
            progress.complete(force=True)
        self._cache.set("preview_render", stage_key, (image, scene))
        return image.copy(), scene

    def _generate_internal(
        self,
        photo_path: str,
        config: PointillizerConfig,
        transparent_png: Optional[str] = None,
        mask_path: Optional[str] = None,
        inside_cb: Optional[Callable[[float, float, float], bool]] = None,
        inside_mask: Optional[np.ndarray] = None,
        progress_controller: Optional[ProgressController] = None,
        preview_mode: bool = False,
        container_signature: str = "",
        preview_profile: str = "settled",
    ) -> PointillizerResult:
        active = self._effective_config(config, preview_mode, preview_profile)
        stage_keys: Dict[str, str] = {}
        timings: Dict[str, float] = {}
        cache_before = self._cache.snapshot_stats()
        result_key = self.build_cache_key(
            photo_path,
            config,
            transparent_png=transparent_png,
            mask_path=mask_path,
            container_signature=container_signature,
            preview_mode=preview_mode,
            preview_profile=preview_profile,
        )

        cached_result = self._controller.preview_result(result_key) if preview_mode else self._controller.final_result(result_key)
        if cached_result is not None:
            logger.info("result cache hit %s", result_key)
            return cached_result

        thread_name = current_thread().name
        logger.info(
            "pointillizer start mode=%s profile=%s thread=%s on_ui_thread=%s performance_mode=%s",
            "preview" if preview_mode else "final",
            preview_profile,
            thread_name,
            current_thread() is main_thread(),
            active.performance_mode,
        )

        rgba = self._stage(timings, "image_load", lambda: self._load_source(photo_path, active, progress_controller, stage_keys))
        self._throw_if_cancelled(progress_controller)
        allowed_mask = self._stage(
            timings,
            "background_mask_build",
            lambda: self._build_mask(rgba, active, transparent_png, mask_path, progress_controller, stage_keys),
        )
        self._throw_if_cancelled(progress_controller)
        points = self._stage(timings, "layout_generation", lambda: self._generate_layout(active, progress_controller, stage_keys))
        self._throw_if_cancelled(progress_controller)
        filtered = self._stage(
            timings,
            "layout_filtering",
            lambda: self._filter_layout(points, allowed_mask, active, inside_cb, inside_mask, progress_controller, stage_keys),
        )
        self._throw_if_cancelled(progress_controller)
        decimated, detail_map = self._stage(
            timings,
            "decimation",
            lambda: self._decimate_layout(filtered, rgba, active, progress_controller, stage_keys),
        )
        self._throw_if_cancelled(progress_controller)
        candidate_points = decimated if (preview_mode or active.size_mode == "single") else filtered
        samples = self._stage(
            timings,
            "image_sampling",
            lambda: self._sample_colors(rgba, candidate_points, active, progress_controller, stage_keys),
        )
        self._throw_if_cancelled(progress_controller)
        valid_mask = samples[:, 3] >= active.alpha_threshold if samples.size else np.zeros((0,), dtype=bool)
        candidate_points = candidate_points[valid_mask]
        samples = samples[valid_mask]
        labels, colors = self._stage(
            timings,
            "color_mapping",
            lambda: self._map_colors(rgba, samples, active, stage_keys),
        )
        self._throw_if_cancelled(progress_controller)
        coverage_recovery = not preview_mode or (preview_profile not in {"drag", "settled"} and not active.performance_mode)
        placement_points, placement_labels, placement_colors, sizes = self._stage(
            timings,
            "size_assignment_and_placement",
            lambda: self._assign_sizes(
                candidate_points,
                labels,
                colors,
                detail_map,
                allowed_mask,
                active,
                progress_controller,
                stage_keys,
                coverage_recovery=coverage_recovery,
            ),
        )
        self._throw_if_cancelled(progress_controller)
        stones, per_color = self._stage(
            timings,
            "stone_build",
            lambda: self._build_stones(placement_points, placement_labels, placement_colors, sizes),
        )
        preview_image, preview_scene = self._stage(
            timings,
            "preview_render",
            lambda: self._build_preview(stones, active, progress_controller, stage_keys, preview_profile, result_key),
        )
        timings["total"] = sum(value for key, value in timings.items() if key != "total")
        cache_after = self._cache.snapshot_stats()
        cache_delta = {
            "hits": int(cache_after["hits"] - cache_before["hits"]),
            "misses": int(cache_after["misses"] - cache_before["misses"]),
            "stage_hits": {
                stage: int(cache_after["stage_hits"].get(stage, 0) - cache_before["stage_hits"].get(stage, 0))
                for stage in set(cache_after["stage_hits"]) | set(cache_before["stage_hits"])
                if int(cache_after["stage_hits"].get(stage, 0) - cache_before["stage_hits"].get(stage, 0)) != 0
            },
            "stage_misses": {
                stage: int(cache_after["stage_misses"].get(stage, 0) - cache_before["stage_misses"].get(stage, 0))
                for stage in set(cache_after["stage_misses"]) | set(cache_before["stage_misses"])
                if int(cache_after["stage_misses"].get(stage, 0) - cache_before["stage_misses"].get(stage, 0)) != 0
            },
        }
        slowest_stage = max((key for key in timings.keys() if key != "total"), key=lambda key: timings[key], default="")

        logger.info(
            "Pointillizer timings (%s/%s) stones=%s slowest=%s cache_hits=%s cache_misses=%s: %s",
            "preview" if preview_mode else "final",
            preview_profile,
            len(stones),
            slowest_stage,
            cache_delta["hits"],
            cache_delta["misses"],
            ", ".join(f"{name}={value:.4f}s" for name, value in timings.items()),
        )

        result = PointillizerResult(
            stones=stones,
            width_mm=active.width_mm,
            height_mm=active.height_mm,
            per_color=per_color,
            preview_image=preview_image,
            timings=timings,
            preview_mode=preview_mode,
            preview_profile=preview_profile,
            cache_key=result_key,
            stage_keys=stage_keys,
            output_mode=active.output_mode,
            preview_scene=preview_scene,
            diagnostics={
                "slowest_stage": slowest_stage,
                "cache": cache_delta,
                "stone_count": len(stones),
                "multi_size_active": active.size_mode != "single",
                "background_removal_active": bool(active.remove_background or active.use_source_alpha),
                "performance_mode": active.performance_mode,
                "thread_name": thread_name,
                "on_ui_thread": current_thread() is main_thread(),
                "coverage_recovery": coverage_recovery,
            },
        )

        if preview_mode:
            return self._controller.set_preview_result(result_key, result)
        return self._controller.set_final_result(result_key, result)

    def generate_preview(
        self,
        photo_path: str,
        config: PointillizerConfig,
        transparent_png: Optional[str] = None,
        mask_path: Optional[str] = None,
        inside_cb: Optional[Callable[[float, float, float], bool]] = None,
        inside_mask: Optional[np.ndarray] = None,
        progress_controller: Optional[ProgressController] = None,
        preview_profile: str = "settled",
        **_,
    ) -> PointillizerResult:
        return self._generate_internal(
            photo_path,
            config,
            transparent_png=transparent_png,
            mask_path=mask_path,
            inside_cb=inside_cb,
            inside_mask=inside_mask,
            progress_controller=progress_controller,
            preview_mode=True,
            preview_profile=preview_profile,
        )

    def generate_final(
        self,
        photo_path: str,
        config: PointillizerConfig,
        transparent_png: Optional[str] = None,
        mask_path: Optional[str] = None,
        inside_cb: Optional[Callable[[float, float, float], bool]] = None,
        inside_mask: Optional[np.ndarray] = None,
        progress_controller: Optional[ProgressController] = None,
        container_signature: str = "",
        **_,
    ) -> PointillizerResult:
        return self._generate_internal(
            photo_path,
            config,
            transparent_png=transparent_png,
            mask_path=mask_path,
            inside_cb=inside_cb,
            inside_mask=inside_mask,
            progress_controller=progress_controller,
            preview_mode=False,
            container_signature=container_signature,
            preview_profile="final",
        )

    def export_bundle(
        self,
        result: PointillizerResult,
        base_path: str,
        background_rgb: Color = (78, 78, 78),
        include_background: bool = False,
    ) -> None:
        self._exporter.export_bundle(
            result.stones,
            result.width_mm,
            result.height_mm,
            result.preview_image,
            base_path,
            background_rgb=background_rgb,
            include_background=include_background,
        )
