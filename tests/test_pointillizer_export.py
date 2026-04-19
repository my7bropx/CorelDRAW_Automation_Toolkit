import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.tools.common.exporter import StoneExporter
from src.tools.common.size_assignment import SizeAssignmentSettings, StoneSizeAssigner
from src.tools.photo_to_rhinestone_svg.photo_pointillizer import Stone


class PointillizerExportTests(unittest.TestCase):
    def test_svg_is_transparent_by_default(self):
        stones = [
            Stone(x_mm=5.0, y_mm=5.0, diameter_mm=2.0, color_name="red", rgb=(255, 0, 0)),
        ]
        exporter = StoneExporter()
        with tempfile.TemporaryDirectory() as temp_dir:
            svg_path = Path(temp_dir) / "pointillizer.svg"
            exporter.export_svg(stones, 10.0, 10.0, str(svg_path), grouped=True)
            text = svg_path.read_text(encoding="utf-8")
        self.assertNotIn("<rect", text)

    def test_svg_can_include_background_when_enabled(self):
        stones = [
            Stone(x_mm=5.0, y_mm=5.0, diameter_mm=2.0, color_name="red", rgb=(255, 0, 0)),
        ]
        exporter = StoneExporter()
        with tempfile.TemporaryDirectory() as temp_dir:
            svg_path = Path(temp_dir) / "pointillizer_bg.svg"
            exporter.export_svg(
                stones,
                10.0,
                10.0,
                str(svg_path),
                grouped=True,
                include_background=True,
                background_rgb=(10, 20, 30),
            )
            text = svg_path.read_text(encoding="utf-8")
        self.assertIn("<rect", text)


class PointillizerPlacementTests(unittest.TestCase):
    def test_multi_size_preserves_multiple_colors_with_small_fallback(self):
        assigner = StoneSizeAssigner()
        xs, ys = np.meshgrid(np.linspace(2.0, 18.0, 9), np.linspace(2.0, 18.0, 9))
        points = np.column_stack((xs.ravel(), ys.ravel())).astype(np.float32)
        labels = np.asarray(["red" if index % 2 == 0 else "blue" for index in range(points.shape[0])], dtype=object)
        colors = np.asarray([(255, 0, 0) if label == "red" else (0, 0, 255) for label in labels], dtype=np.uint8)
        detail_map = np.ones((80, 80), dtype=np.float32) * 0.2
        detail_map[20:60, 20:60] = 0.9
        allowed_mask = np.ones((80, 80), dtype=bool)

        placed_points, placed_labels, placed_colors, placed_sizes = assigner.place_stones(
            points,
            labels,
            colors,
            detail_map,
            allowed_mask,
            ppm=4,
            settings=SizeAssignmentSettings(
                size_mode="small_medium_large",
                allowed_sizes_mm=(2.0, 3.0, 4.0),
                edge_detail_sensitivity=0.85,
                minimum_spacing_mm=0.1,
                edge_margin_mm=0.0,
            ),
        )

        self.assertGreater(len(placed_points), 0)
        self.assertIn("red", set(placed_labels.tolist()))
        self.assertIn("blue", set(placed_labels.tolist()))
        self.assertTrue(np.all(placed_sizes > 0))
        self.assertEqual(len(placed_points), len(placed_labels))
        self.assertEqual(len(placed_points), len(placed_colors))


if __name__ == "__main__":
    unittest.main()
