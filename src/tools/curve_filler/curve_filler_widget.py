"""
Curve Filler Widget
PyQt5 UI for the Advanced Curve Filler tool.
"""

import logging
from typing import Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox,
    QSlider, QCheckBox, QTabWidget, QScrollArea, QFrame,
    QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer

from ...config import config
from ...core.corel_interface import corel, NoSelectionError
from ...core.preset_manager import preset_manager
from ...ui.icon_utils import apply_button_icons
from .curve_filler_engine import (
    CurveFillerEngine, FillSettings, SpacingMode, AngleMode,
    AlignmentMode, PatternMode
)

logger = logging.getLogger(__name__)


class CurveFillerWidget(QWidget):
    """Main widget for the Curve Filler tool."""

    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        """Initialize the curve filler widget."""
        super().__init__(parent)

        self.engine = CurveFillerEngine()
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._update_preview)

        self._init_ui()
        self._connect_signals()

        logger.info("Curve filler widget initialized.")

    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Left panel - Preview area (placeholder for now)
        left_panel = QFrame()
        left_panel.setFrameStyle(QFrame.StyledPanel)
        left_panel.setMinimumWidth(300)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)

        preview_label = QLabel("Preview Area")
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setStyleSheet("font-size: 14px; color: #888;")
        left_layout.addWidget(preview_label)

        # Instructions
        instructions = QLabel(
            "<b>Instructions:</b><br>"
            "1. Select curve/path<br>"
            "2. Click 'Set Container'<br>"
            "3. Select element(s)<br>"
            "4. Click 'Set Elements'<br>"
            "5. Adjust settings<br>"
            "6. Click 'Fill Curve'"
        )
        instructions.setStyleSheet("padding: 15px; background-color: #2a2a2a; border-radius: 6px;")
        instructions.setWordWrap(True)
        left_layout.addWidget(instructions)

        # Status labels
        self.container_label = QLabel("Container: Not set")
        self.container_label.setStyleSheet("color: #cc241d;")
        left_layout.addWidget(self.container_label)

        self.elements_label = QLabel("Elements: Not set")
        self.elements_label.setStyleSheet("color: #cc241d;")
        left_layout.addWidget(self.elements_label)

        left_layout.addStretch()
        main_layout.addWidget(left_panel, 1)

        # Right panel - Controls
        right_panel = QScrollArea()
        right_panel.setWidgetResizable(True)
        right_panel.setMinimumWidth(320)

        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(4, 4, 4, 4)

        # Selection buttons
        selection_group = QGroupBox("Selection")
        selection_layout = QVBoxLayout(selection_group)

        set_container_btn = QPushButton("Set Container")
        set_container_btn.setStyleSheet("background-color: #458588; font-weight: bold; padding: 8px;")
        set_container_btn.setToolTip("Set the selected curve as the fill container")
        set_container_btn.clicked.connect(self._set_container)
        selection_layout.addWidget(set_container_btn)

        set_elements_btn = QPushButton("Set Elements")
        set_elements_btn.setStyleSheet("background-color: #689d6a; font-weight: bold; padding: 8px;")
        set_elements_btn.setToolTip("Set the selected objects as fill elements")
        set_elements_btn.clicked.connect(self._set_elements)
        selection_layout.addWidget(set_elements_btn)

        controls_layout.addWidget(selection_group)

        # Spacing settings
        spacing_group = QGroupBox("Spacing")
        spacing_layout = QFormLayout(spacing_group)

        self.spacing_mode_combo = QComboBox()
        self.spacing_mode_combo.addItem("Fixed Distance", SpacingMode.FIXED.value)
        self.spacing_mode_combo.addItem("Percentage", SpacingMode.PERCENTAGE.value)
        self.spacing_mode_combo.addItem("Auto-fit", SpacingMode.AUTO_FIT.value)
        self.spacing_mode_combo.addItem("Random", SpacingMode.RANDOM.value)
        spacing_layout.addRow("Mode:", self.spacing_mode_combo)

        self.spacing_value = QDoubleSpinBox()
        self.spacing_value.setRange(0.1, 10000)
        self.spacing_value.setValue(10.0)
        self.spacing_value.setSuffix(" mm")
        self.spacing_value.setDecimals(2)
        spacing_layout.addRow("Distance:", self.spacing_value)

        self.spacing_percentage = QDoubleSpinBox()
        self.spacing_percentage.setRange(10, 500)
        self.spacing_percentage.setValue(100)
        self.spacing_percentage.setSuffix("%")
        spacing_layout.addRow("Percentage:", self.spacing_percentage)

        # Random spacing range
        self.spacing_min = QDoubleSpinBox()
        self.spacing_min.setRange(0.1, 1000)
        self.spacing_min.setValue(5.0)
        self.spacing_min.setSuffix(" mm")
        spacing_layout.addRow("Min (Random):", self.spacing_min)

        self.spacing_max = QDoubleSpinBox()
        self.spacing_max.setRange(0.1, 1000)
        self.spacing_max.setValue(20.0)
        self.spacing_max.setSuffix(" mm")
        spacing_layout.addRow("Max (Random):", self.spacing_max)

        # Padding
        self.start_padding = QDoubleSpinBox()
        self.start_padding.setRange(0, 10000)
        self.start_padding.setValue(0)
        self.start_padding.setSuffix(" mm")
        spacing_layout.addRow("Start Padding:", self.start_padding)

        self.end_padding = QDoubleSpinBox()
        self.end_padding.setRange(0, 10000)
        self.end_padding.setValue(0)
        self.end_padding.setSuffix(" mm")
        spacing_layout.addRow("End Padding:", self.end_padding)

        controls_layout.addWidget(spacing_group)

        # Angle settings
        angle_group = QGroupBox("Rotation")
        angle_layout = QFormLayout(angle_group)

        self.angle_mode_combo = QComboBox()
        self.angle_mode_combo.addItem("Follow Curve", AngleMode.FOLLOW_CURVE.value)
        self.angle_mode_combo.addItem("Fixed Angle", AngleMode.FIXED.value)
        self.angle_mode_combo.addItem("Random", AngleMode.RANDOM.value)
        self.angle_mode_combo.addItem("Incremental", AngleMode.INCREMENTAL.value)
        self.angle_mode_combo.addItem("Perpendicular", AngleMode.PERPENDICULAR.value)
        angle_layout.addRow("Mode:", self.angle_mode_combo)

        self.fixed_angle = QDoubleSpinBox()
        self.fixed_angle.setRange(-360, 360)
        self.fixed_angle.setValue(0)
        self.fixed_angle.setSuffix("°")
        angle_layout.addRow("Fixed Angle:", self.fixed_angle)

        self.angle_increment = QDoubleSpinBox()
        self.angle_increment.setRange(-180, 180)
        self.angle_increment.setValue(15)
        self.angle_increment.setSuffix("°")
        angle_layout.addRow("Increment:", self.angle_increment)

        self.angle_min = QDoubleSpinBox()
        self.angle_min.setRange(0, 360)
        self.angle_min.setValue(0)
        self.angle_min.setSuffix("°")
        angle_layout.addRow("Min (Random):", self.angle_min)

        self.angle_max = QDoubleSpinBox()
        self.angle_max.setRange(0, 360)
        self.angle_max.setValue(360)
        self.angle_max.setSuffix("°")
        angle_layout.addRow("Max (Random):", self.angle_max)

        controls_layout.addWidget(angle_group)

        # Count and alignment
        count_group = QGroupBox("Element Count")
        count_layout = QFormLayout(count_group)

        self.element_count = QSpinBox()
        self.element_count.setRange(0, 10000)
        self.element_count.setValue(0)
        self.element_count.setSpecialValueText("Auto (based on spacing)")
        count_layout.addRow("Count:", self.element_count)

        self.count_slider = QSlider(Qt.Horizontal)
        self.count_slider.setRange(1, 100)
        self.count_slider.setValue(20)
        count_layout.addRow("Quick Adjust:", self.count_slider)

        self.distribute_evenly = QCheckBox("Distribute evenly")
        count_layout.addRow("", self.distribute_evenly)

        controls_layout.addWidget(count_group)

        # Advanced options (collapsible)
        advanced_group = QGroupBox("Advanced Options")
        advanced_layout = QFormLayout(advanced_group)

        self.offset_from_curve = QDoubleSpinBox()
        self.offset_from_curve.setRange(-1000, 1000)
        self.offset_from_curve.setValue(0)
        self.offset_from_curve.setSuffix(" mm")
        advanced_layout.addRow("Offset from curve:", self.offset_from_curve)

        self.collision_detection = QCheckBox("Enable collision detection")
        self.collision_detection.setChecked(config.curve_filler.collision_detection)
        advanced_layout.addRow("", self.collision_detection)

        self.use_element_size = QCheckBox("Use element size for spacing")
        self.use_element_size.setChecked(True)
        self.use_element_size.setToolTip("Auto-calculate spacing from selected element sizes")
        advanced_layout.addRow("", self.use_element_size)

        self.remove_overlaps = QCheckBox("Remove overlaps (post)")
        self.remove_overlaps.setChecked(True)
        self.remove_overlaps.setToolTip("Final cleanup pass to remove overlaps/duplicates")
        advanced_layout.addRow("", self.remove_overlaps)

        self.smart_corners = QCheckBox("Smart corner handling")
        self.smart_corners.setChecked(config.curve_filler.smart_corner_handling)
        advanced_layout.addRow("", self.smart_corners)

        # Scale options
        self.scale_mode_combo = QComboBox()
        self.scale_mode_combo.addItem("Uniform", "uniform")
        self.scale_mode_combo.addItem("Gradient", "gradient")
        self.scale_mode_combo.addItem("Random", "random")
        advanced_layout.addRow("Scale Mode:", self.scale_mode_combo)

        self.scale_factor = QDoubleSpinBox()
        self.scale_factor.setRange(0.01, 10.0)
        self.scale_factor.setValue(1.0)
        self.scale_factor.setDecimals(2)
        advanced_layout.addRow("Scale Factor:", self.scale_factor)

        self.scale_start = QDoubleSpinBox()
        self.scale_start.setRange(0.01, 10.0)
        self.scale_start.setValue(0.5)
        advanced_layout.addRow("Scale Start:", self.scale_start)

        self.scale_end = QDoubleSpinBox()
        self.scale_end.setRange(0.01, 10.0)
        self.scale_end.setValue(1.5)
        advanced_layout.addRow("Scale End:", self.scale_end)

        # Pattern mode
        self.pattern_mode_combo = QComboBox()
        self.pattern_mode_combo.addItem("Single Element", PatternMode.SINGLE.value)
        self.pattern_mode_combo.addItem("Sequence", PatternMode.SEQUENCE.value)
        self.pattern_mode_combo.addItem("Random", PatternMode.RANDOM.value)
        self.pattern_mode_combo.addItem("Alternating", PatternMode.ALTERNATING.value)
        advanced_layout.addRow("Pattern:", self.pattern_mode_combo)

        controls_layout.addWidget(advanced_group)

        # Action buttons
        action_group = QGroupBox("Actions")
        action_layout = QVBoxLayout(action_group)

        preview_btn = QPushButton("Preview")
        preview_btn.clicked.connect(self._preview_fill)
        action_layout.addWidget(preview_btn)

        fill_btn = QPushButton("Fill Curve")
        fill_btn.setStyleSheet("background-color: #98971a; font-weight: bold; padding: 10px; font-size: 13px;")
        fill_btn.setToolTip("Execute the fill operation (Ctrl+F)")
        fill_btn.clicked.connect(self._execute_fill)
        action_layout.addWidget(fill_btn)

        # Post-fill actions
        adjust_layout = QHBoxLayout()
        increase_btn = QPushButton("+10")
        increase_btn.clicked.connect(lambda: self._adjust_count(10))
        adjust_layout.addWidget(increase_btn)

        decrease_btn = QPushButton("-10")
        decrease_btn.clicked.connect(lambda: self._adjust_count(-10))
        adjust_layout.addWidget(decrease_btn)

        action_layout.addLayout(adjust_layout)

        group_btn = QPushButton("Group Results")
        group_btn.clicked.connect(self._group_results)
        action_layout.addWidget(group_btn)

        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all_placed)
        action_layout.addWidget(select_all_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.setStyleSheet("background-color: #cc241d; padding: 6px;")
        clear_btn.clicked.connect(self._clear_placed)
        action_layout.addWidget(clear_btn)

        controls_layout.addWidget(action_group)

        # Preset actions
        preset_group = QGroupBox("Presets")
        preset_layout = QHBoxLayout(preset_group)

        save_preset_btn = QPushButton("Save")
        save_preset_btn.clicked.connect(self.save_as_preset)
        preset_layout.addWidget(save_preset_btn)

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset_to_defaults)
        preset_layout.addWidget(reset_btn)

        controls_layout.addWidget(preset_group)

        controls_layout.addStretch()

        right_panel.setWidget(controls_widget)
        main_layout.addWidget(right_panel)

        icon_map = {
            "set container": "container.png",
            "set elements": "elements.png",
            "preview": "preview.png",
            "fill curve": "fill.png",
            "+10": "add.png",
            "-10": "remove.png",
            "group results": "group.png",
            "select all": "select.png",
            "clear all": "clear.png",
            "save": "save.png",
            "reset": "reset.png",
        }
        apply_button_icons(self, icon_map)

    def _connect_signals(self):
        """Connect UI signals for live updates."""
        # Trigger preview update on value changes
        self.spacing_value.valueChanged.connect(self._schedule_preview)
        self.element_count.valueChanged.connect(self._schedule_preview)
        self.count_slider.valueChanged.connect(self._on_slider_changed)
        self.spacing_mode_combo.currentIndexChanged.connect(self._schedule_preview)
        self.angle_mode_combo.currentIndexChanged.connect(self._schedule_preview)

    def _schedule_preview(self):
        """Schedule a preview update after a short delay."""
        if config.curve_filler.show_preview:
            self._preview_timer.start(500)  # 500ms delay

    def _on_slider_changed(self, value: int):
        """Handle count slider changes."""
        self.element_count.setValue(value)

    def _set_container(self):
        """Set the selected shape as the container."""
        if not corel.is_connected:
            self.status_message.emit("Not connected to CorelDRAW")
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return

        try:
            selection = corel.get_selection()
            if selection.Count != 1:
                QMessageBox.warning(
                    self, "Selection Error",
                    "Please select exactly ONE curve/path as the container."
                )
                return

            container = selection.Item(1)  # COM is 1-indexed
            self.engine.set_container(container)

            self.container_label.setText("Container: Set (curve loaded)")
            self.status_message.emit("Container curve set successfully")

        except NoSelectionError:
            QMessageBox.warning(self, "No Selection", "Please select a curve/path in CorelDRAW.")
        except Exception as e:
            logger.error(f"Error setting container: {e}")
            QMessageBox.critical(self, "Error", f"Failed to set container: {e}")

    def _set_elements(self):
        """Set the selected shapes as fill elements."""
        if not corel.is_connected:
            self.status_message.emit("Not connected to CorelDRAW")
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return

        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(
                    self, "Selection Error",
                    "Please select at least one element to use for filling."
                )
                return

            self.engine.set_fill_elements(selection)

            self.elements_label.setText(f"Fill Elements: {selection.Count} element(s)")
            self.status_message.emit(f"Set {selection.Count} fill element(s)")

        except NoSelectionError:
            QMessageBox.warning(self, "No Selection", "Please select objects in CorelDRAW.")
        except Exception as e:
            logger.error(f"Error setting elements: {e}")
            QMessageBox.critical(self, "Error", f"Failed to set elements: {e}")

    def _get_current_settings(self) -> FillSettings:
        """Get current settings from UI controls."""
        settings = FillSettings(
            spacing_mode=SpacingMode(self.spacing_mode_combo.currentData()),
            spacing_value=self.spacing_value.value(),
            spacing_percentage=self.spacing_percentage.value(),
            spacing_min=self.spacing_min.value(),
            spacing_max=self.spacing_max.value(),
            start_padding=self.start_padding.value(),
            end_padding=self.end_padding.value(),
            angle_mode=AngleMode(self.angle_mode_combo.currentData()),
            fixed_angle=self.fixed_angle.value(),
            angle_min=self.angle_min.value(),
            angle_max=self.angle_max.value(),
            angle_increment=self.angle_increment.value(),
            element_count=self.element_count.value(),
            offset_from_curve=self.offset_from_curve.value(),
            collision_detection=self.collision_detection.isChecked(),
            use_element_size=self.use_element_size.isChecked(),
            remove_overlaps=self.remove_overlaps.isChecked(),
            smart_corners=self.smart_corners.isChecked(),
            distribute_evenly=self.distribute_evenly.isChecked(),
            scale_mode=self.scale_mode_combo.currentData(),
            scale_factor=self.scale_factor.value(),
            scale_start=self.scale_start.value(),
            scale_end=self.scale_end.value(),
            pattern_mode=PatternMode(self.pattern_mode_combo.currentData()),
        )
        return settings

    def _update_preview(self):
        """Update the preview display."""
        # In a full implementation, this would render a preview
        self.status_message.emit("Preview updated")

    def _preview_fill(self):
        """Show a preview of the fill operation."""
        try:
            settings = self._get_current_settings()
            placements = self.engine.calculate_placements(settings)
            self.status_message.emit(f"Preview: {len(placements)} elements would be placed")

            QMessageBox.information(
                self, "Preview",
                f"This operation will place {len(placements)} elements along the curve."
            )
        except Exception as e:
            logger.error(f"Preview failed: {e}")
            QMessageBox.warning(self, "Preview Failed", str(e))

    def _execute_fill(self):
        """Execute the fill operation."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return

        try:
            settings = self._get_current_settings()

            self.progress_updated.emit(0, 100)
            self.status_message.emit("Filling curve...")

            shapes = self.engine.execute_fill(settings=settings)

            self.progress_updated.emit(100, 100)
            self.status_message.emit(f"Successfully placed {len(shapes)} elements")

            # Update UI
            self.count_slider.setValue(len(shapes))

            QMessageBox.information(
                self, "Success",
                f"Successfully placed {len(shapes)} elements along the curve."
            )

            # Hide progress bar after a moment
            QTimer.singleShot(2000, lambda: self.progress_updated.emit(-1, 100))

        except Exception as e:
            logger.error(f"Fill operation failed: {e}")
            self.progress_updated.emit(-1, 100)
            QMessageBox.critical(self, "Fill Failed", f"Operation failed: {e}")

    def _adjust_count(self, delta: int):
        """Adjust the number of placed elements."""
        try:
            stats = self.engine.get_statistics()
            current_count = stats['element_count']
            new_count = max(1, current_count + delta)

            self.engine.adjust_count(new_count)
            self.count_slider.setValue(new_count)
            self.status_message.emit(f"Element count adjusted to {new_count}")

        except Exception as e:
            logger.error(f"Failed to adjust count: {e}")
            QMessageBox.warning(self, "Adjust Failed", str(e))

    def _group_results(self):
        """Group all placed elements."""
        try:
            group = self.engine.group_placed_elements()
            if group:
                self.status_message.emit("Elements grouped successfully")
            else:
                self.status_message.emit("No elements to group")
        except Exception as e:
            logger.error(f"Group failed: {e}")
            QMessageBox.warning(self, "Group Failed", str(e))

    def _select_all_placed(self):
        """Select all placed elements."""
        try:
            self.engine.select_placed_elements()
            self.status_message.emit("All placed elements selected")
        except Exception as e:
            logger.error(f"Select failed: {e}")

    def _clear_placed(self):
        """Clear all placed elements."""
        reply = QMessageBox.question(
            self, "Clear All",
            "Are you sure you want to remove all placed elements?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.engine.clear_placed_elements()
                self.status_message.emit("All placed elements cleared")
            except Exception as e:
                logger.error(f"Clear failed: {e}")
                QMessageBox.warning(self, "Clear Failed", str(e))

    def apply_preset(self, settings: Dict[str, Any]):
        """Apply preset settings to UI controls."""
        try:
            if 'spacing_mode' in settings:
                index = self.spacing_mode_combo.findData(settings['spacing_mode'])
                if index >= 0:
                    self.spacing_mode_combo.setCurrentIndex(index)

            if 'spacing_value' in settings:
                self.spacing_value.setValue(settings['spacing_value'])

            if 'angle_mode' in settings:
                index = self.angle_mode_combo.findData(settings['angle_mode'])
                if index >= 0:
                    self.angle_mode_combo.setCurrentIndex(index)

            if 'fixed_angle' in settings:
                self.fixed_angle.setValue(settings['fixed_angle'])

            if 'collision_detection' in settings:
                self.collision_detection.setChecked(settings['collision_detection'])

            if 'use_element_size' in settings:
                self.use_element_size.setChecked(settings['use_element_size'])

            if 'remove_overlaps' in settings:
                self.remove_overlaps.setChecked(settings['remove_overlaps'])

            if 'smart_corners' in settings:
                self.smart_corners.setChecked(settings['smart_corners'])

            if 'distribute_evenly' in settings:
                self.distribute_evenly.setChecked(settings['distribute_evenly'])

            if 'scale_mode' in settings:
                index = self.scale_mode_combo.findData(settings['scale_mode'])
                if index >= 0:
                    self.scale_mode_combo.setCurrentIndex(index)

            if 'scale_factor' in settings:
                self.scale_factor.setValue(settings['scale_factor'])

            if 'scale_start' in settings:
                self.scale_start.setValue(settings['scale_start'])

            if 'scale_end' in settings:
                self.scale_end.setValue(settings['scale_end'])

            if 'pattern_mode' in settings:
                index = self.pattern_mode_combo.findData(settings['pattern_mode'])
                if index >= 0:
                    self.pattern_mode_combo.setCurrentIndex(index)

            if 'start_padding' in settings:
                self.start_padding.setValue(settings['start_padding'])

            if 'end_padding' in settings:
                self.end_padding.setValue(settings['end_padding'])

            if 'offset_from_curve' in settings:
                self.offset_from_curve.setValue(settings['offset_from_curve'])

            self.status_message.emit("Preset applied successfully")

        except Exception as e:
            logger.error(f"Failed to apply preset: {e}")

    def save_as_preset(self):
        """Save current settings as a preset."""
        name, ok = QInputDialog.getText(
            self, "Save Preset",
            "Enter preset name:"
        )

        if ok and name:
            settings = {
                'spacing_mode': self.spacing_mode_combo.currentData(),
                'spacing_value': self.spacing_value.value(),
                'spacing_percentage': self.spacing_percentage.value(),
                'spacing_min': self.spacing_min.value(),
                'spacing_max': self.spacing_max.value(),
                'start_padding': self.start_padding.value(),
                'end_padding': self.end_padding.value(),
                'angle_mode': self.angle_mode_combo.currentData(),
                'fixed_angle': self.fixed_angle.value(),
                'angle_min': self.angle_min.value(),
                'angle_max': self.angle_max.value(),
                'angle_increment': self.angle_increment.value(),
                'element_count': self.element_count.value(),
                'offset_from_curve': self.offset_from_curve.value(),
                'collision_detection': self.collision_detection.isChecked(),
                'use_element_size': self.use_element_size.isChecked(),
                'remove_overlaps': self.remove_overlaps.isChecked(),
                'smart_corners': self.smart_corners.isChecked(),
                'distribute_evenly': self.distribute_evenly.isChecked(),
                'scale_mode': self.scale_mode_combo.currentData(),
                'scale_factor': self.scale_factor.value(),
                'scale_start': self.scale_start.value(),
                'scale_end': self.scale_end.value(),
                'pattern_mode': self.pattern_mode_combo.currentData(),
            }

            preset_id = preset_manager.save_preset(
                name=name,
                tool='curve_filler',
                settings=settings,
                description=f"Custom curve filler preset: {name}",
                category='curve_filler'
            )

            self.status_message.emit(f"Preset '{name}' saved")
            QMessageBox.information(self, "Saved", f"Preset '{name}' saved successfully.")

    def reset_to_defaults(self):
        """Reset all controls to default values."""
        self.spacing_mode_combo.setCurrentIndex(0)
        self.spacing_value.setValue(config.curve_filler.default_spacing)
        self.spacing_percentage.setValue(100)
        self.spacing_min.setValue(5.0)
        self.spacing_max.setValue(20.0)
        self.start_padding.setValue(0)
        self.end_padding.setValue(0)

        index = self.angle_mode_combo.findData(config.curve_filler.default_angle_mode)
        if index >= 0:
            self.angle_mode_combo.setCurrentIndex(index)

        self.fixed_angle.setValue(config.curve_filler.default_fixed_angle)
        self.angle_min.setValue(0)
        self.angle_max.setValue(360)
        self.angle_increment.setValue(15)

        self.element_count.setValue(0)
        self.offset_from_curve.setValue(0)
        self.collision_detection.setChecked(config.curve_filler.collision_detection)
        self.use_element_size.setChecked(True)
        self.remove_overlaps.setChecked(True)
        self.smart_corners.setChecked(config.curve_filler.smart_corner_handling)

        self.scale_mode_combo.setCurrentIndex(0)
        self.scale_factor.setValue(1.0)
        self.scale_start.setValue(0.5)
        self.scale_end.setValue(1.5)

        self.pattern_mode_combo.setCurrentIndex(0)

        self.status_message.emit("Settings reset to defaults")
