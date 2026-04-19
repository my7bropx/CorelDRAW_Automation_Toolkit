import csv
import logging
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple

import svgwrite
from PIL import Image

Color = Tuple[int, int, int]

logger = logging.getLogger(__name__)


class StoneExporter:
    """Shared export helpers for stone-based tools."""

    def group_stones(self, stones: Sequence) -> Dict[Tuple[Tuple[int, int, int], float], list]:
        grouped: Dict[Tuple[Tuple[int, int, int], float], list] = {}
        for stone in stones:
            key = (tuple(int(channel) for channel in stone.rgb), round(float(stone.diameter_mm), 4))
            grouped.setdefault(key, []).append(stone)
        return grouped

    def export_csv(self, stones: Sequence, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["x_mm", "y_mm", "diameter_mm", "color_name", "r", "g", "b"])
            for stone in stones:
                writer.writerow([
                    f"{float(stone.x_mm):.4f}",
                    f"{float(stone.y_mm):.4f}",
                    f"{float(stone.diameter_mm):.4f}",
                    str(stone.color_name),
                    int(stone.rgb[0]),
                    int(stone.rgb[1]),
                    int(stone.rgb[2]),
                ])

    def export_grouped_csv(self, stones: Sequence, path: str) -> None:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["color_name", "diameter_mm", "r", "g", "b", "count"])
            for (rgb, diameter), grouped in sorted(self.group_stones(stones).items(), key=lambda item: (item[0][0], item[0][1])):
                writer.writerow([
                    grouped[0].color_name,
                    f"{diameter:.4f}",
                    rgb[0],
                    rgb[1],
                    rgb[2],
                    len(grouped),
                ]) 

    def group_stones_by_pattern_layer(self, stones: Sequence) -> Dict[str, list]:
        grouped: Dict[str, list] = {}
        for stone in stones:
            layer_name = str(getattr(stone, "pattern_layer", "") or getattr(stone, "color_name", "layer"))
            grouped.setdefault(layer_name, []).append(stone)
        return grouped

    def export_svg(
        self,
        stones: Sequence,
        width_mm: float,
        height_mm: float,
        path: str,
        grouped: bool = False,
        grouping_mode: str = "color",
        include_background: bool = False,
        background_rgb: Optional[Color] = None,
    ) -> None:
        dwg = svgwrite.Drawing(path, size=(f"{width_mm}mm", f"{height_mm}mm"), viewBox=f"0 0 {width_mm} {height_mm}")
        has_background = bool(include_background and background_rgb is not None)
        if has_background:
            dwg.add(dwg.rect((0, 0), (width_mm, height_mm), fill=f"rgb({background_rgb[0]},{background_rgb[1]},{background_rgb[2]})"))
        if grouped:
            diameter_defs = {}
            for index, diameter in enumerate(sorted({round(float(stone.diameter_mm), 4) for stone in stones}), start=1):
                symbol_id = f"stone_diameter_{index}"
                diameter_defs[diameter] = symbol_id
                dwg.defs.add(dwg.circle(id=symbol_id, center=(0, 0), r=float(diameter / 2.0)))

            if grouping_mode == "pattern_layer":
                for index, (layer_name, grouped_stones) in enumerate(sorted(self.group_stones_by_pattern_layer(stones).items()), start=1):
                    safe_name = "".join(char if char.isalnum() else "_" for char in layer_name).strip("_") or f"layer_{index}"
                    group = dwg.g(id=f"pattern_{index}_{safe_name}", stroke="none")
                    for stone in grouped_stones:
                        fill = f"rgb({int(stone.rgb[0])},{int(stone.rgb[1])},{int(stone.rgb[2])})"
                        diameter = round(float(stone.diameter_mm), 4)
                        use = dwg.use(href=f"#{diameter_defs[diameter]}")
                        use.translate(float(stone.x_mm), float(stone.y_mm))
                        use.fill(fill)
                        group.add(use)
                    dwg.add(group)
            else:
                for index, ((rgb, diameter), grouped_stones) in enumerate(self.group_stones(stones).items(), start=1):
                    fill = f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
                    group = dwg.g(id=f"color_{index}", fill=fill, stroke="none")
                    for stone in grouped_stones:
                        use = dwg.use(href=f"#{diameter_defs[round(float(diameter), 4)]}")
                        use.translate(float(stone.x_mm), float(stone.y_mm))
                        group.add(use)
                    dwg.add(group)
        else:
            for stone in stones:
                fill = f"rgb({int(stone.rgb[0])},{int(stone.rgb[1])},{int(stone.rgb[2])})"
                dwg.add(
                    dwg.circle(
                        center=(float(stone.x_mm), float(stone.y_mm)),
                        r=float(stone.radius_mm),
                        fill=fill,
                        stroke="none",
                    )
                )
        dwg.save()
        logger.info(
            "export_svg path=%s stones=%s grouped=%s grouping_mode=%s background_rect=%s",
            path,
            len(stones),
            grouped,
            grouping_mode,
            has_background,
        )

    def export_png(self, image: Image.Image, path: str) -> None:
        image.save(path)

    def export_bundle(
        self,
        stones: Sequence,
        width_mm: float,
        height_mm: float,
        preview_image: Image.Image,
        base_path: str,
        background_rgb: Color = (78, 78, 78),
        include_background: bool = False,
        grouping_mode: str = "color",
    ) -> None:
        base = Path(base_path)
        self.export_svg(stones, width_mm, height_mm, str(base.with_suffix(".svg")), include_background=include_background, background_rgb=background_rgb)
        self.export_svg(
            stones,
            width_mm,
            height_mm,
            str(base.with_name(base.name + "_grouped").with_suffix(".svg")),
            grouped=True,
            grouping_mode=grouping_mode,
            include_background=include_background,
            background_rgb=background_rgb,
        )
        self.export_csv(stones, str(base.with_suffix(".csv")))
        self.export_grouped_csv(stones, str(base.with_name(base.name + "_grouped").with_suffix(".csv")))
        self.export_png(preview_image, str(base.with_suffix(".png")))
