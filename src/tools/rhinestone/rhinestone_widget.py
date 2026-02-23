"""
Rhinestone Design Widget
Like Curve Filler - select container and element separately.
Features:
- Select container and elements separately
- Hexagonal Grid and Random Fill patterns only
- Enhanced hexagonal grid options
- Detailed container and element information
- Multi-size stone support
- Resizable panels
- Stone size presets
- Change stone sizes for selected elements
"""

import logging
from typing import Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QDoubleSpinBox, QComboBox, QSpinBox,
    QCheckBox, QMessageBox, QFileDialog, QFrame, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea,
    QSizePolicy, QListWidget, QListWidgetItem, QAbstractItemView,
    QGridLayout
)
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QIcon

from ...config import config
from ...core.corel_interface import corel
from ...ui.icon_utils import apply_button_icons, load_icon
from .rhinestone_engine import (
    RhinestoneEngine, RhinestoneSettings, PatternType, STONE_SIZES
)

logger = logging.getLogger(__name__)


class RhinestoneWidget(QWidget):
    """Widget for rhinestone design - like Curve Filler with multi-size support."""

    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = RhinestoneEngine()
        self._container_shape = None
        self._container_bounds = None
        self._element_shapes = []
        self._element_info = None
        self._multi_sizes = []
        self._multi_distributions = []
        self._selected_stone_sizes = {}
        self._init_ui()
        logger.info("Rhinestone widget initialized.")

    def _load_icon(self, name, fallback=None):
        """Load icon with fallback."""
        icon = load_icon(name)
        if not icon.isNull():
            return icon
        return QIcon() if fallback is None else fallback

    def _init_ui(self):
        """Initialize UI - like Curve Filler with resizable panels."""
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Left panel - Instructions, Status & Multi-size Selection
        left_panel = QScrollArea()
        left_panel.setWidgetResizable(True)
        left_panel.setMinimumWidth(300)
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("Rhinestone Designer")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        left_layout.addWidget(title)

        # Selection Buttons with Icons
        selection_group = QGroupBox("Select Shapes")
        selection_layout = QVBoxLayout(selection_group)
        
        set_container_btn = QPushButton("Set Container")
        set_container_btn.setIcon(self._load_icon("container.png"))
        set_container_btn.setIconSize(QSize(16, 16))
        set_container_btn.setStyleSheet("background-color: #458588; font-weight: bold; padding: 8px;")
        set_container_btn.setToolTip("Select container shape in CorelDRAW, then click to set")
        set_container_btn.clicked.connect(self._set_container)
        selection_layout.addWidget(set_container_btn)

        set_elements_btn = QPushButton("Set Elements")
        set_elements_btn.setIcon(self._load_icon("elements.png"))
        set_elements_btn.setIconSize(QSize(16, 16))
        set_elements_btn.setStyleSheet("background-color: #689d6a; font-weight: bold; padding: 8px;")
        set_elements_btn.setToolTip("Select stone/element shapes in CorelDRAW, then click to set")
        set_elements_btn.clicked.connect(self._set_elements)
        selection_layout.addWidget(set_elements_btn)
        
        left_layout.addWidget(selection_group)

        # Container Details Group
        container_group = QGroupBox("Container Details")
        container_layout = QVBoxLayout(container_group)
        
        self.container_label = QLabel("Not set")
        self.container_label.setStyleSheet("color: #cc241d; font-weight: bold;")
        container_layout.addWidget(self.container_label)
        
        # Container info grid
        container_info = QGridLayout()
        container_info.setSpacing(4)
        
        self.container_type_label = QLabel("Type: -")
        self.container_type_label.setStyleSheet("color: #aaa; font-size: 11px;")
        container_info.addWidget(self.container_type_label, 0, 0)
        
        self.container_size_label = QLabel("Size: -")
        self.container_size_label.setStyleSheet("color: #aaa; font-size: 11px;")
        container_info.addWidget(self.container_size_label, 0, 1)
        
        self.container_pos_label = QLabel("Position: -")
        self.container_pos_label.setStyleSheet("color: #aaa; font-size: 11px;")
        container_info.addWidget(self.container_pos_label, 1, 0)
        
        self.container_area_label = QLabel("Area: -")
        self.container_area_label.setStyleSheet("color: #aaa; font-size: 11px;")
        container_info.addWidget(self.container_area_label, 1, 1)
        
        container_layout.addLayout(container_info)
        left_layout.addWidget(container_group)
        
        # Element Details Group
        element_group = QGroupBox("Element Details")
        element_layout = QVBoxLayout(element_group)
        
        self.elements_label = QLabel("Not set")
        self.elements_label.setStyleSheet("color: #cc241d; font-weight: bold;")
        element_layout.addWidget(self.elements_label)
        
        # Element info grid
        element_info = QGridLayout()
        element_info.setSpacing(4)
        
        self.element_count_label = QLabel("Count: -")
        self.element_count_label.setStyleSheet("color: #aaa; font-size: 11px;")
        element_info.addWidget(self.element_count_label, 0, 0)
        
        self.element_size_label = QLabel("Avg Size: -")
        self.element_size_label.setStyleSheet("color: #aaa; font-size: 11px;")
        element_info.addWidget(self.element_size_label, 0, 1)
        
        self.element_type_label = QLabel("Types: -")
        self.element_type_label.setStyleSheet("color: #aaa; font-size: 11px;")
        element_info.addWidget(self.element_type_label, 1, 0, 1, 2)
        
        element_layout.addLayout(element_info)
        left_layout.addWidget(element_group)

        # Instructions
        instructions = QLabel(
            "<b>Instructions:</b><br>"
            "1. Select CONTAINER shape<br>"
            "2. Click 'Set Container'<br>"
            "3. Select STONE shapes<br>"
            "4. Click 'Set Elements'<br>"
            "5. Adjust settings<br>"
            "6. Click 'Fill'"
        )
        instructions.setStyleSheet("padding: 10px; background-color: #2a2a2a; border-radius: 4px;")
        instructions.setWordWrap(True)
        left_layout.addWidget(instructions)

        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QFormLayout(stats_group)
        
        self.stone_count_label = QLabel("0")
        stats_layout.addRow("Total Stones:", self.stone_count_label)
        
        self.coverage_label = QLabel("0 sq mm")
        stats_layout.addRow("Coverage Area:", self.coverage_label)
        
        left_layout.addWidget(stats_group)

        # Multi-size stone selection
        multi_size_group = QGroupBox("Multi-Size Selection")
        multi_size_layout = QVBoxLayout(multi_size_group)
        
        self.enable_multi_size = QCheckBox("Enable Multiple Sizes")
        self.enable_multi_size.stateChanged.connect(self._on_multi_size_toggle)
        multi_size_layout.addWidget(self.enable_multi_size)
        
        self.multi_table = QTableWidget()
        self.multi_table.setColumnCount(3)
        self.multi_table.setHorizontalHeaderLabels(["Size", "%", "Use"])
        header = self.multi_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.Fixed)
            header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.multi_table.setColumnWidth(1, 60)
        self.multi_table.setColumnWidth(2, 50)
        self.multi_table.setMaximumHeight(200)
        
        self.multi_table.setRowCount(len(STONE_SIZES))
        for i, (name, diameter) in enumerate(STONE_SIZES.items()):
            size_item = QTableWidgetItem(f"{name} ({diameter}mm)")
            size_item.setFlags(size_item.flags() & ~Qt.ItemIsEditable)
            size_item.setData(Qt.UserRole, name)
            self.multi_table.setItem(i, 0, size_item)
            
            pct_spin = QDoubleSpinBox()
            pct_spin.setRange(0, 100)
            pct_spin.setValue(0)
            pct_spin.setSuffix("%")
            pct_spin.setEnabled(False)
            pct_spin.valueChanged.connect(lambda v, row=i: self._on_pct_changed(row, v))
            self.multi_table.setCellWidget(i, 1, pct_spin)
            
            use_chk = QCheckBox()
            use_chk.stateChanged.connect(lambda state, row=i: self._on_use_changed(row, state))
            self.multi_table.setCellWidget(i, 2, use_chk)
        
        multi_size_layout.addWidget(self.multi_table)
        
        preset_layout = QHBoxLayout()
        preset_label = QLabel("Presets:")
        preset_layout.addWidget(preset_label)
        
        small_btn = QPushButton("Small")
        small_btn.setToolTip("SS6 + SS10")
        small_btn.clicked.connect(lambda: self._apply_size_preset(["SS6", "SS10"]))
        preset_layout.addWidget(small_btn)
        
        medium_btn = QPushButton("Medium")
        medium_btn.setToolTip("SS10 + SS16 + SS20")
        medium_btn.clicked.connect(lambda: self._apply_size_preset(["SS10", "SS16", "SS20"]))
        preset_layout.addWidget(medium_btn)
        
        large_btn = QPushButton("Large")
        large_btn.setToolTip("SS20 + SS30 + SS40")
        large_btn.clicked.connect(lambda: self._apply_size_preset(["SS20", "SS30", "SS40"]))
        preset_layout.addWidget(large_btn)
        
        equal_btn = QPushButton("Equal")
        equal_btn.setToolTip("Distribute equally")
        equal_btn.clicked.connect(self._equalize_distribution)
        preset_layout.addWidget(equal_btn)
        
        multi_size_layout.addLayout(preset_layout)
        
        self.distribution_label = QLabel("No sizes selected")
        self.distribution_label.setStyleSheet("color: #689d6a; padding: 5px;")
        multi_size_layout.addWidget(self.distribution_label)
        
        left_layout.addWidget(multi_size_group)
        
        # Change Size of Selected Stones
        change_size_group = QGroupBox("Change Selected Stones")
        change_size_layout = QVBoxLayout(change_size_group)
        
        change_size_info = QLabel("Change size of stones already placed in CorelDRAW")
        change_size_info.setStyleSheet("color: #aaa; font-size: 11px;")
        change_size_layout.addWidget(change_size_info)
        
        change_btn_layout = QHBoxLayout()
        self.change_to_size = QComboBox()
        for name in STONE_SIZES.keys():
            self.change_to_size.addItem(f"{name} ({STONE_SIZES[name]}mm)", name)
        change_btn_layout.addWidget(self.change_to_size)
        
        apply_size_btn = QPushButton("Apply to Selected")
        apply_size_btn.setIcon(self._load_icon("apply.png"))
        apply_size_btn.setIconSize(QSize(14, 14))
        apply_size_btn.setToolTip("Apply selected size to selected stones in CorelDRAW")
        apply_size_btn.clicked.connect(self._apply_size_to_selected)
        change_btn_layout.addWidget(apply_size_btn)
        
        change_size_layout.addLayout(change_btn_layout)
        left_layout.addWidget(change_size_group)
        
        left_layout.addStretch()
        
        left_panel.setWidget(left_widget)

        # Right panel - Controls
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(4, 4, 4, 4)

        # Pattern
        pattern_group = QGroupBox("Fill Pattern")
        pattern_layout = QFormLayout(pattern_group)
        
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItem("Hexagonal Grid", "hexagonal")
        self.pattern_combo.addItem("Random Scatter", "random")
        self.pattern_combo.currentIndexChanged.connect(self._on_pattern_changed)
        pattern_layout.addRow("Pattern:", self.pattern_combo)
        
        right_layout.addWidget(pattern_group)
        
        # Hexagonal Grid Options - Comprehensive settings
        self.hex_options_group = QGroupBox("Hexagonal Grid Options")
        hex_layout = QFormLayout(self.hex_options_group)
        
        # Grid Size Section
        grid_size_label = QLabel("Grid Size")
        grid_size_label.setStyleSheet("font-weight: bold; color: #83a598; margin-top: 5px;")
        hex_layout.addRow(grid_size_label)
        
        self.hex_auto_calc = QCheckBox("Auto-calculate grid size")
        self.hex_auto_calc.setChecked(True)
        self.hex_auto_calc.setToolTip("Automatically calculate rows/columns based on container size")
        self.hex_auto_calc.stateChanged.connect(self._on_auto_calc_toggle)
        hex_layout.addRow("", self.hex_auto_calc)
        
        self.hex_rows = QSpinBox()
        self.hex_rows.setRange(1, 1000)
        self.hex_rows.setValue(20)
        self.hex_rows.setEnabled(False)
        self.hex_rows.setToolTip("Number of rows in the grid")
        hex_layout.addRow("Rows:", self.hex_rows)
        
        self.hex_cols = QSpinBox()
        self.hex_cols.setRange(1, 1000)
        self.hex_cols.setValue(20)
        self.hex_cols.setEnabled(False)
        self.hex_cols.setToolTip("Number of columns in the grid")
        hex_layout.addRow("Columns:", self.hex_cols)
        
        # Stagger Section
        stagger_label = QLabel("Stagger (Offset)")
        stagger_label.setStyleSheet("font-weight: bold; color: #83a598; margin-top: 10px;")
        hex_layout.addRow(stagger_label)
        
        self.hex_stagger = QCheckBox("Enable stagger (honeycomb pattern)")
        self.hex_stagger.setChecked(True)
        self.hex_stagger.setToolTip("Offset alternate rows for honeycomb pattern")
        hex_layout.addRow("", self.hex_stagger)
        
        self.hex_stagger_amount = QDoubleSpinBox()
        self.hex_stagger_amount.setRange(0, 100)
        self.hex_stagger_amount.setValue(50)
        self.hex_stagger_amount.setSuffix(" %")
        self.hex_stagger_amount.setSingleStep(5)
        self.hex_stagger_amount.setToolTip("Amount of stagger (50% = perfect honeycomb)")
        hex_layout.addRow("Stagger Amount:", self.hex_stagger_amount)
        
        # Positioning Section
        position_label = QLabel("Position & Orientation")
        position_label.setStyleSheet("font-weight: bold; color: #83a598; margin-top: 10px;")
        hex_layout.addRow(position_label)
        
        self.hex_rotation = QDoubleSpinBox()
        self.hex_rotation.setRange(-180, 180)
        self.hex_rotation.setValue(0)
        self.hex_rotation.setSuffix("°")
        self.hex_rotation.setSingleStep(15)
        self.hex_rotation.setToolTip("Rotate the entire grid pattern")
        hex_layout.addRow("Grid Rotation:", self.hex_rotation)
        
        self.hex_offset_x = QDoubleSpinBox()
        self.hex_offset_x.setRange(-500, 500)
        self.hex_offset_x.setValue(0)
        self.hex_offset_x.setSuffix(" mm")
        self.hex_offset_x.setSingleStep(0.5)
        self.hex_offset_x.setToolTip("Horizontal offset from container edge")
        hex_layout.addRow("Offset X:", self.hex_offset_x)
        
        self.hex_offset_y = QDoubleSpinBox()
        self.hex_offset_y.setRange(-500, 500)
        self.hex_offset_y.setValue(0)
        self.hex_offset_y.setSuffix(" mm")
        self.hex_offset_y.setSingleStep(0.5)
        self.hex_offset_y.setToolTip("Vertical offset from container edge")
        hex_layout.addRow("Offset Y:", self.hex_offset_y)
        
        # Margins & Boundaries Section
        margin_label = QLabel("Margins & Boundaries")
        margin_label.setStyleSheet("font-weight: bold; color: #83a598; margin-top: 10px;")
        hex_layout.addRow(margin_label)
        
        self.hex_edge_margin = QDoubleSpinBox()
        self.hex_edge_margin.setRange(0, 50)
        self.hex_edge_margin.setValue(1.0)
        self.hex_edge_margin.setSuffix(" mm")
        self.hex_edge_margin.setSingleStep(0.5)
        self.hex_edge_margin.setToolTip("Distance from container edge to first stone")
        hex_layout.addRow("Edge Margin:", self.hex_edge_margin)
        
        self.hex_clip_to_container = QCheckBox("Clip to container bounds")
        self.hex_clip_to_container.setChecked(True)
        self.hex_clip_to_container.setToolTip("Only place stones inside container boundaries")
        hex_layout.addRow("", self.hex_clip_to_container)
        
        self.hex_center_grid = QCheckBox("Center grid in container")
        self.hex_center_grid.setChecked(True)
        self.hex_center_grid.setToolTip("Center the grid pattern within the container")
        hex_layout.addRow("", self.hex_center_grid)
        
        # Spacing Fine-tuning Section
        spacing_label = QLabel("Spacing Fine-tuning")
        spacing_label.setStyleSheet("font-weight: bold; color: #83a598; margin-top: 10px;")
        hex_layout.addRow(spacing_label)
        
        self.hex_horizontal_spacing = QDoubleSpinBox()
        self.hex_horizontal_spacing.setRange(-5, 20)
        self.hex_horizontal_spacing.setValue(0)
        self.hex_horizontal_spacing.setSuffix(" mm")
        self.hex_horizontal_spacing.setSingleStep(0.1)
        self.hex_horizontal_spacing.setToolTip("Additional horizontal spacing between stones")
        hex_layout.addRow("H Spacing:", self.hex_horizontal_spacing)
        
        self.hex_vertical_spacing = QDoubleSpinBox()
        self.hex_vertical_spacing.setRange(-5, 20)
        self.hex_vertical_spacing.setValue(0)
        self.hex_vertical_spacing.setSuffix(" mm")
        self.hex_vertical_spacing.setSingleStep(0.1)
        self.hex_vertical_spacing.setToolTip("Additional vertical spacing between stones")
        hex_layout.addRow("V Spacing:", self.hex_vertical_spacing)
        
        self.hex_scale_factor = QDoubleSpinBox()
        self.hex_scale_factor.setRange(0.5, 2.0)
        self.hex_scale_factor.setValue(1.0)
        self.hex_scale_factor.setSingleStep(0.05)
        self.hex_scale_factor.setToolTip("Scale factor for overall grid spacing (1.0 = normal)")
        hex_layout.addRow("Scale Factor:", self.hex_scale_factor)
        
        # Quick Presets
        preset_label = QLabel("Quick Presets")
        preset_label.setStyleSheet("font-weight: bold; color: #83a598; margin-top: 10px;")
        hex_layout.addRow(preset_label)
        
        hex_preset_layout = QHBoxLayout()
        
        tight_btn = QPushButton("Tight")
        tight_btn.setToolTip("Minimal spacing for maximum coverage")
        tight_btn.setMaximumWidth(60)
        tight_btn.clicked.connect(lambda: self._apply_hex_preset('tight'))
        hex_preset_layout.addWidget(tight_btn)
        
        normal_btn = QPushButton("Normal")
        normal_btn.setToolTip("Standard honeycomb spacing")
        normal_btn.setMaximumWidth(60)
        normal_btn.clicked.connect(lambda: self._apply_hex_preset('normal'))
        hex_preset_layout.addWidget(normal_btn)
        
        loose_btn = QPushButton("Loose")
        loose_btn.setToolTip("Wider spacing for airy look")
        loose_btn.setMaximumWidth(60)
        loose_btn.clicked.connect(lambda: self._apply_hex_preset('loose'))
        hex_preset_layout.addWidget(loose_btn)
        
        rotated_btn = QPushButton("30°")
        rotated_btn.setToolTip("30-degree rotated pattern")
        rotated_btn.setMaximumWidth(40)
        rotated_btn.clicked.connect(lambda: self._apply_hex_preset('rotated'))
        hex_preset_layout.addWidget(rotated_btn)
        
        hex_layout.addRow("", hex_preset_layout)
        
        right_layout.addWidget(self.hex_options_group)
        
        # Random Options (initially hidden)
        self.random_options_group = QGroupBox("Random Options")
        random_layout = QFormLayout(self.random_options_group)
        
        self.random_count = QSpinBox()
        self.random_count.setRange(1, 10000)
        self.random_count.setValue(100)
        random_layout.addRow("Stone Count:", self.random_count)
        
        self.random_seed = QSpinBox()
        self.random_seed.setRange(0, 99999)
        self.random_seed.setValue(42)
        random_layout.addRow("Random Seed:", self.random_seed)
        
        self.random_density = QDoubleSpinBox()
        self.random_density.setRange(0.1, 1.0)
        self.random_density.setValue(0.8)
        self.random_density.setSingleStep(0.1)
        random_layout.addRow("Density:", self.random_density)
        
        self.random_options_group.setVisible(False)
        right_layout.addWidget(self.random_options_group)

        # Stone Size (Single)
        size_group = QGroupBox("Primary Stone Size")
        size_layout = QFormLayout(size_group)
        
        self.primary_stone = QComboBox()
        for name in STONE_SIZES.keys():
            self.primary_stone.addItem(f"{name} ({STONE_SIZES[name]}mm)", name)
        self.primary_stone.setCurrentIndex(9)
        size_layout.addRow("Size:", self.primary_stone)
        
        quick_layout = QHBoxLayout()
        for s in ["SS6", "SS10", "SS16", "SS20"]:
            btn = QPushButton(s)
            btn.setMaximumWidth(50)
            btn.clicked.connect(lambda checked, sz=s: self._set_primary_size(sz))
            quick_layout.addWidget(btn)
        size_layout.addRow("Quick:", quick_layout)
        
        right_layout.addWidget(size_group)

        # Density & Spacing
        density_group = QGroupBox("Density & Spacing")
        density_layout = QFormLayout(density_group)
        
        self.density = QDoubleSpinBox()
        self.density.setRange(0.1, 1.0)
        self.density.setValue(0.85)
        self.density.setSingleStep(0.05)
        self.density.setDecimals(2)
        density_layout.addRow("Density:", self.density)
        
        self.spacing = QDoubleSpinBox()
        self.spacing.setRange(0, 20)
        self.spacing.setValue(0)
        self.spacing.setSuffix(" mm")
        density_layout.addRow("Gap:", self.spacing)
        
        self.min_gap = QDoubleSpinBox()
        self.min_gap.setRange(0, 10)
        self.min_gap.setValue(0.3)
        self.min_gap.setSuffix(" mm")
        density_layout.addRow("Min:", self.min_gap)
        
        self.gap_optimization = QCheckBox("Avoid overlaps")
        self.gap_optimization.setChecked(True)
        density_layout.addRow("", self.gap_optimization)

        self.use_element_size = QCheckBox("Use element size for spacing")
        self.use_element_size.setChecked(True)
        self.use_element_size.setToolTip("Auto-calculate spacing from selected element sizes (SS mapping)")
        density_layout.addRow("", self.use_element_size)

        self.remove_overlaps = QCheckBox("Remove overlaps (post)")
        self.remove_overlaps.setChecked(True)
        self.remove_overlaps.setToolTip("Final cleanup pass to remove overlaps/duplicates")
        density_layout.addRow("", self.remove_overlaps)
        
        right_layout.addWidget(density_group)

        # Rotation
        rotation_group = QGroupBox("Rotation")
        rotation_layout = QFormLayout(rotation_group)
        
        self.rotation = QDoubleSpinBox()
        self.rotation.setRange(-360, 360)
        self.rotation.setValue(0)
        self.rotation.setSuffix("°")
        rotation_layout.addRow("Angle:", self.rotation)
        
        self.random_rotation = QCheckBox("Random")
        rotation_layout.addRow("", self.random_rotation)
        
        right_layout.addWidget(rotation_group)

        # Action buttons
        action_group = QGroupBox("Actions")
        action_layout = QVBoxLayout(action_group)
        
        fill_btn = QPushButton("Fill")
        fill_btn.setIcon(self._load_icon("fill.png"))
        fill_btn.setIconSize(QSize(16, 16))
        fill_btn.setStyleSheet("background-color: #98971a; font-weight: bold; padding: 10px; font-size: 14px;")
        fill_btn.clicked.connect(self._fill_shape)
        action_layout.addWidget(fill_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.setStyleSheet("background-color: #cc241d; padding: 8px;")
        clear_btn.clicked.connect(self._clear_all)
        action_layout.addWidget(clear_btn)
        
        right_layout.addWidget(action_group)
        right_layout.addStretch()

        # Splitter with better resizing
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 400])
        splitter.setHandleWidth(6)
        splitter.setStyleSheet("QSplitter::handle { background-color: #3c3836; }")
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        main_layout.addWidget(splitter)

        icon_map = {
            "set container": "container.png",
            "set elements": "elements.png",
            "apply to selected": "apply.png",
            "fill": "fill.png",
            "clear all": "clear.png",
        }
        apply_button_icons(self, icon_map)

    def _set_primary_size(self, size_name):
        """Set the primary stone size."""
        index = self.primary_stone.findData(size_name)
        if index >= 0:
            self.primary_stone.setCurrentIndex(index)

    def _on_auto_calc_toggle(self, state):
        """Handle auto-calculate grid size toggle."""
        enabled = state != Qt.Checked
        self.hex_rows.setEnabled(enabled)
        self.hex_cols.setEnabled(enabled)

    def _apply_hex_preset(self, preset_name):
        """Apply hexagonal grid preset."""
        if preset_name == 'tight':
            self.hex_stagger.setChecked(True)
            self.hex_stagger_amount.setValue(50)
            self.hex_edge_margin.setValue(0.5)
            self.hex_horizontal_spacing.setValue(0)
            self.hex_vertical_spacing.setValue(0)
            self.hex_scale_factor.setValue(0.95)
            self.hex_rotation.setValue(0)
            self.density.setValue(0.95)
            self.min_gap.setValue(0.2)
            self.status_message.emit("Applied tight preset")
        elif preset_name == 'normal':
            self.hex_stagger.setChecked(True)
            self.hex_stagger_amount.setValue(50)
            self.hex_edge_margin.setValue(1.0)
            self.hex_horizontal_spacing.setValue(0)
            self.hex_vertical_spacing.setValue(0)
            self.hex_scale_factor.setValue(1.0)
            self.hex_rotation.setValue(0)
            self.density.setValue(0.85)
            self.min_gap.setValue(0.3)
            self.status_message.emit("Applied normal preset")
        elif preset_name == 'loose':
            self.hex_stagger.setChecked(True)
            self.hex_stagger_amount.setValue(50)
            self.hex_edge_margin.setValue(2.0)
            self.hex_horizontal_spacing.setValue(0.5)
            self.hex_vertical_spacing.setValue(0.5)
            self.hex_scale_factor.setValue(1.2)
            self.hex_rotation.setValue(0)
            self.density.setValue(0.7)
            self.min_gap.setValue(0.5)
            self.status_message.emit("Applied loose preset")
        elif preset_name == 'rotated':
            self.hex_stagger.setChecked(True)
            self.hex_stagger_amount.setValue(50)
            self.hex_rotation.setValue(30)
            self.status_message.emit("Applied 30° rotation")

    def _on_multi_size_toggle(self, state):
        """Handle multi-size enable toggle."""
        enabled = state == Qt.Checked
        self.multi_table.setEnabled(enabled)
        self.primary_stone.setEnabled(not enabled)
        
        if enabled:
            self._update_multi_distribution()
        else:
            self.distribution_label.setText("Using primary size only")

    def _on_pattern_changed(self, index):
        """Handle pattern selection change."""
        pattern = self.pattern_combo.currentData()
        if pattern == "hexagonal":
            self.hex_options_group.setVisible(True)
            self.random_options_group.setVisible(False)
        elif pattern == "random":
            self.hex_options_group.setVisible(False)
            self.random_options_group.setVisible(True)

    def _on_use_changed(self, row, state):
        """Handle size use checkbox change."""
        pct_spin = self.multi_table.cellWidget(row, 1)
        if pct_spin:
            pct_spin.setEnabled(state == Qt.Checked)
            if state == Qt.Checked and pct_spin.value() == 0:
                pct_spin.setValue(10)  # Default to 10%
        
        self._update_multi_distribution()

    def _on_pct_changed(self, row, value):
        """Handle percentage value change."""
        self._update_multi_distribution()

    def _update_multi_distribution(self):
        """Update the multi-size distribution."""
        sizes = []
        distributions = []
        
        for i in range(self.multi_table.rowCount()):
            chk = self.multi_table.cellWidget(i, 2)
            spin = self.multi_table.cellWidget(i, 1)
            item = self.multi_table.item(i, 0)
            
            if chk and chk.isChecked() and item:
                size_name = item.data(Qt.UserRole)
                pct = spin.value() if spin else 0
                if pct > 0:
                    sizes.append(size_name)
                    distributions.append(pct)
        
        self._multi_sizes = sizes
        self._multi_distributions = distributions
        
        if sizes:
            total = sum(distributions)
            if total > 0:
                dist_text = " + ".join([f"{s} ({int(d/total*100)}%)" for s, d in zip(sizes, distributions)])
                self.distribution_label.setText(f"Mix: {dist_text}")
            else:
                self.distribution_label.setText(f"Selected {len(sizes)} sizes (set percentages)")
        else:
            self.distribution_label.setText("No sizes selected")

    def _apply_size_preset(self, size_names):
        """Apply a preset size mix."""
        # First clear all
        for i in range(self.multi_table.rowCount()):
            chk = self.multi_table.cellWidget(i, 2)
            spin = self.multi_table.cellWidget(i, 1)
            if chk:
                chk.setChecked(False)
            if spin:
                spin.setValue(0)
                spin.setEnabled(False)
        
        # Enable multi-size mode
        self.enable_multi_size.setChecked(True)
        
        # Set selected sizes with equal distribution
        dist = 100 // len(size_names) if size_names else 0
        remainder = 100 % len(size_names) if size_names else 0
        
        for i in range(self.multi_table.rowCount()):
            item = self.multi_table.item(i, 0)
            if item and item.data(Qt.UserRole) in size_names:
                chk = self.multi_table.cellWidget(i, 2)
                spin = self.multi_table.cellWidget(i, 1)
                if chk:
                    chk.setChecked(True)
                if spin:
                    spin.setEnabled(True)
                    # First sizes get any remainder
                    idx = size_names.index(item.data(Qt.UserRole))
                    pct = dist + (1 if idx < remainder else 0)
                    spin.setValue(pct)
        
        self._update_multi_distribution()
        self.status_message.emit(f"Applied preset: {', '.join(size_names)}")

    def _equalize_distribution(self):
        """Equalize distribution among selected sizes."""
        selected_rows = []
        for i in range(self.multi_table.rowCount()):
            chk = self.multi_table.cellWidget(i, 2)
            if chk and chk.isChecked():
                selected_rows.append(i)
        
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select at least one stone size first.")
            return
        
        count = len(selected_rows)
        base_pct = 100 // count
        remainder = 100 % count
        
        for idx, row in enumerate(selected_rows):
            spin = self.multi_table.cellWidget(row, 1)
            if spin:
                # First sizes get any remainder
                pct = base_pct + (1 if idx < remainder else 0)
                spin.setValue(pct)
        
        self._update_multi_distribution()

    def _set_container(self):
        """Set the container shape with detailed information."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return
        
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "No Selection", "Select a shape in CorelDRAW.")
                return
            
            self._container_shape = selection.Item(1)
            name = getattr(self._container_shape, 'Name', 'Unnamed') or 'Unnamed'
            
            # Get comprehensive shape details
            width = 0
            height = 0
            pos_x = 0
            pos_y = 0
            shape_type = "Unknown"
            area = 0
            
            try:
                width = getattr(self._container_shape, 'SizeWidth', 0) or 0
                height = getattr(self._container_shape, 'SizeHeight', 0) or 0
                pos_x = getattr(self._container_shape, 'LeftX', 0) or getattr(self._container_shape, 'CenterX', 0) or 0
                pos_y = getattr(self._container_shape, 'TopY', 0) or getattr(self._container_shape, 'CenterY', 0) or 0
                
                # Try to determine shape type
                try:
                    type_val = getattr(self._container_shape, 'Type', None)
                    if type_val:
                        type_map = {
                            1: "Rectangle", 2: "Ellipse", 3: "Polygon", 
                            4: "Curve", 5: "Text", 6: "Bitmap", 7: "Group"
                        }
                        shape_type = type_map.get(type_val, f"Type {type_val}")
                except:
                    shape_type = "Shape"
                
                # Estimate area
                if width > 0 and height > 0:
                    if shape_type == "Ellipse":
                        import math
                        area = math.pi * (width / 2) * (height / 2)
                    else:
                        area = width * height
            except Exception as e:
                logger.debug(f"Error getting container details: {e}")
            
            # Update container labels
            if name and name != 'Unnamed':
                self.container_label.setText(name)
            else:
                self.container_label.setText(f"{shape_type}")
            self.container_label.setStyleSheet("color: #689d6a; font-weight: bold;")
            
            self.container_type_label.setText(f"Type: {shape_type}")
            
            if width > 0 and height > 0:
                self.container_size_label.setText(f"Size: {width:.1f} x {height:.1f} mm")
            else:
                self.container_size_label.setText("Size: -")
            
            if pos_x != 0 or pos_y != 0:
                self.container_pos_label.setText(f"Position: ({pos_x:.1f}, {pos_y:.1f})")
            else:
                self.container_pos_label.setText("Position: -")
            
            if area > 0:
                self.container_area_label.setText(f"Area: {area:.1f} mm²")
            else:
                self.container_area_label.setText("Area: -")
            
            # Store container bounds for later use
            self._container_bounds = {
                'x': pos_x,
                'y': pos_y,
                'width': width,
                'height': height,
                'area': area
            }
            
            self.status_message.emit(f"Container set: {shape_type} ({width:.1f}x{height:.1f}mm)")
            
        except Exception as e:
            logger.error(f"Container error: {e}")
            QMessageBox.critical(self, "Error", str(e))

    def _set_elements(self):
        """Set the element shapes (stones to use) with detailed information."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return
        
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "No Selection", "Select shapes in CorelDRAW.")
                return
            
            self._element_shapes = []
            total_width = 0
            total_height = 0
            shape_types = set()
            min_size = float('inf')
            max_size = 0
            
            for i in range(1, selection.Count + 1):
                shape = selection.Item(i)
                self._element_shapes.append(shape)
                
                # Get element details
                try:
                    w = getattr(shape, 'SizeWidth', 0) or 0
                    h = getattr(shape, 'SizeHeight', 0) or 0
                    total_width += w
                    total_height += h
                    
                    avg_dim = (w + h) / 2
                    if avg_dim > 0:
                        min_size = min(min_size, avg_dim)
                        max_size = max(max_size, avg_dim)
                    
                    # Get shape type
                    try:
                        type_val = getattr(shape, 'Type', None)
                        if type_val:
                            type_map = {
                                1: "Rect", 2: "Ellipse", 3: "Polygon", 
                                4: "Curve", 5: "Text", 6: "Bitmap", 7: "Group"
                            }
                            shape_types.add(type_map.get(type_val, "Other"))
                    except:
                        shape_types.add("Shape")
                except:
                    pass
            
            count = len(self._element_shapes)
            
            # Update elements label
            if count > 0 and total_width > 0:
                avg_width = total_width / count
                avg_height = total_height / count
                self.elements_label.setText(f"{count} element(s) ready")
            else:
                self.elements_label.setText(f"{count} element(s)")
            self.elements_label.setStyleSheet("color: #689d6a; font-weight: bold;")
            
            # Update detail labels
            self.element_count_label.setText(f"Count: {count}")
            
            if count > 0 and total_width > 0:
                avg_width = total_width / count
                avg_height = total_height / count
                if min_size != float('inf') and min_size != max_size:
                    self.element_size_label.setText(f"Size: {min_size:.1f}-{max_size:.1f} mm")
                else:
                    self.element_size_label.setText(f"Avg: {avg_width:.1f}x{avg_height:.1f} mm")
            else:
                self.element_size_label.setText("Avg Size: -")
            
            if shape_types:
                self.element_type_label.setText(f"Types: {', '.join(sorted(shape_types))}")
            else:
                self.element_type_label.setText("Types: -")
            
            # Store element info for later use
            self._element_info = {
                'count': count,
                'avg_width': total_width / count if count > 0 else 0,
                'avg_height': total_height / count if count > 0 else 0,
                'min_size': min_size if min_size != float('inf') else 0,
                'max_size': max_size,
                'types': list(shape_types)
            }
            
            self.status_message.emit(f"Set {count} elements ({', '.join(shape_types) if shape_types else 'unknown type'})")
            
        except Exception as e:
            logger.error(f"Elements error: {e}")
            QMessageBox.critical(self, "Error", str(e))

    def _apply_size_to_selected(self):
        """Apply selected stone size to selected objects in CorelDRAW."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return
        
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "No Selection", "Select stones in CorelDRAW to resize.")
                return
            
            new_size_name = self.change_to_size.currentData()
            new_diameter = STONE_SIZES.get(new_size_name, 3.0)
            
            resized = 0
            for i in range(1, selection.Count + 1):
                shape = selection.Item(i)
                try:
                    current_width = getattr(shape, 'SizeWidth', None) or 0
                    current_height = getattr(shape, 'SizeHeight', None) or 0
                    
                    if current_width > 0 and current_height > 0:
                        avg_current = (current_width + current_height) / 2
                        if avg_current > 0:
                            scale_factor = new_diameter / avg_current
                            shape.ScaleX = scale_factor
                            shape.ScaleY = scale_factor
                            resized += 1
                except Exception as e:
                    logger.error(f"Error scaling shape {i}: {e}")
            
            self.status_message.emit(f"Resized {resized} stones to {new_size_name}")
            QMessageBox.information(self, "Done", f"Resized {resized} stones to {new_size_name}")
            
        except Exception as e:
            logger.error(f"Error applying size: {e}")
            QMessageBox.critical(self, "Error", str(e))

    def _get_settings(self) -> RhinestoneSettings:
        """Get current settings including multi-size if enabled."""
        pattern_map = {
            "hexagonal": PatternType.HEXAGONAL,
            "random": PatternType.RANDOM,
        }
        
        # Determine stone sizes
        if self.enable_multi_size.isChecked() and self._multi_sizes:
            stone_size = self._multi_sizes[0]  # Primary
            stone_sizes = self._multi_sizes
            # Normalize distributions
            total = sum(self._multi_distributions)
            size_distribution = [d / total for d in self._multi_distributions] if total > 0 else None
        else:
            stone_size = self.primary_stone.currentData()
            stone_sizes = [stone_size]
            size_distribution = [1.0]
        
        return RhinestoneSettings(
            stone_size=stone_size,
            stone_sizes=stone_sizes,
            size_distribution=size_distribution,
            pattern=pattern_map.get(self.pattern_combo.currentData(), PatternType.HEXAGONAL),
            density=self.density.value(),
            spacing=self.spacing.value(),
            min_gap=self.min_gap.value(),
            gap_optimization=self.gap_optimization.isChecked(),
            rotation=self.rotation.value(),
            random_rotation=self.random_rotation.isChecked(),
            use_element_size=self.use_element_size.isChecked(),
            remove_overlaps=self.remove_overlaps.isChecked(),
        )

    def _get_shape_bounds(self, shape):
        """Get bounds from shape."""
        try:
            bb = shape.BoundingBox
            x = getattr(bb, 'x', 0) or getattr(bb, 'Left', 0) or 0
            y = getattr(bb, 'y', 0) or getattr(bb, 'Top', 0) or 0
            w = getattr(bb, 'width', 0) or getattr(bb, 'Right', 0) - x if x else 0
            h = getattr(bb, 'height', 0) or getattr(bb, 'Bottom', 0) - y if y else 0
            
            if w <= 0 or h <= 0:
                w = shape.SizeWidth or 100
                h = shape.SizeHeight or 100
                x = shape.CenterX - w/2
                y = shape.CenterY - h/2
            
            return type('obj', (object,), {'x': x, 'y': y, 'width': w, 'height': h})()
        except Exception as e:
            logger.error(f"Bounds error: {e}")
            return type('obj', (object,), {'x': 0, 'y': 0, 'width': 100, 'height': 100})()

    def _fill_shape(self):
        """Fill container with elements."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Connect to CorelDRAW first.")
            return
        
        if not self._container_shape:
            QMessageBox.warning(self, "No Container", "Set container first.")
            return
        
        if not self._element_shapes:
            QMessageBox.warning(self, "No Elements", "Set element shapes first.")
            return
        
        try:
            settings = self._get_settings()
            bounds = self._get_shape_bounds(self._container_shape)
            
            # Get hexagonal options with enhanced settings
            hex_options = {
                'rows': None if self.hex_auto_calc.isChecked() else self.hex_rows.value(),
                'cols': None if self.hex_auto_calc.isChecked() else self.hex_cols.value(),
                'stagger': self.hex_stagger.isChecked(),
                'stagger_amount': self.hex_stagger_amount.value(),
                'rotation': self.hex_rotation.value(),
                'offset_x': self.hex_offset_x.value(),
                'offset_y': self.hex_offset_y.value(),
                'edge_margin': self.hex_edge_margin.value(),
                'clip_to_container': self.hex_clip_to_container.isChecked(),
                'center_grid': self.hex_center_grid.isChecked(),
                'horizontal_spacing': self.hex_horizontal_spacing.value(),
                'vertical_spacing': self.hex_vertical_spacing.value(),
                'scale_factor': self.hex_scale_factor.value(),
            }
            
            # Calculate based on pattern
            if settings.pattern == PatternType.HEXAGONAL:
                self.engine.calculate_hexagonal_grid(
                    bounds, settings.stone_size, settings.density, 
                    settings.min_gap, settings, container_shape=self._container_shape,
                    element_shapes=self._element_shapes, **hex_options
                )
            elif settings.pattern == PatternType.RANDOM:
                random_options = {
                    'count': self.random_count.value(),
                    'seed': self.random_seed.value(),
                    'density': self.random_density.value(),
                }
                self.engine.calculate_random_scatter(
                    bounds, settings.stone_size, settings.density, 
                    settings.min_gap, settings,
                    element_shapes=self._element_shapes,
                    container_shape=self._container_shape,
                    **random_options
                )
            
            # Update stats
            stats = self.engine.get_statistics()
            self.stone_count_label.setText(str(stats['total_stones']))
            self.coverage_label.setText(f"{stats['coverage_area']:.1f} sq mm")
            
            self.status_message.emit(f"Calculated {self.engine.stone_count} stones")
            
            if self.engine.stone_count == 0:
                QMessageBox.warning(self, "No Stones", "No stones calculated. Try adjusting density.")
                return
            
            # Place stones inside container
            placed = self.engine.place_stones_in_coreldraw(settings, self._element_shapes, bounds)
            
            self.status_message.emit(f"Placed {len(placed)} stones inside container")
            QMessageBox.information(self, "Done", f"Placed {len(placed)} rhinestones inside container!")
            
        except Exception as e:
            logger.error(f"Fill error: {e}")
            QMessageBox.critical(self, "Error", str(e))

    def _clear_all(self):
        """Clear all."""
        self._container_shape = None
        self._element_shapes = []
        self._multi_sizes = []
        self._multi_distributions = []
        self._container_bounds = None
        self._element_info = None
        self.engine.clear()
        
        # Reset container labels
        self.container_label.setText("Not set")
        self.container_label.setStyleSheet("color: #cc241d;")
        self.container_type_label.setText("Type: -")
        self.container_size_label.setText("Size: -")
        self.container_pos_label.setText("Position: -")
        self.container_area_label.setText("Area: -")
        
        # Reset element labels
        self.elements_label.setText("Not set")
        self.elements_label.setStyleSheet("color: #cc241d;")
        self.element_count_label.setText("Count: -")
        self.element_size_label.setText("Avg Size: -")
        self.element_type_label.setText("Types: -")
        
        # Reset stats
        self.stone_count_label.setText("0")
        self.coverage_label.setText("0 sq mm")
        
        # Reset multi-size
        self.enable_multi_size.setChecked(False)
        for i in range(self.multi_table.rowCount()):
            chk = self.multi_table.cellWidget(i, 2)
            spin = self.multi_table.cellWidget(i, 1)
            if chk:
                chk.setChecked(False)
            if spin:
                spin.setValue(0)
                spin.setEnabled(False)
        self.distribution_label.setText("No sizes selected")
        self.status_message.emit("Cleared")

    def apply_preset(self, settings: Dict[str, Any]):
        """Apply preset."""
        if 'stone_size' in settings:
            self._set_primary_size(settings['stone_size'])
        if 'pattern' in settings:
            idx = self.pattern_combo.findData(settings['pattern'])
            if idx >= 0:
                self.pattern_combo.setCurrentIndex(idx)
        if 'density' in settings:
            self.density.setValue(settings['density'])
        if 'multi_sizes' in settings and settings['multi_sizes']:
            self._apply_size_preset(settings['multi_sizes'])

    def reset_to_defaults(self):
        """Reset defaults."""
        self._clear_all()
        self.pattern_combo.setCurrentIndex(0)
        self._set_primary_size("SS16")
        self.density.setValue(0.85)
        self.spacing.setValue(0)
        self.min_gap.setValue(0.3)
        self.gap_optimization.setChecked(True)
        self.use_element_size.setChecked(True)
        self.remove_overlaps.setChecked(True)
        self.rotation.setValue(0)
        self.random_rotation.setChecked(False)
        self.status_message.emit("Reset to defaults")
