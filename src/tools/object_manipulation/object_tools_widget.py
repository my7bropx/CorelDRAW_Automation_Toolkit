import logging
import math
import random
from typing import Any, Dict, List, Tuple

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from ...core.corel_interface import BoundingBox, Point, corel
from ...ui.widgets.tool_base import ToolBaseWidget
from ...ui.widgets.tool_components import InfoPanel, SettingsGroup, ToolHeader

logger = logging.getLogger(__name__)


class ObjectToolsWidget(ToolBaseWidget):
    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__("Object Tools", parent)
        self._build_ui()
        self._configure_interaction_help()
        self.add_stretch()

    def _build_ui(self):
        self.add_widget(ToolHeader("Object Tools", "Run array, alignment, transform, and boolean operations against the current CorelDRAW selection."))
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_array_tab(), "Array")
        self.tabs.addTab(self._build_alignment_tab(), "Alignment")
        self.tabs.addTab(self._build_transform_tab(), "Transform")
        self.tabs.addTab(self._build_effects_tab(), "Effects")
        self.tabs.currentChanged.connect(lambda index: self.lbl_mode.setText(self.tabs.tabText(index)))
        self.add_widget(self.tabs)
        self.set_context_panel(self._build_info_panel())
        self.refresh_selection_state(force=True)

    def _build_info_panel(self):
        self.lbl_mode = QLabel("Array")
        self.lbl_selection = QLabel("0 selected")
        self.lbl_status = QLabel("Idle")
        self.lbl_last_action = QLabel("-")
        self.lbl_options = QLabel("-")
        self.lbl_warning = QLabel("None")
        return InfoPanel(
            "Object Tools Info",
            sections=[
                ("Selection", [("Objects", self.lbl_selection), ("Mode", self.lbl_mode)]),
                ("Actions", [("Last action", self.lbl_last_action), ("Options", self.lbl_options)]),
                ("Status", [("State", self.lbl_status), ("Warning", self.lbl_warning)]),
            ],
        )

    def _set_status(self, text: str, options: str = "-", warning: str = "None"):
        self.lbl_status.setText(text)
        self.lbl_last_action.setText(text)
        self.lbl_options.setText(options)
        self.lbl_warning.setText(warning)
        self.status_message.emit(text)

    def refresh_selection_state(self, force: bool = False):
        if corel.is_connected:
            try:
                self.lbl_selection.setText(f"{corel.get_selection_count()} selected")
            except Exception:
                self.lbl_selection.setText("Unavailable")
        else:
            self.lbl_selection.setText("Not connected")
        self.lbl_mode.setText(self.tabs.tabText(self.tabs.currentIndex()))

    def on_selection_changed(self, count: int):
        self.lbl_selection.setText(f"{count} selected")

    def _ensure_corel(self) -> bool:
        if corel.is_connected:
            return True
        self._set_status("CorelDRAW is not connected.", warning="Connect to CorelDRAW first.")
        QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
        return False

    def _selected_shapes(self, minimum: int = 1) -> List[Any]:
        selection = corel.get_selection()
        if selection.Count < minimum:
            raise ValueError(f"Select at least {minimum} object(s) in CorelDRAW.")
        return [selection.Item(i) for i in range(1, selection.Count + 1)]

    def _bounds_of(self, shapes: List[Any]) -> BoundingBox:
        bounds = [corel.get_shape_bounds(shape) for shape in shapes]
        return BoundingBox(min(b.left for b in bounds), min(b.bottom for b in bounds), max(b.right for b in bounds), max(b.top for b in bounds))

    def _move_center(self, shape: Any, x: float, y: float):
        center = corel.get_shape_center(shape)
        corel.move_shape_by(shape, x - center.x, y - center.y)

    def _page_center(self) -> Point:
        page = corel.get_active_document().ActivePage
        if hasattr(page, "CenterX") and hasattr(page, "CenterY"):
            return Point(corel._corel_to_mm(page.CenterX), corel._corel_to_mm(page.CenterY))
        return Point(0.0, 0.0)

    def _sync_scale(self, checked: bool):
        self.scale_y.setEnabled(not checked)
        if checked:
            self.scale_y.setValue(self.scale_x.value())

    def _sync_scale_x(self, value: float):
        if self.lock_aspect.isChecked():
            self.scale_y.blockSignals(True)
            self.scale_y.setValue(value)
            self.scale_y.blockSignals(False)

    def _build_array_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        group = SettingsGroup("Array Type")
        self.array_type = QComboBox()
        self.array_type.addItem("Linear (Horizontal)", "linear_h")
        self.array_type.addItem("Linear (Vertical)", "linear_v")
        self.array_type.addItem("Grid", "grid")
        self.array_type.addItem("Circular", "circular")
        self.array_type.addItem("Along Path", "path")
        self.array_columns = QSpinBox(); self.array_columns.setRange(1, 100); self.array_columns.setValue(5)
        self.array_rows = QSpinBox(); self.array_rows.setRange(1, 100); self.array_rows.setValue(5)
        group.add_row("Type", self.array_type)
        group.add_row("Columns", self.array_columns)
        group.add_row("Rows", self.array_rows)
        layout.addWidget(group)
        params = SettingsGroup("Array Parameters")
        self.array_spacing_x = QDoubleSpinBox(); self.array_spacing_x.setRange(0, 10000); self.array_spacing_x.setValue(10); self.array_spacing_x.setSuffix(" mm")
        self.array_spacing_y = QDoubleSpinBox(); self.array_spacing_y.setRange(0, 10000); self.array_spacing_y.setValue(10); self.array_spacing_y.setSuffix(" mm")
        self.circular_radius = QDoubleSpinBox(); self.circular_radius.setRange(1, 10000); self.circular_radius.setValue(50); self.circular_radius.setSuffix(" mm")
        self.circular_count = QSpinBox(); self.circular_count.setRange(2, 360); self.circular_count.setValue(8)
        self.array_use_element_size = QCheckBox("Use element size for spacing"); self.array_use_element_size.setChecked(True)
        self.array_remove_overlaps = QCheckBox("Remove overlaps after duplication"); self.array_remove_overlaps.setChecked(True)
        self.rotate_copies = QCheckBox("Rotate copies")
        params.add_row("Spacing X", self.array_spacing_x)
        params.add_row("Spacing Y", self.array_spacing_y)
        params.add_full_row(self.array_use_element_size)
        params.add_full_row(self.array_remove_overlaps)
        params.add_row("Circular radius", self.circular_radius)
        params.add_row("Circular count", self.circular_count)
        params.add_full_row(self.rotate_copies)
        layout.addWidget(params)
        button = QPushButton("Create Array")
        button.setProperty("accent", True)
        button.clicked.connect(self._create_array)
        layout.addWidget(button)
        layout.addStretch()
        return page

    def _build_alignment_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        align = SettingsGroup("Align Objects")
        row = QWidget()
        row_layout = QHBoxLayout(row); row_layout.setContentsMargins(0, 0, 0, 0); row_layout.setSpacing(8)
        for label, value in [("Left", "left"), ("Center", "center_h"), ("Right", "right"), ("Top", "top"), ("Middle", "center_v"), ("Bottom", "bottom")]:
            btn = QPushButton(label); btn.clicked.connect(lambda checked, v=value: self._align(v)); row_layout.addWidget(btn)
        align.add_full_row(row)
        layout.addWidget(align)
        dist = SettingsGroup("Distribute")
        self.distribute_spacing = QDoubleSpinBox(); self.distribute_spacing.setRange(0, 1000); self.distribute_spacing.setValue(10); self.distribute_spacing.setSuffix(" mm")
        self.distribute_use_element_size = QCheckBox("Use element size for spacing"); self.distribute_use_element_size.setChecked(True)
        self.distribute_remove_overlaps = QCheckBox("Remove overlaps"); self.distribute_remove_overlaps.setChecked(True)
        self.distribute_use_container = QCheckBox("Use first selected object as container")
        self.distribute_seed = QSpinBox(); self.distribute_seed.setRange(0, 99999); self.distribute_seed.setValue(42)
        dist.add_row("Spacing", self.distribute_spacing)
        dist.add_full_row(self.distribute_use_element_size)
        dist.add_full_row(self.distribute_remove_overlaps)
        dist.add_full_row(self.distribute_use_container)
        dist.add_row("Random seed", self.distribute_seed)
        dist_row = QWidget()
        dist_row_layout = QHBoxLayout(dist_row); dist_row_layout.setContentsMargins(0, 0, 0, 0); dist_row_layout.setSpacing(8)
        for label, value in [("Horizontal", "horizontal"), ("Vertical", "vertical"), ("Random", "random")]:
            btn = QPushButton(label); btn.clicked.connect(lambda checked, v=value: self._distribute(v)); dist_row_layout.addWidget(btn)
        dist.add_full_row(dist_row)
        layout.addWidget(dist)
        center = QPushButton("Center on Page")
        center.clicked.connect(self._center_on_page)
        layout.addWidget(center)
        layout.addStretch()
        return page

    def _build_transform_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        scale = SettingsGroup("Scale")
        self.scale_x = QDoubleSpinBox(); self.scale_x.setRange(1, 1000); self.scale_x.setValue(100); self.scale_x.setSuffix("%")
        self.scale_y = QDoubleSpinBox(); self.scale_y.setRange(1, 1000); self.scale_y.setValue(100); self.scale_y.setSuffix("%")
        self.lock_aspect = QCheckBox("Lock aspect ratio"); self.lock_aspect.setChecked(True)
        self.lock_aspect.toggled.connect(self._sync_scale)
        self.scale_x.valueChanged.connect(self._sync_scale_x)
        scale.add_row("Scale X", self.scale_x); scale.add_row("Scale Y", self.scale_y); scale.add_full_row(self.lock_aspect)
        scale_btn = QPushButton("Apply Scale"); scale_btn.clicked.connect(self._apply_scale); scale.add_full_row(scale_btn)
        layout.addWidget(scale)
        rotate = SettingsGroup("Rotate / Mirror")
        self.rotate_angle = QDoubleSpinBox(); self.rotate_angle.setRange(-360, 360); self.rotate_angle.setValue(45); self.rotate_angle.setSuffix(" deg")
        rotate.add_row("Angle", self.rotate_angle)
        rotate_btn = QPushButton("Apply Rotation"); rotate_btn.clicked.connect(self._apply_rotation); rotate.add_full_row(rotate_btn)
        mirror_row = QWidget()
        mirror_layout = QHBoxLayout(mirror_row); mirror_layout.setContentsMargins(0, 0, 0, 0); mirror_layout.setSpacing(8)
        btn = QPushButton("Mirror Horizontal"); btn.clicked.connect(lambda: self._mirror("horizontal")); mirror_layout.addWidget(btn)
        btn = QPushButton("Mirror Vertical"); btn.clicked.connect(lambda: self._mirror("vertical")); mirror_layout.addWidget(btn)
        rotate.add_full_row(mirror_row)
        layout.addWidget(rotate)
        skew = SettingsGroup("Skew")
        self.skew_h = QDoubleSpinBox(); self.skew_h.setRange(-89, 89); self.skew_h.setValue(0); self.skew_h.setSuffix(" deg")
        self.skew_v = QDoubleSpinBox(); self.skew_v.setRange(-89, 89); self.skew_v.setValue(0); self.skew_v.setSuffix(" deg")
        skew.add_row("Horizontal", self.skew_h); skew.add_row("Vertical", self.skew_v)
        skew_btn = QPushButton("Apply Skew"); skew_btn.clicked.connect(self._apply_skew); skew.add_full_row(skew_btn)
        layout.addWidget(skew)
        layout.addStretch()
        return page

    def _build_effects_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        offset = SettingsGroup("Path Offset")
        self.offset_distance = QDoubleSpinBox(); self.offset_distance.setRange(-1000, 1000); self.offset_distance.setValue(5); self.offset_distance.setSuffix(" mm")
        self.offset_corners = QComboBox()
        self.offset_corners.addItem("Miter", "miter"); self.offset_corners.addItem("Round", "round"); self.offset_corners.addItem("Bevel", "bevel")
        offset.add_row("Distance", self.offset_distance); offset.add_row("Corners", self.offset_corners)
        offset_btn = QPushButton("Create Offset"); offset_btn.clicked.connect(self._create_offset); offset.add_full_row(offset_btn)
        layout.addWidget(offset)
        blend = SettingsGroup("Blend")
        self.blend_steps = QSpinBox(); self.blend_steps.setRange(2, 100); self.blend_steps.setValue(10)
        blend.add_row("Steps", self.blend_steps)
        blend_btn = QPushButton("Create Blend"); blend_btn.clicked.connect(self._create_blend); blend.add_full_row(blend_btn)
        layout.addWidget(blend)
        boolean = SettingsGroup("Boolean Operations")
        b_row = QWidget()
        b_layout = QHBoxLayout(b_row); b_layout.setContentsMargins(0, 0, 0, 0); b_layout.setSpacing(8)
        for label, value in [("Union", "union"), ("Intersect", "intersect"), ("Subtract", "subtract")]:
            btn = QPushButton(label); btn.clicked.connect(lambda checked, v=value: self._boolean(v)); b_layout.addWidget(btn)
        boolean.add_full_row(b_row)
        layout.addWidget(boolean)
        layout.addStretch()
        return page

    def _configure_interaction_help(self):
        self.enable_safe_panel_interactions()
        self.apply_default_button_tooltips()
        self.apply_tooltips([
            (self.array_type, "Choose the duplication pattern for the current selection. Different modes change how copies are positioned."),
            (self.array_columns, "Number of columns used by grid and horizontal array layouts."),
            (self.array_rows, "Number of rows used by grid and vertical array layouts."),
            (self.array_spacing_x, "Horizontal spacing between copies. Larger values spread output wider."),
            (self.array_spacing_y, "Vertical spacing between copies. Larger values spread output taller."),
            (self.circular_radius, "Radius used for circular arrays. This changes how far copies sit from the original center."),
            (self.circular_count, "Number of copies around the circle. Higher values create denser circular arrays."),
            (self.array_use_element_size, "Include the object size in spacing calculations so duplicates do not start on top of each other."),
            (self.array_remove_overlaps, "Delete overlapping duplicates after creation for safer and cleaner output."),
            (self.rotate_copies, "Rotate circular array copies to follow their angular position."),
            (self.distribute_spacing, "Gap target used when distributing objects."),
            (self.distribute_use_element_size, "Account for object size while distributing so visible gaps stay more consistent."),
            (self.distribute_remove_overlaps, "Clean up overlapping objects after distribution."),
            (self.distribute_use_container, "Treat the first selected object as the container or boundary for distribution decisions."),
            (self.distribute_seed, "Random seed used for repeatable random distribution results."),
            (self.scale_x, "Horizontal scale percentage applied to the current selection."),
            (self.scale_y, "Vertical scale percentage applied to the current selection."),
            (self.lock_aspect, "Keep X and Y scaling linked so the object shape stays proportional."),
            (self.rotate_angle, "Rotation angle in degrees for the selected objects."),
            (self.skew_h, "Horizontal skew angle. Strong values create more distortion."),
            (self.skew_v, "Vertical skew angle. Strong values create more distortion."),
            (self.offset_distance, "Distance used to create path offsets. Positive and negative values expand or contract the path."),
            (self.offset_corners, "Corner style used when building the offset path."),
            (self.blend_steps, "Number of intermediate shapes created in the blend. Higher values create smoother transitions but more output objects."),
        ])

    def _remove_overlaps(self, shapes: List[Any]):
        if not shapes:
            return
        bounds = [corel.get_shape_bounds(shape) for shape in shapes]
        cell = max(max(b.width for b in bounds), max(b.height for b in bounds), 1.0)
        grid: Dict[Tuple[int, int], List[int]] = {}
        kept: List[BoundingBox] = []
        removed = 0
        for shape, box in zip(shapes, bounds):
            key = (int(box.center.x // cell), int(box.center.y // cell))
            overlap = False
            for gx in (key[0] - 1, key[0], key[0] + 1):
                for gy in (key[1] - 1, key[1], key[1] + 1):
                    for idx in grid.get((gx, gy), []):
                        other = kept[idx]
                        if abs(box.center.x - other.center.x) < ((box.width + other.width) / 2.0) and abs(box.center.y - other.center.y) < ((box.height + other.height) / 2.0):
                            overlap = True
                            break
                    if overlap:
                        break
                if overlap:
                    break
            if overlap:
                removed += 1
                try:
                    corel.delete_shape(shape)
                except Exception:
                    pass
                continue
            grid.setdefault(key, []).append(len(kept))
            kept.append(box)
        if removed:
            self.lbl_warning.setText(f"Removed {removed} overlapping duplicate(s).")

    def _create_array(self):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(1)
            base = shapes[0]
            bounds = corel.get_shape_bounds(base)
            center = bounds.center
            sx = self.array_spacing_x.value()
            sy = self.array_spacing_y.value()
            if self.array_use_element_size.isChecked():
                sx += bounds.width
                sy += bounds.height
            created: List[Any] = []
            mode = self.array_type.currentData()
            with corel.optimization_mode(), corel.command_group("Object Tools Array"):
                if mode in ("linear_h", "linear_v", "grid"):
                    cols = self.array_columns.value()
                    rows = self.array_rows.value()
                    if mode == "linear_h":
                        rows = 1
                    if mode == "linear_v":
                        cols = 1
                    for row in range(rows):
                        for col in range(cols):
                            if row == 0 and col == 0:
                                continue
                            created.append(corel.duplicate_shape(base, col * sx, row * sy))
                elif mode == "circular":
                    for index in range(1, self.circular_count.value()):
                        angle = (2.0 * math.pi * index) / self.circular_count.value()
                        x = center.x + (self.circular_radius.value() * math.cos(angle))
                        y = center.y + (self.circular_radius.value() * math.sin(angle))
                        shape = corel.duplicate_shape(base)
                        self._move_center(shape, x, y)
                        if self.rotate_copies.isChecked():
                            corel.rotate_shape(shape, math.degrees(angle), x, y)
                        created.append(shape)
                else:
                    if len(shapes) < 2:
                        raise ValueError("Select a base object first and a path second.")
                    segments = corel.get_curve_path(shapes[1])
                    total = corel.get_curve_total_length(segments)
                    step = max(0.01, sx)
                    distance = step
                    while distance <= total + 1e-9:
                        point, tangent = corel.get_point_on_curve(segments, distance)
                        shape = corel.duplicate_shape(base)
                        self._move_center(shape, point.x, point.y)
                        if self.rotate_copies.isChecked():
                            corel.rotate_shape(shape, tangent, point.x, point.y)
                        created.append(shape)
                        distance += step
                if self.array_remove_overlaps.isChecked() and created:
                    self._remove_overlaps(created)
            self._set_status(f"Created array with {len(created)} duplicate(s).", options=f"{mode}; spacing=({sx:.2f}, {sy:.2f}) mm")
        except Exception as exc:
            logger.error("Object tools array error: %s", exc)
            self._set_status("Array failed.", warning=str(exc))
            QMessageBox.critical(self, "Array Error", str(exc))

    def _align(self, direction: str):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(2)
            outer = self._bounds_of(shapes)
            with corel.optimization_mode(), corel.command_group(f"Object Tools Align {direction}"):
                for shape in shapes:
                    bounds = corel.get_shape_bounds(shape)
                    dx = 0.0
                    dy = 0.0
                    if direction == "left":
                        dx = outer.left - bounds.left
                    elif direction == "center_h":
                        dx = outer.center.x - bounds.center.x
                    elif direction == "right":
                        dx = outer.right - bounds.right
                    elif direction == "top":
                        dy = outer.top - bounds.top
                    elif direction == "center_v":
                        dy = outer.center.y - bounds.center.y
                    elif direction == "bottom":
                        dy = outer.bottom - bounds.bottom
                    corel.move_shape_by(shape, dx, dy)
            self._set_status(f"Aligned {len(shapes)} object(s): {direction}.", options=f"mode={direction}")
        except Exception as exc:
            logger.error("Object tools align error: %s", exc)
            self._set_status("Align failed.", warning=str(exc))
            QMessageBox.critical(self, "Align Error", str(exc))

    def _distribute(self, direction: str):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(2 if direction == "random" else 3)
            container = None
            targets = shapes
            if self.distribute_use_container.isChecked():
                container = shapes[0]
                targets = shapes[1:]
                if not targets:
                    raise ValueError("Select a container first, then objects to distribute.")
            spacing = self.distribute_spacing.value()
            use_size = self.distribute_use_element_size.isChecked()
            with corel.optimization_mode(), corel.command_group(f"Object Tools Distribute {direction}"):
                if direction in ("horizontal", "vertical"):
                    axis = "x" if direction == "horizontal" else "y"
                    targets = sorted(targets, key=lambda shape: corel.get_shape_bounds(shape).center.x if axis == "x" else corel.get_shape_bounds(shape).center.y)
                    bounds = corel.get_shape_bounds(container) if container is not None else self._bounds_of(targets)
                    cursor = bounds.left if axis == "x" else bounds.bottom
                    if container is not None:
                        total = 0.0
                        for index, shape in enumerate(targets):
                            box = corel.get_shape_bounds(shape)
                            total += (box.width if axis == "x" else box.height) if use_size else 0.0
                            if index < len(targets) - 1:
                                total += spacing
                        cursor += max(0.0, ((bounds.width if axis == "x" else bounds.height) - total) / 2.0)
                    for shape in targets:
                        box = corel.get_shape_bounds(shape)
                        half = ((box.width if axis == "x" else box.height) / 2.0) if use_size else 0.0
                        target_center = cursor + half
                        if axis == "x":
                            corel.move_shape_by(shape, target_center - box.center.x, 0.0)
                        else:
                            corel.move_shape_by(shape, 0.0, target_center - box.center.y)
                        cursor = target_center + half + spacing
                else:
                    random.seed(self.distribute_seed.value())
                    outer = corel.get_shape_bounds(container) if container is not None else self._bounds_of(targets)
                    placed: List[BoundingBox] = []
                    warning = "None"
                    for shape in targets:
                        box = corel.get_shape_bounds(shape)
                        success = False
                        for _ in range(300):
                            x = random.uniform(outer.left + box.width / 2.0, outer.right - box.width / 2.0)
                            y = random.uniform(outer.bottom + box.height / 2.0, outer.top - box.height / 2.0)
                            if container is not None and not corel.is_point_inside_shape(container, Point(x, y)):
                                continue
                            candidate = BoundingBox(x - box.width / 2.0, y - box.height / 2.0, x + box.width / 2.0, y + box.height / 2.0)
                            if self.distribute_remove_overlaps.isChecked():
                                bad = any(abs(candidate.center.x - other.center.x) < ((candidate.width + other.width) / 2.0) and abs(candidate.center.y - other.center.y) < ((candidate.height + other.height) / 2.0) for other in placed)
                                if bad:
                                    continue
                            self._move_center(shape, x, y)
                            placed.append(candidate)
                            success = True
                            break
                        if not success:
                            warning = "Some objects could not be placed without overlap."
                    self.lbl_warning.setText(warning)
                if self.distribute_remove_overlaps.isChecked() and direction != "random":
                    self._remove_overlaps(targets)
            self._set_status(f"Distributed {len(targets)} object(s): {direction}.", options=f"spacing={spacing:.2f} mm", warning=self.lbl_warning.text())
        except Exception as exc:
            logger.error("Object tools distribute error: %s", exc)
            self._set_status("Distribute failed.", warning=str(exc))
            QMessageBox.critical(self, "Distribute Error", str(exc))

    def _center_on_page(self):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(1)
            outer = self._bounds_of(shapes)
            page_center = self._page_center()
            dx = page_center.x - outer.center.x
            dy = page_center.y - outer.center.y
            with corel.optimization_mode(), corel.command_group("Object Tools Center On Page"):
                for shape in shapes:
                    corel.move_shape_by(shape, dx, dy)
            self._set_status(f"Centered {len(shapes)} object(s) on the page.", options="page center")
        except Exception as exc:
            logger.error("Object tools center error: %s", exc)
            self._set_status("Center on page failed.", warning=str(exc))
            QMessageBox.critical(self, "Center Error", str(exc))

    def _apply_scale(self):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(1)
            sx = self.scale_x.value() / 100.0
            sy = sx if self.lock_aspect.isChecked() else self.scale_y.value() / 100.0
            with corel.optimization_mode(), corel.command_group("Object Tools Scale"):
                for shape in shapes:
                    corel.scale_shape(shape, sx, sy)
            self._set_status(f"Scaled {len(shapes)} object(s).", options=f"{sx * 100:.1f}% x {sy * 100:.1f}%")
        except Exception as exc:
            logger.error("Object tools scale error: %s", exc)
            self._set_status("Scale failed.", warning=str(exc))
            QMessageBox.critical(self, "Scale Error", str(exc))

    def _apply_rotation(self):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(1)
            angle = self.rotate_angle.value()
            with corel.optimization_mode(), corel.command_group("Object Tools Rotate"):
                for shape in shapes:
                    corel.rotate_shape(shape, angle)
            self._set_status(f"Rotated {len(shapes)} object(s) by {angle:.1f} deg.", options=f"angle={angle:.1f}")
        except Exception as exc:
            logger.error("Object tools rotation error: %s", exc)
            self._set_status("Rotation failed.", warning=str(exc))
            QMessageBox.critical(self, "Rotation Error", str(exc))

    def _mirror(self, direction: str):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(1)
            with corel.optimization_mode(), corel.command_group(f"Object Tools Mirror {direction}"):
                for shape in shapes:
                    try:
                        shape.Stretch(-1.0, 1.0) if direction == "horizontal" else shape.Stretch(1.0, -1.0)
                    except Exception:
                        shape.Flip(0 if direction == "horizontal" else 1)
            self._set_status(f"Mirrored {len(shapes)} object(s): {direction}.", options=direction)
        except Exception as exc:
            logger.error("Object tools mirror error: %s", exc)
            self._set_status("Mirror failed.", warning=str(exc))
            QMessageBox.critical(self, "Mirror Error", str(exc))

    def _apply_skew(self):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(1)
            h = self.skew_h.value()
            v = self.skew_v.value()
            with corel.optimization_mode(), corel.command_group("Object Tools Skew"):
                for shape in shapes:
                    try:
                        shape.Skew(h, v)
                    except Exception:
                        center = corel.get_shape_center(shape)
                        shape.SkewEx(h, v, corel._mm_to_corel(center.x), corel._mm_to_corel(center.y))
            self._set_status(f"Skewed {len(shapes)} object(s).", options=f"H={h:.1f} deg, V={v:.1f} deg")
        except Exception as exc:
            logger.error("Object tools skew error: %s", exc)
            self._set_status("Skew failed.", warning=str(exc))
            QMessageBox.critical(self, "Skew Error", str(exc))

    def _create_offset(self):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(1)
            distance = self.offset_distance.value()
            if abs(distance) < 1e-9:
                raise ValueError("Offset distance must be non-zero.")
            direction = 0 if distance >= 0 else 1
            corners = {"miter": 0, "round": 1, "bevel": 2}.get(self.offset_corners.currentData(), 0)
            created = 0
            with corel.optimization_mode(), corel.command_group("Object Tools Offset"):
                for shape in shapes:
                    try:
                        result = shape.CreateContour(direction, corel._mm_to_corel(abs(distance)), 1, 0, corners)
                    except TypeError:
                        result = shape.CreateContour(direction, corel._mm_to_corel(abs(distance)), 1)
                    if result is not None:
                        created += 1
            self._set_status(f"Created {created} offset contour(s).", options=f"distance={distance:.2f} mm")
        except Exception as exc:
            logger.error("Object tools offset error: %s", exc)
            self._set_status("Offset failed.", warning=str(exc))
            QMessageBox.critical(self, "Offset Error", str(exc))

    def _create_blend(self):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(2)
            if len(shapes) != 2:
                raise ValueError("Select exactly two objects to create a blend.")
            steps = self.blend_steps.value()
            with corel.optimization_mode(), corel.command_group("Object Tools Blend"):
                try:
                    shapes[0].CreateBlend(shapes[1], steps)
                except TypeError:
                    shapes[0].CreateBlend(shapes[1], steps, 0)
            self._set_status(f"Created blend with {steps} steps.", options=f"steps={steps}")
        except Exception as exc:
            logger.error("Object tools blend error: %s", exc)
            self._set_status("Blend failed.", warning=str(exc))
            QMessageBox.critical(self, "Blend Error", str(exc))

    def _boolean(self, operation: str):
        if not self._ensure_corel():
            return
        try:
            shapes = self._selected_shapes(2)
            result = shapes[0]
            with corel.optimization_mode(), corel.command_group(f"Object Tools {operation.title()}"):
                for other in shapes[1:]:
                    if operation == "union":
                        result = result.Weld(other, False, False)
                    elif operation == "intersect":
                        result = result.Intersect(other, False, False)
                    else:
                        result = result.Trim(other, False, False)
            self._set_status(f"Boolean operation completed: {operation}.", options=operation)
        except Exception as exc:
            logger.error("Object tools boolean error: %s", exc)
            self._set_status("Boolean operation failed.", warning=str(exc))
            QMessageBox.critical(self, "Boolean Error", str(exc))

    def apply_preset(self, settings: Dict[str, Any]):
        for name, widget in [
            ("array_columns", self.array_columns), ("array_rows", self.array_rows),
            ("array_spacing_x", self.array_spacing_x), ("array_spacing_y", self.array_spacing_y),
            ("circular_radius", self.circular_radius), ("circular_count", self.circular_count),
            ("distribute_spacing", self.distribute_spacing), ("distribute_seed", self.distribute_seed),
            ("scale_x", self.scale_x), ("scale_y", self.scale_y), ("rotate_angle", self.rotate_angle),
            ("skew_h", self.skew_h), ("skew_v", self.skew_v), ("offset_distance", self.offset_distance),
            ("blend_steps", self.blend_steps),
        ]:
            if name in settings:
                widget.setValue(settings[name])
        for name, widget in [
            ("array_use_element_size", self.array_use_element_size),
            ("array_remove_overlaps", self.array_remove_overlaps),
            ("rotate_copies", self.rotate_copies),
            ("distribute_use_element_size", self.distribute_use_element_size),
            ("distribute_remove_overlaps", self.distribute_remove_overlaps),
            ("distribute_use_container", self.distribute_use_container),
            ("lock_aspect", self.lock_aspect),
        ]:
            if name in settings:
                widget.setChecked(bool(settings[name]))
        self._set_status("Object tools preset applied.")

    def reset_to_defaults(self):
        self.array_columns.setValue(5); self.array_rows.setValue(5)
        self.array_spacing_x.setValue(10); self.array_spacing_y.setValue(10)
        self.array_use_element_size.setChecked(True); self.array_remove_overlaps.setChecked(True)
        self.circular_radius.setValue(50); self.circular_count.setValue(8); self.rotate_copies.setChecked(False)
        self.distribute_spacing.setValue(10); self.distribute_use_element_size.setChecked(True)
        self.distribute_remove_overlaps.setChecked(True); self.distribute_use_container.setChecked(False); self.distribute_seed.setValue(42)
        self.scale_x.setValue(100); self.scale_y.setValue(100); self.lock_aspect.setChecked(True)
        self.rotate_angle.setValue(45); self.skew_h.setValue(0); self.skew_v.setValue(0)
        self.offset_distance.setValue(5); self.blend_steps.setValue(10)
        self._set_status("Object tools reset.", options="defaults")
