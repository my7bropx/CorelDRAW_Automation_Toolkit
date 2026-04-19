from dataclasses import dataclass
from functools import lru_cache
import logging
from typing import Optional, Sequence, Tuple

import numpy as np

from .progress_controller import ProgressController

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SizeAssignmentSettings:
    size_mode: str = "single"
    allowed_sizes_mm: Sequence[float] = (2.8,)
    edge_detail_sensitivity: float = 0.85
    minimum_spacing_mm: float = 0.2
    favor_large_in_flat_areas: bool = True
    edge_margin_mm: float = 0.0
    coverage_recovery: bool = True


class StoneSizeAssigner:
    @staticmethod
    @lru_cache(maxsize=32)
    def _disk_offsets(radius_px: int) -> np.ndarray:
        radius_px = max(0, int(radius_px))
        rr = np.arange(-radius_px, radius_px + 1)
        gx, gy = np.meshgrid(rr, rr)
        mask = (gx * gx + gy * gy) <= (radius_px * radius_px)
        return np.column_stack((gy[mask], gx[mask])).astype(np.int16)

    def _normalized_detail(self, points_mm: np.ndarray, detail_map: np.ndarray, ppm: int, sensitivity: float) -> np.ndarray:
        px = np.clip(np.round(points_mm[:, 0] * ppm).astype(np.int32), 0, detail_map.shape[1] - 1)
        py = np.clip(np.round(points_mm[:, 1] * ppm).astype(np.int32), 0, detail_map.shape[0] - 1)
        detail = detail_map[py, px]
        sensitivity = max(0.01, min(1.0, float(sensitivity)))
        return np.clip(detail / sensitivity, 0.0, 1.0)

    def assign_sizes(
        self,
        points_mm: np.ndarray,
        detail_map: np.ndarray,
        ppm: int,
        settings: SizeAssignmentSettings,
    ) -> np.ndarray:
        if points_mm.size == 0:
            return np.empty((0,), dtype=np.float32)

        allowed = sorted({round(float(size), 4) for size in settings.allowed_sizes_mm if float(size) > 0})
        if not allowed:
            allowed = [2.8]
        if settings.size_mode == "single" or len(allowed) == 1:
            return np.full(points_mm.shape[0], allowed[0], dtype=np.float32)

        normalized = self._normalized_detail(points_mm, detail_map, ppm, settings.edge_detail_sensitivity)

        if settings.size_mode == "small_medium":
            pair = [allowed[0], allowed[min(1, len(allowed) - 1)]]
            low_detail, high_detail = (pair[-1], pair[0]) if settings.favor_large_in_flat_areas else (pair[0], pair[-1])
            return np.where(normalized >= 0.5, high_detail, low_detail).astype(np.float32)

        if settings.size_mode == "small_medium_large":
            trio = allowed[:3] if len(allowed) >= 3 else [allowed[0], allowed[min(1, len(allowed) - 1)], allowed[-1]]
            if settings.favor_large_in_flat_areas:
                trio = list(reversed(trio))
            bins = np.digitize(normalized, [0.34, 0.67])
            return np.asarray([trio[min(int(bin_id), len(trio) - 1)] for bin_id in bins], dtype=np.float32)

        ordered = list(reversed(allowed)) if settings.favor_large_in_flat_areas else list(allowed)
        bins = np.linspace(0.0, 1.0, num=len(ordered), endpoint=True)
        indices = np.searchsorted(bins, normalized, side="right") - 1
        indices = np.clip(indices, 0, len(ordered) - 1)
        return np.asarray([ordered[int(index)] for index in indices], dtype=np.float32)

    def _build_safe_center_mask(self, allowed_mask: np.ndarray, radius_mm: float, ppm: int) -> np.ndarray:
        allowed_mask = np.asarray(allowed_mask, dtype=bool)
        radius_px = max(0, int(np.ceil(radius_mm * ppm)))
        offsets = self._disk_offsets(radius_px)
        safe = np.zeros_like(allowed_mask, dtype=bool)
        height, width = allowed_mask.shape

        y_start = radius_px
        y_end = max(radius_px, height - radius_px)
        x_start = radius_px
        x_end = max(radius_px, width - radius_px)
        if y_end <= y_start or x_end <= x_start:
            return safe

        interior = np.ones((y_end - y_start, x_end - x_start), dtype=bool)
        for dy, dx in offsets:
            interior &= allowed_mask[y_start + int(dy):y_end + int(dy), x_start + int(dx):x_end + int(dx)]
        safe[y_start:y_end, x_start:x_end] = interior
        return safe

    def _mark_occupancy(self, occupancy: np.ndarray, cx: int, cy: int, radius_px: int) -> None:
        offsets = self._disk_offsets(radius_px)
        ys = cy + offsets[:, 0]
        xs = cx + offsets[:, 1]
        valid = (ys >= 0) & (xs >= 0) & (ys < occupancy.shape[0]) & (xs < occupancy.shape[1])
        occupancy[ys[valid], xs[valid]] = True

    def _can_place(self, occupancy: np.ndarray, cx: int, cy: int, radius_px: int) -> bool:
        offsets = self._disk_offsets(radius_px)
        ys = cy + offsets[:, 0]
        xs = cx + offsets[:, 1]
        valid = (ys >= 0) & (xs >= 0) & (ys < occupancy.shape[0]) & (xs < occupancy.shape[1])
        return not bool(occupancy[ys[valid], xs[valid]].any())

    def place_stones(
        self,
        points_mm: np.ndarray,
        labels: np.ndarray,
        colors: np.ndarray,
        detail_map: np.ndarray,
        allowed_mask: np.ndarray,
        ppm: int,
        settings: SizeAssignmentSettings,
        progress: Optional[ProgressController] = None,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        total = int(points_mm.shape[0])
        if total == 0:
            empty_points = np.empty((0, 2), dtype=np.float32)
            empty_labels = np.empty((0,), dtype=labels.dtype if hasattr(labels, "dtype") else object)
            empty_colors = np.empty((0, 3), dtype=np.uint8)
            empty_sizes = np.empty((0,), dtype=np.float32)
            return empty_points, empty_labels, empty_colors, empty_sizes

        allowed_mask = np.asarray(allowed_mask, dtype=bool)

        desired_sizes = self.assign_sizes(points_mm, detail_map, ppm, settings)
        normalized_detail = self._normalized_detail(points_mm, detail_map, ppm, settings.edge_detail_sensitivity)

        available_sizes = sorted({round(float(size), 4) for size in desired_sizes.tolist()}, reverse=True)
        if not available_sizes:
            available_sizes = [round(float(settings.allowed_sizes_mm[0]), 4)]

        desired_rank = {size: rank for rank, size in enumerate(available_sizes)}
        original_rank = np.asarray([desired_rank[round(float(candidate), 4)] for candidate in desired_sizes], dtype=np.int32)
        point_px = np.clip(np.round(points_mm[:, 0] * ppm).astype(np.int32), 0, allowed_mask.shape[1] - 1)
        point_py = np.clip(np.round(points_mm[:, 1] * ppm).astype(np.int32), 0, allowed_mask.shape[0] - 1)

        occupancy = np.zeros_like(allowed_mask, dtype=bool)
        placed_mask = np.zeros(total, dtype=bool)
        placed_size = np.zeros(total, dtype=np.float32)
        rejected_boundary = 0
        rejected_overlap = 0
        retried_smaller = 0

        safe_masks = {}
        collision_radii = {}
        for size in available_sizes:
            safe_masks[size] = self._build_safe_center_mask(
                allowed_mask,
                (size / 2.0) + float(settings.edge_margin_mm),
                ppm,
            )
            collision_radii[size] = max(0, int(np.ceil(((size / 2.0) + (settings.minimum_spacing_mm / 2.0)) * ppm)))

        if progress:
            progress.start_phase("Assigning stone sizes", total=max(1, total))

        processed = 0
        for pass_index, size in enumerate(available_sizes):
            eligible = np.flatnonzero(~placed_mask & np.array([
                desired_rank[round(float(candidate), 4)] <= pass_index
                for candidate in desired_sizes
            ]))
            if eligible.size == 0:
                continue

            if pass_index == len(available_sizes) - 1:
                order = np.argsort(-normalized_detail[eligible])
            else:
                exact_match = (np.round(desired_sizes[eligible], 4) == round(float(size), 4)).astype(np.int32)
                order = np.lexsort((normalized_detail[eligible], -exact_match))

            safe_mask = safe_masks[size]
            collision_radius = collision_radii[size]
            pass_placed = 0
            pass_boundary_rejects = 0
            pass_overlap_rejects = 0

            for index in eligible[order]:
                if progress:
                    progress.throw_if_cancelled()
                if placed_mask[index]:
                    continue
                cx = int(point_px[index])
                cy = int(point_py[index])
                if not safe_mask[cy, cx]:
                    rejected_boundary += 1
                    pass_boundary_rejects += 1
                    continue
                if not self._can_place(occupancy, cx, cy, collision_radius):
                    rejected_overlap += 1
                    pass_overlap_rejects += 1
                    continue
                placed_mask[index] = True
                placed_size[index] = size
                if pass_index > int(original_rank[index]):
                    retried_smaller += 1
                self._mark_occupancy(occupancy, cx, cy, collision_radius)
                processed += 1
                pass_placed += 1
                if progress and ((processed % 128) == 0 or processed == total):
                    progress.update(processed, total)

            uncovered_pixels = int(np.count_nonzero(allowed_mask & ~occupancy))
            logger.info(
                "pointillizer placement pass=%s size=%.4f placed=%s boundary_rejects=%s overlap_rejects=%s uncovered_pixels=%s",
                pass_index + 1,
                size,
                pass_placed,
                pass_boundary_rejects,
                pass_overlap_rejects,
                uncovered_pixels,
            )

        if settings.coverage_recovery:
            smallest_size = available_sizes[-1]
            fallback_mask = safe_masks[smallest_size]
            fallback_radius = collision_radii[smallest_size]
            remaining = np.flatnonzero(~placed_mask)
            if remaining.size:
                coverage_order = remaining[np.argsort(-normalized_detail[remaining])]
                for index in coverage_order:
                    if progress:
                        progress.throw_if_cancelled()
                    cx = int(point_px[index])
                    cy = int(point_py[index])
                    if not fallback_mask[cy, cx]:
                        rejected_boundary += 1
                        continue
                    if not self._can_place(occupancy, cx, cy, fallback_radius):
                        rejected_overlap += 1
                        continue
                    placed_mask[index] = True
                    placed_size[index] = smallest_size
                    if  int(original_rank[index]) < len(available_sizes) - 1:
                        retried_smaller += 1
                    self._mark_occupancy(occupancy, cx, cy, fallback_radius)
                    processed += 1
                    if progress and ((processed % 128) == 0 or processed == total):
                        progress.update(processed, total)

        if progress:
            progress.update(max(processed, int(placed_mask.sum())), total, force=True)

        logger.info(
            "pointillizer placement summary total_candidates=%s placed=%s rejected_boundary=%s rejected_overlap=%s retried_smaller=%s uncovered_pixels=%s",
            total,
            int(placed_mask.sum()),
            rejected_boundary,
            rejected_overlap,
            retried_smaller,
            int(np.count_nonzero(allowed_mask & ~occupancy)),
        )

        return (
            points_mm[placed_mask],
            labels[placed_mask],
            colors[placed_mask],
            placed_size[placed_mask],
        )
