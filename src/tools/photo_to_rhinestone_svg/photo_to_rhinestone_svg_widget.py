import logging
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image, ImageDraw
from PyQt5.QtCore import QObject, QEvent, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractSlider,
    QAbstractSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.corel_interface import BoundingBox, CurveSegment, Point, corel
from ...ui.widgets.collapsible_section import CollapsibleSection
from ...ui.widgets.tool_base import ToolBaseWidget
from ...ui.widgets.tool_components import ActionBar, InfoPanel, SettingsGroup, ToolHeader
from ..common import (
    FinalRenderer,
    OperationWorker,
    PointillizerPreviewCanvas,
    ProgressSnapshot,
    StructuralDetailConfig,
    StructuralDetailExtractor,
    StructuralDetailResult,
)
from ..pattern_fill.pattern_fill_engine import PatternFillConfig, PatternFillEngine
from .photo_pointillizer import PhotoPointillizerEngine, PointillizerConfig, PointillizerResult

logger = logging.getLogger(__name__)


class _PreviewInteractionFilter(QObject):
    def __init__(self, owner):
        super().__init__(owner)
        self._owner = owner

    def eventFilter(self, watched, event):  # noqa: N802
        event_type = event.type()
        if event_type == QEvent.MouseButtonPress:
            self._owner._on_preview_interaction_started(watched)
        elif event_type == QEvent.MouseButtonRelease:
            self._owner._on_preview_interaction_finished(watched)
        return False


class PhotoPointillizerWidget(ToolBaseWidget):
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Photo Pointillizer", parent)
        self.engine = PhotoPointillizerEngine()
        self.structural_engine = StructuralDetailExtractor()
        self.pattern_engine = PatternFillEngine()
        self.final_renderer = FinalRenderer()
        self._preview_result: Optional[PointillizerResult] = None
        self._final_result: Optional[PointillizerResult] = None
        self._structural_preview_result: Optional[StructuralDetailResult] = None
        self._structural_pattern_result = None
        self._container_shape = None
        self._container_contours: List[List[Point]] = []
        self._container_name = "None"
        self._container_signature = ""
        self._worker: Optional[OperationWorker] = None
        self._pending_preview_request: Optional[Dict[str, Any]] = None
        self._current_job_kind: Optional[str] = None
        self._current_preview_request_id = 0
        self._next_preview_request_id = 0
        self._latest_preview_request_id = 0
        self._latest_applied_preview_id = 0
        self._active_preview_profile = "settled"
        self._last_invalidation_summary = ""
        self._last_log_append = 0.0
        self._perf_metrics: Dict[str, Dict[str, Any]] = {
            "pointillizer": self._new_perf_metrics(),
            "structural": self._new_perf_metrics(),
        }
        self._interaction_filter = _PreviewInteractionFilter(self)
        self._drag_preview_timer = QTimer(self)
        self._drag_preview_timer.setSingleShot(True)
        self._drag_preview_timer.timeout.connect(lambda: self._dispatch_preview("drag"))
        self._settled_preview_timer = QTimer(self)
        self._settled_preview_timer.setSingleShot(True)
        self._settled_preview_timer.timeout.connect(lambda: self._dispatch_preview("settled"))
        self._build_ui()
        self._configure_interaction_help()
        self._wire_live_preview()
        self.add_stretch()
        self._set_running(False)
        self._update_info("Idle", "-")

    def _new_perf_metrics(self) -> Dict[str, Any]:
        return {
            "drag_ms": 0.0,
            "settled_ms": 0.0,
            "final_ms": 0.0,
            "paint_ms": 0.0,
            "stone_counts": {"drag": 0, "settled": 0, "final": 0},
            "structural_paths": 0,
            "slowest_stage": "-",
            "cache": "hits:0 misses:0",
        }

    def _mode_key(self) -> str:
        return "structural" if self.cmb_processing_mode.currentData() == "structural" else "pointillizer"

    def _build_ui(self):
        self.add_widget(
            ToolHeader(
                "Photo Pointillizer",
                "Switch between photo pointillizer output and structural detail extraction. Both preview paths stay non-destructive and run separately from final document apply.",
            )
        )
        self.add_widget(self._mode_section())
        self.files_section = self._files_section()
        self.layout_section = self._layout_section()
        self.background_section = self._background_section()
        self.decimation_section = self._decimation_section()
        self.size_section = self._size_section()
        self.sampling_section = self._sampling_section()
        self.output_section = self._output_section()
        self.structural_section = self._structural_section()
        self.add_widget(self.files_section)
        self.add_widget(self.layout_section)
        self.add_widget(self.background_section)
        self.add_widget(self.decimation_section)
        self.add_widget(self.size_section)
        self.add_widget(self.sampling_section)
        self.add_widget(self.output_section)
        self.add_widget(self.structural_section)
        self.add_widget(self._operation_section())
        self.add_widget(self._preview_section())
        self.add_widget(self._actions_section())
        self.set_context_panel(self._info_panel())
        self._update_mode_visibility()

    def _mode_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Processing Mode")
        self.cmb_processing_mode = QComboBox()
        self.cmb_processing_mode.addItem("Photo Pointillizer", "pointillizer")
        self.cmb_processing_mode.addItem("Structural Detail Extraction", "structural")
        group.add_row("Mode", self.cmb_processing_mode)
        layout.addWidget(group)
        return CollapsibleSection("Mode", content, True)

    def _browse_row(self, text_box: QLineEdit, title: str, filter_text: str):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(text_box)
        btn = QPushButton("Browse...")
        btn.clicked.connect(lambda: self._browse_file(text_box, title, filter_text))
        layout.addWidget(btn)
        return row

    def _update_mode_visibility(self) -> None:
        structural_mode = self.cmb_processing_mode.currentData() == "structural"
        pattern_mode = structural_mode and self.cmb_structural_output_mode.currentData() == "pattern_integration"
        self.layout_section.setVisible(not structural_mode)
        self.background_section.setVisible(not structural_mode)
        self.decimation_section.setVisible(not structural_mode)
        self.size_section.setVisible(not structural_mode)
        self.sampling_section.setVisible(not structural_mode)
        self.output_section.setVisible(not structural_mode or pattern_mode)
        self.structural_section.setVisible(structural_mode)

    def _files_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Inputs")
        self.edt_photo = QLineEdit()
        self.edt_overlay = QLineEdit()
        self.edt_mask = QLineEdit()
        self.edt_output = QLineEdit()
        self.spn_width = QDoubleSpinBox()
        self.spn_width.setRange(10, 2000)
        self.spn_width.setValue(120)
        self.spn_width.setSuffix(" mm")
        self.spn_height = QDoubleSpinBox()
        self.spn_height.setRange(10, 2000)
        self.spn_height.setValue(120)
        self.spn_height.setSuffix(" mm")
        group.add_row("Photo", self._browse_row(self.edt_photo, "Select Photo", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"))
        group.add_row("Transparent PNG", self._browse_row(self.edt_overlay, "Select Transparent PNG", "PNG Files (*.png);;Images (*.png *.jpg *.jpeg *.bmp)"))
        group.add_row("Mask", self._browse_row(self.edt_mask, "Select Mask", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"))
        group.add_row("Output base", self._browse_row(self.edt_output, "Choose Output Base", "All Files (*)"))
        group.add_row("Width", self.spn_width)
        group.add_row("Height", self.spn_height)
        vector_btn = QPushButton("Use Selected Vector Shape")
        vector_btn.clicked.connect(self._capture_vector_shape)
        group.add_full_row(vector_btn)
        layout.addWidget(group)
        return CollapsibleSection("Input", content, True)

    def _layout_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Stone Layout")
        self.cmb_layout = QComboBox()
        self.cmb_layout.addItem("Hex Packing", "hex")
        self.cmb_layout.addItem("Square Grid", "grid")
        self.cmb_layout.addItem("Staggered Rows", "staggered")
        self.cmb_layout.addItem("Random Jitter", "random")
        self.cmb_layout.addItem("Spiral", "spiral")
        self.cmb_layout.addItem("Contour Follow (Preview)", "contour")
        self.spn_stone = QDoubleSpinBox()
        self.spn_stone.setRange(1.0, 12.0)
        self.spn_stone.setValue(2.8)
        self.spn_stone.setSuffix(" mm")
        self.spn_gap = QDoubleSpinBox()
        self.spn_gap.setRange(0, 5.0)
        self.spn_gap.setValue(0.2)
        self.spn_gap.setSuffix(" mm")
        self.spn_margin = QDoubleSpinBox()
        self.spn_margin.setRange(0, 5.0)
        self.spn_margin.setValue(0.2)
        self.spn_margin.setSuffix(" mm")
        self.spn_jitter = QDoubleSpinBox()
        self.spn_jitter.setRange(0, 2.0)
        self.spn_jitter.setValue(0.0)
        self.spn_jitter.setSuffix(" mm")
        group.add_row("Layout", self.cmb_layout)
        group.add_row("Stone size", self.spn_stone)
        group.add_row("Gap", self.spn_gap)
        group.add_row("Edge margin", self.spn_margin)
        group.add_row("Jitter", self.spn_jitter)
        layout.addWidget(group)
        return CollapsibleSection("Stone Layout", content, True)

    def _background_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Background Removal")
        self.chk_remove_background = QCheckBox("Remove background")
        self.chk_remove_background.setChecked(True)
        self.chk_use_alpha = QCheckBox("Use source alpha")
        self.chk_use_alpha.setChecked(True)
        self.chk_auto_background = QCheckBox("Auto-detect background color")
        self.chk_auto_background.setChecked(True)
        self.spn_bg_tolerance = QDoubleSpinBox()
        self.spn_bg_tolerance.setRange(0, 255)
        self.spn_bg_tolerance.setDecimals(0)
        self.spn_bg_tolerance.setValue(28)
        self.spn_feather = QDoubleSpinBox()
        self.spn_feather.setRange(0, 12)
        self.spn_feather.setDecimals(0)
        self.spn_feather.setValue(0)
        self.chk_keep_holes = QCheckBox("Keep internal transparency")
        self.chk_keep_holes.setChecked(True)
        group.add_full_row(self.chk_remove_background)
        group.add_full_row(self.chk_use_alpha)
        group.add_full_row(self.chk_auto_background)
        group.add_row("Tolerance", self.spn_bg_tolerance)
        group.add_row("Feather", self.spn_feather)
        group.add_full_row(self.chk_keep_holes)
        layout.addWidget(group)
        return CollapsibleSection("Background Removal", content, False)

    def _decimation_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Density && Decimation")
        self.spn_target_density = QDoubleSpinBox()
        self.spn_target_density.setRange(0.05, 1.0)
        self.spn_target_density.setSingleStep(0.05)
        self.spn_target_density.setValue(0.95)
        self.spn_edge_strength = QDoubleSpinBox()
        self.spn_edge_strength.setRange(0.0, 1.0)
        self.spn_edge_strength.setSingleStep(0.05)
        self.spn_edge_strength.setValue(0.75)
        self.spn_detail_threshold = QDoubleSpinBox()
        self.spn_detail_threshold.setRange(0.01, 1.0)
        self.spn_detail_threshold.setSingleStep(0.05)
        self.spn_detail_threshold.setValue(0.18)
        self.spn_max_stones = QDoubleSpinBox()
        self.spn_max_stones.setRange(0, 500000)
        self.spn_max_stones.setDecimals(0)
        self.spn_max_stones.setValue(0)
        group.add_row("Target density", self.spn_target_density)
        group.add_row("Preserve edges", self.spn_edge_strength)
        group.add_row("Detail threshold", self.spn_detail_threshold)
        group.add_row("Max stone count", self.spn_max_stones)
        layout.addWidget(group)
        return CollapsibleSection("Density && Decimation", content, True)

    def _size_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Stone Sizes")
        self.cmb_size_mode = QComboBox()
        self.cmb_size_mode.addItem("Single size", "single")
        self.cmb_size_mode.addItem("Small + medium", "small_medium")
        self.cmb_size_mode.addItem("Small + medium + large", "small_medium_large")
        self.cmb_size_mode.addItem("Adaptive by detail", "adaptive")
        self.spn_small = QDoubleSpinBox(); self.spn_small.setRange(1.0, 12.0); self.spn_small.setValue(2.0); self.spn_small.setSuffix(" mm")
        self.spn_medium = QDoubleSpinBox(); self.spn_medium.setRange(1.0, 12.0); self.spn_medium.setValue(2.8); self.spn_medium.setSuffix(" mm")
        self.spn_large = QDoubleSpinBox(); self.spn_large.setRange(1.0, 12.0); self.spn_large.setValue(4.0); self.spn_large.setSuffix(" mm")
        self.spn_size_sensitivity = QDoubleSpinBox(); self.spn_size_sensitivity.setRange(0.1, 1.0); self.spn_size_sensitivity.setValue(0.85)
        self.spn_min_spacing = QDoubleSpinBox(); self.spn_min_spacing.setRange(0.0, 5.0); self.spn_min_spacing.setValue(0.2); self.spn_min_spacing.setSuffix(" mm")
        group.add_row("Mode", self.cmb_size_mode)
        group.add_row("Small", self.spn_small)
        group.add_row("Medium", self.spn_medium)
        group.add_row("Large", self.spn_large)
        group.add_row("Edge sensitivity", self.spn_size_sensitivity)
        group.add_row("Min spacing", self.spn_min_spacing)
        layout.addWidget(group)
        return CollapsibleSection("Stone Sizes", content, True)

    def _sampling_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Sampling && Color Reduction")
        self.cmb_sampling = QComboBox()
        self.cmb_sampling.addItem("Average Color in Circle", "average")
        self.cmb_sampling.addItem("Nearest Pixel", "nearest")
        self.chk_brightness = QCheckBox("Brightness only")
        self.chk_invert = QCheckBox("Invert brightness")
        self.cmb_palette_mode = QComboBox()
        self.cmb_palette_mode.addItem("Nearest Palette Color", "nearest")
        self.cmb_palette_mode.addItem("Grayscale Stone Palette", "grayscale")
        self.cmb_palette_mode.addItem("Rhinestone Palette", "rhinestone")
        self.cmb_palette_mode.addItem("Dominant + Accent Colors", "dominant_accents")
        self.cmb_palette = QComboBox()
        self.cmb_palette.addItem("Bright", "bright")
        self.cmb_palette.addItem("Grayscale", "grayscale")
        self.cmb_palette.addItem("Rhinestone", "rhinestone")
        self.spn_gamma = QDoubleSpinBox()
        self.spn_gamma.setRange(0.2, 4.0)
        self.spn_gamma.setValue(1.0)
        self.spn_contrast = QDoubleSpinBox()
        self.spn_contrast.setRange(0.2, 4.0)
        self.spn_contrast.setValue(1.0)
        self.spn_brightness = QDoubleSpinBox()
        self.spn_brightness.setRange(0.2, 4.0)
        self.spn_brightness.setValue(1.0)
        group.add_row("Sampling", self.cmb_sampling)
        group.add_full_row(self.chk_brightness)
        group.add_full_row(self.chk_invert)
        group.add_row("Palette mode", self.cmb_palette_mode)
        group.add_row("Palette", self.cmb_palette)
        group.add_row("Gamma", self.spn_gamma)
        group.add_row("Contrast", self.spn_contrast)
        group.add_row("Brightness", self.spn_brightness)
        layout.addWidget(group)
        return CollapsibleSection("Image Sampling", content, True)

    def _output_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Output")
        self.cmb_output_mode = QComboBox()
        self.cmb_output_mode.addItem("Preview only", "preview_only")
        self.cmb_output_mode.addItem("Separate stones", "separate")
        self.cmb_output_mode.addItem("Grouped by color", "grouped_color")
        self.cmb_output_mode.addItem("Merged/Welded by color", "welded_color")
        self.cmb_output_mode.addItem("Multi-size grouped output", "multi_size_grouped")
        self.cmb_output_mode.setCurrentIndex(2)
        self.chk_group_output = QCheckBox("Group imported output")
        self.chk_group_output.setChecked(True)
        self.chk_weld_by_color = QCheckBox("Weld color groups when possible")
        self.chk_export_background = QCheckBox("Export background rectangle")
        self.chk_debug_export = QCheckBox("Keep debug SVG for Apply")
        self.chk_allow_svg_fallback = QCheckBox("Allow SVG import fallback for Apply")
        self.chk_performance_mode = QCheckBox("Performance mode for interactive preview")
        self.chk_performance_mode.setChecked(True)
        group.add_row("Apply mode", self.cmb_output_mode)
        group.add_full_row(self.chk_performance_mode)
        group.add_full_row(self.chk_group_output)
        group.add_full_row(self.chk_weld_by_color)
        group.add_full_row(self.chk_export_background)
        group.add_full_row(self.chk_debug_export)
        group.add_full_row(self.chk_allow_svg_fallback)
        layout.addWidget(group)
        return CollapsibleSection("Output", content, True)

    def _structural_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        group = SettingsGroup("Ornamental Structure Extraction")
        self.cmb_structural_mode = QComboBox()
        self.cmb_structural_mode.addItem("Major structure only", "major")
        self.cmb_structural_mode.addItem("Balanced ornamental extraction", "balanced")
        self.cmb_structural_mode.addItem("Full ornamental extraction", "full")
        self.spn_structure_strength = QDoubleSpinBox()
        self.spn_structure_strength.setRange(0.0, 1.0)
        self.spn_structure_strength.setSingleStep(0.05)
        self.spn_structure_strength.setValue(0.72)
        self.spn_structural_feature = QDoubleSpinBox()
        self.spn_structural_feature.setRange(8, 20000)
        self.spn_structural_feature.setDecimals(0)
        self.spn_structural_feature.setValue(80)
        self.spn_symmetry_influence = QDoubleSpinBox()
        self.spn_symmetry_influence.setRange(0.0, 1.0)
        self.spn_symmetry_influence.setSingleStep(0.05)
        self.spn_symmetry_influence.setValue(0.65)
        self.spn_border_priority = QDoubleSpinBox()
        self.spn_border_priority.setRange(0.0, 1.0)
        self.spn_border_priority.setSingleStep(0.05)
        self.spn_border_priority.setValue(0.8)
        self.spn_center_priority = QDoubleSpinBox()
        self.spn_center_priority.setRange(0.0, 1.0)
        self.spn_center_priority.setSingleStep(0.05)
        self.spn_center_priority.setValue(0.7)
        self.spn_curve_smoothness = QDoubleSpinBox()
        self.spn_curve_smoothness.setRange(0.0, 2.0)
        self.spn_curve_smoothness.setSingleStep(0.05)
        self.spn_curve_smoothness.setValue(0.45)
        self.spn_simplify = QDoubleSpinBox()
        self.spn_simplify.setRange(0.05, 8.0)
        self.spn_simplify.setSingleStep(0.05)
        self.spn_simplify.setValue(0.5)
        self.chk_symmetry = QCheckBox("Mirror vertical symmetry")
        self.spn_detail_retention = QDoubleSpinBox()
        self.spn_detail_retention.setRange(0.0, 1.0)
        self.spn_detail_retention.setSingleStep(0.05)
        self.spn_detail_retention.setValue(0.35)
        self.spn_silhouette_priority = QDoubleSpinBox()
        self.spn_silhouette_priority.setRange(0.0, 1.0)
        self.spn_silhouette_priority.setSingleStep(0.05)
        self.spn_silhouette_priority.setValue(0.95)
        self.spn_merge_distance = QDoubleSpinBox()
        self.spn_merge_distance.setRange(0.1, 20.0)
        self.spn_merge_distance.setValue(1.8)
        self.spn_merge_distance.setSuffix(" mm")
        self.spn_min_curve_length = QDoubleSpinBox()
        self.spn_min_curve_length.setRange(0.5, 100.0)
        self.spn_min_curve_length.setValue(8.0)
        self.spn_min_curve_length.setSuffix(" mm")
        self.cmb_structural_output_mode = QComboBox()
        self.cmb_structural_output_mode.addItem("Preview curves only", "preview_curves")
        self.cmb_structural_output_mode.addItem("Vector SVG output", "vector_svg")
        self.cmb_structural_output_mode.addItem("Pattern integration stones", "pattern_integration")
        self.spn_structural_stone = QDoubleSpinBox()
        self.spn_structural_stone.setRange(1.0, 12.0)
        self.spn_structural_stone.setValue(2.8)
        self.spn_structural_stone.setSuffix(" mm")
        self.spn_structural_spacing = QDoubleSpinBox()
        self.spn_structural_spacing.setRange(0.0, 10.0)
        self.spn_structural_spacing.setValue(0.3)
        self.spn_structural_spacing.setSuffix(" mm")
        self.cmb_structural_apply_mode = QComboBox()
        self.cmb_structural_apply_mode.addItem("Grouped by color", "grouped_color")
        self.cmb_structural_apply_mode.addItem("Grouped by pattern layer", "grouped_pattern_layer")
        self.cmb_structural_apply_mode.addItem("Merged/Welded by color", "welded_color")
        group.add_row("Extraction mode", self.cmb_structural_mode)
        group.add_row("Structure strength", self.spn_structure_strength)
        group.add_row("Min motif size", self.spn_structural_feature)
        group.add_row("Symmetry influence", self.spn_symmetry_influence)
        group.add_row("Border band priority", self.spn_border_priority)
        group.add_row("Center motif priority", self.spn_center_priority)
        group.add_row("Curve smoothness", self.spn_curve_smoothness)
        group.add_row("Simplify tolerance", self.spn_simplify)
        group.add_full_row(self.chk_symmetry)
        group.add_row("Decorative detail retention", self.spn_detail_retention)
        group.add_row("Silhouette priority", self.spn_silhouette_priority)
        group.add_row("Merge distance", self.spn_merge_distance)
        group.add_row("Minimum curve length", self.spn_min_curve_length)
        group.add_row("Structural output", self.cmb_structural_output_mode)
        group.add_row("Pattern stone size", self.spn_structural_stone)
        group.add_row("Pattern spacing", self.spn_structural_spacing)
        group.add_row("Pattern apply mode", self.cmb_structural_apply_mode)
        layout.addWidget(group)
        return CollapsibleSection("Structural Extraction", content, False)

    def _operation_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.phase_label = QLabel("Idle")
        self.elapsed_label = QLabel("Elapsed: 00:00")
        self.eta_label = QLabel("ETA: --:--")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        stats_row = QWidget()
        stats_layout = QHBoxLayout(stats_row)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(12)
        stats_layout.addWidget(self.phase_label, 1)
        stats_layout.addWidget(self.elapsed_label)
        stats_layout.addWidget(self.eta_label)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self._cancel_operation)

        layout.addWidget(stats_row)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.stop_btn, 0, Qt.AlignRight)
        return CollapsibleSection("Operation Status", content, True)

    def _preview_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.preview_canvas = PointillizerPreviewCanvas()
        self.output_log = QPlainTextEdit()
        self.output_log.setReadOnly(True)
        self.output_log.setMinimumHeight(140)
        layout.addWidget(self.preview_canvas)
        layout.addWidget(self.output_log)
        return CollapsibleSection("Preview && Output", content, True)

    def _actions_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        self.actions = ActionBar("Preview", "Apply", "Clear", "Export")
        self.actions.preview_clicked.connect(self._start_preview)
        self.actions.apply_clicked.connect(self._start_apply)
        self.actions.export_clicked.connect(self._start_export)
        self.actions.clear_clicked.connect(self.reset_to_defaults)
        layout.addWidget(self.actions)
        return CollapsibleSection("Actions", content, True)

    def _info_panel(self):
        self.lbl_source = QLabel("No photo")
        self.lbl_container = QLabel("None")
        self.lbl_status = QLabel("Idle")
        self.lbl_phase = QLabel("Idle")
        self.lbl_stones = QLabel("0")
        self.lbl_colors = QLabel("-")
        self.lbl_elapsed = QLabel("00:00")
        self.lbl_eta = QLabel("--:--")
        self.lbl_perf_preview = QLabel("drag 0 ms | settled 0 ms")
        self.lbl_perf_paint = QLabel("paint 0 ms")
        self.lbl_perf_cache = QLabel("hits:0 misses:0")
        self.lbl_perf_slowest = QLabel("-")
        return InfoPanel(
            "Photo Pointillizer Info",
            sections=[
                ("Selection", [("Photo", self.lbl_source), ("Vector shape", self.lbl_container)]),
                ("Preview", [("Stone count", self.lbl_stones), ("Per-color", self.lbl_colors)]),
                ("Operation", [("Status", self.lbl_status), ("Phase", self.lbl_phase), ("Elapsed", self.lbl_elapsed), ("ETA", self.lbl_eta)]),
                ("Performance", [("Preview", self.lbl_perf_preview), ("Paint", self.lbl_perf_paint), ("Cache", self.lbl_perf_cache), ("Slowest", self.lbl_perf_slowest)]),
            ],
        )

    def _configure_interaction_help(self):
        self.enable_safe_panel_interactions()
        self.apply_default_button_tooltips()
        self.apply_tooltips([
            (self.cmb_processing_mode, "Choose between stone-based photo pointillizer output and structural detail extraction. Structural mode keeps only the major design curves and shapes."),
            (self.edt_photo, "Path to the source photo used to generate the rhinestone layout. The image content drives the preview and export result."),
            (self.edt_overlay, "Optional transparent overlay image to blend with the source before sampling. Use this to add highlights or masks baked into the preview."),
            (self.edt_mask, "Optional mask image that limits where stones can be generated. Darker masked areas reduce or block output."),
            (self.edt_output, "Base path used for exported files. The tool writes preview and final outputs relative to this location."),
            (self.spn_width, "Final artwork width in millimeters. Changing this scales the layout, stone count, and export dimensions."),
            (self.spn_height, "Final artwork height in millimeters. Larger values create more output area and usually increase stone count."),
            (self.cmb_layout, "Choose the base stone arrangement strategy. Layout choice changes coverage style, regularity, and output character."),
            (self.spn_stone, "Stone diameter used for the generated layout. Smaller stones preserve more detail but increase processing and output size."),
            (self.spn_gap, "Extra space between stones. Increasing gap reduces density and can improve readability or manufacturing tolerance."),
            (self.spn_margin, "Keeps stones away from the outer edge of the shape or canvas. Higher margins protect borders but reduce coverage."),
            (self.spn_jitter, "Adds controlled randomness to placement. Higher jitter makes the layout less rigid but can reduce clean alignment."),
            (self.chk_remove_background, "Remove near-solid background areas before generating stones. This reduces wasted stones and speeds large jobs."),
            (self.chk_use_alpha, "Use transparent pixels from the source image as a mask. This is the safest background-removal mode when the image already has alpha."),
            (self.chk_auto_background, "Sample the source corners to auto-detect the background color. Useful for photos with a mostly solid backdrop."),
            (self.spn_bg_tolerance, "How close a color can be to the detected background before it is removed. Higher values remove more background but can eat into the subject."),
            (self.spn_feather, "Softens the background mask edge to reduce jagged transitions. Higher values are smoother but can blur fine detail."),
            (self.chk_keep_holes, "Preserve holes and inner transparent areas in the subject mask."),
            (self.spn_target_density, "Overall density target after decimation. Lower values reduce stone count and speed up output while keeping the broad visual structure."),
            (self.spn_edge_strength, "How strongly decimation protects edges and high-detail regions. Higher values preserve detail but keep more stones."),
            (self.spn_detail_threshold, "Threshold that separates flat regions from important detail during decimation."),
            (self.spn_max_stones, "Hard cap on generated stones. Use this to keep large jobs fast and manufacturable."),
            (self.cmb_size_mode, "Choose whether the output uses one size or multiple sizes based on detail."),
            (self.spn_small, "Small stone diameter used in multi-size modes for edges and fine detail."),
            (self.spn_medium, "Medium stone diameter used for general mid-detail regions."),
            (self.spn_large, "Large stone diameter used in smooth low-detail regions to reduce object count."),
            (self.spn_size_sensitivity, "How aggressively the tool switches to smaller stones near edges and detailed regions."),
            (self.spn_min_spacing, "Minimum spacing target between mixed stone sizes to keep output manufacturable."),
            (self.cmb_sampling, "Controls how image color is sampled for each stone. Faster modes are simpler, while averaged modes usually look smoother."),
            (self.chk_brightness, "Use brightness instead of full color for sampling. This simplifies output and can be better for single-color stone plans."),
            (self.chk_invert, "Invert brightness before generating stones. Useful when dark and light areas need to swap roles."),
            (self.cmb_palette_mode, "Select how sampled colors map to the output palette. This affects realism, simplification, and color consistency."),
            (self.cmb_palette, "Choose the palette set used for color reduction. Different palettes change the final look and available stone colors."),
            (self.spn_gamma, "Adjust gamma before color reduction. Higher or lower values shift midtone balance and can reveal different detail."),
            (self.spn_contrast, "Increase or decrease contrast before layout generation. More contrast strengthens separation but can lose subtle gradients."),
            (self.spn_brightness, "Raise or lower overall image brightness before sampling. This changes how many stones appear in darker or lighter regions."),
            (self.cmb_output_mode, "Choose how Apply organizes the final output in CorelDRAW. Grouped modes are much faster than separate-stone output."),
            (self.chk_performance_mode, "Prioritize smooth interaction by using cheaper drag preview, lighter settled preview, and lower preview logging while keeping final Apply full quality."),
            (self.chk_group_output, "Group imported output so it is easier to move and manage after Apply."),
            (self.chk_weld_by_color, "Try to merge shapes by color after grouped import. This can make production cleanup easier but may take extra time."),
            (self.chk_export_background, "Include a solid background rectangle in exported SVG output. Leave this off for transparent final artwork."),
            (self.chk_debug_export, "Keep the grouped SVG in a stable debug_exports folder during Apply so failed Corel imports can be inspected later."),
            (self.chk_allow_svg_fallback, "Only for debugging. If native Corel apply fails, allow Apply to try importing the kept SVG as a fallback."),
            (self.cmb_structural_mode, "Choose how aggressively the ornamental hierarchy is simplified. Major keeps only the dominant skeleton, while Full preserves more supporting motifs."),
            (self.spn_structure_strength, "How strongly the extractor favors long, connected, design-defining ornamental structures over small local fragments."),
            (self.spn_structural_feature, "Minimum motif scale kept during ornamental grouping. Larger values drop tiny embroidery clutter and filler decoration."),
            (self.spn_symmetry_influence, "How strongly mirrored motif participation boosts a feature's structural importance."),
            (self.spn_border_priority, "Boost border ribbons, hem bands, neckline bands, and other ornamental structures that behave like major decorative bands."),
            (self.spn_center_priority, "Boost central spine motifs and vertically organized ornamental panels near the dress centerline."),
            (self.spn_curve_smoothness, "Smooth the reconstructed ornamental curves after structural selection so the result feels vector-like instead of pixel-jagged."),
            (self.spn_simplify, "How aggressively the final vector curves are simplified after major motifs are selected and reconstructed."),
            (self.chk_symmetry, "Enable symmetry-aware reinforcement and optional cleanup of mirrored ornamental structures."),
            (self.spn_detail_retention, "Retain more secondary decorative motifs when increased. Lower values remove micro ornament clutter more aggressively."),
            (self.spn_silhouette_priority, "Protect the outer silhouette and major dress boundary structure during reconstruction."),
            (self.spn_merge_distance, "Merge nearby related ornamental fragments into larger motif units before vector reconstruction."),
            (self.spn_min_curve_length, "Minimum final reconstructed curve length to keep. Larger values remove isolated ornamental fragments."),
            (self.cmb_structural_output_mode, "Choose whether ornamental structure mode only previews clean curves, exports vector paths, or feeds the cleaned structure into pattern-based stone placement."),
            (self.spn_structural_stone, "Stone diameter used only when structural curves are sent into pattern integration output."),
            (self.spn_structural_spacing, "Spacing used between stones when structural curves are converted into a pattern-following rhinestone path."),
            (self.cmb_structural_apply_mode, "How structural pattern integration organizes the final Corel output. Pattern-layer grouping keeps structural bands separated."),
            (self.progress_bar, "Shows progress for the current preview, export, or apply operation."),
            (self.stop_btn, "Cancel the current operation without changing settings that are already loaded."),
            (self.preview_canvas, "Interactive preview canvas for drag and settled preview modes. Drag to pan, Ctrl+wheel to zoom, and double-click to reset the view without regenerating data."),
            (self.output_log, "Detailed output log for preview, export, and apply steps."),
        ])

    def _wire_live_preview(self):
        preview_controls = [
            self.cmb_processing_mode,
            self.spn_width,
            self.spn_height,
            self.cmb_layout,
            self.spn_stone,
            self.spn_gap,
            self.spn_margin,
            self.spn_jitter,
            self.chk_remove_background,
            self.chk_use_alpha,
            self.chk_auto_background,
            self.spn_bg_tolerance,
            self.spn_feather,
            self.chk_keep_holes,
            self.spn_target_density,
            self.spn_edge_strength,
            self.spn_detail_threshold,
            self.spn_max_stones,
            self.cmb_size_mode,
            self.spn_small,
            self.spn_medium,
            self.spn_large,
            self.spn_size_sensitivity,
            self.spn_min_spacing,
            self.cmb_sampling,
            self.chk_brightness,
            self.chk_invert,
            self.cmb_palette_mode,
            self.cmb_palette,
            self.spn_gamma,
            self.spn_contrast,
            self.spn_brightness,
            self.cmb_output_mode,
            self.chk_performance_mode,
            self.chk_group_output,
            self.chk_weld_by_color,
            self.chk_export_background,
            self.chk_debug_export,
            self.chk_allow_svg_fallback,
            self.cmb_structural_mode,
            self.spn_structure_strength,
            self.spn_structural_feature,
            self.spn_symmetry_influence,
            self.spn_border_priority,
            self.spn_center_priority,
            self.spn_curve_smoothness,
            self.spn_simplify,
            self.chk_symmetry,
            self.spn_detail_retention,
            self.spn_silhouette_priority,
            self.spn_merge_distance,
            self.spn_min_curve_length,
            self.cmb_structural_output_mode,
            self.spn_structural_stone,
            self.spn_structural_spacing,
            self.cmb_structural_apply_mode,
        ]
        for control in preview_controls:
            if isinstance(control, (QAbstractSlider, QAbstractSpinBox)):
                control.installEventFilter(self._interaction_filter)
            if hasattr(control, "valueChanged"):
                control.valueChanged.connect(self._on_live_control_changed)
            elif hasattr(control, "currentIndexChanged"):
                control.currentIndexChanged.connect(self._on_live_control_changed)
            elif hasattr(control, "toggled"):
                control.toggled.connect(self._on_live_control_changed)
            elif hasattr(control, "textChanged"):
                control.textChanged.connect(self._on_live_control_changed)

    def _on_preview_interaction_started(self, control):
        if not self.is_tool_active():
            return
        if not self.edt_photo.text().strip():
            return
        if isinstance(control, (QAbstractSlider, QAbstractSpinBox)):
            self._queue_preview("drag", immediate=True)

    def _on_preview_interaction_finished(self, _control):
        if not self.is_tool_active():
            return
        if not self.edt_photo.text().strip():
            return
        self._queue_preview("settled", immediate=False)

    def _invalidation_scope_for_control(self, control) -> str:
        if control in {self.cmb_processing_mode, self.cmb_structural_output_mode}:
            return "mode"
        if control in {self.edt_photo, self.edt_overlay, self.edt_mask}:
            return "source"
        if control in {
            self.cmb_structural_mode,
            self.spn_structure_strength,
            self.spn_structural_feature,
            self.spn_symmetry_influence,
            self.spn_border_priority,
            self.spn_center_priority,
            self.spn_curve_smoothness,
            self.spn_simplify,
            self.chk_symmetry,
            self.spn_detail_retention,
            self.spn_silhouette_priority,
            self.spn_merge_distance,
            self.spn_min_curve_length,
        }:
            return "structural"
        if control in {self.spn_structural_stone, self.spn_structural_spacing, self.cmb_structural_apply_mode}:
            return "structural_pattern"
        if control in {self.chk_remove_background, self.chk_use_alpha, self.chk_auto_background, self.spn_bg_tolerance, self.spn_feather, self.chk_keep_holes}:
            return "mask"
        if control in {self.spn_width, self.spn_height, self.cmb_layout, self.spn_stone, self.spn_gap, self.spn_margin, self.spn_jitter}:
            return "layout"
        if control in {self.spn_target_density, self.spn_edge_strength, self.spn_detail_threshold, self.spn_max_stones}:
            return "decimation"
        if control in {self.cmb_size_mode, self.spn_small, self.spn_medium, self.spn_large, self.spn_size_sensitivity, self.spn_min_spacing}:
            return "size"
        if control in {self.cmb_sampling, self.chk_brightness, self.chk_invert, self.spn_gamma, self.spn_contrast, self.spn_brightness}:
            return "sampling"
        if control in {self.cmb_palette_mode, self.cmb_palette}:
            return "color"
        if control in {self.cmb_output_mode, self.chk_group_output, self.chk_weld_by_color, self.chk_allow_svg_fallback}:
            return "final_output"
        return "view"

    def _on_live_control_changed(self, *_):
        if not self.is_tool_active():
            return
        if self.sender() is self.cmb_processing_mode:
            self._cancel_background_activity(reason="mode switch")
        self._invalidate_cache()
        scope_name = self._invalidation_scope_for_control(self.sender())
        if self.cmb_processing_mode.currentData() == "structural":
            scope = {
                "source": ("image_load", "edge_detection", "detail_filtering", "contour_extraction", "preview_render"),
                "structural": ("edge_detection", "detail_filtering", "contour_extraction", "preview_render"),
                "structural_pattern": ("pattern_integration",),
                "mode": ("preview_render",),
            }.get(scope_name, ("preview_render",))
        else:
            scope = self.engine._controller.affected_stages(scope_name)
        summary = f"{scope_name}: {', '.join(scope)}"
        if summary != self._last_invalidation_summary:
            self._last_invalidation_summary = summary
            logger.info("pointillizer invalidated stages: %s", summary)
        if self.sender() in {self.cmb_processing_mode, self.cmb_structural_output_mode}:
            self._update_mode_visibility()
        if self.edt_photo.text().strip():
            self._queue_preview("settled")

    def _queue_preview(self, profile: str, immediate: bool = False):
        if not self.is_tool_active():
            return
        if not self.edt_photo.text().strip():
            return
        request = self._build_preview_request(profile)
        self._pending_preview_request = request
        self._latest_preview_request_id = request["request_id"]
        structural_mode = request.get("mode") == "structural"
        if profile == "drag":
            self._settled_preview_timer.stop()
            delay_ms = 80 if structural_mode else 56
            if immediate:
                delay_ms = max(40, delay_ms // 2)
            logger.info("photo pointillizer timer start drag-preview delay_ms=%s mode=%s", delay_ms, request.get("mode"))
            self._drag_preview_timer.start(delay_ms)
        else:
            self._drag_preview_timer.stop()
            delay_ms = 260 if structural_mode else 180
            if immediate:
                delay_ms = max(100, delay_ms // 2)
            logger.info("photo pointillizer timer start settled-preview delay_ms=%s mode=%s", delay_ms, request.get("mode"))
            self._settled_preview_timer.start(delay_ms)
        if self._worker and self._worker.isRunning() and self._current_job_kind == "preview":
            self._worker.cancel()

    def _dispatch_preview(self, profile: str):
        if not self.is_tool_active():
            return
        if not self.edt_photo.text().strip():
            return
        request = self._pending_preview_request
        if request is None or request["preview_profile"] != profile:
            return
        if self._worker and self._worker.isRunning():
            return
        self._pending_preview_request = None
        self._start_preview(request, live=True)

    def _browse_file(self, target: QLineEdit, title: str, filter_text: str):
        path, _ = QFileDialog.getOpenFileName(self, title, str(Path.home()), filter_text)
        if path:
            target.setText(path)
            if target is self.edt_photo and not self.edt_output.text().strip():
                self.edt_output.setText(str(Path(path).with_suffix("")))
            self._invalidate_cache()
            self._update_info("Input updated", "-")

    def _capture_vector_shape(self):
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            self._container_shape = selection.Item(1)
            self._container_name = getattr(self._container_shape, "Name", "Selected shape") or "Selected shape"
            self._container_contours = self._flatten_shape_contours(self._container_shape)
            if not self._container_contours:
                raise ValueError("The selected vector shape does not contain a usable closed contour.")
            width, height = corel.get_true_size(self._container_shape)
            self.spn_width.setValue(width)
            self.spn_height.setValue(height)
            bounds = corel.get_shape_bounds(self._container_shape)
            self._container_signature = f"{self._container_name}|{bounds.left:.3f}|{bounds.bottom:.3f}|{bounds.right:.3f}|{bounds.top:.3f}"
            self._invalidate_cache()
            self._update_info("Vector shape captured", "-")
        except Exception as exc:
            QMessageBox.critical(self, "Selection Error", str(exc))

    def _inside_cb(self, x_mm: float, y_mm: float, radius_mm: float) -> bool:
        if not self._container_contours:
            return True
        return self._stone_inside_contours(x_mm, y_mm, radius_mm)

    def _point_line_distance(self, point: Point, start: Point, end: Point) -> float:
        dx = end.x - start.x
        dy = end.y - start.y
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            return point.distance_to(start)
        return abs((dy * point.x) - (dx * point.y) + (end.x * start.y) - (end.y * start.x)) / length

    def _flatten_bezier_segment(
        self,
        start: Point,
        control1: Point,
        control2: Point,
        end: Point,
        tolerance: float,
        depth: int = 0,
        max_depth: int = 12,
    ) -> List[Point]:
        if depth >= max_depth:
            return [start, end]

        flatness = max(
            self._point_line_distance(control1, start, end),
            self._point_line_distance(control2, start, end),
        )
        if flatness <= tolerance:
            return [start, end]

        p01 = Point((start.x + control1.x) / 2.0, (start.y + control1.y) / 2.0)
        p12 = Point((control1.x + control2.x) / 2.0, (control1.y + control2.y) / 2.0)
        p23 = Point((control2.x + end.x) / 2.0, (control2.y + end.y) / 2.0)
        p012 = Point((p01.x + p12.x) / 2.0, (p01.y + p12.y) / 2.0)
        p123 = Point((p12.x + p23.x) / 2.0, (p12.y + p23.y) / 2.0)
        midpoint = Point((p012.x + p123.x) / 2.0, (p012.y + p123.y) / 2.0)

        left = self._flatten_bezier_segment(start, p01, p012, midpoint, tolerance, depth + 1, max_depth)
        right = self._flatten_bezier_segment(midpoint, p123, p23, end, tolerance, depth + 1, max_depth)
        return left[:-1] + right

    def _segment_polyline(self, segment: CurveSegment, tolerance: float = 0.15) -> List[Point]:
        if not segment.is_bezier or not segment.control1 or not segment.control2:
            return [segment.start, segment.end]
        return self._flatten_bezier_segment(
            segment.start,
            segment.control1,
            segment.control2,
            segment.end,
            max(0.01, tolerance),
        )

    def _normalize_contour(self, contour: List[Point]) -> List[Point]:
        cleaned: List[Point] = []
        for point in contour:
            if not cleaned or abs(cleaned[-1].x - point.x) > 1e-9 or abs(cleaned[-1].y - point.y) > 1e-9:
                cleaned.append(point)

        if len(cleaned) < 3:
            return []

        if abs(cleaned[0].x - cleaned[-1].x) > 1e-9 or abs(cleaned[0].y - cleaned[-1].y) > 1e-9:
            cleaned.append(Point(cleaned[0].x, cleaned[0].y))

        return cleaned if len(cleaned) >= 4 else []

    def _flatten_shape_contours(self, shape, tolerance: float = 0.15) -> List[List[Point]]:
        contours: List[List[Point]] = []
        for segments in corel.get_curve_subpaths(shape, require_closed=True):
            points: List[Point] = []
            for segment in segments or []:
                polyline = self._segment_polyline(segment, tolerance=tolerance)
                if points and polyline:
                    polyline = polyline[1:]
                points.extend(polyline)
            contour = self._normalize_contour(points)
            if contour:
                contours.append(contour)
        return contours

    def _contour_row_intersections(self, y: float, contours: List[List[Point]]) -> List[float]:
        intersections: List[float] = []
        for contour in contours:
            if len(contour) < 2:
                continue
            for index in range(1, len(contour)):
                start = contour[index - 1]
                end = contour[index]
                if abs(start.y - end.y) <= 1e-9:
                    continue
                lower_y = min(start.y, end.y)
                upper_y = max(start.y, end.y)
                if y < lower_y or y >= upper_y:
                    continue
                ratio = (y - start.y) / (end.y - start.y)
                intersections.append(start.x + (ratio * (end.x - start.x)))
        intersections.sort()
        return intersections

    def _point_in_contours(self, x: float, y: float) -> bool:
        intersections = self._contour_row_intersections(y, self._container_contours)
        crossings = sum(1 for boundary_x in intersections if x < boundary_x)
        return (crossings % 2) == 1

    def _distance_point_to_segment(self, px: float, py: float, start: Point, end: Point) -> float:
        dx = end.x - start.x
        dy = end.y - start.y
        length_sq = (dx * dx) + (dy * dy)
        if length_sq <= 1e-12:
            return math.hypot(px - start.x, py - start.y)
        t = ((px - start.x) * dx + (py - start.y) * dy) / length_sq
        t = max(0.0, min(1.0, t))
        closest_x = start.x + (t * dx)
        closest_y = start.y + (t * dy)
        return math.hypot(px - closest_x, py - closest_y)

    def _distance_to_contours(self, x: float, y: float) -> float:
        best = float("inf")
        for contour in self._container_contours:
            for index in range(1, len(contour)):
                best = min(best, self._distance_point_to_segment(x, y, contour[index - 1], contour[index]))
        return best

    def _stone_inside_contours(self, x: float, y: float, radius_mm: float) -> bool:
        if not self._point_in_contours(x, y):
            return False
        return self._distance_to_contours(x, y) + 1e-6 >= radius_mm

    def _config(self) -> PointillizerConfig:
        allowed_sizes = [self.spn_medium.value()]
        if self.cmb_size_mode.currentData() != "single":
            allowed_sizes = [self.spn_small.value(), self.spn_medium.value()]
        if self.cmb_size_mode.currentData() in ("small_medium_large", "adaptive"):
            allowed_sizes.append(self.spn_large.value())

        return PointillizerConfig(
            width_mm=self.spn_width.value(),
            height_mm=self.spn_height.value(),
            stone_diameter_mm=self.spn_stone.value(),
            gap_mm=self.spn_gap.value(),
            edge_margin_mm=self.spn_margin.value(),
            jitter_mm=self.spn_jitter.value(),
            layout=self.cmb_layout.currentData(),
            sampling_mode=self.cmb_sampling.currentData(),
            brightness_only=self.chk_brightness.isChecked(),
            brightness_invert=self.chk_invert.isChecked(),
            gamma=self.spn_gamma.value(),
            contrast=self.spn_contrast.value(),
            brightness=self.spn_brightness.value(),
            palette_mode=self.cmb_palette_mode.currentData(),
            palette_name=self.cmb_palette.currentData(),
            output_mode=self.cmb_output_mode.currentData(),
            performance_mode=self.chk_performance_mode.isChecked(),
            group_output=self.chk_group_output.isChecked(),
            weld_by_color=self.chk_weld_by_color.isChecked(),
            export_background=self.chk_export_background.isChecked(),
            debug_export=self.chk_debug_export.isChecked(),
            remove_background=self.chk_remove_background.isChecked(),
            use_source_alpha=self.chk_use_alpha.isChecked(),
            auto_detect_background=self.chk_auto_background.isChecked(),
            background_tolerance=int(self.spn_bg_tolerance.value()),
            feather_px=int(self.spn_feather.value()),
            keep_holes=self.chk_keep_holes.isChecked(),
            target_density=self.spn_target_density.value(),
            preserve_edges_strength=self.spn_edge_strength.value(),
            detail_threshold=self.spn_detail_threshold.value(),
            max_stone_count=int(self.spn_max_stones.value()),
            size_mode=self.cmb_size_mode.currentData(),
            allowed_sizes_mm=tuple(sorted(allowed_sizes)),
            edge_detail_sensitivity=self.spn_size_sensitivity.value(),
            minimum_spacing_mm=self.spn_min_spacing.value(),
        )

    def _structural_config(self) -> StructuralDetailConfig:
        return StructuralDetailConfig(
            width_mm=self.spn_width.value(),
            height_mm=self.spn_height.value(),
            preview_ppm=5 if not self.chk_performance_mode.isChecked() else 4,
            drag_preview_ppm=3 if not self.chk_performance_mode.isChecked() else 2,
            extraction_mode=self.cmb_structural_mode.currentData(),
            structure_strength=self.spn_structure_strength.value(),
            min_motif_size=int(self.spn_structural_feature.value()),
            curve_smoothness=self.spn_curve_smoothness.value(),
            simplification_tolerance=self.spn_simplify.value(),
            symmetry_enabled=self.chk_symmetry.isChecked(),
            symmetry_influence=self.spn_symmetry_influence.value(),
            border_band_priority=self.spn_border_priority.value(),
            center_motif_priority=self.spn_center_priority.value(),
            merge_distance_mm=self.spn_merge_distance.value(),
            minimum_curve_length_mm=self.spn_min_curve_length.value(),
            decorative_detail_retention=self.spn_detail_retention.value(),
            silhouette_priority=self.spn_silhouette_priority.value(),
            performance_mode=self.chk_performance_mode.isChecked(),
        )

    def _structural_pattern_config(self) -> PatternFillConfig:
        return PatternFillConfig(
            width_mm=self.spn_width.value(),
            height_mm=self.spn_height.value(),
            stone_diameter_mm=self.spn_structural_stone.value(),
            spacing_mm=self.spn_structural_spacing.value(),
            offset_mm=0.0,
            offset_count=0,
            line_offset_mm=0.0,
            edge_margin_mm=max(0.0, self.spn_structural_spacing.value() / 2.0),
            fill_layout="hex",
            preview_ppm=6 if not self.chk_performance_mode.isChecked() else 4,
            enable_curve=True,
            enable_offsets=False,
            enable_rays=False,
            enable_fill=False,
            enable_boundary=False,
            color_mode="per_layer",
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
        self.cmb_processing_mode.setEnabled(not running)
        self.cmb_structural_output_mode.setEnabled(not running)

    def _invalidate_cache(self) -> None:
        self._preview_result = None
        self._final_result = None
        self._structural_preview_result = None
        self._structural_pattern_result = None

    def _cancel_background_activity(self, reason: str = "") -> None:
        if self._drag_preview_timer.isActive():
            logger.info("photo pointillizer timer stop drag-preview")
        if self._settled_preview_timer.isActive():
            logger.info("photo pointillizer timer stop settled-preview")
        self._drag_preview_timer.stop()
        self._settled_preview_timer.stop()
        self._pending_preview_request = None
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        if reason:
            logger.info("photo pointillizer background activity cancelled: %s", reason)

    def cancel_pending_work(self) -> None:
        self._cancel_background_activity(reason="cancel_pending_work")

    def suspend_live_updates(self) -> None:
        self._drag_preview_timer.stop()
        self._settled_preview_timer.stop()
        self.preview_canvas.setUpdatesEnabled(False)
        super().suspend_live_updates()

    def resume_live_updates(self) -> None:
        super().resume_live_updates()
        self.preview_canvas.setUpdatesEnabled(True)

    def on_tool_activated(self) -> None:
        super().on_tool_activated()
        self._update_mode_visibility()

    def on_tool_deactivated(self) -> None:
        self._cancel_background_activity(reason="tool deactivated")
        super().on_tool_deactivated()

    def _update_preview_canvas(self):
        if self.cmb_processing_mode.currentData() == "structural":
            if self._structural_pattern_result is not None and getattr(self._structural_pattern_result, "preview_scene", None) is not None:
                self.preview_canvas.set_scene(self._structural_pattern_result.preview_scene, "Structural pattern preview")
                return
            if self._structural_preview_result is not None:
                self.preview_canvas.set_image_preview(
                    self._structural_preview_result.preview_image,
                    self._structural_preview_result.width_mm,
                    self._structural_preview_result.height_mm,
                    render_profile="structural",
                    status_text="Structural detail preview",
                    cache_key=self._structural_preview_result.cache_key,
                )
                return
            self.preview_canvas.clear_scene("No preview generated")
            return
        result = self._preview_result or self._final_result
        if not result:
            self.preview_canvas.clear_scene("No preview generated")
            return
        if result.preview_scene is not None:
            self.preview_canvas.set_scene(result.preview_scene, f"{result.preview_profile.title()} preview")
            return
        self.preview_canvas.clear_scene("Preview scene unavailable")

    def _update_info(self, status: str, result_text: str):
        self.lbl_source.setText(Path(self.edt_photo.text()).name if self.edt_photo.text().strip() else "No photo")
        self.lbl_container.setText(self._container_name)
        self.lbl_status.setText(status)
        if self.cmb_processing_mode.currentData() == "structural":
            if self._structural_pattern_result is not None:
                self.lbl_stones.setText(str(len(self._structural_pattern_result.stones)))
                summary = ", ".join(f"{name}:{count}" for name, count in sorted(self._structural_pattern_result.per_layer.items()))
                self.lbl_colors.setText(summary or "-")
            elif self._structural_preview_result is not None:
                self.lbl_stones.setText(str(len(self._structural_preview_result.paths)))
                self.lbl_colors.setText(f"{len(self._structural_preview_result.paths)} clean curves")
            else:
                self.lbl_stones.setText("0")
                self.lbl_colors.setText(result_text)
        else:
            result = self._preview_result or self._final_result
            if result:
                self.lbl_stones.setText(str(len(result.stones)))
                summary = ", ".join(f"{name}:{count}" for name, count in sorted(result.per_color.items()))
                self.lbl_colors.setText(summary or "-")
            else:
                self.lbl_stones.setText("0")
                self.lbl_colors.setText(result_text)

    def _update_performance_report(self, result) -> None:
        metrics = self._perf_metrics[self._mode_key()]
        if self.cmb_processing_mode.currentData() == "structural":
            total_ms = float(result.timings.get("total", 0.0) * 1000.0)
            diagnostics = dict(getattr(result, "diagnostics", {}) or {})
            profile_name = diagnostics.get("profile", "settled")
            metrics[f"{profile_name}_ms"] = total_ms
            metrics["structural_paths"] = len(getattr(result, "paths", []))
            paint_snapshot = self.preview_canvas.performance_snapshot()
            metrics["paint_ms"] = float(paint_snapshot.get("latest_paint_ms", 0.0))
            cache = dict(diagnostics.get("cache", {}))
            metrics["cache"] = f"hits:{cache.get('hits', 0)} misses:{cache.get('misses', 0)}"
            metrics["slowest_stage"] = diagnostics.get("slowest_stage", "-")
            if hasattr(result, "stones"):
                self.lbl_perf_preview.setText(
                    f"structural drag {metrics['drag_ms']:.0f} ms | settled {metrics['settled_ms']:.0f} ms | pattern stones {len(result.stones)}"
                )
                self.lbl_perf_paint.setText(f"{metrics['paint_ms']:.1f} ms | pattern preview")
            else:
                self.lbl_perf_preview.setText(
                    f"structural drag {metrics['drag_ms']:.0f} ms | settled {metrics['settled_ms']:.0f} ms | curves {metrics['structural_paths']}"
                )
                self.lbl_perf_paint.setText(f"{metrics['paint_ms']:.1f} ms | preview image")
            self.lbl_perf_cache.setText(metrics["cache"])
            self.lbl_perf_slowest.setText(
                f"{metrics['slowest_stage']} | symmetry {'on' if diagnostics.get('symmetry') else 'off'} | perf {'on' if diagnostics.get('performance_mode', self.chk_performance_mode.isChecked()) else 'off'}"
            )
            return
        total_ms = float(result.timings.get("total", 0.0) * 1000.0)
        metrics[f"{result.preview_profile}_ms"] = total_ms
        metrics["stone_counts"][result.preview_profile] = len(result.stones)
        paint_snapshot = self.preview_canvas.performance_snapshot()
        metrics["paint_ms"] = float(paint_snapshot.get("latest_paint_ms", 0.0))
        diagnostics = dict(result.diagnostics or {})
        cache = diagnostics.get("cache", {})
        metrics["cache"] = f"hits:{cache.get('hits', 0)} misses:{cache.get('misses', 0)}"
        metrics["slowest_stage"] = diagnostics.get("slowest_stage", "-")
        self.lbl_perf_preview.setText(
            f"pointillizer drag {metrics['drag_ms']:.0f} ms | settled {metrics['settled_ms']:.0f} ms | final {metrics['final_ms']:.0f} ms"
        )
        self.lbl_perf_paint.setText(
            f"{metrics['paint_ms']:.1f} ms | stones d/s/f {metrics['stone_counts']['drag']}/{metrics['stone_counts']['settled']}/{metrics['stone_counts']['final']}"
        )
        self.lbl_perf_cache.setText(metrics["cache"])
        self.lbl_perf_slowest.setText(
            f"{metrics['slowest_stage']} | multi-size {'on' if diagnostics.get('multi_size_active') else 'off'} | bg {'on' if diagnostics.get('background_removal_active') else 'off'} | perf {'on' if diagnostics.get('performance_mode') else 'off'}"
        )

    def _append_log(self, message: str, *, level: str = "info", force: bool = False) -> None:
        now = time.perf_counter()
        if not force and (now - self._last_log_append) < 0.12:
            return
        self._last_log_append = now
        self.output_log.appendPlainText(message)
        logger.log(getattr(logging, level.upper(), logging.INFO), message)

    def _snapshot_contours(self) -> List[List[Point]]:
        return [[Point(float(point.x), float(point.y)) for point in contour] for contour in self._container_contours]

    def _build_preview_request(self, preview_profile: str) -> Dict[str, Any]:
        self._next_preview_request_id += 1
        request_id = self._next_preview_request_id
        if self.cmb_processing_mode.currentData() == "structural":
            return {
                "request_id": request_id,
                "mode": "structural",
                "preview_profile": preview_profile,
                "photo_path": self.edt_photo.text().strip(),
                "output_base": self.edt_output.text().strip(),
                "structural_config": self._structural_config(),
                "pattern_config": self._structural_pattern_config(),
                "structural_output_mode": self.cmb_structural_output_mode.currentData(),
                "structural_apply_mode": self.cmb_structural_apply_mode.currentData(),
            }
        config = self._config()
        return {
            "request_id": request_id,
            "mode": "pointillizer",
            "preview_profile": preview_profile,
            "photo_path": self.edt_photo.text().strip(),
            "transparent_png": self.edt_overlay.text().strip() or None,
            "mask_path": self.edt_mask.text().strip() or None,
            "container_signature": self._container_signature,
            "config": config,
            "contours": self._snapshot_contours() if self._container_shape is not None else None,
        }

    def _build_final_request(self) -> Dict[str, Any]:
        if self.cmb_processing_mode.currentData() == "structural":
            return {
                "mode": "structural",
                "photo_path": self.edt_photo.text().strip(),
                "output_base": self.edt_output.text().strip(),
                "structural_config": self._structural_config(),
                "pattern_config": self._structural_pattern_config(),
                "structural_output_mode": self.cmb_structural_output_mode.currentData(),
                "structural_apply_mode": self.cmb_structural_apply_mode.currentData(),
            }
        return {
            "mode": "pointillizer",
            "photo_path": self.edt_photo.text().strip(),
            "transparent_png": self.edt_overlay.text().strip() or None,
            "mask_path": self.edt_mask.text().strip() or None,
            "container_signature": self._container_signature,
            "config": self._config(),
            "contours": self._snapshot_contours() if self._container_shape is not None else None,
        }

    def _build_inside_mask(self, contours: Optional[List[List[Point]]], width_mm: float, height_mm: float, ppm: int):
        if not contours:
            return None
        width_px = max(1, int(round(width_mm * ppm)))
        height_px = max(1, int(round(height_mm * ppm)))
        image = Image.new("L", (width_px, height_px), 0)
        draw = ImageDraw.Draw(image)
        for contour in contours:
            points = [(float(point.x) * ppm, float(point.y) * ppm) for point in contour]
            if len(points) >= 3:
                draw.polygon(points, fill=255)
        mask = np.array(image) >= 128
        return mask if bool(mask.any()) else None

    def _preview_cache_key(self, request: Dict[str, Any]) -> str:
        if request.get("mode") == "structural":
            return self.structural_engine.build_cache_key(
                request["photo_path"],
                request["structural_config"],
                preview_profile=request["preview_profile"],
            )
        return self.engine.build_cache_key(
            request["photo_path"],
            request["config"],
            transparent_png=request["transparent_png"],
            mask_path=request["mask_path"],
            container_signature=request["container_signature"],
            preview_mode=True,
            preview_profile=request["preview_profile"],
        )

    def _final_cache_key(self, request: Dict[str, Any]) -> str:
        if request.get("mode") == "structural":
            return self.structural_engine.build_cache_key(
                request["photo_path"],
                request["structural_config"],
                preview_profile="settled",
            )
        return self.engine.build_cache_key(
            request["photo_path"],
            request["config"],
            transparent_png=request["transparent_png"],
            mask_path=request["mask_path"],
            container_signature=request["container_signature"],
            preview_mode=False,
        )

    def _structural_bounds(self, config: StructuralDetailConfig) -> BoundingBox:
        return BoundingBox(0.0, 0.0, float(config.width_mm), float(config.height_mm))

    def _cancel_operation(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self.status_message.emit("Cancelling operation...")

    def _on_snapshot(self, snapshot: ProgressSnapshot) -> None:
        self.phase_label.setText(snapshot.phase)
        self.elapsed_label.setText(f"Elapsed: {self._format_duration(snapshot.elapsed_seconds)}")
        self.eta_label.setText(f"ETA: {self._format_duration(snapshot.eta_seconds)}")
        self.progress_bar.setValue(int(round(snapshot.percent)))
        self.lbl_phase.setText(snapshot.phase)
        self.lbl_elapsed.setText(self._format_duration(snapshot.elapsed_seconds))
        self.lbl_eta.setText(self._format_duration(snapshot.eta_seconds))

    def _start_worker(self, func, finished_slot, *, job_kind: str) -> None:
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Busy", "An operation is already running.")
            return
        self._current_job_kind = job_kind
        self._worker = OperationWorker(func)
        self._worker.snapshot.connect(self._on_snapshot)
        self._worker.finished.connect(finished_slot)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.error.connect(self._on_worker_error)
        self._set_running(True)
        self.progress_bar.setValue(0)
        self._worker.start()

    def _ensure_final_result(self, request: Dict[str, Any], progress_controller=None):
        if request.get("mode") == "structural":
            cache_key = self._final_cache_key(request)
            if self._structural_preview_result and self._structural_preview_result.cache_key == cache_key:
                return self._structural_preview_result, True
            result = self.structural_engine.generate_preview(
                request["photo_path"],
                request["structural_config"],
                preview_profile="settled",
                progress_controller=progress_controller,
            )
            self._structural_preview_result = result
            return result, False
        final_key = self._final_cache_key(request)
        if self._final_result and self._final_result.cache_key == final_key:
            return self._final_result, True
        inside_mask = self._build_inside_mask(
            request.get("contours"),
            request["config"].width_mm,
            request["config"].height_mm,
            request["config"].preview_ppm,
        )
        result = self.engine.generate_final(
            request["photo_path"],
            request["config"],
            transparent_png=request["transparent_png"],
            mask_path=request["mask_path"],
            inside_cb=None,
            inside_mask=inside_mask,
            progress_controller=progress_controller,
            container_signature=request["container_signature"],
        )
        self._final_result = result
        return result, False

    def _ensure_structural_pattern_result(self, request: Dict[str, Any], progress_controller=None):
        structural_result, reused = self._ensure_final_result(request, progress_controller=progress_controller)
        bounds = self._structural_bounds(request["structural_config"])
        pattern_paths = self.structural_engine.to_pattern_paths(structural_result.paths)
        result = self.pattern_engine.generate(bounds, pattern_paths, request["pattern_config"], progress_controller=progress_controller)
        self._structural_pattern_result = result
        return result, reused

    def _apply_task(self, request: Dict[str, Any], progress_controller=None, cancel_callback=None, **_):
        if request.get("mode") == "structural":
            if request["structural_output_mode"] != "pattern_integration":
                raise RuntimeError("Structural Detail Extraction Apply is only available in Pattern integration mode.")
            result, reused = self._ensure_structural_pattern_result(request, progress_controller=progress_controller)
            created = self.final_renderer.render_colored_circles(
                result.stones,
                layer_name="Structural Detail Extraction",
                progress_controller=progress_controller,
                cancel_callback=cancel_callback,
                group_output=True,
                output_mode=request["structural_apply_mode"],
                width_mm=result.width_mm,
                height_mm=result.height_mm,
                weld_by_color=request["structural_apply_mode"] == "welded_color",
                debug_export=self.chk_debug_export.isChecked(),
                allow_svg_fallback=self.chk_allow_svg_fallback.isChecked(),
            )
            return {"result": result, "created": created, "reused_generation": reused}
        result, reused = self._ensure_final_result(request, progress_controller=progress_controller)
        active_config = request["config"]
        created = self.final_renderer.render_colored_circles(
            result.stones,
            layer_name="Photo Pointillizer",
            progress_controller=progress_controller,
            cancel_callback=cancel_callback,
            group_output=active_config.group_output,
            output_mode=active_config.output_mode,
            width_mm=result.width_mm,
            height_mm=result.height_mm,
            weld_by_color=active_config.weld_by_color,
            background_rgb=active_config.background_rgb,
            export_background=active_config.export_background,
            debug_export=active_config.debug_export,
            allow_svg_fallback=self.chk_allow_svg_fallback.isChecked(),
        )
        return {"result": result, "created": created, "reused_generation": reused}

    def _export_task(self, request: Dict[str, Any], progress_controller=None, **_):
        if request.get("mode") == "structural":
            result, reused = self._ensure_final_result(request, progress_controller=progress_controller)
            base = request["output_base"] or str(Path(request["photo_path"]).with_suffix(""))
            if progress_controller:
                progress_controller.start_phase("Exporting structural vectors", total=1, current=0)
            self.structural_engine.export_svg(result.paths, result.width_mm, result.height_mm, str(Path(base).with_suffix(".svg")))
            if progress_controller:
                progress_controller.update(1, 1, force=True)
            return {"result": result, "base": base, "reused_generation": reused}
        result, reused = self._ensure_final_result(request, progress_controller=progress_controller)
        base = request["output_base"]
        if progress_controller:
            progress_controller.start_phase("Exporting output", total=3, current=0)
        self.engine.export_bundle(
            result,
            base,
            background_rgb=request["config"].background_rgb,
            include_background=request["config"].export_background,
        )
        if progress_controller:
            progress_controller.update(3, 3, force=True)
        return {"result": result, "base": base, "reused_generation": reused}

    def _start_preview(self, request: Optional[Dict[str, Any]] = None, live: bool = False, preview_profile: str = "settled"):
        if not self.edt_photo.text().strip():
            QMessageBox.warning(self, "Missing Photo", "Choose a source photo first.")
            return
        request = request or self._build_preview_request(preview_profile)
        if request.get("mode") == "structural":
            self._active_preview_profile = request["preview_profile"]
            self._current_preview_request_id = request["request_id"]
            self._latest_preview_request_id = max(self._latest_preview_request_id, request["request_id"])
            preview_key = self._preview_cache_key(request)
            if self._structural_preview_result and self._structural_preview_result.cache_key == preview_key:
                self._update_preview_canvas()
                self._update_performance_report(self._structural_preview_result)
                self._update_info("Structural preview ready", "-")
                self.status_message.emit(f"Structural preview cache reused: {len(self._structural_preview_result.paths)} curves")
                return
            if request["preview_profile"] != "drag":
                self._append_log("Refreshing structural detail preview..." if live else "Starting structural detail preview...")
            self._start_worker(
                lambda progress_controller=None, **kwargs: {
                    "request_id": request["request_id"],
                    "result": self.structural_engine.generate_preview(
                        request["photo_path"],
                        request["structural_config"],
                        preview_profile=request["preview_profile"],
                        progress_controller=progress_controller,
                    ),
                },
                self._on_preview_finished,
                job_kind="preview",
            )
            return
        self._active_preview_profile = request["preview_profile"]
        self._current_preview_request_id = request["request_id"]
        self._latest_preview_request_id = max(self._latest_preview_request_id, request["request_id"])
        preview_key = self._preview_cache_key(request)
        if self._preview_result and self._preview_result.cache_key == preview_key:
            self._update_preview_canvas()
            self._update_performance_report(self._preview_result)
            self._update_info("Preview ready", "-")
            self.status_message.emit(f"{request['preview_profile'].title()} preview cache reused: {len(self._preview_result.stones)} stones")
            return
        if request["preview_profile"] != "drag":
            message = "Starting preview generation..." if not live else f"Refreshing {request['preview_profile']} preview..."
            self._append_log(message)
        self._start_worker(
            lambda progress_controller=None, **kwargs: {
                "request_id": request["request_id"],
                "result": self.engine.generate_preview(
                    request["photo_path"],
                    request["config"],
                    transparent_png=request["transparent_png"],
                    mask_path=request["mask_path"],
                    inside_cb=None,
                    inside_mask=self._build_inside_mask(
                        request.get("contours"),
                        request["config"].width_mm,
                        request["config"].height_mm,
                        self.engine._effective_config(request["config"], True, request["preview_profile"]).preview_ppm,
                    ),
                    progress_controller=progress_controller,
                    preview_profile=request["preview_profile"],
                ),
            },
            self._on_preview_finished,
            job_kind="preview",
        )

    def _start_apply(self):
        if not self.edt_photo.text().strip():
            QMessageBox.warning(self, "Missing Photo", "Choose a source photo first.")
            return
        if self.cmb_processing_mode.currentData() == "structural" and self.cmb_structural_output_mode.currentData() != "pattern_integration":
            QMessageBox.information(
                self,
                "Structural Preview / Export",
                "Structural Detail Extraction only applies to CorelDRAW when Structural output is set to Pattern integration stones.",
            )
            return
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return
        if self.cmb_output_mode.currentData() == "preview_only":
            QMessageBox.information(self, "Preview Only", "Switch the output mode to a document-writing mode before applying.")
            return
        estimated_stones = len((self._preview_result or self._final_result).stones) if (self._preview_result or self._final_result) else 0
        if self.cmb_output_mode.currentData() == "separate" and estimated_stones > 12000:
            box = QMessageBox(self)
            box.setWindowTitle("Large Native Apply")
            box.setText(
                f"This job is estimated at about {estimated_stones} stones in separate-object mode.\n"
                "Separate native apply is unreliable at this count."
            )
            grouped_btn = box.addButton("Use Grouped Apply", QMessageBox.AcceptRole)
            export_btn = box.addButton("Export Only", QMessageBox.ActionRole)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec_()
            clicked = box.clickedButton()
            if clicked is grouped_btn:
                self.cmb_output_mode.setCurrentIndex(self.cmb_output_mode.findData("grouped_color"))
            elif clicked is export_btn:
                self._start_export()
                return
            else:
                return
        request = self._build_final_request()
        self._append_log("Starting final apply...", force=True)
        self._start_worker(
            lambda progress_controller=None, cancel_callback=None, **kwargs: self._apply_task(
                request,
                progress_controller=progress_controller,
                cancel_callback=cancel_callback,
            ),
            self._on_apply_finished,
            job_kind="apply",
        )

    def _start_export(self):
        if not self.edt_photo.text().strip():
            QMessageBox.warning(self, "Missing Photo", "Choose a source photo first.")
            return
        request = self._build_final_request()
        request["output_base"] = self.edt_output.text().strip() or str(Path(self.edt_photo.text()).with_suffix(""))
        self._append_log(
            "Starting structural vector export..." if request.get("mode") == "structural" else "Starting export...",
            force=True,
        )
        self._start_worker(
            lambda progress_controller=None, **kwargs: self._export_task(
                request,
                progress_controller=progress_controller,
            ),
            self._on_export_finished,
            job_kind="export",
        )

    def _on_preview_finished(self, payload):
        self._set_running(False)
        self._current_job_kind = None
        if not self.is_tool_active():
            return
        request_id = int(payload["request_id"])
        result = payload["result"]
        if request_id != self._latest_preview_request_id:
            self._append_log(
                f"Ignored stale {result.preview_profile} preview result #{request_id}; newer request #{self._latest_preview_request_id} already exists.",
                level="debug",
            )
            if self._pending_preview_request is not None:
                self._queue_preview(self._pending_preview_request["preview_profile"], immediate=True)
            return
        self._latest_applied_preview_id = request_id
        if self.cmb_processing_mode.currentData() == "structural":
            result.diagnostics["profile"] = result.preview_profile if hasattr(result, "preview_profile") else self._active_preview_profile
            self._structural_preview_result = result
        else:
            self._preview_result = result
        self._update_preview_canvas()
        self._update_performance_report(result)
        if self.cmb_processing_mode.currentData() == "structural":
            if self._active_preview_profile != "drag" or result.timings.get("total", 0.0) > 0.12:
                self._append_log(f"{self._active_preview_profile.title()} structural preview ready: {len(result.paths)} curves.")
            self._update_info("Structural preview ready", "-")
            self.status_message.emit(f"Structural detail preview ready: {len(result.paths)} curves")
        else:
            if result.preview_profile != "drag" or result.timings.get("total", 0.0) > 0.12:
                self._append_log(f"{result.preview_profile.title()} preview ready: {len(result.stones)} stones.")
            self._update_info("Preview ready", "-")
            self.status_message.emit(f"Photo Pointillizer {result.preview_profile} preview ready: {len(result.stones)} stones")
        if self._pending_preview_request is not None and self._pending_preview_request["request_id"] > request_id:
            self._queue_preview(self._pending_preview_request["preview_profile"], immediate=True)

    def _on_apply_finished(self, payload):
        self._set_running(False)
        self._current_job_kind = None
        if not self.is_tool_active():
            return
        result = payload["result"]
        if self.cmb_processing_mode.currentData() == "structural":
            self._structural_pattern_result = result
        else:
            self._final_result = result
            self._preview_result = result
        self._update_preview_canvas()
        self._update_performance_report(result)
        created = payload["created"]
        reused = payload["reused_generation"]
        if self.cmb_processing_mode.currentData() == "structural":
            self._append_log(
                f"Applied {created} structural pattern stones to CorelDRAW ({'reused extracted curves' if reused else 'fresh structural extraction'})."
            )
            self._update_info("Applied structural pattern", "-")
            self.status_message.emit(f"Applied {created} structural pattern stones to CorelDRAW")
        else:
            self._append_log(
                f"Applied {created} stones to CorelDRAW ({'reused cached final data' if reused else 'fresh final generation'})."
            )
            self._update_info("Applied to CorelDRAW", "-")
            self.status_message.emit(f"Applied {created} stones to CorelDRAW")
        if self._pending_preview_request is not None:
            self._queue_preview(self._pending_preview_request["preview_profile"], immediate=True)

    def _on_export_finished(self, payload):
        self._set_running(False)
        self._current_job_kind = None
        if not self.is_tool_active():
            return
        result = payload["result"]
        if self.cmb_processing_mode.currentData() == "structural":
            self._structural_preview_result = result
        else:
            self._final_result = result
            self._preview_result = result
        self._update_preview_canvas()
        self._update_performance_report(result)
        if self.cmb_processing_mode.currentData() == "structural":
            self._append_log(f"Exported structural SVG: {payload['base']}.svg")
            self._update_info("Structural SVG exported", Path(payload["base"]).name)
            self.status_message.emit(f"Exported structural SVG: {payload['base']}.svg")
        else:
            self._append_log(f"Exported bundle: {payload['base']}.svg / .csv / .png")
            self._update_info("Exported", Path(payload["base"]).name)
            self.status_message.emit(f"Exported Photo Pointillizer bundle: {payload['base']}")
        if self._pending_preview_request is not None:
            self._queue_preview(self._pending_preview_request["preview_profile"], immediate=True)

    def _on_cancelled(self):
        job_kind = self._current_job_kind
        self._set_running(False)
        self._current_job_kind = None
        if not self.is_tool_active():
            return
        self.phase_label.setText("Cancelled")
        self.lbl_phase.setText("Cancelled")
        self.lbl_status.setText("Cancelled")
        if job_kind != "preview":
            self._append_log("Operation cancelled.")
            self.status_message.emit("Photo Pointillizer operation cancelled")
        if self._pending_preview_request is not None:
            self._queue_preview(self._pending_preview_request["preview_profile"], immediate=True)

    def _on_worker_error(self, message: str):
        job_kind = self._current_job_kind
        self._set_running(False)
        self._current_job_kind = None
        if not self.is_tool_active():
            return
        logger.error("Photo Pointillizer worker failed: %s", message)
        self._append_log(f"Error: {message}", force=True)
        self._update_info("Failed", message)
        if job_kind != "preview":
            QMessageBox.critical(self, "Operation Error", message)
        if self._pending_preview_request is not None:
            self._queue_preview(self._pending_preview_request["preview_profile"], immediate=True)

    def reset_to_defaults(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
        self.cmb_processing_mode.setCurrentIndex(0)
        self.edt_photo.clear()
        self.edt_overlay.clear()
        self.edt_mask.clear()
        self.edt_output.clear()
        self.spn_width.setValue(120)
        self.spn_height.setValue(120)
        self.spn_stone.setValue(2.8)
        self.spn_gap.setValue(0.2)
        self.spn_margin.setValue(0.2)
        self.spn_jitter.setValue(0.0)
        self.cmb_layout.setCurrentIndex(0)
        self.chk_remove_background.setChecked(True)
        self.chk_use_alpha.setChecked(True)
        self.chk_auto_background.setChecked(True)
        self.spn_bg_tolerance.setValue(28)
        self.spn_feather.setValue(0)
        self.chk_keep_holes.setChecked(True)
        self.spn_target_density.setValue(0.95)
        self.spn_edge_strength.setValue(0.75)
        self.spn_detail_threshold.setValue(0.18)
        self.spn_max_stones.setValue(0)
        self.cmb_size_mode.setCurrentIndex(0)
        self.spn_small.setValue(2.0)
        self.spn_medium.setValue(2.8)
        self.spn_large.setValue(4.0)
        self.spn_size_sensitivity.setValue(0.85)
        self.spn_min_spacing.setValue(0.2)
        self.cmb_sampling.setCurrentIndex(0)
        self.chk_brightness.setChecked(False)
        self.chk_invert.setChecked(False)
        self.cmb_palette_mode.setCurrentIndex(2)
        self.cmb_palette.setCurrentIndex(0)
        self.spn_gamma.setValue(1.0)
        self.spn_contrast.setValue(1.0)
        self.spn_brightness.setValue(1.0)
        self.cmb_output_mode.setCurrentIndex(2)
        self.chk_performance_mode.setChecked(True)
        self.chk_group_output.setChecked(True)
        self.chk_weld_by_color.setChecked(False)
        self.chk_export_background.setChecked(False)
        self.chk_debug_export.setChecked(False)
        self.chk_allow_svg_fallback.setChecked(False)
        self.cmb_structural_mode.setCurrentIndex(1)
        self.spn_structure_strength.setValue(0.72)
        self.spn_structural_feature.setValue(80)
        self.spn_symmetry_influence.setValue(0.65)
        self.spn_border_priority.setValue(0.8)
        self.spn_center_priority.setValue(0.7)
        self.spn_curve_smoothness.setValue(0.45)
        self.spn_simplify.setValue(0.5)
        self.chk_symmetry.setChecked(True)
        self.spn_detail_retention.setValue(0.35)
        self.spn_silhouette_priority.setValue(0.95)
        self.spn_merge_distance.setValue(1.8)
        self.spn_min_curve_length.setValue(8.0)
        self.cmb_structural_output_mode.setCurrentIndex(0)
        self.spn_structural_stone.setValue(2.8)
        self.spn_structural_spacing.setValue(0.3)
        self.cmb_structural_apply_mode.setCurrentIndex(0)
        self._container_shape = None
        self._container_contours = []
        self._container_name = "None"
        self._container_signature = ""
        self._pending_preview_request = None
        self._current_job_kind = None
        self._current_preview_request_id = 0
        self._next_preview_request_id = 0
        self._latest_preview_request_id = 0
        self._latest_applied_preview_id = 0
        self._drag_preview_timer.stop()
        self._settled_preview_timer.stop()
        self._perf_metrics = {
            "pointillizer": self._new_perf_metrics(),
            "structural": self._new_perf_metrics(),
        }
        self._invalidate_cache()
        self._update_mode_visibility()
        self.output_log.clear()
        self.preview_canvas.clear_scene("No preview generated")
        self.phase_label.setText("Idle")
        self.elapsed_label.setText("Elapsed: 00:00")
        self.eta_label.setText("ETA: --:--")
        self.progress_bar.setValue(0)
        self.lbl_phase.setText("Idle")
        self.lbl_elapsed.setText("00:00")
        self.lbl_eta.setText("--:--")
        self.lbl_perf_preview.setText("drag 0 ms | settled 0 ms")
        self.lbl_perf_paint.setText("paint 0 ms")
        self.lbl_perf_cache.setText("hits:0 misses:0")
        self.lbl_perf_slowest.setText("-")
        self._set_running(False)
        self._update_info("Idle", "-")


PhotoToRhinestoneSvgWidget = PhotoPointillizerWidget
