import logging
from dataclasses import dataclass
from typing import Dict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.corel_interface import corel
from ...ui.widgets.collapsible_section import CollapsibleSection
from ...ui.widgets.tool_base import ToolBaseWidget
from ...ui.widgets.tool_components import ActionBar, SettingsGroup
from ..common import OperationWorker, ProgressSnapshot
from .curve_filler_engine import (
    AngleMode,
    CurveFillerEngine,
    DirectionMode,
    FillSettings,
    OverlapMode,
    PatternMode,
    SpacingMode,
)

logger = logging.getLogger(__name__)

@dataclass
class CurveFillerConfig:
    spacing_mode: str
    spacing_value: float
    angle_mode: str
    fixed_angle: float
    direction: str
    pattern_mode: str
    collision_detection: bool
    remove_overlaps: bool
    overlap_mode: str
    use_element_size: bool
    offset_from_curve: float

    def to_engine_settings(self) -> FillSettings:
        settings = FillSettings()
        settings.spacing_mode = SpacingMode(self.spacing_mode)
        settings.spacing_value = self.spacing_value
        settings.angle_mode = AngleMode(self.angle_mode)
        settings.fixed_angle = self.fixed_angle
        settings.direction = DirectionMode(self.direction)
        settings.pattern_mode = PatternMode(self.pattern_mode)
        settings.collision_detection = self.collision_detection
        settings.remove_overlaps = self.remove_overlaps
        settings.overlap_mode = OverlapMode(self.overlap_mode)
        settings.use_element_size = self.use_element_size
        settings.offset_from_curve = self.offset_from_curve
        return settings


class CurveFillerController:
    def __init__(self, engine: CurveFillerEngine):
        self.engine = engine

    def sync_selection(self):
        selection = corel.get_selection()
        count = selection.Count if selection else 0
        if count == 0:
            raise ValueError("No CorelDRAW selection found.")

        container = selection.Item(1)
        self.engine.set_container(container)

        if count > 1:
            elements = [selection.Item(i) for i in range(2, count + 1)]
        else:
            elements = [container]

        self.engine.set_fill_elements(elements)
        return {
            "container_name": getattr(container, "Name", "Unnamed shape") or "Unnamed shape",
            "element_count": len(elements),
        }

    def preview(self, config: CurveFillerConfig):
        # Re-sync inside the worker thread so cached COM shapes are thread-local.
        self.sync_selection()
        settings = config.to_engine_settings()
        return self.engine.calculate_placements(settings)

    def apply(self, config: CurveFillerConfig, progress_callback=None, cancel_callback=None):
        # Re-sync inside the worker thread so cached COM shapes are thread-local.
        self.sync_selection()
        settings = config.to_engine_settings()
        placements = self.engine.calculate_placements(settings)
        return self.engine.execute_fill(
            placements,
            settings,
            progress_callback=progress_callback,
            cancel_callback=cancel_callback,
        )

    def clear(self):
        self.engine.clear_placed_elements()


class CurveFillerWidget(ToolBaseWidget):
    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        self.engine = CurveFillerEngine()
        self.controller = CurveFillerController(self.engine)
        self._worker = None
        self._last_selection_notice = ""
        super().__init__("Curve Filler", parent)
        self._build_ui()
        self._configure_interaction_help()
        self.add_stretch()
        self._set_running(False)

    def _build_ui(self):
        title = QLabel("Curve Filler")
        title_font = QFont(title.font())
        title_font.setPointSize(max(title_font.pointSize(), 14))
        title_font.setBold(True)
        title.setFont(title_font)
        self.add_widget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_basic_tab(), "Basic")
        self.tabs.addTab(self._build_advanced_tab(), "Advanced")
        self.add_widget(self.tabs)

        self.set_context_panel(self._build_context_panel())

    def _build_basic_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._geometry_section())
        layout.addWidget(self._pattern_section())
        layout.addWidget(self._stone_section())
        layout.addWidget(self._operation_section())
        layout.addWidget(self._actions_section())
        layout.addStretch()
        return page

    def _build_advanced_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._advanced_section())
        layout.addStretch()
        return page

    def _geometry_section(self):
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        group = SettingsGroup("Geometry / Input")
        self.container_label = QLabel("Not synced")
        self.elements_label = QLabel("0")
        group.add_row("Container", self.container_label)
        group.add_row("Elements", self.elements_label)
        body.addWidget(group)

        self.sync_btn = QPushButton("Sync Corel Selection")
        self.sync_btn.clicked.connect(self._sync_selection)
        body.addWidget(self.sync_btn)

        return CollapsibleSection("Geometry / Input", content, True)

    def _pattern_section(self):
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        group = SettingsGroup("Pattern Settings")

        self.spacing_mode = QComboBox()
        self.spacing_mode.addItem("Fixed", SpacingMode.FIXED.value)
        self.spacing_mode.addItem("Percentage", SpacingMode.PERCENTAGE.value)
        self.spacing_mode.addItem("Auto Fit", SpacingMode.AUTO_FIT.value)
        self.spacing_mode.addItem("Random", SpacingMode.RANDOM.value)

        self.spacing_value = QDoubleSpinBox()
        self.spacing_value.setRange(0.1, 1000.0)
        self.spacing_value.setDecimals(2)
        self.spacing_value.setSuffix(" mm")
        self.spacing_value.setValue(10.0)

        self.angle_mode = QComboBox()
        self.angle_mode.addItem("Follow Curve", AngleMode.FOLLOW_CURVE.value)
        self.angle_mode.addItem("Fixed Angle", AngleMode.FIXED.value)
        self.angle_mode.addItem("Perpendicular", AngleMode.PERPENDICULAR.value)

        self.direction = QComboBox()
        self.direction.addItem("Outside", DirectionMode.OUTSIDE.value)
        self.direction.addItem("Inside", DirectionMode.INSIDE.value)
        self.direction.addItem("Both", DirectionMode.BOTH.value)

        self.pattern_mode = QComboBox()
        self.pattern_mode.addItem("Single", PatternMode.SINGLE.value)
        self.pattern_mode.addItem("Sequence", PatternMode.SEQUENCE.value)
        self.pattern_mode.addItem("Random", PatternMode.RANDOM.value)
        self.pattern_mode.addItem("Alternating", PatternMode.ALTERNATING.value)

        group.add_row("Spacing Mode", self.spacing_mode)
        group.add_row("Spacing", self.spacing_value)
        group.add_row("Rotation", self.angle_mode)
        group.add_row("Direction", self.direction)
        group.add_row("Pattern", self.pattern_mode)

        body.addWidget(group)
        return CollapsibleSection("Pattern Settings", content, True)

    def _stone_section(self):
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        group = SettingsGroup("Stone Settings")

        self.use_element_size = QCheckBox("Use selected element size")
        self.use_element_size.setChecked(True)

        self.offset_from_curve = QDoubleSpinBox()
        self.offset_from_curve.setRange(-1000.0, 1000.0)
        self.offset_from_curve.setDecimals(2)
        self.offset_from_curve.setSuffix(" mm")
        self.offset_from_curve.setValue(0.0)

        group.add_row("Offset", self.offset_from_curve)
        group.add_row("Element Sizing", self.use_element_size)

        body.addWidget(group)
        return CollapsibleSection("Stone Settings", content, True)

    def _advanced_section(self):
        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        group = SettingsGroup("Advanced Controls")

        self.fixed_angle = QDoubleSpinBox()
        self.fixed_angle.setRange(-360.0, 360.0)
        self.fixed_angle.setDecimals(1)
        self.fixed_angle.setSuffix(" deg")
        self.fixed_angle.setValue(0.0)

        self.collision_detection = QCheckBox("Enable collision detection")
        self.remove_overlaps = QCheckBox("Remove overlaps")
        self.remove_overlaps.setChecked(True)

        self.overlap_mode = QComboBox()
        self.overlap_mode.addItem("None", OverlapMode.NONE.value)
        self.overlap_mode.addItem("Remove Duplicates", OverlapMode.REMOVE_DUPLICATES.value)
        self.overlap_mode.addItem("Collision Detect", OverlapMode.COLLISION_DETECT.value)

        group.add_row("Fixed Angle", self.fixed_angle)
        group.add_row("Overlap Mode", self.overlap_mode)
        group.add_row("Collision", self.collision_detection)
        group.add_row("Cleanup", self.remove_overlaps)

        body.addWidget(group)
        return CollapsibleSection("Advanced Controls", content, False)

    def _operation_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Operation")
        self.phase_label = QLabel("Idle")
        group.add_row("Phase", self.phase_label)
        self.elapsed_value = QLabel("00:00")
        group.add_row("Elapsed", self.elapsed_value)
        self.eta_value = QLabel("--:--")
        group.add_row("ETA", self.eta_value)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        group.add_full_row(self.progress_bar)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._cancel_operation)
        group.add_full_row(self.stop_btn)
        layout.addWidget(group)
        return CollapsibleSection("Operation Status", content, True)

    def _actions_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)

        self.action_bar = ActionBar()
        self.action_bar.preview_clicked.connect(self._preview)
        self.action_bar.apply_clicked.connect(self._apply)
        self.action_bar.clear_clicked.connect(self._clear)
        self.action_bar.export_btn.hide()

        layout.addWidget(self.action_bar)
        return CollapsibleSection("Actions", content, True)

    def _build_context_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Curve Filler Info")
        info_font = QFont(title.font())
        info_font.setPointSize(max(info_font.pointSize(), 11))
        info_font.setBold(True)
        title.setFont(info_font)
        layout.addWidget(title)

        summary = QGroupBox("Summary")
        form = QFormLayout(summary)

        self.preview_count = QLabel("0")
        self.status_label = QLabel("Idle")
        self.warning_label = QLabel("No warnings")
        self.phase_value = QLabel("Idle")
        self.elapsed_context = QLabel("00:00")
        self.eta_context = QLabel("--:--")

        form.addRow("Preview Count", self.preview_count)
        form.addRow("Status", self.status_label)
        form.addRow("Warnings", self.warning_label)
        form.addRow("Phase", self.phase_value)
        form.addRow("Elapsed", self.elapsed_context)
        form.addRow("ETA", self.eta_context)

        layout.addWidget(summary)
        layout.addStretch()
        return panel

    def _configure_interaction_help(self):
        self.enable_safe_panel_interactions()
        self.apply_default_button_tooltips()
        self.apply_tooltips([
            (self.sync_btn, "Read the current CorelDRAW selection and use it as the curve filler container and elements."),
            (self.spacing_mode, "Choose how spacing is calculated along the curve. Different modes trade off control, randomness, and fit accuracy."),
            (self.spacing_value, "Base spacing value used by the selected spacing mode. Smaller values create denser fills and can increase runtime."),
            (self.angle_mode, "Controls how each element rotates along the curve. This changes flow, direction, and visual consistency."),
            (self.direction, "Choose which side of the curve receives the fill. This affects output placement relative to the selected path."),
            (self.pattern_mode, "Select how multiple elements repeat along the curve. More complex modes can create richer but less predictable layouts."),
            (self.use_element_size, "Use the selected CorelDRAW element size when calculating spacing. This helps keep physical output closer to the source element."),
            (self.offset_from_curve, "Offset placed elements away from the curve in millimeters. Useful for clearance and layered effects."),
            (self.fixed_angle, "Rotation angle used when the rotation mode is set to Fixed Angle."),
            (self.overlap_mode, "Controls how overlapping placements are handled. Safer cleanup modes may remove stones but improve output reliability."),
            (self.collision_detection, "Check placements for collisions before final output. This adds safety but can slow heavy previews."),
            (self.remove_overlaps, "Remove overlapping results during cleanup so the final output is safer and easier to manufacture."),
            (self.progress_bar, "Shows progress for the active preview or apply operation."),
            (self.stop_btn, "Cancel the current curve fill operation at the next safe stop point."),
        ])

    def _config(self):
        return CurveFillerConfig(
            spacing_mode=self.spacing_mode.currentData(),
            spacing_value=self.spacing_value.value(),
            angle_mode=self.angle_mode.currentData(),
            fixed_angle=self.fixed_angle.value(),
            direction=self.direction.currentData(),
            pattern_mode=self.pattern_mode.currentData(),
            collision_detection=self.collision_detection.isChecked(),
            remove_overlaps=self.remove_overlaps.isChecked(),
            overlap_mode=self.overlap_mode.currentData(),
            use_element_size=self.use_element_size.isChecked(),
            offset_from_curve=self.offset_from_curve.value(),
        )

    def _format_duration(self, seconds) -> str:
        if seconds is None:
            return "--:--"
        total = max(0, int(round(seconds)))
        return f"{total // 60:02d}:{total % 60:02d}"

    def _set_running(self, running: bool) -> None:
        self.action_bar.preview_btn.setEnabled(not running)
        self.action_bar.apply_btn.setEnabled(not running)
        self.action_bar.clear_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def _cancel_operation(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.status_label.setText("Cancelling")

    def _on_snapshot(self, snapshot: ProgressSnapshot) -> None:
        self.phase_label.setText(snapshot.phase)
        self.elapsed_value.setText(self._format_duration(snapshot.elapsed_seconds))
        self.eta_value.setText(self._format_duration(snapshot.eta_seconds))
        self.progress_bar.setValue(int(round(snapshot.percent)))
        self.phase_value.setText(snapshot.phase)
        self.elapsed_context.setText(self._format_duration(snapshot.elapsed_seconds))
        self.eta_context.setText(self._format_duration(snapshot.eta_seconds))

    def _start_worker(self, func, finished_slot) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Busy", "An operation is already running.")
            return
        self._worker = OperationWorker(func)
        self._worker.snapshot.connect(self._on_snapshot)
        self._worker.finished.connect(finished_slot)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.error.connect(self._on_worker_error)
        self.progress_bar.setValue(0)
        self._set_running(True)
        self._worker.start()

    def on_tool_activated(self) -> None:
        super().on_tool_activated()

    def on_tool_deactivated(self) -> None:
        self.cancel_pending_work()
        super().on_tool_deactivated()

    def cancel_pending_work(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()

    def _sync_selection(self):
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return
        try:
            data = self.controller.sync_selection()
            self.container_label.setText(data["container_name"])
            self.elements_label.setText(str(data["element_count"]))
            self.status_label.setText("Selection synced")
            self.warning_label.setText("No warnings")
            self._last_selection_notice = ""
            self.status_message.emit("Selection synced")
        except Exception as exc:
            logger.error("Curve Filler selection sync failed: %s", exc)
            message = str(exc)
            self.status_label.setText("Waiting for selection")
            self.warning_label.setText(message)
            if self._last_selection_notice != message:
                self.status_message.emit(f"Curve Filler selection: {message}")
                self._last_selection_notice = message

    def _preview(self):
        self._start_worker(lambda **_: self.controller.preview(self._config()), self._on_preview_finished)

    def _apply(self):
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return
        self._start_worker(
            lambda progress_callback=None, cancel_callback=None, **_: self.controller.apply(
                self._config(),
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            ),
            self._on_apply_finished,
        )

    def _clear(self):
        try:
            self.controller.clear()
            self.preview_count.setText("0")
            self.status_label.setText("Cleared")
            self.warning_label.setText("No warnings")
            self.status_message.emit("Curve Filler cleared")
        except Exception as exc:
            logger.error("Curve Filler clear failed: %s", exc)
            QMessageBox.critical(self, "Clear Error", str(exc))

    def _on_preview_finished(self, placements):
        self._set_running(False)
        if not self.is_tool_active():
            return
        self.preview_count.setText(str(len(placements)))
        self.status_label.setText("Preview ready")
        self.status_message.emit(f"Preview: {len(placements)} placements")

    def _on_apply_finished(self, shapes):
        self._set_running(False)
        if not self.is_tool_active():
            return
        count = len(shapes) if shapes else 0
        self.status_label.setText("Applied")
        self.status_message.emit(f"Applied {count} elements")

    def _on_cancelled(self):
        self._set_running(False)
        if not self.is_tool_active():
            return
        self.status_label.setText("Cancelled")
        self.phase_label.setText("Cancelled")
        self.phase_value.setText("Cancelled")

    def _on_worker_error(self, message: str):
        self._set_running(False)
        if not self.is_tool_active():
            return
        logger.error("Curve Filler worker failed: %s", message)
        if message == "Operation cancelled.":
            self.status_label.setText("Cancelled")
            return
        QMessageBox.critical(self, "Operation Error", message)

    def refresh_selection_state(self, force: bool = False):
        if corel.is_connected and force:
            try:
                self._sync_selection()
            except Exception:
                pass

    def on_selection_changed(self, count: int):
        if count > 0:
            self.refresh_selection_state(force=True)

    def _set_combo_value(self, combo: QComboBox, value) -> None:
        if value is None:
            return
        text_value = str(value)
        index = combo.findData(text_value)
        if index < 0:
            index = combo.findText(text_value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def apply_preset(self, settings: Dict[str, object]):
        self._set_combo_value(self.spacing_mode, settings.get("spacing_mode"))
        if "spacing_value" in settings:
            self.spacing_value.setValue(float(settings["spacing_value"]))
        self._set_combo_value(self.angle_mode, settings.get("angle_mode"))
        if "fixed_angle" in settings:
            self.fixed_angle.setValue(float(settings["fixed_angle"]))
        self._set_combo_value(self.direction, settings.get("direction"))
        self._set_combo_value(self.pattern_mode, settings.get("pattern_mode"))
        if "collision_detection" in settings:
            self.collision_detection.setChecked(bool(settings["collision_detection"]))
        if "remove_overlaps" in settings:
            self.remove_overlaps.setChecked(bool(settings["remove_overlaps"]))
        self._set_combo_value(self.overlap_mode, settings.get("overlap_mode"))
        if "use_element_size" in settings:
            self.use_element_size.setChecked(bool(settings["use_element_size"]))
        if "offset_from_curve" in settings:
            self.offset_from_curve.setValue(float(settings["offset_from_curve"]))
        self.status_label.setText("Preset applied")
        self.warning_label.setText("No warnings")
        self.status_message.emit("Curve Filler preset applied")

    def reset_to_defaults(self):
        self.spacing_mode.setCurrentIndex(0)
        self.spacing_value.setValue(10.0)
        self.angle_mode.setCurrentIndex(0)
        self.fixed_angle.setValue(0.0)
        self.direction.setCurrentIndex(0)
        self.pattern_mode.setCurrentIndex(0)
        self.collision_detection.setChecked(False)
        self.remove_overlaps.setChecked(True)
        self.overlap_mode.setCurrentIndex(0)
        self.use_element_size.setChecked(True)
        self.offset_from_curve.setValue(0.0)
        self.preview_count.setText("0")
        self.status_label.setText("Idle")
        self.warning_label.setText("No warnings")
        self.phase_label.setText("Idle")
        self.phase_value.setText("Idle")
        self.elapsed_value.setText("00:00")
        self.elapsed_context.setText("00:00")
        self.eta_value.setText("--:--")
        self.eta_context.setText("--:--")
        self.progress_bar.setValue(0)
        self._set_running(False)
