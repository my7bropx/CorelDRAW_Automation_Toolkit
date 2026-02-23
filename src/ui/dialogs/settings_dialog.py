"""
Settings Dialog
Application preferences and configuration.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox,
    QPushButton, QGroupBox, QLabel, QLineEdit, QFileDialog
)
from PyQt5.QtCore import Qt

from ...config import config
from ..icon_utils import apply_button_icons


class SettingsDialog(QDialog):
    """Dialog for configuring application settings."""

    def __init__(self, parent=None):
        """Initialize the settings dialog."""
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(500)
        self._init_ui()
        self._load_current_settings()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Tab widget for different setting categories
        self.tabs = QTabWidget()

        # General settings tab
        general_tab = self._create_general_tab()
        self.tabs.addTab(general_tab, "General")

        # Units settings tab
        units_tab = self._create_units_tab()
        self.tabs.addTab(units_tab, "Units")

        # Curve Filler settings tab
        curve_filler_tab = self._create_curve_filler_tab()
        self.tabs.addTab(curve_filler_tab, "Curve Filler")

        # Performance settings tab
        performance_tab = self._create_performance_tab()
        self.tabs.addTab(performance_tab, "Performance")

        layout.addWidget(self.tabs)

        # Buttons
        button_layout = QHBoxLayout()

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_settings)
        button_layout.addWidget(apply_btn)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self._ok_clicked)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

        icon_map = {
            "reset to defaults": "reset.png",
            "cancel": "clear.png",
            "apply": "apply.png",
            "ok": "apply.png",
        }
        apply_button_icons(self, icon_map)

    def _create_general_tab(self) -> QWidget:
        """Create the general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Appearance group
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout(appearance_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        appearance_layout.addRow("Theme:", self.theme_combo)

        self.tooltips_check = QCheckBox("Show tooltips")
        appearance_layout.addRow("", self.tooltips_check)

        self.animations_check = QCheckBox("Enable animations")
        appearance_layout.addRow("", self.animations_check)

        layout.addWidget(appearance_group)

        # Auto-save group
        autosave_group = QGroupBox("Auto-save")
        autosave_layout = QFormLayout(autosave_group)

        self.autosave_check = QCheckBox("Enable auto-save")
        autosave_layout.addRow("", self.autosave_check)

        self.autosave_interval = QSpinBox()
        self.autosave_interval.setRange(60, 3600)
        self.autosave_interval.setSuffix(" seconds")
        autosave_layout.addRow("Interval:", self.autosave_interval)

        layout.addWidget(autosave_group)

        # Recent files
        recent_group = QGroupBox("Recent Files")
        recent_layout = QFormLayout(recent_group)

        self.recent_limit = QSpinBox()
        self.recent_limit.setRange(5, 50)
        recent_layout.addRow("Maximum entries:", self.recent_limit)

        layout.addWidget(recent_group)

        layout.addStretch()
        return widget

    def _create_units_tab(self) -> QWidget:
        """Create the units settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        units_group = QGroupBox("Measurement Units")
        units_layout = QFormLayout(units_group)

        self.default_unit = QComboBox()
        self.default_unit.addItem("Millimeters (mm)", "mm")
        self.default_unit.addItem("Inches (in)", "inches")
        self.default_unit.addItem("Pixels (px)", "pixels")
        self.default_unit.addItem("Points (pt)", "points")
        units_layout.addRow("Default unit:", self.default_unit)

        self.decimal_precision = QSpinBox()
        self.decimal_precision.setRange(1, 6)
        units_layout.addRow("Decimal precision:", self.decimal_precision)

        self.use_system_units = QCheckBox("Use CorelDRAW document units")
        units_layout.addRow("", self.use_system_units)

        layout.addWidget(units_group)
        layout.addStretch()
        return widget

    def _create_curve_filler_tab(self) -> QWidget:
        """Create curve filler specific settings."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        defaults_group = QGroupBox("Default Values")
        defaults_layout = QFormLayout(defaults_group)

        self.cf_default_spacing = QDoubleSpinBox()
        self.cf_default_spacing.setRange(0.1, 1000)
        self.cf_default_spacing.setDecimals(2)
        defaults_layout.addRow("Default spacing:", self.cf_default_spacing)

        self.cf_angle_mode = QComboBox()
        self.cf_angle_mode.addItem("Follow Curve", "follow_curve")
        self.cf_angle_mode.addItem("Fixed Angle", "fixed")
        self.cf_angle_mode.addItem("Random", "random")
        defaults_layout.addRow("Default angle mode:", self.cf_angle_mode)

        self.cf_fixed_angle = QDoubleSpinBox()
        self.cf_fixed_angle.setRange(0, 360)
        self.cf_fixed_angle.setSuffix("°")
        defaults_layout.addRow("Default fixed angle:", self.cf_fixed_angle)

        layout.addWidget(defaults_group)

        preview_group = QGroupBox("Preview")
        preview_layout = QFormLayout(preview_group)

        self.cf_show_preview = QCheckBox("Show live preview")
        preview_layout.addRow("", self.cf_show_preview)

        self.cf_preview_quality = QComboBox()
        self.cf_preview_quality.addItem("Low (Fast)", "low")
        self.cf_preview_quality.addItem("Medium", "medium")
        self.cf_preview_quality.addItem("High (Slow)", "high")
        preview_layout.addRow("Preview quality:", self.cf_preview_quality)

        layout.addWidget(preview_group)

        advanced_group = QGroupBox("Advanced")
        advanced_layout = QFormLayout(advanced_group)

        self.cf_collision_detection = QCheckBox("Enable collision detection")
        advanced_layout.addRow("", self.cf_collision_detection)

        self.cf_smart_corners = QCheckBox("Smart corner handling")
        advanced_layout.addRow("", self.cf_smart_corners)

        self.cf_undo_steps = QSpinBox()
        self.cf_undo_steps.setRange(10, 200)
        advanced_layout.addRow("Undo history size:", self.cf_undo_steps)

        layout.addWidget(advanced_group)

        layout.addStretch()
        return widget

    def _create_performance_tab(self) -> QWidget:
        """Create performance settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        threading_group = QGroupBox("Multi-threading")
        threading_layout = QFormLayout(threading_group)

        self.parallel_processing = QCheckBox("Enable parallel processing")
        threading_layout.addRow("", self.parallel_processing)

        self.max_threads = QSpinBox()
        self.max_threads.setRange(1, 16)
        threading_layout.addRow("Maximum threads:", self.max_threads)

        layout.addWidget(threading_group)

        logging_group = QGroupBox("Logging")
        logging_layout = QFormLayout(logging_group)

        self.log_level = QComboBox()
        self.log_level.addItem("Debug", "DEBUG")
        self.log_level.addItem("Info", "INFO")
        self.log_level.addItem("Warning", "WARNING")
        self.log_level.addItem("Error", "ERROR")
        logging_layout.addRow("Log level:", self.log_level)

        layout.addWidget(logging_group)

        updates_group = QGroupBox("Updates")
        updates_layout = QFormLayout(updates_group)

        self.check_updates = QCheckBox("Check for updates automatically")
        updates_layout.addRow("", self.check_updates)

        layout.addWidget(updates_group)

        layout.addStretch()
        return widget

    def _load_current_settings(self):
        """Load current settings into UI controls."""
        # General
        index = self.theme_combo.findData(config.app.theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        self.tooltips_check.setChecked(config.app.show_tooltips)
        self.animations_check.setChecked(config.app.enable_animations)
        self.autosave_check.setChecked(config.app.auto_save)
        self.autosave_interval.setValue(config.app.auto_save_interval)
        self.recent_limit.setValue(config.app.recent_files_limit)

        # Units
        index = self.default_unit.findData(config.units.default_unit)
        if index >= 0:
            self.default_unit.setCurrentIndex(index)
        self.decimal_precision.setValue(config.units.decimal_precision)
        self.use_system_units.setChecked(config.units.use_system_units)

        # Curve Filler
        self.cf_default_spacing.setValue(config.curve_filler.default_spacing)
        index = self.cf_angle_mode.findData(config.curve_filler.default_angle_mode)
        if index >= 0:
            self.cf_angle_mode.setCurrentIndex(index)
        self.cf_fixed_angle.setValue(config.curve_filler.default_fixed_angle)
        self.cf_show_preview.setChecked(config.curve_filler.show_preview)
        index = self.cf_preview_quality.findData(config.curve_filler.preview_quality)
        if index >= 0:
            self.cf_preview_quality.setCurrentIndex(index)
        self.cf_collision_detection.setChecked(config.curve_filler.collision_detection)
        self.cf_smart_corners.setChecked(config.curve_filler.smart_corner_handling)
        self.cf_undo_steps.setValue(config.curve_filler.undo_steps)

        # Performance
        self.parallel_processing.setChecked(config.batch_processor.parallel_processing)
        self.max_threads.setValue(config.batch_processor.max_threads)
        index = self.log_level.findData(config.app.log_level)
        if index >= 0:
            self.log_level.setCurrentIndex(index)
        self.check_updates.setChecked(config.app.check_updates)

    def _apply_settings(self):
        """Apply settings from UI to config."""
        # General
        config.app.theme = self.theme_combo.currentData()
        config.app.show_tooltips = self.tooltips_check.isChecked()
        config.app.enable_animations = self.animations_check.isChecked()
        config.app.auto_save = self.autosave_check.isChecked()
        config.app.auto_save_interval = self.autosave_interval.value()
        config.app.recent_files_limit = self.recent_limit.value()

        # Units
        config.units.default_unit = self.default_unit.currentData()
        config.units.decimal_precision = self.decimal_precision.value()
        config.units.use_system_units = self.use_system_units.isChecked()

        # Curve Filler
        config.curve_filler.default_spacing = self.cf_default_spacing.value()
        config.curve_filler.default_angle_mode = self.cf_angle_mode.currentData()
        config.curve_filler.default_fixed_angle = self.cf_fixed_angle.value()
        config.curve_filler.show_preview = self.cf_show_preview.isChecked()
        config.curve_filler.preview_quality = self.cf_preview_quality.currentData()
        config.curve_filler.collision_detection = self.cf_collision_detection.isChecked()
        config.curve_filler.smart_corner_handling = self.cf_smart_corners.isChecked()
        config.curve_filler.undo_steps = self.cf_undo_steps.value()

        # Performance
        config.batch_processor.parallel_processing = self.parallel_processing.isChecked()
        config.batch_processor.max_threads = self.max_threads.value()
        config.app.log_level = self.log_level.currentData()
        config.app.check_updates = self.check_updates.isChecked()

        config.save()

    def _reset_to_defaults(self):
        """Reset all settings to defaults."""
        config.reset_to_defaults()
        self._load_current_settings()

    def _ok_clicked(self):
        """Handle OK button click."""
        self._apply_settings()
        self.accept()
