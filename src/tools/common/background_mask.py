from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter

Color = Tuple[int, int, int]


@dataclass(frozen=True)
class BackgroundMaskSettings:
    remove_background: bool = False
    use_source_alpha: bool = True
    auto_detect: bool = True
    background_rgb: Color = (255, 255, 255)
    tolerance: int = 28
    feather_px: int = 0
    keep_holes: bool = True
    alpha_threshold: int = 8
    mask_threshold: int = 128


class BackgroundMaskBuilder:
    def detect_background_color(self, rgba: np.ndarray) -> Color:
        rgb = rgba[..., :3].astype(np.float32)
        corners = np.concatenate(
            [
                rgb[:8, :8].reshape(-1, 3),
                rgb[:8, -8:].reshape(-1, 3),
                rgb[-8:, :8].reshape(-1, 3),
                rgb[-8:, -8:].reshape(-1, 3),
            ],
            axis=0,
        )
        median = np.median(corners, axis=0)
        return int(median[0]), int(median[1]), int(median[2])

    def build_mask(
        self,
        source: np.ndarray,
        settings: BackgroundMaskSettings,
        transparent_png: Optional[str] = None,
        mask_path: Optional[str] = None,
    ) -> np.ndarray:
        allowed = np.ones(source.shape[:2], dtype=np.float32)

        if settings.use_source_alpha:
            allowed *= (source[..., 3] >= int(settings.alpha_threshold)).astype(np.float32)

        if transparent_png:
            overlay = np.array(Image.open(transparent_png).convert("RGBA").resize((source.shape[1], source.shape[0]), Image.Resampling.LANCZOS))
            allowed *= (overlay[..., 3] >= int(settings.alpha_threshold)).astype(np.float32)

        if mask_path:
            mask = Image.open(mask_path).convert("L").resize((source.shape[1], source.shape[0]), Image.Resampling.LANCZOS)
            allowed *= (np.array(mask) >= int(settings.mask_threshold)).astype(np.float32)

        if settings.remove_background:
            background_rgb = settings.background_rgb
            if settings.auto_detect:
                background_rgb = self.detect_background_color(source)
            diff = np.linalg.norm(source[..., :3].astype(np.int16) - np.array(background_rgb, dtype=np.int16), axis=2)
            allowed *= (diff >= int(settings.tolerance)).astype(np.float32)

        if settings.feather_px > 0:
            mask_img = Image.fromarray(np.clip(allowed * 255.0, 0, 255).astype(np.uint8), mode="L")
            mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=float(settings.feather_px)))
            allowed = np.array(mask_img, dtype=np.float32) / 255.0

        return allowed
