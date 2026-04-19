from dataclasses import dataclass
from typing import Optional

import numpy as np

from .progress_controller import ProgressController


@dataclass(frozen=True)
class DecimationSettings:
    target_density: float = 1.0
    preserve_edges_strength: float = 0.75
    detail_threshold: float = 0.18
    max_stone_count: int = 0
    seed: int = 12


class StoneDecimator:
    def build_detail_map(self, rgba: np.ndarray) -> np.ndarray:
        gray = (0.2126 * rgba[..., 0] + 0.7152 * rgba[..., 1] + 0.0722 * rgba[..., 2]).astype(np.float32) / 255.0
        gy, gx = np.gradient(gray)
        detail = np.sqrt((gx * gx) + (gy * gy))
        if detail.size:
            peak = float(detail.max())
            if peak > 1e-6:
                detail /= peak
        return detail.astype(np.float32)

    def decimate(
        self,
        points_mm: np.ndarray,
        detail_map: np.ndarray,
        ppm: int,
        settings: DecimationSettings,
        progress: Optional[ProgressController] = None,
    ) -> np.ndarray:
        if points_mm.size == 0:
            return points_mm

        total = int(points_mm.shape[0])
        if progress:
            progress.start_phase("Decimating", total=total)

        px = np.clip(np.round(points_mm[:, 0] * ppm).astype(np.int32), 0, detail_map.shape[1] - 1)
        py = np.clip(np.round(points_mm[:, 1] * ppm).astype(np.int32), 0, detail_map.shape[0] - 1)
        detail = detail_map[py, px]
        density = max(0.02, min(1.0, float(settings.target_density)))
        preserve = max(0.0, min(1.0, float(settings.preserve_edges_strength)))
        threshold = max(0.0, min(1.0, float(settings.detail_threshold)))

        rng = np.random.default_rng(int(settings.seed))
        jitter = rng.random(total, dtype=np.float32) * 1e-4
        score = (detail * preserve) + ((1.0 - preserve) * density) + jitter
        keep_mask = score >= ((1.0 - density) * max(0.05, threshold))

        if settings.max_stone_count and int(keep_mask.sum()) > int(settings.max_stone_count):
            keep_indices = np.argsort(score)[-int(settings.max_stone_count):]
            keep_mask = np.zeros(total, dtype=bool)
            keep_mask[keep_indices] = True

        if progress:
            progress.update(total, total, force=True)

        return points_mm[keep_mask]
