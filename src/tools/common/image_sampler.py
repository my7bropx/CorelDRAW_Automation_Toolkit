from functools import lru_cache
from typing import Callable, Optional, Tuple

import numpy as np
from PIL import Image

from .progress_controller import ProgressController


class ImageSampler:
    """Shared photo sampling pipeline for stone-based image tools."""

    def fit_rgba(self, path: str, width_mm: float, height_mm: float, ppm: int) -> np.ndarray:
        size = (max(1, int(round(width_mm * ppm))), max(1, int(round(height_mm * ppm))))
        return np.array(Image.open(path).convert("RGBA").resize(size, Image.Resampling.LANCZOS))

    def tone(self, rgba: np.ndarray, gamma: float, contrast: float, brightness: float) -> np.ndarray:
        arr = rgba.astype(np.float32) / 255.0
        rgb = arr[..., :3]
        rgb = np.clip((rgb - 0.5) * float(contrast) + 0.5, 0.0, 1.0)
        rgb = np.clip(rgb * float(brightness), 0.0, 1.0)
        rgb = np.clip(rgb ** (1.0 / max(1e-6, float(gamma))), 0.0, 1.0)
        return np.concatenate(((rgb * 255.0).astype(np.uint8), rgba[..., 3:4]), axis=-1)

    def build_allowed_mask(
        self,
        source: np.ndarray,
        width_mm: float,
        height_mm: float,
        ppm: int,
        alpha_threshold: int,
        use_source_alpha: bool,
        transparent_png: Optional[str] = None,
        mask_path: Optional[str] = None,
        mask_threshold: int = 128,
    ) -> np.ndarray:
        allowed = np.ones(source.shape[:2], dtype=bool)
        if use_source_alpha:
            allowed &= source[..., 3] >= int(alpha_threshold)
        if transparent_png:
            overlay = self.fit_rgba(transparent_png, width_mm, height_mm, ppm)
            allowed &= overlay[..., 3] >= int(alpha_threshold)
        if mask_path:
            mask = Image.open(mask_path).convert("L").resize((source.shape[1], source.shape[0]), Image.Resampling.LANCZOS)
            allowed &= np.array(mask) >= int(mask_threshold)
        return allowed

    @staticmethod
    @lru_cache(maxsize=16)
    def _disk_offsets(radius_px: int) -> np.ndarray:
        radius_px = max(1, int(radius_px))
        rr = np.arange(-radius_px, radius_px + 1)
        gx, gy = np.meshgrid(rr, rr)
        mask = (gx * gx + gy * gy) <= (radius_px * radius_px)
        offsets = np.column_stack((gy[mask], gx[mask]))
        return offsets.astype(np.int16)

    def accept_point(self, allowed: np.ndarray, x_mm: float, y_mm: float, radius_mm: float, ppm: int) -> bool:
        cx = int(round(x_mm * ppm))
        cy = int(round(y_mm * ppm))
        offsets = self._disk_offsets(max(1, int(round(radius_mm * ppm))))
        ys = cy + offsets[:, 0]
        xs = cx + offsets[:, 1]
        if ys.size == 0:
            return False
        if ys.min() < 0 or xs.min() < 0 or ys.max() >= allowed.shape[0] or xs.max() >= allowed.shape[1]:
            return False
        return bool(allowed[ys, xs].all())

    def build_safe_center_mask(self, allowed: np.ndarray, radius_mm: float, ppm: int) -> np.ndarray:
        if allowed.size == 0:
            return allowed.astype(bool)

        radius_px = max(1, int(round(radius_mm * ppm)))
        offsets = self._disk_offsets(radius_px)
        height, width = allowed.shape
        safe = np.zeros_like(allowed, dtype=bool)

        y_start = radius_px
        y_end = max(radius_px, height - radius_px)
        x_start = radius_px
        x_end = max(radius_px, width - radius_px)
        if y_end <= y_start or x_end <= x_start:
            return safe

        interior = np.ones((y_end - y_start, x_end - x_start), dtype=bool)
        for dy, dx in offsets:
            source_y = slice(y_start + int(dy), y_end + int(dy))
            source_x = slice(x_start + int(dx), x_end + int(dx))
            interior &= allowed[source_y, source_x]
        safe[y_start:y_end, x_start:x_end] = interior
        return safe

    def filter_points(
        self,
        points_mm: np.ndarray,
        allowed: np.ndarray,
        radius_mm: float,
        ppm: int,
        inside_cb: Optional[Callable[[float, float, float], bool]] = None,
        inside_mask: Optional[np.ndarray] = None,
        progress: Optional[ProgressController] = None,
    ) -> np.ndarray:
        if points_mm.size == 0:
            return points_mm

        combined_mask = allowed.astype(bool)
        if inside_mask is not None:
            combined_mask &= inside_mask.astype(bool)
        safe_centers = self.build_safe_center_mask(combined_mask, radius_mm, ppm)

        total = int(points_mm.shape[0])
        if progress:
            progress.start_phase("Filtering valid stone centers", total=total)

        px = np.round(points_mm[:, 0] * ppm).astype(np.int32)
        py = np.round(points_mm[:, 1] * ppm).astype(np.int32)
        bounds = (
            (px >= 0)
            & (py >= 0)
            & (px < safe_centers.shape[1])
            & (py < safe_centers.shape[0])
        )
        keep_mask = np.zeros(total, dtype=bool)
        keep_mask[bounds] = safe_centers[py[bounds], px[bounds]]

        if inside_cb is not None:
            candidate_indices = np.flatnonzero(keep_mask)
            for offset, index in enumerate(candidate_indices, start=1):
                if progress:
                    progress.throw_if_cancelled()
                x_mm, y_mm = points_mm[index]
                if not inside_cb(float(x_mm), float(y_mm), radius_mm):
                    keep_mask[index] = False
                if progress and ((offset % 64) == 0 or offset == candidate_indices.size):
                    progress.update(min(total, index + 1), total)
        elif progress:
            progress.update(total, total, force=True)

        return points_mm[keep_mask]

    def sample_colors(
        self,
        rgba: np.ndarray,
        points_mm: np.ndarray,
        radius_mm: float,
        ppm: int,
        mode: str,
        alpha_threshold: int,
        progress: Optional[ProgressController] = None,
    ) -> np.ndarray:
        if points_mm.size == 0:
            return np.empty((0, 4), dtype=np.uint8)

        total = int(points_mm.shape[0])
        samples = np.empty((total, 4), dtype=np.uint8)
        radius_px = max(1, int(round(radius_mm * ppm)))
        offsets = self._disk_offsets(radius_px)

        if progress:
            progress.start_phase("Sampling image", total=total)

        height, width = rgba.shape[:2]
        nearest_mode = mode == "nearest"
        for index, (x_mm, y_mm) in enumerate(points_mm, start=1):
            if progress:
                progress.throw_if_cancelled()
            cx = int(round(float(x_mm) * ppm))
            cy = int(round(float(y_mm) * ppm))
            cx = min(max(cx, 0), width - 1)
            cy = min(max(cy, 0), height - 1)

            if nearest_mode:
                pixel = rgba[cy, cx]
                samples[index - 1] = pixel
            else:
                ys = cy + offsets[:, 0]
                xs = cx + offsets[:, 1]
                valid = (ys >= 0) & (ys < height) & (xs >= 0) & (xs < width)
                region = rgba[ys[valid], xs[valid]]
                if region.size == 0:
                    samples[index - 1] = rgba[cy, cx]
                else:
                    samples[index - 1] = np.round(region.mean(axis=0)).astype(np.uint8)

            if samples[index - 1][3] < alpha_threshold:
                samples[index - 1][3] = 0

            if progress:
                progress.update(index, total)

        return samples
