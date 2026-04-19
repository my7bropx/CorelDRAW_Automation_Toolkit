import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
import svgwrite
from PIL import Image, ImageDraw

from .cache_manager import CacheManager

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StructuralPath:
    points: Tuple[Tuple[float, float], ...]
    closed: bool = False


@dataclass
class StructuralDetailConfig:
    width_mm: float
    height_mm: float
    preview_ppm: int = 6
    drag_preview_ppm: int = 3
    extraction_mode: str = "balanced"
    structure_strength: float = 0.72
    min_motif_size: int = 80
    symmetry_enabled: bool = True
    symmetry_influence: float = 0.65
    border_band_priority: float = 0.8
    center_motif_priority: float = 0.7
    curve_smoothness: float = 0.45
    simplification_tolerance: float = 0.5
    merge_distance_mm: float = 1.8
    decorative_detail_retention: float = 0.35
    silhouette_priority: float = 0.95
    minimum_curve_length_mm: float = 8.0
    performance_mode: bool = True


@dataclass
class StructuralDetailResult:
    paths: List[StructuralPath]
    preview_image: Image.Image
    width_mm: float
    height_mm: float
    timings: Dict[str, float]
    cache_key: str
    diagnostics: Dict[str, object] = field(default_factory=dict)


class StructuralDetailExtractor:
    def __init__(self) -> None:
        self._cache = CacheManager()
        self._preview_cache: Dict[str, StructuralDetailResult] = {}

    def _file_stamp(self, path: str) -> str:
        try:
            stat = Path(path).stat()
            return f"{stat.st_mtime_ns}:{stat.st_size}"
        except OSError:
            return "missing"

    def build_cache_key(self, photo_path: str, config: StructuralDetailConfig, preview_profile: str = "settled") -> str:
        return self._cache.build_key(
            "ornamental_structure",
            {
                "photo_path": photo_path,
                "photo_stamp": self._file_stamp(photo_path),
                "preview_profile": preview_profile,
                "config": vars(config),
            },
        )

    def _effective_config(self, config: StructuralDetailConfig, preview_profile: str) -> StructuralDetailConfig:
        active = StructuralDetailConfig(**vars(config))
        if preview_profile == "drag":
            active.preview_ppm = min(config.preview_ppm, config.drag_preview_ppm)
            active.min_motif_size = int(max(config.min_motif_size, config.min_motif_size * (1.8 if config.performance_mode else 1.35)))
            active.structure_strength = min(1.0, config.structure_strength + (0.08 if config.performance_mode else 0.03))
            active.decorative_detail_retention = max(0.05, config.decorative_detail_retention * (0.55 if config.performance_mode else 0.75))
            active.merge_distance_mm = max(config.merge_distance_mm, config.merge_distance_mm * 1.2)
            active.simplification_tolerance = max(config.simplification_tolerance, config.simplification_tolerance * 1.35)
        elif config.performance_mode:
            active.preview_ppm = max(4, min(config.preview_ppm, 5))
            active.min_motif_size = int(max(config.min_motif_size, config.min_motif_size * 1.2))
            active.decorative_detail_retention = max(0.08, config.decorative_detail_retention * 0.85)
        return active

    def _stage(self, timings: Dict[str, float], name: str, fn):
        started = time.perf_counter()
        result = fn()
        timings[name] = time.perf_counter() - started
        logger.info("ornamental stage=%s elapsed=%.4fs", name, timings[name])
        return result

    def _get_or_set(self, stage: str, key: str, builder):
        cached = self._cache.get(stage, key)
        if cached is not None:
            return cached
        return self._cache.set(stage, key, builder())

    def _load_image(self, photo_path: str, config: StructuralDetailConfig) -> Tuple[np.ndarray, np.ndarray]:
        size = (
            max(1, int(round(config.width_mm * config.preview_ppm))),
            max(1, int(round(config.height_mm * config.preview_ppm))),
        )
        image = Image.open(photo_path).convert("RGB").resize(size, Image.Resampling.LANCZOS)
        rgb = np.asarray(image, dtype=np.uint8)
        gray = np.asarray(image.convert("L"), dtype=np.uint8)
        return rgb, gray

    def _largest_component(self, mask: np.ndarray) -> np.ndarray:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
        if count <= 1:
            return mask.astype(bool)
        largest_index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        return labels == largest_index

    def _isolate_subject(self, gray: np.ndarray, config: StructuralDetailConfig) -> Tuple[np.ndarray, float]:
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        corners = np.concatenate(
            [
                blurred[: max(1, blurred.shape[0] // 10), : max(1, blurred.shape[1] // 10)].ravel(),
                blurred[: max(1, blurred.shape[0] // 10), -max(1, blurred.shape[1] // 10):].ravel(),
                blurred[-max(1, blurred.shape[0] // 10):, : max(1, blurred.shape[1] // 10)].ravel(),
                blurred[-max(1, blurred.shape[0] // 10):, -max(1, blurred.shape[1] // 10):].ravel(),
            ]
        )
        background_brightness = float(np.mean(corners))
        _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        fg_ratio = float(np.mean(otsu > 0))
        if background_brightness >= 127.0:
            candidate = gray < int(np.clip(background_brightness - 12, 0, 255))
            if fg_ratio < 0.42:
                candidate = candidate | (otsu == 0)
        else:
            candidate = gray > int(np.clip(background_brightness + 12, 0, 255))
            if fg_ratio < 0.42:
                candidate = candidate | (otsu > 0)
        kernel = np.ones((5, 5), dtype=np.uint8)
        candidate = cv2.morphologyEx(candidate.astype(np.uint8), cv2.MORPH_CLOSE, kernel) > 0
        candidate = cv2.morphologyEx(candidate.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8)) > 0
        candidate = self._largest_component(candidate)
        return candidate.astype(bool), background_brightness

    def _skeletonize(self, mask: np.ndarray) -> np.ndarray:
        image = (mask.astype(np.uint8) * 255).copy()
        skeleton = np.zeros_like(image)
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        while True:
            eroded = cv2.erode(image, kernel)
            opened = cv2.dilate(eroded, kernel)
            skeleton = cv2.bitwise_or(skeleton, cv2.subtract(image, opened))
            image = eroded
            if cv2.countNonZero(image) == 0:
                break
        return skeleton > 0

    def _extract_ornament_map(self, gray: np.ndarray, subject_mask: np.ndarray, background_brightness: float, config: StructuralDetailConfig) -> np.ndarray:
        masked_values = gray[subject_mask]
        if masked_values.size == 0:
            return np.zeros_like(gray, dtype=bool)
        subject_mean = float(np.mean(masked_values))
        bright_subject = subject_mean > background_brightness
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        tophat = cv2.morphologyEx(blur, cv2.MORPH_TOPHAT, np.ones((11, 11), dtype=np.uint8))
        blackhat = cv2.morphologyEx(blur, cv2.MORPH_BLACKHAT, np.ones((11, 11), dtype=np.uint8))
        detail_bias = np.clip(config.decorative_detail_retention, 0.0, 1.0)
        if bright_subject:
            base_threshold = float(np.quantile(masked_values, max(0.35, 0.82 - (detail_bias * 0.32))))
            ornament = (gray >= base_threshold) | (tophat >= np.quantile(tophat[subject_mask], max(0.55, 0.86 - (detail_bias * 0.28))))
        else:
            base_threshold = float(np.quantile(masked_values, min(0.65, 0.18 + ((1.0 - detail_bias) * 0.22))))
            ornament = (gray <= base_threshold) | (blackhat >= np.quantile(blackhat[subject_mask], max(0.55, 0.86 - (detail_bias * 0.28))))
        ornament &= subject_mask
        close_size = 3 if config.extraction_mode == "full" else 5
        ornament = cv2.morphologyEx(ornament.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((close_size, close_size), dtype=np.uint8)) > 0
        ornament = cv2.morphologyEx(ornament.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8)) > 0
        return ornament

    def _band_rows(self, mask: np.ndarray, config: StructuralDetailConfig) -> np.ndarray:
        row_density = np.mean(mask.astype(np.float32), axis=1)
        if row_density.size == 0:
            return np.zeros((0,), dtype=bool)
        smooth = cv2.GaussianBlur(row_density.reshape((-1, 1)), (1, 15), 0).ravel()
        threshold = float(np.quantile(smooth, max(0.55, 0.82 - (config.border_band_priority * 0.28))))
        return smooth >= threshold

    def _component_features(
        self,
        labels: np.ndarray,
        stats: np.ndarray,
        index: int,
        axis_x: float,
        band_rows: np.ndarray,
        subject_boundary_distance: np.ndarray,
        config: StructuralDetailConfig,
    ) -> Dict[str, float]:
        component_mask = labels == index
        ys, xs = np.nonzero(component_mask)
        if xs.size == 0:
            return {}
        area = float(stats[index, cv2.CC_STAT_AREA])
        min_x = float(stats[index, cv2.CC_STAT_LEFT])
        min_y = float(stats[index, cv2.CC_STAT_TOP])
        width = float(stats[index, cv2.CC_STAT_WIDTH])
        height = float(stats[index, cv2.CC_STAT_HEIGHT])
        centroid_x = float(np.mean(xs))
        centroid_y = float(np.mean(ys))
        border_distance = float(np.mean(subject_boundary_distance[component_mask])) if np.any(component_mask) else 0.0
        center_distance = abs(centroid_x - axis_x)
        center_score = 1.0 - min(1.0, center_distance / max(1.0, labels.shape[1] * 0.5))
        band_score = float(np.mean(band_rows[ys])) if ys.size > 0 and band_rows.size > 0 else 0.0
        mirrored = np.flip(component_mask, axis=1)
        symmetry_overlap = float(np.count_nonzero(component_mask & mirrored)) / max(1.0, float(np.count_nonzero(component_mask | mirrored)))
        contour = cv2.findContours(component_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0]
        perimeter = float(cv2.arcLength(contour[0], closed=False)) if contour else 0.0
        smoothness = (perimeter / max(1.0, math.sqrt(area))) if perimeter > 0 else 0.0
        length_score = min(1.0, perimeter / max(8.0, labels.shape[0] * 0.18))
        area_score = min(1.0, area / max(16.0, float(config.min_motif_size) * 2.5))
        compactness = float(width * height) / max(1.0, area)
        return {
            "index": float(index),
            "area": area,
            "centroid_x": centroid_x,
            "centroid_y": centroid_y,
            "width": width,
            "height": height,
            "min_x": min_x,
            "min_y": min_y,
            "length_score": length_score,
            "area_score": area_score,
            "center_score": center_score,
            "band_score": band_score,
            "symmetry_score": symmetry_overlap,
            "border_score": 1.0 - min(1.0, border_distance / max(1.0, labels.shape[0] * 0.18)),
            "smooth_score": 1.0 / max(1.0, smoothness),
            "compactness_score": 1.0 / max(1.0, compactness),
        }

    def _mode_threshold(self, config: StructuralDetailConfig) -> float:
        if config.extraction_mode == "major":
            return 0.68
        if config.extraction_mode == "full":
            return 0.34
        return 0.48

    def _rank_components(self, ornament_mask: np.ndarray, subject_mask: np.ndarray, config: StructuralDetailConfig) -> Tuple[np.ndarray, Dict[str, float]]:
        skeleton = self._skeletonize(ornament_mask)
        if not np.any(skeleton):
            return np.zeros_like(ornament_mask, dtype=bool), {"components": 0.0, "selected_components": 0.0, "axis_x": ornament_mask.shape[1] / 2.0}
        distance_to_boundary = cv2.distanceTransform(subject_mask.astype(np.uint8), cv2.DIST_L2, 5)
        band_rows = self._band_rows(ornament_mask, config)
        axis_x = float(np.mean(np.nonzero(subject_mask)[1])) if np.any(subject_mask) else ornament_mask.shape[1] / 2.0
        count, labels, stats, _ = cv2.connectedComponentsWithStats(ornament_mask.astype(np.uint8), connectivity=8)
        selected = np.zeros_like(ornament_mask, dtype=bool)
        component_scores: List[float] = []
        selected_components = 0
        for index in range(1, count):
            if int(stats[index, cv2.CC_STAT_AREA]) < max(4, int(config.min_motif_size * 0.25)):
                continue
            features = self._component_features(labels, stats, index, axis_x, band_rows, distance_to_boundary, config)
            if not features:
                continue
            score = (
                features["length_score"] * (0.26 + (config.structure_strength * 0.22))
                + features["area_score"] * 0.18
                + features["smooth_score"] * 0.12
                + features["symmetry_score"] * config.symmetry_influence * 0.18
                + features["band_score"] * config.border_band_priority * 0.16
                + features["center_score"] * config.center_motif_priority * 0.1
                + features["border_score"] * config.silhouette_priority * 0.12
                + features["compactness_score"] * 0.06
            )
            score += config.decorative_detail_retention * 0.08
            component_scores.append(score)
            if score >= self._mode_threshold(config):
                selected |= labels == index
                selected_components += 1

        if config.symmetry_enabled and np.any(selected):
            mirrored = np.flip(selected, axis=1)
            selected |= (mirrored & ornament_mask)

        metrics = {
            "components": float(max(0, count - 1)),
            "selected_components": float(selected_components),
            "axis_x": axis_x,
            "avg_component_score": float(np.mean(component_scores)) if component_scores else 0.0,
        }
        return selected, metrics

    def _build_silhouette_mask(self, subject_mask: np.ndarray, config: StructuralDetailConfig) -> np.ndarray:
        if config.silhouette_priority <= 0.05:
            return np.zeros_like(subject_mask, dtype=bool)
        contour_mask = cv2.morphologyEx(subject_mask.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), dtype=np.uint8)) > 0
        if config.extraction_mode == "major":
            contour_mask = cv2.dilate(contour_mask.astype(np.uint8), np.ones((3, 3), dtype=np.uint8), iterations=1) > 0
        return contour_mask

    def _build_center_spine(self, selected_mask: np.ndarray, subject_mask: np.ndarray, axis_x: float, config: StructuralDetailConfig) -> np.ndarray:
        if config.center_motif_priority <= 0.1:
            return np.zeros_like(selected_mask, dtype=bool)
        line_half_width = max(1, int(round(config.merge_distance_mm * config.preview_ppm * 0.35)))
        center_mask = np.zeros_like(selected_mask, dtype=bool)
        axis_index = int(round(np.clip(axis_x, 0, selected_mask.shape[1] - 1)))
        center_mask[:, max(0, axis_index - line_half_width): min(selected_mask.shape[1], axis_index + line_half_width + 1)] = True
        return center_mask & (selected_mask | subject_mask)

    def _reconstruct_major_units(
        self,
        selected_mask: np.ndarray,
        subject_mask: np.ndarray,
        axis_x: float,
        config: StructuralDetailConfig,
    ) -> np.ndarray:
        silhouette = self._build_silhouette_mask(subject_mask, config)
        center_spine = self._build_center_spine(selected_mask, subject_mask, axis_x, config)
        merged = selected_mask | silhouette | center_spine
        merge_px = max(1, int(round(config.merge_distance_mm * config.preview_ppm)))
        merged = cv2.morphologyEx(merged.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((merge_px * 2 + 1, merge_px * 2 + 1), dtype=np.uint8)) > 0
        if config.extraction_mode == "major":
            merged = cv2.morphologyEx(merged.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), dtype=np.uint8)) > 0
        return merged & subject_mask

    def _smooth_points(self, points: np.ndarray, smoothness: float) -> np.ndarray:
        if points.shape[0] < 4 or smoothness <= 0:
            return points
        window = max(3, int(round(3 + (smoothness * 8))))
        if window % 2 == 0:
            window += 1
        pad = window // 2
        padded = np.pad(points, ((pad, pad), (0, 0)), mode="edge")
        kernel = np.ones(window, dtype=np.float32) / float(window)
        smoothed_x = np.convolve(padded[:, 0], kernel, mode="valid")
        smoothed_y = np.convolve(padded[:, 1], kernel, mode="valid")
        return np.column_stack((smoothed_x, smoothed_y)).astype(np.float32)

    def _merge_paths(self, paths: List[StructuralPath], merge_distance_mm: float) -> List[StructuralPath]:
        threshold = max(0.1, float(merge_distance_mm))
        remaining = list(paths)
        merged: List[StructuralPath] = []
        while remaining:
            current = remaining.pop(0)
            current_points = [tuple(point) for point in current.points]
            changed = True
            while changed:
                changed = False
                for index, other in enumerate(list(remaining)):
                    start_a = np.asarray(current_points[0], dtype=np.float32)
                    end_a = np.asarray(current_points[-1], dtype=np.float32)
                    start_b = np.asarray(other.points[0], dtype=np.float32)
                    end_b = np.asarray(other.points[-1], dtype=np.float32)
                    if np.linalg.norm(end_a - start_b) <= threshold:
                        current_points.extend(other.points[1:])
                    elif np.linalg.norm(end_a - end_b) <= threshold:
                        current_points.extend(tuple(reversed(other.points[:-1])))
                    elif np.linalg.norm(start_a - end_b) <= threshold:
                        current_points = list(other.points[:-1]) + current_points
                    elif np.linalg.norm(start_a - start_b) <= threshold:
                        current_points = list(reversed(other.points[1:])) + current_points
                    else:
                        continue
                    remaining.pop(index)
                    changed = True
                    break
            merged.append(StructuralPath(points=tuple(current_points), closed=current.closed))
        return merged

    def _extract_paths(self, reconstructed_mask: np.ndarray, subject_mask: np.ndarray, config: StructuralDetailConfig) -> List[StructuralPath]:
        contours, _ = cv2.findContours(reconstructed_mask.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        silhouette_contours, _ = cv2.findContours(subject_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        contours = list(contours) + list(silhouette_contours)
        min_length_px = max(2.0, config.minimum_curve_length_mm * config.preview_ppm)
        merge_distance_px = max(1.0, config.merge_distance_mm * config.preview_ppm)
        epsilon = max(0.5, float(config.simplification_tolerance * config.preview_ppm))
        paths: List[StructuralPath] = []
        for contour in contours:
            if contour is None or len(contour) < 2:
                continue
            length_px = float(cv2.arcLength(contour, closed=True))
            if length_px < min_length_px:
                continue
            simplified = cv2.approxPolyDP(contour, epsilon=epsilon, closed=True)[:, 0, :].astype(np.float32)
            smoothed = self._smooth_points(simplified, config.curve_smoothness)
            if smoothed.shape[0] < 2:
                continue
            closed = np.linalg.norm(smoothed[0] - smoothed[-1]) <= merge_distance_px or contour.shape[0] >= 3
            if closed and smoothed.shape[0] >= 3:
                smoothed[-1] = smoothed[0]
            points_mm = tuple((float(point[0]) / config.preview_ppm, float(point[1]) / config.preview_ppm) for point in smoothed)
            paths.append(StructuralPath(points=points_mm, closed=closed))
        return self._merge_paths(paths, config.merge_distance_mm)

    def _render_preview(self, paths: Sequence[StructuralPath], config: StructuralDetailConfig) -> Image.Image:
        width_px = max(1, int(round(config.width_mm * config.preview_ppm)))
        height_px = max(1, int(round(config.height_mm * config.preview_ppm)))
        image = Image.new("RGB", (width_px, height_px), (26, 30, 36))
        draw = ImageDraw.Draw(image)
        stroke = max(1, int(round(1 + config.curve_smoothness * 2.5)))
        for path in paths:
            scaled = [(float(x) * config.preview_ppm, float(y) * config.preview_ppm) for x, y in path.points]
            if len(scaled) >= 2:
                draw.line(scaled, fill=(244, 247, 252), width=stroke, joint="curve")
        return image

    def to_pattern_paths(self, paths: Sequence[StructuralPath]):
        from ..pattern_fill.pattern_fill_engine import PatternPath

        return [PatternPath(points=tuple(path.points), closed=bool(path.closed), name=f"structural_{index}") for index, path in enumerate(paths, start=1)]

    def generate_preview(self, photo_path: str, config: StructuralDetailConfig, preview_profile: str = "settled", progress_controller=None) -> StructuralDetailResult:
        active = self._effective_config(config, preview_profile)
        cache_key = self.build_cache_key(photo_path, active, preview_profile=preview_profile)
        cached = self._preview_cache.get(cache_key)
        if cached is not None:
            return cached

        timings: Dict[str, float] = {}
        cache_before = self._cache.snapshot_stats()
        source_key = self._cache.build_key("ornamental_source", {"photo_path": photo_path, "stamp": self._file_stamp(photo_path), "config": vars(active)})
        rgb, gray = self._stage(
            timings,
            "image_load",
            lambda: self._get_or_set("ornamental_source", source_key, lambda: self._load_image(photo_path, active)),
        )
        if progress_controller:
            progress_controller.start_phase("Isolating subject", total=6, current=1, force=True)
            progress_controller.throw_if_cancelled()

        subject_key = self._cache.build_key("ornamental_subject", {"source": source_key})
        subject_mask, background_brightness = self._stage(
            timings,
            "subject_isolation",
            lambda: self._get_or_set("ornamental_subject", subject_key, lambda: self._isolate_subject(gray, active)),
        )
        if progress_controller:
            progress_controller.update(2, 6, phase="Extracting ornaments", force=True)
            progress_controller.throw_if_cancelled()

        ornament_key = self._cache.build_key(
            "ornamental_mask",
            {"subject": subject_key, "structure_strength": active.structure_strength, "retention": active.decorative_detail_retention, "mode": active.extraction_mode},
        )
        ornament_mask = self._stage(
            timings,
            "ornament_extraction",
            lambda: self._get_or_set(
                "ornamental_mask",
                ornament_key,
                lambda: self._extract_ornament_map(gray, subject_mask, background_brightness, active),
            ),
        )
        if progress_controller:
            progress_controller.update(3, 6, phase="Ranking motifs", force=True)
            progress_controller.throw_if_cancelled()

        ranked_key = self._cache.build_key(
            "ornamental_ranked",
            {
                "ornament": ornament_key,
                "min_motif_size": active.min_motif_size,
                "symmetry_influence": active.symmetry_influence,
                "border_band_priority": active.border_band_priority,
                "center_motif_priority": active.center_motif_priority,
                "silhouette_priority": active.silhouette_priority,
            },
        )
        ranked_mask, ranking_metrics = self._stage(
            timings,
            "structural_ranking",
            lambda: self._get_or_set("ornamental_ranked", ranked_key, lambda: self._rank_components(ornament_mask, subject_mask, active)),
        )
        if progress_controller:
            progress_controller.update(4, 6, phase="Reconstructing motifs", force=True)
            progress_controller.throw_if_cancelled()

        reconstructed_key = self._cache.build_key(
            "ornamental_reconstructed",
            {"ranked": ranked_key, "merge_distance_mm": active.merge_distance_mm, "mode": active.extraction_mode},
        )
        reconstructed_mask = self._stage(
            timings,
            "motif_reconstruction",
            lambda: self._get_or_set(
                "ornamental_reconstructed",
                reconstructed_key,
                lambda: self._reconstruct_major_units(ranked_mask, subject_mask, ranking_metrics.get("axis_x", ornament_mask.shape[1] / 2.0), active),
            ),
        )
        if progress_controller:
            progress_controller.update(5, 6, phase="Vectorizing structure", force=True)
            progress_controller.throw_if_cancelled()

        paths_key = self._cache.build_key(
            "ornamental_paths",
            {
                "reconstructed": reconstructed_key,
                "curve_smoothness": active.curve_smoothness,
                "simplification_tolerance": active.simplification_tolerance,
                "minimum_curve_length_mm": active.minimum_curve_length_mm,
            },
        )
        paths = self._stage(
            timings,
            "contour_extraction",
            lambda: self._get_or_set("ornamental_paths", paths_key, lambda: self._extract_paths(reconstructed_mask, subject_mask, active)),
        )
        preview_key = self._cache.build_key("ornamental_preview", {"paths": paths_key, "config": vars(active)})
        preview_image = self._stage(
            timings,
            "preview_render",
            lambda: self._get_or_set("ornamental_preview", preview_key, lambda: self._render_preview(paths, active)),
        )
        if progress_controller:
            progress_controller.update(6, 6, phase="Preview ready", force=True)

        timings["total"] = sum(value for key, value in timings.items() if key != "total")
        cache_after = self._cache.snapshot_stats()
        cache_delta = {
            "hits": int(cache_after["hits"] - cache_before["hits"]),
            "misses": int(cache_after["misses"] - cache_before["misses"]),
        }
        result = StructuralDetailResult(
            paths=paths,
            preview_image=preview_image,
            width_mm=active.width_mm,
            height_mm=active.height_mm,
            timings=timings,
            cache_key=cache_key,
            diagnostics={
                "path_count": len(paths),
                "profile": preview_profile,
                "slowest_stage": max((key for key in timings.keys() if key != "total"), key=lambda key: timings[key], default="-"),
                "cache": cache_delta,
                "symmetry": active.symmetry_enabled,
                "performance_mode": active.performance_mode,
                "mode": active.extraction_mode,
                "selected_components": int(ranking_metrics.get("selected_components", 0)),
                "components": int(ranking_metrics.get("components", 0)),
            },
        )
        self._preview_cache[cache_key] = result
        return result

    def export_svg(self, paths: Sequence[StructuralPath], width_mm: float, height_mm: float, output_path: str) -> None:
        drawing = svgwrite.Drawing(output_path, size=(f"{width_mm}mm", f"{height_mm}mm"), viewBox=f"0 0 {width_mm} {height_mm}")
        root = drawing.g(id="structural_detail", fill="none", stroke="black", stroke_width=0.35, stroke_linecap="round", stroke_linejoin="round")
        for index, path in enumerate(paths, start=1):
            if len(path.points) < 2:
                continue
            commands = [f"M {path.points[0][0]:.4f} {path.points[0][1]:.4f}"]
            commands.extend(f"L {point[0]:.4f} {point[1]:.4f}" for point in path.points[1:])
            if path.closed:
                commands.append("Z")
            root.add(drawing.path(d=" ".join(commands), id=f"path_{index}"))
        drawing.add(root)
        drawing.save()
