import logging
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

from ...core.corel_interface import CorelDRAWConnectionError, NoDocumentError, corel
from .exporter import StoneExporter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FinalRenderOptions:
    layer_name: str = "Rhinestones"
    output_mode: str = "grouped_color"
    weld_by_color: bool = False
    group_output: bool = True
    background_rgb: tuple = (255, 255, 255)
    export_background: bool = False
    debug_export: bool = False
    allow_svg_fallback: bool = False


class FinalRenderer:
    """Reliable apply path that prefers native Corel creation and keeps SVG for export/debugging."""

    def __init__(self) -> None:
        self._exporter = StoneExporter()
        self._last_export_path: Optional[Path] = None

    def _debug_export_dir(self) -> Path:
        base = Path(os.environ.get("APPDATA", Path.home()))
        target = base / "CorelDRAW_Automation_Toolkit" / "debug_exports"
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _inspect_svg(self, svg_path: Path) -> tuple[int, str, bool]:
        size = svg_path.stat().st_size if svg_path.exists() else 0
        header = svg_path.read_text(encoding="utf-8", errors="replace")[:200] if svg_path.exists() else ""
        has_background = "<rect" in header or "<rect" in svg_path.read_text(encoding="utf-8", errors="replace")[:2000]
        logger.info(
            "pointillizer svg diagnostics path=%s exists=%s size=%s has_background_rect=%s header=%r",
            svg_path,
            svg_path.exists(),
            size,
            has_background,
            header[:120],
        )
        return size, header, has_background

    def _preserve_failed_svg(self, svg_path: Path) -> Path:
        debug_dir = self._debug_export_dir()
        target = debug_dir / svg_path.name
        if svg_path.resolve() != target.resolve():
            shutil.copy2(svg_path, target)
        return target

    def _validate_corel_document_ready(self) -> None:
        logger.info(
            "pointillizer native apply preflight connected=%s has_app=%s has_document=%s active_document=%s",
            corel.is_connected,
            getattr(corel, "_app", None) is not None,
            corel.has_active_document() if corel.is_connected else False,
            corel.get_active_document_name() if corel.is_connected else "",
        )
        if not corel.is_connected:
            raise RuntimeError("CorelDRAW is not connected.")
        if not corel.has_active_document():
            raise RuntimeError("No active CorelDRAW document is open. Open a document before applying the Pointillizer output.")

    def _validate_corel_import_ready(self, svg_path: Path) -> None:
        self._validate_corel_document_ready()
        if not svg_path.exists():
            raise RuntimeError(f"Grouped SVG export was not created: {svg_path}")
        size, header, _ = self._inspect_svg(svg_path)
        if size <= 0:
            raise RuntimeError(f"Grouped SVG export is empty: {svg_path}")
        if "<svg" not in header:
            raise RuntimeError(f"Grouped SVG export does not start like a readable SVG file: {svg_path}")

    def _native_bucket_key(self, stone, output_mode: str) -> Tuple[str, Tuple[int, int, int], float]:
        if output_mode == "grouped_pattern_layer":
            return (
                str(getattr(stone, "pattern_layer", "") or getattr(stone, "color_name", "layer")),
                tuple(int(channel) for channel in stone.rgb),
                round(float(stone.diameter_mm), 4),
            )
        return (
            str(getattr(stone, "color_name", "color")),
            tuple(int(channel) for channel in stone.rgb),
            round(float(stone.diameter_mm), 4),
        )

    def _group_native_buckets(self, stones: Sequence, output_mode: str) -> Dict[Tuple[str, Tuple[int, int, int], float], list]:
        buckets: Dict[Tuple[str, Tuple[int, int, int], float], list] = {}
        for stone in stones:
            buckets.setdefault(self._native_bucket_key(stone, output_mode), []).append(stone)
        return buckets

    def _safe_name(self, text: str) -> str:
        return "".join(char if char.isalnum() or char in ("_", "-") else "_" for char in str(text)).strip("_") or "group"

    def _native_apply(
        self,
        stones: Sequence,
        layer_name: str,
        output_mode: str,
        group_output: bool,
        weld_by_color: bool,
        progress_controller=None,
        cancel_callback=None,
    ) -> int:
        self._validate_corel_document_ready()
        base_layer = corel.get_or_create_layer(layer_name)
        buckets = self._group_native_buckets(stones, output_mode)
        total = len(stones)
        created = 0
        created_groups = []
        bucket_items = sorted(buckets.items(), key=lambda item: (item[0][0], item[0][2]))

        prepare_started = time.perf_counter()
        logger.info(
            "pointillizer native apply preparation stones=%s buckets=%s output_mode=%s",
            total,
            len(bucket_items),
            output_mode,
        )
        logger.info("pointillizer native apply preparation elapsed=%.4fs", time.perf_counter() - prepare_started)

        creation_started = time.perf_counter()
        with corel.optimization_mode():
            with corel.command_group(f"{layer_name} Native Apply"):
                if progress_controller:
                    progress_controller.start_phase("Creating native Corel output", total=max(1, total), current=0, force=True)
                for bucket_index, ((group_name, rgb, diameter_mm), bucket_stones) in enumerate(bucket_items, start=1):
                    if cancel_callback and cancel_callback():
                        return created
                    template = corel.create_circle_template(base_layer, diameter_mm, no_fill=False)
                    corel.set_shape_fill_color(template, rgb)
                    corel.set_shape_no_outline(template)
                    bucket_range = corel.create_shape_range()
                    try:
                        for stone_index, stone in enumerate(bucket_stones, start=1):
                            if cancel_callback and cancel_callback():
                                return created
                            shape = corel.duplicate_centered_template(template, float(stone.x_mm), float(stone.y_mm))
                            bucket_range.Add(shape)
                            created += 1
                            if progress_controller and ((created % 100) == 0 or created == total):
                                progress_controller.update(created, total, force=(created == total))
                        if bucket_range.Count == 0:
                            continue
                        if output_mode == "welded_color" or weld_by_color:
                            try:
                                final_bucket = bucket_range.Combine()
                            except Exception as exc:
                                logger.warning("Native combine failed for %s; falling back to group: %s", group_name, exc)
                                final_bucket = bucket_range.Group() if bucket_range.Count > 1 else bucket_range.Item(1)
                        else:
                            final_bucket = bucket_range.Group() if bucket_range.Count > 1 else bucket_range.Item(1)
                        bucket_name = f"{self._safe_name(group_name)}_{diameter_mm:.2f}mm"
                        corel.try_set_shape_name(final_bucket, bucket_name)
                        created_groups.append(final_bucket)
                    finally:
                        try:
                            corel.delete_shape(template)
                        except Exception:
                            pass
        creation_elapsed = time.perf_counter() - creation_started
        logger.info("pointillizer native creation stones=%s elapsed=%.4fs", created, creation_elapsed)

        finalize_started = time.perf_counter()
        if group_output and len(created_groups) > 1:
            try:
                group_range = corel.create_shape_range()
                for shape in created_groups:
                    group_range.Add(shape)
                grouped = group_range.Group()
                corel.try_set_shape_name(grouped, self._safe_name(layer_name))
            except Exception as exc:
                logger.warning("Native final grouping failed: %s", exc)
        logger.info("pointillizer native finalization elapsed=%.4fs", time.perf_counter() - finalize_started)
        corel.refresh()
        return created

    def render_colored_circles(
        self,
        stones: Sequence,
        layer_name: str = "Rhinestones",
        progress_controller=None,
        progress_callback=None,
        cancel_callback=None,
        group_output: bool = True,
        output_mode: str = "grouped_color",
        width_mm: Optional[float] = None,
        height_mm: Optional[float] = None,
        weld_by_color: bool = False,
        background_rgb=(255, 255, 255),
        export_background: bool = False,
        debug_export: bool = False,
        allow_svg_fallback: bool = False,
    ) -> int:
        if not stones:
            return 0
        if not corel.is_connected:
            raise RuntimeError("CorelDRAW is not connected.")
        self._validate_corel_document_ready()

        width_mm = float(width_mm if width_mm is not None else max(stone.x_mm + stone.radius_mm for stone in stones))
        height_mm = float(height_mm if height_mm is not None else max(stone.y_mm + stone.radius_mm for stone in stones))
        debug_svg_path: Optional[Path] = None
        if debug_export:
            grouping_mode = "pattern_layer" if output_mode == "grouped_pattern_layer" else "color"
            debug_svg_path = self._debug_export_dir() / f"pointillizer_grouped_{int(time.time())}.svg"
            self._last_export_path = debug_svg_path
            export_started = time.perf_counter()
            self._exporter.export_svg(
                stones,
                width_mm,
                height_mm,
                str(debug_svg_path),
                grouped=True,
                grouping_mode=grouping_mode,
                include_background=export_background,
                background_rgb=background_rgb,
            )
            logger.info(
                "pointillizer debug svg export stones=%s elapsed=%.4fs grouping_mode=%s path=%s",
                len(stones),
                time.perf_counter() - export_started,
                grouping_mode,
                debug_svg_path,
            )
            self._inspect_svg(debug_svg_path)

        if output_mode == "separate" and len(stones) > 12000:
            raise RuntimeError(
                f"Separate native apply is unsafe for {len(stones)} stones. Switch to grouped native apply, reduce stone count, or use Export only."
            )

        try:
            if progress_controller:
                progress_controller.start_phase("Preparing native apply", total=3, current=0, force=True)
            native_started = time.perf_counter()
            created = self._native_apply(
                stones,
                layer_name=layer_name,
                output_mode=output_mode,
                group_output=group_output,
                weld_by_color=weld_by_color,
                progress_controller=progress_controller,
                cancel_callback=cancel_callback,
            )
            logger.info("pointillizer native apply total elapsed=%.4fs", time.perf_counter() - native_started)
        except Exception as native_exc:
            logger.error("Native apply failed after generation: %s", native_exc)
            if allow_svg_fallback and debug_svg_path is not None:
                self._append_svg_fallback_log(debug_svg_path)
                self._validate_corel_import_ready(debug_svg_path)
                try:
                    import_started = time.perf_counter()
                    imported = corel.import_svg_to_layer(str(debug_svg_path), layer_name)
                    logger.info("pointillizer svg fallback import elapsed=%.4fs", time.perf_counter() - import_started)
                    if output_mode != "grouped_pattern_layer":
                        imported = corel.try_group_or_weld_by_color(imported, weld=weld_by_color or output_mode == "welded_color")
                    if group_output and imported is not None and hasattr(imported, "Group"):
                        imported = imported.Group()
                    corel.refresh()
                    created = len(stones)
                except (NoDocumentError, CorelDRAWConnectionError) as exc:
                    preserved = self._preserve_failed_svg(debug_svg_path)
                    raise RuntimeError(f"Native apply failed and SVG fallback precondition failed: {exc}. Debug SVG kept at: {preserved}") from exc
                except Exception as exc:
                    preserved = self._preserve_failed_svg(debug_svg_path)
                    raise RuntimeError(f"Native apply failed and SVG fallback import failed: {exc}. Debug SVG kept at: {preserved}") from exc
            else:
                if debug_svg_path is not None:
                    raise RuntimeError(f"Native Corel apply failed. Debug SVG kept at: {debug_svg_path}. Error: {native_exc}") from native_exc
                raise RuntimeError(f"Native Corel apply failed: {native_exc}") from native_exc

        if progress_callback:
            progress_callback(created, len(stones))
        return created

    def _append_svg_fallback_log(self, svg_path: Path) -> None:
        logger.warning("Native apply failed; attempting explicit SVG fallback using %s", svg_path)
