import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from src.tools.common.structural_detail_extractor import StructuralDetailConfig, StructuralDetailExtractor


class StructuralDetailExtractorTests(unittest.TestCase):
    def test_exported_structural_svg_is_clean_and_transparent(self):
        extractor = StructuralDetailExtractor()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            image_path = temp_path / "source.png"
            svg_path = temp_path / "structural.svg"

            image = Image.new("RGB", (220, 220), "white")
            draw = ImageDraw.Draw(image)
            draw.arc((20, 20, 200, 180), start=10, end=170, fill="black", width=10)
            draw.rectangle((40, 145, 180, 198), outline="black", width=8)
            draw.line((35, 80, 185, 125), fill="black", width=8)
            draw.ellipse((8, 8, 14, 14), fill="black")
            draw.ellipse((204, 18, 210, 24), fill="black")
            image.save(image_path)

            result = extractor.generate_preview(
                str(image_path),
                StructuralDetailConfig(
                    width_mm=120.0,
                    height_mm=120.0,
                    extraction_mode="balanced",
                    min_motif_size=18,
                    minimum_curve_length_mm=4.0,
                    simplification_tolerance=0.6,
                    structure_strength=0.65,
                    decorative_detail_retention=0.45,
                ),
                preview_profile="settled",
            )
            extractor.export_svg(result.paths, result.width_mm, result.height_mm, str(svg_path))
            text = svg_path.read_text(encoding="utf-8")

        self.assertGreater(len(result.paths), 0)
        self.assertIn("<path", text)
        self.assertNotIn("<rect", text)
        self.assertEqual(len(result.paths), len(extractor.to_pattern_paths(result.paths)))

    def test_major_mode_is_more_aggressive_than_full_mode(self):
        extractor = StructuralDetailExtractor()
        with tempfile.TemporaryDirectory() as temp_dir:
            image_path = Path(temp_dir) / "ornate.png"
            image = Image.new("RGB", (260, 320), "black")
            draw = ImageDraw.Draw(image)
            draw.polygon([(40, 300), (120, 30), (140, 30), (220, 300)], outline="white", width=8)
            for offset in range(0, 5):
                draw.arc((70 - offset, 80 - offset, 190 + offset, 210 + offset), 205, 335, fill="white", width=4)
            for y in (110, 150, 210, 255):
                draw.line((70, y, 190, y), fill="white", width=3)
            for x in (85, 110, 150, 175):
                draw.ellipse((x - 8, 160, x + 8, 176), fill="white")
            image.save(image_path)

            major = extractor.generate_preview(
                str(image_path),
                StructuralDetailConfig(width_mm=120.0, height_mm=160.0, extraction_mode="major"),
                preview_profile="settled",
            )
            full = extractor.generate_preview(
                str(image_path),
                StructuralDetailConfig(
                    width_mm=120.0,
                    height_mm=160.0,
                    extraction_mode="full",
                    decorative_detail_retention=0.75,
                ),
                preview_profile="settled",
            )

        self.assertGreater(len(full.paths), 0)
        self.assertGreater(len(major.paths), 0)
        self.assertLessEqual(len(major.paths), len(full.paths))


if __name__ == "__main__":
    unittest.main()
