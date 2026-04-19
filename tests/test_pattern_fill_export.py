import tempfile
import unittest
from pathlib import Path

from src.tools.common.exporter import StoneExporter
from src.tools.pattern_fill.pattern_fill_engine import PatternStone


class PatternFillExportTests(unittest.TestCase):
    def test_grouped_pattern_layer_svg_preserves_layer_groups(self):
        stones = [
            PatternStone(x_mm=5.0, y_mm=5.0, diameter_mm=2.0, color_name="red", rgb=(255, 0, 0), pattern_layer="boundary_1"),
            PatternStone(x_mm=7.0, y_mm=5.0, diameter_mm=2.0, color_name="blue", rgb=(0, 0, 255), pattern_layer="fill"),
        ]
        exporter = StoneExporter()
        with tempfile.TemporaryDirectory() as temp_dir:
            svg_path = Path(temp_dir) / "pattern_layer.svg"
            exporter.export_svg(
                stones,
                20.0,
                20.0,
                str(svg_path),
                grouped=True,
                grouping_mode="pattern_layer",
            )
            text = svg_path.read_text(encoding="utf-8")

        self.assertIn("pattern_1_boundary_1", text)
        self.assertIn("pattern_2_fill", text)
        self.assertNotIn("<rect", text)


if __name__ == "__main__":
    unittest.main()
