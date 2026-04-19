import logging
import math
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.corel_interface import CurveSegment, Point, corel
from ...ui.widgets.collapsible_section import CollapsibleSection
from ...ui.widgets.tool_base import ToolBaseWidget
from ...ui.widgets.tool_components import ActionBar, InfoPanel, SettingsGroup, ToolHeader
from ..common import FinalRenderer, OperationWorker, PointillizerPreviewCanvas, ProgressSnapshot, StoneExporter
from .pattern_fill_engine import PatternFillConfig, PatternFillEngine, PatternPath

logger = logging.getLogger(__name__)


class PatternFillWidget(ToolBaseWidget):
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Pattern Fill", parent)
        self.engine = PatternFillEngine()
        self.final_renderer = FinalRenderer()
        self.exporter = StoneExporter()
        self._worker: Optional[OperationWorker] = None
        self._shape = None
        self._bounds = None
        self._paths: List[PatternPath] = []
        self._result = None
        self._selection_name = "pattern_fill"
        self._build_ui()
        self._configure_interaction_help()
        self.add_stretch()
        self._set_running(False)

    def _build_ui(self):
        self.add_widget(ToolHeader("Pattern Fill", "Generate structured rhinestone layouts from vector paths, offsets, rays, and shape fill without using photo sampling."))
        self.add_widget(self._selection_section())
        self.add_widget(self._pattern_section())
        self.add_widget(self._color_section())
        self.add_widget(self._output_section())
        self.add_widget(self._status_section())
        self.add_widget(self._preview_section())
        self.add_widget(self._actions_section())
        self.set_context_panel(self._info_panel())

    def _selection_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Selection")
        self.lbl_shape = QLabel("No vector shape")
        self.lbl_bounds = QLabel("-")
        self.lbl_paths = QLabel("0")
        group.add_row("Shape", self.lbl_shape)
        group.add_row("Bounds", self.lbl_bounds)
        group.add_row("Paths", self.lbl_paths)
        btn = QPushButton("Use Selected Vector Geometry")
        btn.clicked.connect(self._capture_selection)
        group.add_full_row(btn)
        layout.addWidget(group)
        return CollapsibleSection("Selection", content, True)

    def _pattern_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)

        base = SettingsGroup("Base Pattern")
        self.spn_stone = QDoubleSpinBox(); self.spn_stone.setRange(1.0, 12.0); self.spn_stone.setValue(2.8); self.spn_stone.setSuffix(" mm")
        self.spn_spacing = QDoubleSpinBox(); self.spn_spacing.setRange(0.0, 10.0); self.spn_spacing.setValue(0.2); self.spn_spacing.setSuffix(" mm")
        self.spn_margin = QDoubleSpinBox(); self.spn_margin.setRange(0.0, 10.0); self.spn_margin.setValue(0.2); self.spn_margin.setSuffix(" mm")
        self.cmb_fill_layout = QComboBox(); self.cmb_fill_layout.addItem("Hex", "hex"); self.cmb_fill_layout.addItem("Grid", "grid")
        base.add_row("Stone size", self.spn_stone)
        base.add_row("Spacing", self.spn_spacing)
        base.add_row("Edge margin", self.spn_margin)
        base.add_row("Fill layout", self.cmb_fill_layout)

        generators = SettingsGroup("Generators")
        self.chk_boundary = QCheckBox("Boundary placement"); self.chk_boundary.setChecked(True)
        self.chk_curve = QCheckBox("Curve placement"); self.chk_curve.setChecked(True)
        self.chk_offsets = QCheckBox("Offset curves")
        self.chk_rays = QCheckBox("Ray / radial pattern")
        self.chk_fill = QCheckBox("Interior shape fill"); self.chk_fill.setChecked(True)
        generators.add_full_row(self.chk_boundary)
        generators.add_full_row(self.chk_curve)
        generators.add_full_row(self.chk_offsets)
        generators.add_full_row(self.chk_rays)
        generators.add_full_row(self.chk_fill)

        offsets = SettingsGroup("Offsets && Rays")
        self.spn_offset = QDoubleSpinBox(); self.spn_offset.setRange(0.0, 30.0); self.spn_offset.setValue(3.0); self.spn_offset.setSuffix(" mm")
        self.spn_offset_count = QDoubleSpinBox(); self.spn_offset_count.setRange(0, 12); self.spn_offset_count.setDecimals(0); self.spn_offset_count.setValue(2)
        self.spn_ray_count = QDoubleSpinBox(); self.spn_ray_count.setRange(1, 360); self.spn_ray_count.setDecimals(0); self.spn_ray_count.setValue(24)
        self.spn_ray_start = QDoubleSpinBox(); self.spn_ray_start.setRange(-360, 360); self.spn_ray_start.setValue(0); self.spn_ray_start.setSuffix(" deg")
        self.spn_ray_end = QDoubleSpinBox(); self.spn_ray_end.setRange(-360, 360); self.spn_ray_end.setValue(360); self.spn_ray_end.setSuffix(" deg")
        self.cmb_ray_center = QComboBox(); self.cmb_ray_center.addItem("Bounds center", "bounds_center"); self.cmb_ray_center.addItem("Manual", "manual")
        self.spn_center_x = QDoubleSpinBox(); self.spn_center_x.setRange(-5000, 5000); self.spn_center_x.setValue(0); self.spn_center_x.setSuffix(" mm")
        self.spn_center_y = QDoubleSpinBox(); self.spn_center_y.setRange(-5000, 5000); self.spn_center_y.setValue(0); self.spn_center_y.setSuffix(" mm")
        offsets.add_row("Offset step", self.spn_offset)
        offsets.add_row("Offset count", self.spn_offset_count)
        offsets.add_row("Ray count", self.spn_ray_count)
        offsets.add_row("Angle start", self.spn_ray_start)
        offsets.add_row("Angle end", self.spn_ray_end)
        offsets.add_row("Ray center", self.cmb_ray_center)
        offsets.add_row("Center X", self.spn_center_x)
        offsets.add_row("Center Y", self.spn_center_y)

        layout.addWidget(base)
        layout.addWidget(generators)
        layout.addWidget(offsets)
        return CollapsibleSection("Pattern", content, True)

    def _color_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Colors")
        self.cmb_color_mode = QComboBox()
        self.cmb_color_mode.addItem("Single color", "single")
        self.cmb_color_mode.addItem("Per layer", "per_layer")
        self.cmb_color_mode.addItem("Per rule", "per_rule")
        self.cmb_single_color = QComboBox()
        for name in ("crystal", "jet", "sapphire", "aquamarine", "hyacinth", "citrine", "emerald", "rose"):
            self.cmb_single_color.addItem(name.title(), name)
        group.add_row("Mode", self.cmb_color_mode)
        group.add_row("Single color", self.cmb_single_color)
        layout.addWidget(group)
        return CollapsibleSection("Colors", content, True)

    def _output_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Output")
        self.cmb_output_mode = QComboBox()
        self.cmb_output_mode.addItem("Grouped by color", "grouped_color")
        self.cmb_output_mode.addItem("Grouped by pattern layer", "grouped_pattern_layer")
        self.cmb_output_mode.addItem("Merged/Welded by color", "welded_color")
        self.chk_group = QCheckBox("Group imported output"); self.chk_group.setChecked(True)
        self.chk_weld = QCheckBox("Weld by color when possible")
        self.chk_debug_export = QCheckBox("Keep debug SVG for Apply")
        self.edt_output = QLineEdit()
        self.edt_output.setPlaceholderText("Optional export base path")
        group.add_row("Apply mode", self.cmb_output_mode)
        group.add_row("Export base", self.edt_output)
        group.add_full_row(self.chk_group)
        group.add_full_row(self.chk_weld)
        group.add_full_row(self.chk_debug_export)
        layout.addWidget(group)
        return CollapsibleSection("Output", content, True)

    def _status_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Operation")
        self.phase_label = QLabel("Idle")
        self.elapsed_label = QLabel("00:00")
        self.eta_label = QLabel("--:--")
        self.progress_bar = QProgressBar(); self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0)
        self.stop_btn = QPushButton("Stop"); self.stop_btn.clicked.connect(self._cancel_operation)
        group.add_row("Phase", self.phase_label)
        group.add_row("Elapsed", self.elapsed_label)
        group.add_row("ETA", self.eta_label)
        group.add_full_row(self.progress_bar)
        group.add_full_row(self.stop_btn)
        layout.addWidget(group)
        return CollapsibleSection("Status", content, True)

    def _preview_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        self.preview_canvas = PointillizerPreviewCanvas()
        self.output_log = QPlainTextEdit(); self.output_log.setReadOnly(True); self.output_log.setMinimumHeight(160)
        layout.addWidget(self.preview_canvas)
        layout.addWidget(self.output_log)
        return CollapsibleSection("Preview", content, True)

    def _actions_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        self.actions = ActionBar("Preview", "Apply", "Clear", "Export")
        self.actions.preview_clicked.connect(self._start_preview)
        self.actions.apply_clicked.connect(self._start_apply)
        self.actions.clear_clicked.connect(self.reset_to_defaults)
        self.actions.export_clicked.connect(self._start_export)
        layout.addWidget(self.actions)
        return CollapsibleSection("Actions", content, True)

    def _info_panel(self):
        self.info_shape = QLabel("No shape")
        self.info_paths = QLabel("0")
        self.info_stones = QLabel("0")
        self.info_layers = QLabel("-")
        self.info_status = QLabel("Idle")
        self.info_elapsed = QLabel("00:00")
        self.info_eta = QLabel("--:--")
        return InfoPanel(
            "Pattern Fill Info",
            sections=[
                ("Selection", [("Shape", self.info_shape), ("Paths", self.info_paths)]),
                ("Result", [("Stones", self.info_stones), ("Layers", self.info_layers)]),
                ("Operation", [("Status", self.info_status), ("Elapsed", self.info_elapsed), ("ETA", self.info_eta)]),
            ],
        )

    def _configure_interaction_help(self):
        self.enable_safe_panel_interactions()
        self.apply_default_button_tooltips()
        self.apply_tooltips([
            (self.spn_stone, "Base stone diameter for the vector-driven pattern engine. Spacing and edge fit are derived from this size."),
            (self.spn_spacing, "Extra spacing between stones. Lower spacing gives denser bands and fills."),
            (self.spn_offset, "Distance between successive offset curves for banded or fan-like layouts."),
            (self.spn_offset_count, "How many parallel offset bands to generate from each selected path."),
            (self.spn_ray_count, "Number of rays emitted from the chosen center point."),
            (self.cmb_fill_layout, "Packing used for interior vector fill. Hex is denser; grid is more geometric."),
            (self.chk_boundary, "Generate a clean outline pass along closed shape edges before filling the interior."),
            (self.chk_curve, "Place stones directly along the original vector curves with uniform spacing."),
            (self.chk_offsets, "Add parallel curves from the base paths to create bands, fans, and contour-driven structure."),
            (self.chk_rays, "Generate radial placements from a center point through the valid shape area."),
            (self.chk_fill, "Fill the valid interior region with a structured packing after boundary and curve passes."),
            (self.cmb_color_mode, "Choose whether colors are assigned once, per generated pattern layer, or per generator rule."),
            (self.cmb_output_mode, "Controls how final Apply organizes the SVG/Corel import result."),
            (self.edt_output, "Optional export base path for SVG, CSV, and PNG output. Leave empty to export into Downloads with the selection name."),
            (self.chk_group, "Group the imported result in CorelDRAW after the fast grouped SVG import finishes."),
            (self.chk_weld, "Try to weld or combine imported color groups after import. This may simplify output but can change editability."),
            (self.chk_debug_export, "Keep the grouped SVG used for Apply in the debug export folder so import problems are easier to inspect."),
            (self.preview_canvas, "Batched preview of the structured vector pattern. Ctrl+wheel zooms and drag pans without recomputing."),
        ])

    def _segment_polyline(self, segment: CurveSegment, tolerance: float = 0.15) -> List[Point]:
        if not segment.is_bezier:
            return [segment.start, segment.end]
        length = max(segment.length, tolerance)
        steps = max(4, int(math.ceil(length / max(0.05, tolerance))))
        return [segment.get_point_at_t(index / steps) for index in range(steps + 1)]

    def _flatten_paths(self, shape, tolerance: float = 0.15) -> List[PatternPath]:
        paths: List[PatternPath] = []
        for path_index, segments in enumerate(corel.get_curve_subpaths(shape, require_closed=False), start=1):
            points: List[Point] = []
            closed = False
            for segment in segments or []:
                polyline = self._segment_polyline(segment, tolerance=tolerance)
                if points and polyline:
                    polyline = polyline[1:]
                points.extend(polyline)
            if len(points) >= 2:
                closed = points[0].distance_to(points[-1]) <= 0.25
                tuples = tuple((float(point.x), float(point.y)) for point in points)
                paths.append(PatternPath(points=tuples, closed=closed, name=f"path_{path_index}"))
        return paths

    def _capture_selection(self):
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            self._shape = selection.Item(1)
            self._bounds = corel.get_shape_bounds(self._shape)
            self._paths = self._flatten_paths(self._shape)
            name = getattr(self._shape, "Name", "") or "Selected shape"
            self._selection_name = "".join(char if char.isalnum() or char in ("_", "-") else "_" for char in name).strip("_") or "pattern_fill"
            self.lbl_shape.setText(name)
            self.lbl_bounds.setText(f"{self._bounds.width:.2f} x {self._bounds.height:.2f} mm")
            self.lbl_paths.setText(str(len(self._paths)))
            self.info_shape.setText(name)
            self.info_paths.setText(str(len(self._paths)))
            self.status_message.emit(f"Pattern Fill selection captured: {name}")
        except Exception as exc:
            QMessageBox.critical(self, "Selection Error", str(exc))

    def _config(self) -> PatternFillConfig:
        palette = {
            "crystal": (239, 239, 239),
            "jet": (18, 18, 18),
            "sapphire": (44, 82, 205),
            "aquamarine": (60, 201, 214),
            "hyacinth": (220, 88, 62),
            "citrine": (239, 199, 58),
            "emerald": (67, 186, 92),
            "rose": (219, 125, 191),
        }
        return PatternFillConfig(
            width_mm=float(self._bounds.width if self._bounds else 100.0),
            height_mm=float(self._bounds.height if self._bounds else 100.0),
            stone_diameter_mm=self.spn_stone.value(),
            spacing_mm=self.spn_spacing.value(),
            offset_mm=self.spn_offset.value(),
            offset_count=int(self.spn_offset_count.value()),
            edge_margin_mm=self.spn_margin.value(),
            fill_layout=self.cmb_fill_layout.currentData(),
            ray_count=int(self.spn_ray_count.value()),
            ray_angle_start_deg=self.spn_ray_start.value(),
            ray_angle_end_deg=self.spn_ray_end.value(),
            ray_center_mode=self.cmb_ray_center.currentData(),
            ray_center_x_mm=self.spn_center_x.value(),
            ray_center_y_mm=self.spn_center_y.value(),
            enable_curve=self.chk_curve.isChecked(),
            enable_offsets=self.chk_offsets.isChecked(),
            enable_rays=self.chk_rays.isChecked(),
            enable_fill=self.chk_fill.isChecked(),
            enable_boundary=self.chk_boundary.isChecked(),
            color_mode=self.cmb_color_mode.currentData(),
            single_color_name=self.cmb_single_color.currentData(),
            single_color_rgb=palette[self.cmb_single_color.currentData()],
            palette=palette,
        )

    def _format_duration(self, seconds: Optional[float]) -> str:
        if seconds is None:
            return "--:--"
        total = max(0, int(round(seconds)))
        return f"{total // 60:02d}:{total % 60:02d}"

    def _set_running(self, running: bool) -> None:
        self.actions.preview_btn.setEnabled(not running)
        self.actions.apply_btn.setEnabled(not running)
        self.actions.export_btn.setEnabled(not running)
        self.actions.clear_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def _cancel_operation(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()

    def _on_snapshot(self, snapshot: ProgressSnapshot) -> None:
        self.phase_label.setText(snapshot.phase)
        self.elapsed_label.setText(self._format_duration(snapshot.elapsed_seconds))
        self.eta_label.setText(self._format_duration(snapshot.eta_seconds))
        self.progress_bar.setValue(int(round(snapshot.percent)))
        self.info_status.setText(snapshot.phase)
        self.info_elapsed.setText(self._format_duration(snapshot.elapsed_seconds))
        self.info_eta.setText(self._format_duration(snapshot.eta_seconds))
        self.progress_updated.emit(int(round(snapshot.percent)), 100)

    def _start_worker(self, func, finished_slot) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Busy", "An operation is already running.")
            return
        self._worker = OperationWorker(func)
        self._worker.snapshot.connect(self._on_snapshot)
        self._worker.finished.connect(finished_slot)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.error.connect(self._on_error)
        self._set_running(True)
        self.info_status.setText("Running")
        self.progress_bar.setValue(0)
        self._worker.start()

    def on_tool_activated(self) -> None:
        super().on_tool_activated()

    def on_tool_deactivated(self) -> None:
        self.cancel_pending_work()
        super().on_tool_deactivated()

    def cancel_pending_work(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()

    def suspend_live_updates(self) -> None:
        self.preview_canvas.setUpdatesEnabled(False)
        super().suspend_live_updates()

    def resume_live_updates(self) -> None:
        super().resume_live_updates()
        self.preview_canvas.setUpdatesEnabled(True)

    def _ensure_selection(self) -> bool:
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return False
        if not self._shape or not self._bounds or not self._paths:
            QMessageBox.warning(self, "No Vector", "Capture a vector selection first.")
            return False
        return True

    def _preview_task(self, progress_controller=None, **_):
        return self.engine.generate(self._bounds, self._paths, self._config(), progress_controller=progress_controller)

    def _apply_task(self, progress_controller=None, cancel_callback=None, **_):
        result = self.engine.generate(self._bounds, self._paths, self._config(), progress_controller=progress_controller)
        created = self.final_renderer.render_colored_circles(
            result.stones,
            layer_name="Pattern Fill",
            progress_controller=progress_controller,
            cancel_callback=cancel_callback,
            group_output=self.chk_group.isChecked(),
            output_mode=self.cmb_output_mode.currentData(),
            width_mm=result.width_mm,
            height_mm=result.height_mm,
            weld_by_color=self.chk_weld.isChecked(),
            debug_export=self.chk_debug_export.isChecked(),
        )
        return {"result": result, "created": created}

    def _export_task(self, progress_controller=None, **_):
        result = self.engine.generate(self._bounds, self._paths, self._config(), progress_controller=progress_controller)
        base_text = self.edt_output.text().strip()
        base = Path(base_text) if base_text else Path.home() / "Downloads" / self._selection_name
        grouping_mode = "pattern_layer" if self.cmb_output_mode.currentData() == "grouped_pattern_layer" else "color"
        self.exporter.export_bundle(
            result.stones,
            result.width_mm,
            result.height_mm,
            result.preview_image,
            str(base),
            grouping_mode=grouping_mode,
        )
        return {"result": result, "base": str(base)}

    def _start_preview(self):
        if not self._ensure_selection():
            return
        self.output_log.appendPlainText("Generating pattern preview...")
        self._start_worker(self._preview_task, self._on_preview_finished)

    def _start_apply(self):
        if not self._ensure_selection():
            return
        self.output_log.appendPlainText("Applying pattern fill to CorelDRAW...")
        self._start_worker(self._apply_task, self._on_apply_finished)

    def _start_export(self):
        if not self._ensure_selection():
            return
        self.output_log.appendPlainText("Exporting pattern fill bundle...")
        self._start_worker(self._export_task, self._on_export_finished)

    def _show_result(self, result):
        self._result = result
        self.preview_canvas.set_scene(result.preview_scene, "Pattern fill preview")
        self.info_stones.setText(str(len(result.stones)))
        self.info_layers.setText(", ".join(f"{name}:{count}" for name, count in result.per_layer.items() if count > 0) or "-")
        self.info_status.setText("Ready")
        self.output_log.appendPlainText(
            "Timings: " + ", ".join(f"{name}={value:.3f}s" for name, value in sorted(result.timings.items()))
        )

    def _on_preview_finished(self, result):
        self._set_running(False)
        if not self.is_tool_active():
            return
        self._show_result(result)
        self.output_log.appendPlainText(f"Preview ready: {len(result.stones)} stones.")
        self.status_message.emit(f"Pattern Fill preview ready: {len(result.stones)} stones")

    def _on_apply_finished(self, payload):
        self._set_running(False)
        if not self.is_tool_active():
            return
        self._show_result(payload["result"])
        self.output_log.appendPlainText(f"Applied {payload['created']} stones.")
        self.status_message.emit(f"Pattern Fill applied: {payload['created']} stones")

    def _on_export_finished(self, payload):
        self._set_running(False)
        if not self.is_tool_active():
            return
        self._show_result(payload["result"])
        self.output_log.appendPlainText(f"Exported bundle to {payload['base']}.svg/.csv/.png")
        self.status_message.emit(f"Pattern Fill exported: {payload['base']}")

    def _on_cancelled(self):
        self._set_running(False)
        if not self.is_tool_active():
            return
        self.info_status.setText("Cancelled")
        self.phase_label.setText("Cancelled")
        self.output_log.appendPlainText("Operation cancelled.")
        self.status_message.emit("Pattern Fill operation cancelled")

    def _on_error(self, message: str):
        self._set_running(False)
        if not self.is_tool_active():
            return
        self.info_status.setText("Failed")
        self.output_log.appendPlainText(f"Error: {message}")
        self.status_message.emit(f"Pattern Fill failed: {message}")
        QMessageBox.critical(self, "Pattern Fill Error", message)

    def refresh_selection_state(self, force: bool = False):
        if force and corel.is_connected and corel.has_selection():
            try:
                selection = corel.get_selection()
                shape = selection.Item(1)
                name = getattr(shape, "Name", "") or "Selected shape"
                self.lbl_shape.setText(name)
                self.info_shape.setText(name)
            except Exception:
                return

    def reset_to_defaults(self):
        self.spn_stone.setValue(2.8)
        self.spn_spacing.setValue(0.2)
        self.spn_margin.setValue(0.2)
        self.cmb_fill_layout.setCurrentIndex(0)
        self.chk_boundary.setChecked(True)
        self.chk_curve.setChecked(True)
        self.chk_offsets.setChecked(False)
        self.chk_rays.setChecked(False)
        self.chk_fill.setChecked(True)
        self.spn_offset.setValue(3.0)
        self.spn_offset_count.setValue(2)
        self.spn_ray_count.setValue(24)
        self.spn_ray_start.setValue(0)
        self.spn_ray_end.setValue(360)
        self.cmb_ray_center.setCurrentIndex(0)
        self.spn_center_x.setValue(0)
        self.spn_center_y.setValue(0)
        self.cmb_color_mode.setCurrentIndex(1)
        self.cmb_single_color.setCurrentIndex(0)
        self.cmb_output_mode.setCurrentIndex(0)
        self.chk_group.setChecked(True)
        self.chk_weld.setChecked(False)
        self.chk_debug_export.setChecked(False)
        self.edt_output.clear()
        self.preview_canvas.clear_scene("No preview generated")
        self.output_log.clear()
        self._result = None
        self._shape = None
        self._bounds = None
        self._paths = []
        self._selection_name = "pattern_fill"
        self.lbl_shape.setText("No vector shape")
        self.lbl_bounds.setText("-")
        self.lbl_paths.setText("0")
        self.info_shape.setText("No shape")
        self.info_paths.setText("0")
        self.info_stones.setText("0")
        self.info_layers.setText("-")
        self.info_status.setText("Idle")
        self.info_elapsed.setText("00:00")
        self.info_eta.setText("--:--")
        self.phase_label.setText("Idle")
        self.elapsed_label.setText("00:00")
        self.eta_label.setText("--:--")
        self.progress_bar.setValue(0)
