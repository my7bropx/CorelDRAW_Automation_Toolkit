import logging

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.corel_interface import corel
from ...ui.widgets.collapsible_section import CollapsibleSection
from ...ui.widgets.tool_base import ToolBaseWidget
from ...ui.widgets.tool_components import ActionBar, InfoPanel, SettingsGroup, ToolHeader
from ..common import OperationWorker, ProgressSnapshot
from .rhinestone_engine import PatternType, RhinestoneEngine, RhinestoneSettings, STONE_SIZES

logger = logging.getLogger(__name__)


class RhinestoneWidget(ToolBaseWidget):
    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__("Rhinestone Designer", parent)
        self.engine = RhinestoneEngine()
        self._container_shape = None
        self._container_bounds = None
        self._element_shapes = []
        self._auto_detect_enabled = True
        self._last_selection_signature = None
        self._worker = None
        self._preview_cache_key = ""
        self._build_ui()
        self._configure_interaction_help()
        logger.info("Rhinestone widget initialized.")

    def _build_ui(self):
        self.add_widget(
            ToolHeader(
                "Rhinestone Designer",
                "Select a closed CorelDRAW shape, preview placements, and apply a production-ready rhinestone fill.",
            )
        )
        self.add_widget(self._build_selection_section())
        self.add_widget(self._build_pattern_section())
        self.add_widget(self._build_size_section())
        self.add_widget(self._build_options_section())
        self.add_widget(self._build_operation_section())
        self.add_widget(self._build_action_section())
        self.add_widget(self._build_preview_section())
        self.add_stretch()
        self.set_context_panel(self._build_info_panel())
        self._reset_selection_state()

    def _build_selection_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Selection")
        self.container_label = QLabel("No container")
        group.add_row("Container", self.container_label)
        self.container_info = QLabel("-")
        group.add_row("Size", self.container_info)
        self.elements_label = QLabel("No elements")
        group.add_row("Elements", self.elements_label)
        layout.addWidget(group)
        return CollapsibleSection("Selection", content, True)

    def _build_pattern_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Pattern")
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItem("Hexagonal Grid", "hexagonal")
        self.pattern_combo.addItem("Random Scatter", "random")
        self.pattern_combo.addItem("Procedural", "procedural")
        group.add_row("Type", self.pattern_combo)
        self.density = QDoubleSpinBox()
        self.density.setRange(0.1, 1.0)
        self.density.setValue(0.85)
        self.density.setSingleStep(0.05)
        group.add_row("Density", self.density)
        layout.addWidget(group)
        return CollapsibleSection("Pattern Settings", content, True)

    def _build_size_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Stone Size")
        self.stone_size = QComboBox()
        for name, mm in STONE_SIZES.items():
            self.stone_size.addItem(f"{name} ({mm}mm)", name)
        self.stone_size.setCurrentText("SS16 (3.9mm)")
        group.add_row("Preset", self.stone_size)
        self.custom_size = QDoubleSpinBox()
        self.custom_size.setRange(0.5, 20.0)
        self.custom_size.setValue(3.0)
        self.custom_size.setSuffix(" mm")
        group.add_row("Custom", self.custom_size)
        layout.addWidget(group)
        return CollapsibleSection("Stone Settings", content, True)

    def _build_options_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Options")
        self.stagger_cbx = QCheckBox("Stagger rows (honeycomb)")
        self.stagger_cbx.setChecked(True)
        group.add_full_row(self.stagger_cbx)
        self.center_cbx = QCheckBox("Center grid")
        self.center_cbx.setChecked(True)
        group.add_full_row(self.center_cbx)
        self.gap_opt_cbx = QCheckBox("Gap optimization")
        self.gap_opt_cbx.setChecked(True)
        group.add_full_row(self.gap_opt_cbx)
        layout.addWidget(group)
        return CollapsibleSection("Advanced Options", content, False)

    def _build_operation_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Operation")
        self.phase_label = QLabel("Idle")
        group.add_row("Phase", self.phase_label)
        self.elapsed_label = QLabel("00:00")
        group.add_row("Elapsed", self.elapsed_label)
        self.eta_label = QLabel("--:--")
        group.add_row("ETA", self.eta_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        group.add_full_row(self.progress_bar)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._cancel_operation)
        group.add_full_row(self.stop_btn)
        layout.addWidget(group)
        return CollapsibleSection("Operation Status", content, True)

    def _build_action_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        self.action_bar = ActionBar("Preview", "Apply", "Clear", "Refresh")
        self.action_bar.preview_clicked.connect(self._preview_shape)
        self.action_bar.apply_clicked.connect(self._fill_shape)
        self.action_bar.clear_clicked.connect(self._clear_all)
        self.action_bar.export_clicked.connect(lambda: self.refresh_selection_state(force=True))
        layout.addWidget(self.action_bar)
        return CollapsibleSection("Actions", content, True)

    def _build_preview_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        self.preview_report = QTextEdit()
        self.preview_report.setReadOnly(True)
        self.preview_report.setMinimumHeight(180)
        layout.addWidget(self.preview_report)
        return CollapsibleSection("Live Preview", content, True)

    def _build_info_panel(self):
        self.info_container = QLabel("No container")
        self.info_size = QLabel("-")
        self.stone_count = QLabel("0")
        self.coverage = QLabel("-")
        self.bounding_area = QLabel("-")
        self.overlap_warnings = QLabel("None")
        self.info_state = QLabel("Idle")
        self.info_phase = QLabel("Idle")
        self.info_elapsed = QLabel("00:00")
        self.info_eta = QLabel("--:--")
        return InfoPanel(
            "Rhinestone Info",
            sections=[
                ("Selection", [("Container", self.info_container), ("Size", self.info_size)]),
                ("Results", [("Stones", self.stone_count), ("Coverage", self.coverage), ("Bounds", self.bounding_area)]),
                ("Warnings", [("Overlap", self.overlap_warnings), ("Status", self.info_state)]),
                ("Operation", [("Phase", self.info_phase), ("Elapsed", self.info_elapsed), ("ETA", self.info_eta)]),
            ],
        )

    def _configure_interaction_help(self):
        self.enable_safe_panel_interactions()
        self.apply_default_button_tooltips()
        self.apply_tooltips([
            (self.pattern_combo, "Choose how stones are distributed across the container. Different patterns change spacing character and visual texture."),
            (self.density, "Controls how tightly stones are packed. Higher values increase coverage but can raise overlap risk and processing time."),
            (self.stone_size, "Select a preset stone diameter. Larger stones reduce count and detail, while smaller stones increase detail and runtime."),
            (self.custom_size, "Override the preset with a custom stone diameter in millimeters. This directly changes count, spacing, and output scale."),
            (self.stagger_cbx, "Offset alternate rows for a honeycomb layout. This usually gives better coverage with a more natural rhinestone pattern."),
            (self.center_cbx, "Center the generated grid inside the container bounds. Turn this off if you need alignment to stay anchored to one side."),
            (self.gap_opt_cbx, "Optimize spacing to reduce visible gaps and fit the shape more cleanly. This can add extra calculation time."),
            (self.progress_bar, "Shows progress for the active preview or apply operation."),
            (self.stop_btn, "Cancel the current preview or apply operation at the next safe stop point."),
            (self.preview_report, "Displays the latest preview summary, warnings, and expected output details before you apply changes."),
        ])

    def on_selection_changed(self, count: int):
        self.refresh_selection_state(force=False)

    def refresh_selection_state(self, force: bool = False, expected_count: int = None):
        if not self._auto_detect_enabled:
            return
        if not corel.is_connected:
            self._reset_selection_state()
            return

        try:
            shapes = corel.get_selected_shapes() or []
        except Exception as exc:
            logger.warning("Failed to read CorelDRAW selection for rhinestone widget: %s", exc)
            self._reset_selection_state()
            return

        if len(shapes) == 0:
            self._reset_selection_state()
            return

        selection_signature = self._build_selection_signature(shapes)
        if not force and selection_signature == self._last_selection_signature:
            return

        try:
            self._container_shape = shapes[0]
            self._container_bounds = self._get_shape_bounds(self._container_shape)
            self._element_shapes = shapes[1:] if len(shapes) > 1 else []
            self._last_selection_signature = selection_signature
            corel.log_shape_metrics(self._container_shape, "Rhinestone container selection")

            container_name = getattr(self._container_shape, "Name", "") or "Unnamed shape"
            display_width, display_height = self._get_display_size(self._container_shape)
            self.container_label.setText(container_name)
            self.container_info.setText(self._format_size(display_width, display_height))
            self.info_container.setText(container_name)
            self.info_size.setText(self._format_size(display_width, display_height))

            if self._element_shapes:
                element_text = f"{len(self._element_shapes)} stone element(s)"
            else:
                element_text = "Using default circles"
            self.elements_label.setText(element_text)
            self.info_state.setText("Selection synced")
            self.preview_report.setPlainText(
                "Run Preview to estimate stone count, bounds, overlap risk, and expected output before writing into CorelDRAW."
            )
        except Exception as exc:
            logger.warning("Failed to apply CorelDRAW selection to rhinestone widget: %s", exc)
            self._set_selection_error(str(exc))

    def _shape_identity(self, shape):
        parts = []
        for attr in ("StaticID", "ID", "Name", "Type"):
            try:
                value = getattr(shape, attr, None)
            except Exception:
                value = None
            if value not in (None, ""):
                parts.append(f"{attr}={value}")
        try:
            bounds = self._get_shape_bounds(shape)
            parts.append(f"bounds={bounds.left:.3f},{bounds.bottom:.3f},{bounds.right:.3f},{bounds.top:.3f}")
        except Exception:
            pass
        if not parts:
            parts.append(f"repr={repr(shape)}")
        return "|".join(parts)

    def _build_selection_signature(self, shapes) -> tuple:
        return tuple(self._shape_identity(shape) for shape in shapes)

    def _format_size(self, width: float, height: float) -> str:
        return f"{width:.3f} x {height:.3f} mm"

    def _set_combo_value(self, combo: QComboBox, value) -> None:
        if value is None:
            return
        text_value = str(value)
        index = combo.findData(text_value)
        if index < 0:
            index = combo.findText(text_value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _set_selection_error(self, message: str) -> None:
        self._container_shape = None
        self._container_bounds = None
        self._element_shapes = []
        self._last_selection_signature = None
        self.engine.clear()
        self.container_label.setText("Invalid selection")
        self.container_info.setText("Unable to read shape bounds")
        self.elements_label.setText("No elements")
        self.info_container.setText("Invalid selection")
        self.info_size.setText("Bounds unavailable")
        self.info_state.setText("Selection error")
        self.stone_count.setText("0")
        self.coverage.setText("-")
        self.bounding_area.setText("-")
        self.overlap_warnings.setText("Selection invalid")
        self.preview_report.setPlainText(
            f"Selection sync failed.\n\n{message}\n\nChoose a valid closed CorelDRAW shape and refresh the selection."
        )
        self.status_message.emit(f"Rhinestone selection error: {message}")

    def _reset_selection_state(self):
        self._container_shape = None
        self._container_bounds = None
        self._element_shapes = []
        self._last_selection_signature = None
        self._preview_cache_key = ""
        self.container_label.setText("No container")
        self.container_info.setText("-")
        self.elements_label.setText("No elements")
        self.info_container.setText("No container")
        self.info_size.setText("-")
        self.info_state.setText("Idle")
        self.info_phase.setText("Idle")
        self.info_elapsed.setText("00:00")
        self.info_eta.setText("--:--")
        self.phase_label.setText("Idle")
        self.elapsed_label.setText("00:00")
        self.eta_label.setText("--:--")
        self.progress_bar.setValue(0)
        self._set_running(False)
        self._reset_preview_state()

    def _reset_preview_state(self):
        self.engine.clear()
        self.stone_count.setText("0")
        self.coverage.setText("-")
        self.bounding_area.setText("-")
        self.overlap_warnings.setText("None")
        self.preview_report.setPlainText(
            "Run Preview to estimate stone count, bounds, overlap risk, and expected output before writing into CorelDRAW."
        )

    def _get_shape_bounds(self, shape):
        bounds = corel.get_shape_bounds(shape)
        if bounds.width <= 0 or bounds.height <= 0:
            corel.log_shape_metrics(shape, "Rhinestone invalid bounds")
            raise ValueError(f"Invalid bounds for '{getattr(shape, 'Name', 'Unnamed shape')}'.")
        return bounds

    def _get_display_size(self, shape) -> tuple:
        try:
            true_width, true_height = corel.get_true_size(shape)
            if true_width > 0 and true_height > 0:
                return true_width, true_height
        except Exception:
            pass

        bounds = self._get_shape_bounds(shape)
        return bounds.width, bounds.height

    def _validate_ready_state(self) -> bool:
        self.refresh_selection_state(force=True)
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return False
        if not self._container_shape:
            QMessageBox.warning(self, "No Container", "Select a container shape in CorelDRAW first.")
            return False
        return True

    def _confirm_document_units(self) -> bool:
        if corel.validate_document_units():
            return True
        result = QMessageBox.warning(
            self,
            "Wrong Document Units",
            "Your CorelDRAW document is not set to millimeters.\n\nAll calculations assume mm. Continue anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return result == QMessageBox.Yes

    def _build_settings(self) -> RhinestoneSettings:
        stone_size = self.stone_size.currentData()
        if stone_size == "custom":
            stone_size = str(self.custom_size.value())
        pattern_value = self.pattern_combo.currentData()
        pattern = PatternType.RANDOM if pattern_value == "random" else PatternType.HEXAGONAL
        return RhinestoneSettings(
            stone_size=stone_size,
            pattern=pattern,
            density=self.density.value(),
            gap_optimization=self.gap_opt_cbx.isChecked(),
        )

    def _settings_cache_key(self, settings: RhinestoneSettings) -> str:
        return "|".join(
            [
                str(self._last_selection_signature or ""),
                str(settings.pattern.value),
                str(settings.stone_size),
                f"{settings.density:.4f}",
                str(self.stagger_cbx.isChecked()),
                str(self.center_cbx.isChecked()),
                str(self.gap_opt_cbx.isChecked()),
                str(len(self._element_shapes)),
            ]
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
        self.action_bar.export_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

    def _cancel_operation(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.info_state.setText("Cancelling")

    def _on_snapshot(self, snapshot: ProgressSnapshot) -> None:
        self.phase_label.setText(snapshot.phase)
        self.elapsed_label.setText(self._format_duration(snapshot.elapsed_seconds))
        self.eta_label.setText(self._format_duration(snapshot.eta_seconds))
        self.progress_bar.setValue(int(round(snapshot.percent)))
        self.info_phase.setText(snapshot.phase)
        self.info_elapsed.setText(self._format_duration(snapshot.elapsed_seconds))
        self.info_eta.setText(self._format_duration(snapshot.eta_seconds))

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

    def _calculate_preview(self, progress_controller=None, cancel_callback=None):
        settings = self._build_settings()
        if settings.pattern == PatternType.RANDOM:
            self.engine.calculate_random_scatter(
                self._container_bounds,
                settings.stone_size,
                settings.density,
                settings.min_gap,
                settings=settings,
                element_shapes=self._element_shapes,
                container_shape=self._container_shape,
                progress_controller=progress_controller,
                cancel_callback=cancel_callback,
            )
        else:
            self.engine.calculate_hexagonal_grid(
                self._container_bounds,
                settings.stone_size,
                settings.density,
                settings.min_gap,
                settings,
                container_shape=self._container_shape,
                element_shapes=self._element_shapes,
                stagger=self.stagger_cbx.isChecked(),
                center_grid=self.center_cbx.isChecked(),
                progress_controller=progress_controller,
                cancel_callback=cancel_callback,
            )
        preview = self.engine.get_preview_summary(
            container_bounds=self._container_bounds,
            settings=settings,
            element_shapes=self._element_shapes,
        )
        self._update_preview_display(preview)
        return settings, preview

    def _update_preview_display(self, preview: dict):
        total_stones = preview.get("total_stones", 0)
        coverage_area = preview.get("coverage_area", 0.0)
        placement_bounds = preview.get("placement_bounds")
        overlap_pairs = preview.get("overlap_pairs", 0)
        self.stone_count.setText(str(total_stones))
        self.coverage.setText(f"{coverage_area:.1f} mm^2")
        if placement_bounds:
            self.bounding_area.setText(f"{placement_bounds.width:.1f} x {placement_bounds.height:.1f} mm")
            bounds_line = f"Placement bounds: {placement_bounds.width:.2f} x {placement_bounds.height:.2f} mm"
        else:
            self.bounding_area.setText("-")
            bounds_line = "Placement bounds: not available"
        self.overlap_warnings.setText(f"{overlap_pairs} overlap risk pair(s)" if overlap_pairs > 0 else "None")

        container_area = preview.get("container_area", 0.0)
        coverage_ratio = preview.get("coverage_ratio", 0.0) * 100.0
        output_mode = preview.get("output_mode", "Unknown")
        self.preview_report.setPlainText(
            "\n".join(
                [
                    f"Estimated stones: {total_stones}",
                    f"Estimated stone coverage: {coverage_area:.2f} mm^2",
                    f"Container area: {container_area:.2f} mm^2",
                    f"Coverage ratio: {coverage_ratio:.1f}%",
                    bounds_line,
                    (
                        f"Overlap warning: {overlap_pairs} potential pair(s) detected."
                        if overlap_pairs > 0
                        else "Overlap warning: none detected after spacing rules."
                    ),
                    f"Expected output: {output_mode}",
                    "Dry run only: no CorelDRAW shapes were created or modified.",
                ]
            )
        )

    def _preview_shape(self):
        if not self._validate_ready_state() or not self._confirm_document_units():
            return
        settings = self._build_settings()
        cache_key = self._settings_cache_key(settings)
        if self._preview_cache_key == cache_key and self.engine.stone_count > 0:
            self.info_state.setText("Preview cache reused")
            self.status_message.emit(f"Preview cache reused: {self.engine.stone_count} stones")
            return

        def task(progress_controller=None, cancel_callback=None, **_):
            settings_local, preview_local = self._calculate_preview(
                progress_controller=progress_controller,
                cancel_callback=cancel_callback,
            )
            return {"settings": settings_local, "preview": preview_local, "cache_key": cache_key}

        self._start_worker(task, self._on_preview_finished)

    def _fill_shape(self):
        if not self._validate_ready_state() or not self._confirm_document_units():
            return
        settings = self._build_settings()
        cache_key = self._settings_cache_key(settings)

        def task(progress_controller=None, progress_callback=None, cancel_callback=None, **_):
            preview = None
            reused = self._preview_cache_key == cache_key and self.engine.stone_count > 0
            if not reused:
                _, preview = self._calculate_preview(
                    progress_controller=progress_controller,
                    cancel_callback=cancel_callback,
                )
            else:
                preview = self.engine.get_preview_summary(
                    container_bounds=self._container_bounds,
                    settings=settings,
                    element_shapes=self._element_shapes,
                )
            placed = self.engine.place_stones_in_coreldraw(
                settings,
                self._element_shapes,
                self._container_bounds,
                progress_controller=progress_controller,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            )
            return {"placed": placed, "preview": preview, "cache_key": cache_key, "reused": reused}

        self._start_worker(task, self._on_apply_finished)

    def _clear_all(self):
        self._reset_selection_state()

    def _on_preview_finished(self, payload):
        self._set_running(False)
        if not self.is_tool_active():
            return
        preview = payload["preview"]
        self._preview_cache_key = payload["cache_key"]
        self.info_state.setText("Preview ready")
        if self.engine.stone_count == 0:
            QMessageBox.warning(self, "No Stones", "No stones fit the current settings. Try adjusting density or size.")
            return
        if preview.get("has_overlap_warning"):
            QMessageBox.information(self, "Preview Ready", "Preview completed with overlap warnings. Review the report before applying.")
        else:
            QMessageBox.information(self, "Preview Ready", "Preview completed. No shapes were written into CorelDRAW.")

    def _on_apply_finished(self, payload):
        self._set_running(False)
        if not self.is_tool_active():
            return
        self._preview_cache_key = payload["cache_key"]
        self.info_state.setText("Applied")
        preview = payload["preview"]
        QMessageBox.information(
            self,
            "Done",
            f"Placed {len(payload['placed'])} rhinestones.\n\nPreview estimate: {preview.get('total_stones', 0)} stone(s).",
        )

    def _on_cancelled(self):
        self._set_running(False)
        if not self.is_tool_active():
            return
        self.info_state.setText("Cancelled")
        self.phase_label.setText("Cancelled")
        self.info_phase.setText("Cancelled")
        self.status_message.emit("Rhinestone operation cancelled.")

    def _on_worker_error(self, message: str):
        self._set_running(False)
        if not self.is_tool_active():
            return
        logger.error("Rhinestone worker error: %s", message)
        self.info_state.setText("Error")
        QMessageBox.critical(self, "Error", message)

    def apply_preset(self, settings: dict):
        stone_size = settings.get("stone_size")
        if stone_size is not None:
            self._set_combo_value(self.stone_size, stone_size)
            index = self.stone_size.findData(str(stone_size))
            if index < 0:
                try:
                    self.custom_size.setValue(float(stone_size))
                except (TypeError, ValueError):
                    pass

        pattern = settings.get("pattern")
        if hasattr(pattern, "value"):
            pattern = pattern.value
        if pattern in ("hexagonal", "random", "procedural"):
            self._set_combo_value(self.pattern_combo, pattern)
        if "density" in settings:
            self.density.setValue(float(settings["density"]))
        if "gap_optimization" in settings:
            self.gap_opt_cbx.setChecked(bool(settings["gap_optimization"]))
        self.info_state.setText("Preset applied")
        self.status_message.emit("Rhinestone preset applied")

    def reset_to_defaults(self):
        self.pattern_combo.setCurrentIndex(0)
        self.density.setValue(0.85)
        default_index = self.stone_size.findData("SS16")
        if default_index >= 0:
            self.stone_size.setCurrentIndex(default_index)
        self.custom_size.setValue(3.0)
        self.stagger_cbx.setChecked(True)
        self.center_cbx.setChecked(True)
        self.gap_opt_cbx.setChecked(True)
        self._reset_selection_state()
