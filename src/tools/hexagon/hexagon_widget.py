"""
PyQt5 widget for the hexagon design engine.
"""

import logging
from typing import List, Optional

from PyQt5.QtCore import QThread, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.corel_interface import corel
from ...ui.widgets.tool_base import ToolBaseWidget
from ...ui.widgets.tool_components import InfoPanel, ToolHeader
from ..common import OperationCancelled, ProgressController, ProgressSnapshot
from .hexagon_engine import (
    CollisionAction,
    DEFAULT_FIT_FACTOR,
    FIT_FACTOR_MAX,
    FIT_FACTOR_MIN,
    HoneycombOrigin,
    HexSettings,
    HexStone,
    HexagonEngine,
    OutputMode,
    PathDistribution,
    STONE_SIZES,
)
from .preview_widget import PreviewWidget

logger = logging.getLogger(__name__)


class _Worker(QThread):
    progress = pyqtSignal(int, int)
    snapshot = pyqtSignal(object)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            import pythoncom

            pythoncom.CoInitialize()
            com_ready = True
        except Exception:
            com_ready = False

        try:
            controller = ProgressController(
                snapshot_callback=lambda snapshot: self.snapshot.emit(snapshot),
                cancel_check=lambda: self._cancelled,
            )
            result = self._func(
                *self._args,
                progress_controller=controller,
                progress_callback=lambda current, total: self.progress.emit(current, total),
                cancel_callback=lambda: self._cancelled,
                **self._kwargs,
            )
            self.finished.emit(result)
        except OperationCancelled:
            self.error.emit("Operation cancelled.")
        except Exception as exc:
            logger.error("Hexagon worker failed: %s", exc)
            self.error.emit(str(exc))
        finally:
            if com_ready:
                try:
                    import pythoncom

                    pythoncom.CoUninitialize()
                except Exception:
                    pass


class HexagonWidget(ToolBaseWidget):
    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__("Hexagon Designer", parent)
        self.engine = HexagonEngine()
        self._container_shape = None
        self._curve_shape = None
        self._element_shape = None
        self._selection_shapes = []
        self._last_selection_signature = None
        self._container_bounds = None
        self._container_contours = []
        self._container_segments = []
        self._curve_segments = []
        self._curve_length = 0.0
        self._last_stones: List[HexStone] = []
        self._worker: Optional[_Worker] = None
        self._last_preview_key = ""
        self._pending_preview_key = ""
        self._size_table_initialized = False
        self._build_ui()
        self._configure_interaction_help()
        self._refresh_preview()

    def _build_ui(self) -> None:
        self.add_widget(
            ToolHeader(
                "Hexagon Designer",
                "Blend stones along curves, fill closed contours with honeycomb packing, preview locally, and export or render through CorelDRAW.",
            )
        )

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_stone_tab(), "Stone Size")
        self.tabs.addTab(self._build_path_tab(), "Path Blend")
        self.tabs.addTab(self._build_fill_tab(), "Hatch Fill")
        self.tabs.addTab(self._build_collision_tab(), "Collision")
        self.tabs.addTab(self._build_preview_tab(), "Preview")
        self.tabs.addTab(self._build_results_tab(), "Results")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.add_widget(self.tabs)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.add_widget(self.progress_bar)

        actions = QHBoxLayout()
        self.btn_path = QPushButton("Fill Path")
        self.btn_fill = QPushButton("Fill Shape")
        self.btn_place = QPushButton("Draw in CorelDRAW")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_clear = QPushButton("Clear")

        self.btn_path.clicked.connect(self._run_path_fill)
        self.btn_fill.clicked.connect(self._run_hatch_fill)
        self.btn_place.clicked.connect(self._run_place)
        self.btn_cancel.clicked.connect(self._cancel_worker)
        self.btn_clear.clicked.connect(self._clear)
        self.btn_cancel.setVisible(False)

        actions.addWidget(self.btn_path)
        actions.addWidget(self.btn_fill)
        actions.addWidget(self.btn_place)
        actions.addWidget(self.btn_cancel)
        actions.addWidget(self.btn_clear)
        actions_widget = QWidget()
        actions_widget.setLayout(actions)
        self.add_widget(actions_widget)
        self.add_stretch()
        self.set_context_panel(self._build_info_panel())
        self.cmb_output_mode.currentTextChanged.connect(self.info_output.setText)

    def _build_info_panel(self) -> QWidget:
        self.info_container = QLabel("Not set")
        self.info_curve = QLabel("Not set")
        self.info_element = QLabel("Default circle")
        self.info_count = QLabel("0")
        self.info_coverage = QLabel("0.00 mm^2")
        self.info_overlaps = QLabel("0")
        self.info_output = QLabel("Render in CorelDRAW")
        self.info_status = QLabel("Idle")
        self.info_phase = QLabel("Idle")
        self.info_elapsed = QLabel("00:00")
        self.info_eta = QLabel("--:--")
        return InfoPanel(
            "Hexagon Info",
            sections=[
                ("Selection", [("Container", self.info_container), ("Path", self.info_curve), ("Element", self.info_element)]),
                ("Results", [("Stones", self.info_count), ("Coverage", self.info_coverage), ("Overlaps", self.info_overlaps)]),
                ("Output", [("Mode", self.info_output), ("Status", self.info_status)]),
                ("Operation", [("Phase", self.info_phase), ("Elapsed", self.info_elapsed), ("ETA", self.info_eta)]),
            ],
        )

    def _build_stone_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        selection_group = QGroupBox("CorelDRAW Selection")
        selection_form = QFormLayout(selection_group)
        self.lbl_container = QLabel("Not set")
        self.lbl_curve = QLabel("Not set")
        self.lbl_element = QLabel("Default circle")
        selection_form.addRow("Container shape:", self.lbl_container)
        selection_form.addRow("Path/curve:", self.lbl_curve)
        selection_form.addRow("Stone element:", self.lbl_element)

        selection_buttons = QHBoxLayout()
        btn_container = QPushButton("Set Container from Selection")
        btn_curve = QPushButton("Set Path from Selection")
        btn_element = QPushButton("Set Stone Element from Selection")
        btn_container.clicked.connect(self._set_container)
        btn_curve.clicked.connect(self._set_curve)
        btn_element.clicked.connect(self._set_element)
        selection_buttons.addWidget(btn_container)
        selection_buttons.addWidget(btn_curve)
        selection_buttons.addWidget(btn_element)
        selection_form.addRow(selection_buttons)
        layout.addWidget(selection_group)

        size_group = QGroupBox("Stone Size")
        size_form = QFormLayout(size_group)
        self.cmb_size = QComboBox()
        self.cmb_size.addItem("Custom", "custom")
        for code, diameter in STONE_SIZES.items():
            self.cmb_size.addItem(f"{code} ({diameter} mm)", code)
        default_index = self.cmb_size.findData("SS10")
        if default_index >= 0:
            self.cmb_size.setCurrentIndex(default_index)
        self.cmb_size.currentIndexChanged.connect(self._on_size_changed)
        size_form.addRow("Size:", self.cmb_size)

        self.spn_custom = QDoubleSpinBox()
        self.spn_custom.setRange(0.5, 25.0)
        self.spn_custom.setDecimals(2)
        self.spn_custom.setSuffix(" mm")
        self.spn_custom.setValue(2.80)
        self.spn_custom.setEnabled(False)
        self.spn_custom.valueChanged.connect(self._refresh_preview)
        size_form.addRow("Custom diameter:", self.spn_custom)
        layout.addWidget(size_group)

        fit_group = QGroupBox("Template Fit")
        fit_form = QFormLayout(fit_group)
        self.spn_fit = QDoubleSpinBox()
        self.spn_fit.setRange(FIT_FACTOR_MIN, FIT_FACTOR_MAX)
        self.spn_fit.setDecimals(3)
        self.spn_fit.setSingleStep(0.01)
        self.spn_fit.setValue(DEFAULT_FIT_FACTOR)
        self.spn_fit.valueChanged.connect(self._refresh_preview)
        fit_form.addRow("Fit factor:", self.spn_fit)

        self.spn_gap = QDoubleSpinBox()
        self.spn_gap.setRange(0.0, 10.0)
        self.spn_gap.setDecimals(2)
        self.spn_gap.setSuffix(" mm")
        self.spn_gap.setValue(0.20)
        self.spn_gap.valueChanged.connect(self._refresh_preview)
        fit_form.addRow("Minimum gap:", self.spn_gap)

        self.lbl_template = QLabel("-")
        self.lbl_pitch = QLabel("-")
        fit_form.addRow("Template diameter:", self.lbl_template)
        fit_form.addRow("Center pitch:", self.lbl_pitch)
        layout.addWidget(fit_group)

        table_group = QGroupBox("Size Reference")
        table_layout = QVBoxLayout(table_group)
        self.tbl_sizes = QTableWidget(0, 3)
        self.tbl_sizes.setHorizontalHeaderLabels(["Code", "Physical mm", "Template mm"])
        self.tbl_sizes.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_sizes.setEditTriggers(QTableWidget.NoEditTriggers)
        table_layout.addWidget(self.tbl_sizes)
        btn_table = QPushButton("Refresh Table")
        btn_table.clicked.connect(self._refresh_table)
        table_layout.addWidget(btn_table)
        layout.addWidget(table_group)
        layout.addStretch()
        return widget

    def _build_path_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        dist_group = QGroupBox("Distribution")
        dist_form = QFormLayout(dist_group)
        self.cmb_path_distribution = QComboBox()
        self.cmb_path_distribution.addItem("Distribute evenly", PathDistribution.DISTRIBUTE.value)
        self.cmb_path_distribution.addItem("Fixed pitch", PathDistribution.FIXED_PITCH.value)
        self.cmb_path_distribution.addItem("Fit exact", PathDistribution.FIT_EXACT.value)
        dist_form.addRow("Mode:", self.cmb_path_distribution)
        layout.addWidget(dist_group)

        spacing_group = QGroupBox("Spacing")
        spacing_form = QFormLayout(spacing_group)
        self.spn_path_extra_gap = QDoubleSpinBox()
        self.spn_path_extra_gap.setRange(0.0, 20.0)
        self.spn_path_extra_gap.setDecimals(2)
        self.spn_path_extra_gap.setSuffix(" mm")
        spacing_form.addRow("Extra path gap:", self.spn_path_extra_gap)

        self.spn_start_padding = QDoubleSpinBox()
        self.spn_start_padding.setRange(0.0, 500.0)
        self.spn_start_padding.setDecimals(2)
        self.spn_start_padding.setSuffix(" mm")
        spacing_form.addRow("Start padding:", self.spn_start_padding)

        self.spn_end_padding = QDoubleSpinBox()
        self.spn_end_padding.setRange(0.0, 500.0)
        self.spn_end_padding.setDecimals(2)
        self.spn_end_padding.setSuffix(" mm")
        spacing_form.addRow("End padding:", self.spn_end_padding)
        layout.addWidget(spacing_group)

        rotate_group = QGroupBox("Rotation")
        rotate_layout = QVBoxLayout(rotate_group)
        self.chk_tangent = QCheckBox("Rotate stones to curve tangent")
        self.chk_tangent.setChecked(True)
        rotate_layout.addWidget(self.chk_tangent)
        layout.addWidget(rotate_group)
        layout.addStretch()
        return widget

    def _build_fill_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        fill_group = QGroupBox("Honeycomb Grid")
        fill_form = QFormLayout(fill_group)
        self.spn_stagger = QDoubleSpinBox()
        self.spn_stagger.setRange(0.0, 100.0)
        self.spn_stagger.setDecimals(1)
        self.spn_stagger.setSuffix(" %")
        self.spn_stagger.setValue(50.0)
        fill_form.addRow("Row stagger:", self.spn_stagger)

        self.spn_grid_angle = QDoubleSpinBox()
        self.spn_grid_angle.setRange(-180.0, 180.0)
        self.spn_grid_angle.setDecimals(1)
        self.spn_grid_angle.setSuffix(" deg")
        fill_form.addRow("Grid angle:", self.spn_grid_angle)

        self.spn_edge_margin = QDoubleSpinBox()
        self.spn_edge_margin.setRange(0.0, 100.0)
        self.spn_edge_margin.setDecimals(2)
        self.spn_edge_margin.setSuffix(" mm")
        fill_form.addRow("Edge margin:", self.spn_edge_margin)

        self.cmb_origin = QComboBox()
        self.cmb_origin.addItem("Center", HoneycombOrigin.CENTER.value)
        self.cmb_origin.addItem("Top left", HoneycombOrigin.TOP_LEFT.value)
        self.cmb_origin.addItem("Bottom left", HoneycombOrigin.BOTTOM_LEFT.value)
        fill_form.addRow("Grid origin:", self.cmb_origin)

        self.chk_clip_shape = QCheckBox("Clip to actual shape boundary")
        self.chk_clip_shape.setChecked(True)
        fill_form.addRow(self.chk_clip_shape)
        layout.addWidget(fill_group)
        layout.addStretch()
        return widget

    def _build_collision_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox("Collision Handling")
        form = QFormLayout(group)
        self.cmb_collision = QComboBox()
        self.cmb_collision.addItem("Remove second stone", CollisionAction.REMOVE_SECOND.value)
        self.cmb_collision.addItem("Merge to midpoint", CollisionAction.MERGE_MIDPOINT.value)
        self.cmb_collision.addItem("Shrink both", CollisionAction.SHRINK_BOTH.value)
        self.cmb_collision.addItem("Highlight only", CollisionAction.HIGHLIGHT.value)
        form.addRow("Action:", self.cmb_collision)

        self.spn_collision_gap = QDoubleSpinBox()
        self.spn_collision_gap.setRange(0.0, 5.0)
        self.spn_collision_gap.setDecimals(2)
        self.spn_collision_gap.setSuffix(" mm")
        form.addRow("Collision gap:", self.spn_collision_gap)

        self.spn_shrink_min = QDoubleSpinBox()
        self.spn_shrink_min.setRange(0.10, 1.00)
        self.spn_shrink_min.setDecimals(2)
        self.spn_shrink_min.setSingleStep(0.05)
        self.spn_shrink_min.setValue(0.60)
        form.addRow("Minimum shrink factor:", self.spn_shrink_min)
        layout.addWidget(group)

        buttons = QHBoxLayout()
        btn_check = QPushButton("Check Overlaps")
        btn_fix = QPushButton("Apply Collision Rule")
        btn_check.clicked.connect(self._check_overlaps)
        btn_fix.clicked.connect(self._fix_overlaps)
        buttons.addWidget(btn_check)
        buttons.addWidget(btn_fix)
        layout.addLayout(buttons)

        self.lbl_overlap_result = QLabel("")
        self.lbl_overlap_result.setWordWrap(True)
        layout.addWidget(self.lbl_overlap_result)
        layout.addStretch()
        return widget

    def _build_preview_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.preview_widget = PreviewWidget()
        layout.addWidget(self.preview_widget)
        return widget

    def _build_results_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        results = QGroupBox("Results")
        form = QFormLayout(results)
        self.lbl_count = QLabel("0")
        self.lbl_coverage = QLabel("0.00 mm^2")
        self.lbl_overlaps = QLabel("0")
        form.addRow("Stone count:", self.lbl_count)
        form.addRow("Coverage:", self.lbl_coverage)
        form.addRow("Flagged overlaps:", self.lbl_overlaps)
        layout.addWidget(results)

        output = QGroupBox("Output")
        output_form = QFormLayout(output)
        self.cmb_output_mode = QComboBox()
        self.cmb_output_mode.addItem("Preview only", OutputMode.PREVIEW_ONLY.value)
        self.cmb_output_mode.addItem("Export JSON only", OutputMode.EXPORT_ONLY.value)
        self.cmb_output_mode.addItem("Render in CorelDRAW", OutputMode.COREL_RENDER.value)
        self.cmb_output_mode.setCurrentIndex(2)
        output_form.addRow("Output mode:", self.cmb_output_mode)

        self.chk_group_output = QCheckBox("Group output after drawing")
        self.chk_group_output.setChecked(True)
        output_form.addRow(self.chk_group_output)

        self.edt_layer = QLineEdit("Rhinestones")
        output_form.addRow("Target layer:", self.edt_layer)

        self.lbl_last_export = QLabel("-")
        self.lbl_last_export.setWordWrap(True)
        output_form.addRow("Last JSON:", self.lbl_last_export)
        layout.addWidget(output)
        layout.addStretch()
        return widget

    def _build_settings(self) -> HexSettings:
        settings = HexSettings(
            stone_size=self.cmb_size.currentData(),
            custom_diameter=self.spn_custom.value(),
            fit_factor=self.spn_fit.value(),
            min_gap=self.spn_gap.value(),
            path_distribution=PathDistribution(self.cmb_path_distribution.currentData()),
            path_start_padding=self.spn_start_padding.value(),
            path_end_padding=self.spn_end_padding.value(),
            path_rotate_to_tangent=self.chk_tangent.isChecked(),
            path_extra_gap=self.spn_path_extra_gap.value(),
            hatch_origin=HoneycombOrigin(self.cmb_origin.currentData()),
            hatch_row_angle=self.spn_grid_angle.value(),
            hatch_edge_margin=self.spn_edge_margin.value(),
            hatch_stagger_pct=self.spn_stagger.value(),
            hatch_clip_to_shape=self.chk_clip_shape.isChecked(),
            collision_action=CollisionAction(self.cmb_collision.currentData()),
            collision_gap=self.spn_collision_gap.value(),
            shrink_min_factor=self.spn_shrink_min.value(),
            group_output=self.chk_group_output.isChecked(),
            layer_name=self.edt_layer.text().strip() or "Rhinestones",
            output_mode=OutputMode(self.cmb_output_mode.currentData()),
        )
        self.info_output.setText(self.cmb_output_mode.currentText())
        return settings

    def _configure_interaction_help(self) -> None:
        self.enable_safe_panel_interactions()
        self.apply_default_button_tooltips()
        self.apply_tooltips([
            (self.cmb_size, "Choose a preset stone size or switch to Custom for a manual diameter."),
            (self.spn_custom, "Custom stone diameter in millimeters. Smaller stones add detail but increase count and runtime."),
            (self.spn_fit, "Template fit factor used to convert physical stone size into placement spacing. Small changes can noticeably affect coverage."),
            (self.spn_gap, "Minimum gap to keep between stones. Larger gaps reduce collisions but lower density."),
            (self.tbl_sizes, "Reference table showing preset stone sizes and their computed template diameters."),
            (self.cmb_path_distribution, "Controls how stones are spaced along the selected path. Different modes trade off exact fit and regular spacing."),
            (self.spn_path_extra_gap, "Additional gap inserted between stones on path fills."),
            (self.spn_start_padding, "Leaves empty space at the start of the path before the first stone is placed."),
            (self.spn_end_padding, "Leaves empty space at the end of the path after the last stone is placed."),
            (self.chk_tangent, "Rotate stones to follow the path direction. This usually looks more natural on curved layouts."),
            (self.spn_stagger, "Row offset percentage for honeycomb fills. Changing this alters the interlock pattern."),
            (self.spn_grid_angle, "Rotate the hatch grid to a custom angle. This can improve fit or produce a different visual flow."),
            (self.spn_edge_margin, "Keep stones away from the outer edge of the container shape."),
            (self.cmb_origin, "Choose the anchor point used to seed the hatch grid inside the container."),
            (self.chk_clip_shape, "Trim stones to the actual container boundary for cleaner final output."),
            (self.cmb_collision, "Rule used when overlapping stones are detected. Safer rules may remove or shrink stones."),
            (self.spn_collision_gap, "Minimum allowed gap before stones are treated as colliding."),
            (self.spn_shrink_min, "Smallest shrink factor allowed when the collision rule uses shrinking."),
            (self.preview_widget, "Interactive preview of the current hexagon layout before drawing into CorelDRAW."),
            (self.cmb_output_mode, "Choose whether to preview only, export JSON, or render directly in CorelDRAW."),
            (self.chk_group_output, "Group all generated output after drawing so the result is easier to move and manage."),
            (self.edt_layer, "Target CorelDRAW layer name used for rendered output."),
            (self.progress_bar, "Shows progress for the active fill, preview, or draw operation."),
            (self.btn_cancel, "Cancel the current long-running hexagon operation at a safe point."),
        ])

    def _on_size_changed(self) -> None:
        self.spn_custom.setEnabled(self.cmb_size.currentData() == "custom")
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        settings = self._build_settings()
        self.lbl_template.setText(f"{settings.template_diameter():.4f} mm")
        self.lbl_pitch.setText(f"{settings.pitch():.4f} mm")

    def _refresh_table(self) -> None:
        table = self.engine.size_table(self.spn_fit.value())
        self.tbl_sizes.setRowCount(len(table))
        for row, (code, values) in enumerate(table.items()):
            self.tbl_sizes.setItem(row, 0, QTableWidgetItem(code))
            self.tbl_sizes.setItem(row, 1, QTableWidgetItem(f"{values['physical_mm']:.2f}"))
            self.tbl_sizes.setItem(row, 2, QTableWidgetItem(f"{values['template_mm']:.4f}"))
        self._size_table_initialized = True

    def _on_tab_changed(self, index: int) -> None:
        if index == 0 and not self._size_table_initialized:
            self._refresh_table()

    def _set_combo_value(self, combo: QComboBox, value) -> None:
        if value is None:
            return
        text_value = str(value)
        index = combo.findData(text_value)
        if index < 0:
            index = combo.findText(text_value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _ensure_corel_ready(self) -> bool:
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return False
        if not corel.validate_document_units():
            result = QMessageBox.warning(
                self,
                "Wrong Document Units",
                "Your CorelDRAW document is not set to millimeters.\n\n"
                "This tool expects mm for size and spacing calculations.\n\n"
                "Continue anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if result != QMessageBox.Yes:
                return False
        return True

    def refresh_selection_state(self, force: bool = False, expected_count: int = None) -> None:
        """Refresh the current CorelDRAW selection snapshot for the widget."""
        if not corel.is_connected:
            self._selection_shapes = []
            self._last_selection_signature = None
            logger.debug("Hexagon selection refresh skipped because CorelDRAW is not connected.")
            return

        try:
            shapes = corel.get_selected_shapes() or []
        except Exception as exc:
            logger.warning("Failed to read CorelDRAW selection for Hexagon tool: %s", exc)
            self._selection_shapes = []
            self._last_selection_signature = None
            return

        signature = self._build_selection_signature(shapes)
        if not force and signature == self._last_selection_signature:
            return

        if expected_count is not None and expected_count != len(shapes):
            logger.debug(
                "Hexagon selection count mismatch between event (%s) and COM read (%s). Using COM selection.",
                expected_count,
                len(shapes),
            )

        self._selection_shapes = shapes
        self._last_selection_signature = signature
        logger.debug("Hexagon selection refreshed: %s shape(s).", len(shapes))

    def _build_selection_signature(self, shapes) -> tuple:
        """Build a stable signature for the currently selected shapes."""
        signature = []
        for shape in shapes:
            try:
                left = float(shape.LeftX)
                bottom = float(shape.BottomY)
                right = float(shape.RightX)
                top = float(shape.TopY)
                bounds_part = f"{left:.3f},{bottom:.3f},{right:.3f},{top:.3f}"
            except Exception:
                bounds_part = "bounds=?"

            shape_id = []
            for attr in ("StaticID", "ID", "Name", "Type"):
                try:
                    value = getattr(shape, attr, None)
                except Exception:
                    value = None
                if value not in (None, ""):
                    shape_id.append(f"{attr}={value}")
            shape_id.append(bounds_part)
            signature.append("|".join(shape_id))
        return tuple(signature)

    def _selected_shape(self, index: int = 0):
        """Return a selected shape from the current CorelDRAW snapshot."""
        self.refresh_selection_state(force=True)
        if len(self._selection_shapes) <= index:
            return None
        return self._selection_shapes[index]

    def _set_container_from_shape(self, shape, emit_status: bool = True) -> bool:
        """Assign the container shape and update UI."""
        if shape is None:
            return False

        try:
            corel.log_shape_metrics(shape, "Hexagon container selection")
            self._container_shape = shape
            self._container_bounds = corel.get_shape_bounds(shape)
            true_width, true_height = corel.get_true_size(shape)
            if true_width <= 0 or true_height <= 0:
                raise ValueError("Selected shape returned an invalid true size.")
            try:
                self._container_contours = corel.get_curve_subpaths(shape, require_closed=True)
                self._container_segments = [segment for contour in self._container_contours for segment in contour]
                if not self._container_contours:
                    logger.warning(
                        "get_curve_subpaths returned no closed contours for '%s'. "
                        "Hatch fill will use corel.is_point_in_shape as a per-stone fallback.",
                        getattr(shape, 'Name', '?'),
                    )
            except Exception as exc:
                logger.warning(
                    "Could not extract contours from '%s': %s. "
                    "Hatch fill will use corel.is_point_in_shape as a per-stone fallback.",
                    getattr(shape, 'Name', '?'),
                    exc,
                )
                self._container_contours = []
                self._container_segments = []
                # Do NOT re-raise — bounds are already set; the engine will use
                # corel.is_point_in_shape for clipping when no contours are available.

            self.lbl_container.setText(
                f"{getattr(shape, 'Name', 'Shape')} ({true_width:.2f} x {true_height:.2f} mm)"
            )
            self.info_container.setText(self.lbl_container.text())
            logger.info(
                "Hexagon container accepted: name=%s true_size_mm=(%.4f, %.4f) bounds_mm=(%.4f, %.4f)",
                getattr(shape, "Name", "Shape"),
                true_width,
                true_height,
                self._container_bounds.width,
                self._container_bounds.height,
            )
            if emit_status:
                self.status_message.emit("Container shape set.")
            return True
        except Exception as exc:
            logger.error("Failed to set hexagon container shape: %s", exc)
            QMessageBox.critical(self, "Container Error", f"Could not use the selected shape as container:\n{exc}")
            return False

    def _set_curve_from_shape(self, shape, emit_status: bool = True) -> bool:
        """Assign the path/curve shape and update UI."""
        if shape is None:
            return False

        try:
            self._curve_shape = shape
            self._curve_segments = corel.get_curve_path(shape)
            self._curve_length = corel.get_curve_total_length(self._curve_segments)
            if not self._curve_segments or self._curve_length <= 0:
                raise ValueError("Selected shape does not provide a usable curve path.")
            self.lbl_curve.setText(f"{getattr(shape, 'Name', 'Curve')} (length {self._curve_length:.2f} mm)")
            self.info_curve.setText(self.lbl_curve.text())
            logger.info(
                "Hexagon path set to '%s' with length %.4f mm and %s segments.",
                getattr(shape, "Name", "Curve"),
                self._curve_length,
                len(self._curve_segments),
            )
            if emit_status:
                self.status_message.emit("Path set.")
            return True
        except Exception as exc:
            self._curve_shape = None
            self._curve_segments = []
            self._curve_length = 0.0
            self.lbl_curve.setText("Not set")
            logger.error("Failed to set hexagon curve shape: %s", exc)
            QMessageBox.critical(self, "Path Error", f"Could not use the selected shape as path:\n{exc}")
            return False

    def _set_element_from_shape(self, shape, emit_status: bool = True) -> bool:
        """Assign the element shape and update UI."""
        if shape is None:
            return False

        try:
            corel.log_shape_metrics(shape, "Hexagon stone element selection")
            self._element_shape = shape
            width, height = corel.get_true_size(shape)
            if width <= 0 or height <= 0:
                raise ValueError("Selected element returned an invalid true size.")
            name = getattr(shape, "Name", "Selected element")
            self.lbl_element.setText(f"{name} ({width:.2f} x {height:.2f} mm)")
            self.info_element.setText(self.lbl_element.text())
            logger.info("Hexagon element set to '%s' size_mm=(%.4f, %.4f)", name, width, height)
            if emit_status:
                self.status_message.emit("Stone element set from selection.")
            return True
        except Exception as exc:
            logger.error("Failed to set hexagon element shape: %s", exc)
            QMessageBox.critical(self, "Element Error", f"Could not use the selected shape as stone element:\n{exc}")
            return False

    def _set_container(self) -> None:
        if not self._ensure_corel_ready():
            return
        shape = self._selected_shape(0)
        if shape is None:
            QMessageBox.warning(self, "No Selection", "Select a closed shape first.")
            return
        self._set_container_from_shape(shape)

    def _set_curve(self) -> None:
        if not self._ensure_corel_ready():
            return
        shape = self._selected_shape(0)
        if shape is None:
            QMessageBox.warning(self, "No Selection", "Select a curve/path first.")
            return
        self._set_curve_from_shape(shape)

    def _set_element(self) -> None:
        if not self._ensure_corel_ready():
            return
        shape = self._selected_shape(0)
        if shape is None:
            QMessageBox.warning(self, "No Selection", "Select one stone element first.")
            return
        self._set_element_from_shape(shape)

    def _start_worker(self, func, *args, on_finish=None) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()

        self._worker = _Worker(func, *args)
        self._worker.progress.connect(self._on_progress)
        self._worker.snapshot.connect(self._on_snapshot)
        self._worker.error.connect(self._on_error)
        if on_finish:
            self._worker.finished.connect(on_finish)

        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.btn_cancel.setVisible(True)
        self._worker.start()

    def cancel_pending_work(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()

    def on_tool_deactivated(self) -> None:
        self.cancel_pending_work()
        super().on_tool_deactivated()

    def _format_duration(self, seconds) -> str:
        if seconds is None:
            return "--:--"
        total = max(0, int(round(seconds)))
        return f"{total // 60:02d}:{total % 60:02d}"

    def _build_preview_key(self, mode: str) -> str:
        settings = self._build_settings()
        return "|".join(
            [
                mode,
                str(self._last_selection_signature or ""),
                str(self._container_shape is not None),
                str(self._curve_shape is not None),
                str(self._element_shape is not None),
                settings.stone_size,
                f"{settings.custom_diameter:.4f}",
                f"{settings.fit_factor:.4f}",
                f"{settings.min_gap:.4f}",
                settings.path_distribution.value,
                f"{settings.path_start_padding:.4f}",
                f"{settings.path_end_padding:.4f}",
                str(settings.path_rotate_to_tangent),
                f"{settings.path_extra_gap:.4f}",
                settings.hatch_origin.value,
                f"{settings.hatch_row_angle:.4f}",
                f"{settings.hatch_edge_margin:.4f}",
                f"{settings.hatch_stagger_pct:.4f}",
                str(settings.hatch_clip_to_shape),
                settings.collision_action.value,
                f"{settings.collision_gap:.4f}",
            ],
        )

    def _run_path_fill(self) -> None:
        if not self._ensure_corel_ready():
            return
        if not self._curve_segments:
            shape = self._selected_shape(0)
            if shape is not None:
                self._set_curve_from_shape(shape, emit_status=False)
        if not self._curve_segments:
            QMessageBox.warning(self, "No Path", "Set a curve/path first.")
            return
        preview_key = self._build_preview_key("path")
        if self._last_preview_key == preview_key and self._last_stones:
            self.info_status.setText("Preview cache reused")
            self.status_message.emit(f"Preview cache reused: {len(self._last_stones)} stones")
            return
        self._pending_preview_key = preview_key
        self._start_worker(
            lambda progress_controller=None, progress_callback=None, cancel_callback=None: self.engine.path_blend(
                self._curve_segments,
                self._build_settings(),
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            ),
            on_finish=self._on_stones_ready,
        )

    def _run_hatch_fill(self) -> None:
        if not self._ensure_corel_ready():
            return
        # Auto-set container from selection if not already set.
        # Only bounds are strictly required; contours are optional (shape fallback used when absent).
        if self._container_bounds is None:
            shape = self._selected_shape(0)
            if shape is not None:
                self._set_container_from_shape(shape, emit_status=False)
        if self._container_bounds is None:
            QMessageBox.warning(self, "No Container", "Set a closed container shape first.")
            return
        preview_key = self._build_preview_key("hatch")
        if self._last_preview_key == preview_key and self._last_stones:
            self.info_status.setText("Preview cache reused")
            self.status_message.emit(f"Preview cache reused: {len(self._last_stones)} stones")
            return
        self._pending_preview_key = preview_key
        self._start_worker(
            lambda progress_controller=None, progress_callback=None, cancel_callback=None: self.engine.honeycomb_fill(
                self._container_bounds,
                self._build_settings(),
                clip_segments=self._container_segments,
                clip_contours=self._container_contours,
                container_shape=self._container_shape,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            ),
            on_finish=self._on_stones_ready,
        )

    def _run_place(self) -> None:
        if not self._last_stones:
            QMessageBox.warning(self, "Nothing To Draw", "Run Fill Path or Fill Shape first.")
            return
        settings = self._build_settings()
        if settings.output_mode == OutputMode.COREL_RENDER and not self._ensure_corel_ready():
            return
        self._start_worker(
            lambda progress_controller=None, progress_callback=None, cancel_callback=None: self.engine.place_in_coreldraw(
                self._last_stones,
                settings,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
                element_shape=self._element_shape,
            ),
            on_finish=self._on_placed,
        )

    def _cancel_worker(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        self.info_status.setText("Cancelling")
        self.status_message.emit("Operation cancelled.")

    def _check_overlaps(self) -> None:
        if not self._last_stones:
            self.lbl_overlap_result.setText("No stones calculated yet.")
            return
        pairs = self.engine.find_overlaps(self._last_stones, self._build_settings())
        if not pairs:
            self.lbl_overlap_result.setText("No overlaps detected.")
            return
        involved = len({index for pair in pairs for index in pair})
        self.lbl_overlap_result.setText(f"Found {len(pairs)} overlapping pairs across {involved} stones.")

    def _fix_overlaps(self) -> None:
        if not self._last_stones:
            QMessageBox.warning(self, "No Stones", "Calculate stones first.")
            return
        before = len(self._last_stones)
        self._last_stones = self.engine.resolve_collisions(self._last_stones, self._build_settings())
        after = len(self._last_stones)
        self._update_stats()
        self.lbl_overlap_result.setText(f"Collision pass complete: {before} -> {after} stones.")
        self.status_message.emit("Collision pass complete.")

    @pyqtSlot(int, int)
    def _on_progress(self, current: int, total: int) -> None:
        if not self.is_tool_active():
            return
        if total > 0:
            self.progress_bar.setValue(int((current / total) * 100))
        self.progress_updated.emit(current, total)

    @pyqtSlot(object)
    def _on_snapshot(self, snapshot: ProgressSnapshot) -> None:
        if not self.is_tool_active():
            return
        self.info_phase.setText(snapshot.phase)
        self.info_elapsed.setText(self._format_duration(snapshot.elapsed_seconds))
        self.info_eta.setText(self._format_duration(snapshot.eta_seconds))

    @pyqtSlot(object)
    def _on_stones_ready(self, stones) -> None:
        if not self.is_tool_active():
            return
        self._last_stones = stones or []
        if self._pending_preview_key:
            self._last_preview_key = self._pending_preview_key
            self._pending_preview_key = ""
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self._update_stats()
        try:
            contours = (
                self.engine._prepare_flattened_contours(self._container_contours, self._container_segments)
                if self._container_contours or self._container_segments
                else []
            )
        except Exception:
            contours = []
        self.preview_widget.set_preview(self._last_stones, contours=contours)
        self.info_status.setText("Preview ready" if self._last_stones else "No stones")
        if not self._last_stones:
            QMessageBox.warning(
                self,
                "No Stones",
                "No stones were generated. Check container/path selection, size, gap, and fit settings.",
            )
        self.status_message.emit(f"{len(self._last_stones)} stones calculated.")

    @pyqtSlot(object)
    def _on_placed(self, result) -> None:
        if not self.is_tool_active():
            return
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        if isinstance(result, dict):
            count = int(result.get("stone_count", 0))
            json_path = result.get("json_path", "")
            rendered = bool(result.get("rendered"))
            mode = result.get("mode", "")
            render_method = result.get("render_method", "")
            self.lbl_last_export.setText(json_path or "-")
            if rendered:
                self.info_status.setText("Rendered in CorelDRAW")
                if render_method == "fallback_internal":
                    created_count = int(result.get("created_count", count))
                    self.status_message.emit(f"Rendered {created_count} stones in CorelDRAW using the internal fallback renderer.")
                    QMessageBox.information(
                        self,
                        "Done",
                        f"Rendered {created_count} stones in CorelDRAW.\n\n"
                        f"The VBA macro renderer was not available, so the app used the internal fallback renderer.\n\n"
                        f"JSON: {json_path}",
                    )
                else:
                    self.status_message.emit(f"Sent {count} stones to CorelDRAW renderer.")
                    QMessageBox.information(self, "Done", f"Rendered {count} stones through the CorelDRAW macro.\n\nJSON: {json_path}")
            elif mode == OutputMode.EXPORT_ONLY.value:
                self.info_status.setText("Exported JSON")
                self.status_message.emit(f"Exported {count} stones to JSON.")
                QMessageBox.information(self, "Export Complete", f"Exported {count} stones.\n\nJSON: {json_path}")
            else:
                self.info_status.setText("Preview exported")
                self.status_message.emit(f"Preview ready for {count} stones.")
                QMessageBox.information(self, "Preview Ready", f"Preview is ready for {count} stones.\n\nJSON: {json_path}")
            return

        count = len(result) if result else 0
        self.info_status.setText("Processed")
        self.status_message.emit(f"Processed {count} stones.")
        QMessageBox.information(self, "Done", f"Processed {count} stones.")

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        if not self.is_tool_active():
            return
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        if message == "Operation cancelled.":
            self.info_status.setText("Cancelled")
            self.info_phase.setText("Cancelled")
            return
        QMessageBox.critical(self, "Error", message)
        self.info_status.setText("Error")

    def _update_stats(self) -> None:
        stats = self.engine.get_statistics(self._last_stones)
        self.lbl_count.setText(str(stats["count"]))
        self.lbl_coverage.setText(f"{stats['coverage_mm2']:.2f} mm^2")
        self.lbl_overlaps.setText(str(stats["overlap_count"]))
        self.info_count.setText(self.lbl_count.text())
        self.info_coverage.setText(self.lbl_coverage.text())
        self.info_overlaps.setText(self.lbl_overlaps.text())

    def _clear(self) -> None:
        self.engine.clear()
        self._last_stones = []
        self._container_shape = None
        self._curve_shape = None
        self._element_shape = None
        self._selection_shapes = []
        self._last_selection_signature = None
        self._container_bounds = None
        self._container_contours = []
        self._container_segments = []
        self._curve_segments = []
        self._curve_length = 0.0
        self._last_preview_key = ""
        self._pending_preview_key = ""
        self.lbl_container.setText("Not set")
        self.lbl_curve.setText("Not set")
        self.lbl_element.setText("Default circle")
        self.info_container.setText("Not set")
        self.info_curve.setText("Not set")
        self.info_element.setText("Default circle")
        self.info_status.setText("Cleared")
        self.info_phase.setText("Idle")
        self.info_elapsed.setText("00:00")
        self.info_eta.setText("--:--")
        self._update_stats()
        self.lbl_overlap_result.setText("")
        self.lbl_last_export.setText("-")
        self.preview_widget.clear_preview()
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self.status_message.emit("Cleared.")

    def on_selection_changed(self, count: int) -> None:
        self.refresh_selection_state(force=False, expected_count=count)

    def apply_preset(self, settings: dict) -> None:
        self._set_combo_value(self.cmb_size, settings.get("stone_size"))
        if "custom_diameter" in settings:
            self.spn_custom.setValue(float(settings["custom_diameter"]))
        if "fit_factor" in settings:
            self.spn_fit.setValue(float(settings["fit_factor"]))
        if "min_gap" in settings:
            self.spn_gap.setValue(float(settings["min_gap"]))
        self._set_combo_value(self.cmb_path_distribution, settings.get("path_distribution"))
        if "path_start_padding" in settings:
            self.spn_start_padding.setValue(float(settings["path_start_padding"]))
        if "path_end_padding" in settings:
            self.spn_end_padding.setValue(float(settings["path_end_padding"]))
        if "path_rotate_to_tangent" in settings:
            self.chk_tangent.setChecked(bool(settings["path_rotate_to_tangent"]))
        if "path_extra_gap" in settings:
            self.spn_path_extra_gap.setValue(float(settings["path_extra_gap"]))
        self._set_combo_value(self.cmb_origin, settings.get("hatch_origin"))
        if "hatch_row_angle" in settings:
            self.spn_grid_angle.setValue(float(settings["hatch_row_angle"]))
        if "hatch_edge_margin" in settings:
            self.spn_edge_margin.setValue(float(settings["hatch_edge_margin"]))
        if "hatch_stagger_pct" in settings:
            self.spn_stagger.setValue(float(settings["hatch_stagger_pct"]))
        if "hatch_clip_to_shape" in settings:
            self.chk_clip_shape.setChecked(bool(settings["hatch_clip_to_shape"]))
        self._set_combo_value(self.cmb_collision, settings.get("collision_action"))
        if "collision_gap" in settings:
            self.spn_collision_gap.setValue(float(settings["collision_gap"]))
        if "shrink_min_factor" in settings:
            self.spn_shrink_min.setValue(float(settings["shrink_min_factor"]))
        if "group_output" in settings:
            self.chk_group_output.setChecked(bool(settings["group_output"]))
        if "layer_name" in settings:
            self.edt_layer.setText(str(settings["layer_name"]))
        self._set_combo_value(self.cmb_output_mode, settings.get("output_mode"))
        self._refresh_preview()
        if self._size_table_initialized:
            self._refresh_table()
        self.info_status.setText("Preset applied")
        self.status_message.emit("Hexagon preset applied.")

    def reset_to_defaults(self) -> None:
        index = self.cmb_size.findData("SS10")
        if index >= 0:
            self.cmb_size.setCurrentIndex(index)
        self.spn_custom.setValue(2.80)
        self.spn_fit.setValue(DEFAULT_FIT_FACTOR)
        self.spn_gap.setValue(0.20)
        self.spn_path_extra_gap.setValue(0.0)
        self.spn_start_padding.setValue(0.0)
        self.spn_end_padding.setValue(0.0)
        self.chk_tangent.setChecked(True)
        self.spn_stagger.setValue(50.0)
        self.spn_grid_angle.setValue(0.0)
        self.spn_edge_margin.setValue(0.0)
        self.cmb_origin.setCurrentIndex(0)
        self.chk_clip_shape.setChecked(True)
        self.cmb_collision.setCurrentIndex(0)
        self.spn_collision_gap.setValue(0.0)
        self.spn_shrink_min.setValue(0.60)
        self.chk_group_output.setChecked(True)
        self.cmb_output_mode.setCurrentIndex(2)
        self.edt_layer.setText("Rhinestones")
        self.lbl_last_export.setText("-")
        self._element_shape = None
        self.lbl_element.setText("Default circle")
        self.info_element.setText("Default circle")
        self.info_output.setText(self.cmb_output_mode.currentText())
        self.info_status.setText("Idle")
        self.preview_widget.clear_preview()
        self._refresh_preview()
        if self._size_table_initialized:
            self._refresh_table()
