"""
Object Manipulation Tools Widget
PyQt5 UI for advanced object manipulation.
"""

import logging
import math
import random
from typing import Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox,
    QTabWidget, QCheckBox, QMessageBox, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal

from ...core.corel_interface import corel
from ...ui.icon_utils import apply_button_icons

logger = logging.getLogger(__name__)


class ObjectToolsWidget(QWidget):
    """Widget for advanced object manipulation tools."""

    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        """Initialize the object tools widget."""
        super().__init__(parent)
        self._init_ui()
        logger.info("Object tools widget initialized.")

    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)

        array_tab = self._create_array_tab()
        tabs.addTab(array_tab, "Array")

        alignment_tab = self._create_alignment_tab()
        tabs.addTab(alignment_tab, "Alignment")

        transform_tab = self._create_transform_tab()
        tabs.addTab(transform_tab, "Transform")

        effects_tab = self._create_effects_tab()
        tabs.addTab(effects_tab, "Effects")

        main_layout.addWidget(tabs)

        icon_map = {
            "create array": "add.png",
            "apply": "apply.png",
            "union (weld)": "group.png",
            "subtract (trim)": "clear.png",
        }
        apply_button_icons(self, icon_map)

    def _create_array_tab(self) -> QWidget:
        """Create array duplication controls."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(350)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        type_group = QGroupBox("Array Type")
        type_layout = QFormLayout(type_group)

        self.array_type = QComboBox()
        self.array_type.addItem("Linear (Horizontal)", "linear_h")
        self.array_type.addItem("Linear (Vertical)", "linear_v")
        self.array_type.addItem("Grid", "grid")
        self.array_type.addItem("Circular", "circular")
        self.array_type.addItem("Along Path", "path")
        type_layout.addRow("Type:", self.array_type)

        layout.addWidget(type_group)

        params_group = QGroupBox("Parameters")
        params_layout = QFormLayout(params_group)

        self.array_columns = QSpinBox()
        self.array_columns.setRange(1, 100)
        self.array_columns.setValue(5)
        params_layout.addRow("Columns:", self.array_columns)

        self.array_rows = QSpinBox()
        self.array_rows.setRange(1, 100)
        self.array_rows.setValue(5)
        params_layout.addRow("Rows:", self.array_rows)

        self.array_spacing_x = QDoubleSpinBox()
        self.array_spacing_x.setRange(0, 10000)
        self.array_spacing_x.setValue(10)
        self.array_spacing_x.setSuffix(" mm")
        params_layout.addRow("Spacing X:", self.array_spacing_x)

        self.array_spacing_y = QDoubleSpinBox()
        self.array_spacing_y.setRange(0, 10000)
        self.array_spacing_y.setValue(10)
        self.array_spacing_y.setSuffix(" mm")
        params_layout.addRow("Spacing Y:", self.array_spacing_y)

        self.array_use_element_size = QCheckBox("Use element size for spacing")
        self.array_use_element_size.setChecked(True)
        params_layout.addRow("", self.array_use_element_size)

        self.array_remove_overlaps = QCheckBox("Remove overlaps (post)")
        self.array_remove_overlaps.setChecked(True)
        params_layout.addRow("", self.array_remove_overlaps)

        path_hint = QLabel("Path array: select base + path, uses Spacing X as step")
        path_hint.setStyleSheet("color: #aaa; font-size: 11px;")
        path_hint.setWordWrap(True)
        params_layout.addRow("Hint:", path_hint)

        self.circular_radius = QDoubleSpinBox()
        self.circular_radius.setRange(1, 10000)
        self.circular_radius.setValue(50)
        self.circular_radius.setSuffix(" mm")
        params_layout.addRow("Radius:", self.circular_radius)

        self.circular_count = QSpinBox()
        self.circular_count.setRange(2, 360)
        self.circular_count.setValue(8)
        params_layout.addRow("Count:", self.circular_count)

        self.rotate_copies = QCheckBox("Rotate copies")
        params_layout.addRow("", self.rotate_copies)

        layout.addWidget(params_group)

        create_array_btn = QPushButton("Create Array")
        create_array_btn.setStyleSheet("background-color: #98971a; font-weight: bold; padding: 8px;")
        create_array_btn.clicked.connect(self._create_array)
        layout.addWidget(create_array_btn)

        layout.addStretch()

        scroll.setWidget(widget)
        return scroll

    def _create_alignment_tab(self) -> QWidget:
        """Create alignment tools controls."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(350)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        align_group = QGroupBox("Align Objects")
        align_layout = QVBoxLayout(align_group)

        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("Horizontal:"))

        align_left_btn = QPushButton("Left")
        align_left_btn.clicked.connect(lambda: self._align("left"))
        h_layout.addWidget(align_left_btn)

        align_center_h_btn = QPushButton("Center")
        align_center_h_btn.clicked.connect(lambda: self._align("center_h"))
        h_layout.addWidget(align_center_h_btn)

        align_right_btn = QPushButton("Right")
        align_right_btn.clicked.connect(lambda: self._align("right"))
        h_layout.addWidget(align_right_btn)

        align_layout.addLayout(h_layout)

        v_layout = QHBoxLayout()
        v_layout.addWidget(QLabel("Vertical:"))

        align_top_btn = QPushButton("Top")
        align_top_btn.clicked.connect(lambda: self._align("top"))
        v_layout.addWidget(align_top_btn)

        align_center_v_btn = QPushButton("Center")
        align_center_v_btn.clicked.connect(lambda: self._align("center_v"))
        v_layout.addWidget(align_center_v_btn)

        align_bottom_btn = QPushButton("Bottom")
        align_bottom_btn.clicked.connect(lambda: self._align("bottom"))
        v_layout.addWidget(align_bottom_btn)

        align_layout.addLayout(v_layout)

        layout.addWidget(align_group)

        distribute_group = QGroupBox("Distribute Objects")
        distribute_layout = QFormLayout(distribute_group)

        self.distribute_spacing = QDoubleSpinBox()
        self.distribute_spacing.setRange(0, 1000)
        self.distribute_spacing.setValue(10)
        self.distribute_spacing.setSuffix(" mm")
        distribute_layout.addRow("Spacing:", self.distribute_spacing)

        self.distribute_use_element_size = QCheckBox("Use element size for spacing")
        self.distribute_use_element_size.setChecked(True)
        distribute_layout.addRow("", self.distribute_use_element_size)

        self.distribute_remove_overlaps = QCheckBox("Remove overlaps (post)")
        self.distribute_remove_overlaps.setChecked(True)
        distribute_layout.addRow("", self.distribute_remove_overlaps)

        self.distribute_use_container = QCheckBox("Use first selected as container")
        self.distribute_use_container.setChecked(False)
        distribute_layout.addRow("", self.distribute_use_container)

        self.distribute_seed = QSpinBox()
        self.distribute_seed.setRange(0, 99999)
        self.distribute_seed.setValue(42)
        distribute_layout.addRow("Random Seed:", self.distribute_seed)

        dist_h_btn = QPushButton("Distribute Horizontally")
        dist_h_btn.clicked.connect(lambda: self._distribute("horizontal"))
        distribute_layout.addRow(dist_h_btn)

        dist_v_btn = QPushButton("Distribute Vertically")
        dist_v_btn.clicked.connect(lambda: self._distribute("vertical"))
        distribute_layout.addRow(dist_v_btn)

        random_btn = QPushButton("Random Distribute")
        random_btn.clicked.connect(lambda: self._distribute("random"))
        distribute_layout.addRow(random_btn)

        layout.addWidget(distribute_group)

        page_group = QGroupBox("Align to Page")
        page_layout = QVBoxLayout(page_group)

        center_page_btn = QPushButton("Center on Page")
        center_page_btn.clicked.connect(self._center_on_page)
        page_layout.addWidget(center_page_btn)

        layout.addWidget(page_group)

        layout.addStretch()

        scroll.setWidget(widget)
        return scroll

    def _create_transform_tab(self) -> QWidget:
        """Create transform tools controls."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(350)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        scale_group = QGroupBox("Scale")
        scale_layout = QFormLayout(scale_group)

        self.scale_x = QDoubleSpinBox()
        self.scale_x.setRange(1, 1000)
        self.scale_x.setValue(100)
        self.scale_x.setSuffix("%")
        scale_layout.addRow("Scale X:", self.scale_x)

        self.scale_y = QDoubleSpinBox()
        self.scale_y.setRange(1, 1000)
        self.scale_y.setValue(100)
        self.scale_y.setSuffix("%")
        scale_layout.addRow("Scale Y:", self.scale_y)

        self.lock_aspect = QCheckBox("Lock aspect ratio")
        self.lock_aspect.setChecked(True)
        scale_layout.addRow("", self.lock_aspect)

        apply_scale_btn = QPushButton("Apply")
        apply_scale_btn.setStyleSheet("background-color: #4b6eaf; padding: 6px;")
        apply_scale_btn.clicked.connect(self._apply_scale)
        scale_layout.addRow(apply_scale_btn)

        layout.addWidget(scale_group)

        rotate_group = QGroupBox("Rotate")
        rotate_layout = QFormLayout(rotate_group)

        self.rotate_angle = QDoubleSpinBox()
        self.rotate_angle.setRange(-360, 360)
        self.rotate_angle.setValue(45)
        self.rotate_angle.setSuffix("°")
        rotate_layout.addRow("Angle:", self.rotate_angle)

        apply_rotate_btn = QPushButton("Apply")
        apply_rotate_btn.setStyleSheet("background-color: #4b6eaf; padding: 6px;")
        apply_rotate_btn.clicked.connect(self._apply_rotation)
        rotate_layout.addRow(apply_rotate_btn)

        layout.addWidget(rotate_group)

        skew_group = QGroupBox("Skew")
        skew_layout = QFormLayout(skew_group)

        self.skew_h = QDoubleSpinBox()
        self.skew_h.setRange(-89, 89)
        self.skew_h.setValue(0)
        self.skew_h.setSuffix("°")
        skew_layout.addRow("Horizontal:", self.skew_h)

        self.skew_v = QDoubleSpinBox()
        self.skew_v.setRange(-89, 89)
        self.skew_v.setValue(0)
        self.skew_v.setSuffix("°")
        skew_layout.addRow("Vertical:", self.skew_v)

        apply_skew_btn = QPushButton("Apply")
        apply_skew_btn.setStyleSheet("background-color: #4b6eaf; padding: 6px;")
        apply_skew_btn.clicked.connect(self._apply_skew)
        skew_layout.addRow(apply_skew_btn)

        layout.addWidget(skew_group)

        mirror_group = QGroupBox("Mirror/Flip")
        mirror_layout = QVBoxLayout(mirror_group)

        mirror_h_btn = QPushButton("Horizontal")
        mirror_h_btn.clicked.connect(lambda: self._mirror("horizontal"))
        mirror_layout.addWidget(mirror_h_btn)

        mirror_v_btn = QPushButton("Vertical")
        mirror_v_btn.clicked.connect(lambda: self._mirror("vertical"))
        mirror_layout.addWidget(mirror_v_btn)

        layout.addWidget(mirror_group)

        layout.addStretch()

        scroll.setWidget(widget)
        return scroll

    def _create_effects_tab(self) -> QWidget:
        """Create effects tools controls."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(350)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        offset_group = QGroupBox("Path Offset")
        offset_layout = QFormLayout(offset_group)

        self.offset_distance = QDoubleSpinBox()
        self.offset_distance.setRange(-1000, 1000)
        self.offset_distance.setValue(5)
        self.offset_distance.setSuffix(" mm")
        offset_layout.addRow("Distance:", self.offset_distance)

        self.offset_corners = QComboBox()
        self.offset_corners.addItem("Miter", "miter")
        self.offset_corners.addItem("Round", "round")
        self.offset_corners.addItem("Bevel", "bevel")
        offset_layout.addRow("Corners:", self.offset_corners)

        create_offset_btn = QPushButton("Create Offset")
        create_offset_btn.setStyleSheet("background-color: #4b6eaf; padding: 6px;")
        create_offset_btn.clicked.connect(self._create_offset)
        offset_layout.addRow(create_offset_btn)

        layout.addWidget(offset_group)

        blend_group = QGroupBox("Blend")
        blend_layout = QFormLayout(blend_group)

        self.blend_steps = QSpinBox()
        self.blend_steps.setRange(2, 100)
        self.blend_steps.setValue(10)
        blend_layout.addRow("Steps:", self.blend_steps)

        create_blend_btn = QPushButton("Create Blend")
        create_blend_btn.setStyleSheet("background-color: #4b6eaf; padding: 6px;")
        create_blend_btn.clicked.connect(self._create_blend)
        blend_layout.addRow(create_blend_btn)

        layout.addWidget(blend_group)

        boolean_group = QGroupBox("Boolean Operations")
        boolean_layout = QVBoxLayout(boolean_group)

        union_btn = QPushButton("Union (Weld)")
        union_btn.setStyleSheet("background-color: #689d6a; padding: 6px;")
        union_btn.clicked.connect(lambda: self._boolean("union"))
        boolean_layout.addWidget(union_btn)

        intersect_btn = QPushButton("Intersect")
        intersect_btn.setStyleSheet("background-color: #458588; padding: 6px;")
        intersect_btn.clicked.connect(lambda: self._boolean("intersect"))
        boolean_layout.addWidget(intersect_btn)

        subtract_btn = QPushButton("Subtract (Trim)")
        subtract_btn.setStyleSheet("background-color: #cc241d; padding: 6px;")
        subtract_btn.clicked.connect(lambda: self._boolean("subtract"))
        boolean_layout.addWidget(subtract_btn)

        layout.addWidget(boolean_group)

        layout.addStretch()

        scroll.setWidget(widget)
        return scroll

    def _create_array(self):
        """Create an array of the selected object."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return

        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "No Selection", "Select at least one object.")
                return

            array_type = self.array_type.currentData()
            if array_type not in ("linear_h", "linear_v", "grid", "circular", "path"):
                QMessageBox.information(
                    self, "Array",
                    f"{array_type} array is not implemented yet."
                )
                return

            base = selection.Item(1)
            bounds = corel.get_shape_bounds(base)
            base_w = bounds.width
            base_h = bounds.height

            spacing_x = self.array_spacing_x.value()
            spacing_y = self.array_spacing_y.value()
            if self.array_use_element_size.isChecked():
                spacing_x = base_w + spacing_x
                spacing_y = base_h + spacing_y

            cols = self.array_columns.value()
            rows = self.array_rows.value()
            if array_type == "linear_h":
                rows = 1
            elif array_type == "linear_v":
                cols = 1

            created = []

            with corel.optimization_mode(), corel.command_group("Create Array"):
                if array_type in ("linear_h", "linear_v", "grid"):
                    for r in range(rows):
                        for c in range(cols):
                            if r == 0 and c == 0:
                                continue
                            dx = c * spacing_x
                            dy = r * spacing_y
                            new_shape = corel.duplicate_shape(base, dx, dy)
                            created.append(new_shape)
                elif array_type == "circular":
                    count = self.circular_count.value()
                    radius = self.circular_radius.value()
                    center_x = bounds.center.x
                    center_y = bounds.center.y
                    for i in range(1, count):
                        angle = (2 * math.pi * i) / count
                        x = center_x + radius * math.cos(angle)
                        y = center_y + radius * math.sin(angle)
                        new_shape = corel.duplicate_shape(base)
                        new_shape.CenterX = x
                        new_shape.CenterY = y
                        if self.rotate_copies.isChecked():
                            new_shape.RotateEx(math.degrees(angle), x, y)
                        created.append(new_shape)
                elif array_type == "path":
                    if selection.Count < 2:
                        QMessageBox.warning(self, "Need Path", "Select a base object and a path.")
                        return
                    path_shape = selection.Item(2)
                    segments = corel.get_curve_path(path_shape)
                    total = corel.get_curve_total_length(segments)
                    if total <= 0:
                        QMessageBox.warning(self, "Invalid Path", "Selected path has no length.")
                        return
                    step = self.array_spacing_x.value()
                    if step <= 0:
                        count = max(2, self.array_columns.value())
                        step = total / (count - 1)
                    distance = 0.0
                    first = True
                    while distance <= total:
                        point, tangent = corel.get_point_on_curve(segments, distance)
                        if first:
                            first = False
                        else:
                            new_shape = corel.duplicate_shape(base)
                            new_shape.CenterX = point.x
                            new_shape.CenterY = point.y
                            if self.rotate_copies.isChecked():
                                new_shape.RotateEx(tangent, point.x, point.y)
                            created.append(new_shape)
                        distance += step

                if self.array_remove_overlaps.isChecked():
                    self._remove_overlaps([base] + created)

            self.status_message.emit(f"Created array: {len(created) + 1} objects")

        except Exception as e:
            logger.error(f"Array error: {e}")
            QMessageBox.critical(self, "Array Error", str(e))

    def _align(self, direction: str):
        """Align selected objects."""
        self.status_message.emit(f"Aligning objects: {direction}")

    def _distribute(self, direction: str):
        """Distribute selected objects."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return

        try:
            selection = corel.get_selection()
            if selection.Count < 2:
                QMessageBox.warning(self, "Need Selection", "Select two or more objects.")
                return

            shapes = [selection.Item(i + 1) for i in range(selection.Count)]
            use_size = self.distribute_use_element_size.isChecked()
            gap = self.distribute_spacing.value()

            with corel.optimization_mode(), corel.command_group("Distribute Objects"):
                if direction == "horizontal":
                    shapes.sort(key=lambda s: corel.get_shape_bounds(s).left)
                    prev = shapes[0]
                    prev_bounds = corel.get_shape_bounds(prev)
                    prev_center = prev_bounds.center
                    for shape in shapes[1:]:
                        bounds = corel.get_shape_bounds(shape)
                        if use_size:
                            new_left = prev_bounds.right + gap
                            dx = new_left - bounds.left
                            shape.Move(dx, 0)
                            prev_bounds = corel.get_shape_bounds(shape)
                        else:
                            new_center_x = prev_center.x + gap
                            dx = new_center_x - bounds.center.x
                            shape.Move(dx, 0)
                            prev_center = corel.get_shape_bounds(shape).center
                elif direction == "vertical":
                    shapes.sort(key=lambda s: corel.get_shape_bounds(s).bottom)
                    prev = shapes[0]
                    prev_bounds = corel.get_shape_bounds(prev)
                    prev_center = prev_bounds.center
                    for shape in shapes[1:]:
                        bounds = corel.get_shape_bounds(shape)
                        if use_size:
                            new_bottom = prev_bounds.top + gap
                            dy = new_bottom - bounds.bottom
                            shape.Move(0, dy)
                            prev_bounds = corel.get_shape_bounds(shape)
                        else:
                            new_center_y = prev_center.y + gap
                                dy = new_center_y - bounds.center.y
                                shape.Move(0, dy)
                                prev_center = corel.get_shape_bounds(shape).center
                elif direction == "random":
                    random.seed(self.distribute_seed.value())
                    container = None
                    move_shapes = shapes
                    if self.distribute_use_container.isChecked() and len(shapes) >= 2:
                        container = shapes[0]
                        move_shapes = shapes[1:]
                    if container:
                        cb = corel.get_shape_bounds(container)
                        min_x, min_y = cb.left, cb.bottom
                        max_x, max_y = cb.right, cb.top
                    else:
                        all_bounds = [corel.get_shape_bounds(s) for s in move_shapes]
                        min_x = min(b.left for b in all_bounds)
                        min_y = min(b.bottom for b in all_bounds)
                        max_x = max(b.right for b in all_bounds)
                        max_y = max(b.top for b in all_bounds)

                    placed = []
                    placed_bounds = []
                    for shape in move_shapes:
                        bounds = corel.get_shape_bounds(shape)
                        w = bounds.width
                        h = bounds.height
                        tries = 0
                        placed_ok = False
                        while tries < 500 and not placed_ok:
                            x = random.uniform(min_x + w / 2, max_x - w / 2)
                            y = random.uniform(min_y + h / 2, max_y - h / 2)
                            if container and not corel.is_point_in_shape(x, y, container):
                                tries += 1
                                continue
                            if use_size:
                                too_close = False
                                for ob in placed_bounds:
                                    min_dist_x = (w + ob.width) / 2 + gap
                                    min_dist_y = (h + ob.height) / 2 + gap
                                    if (abs(x - ob.center.x) < min_dist_x and
                                            abs(y - ob.center.y) < min_dist_y):
                                        too_close = True
                                        break
                                if too_close:
                                    tries += 1
                                    continue
                            shape.CenterX = x
                            shape.CenterY = y
                            placed_ok = True
                            placed.append(shape)
                            placed_bounds.append(corel.get_shape_bounds(shape))
                            break
                        if not placed_ok:
                            logger.warning("Random distribute: could not place shape without overlap.")

                if self.distribute_remove_overlaps.isChecked():
                    self._remove_overlaps(shapes)

            self.status_message.emit(f"Distributed objects: {direction}")

        except Exception as e:
            logger.error(f"Distribute error: {e}")
            QMessageBox.critical(self, "Distribute Error", str(e))

    def _remove_overlaps(self, shapes):
        """Remove overlapping shapes (keeps earlier shapes)."""
        if not shapes:
            return

        bounds_list = []
        max_w = 0.0
        max_h = 0.0
        for shape in shapes:
            bounds = corel.get_shape_bounds(shape)
            bounds_list.append(bounds)
            max_w = max(max_w, bounds.width)
            max_h = max(max_h, bounds.height)

        cell_size = max(max_w, max_h, 1.0)
        grid = {}

        def _cell_key(b):
            return (int(b.center.x // cell_size), int(b.center.y // cell_size))

        kept = []
        kept_bounds = []

        for idx, (shape, bounds) in enumerate(zip(shapes, bounds_list)):
            cx, cy = _cell_key(bounds)
            overlap = False
            for gx in (cx - 1, cx, cx + 1):
                for gy in (cy - 1, cy, cy + 1):
                    for k in grid.get((gx, gy), []):
                        other = kept_bounds[k]
                        if (abs(bounds.center.x - other.center.x) < (bounds.width + other.width) / 2 and
                                abs(bounds.center.y - other.center.y) < (bounds.height + other.height) / 2):
                            overlap = True
                            break
                    if overlap:
                        break
                if overlap:
                    break
            if overlap:
                try:
                    corel.delete_shape(shape)
                except Exception:
                    pass
                continue
            grid.setdefault((cx, cy), []).append(len(kept))
            kept.append(shape)
            kept_bounds.append(bounds)

    def _center_on_page(self):
        """Center selection on page."""
        self.status_message.emit("Centering on page")

    def _apply_scale(self):
        """Apply scale transformation."""
        self.status_message.emit(f"Scaling: {self.scale_x.value()}% x {self.scale_y.value()}%")

    def _apply_rotation(self):
        """Apply rotation transformation."""
        self.status_message.emit(f"Rotating: {self.rotate_angle.value()}°")

    def _apply_skew(self):
        """Apply skew transformation."""
        self.status_message.emit(f"Skewing: H={self.skew_h.value()}° V={self.skew_v.value()}°")

    def _mirror(self, direction: str):
        """Mirror/flip objects."""
        self.status_message.emit(f"Mirroring: {direction}")

    def _create_offset(self):
        """Create offset path."""
        self.status_message.emit(f"Creating offset path: {self.offset_distance.value()}mm")

    def _create_blend(self):
        """Create blend between shapes."""
        self.status_message.emit(f"Creating blend with {self.blend_steps.value()} steps")

    def _boolean(self, operation: str):
        """Perform boolean operation."""
        self.status_message.emit(f"Boolean operation: {operation}")

    def apply_preset(self, settings: Dict[str, Any]):
        """Apply preset settings."""
        self.status_message.emit("Object tools preset applied")

    def reset_to_defaults(self):
        """Reset to default values."""
        self.array_columns.setValue(5)
        self.array_rows.setValue(5)
        self.array_spacing_x.setValue(10)
        self.array_spacing_y.setValue(10)
        self.array_use_element_size.setChecked(True)
        self.array_remove_overlaps.setChecked(True)
        self.scale_x.setValue(100)
        self.scale_y.setValue(100)
        self.rotate_angle.setValue(45)
        self.distribute_use_element_size.setChecked(True)
        self.distribute_remove_overlaps.setChecked(True)
        self.distribute_use_container.setChecked(False)
        self.distribute_seed.setValue(42)
        self.status_message.emit("Object tools reset")
