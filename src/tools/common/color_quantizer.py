from typing import Dict, Tuple

import numpy as np

Color = Tuple[int, int, int]


class ColorQuantizer:
    """Shared palette mapping logic for image-driven stone tools."""

    def nearest_palette(self, samples_rgb: np.ndarray, palette: Dict[str, Color]) -> Tuple[np.ndarray, np.ndarray]:
        names = list(palette.keys())
        palette_rgb = np.asarray([palette[name] for name in names], dtype=np.int16)
        samples = samples_rgb.astype(np.int16)
        deltas = samples[:, None, :] - palette_rgb[None, :, :]
        dist = np.sum(deltas * deltas, axis=2)
        indices = np.argmin(dist, axis=1)
        colors = palette_rgb[indices].astype(np.uint8)
        labels = np.asarray([names[index] for index in indices], dtype=object)
        return labels, colors

    def dominant_name(self, rgba: np.ndarray, palette: Dict[str, Color]) -> str:
        mean_rgb = np.round(rgba[..., :3].reshape(-1, 3).mean(axis=0)).astype(np.uint8).reshape(1, 3)
        labels, _ = self.nearest_palette(mean_rgb, palette)
        return str(labels[0])

    def map_samples(
        self,
        samples_rgba: np.ndarray,
        palette: Dict[str, Color],
        palette_mode: str,
        brightness_only: bool = False,
        brightness_invert: bool = False,
        dominant: str = "",
    ) -> Tuple[np.ndarray, np.ndarray]:
        rgb = samples_rgba[:, :3].astype(np.uint8)
        if brightness_only:
            gray = np.round((0.2126 * rgb[:, 0]) + (0.7152 * rgb[:, 1]) + (0.0722 * rgb[:, 2])).astype(np.uint8)
            if brightness_invert:
                gray = 255 - gray
            rgb = np.stack((gray, gray, gray), axis=1)

        if palette_mode in ("nearest", "rhinestone"):
            return self.nearest_palette(rgb, palette)

        if palette_mode == "grayscale":
            names = list(palette.keys())
            gray = np.round((0.2126 * rgb[:, 0]) + (0.7152 * rgb[:, 1]) + (0.0722 * rgb[:, 2])).astype(np.float32)
            indices = np.rint((gray / 255.0) * max(0, len(names) - 1)).astype(np.int32)
            indices = np.clip(indices, 0, max(0, len(names) - 1))
            if brightness_invert:
                indices = (len(names) - 1) - indices
            mapped_names = np.asarray([names[index] for index in indices], dtype=object)
            mapped_colors = np.asarray([palette[name] for name in mapped_names], dtype=np.uint8)
            return mapped_names, mapped_colors

        if palette_mode == "dominant_accents" and dominant:
            contrasts = rgb.max(axis=1) - rgb.min(axis=1)
            dominant_mask = contrasts < 50
            mapped_names, mapped_colors = self.nearest_palette(rgb, palette)
            mapped_names[dominant_mask] = dominant
            mapped_colors[dominant_mask] = np.asarray(palette[dominant], dtype=np.uint8)
            return mapped_names, mapped_colors

        return self.nearest_palette(rgb, palette)
