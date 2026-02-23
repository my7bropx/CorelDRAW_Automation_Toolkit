"""
Batch Processor Widget
PyQt5 UI for batch processing automation.
"""

import logging
import shutil
from pathlib import Path
from typing import Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QSpinBox, QComboBox, QCheckBox,
    QListWidget, QProgressBar, QFileDialog, QLineEdit,
    QMessageBox, QListWidgetItem, QPlainTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, pyqtSlot

from ...config import config
from ...core.corel_interface import corel
from ...core.preset_manager import preset_manager
from ...tools.curve_filler.curve_filler_engine import CurveFillerEngine, FillSettings, SpacingMode, AngleMode, PatternMode
from ...ui.icon_utils import apply_button_icons

logger = logging.getLogger(__name__)


class BatchProcessorWidget(QWidget):
    """Widget for batch processing operations."""

    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        """Initialize the batch processor widget."""
        super().__init__(parent)
        self._file_list = []
        self._init_ui()
        logger.info("Batch processor widget initialized.")

    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # File selection
        files_group = QGroupBox("File Queue")
        files_layout = QVBoxLayout(files_group)
        files_layout.setContentsMargins(8, 8, 8, 8)

        self.file_list_widget = QListWidget()
        self.file_list_widget.setMinimumHeight(150)
        files_layout.addWidget(self.file_list_widget)

        file_btn_layout = QHBoxLayout()

        add_files_btn = QPushButton("Add Files")
        add_files_btn.setStyleSheet("padding: 6px;")
        add_files_btn.clicked.connect(self._add_files)
        file_btn_layout.addWidget(add_files_btn)

        add_folder_btn = QPushButton("Add Folder")
        add_folder_btn.setStyleSheet("padding: 6px;")
        add_folder_btn.clicked.connect(self._add_folder)
        file_btn_layout.addWidget(add_folder_btn)

        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_selected)
        file_btn_layout.addWidget(remove_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("background-color: #cc241d; padding: 6px;")
        clear_btn.clicked.connect(self._clear_list)
        file_btn_layout.addWidget(clear_btn)

        files_layout.addLayout(file_btn_layout)
        main_layout.addWidget(files_group)

        # Operations panel
        operations_layout = QHBoxLayout()

        # Left - Operation settings
        operation_group = QGroupBox("Batch Operations")
        operation_layout = QVBoxLayout(operation_group)

        # Curve fill operation
        curve_fill_check = QCheckBox("Apply Curve Fill Preset")
        operation_layout.addWidget(curve_fill_check)

        self.curve_fill_preset = QComboBox()
        self.curve_fill_preset.addItem("Select preset...")
        self.curve_fill_preset.addItem("Basic Grid Fill")
        self.curve_fill_preset.addItem("Path Following")
        self.curve_fill_preset.addItem("Decorative Scatter")
        operation_layout.addWidget(self.curve_fill_preset)

        self.curve_container_name = QLineEdit()
        self.curve_container_name.setPlaceholderText("Container name (optional)")
        operation_layout.addWidget(self.curve_container_name)

        self.curve_elements_name = QLineEdit()
        self.curve_elements_name.setPlaceholderText("Elements name (optional)")
        operation_layout.addWidget(self.curve_elements_name)

        self.curve_layer_name = QLineEdit()
        self.curve_layer_name.setPlaceholderText("Layer name (optional)")
        operation_layout.addWidget(self.curve_layer_name)

        hint = QLabel("Auto-select by name/layer if no valid selection")
        hint.setStyleSheet("color: #aaa; font-size: 11px;")
        operation_layout.addWidget(hint)

        # Export operation
        export_check = QCheckBox("Export to Format")
        operation_layout.addWidget(export_check)

        self.export_format = QComboBox()
        self.export_format.addItem("PDF", "pdf")
        self.export_format.addItem("SVG", "svg")
        self.export_format.addItem("AI", "ai")
        self.export_format.addItem("EPS", "eps")
        self.export_format.addItem("PNG", "png")
        self.export_format.addItem("JPEG", "jpg")
        operation_layout.addWidget(self.export_format)

        # Resize operation
        resize_check = QCheckBox("Resize Documents")
        operation_layout.addWidget(resize_check)

        resize_layout = QHBoxLayout()
        self.resize_width = QSpinBox()
        self.resize_width.setRange(100, 10000)
        self.resize_width.setValue(1000)
        self.resize_width.setSuffix(" mm")
        resize_layout.addWidget(QLabel("W:"))
        resize_layout.addWidget(self.resize_width)

        self.resize_height = QSpinBox()
        self.resize_height.setRange(100, 10000)
        self.resize_height.setValue(1000)
        self.resize_height.setSuffix(" mm")
        resize_layout.addWidget(QLabel("H:"))
        resize_layout.addWidget(self.resize_height)
        operation_layout.addLayout(resize_layout)

        # Color conversion
        color_check = QCheckBox("Convert Colors")
        operation_layout.addWidget(color_check)

        self.color_mode = QComboBox()
        self.color_mode.addItem("CMYK", "cmyk")
        self.color_mode.addItem("RGB", "rgb")
        self.color_mode.addItem("Grayscale", "grayscale")
        operation_layout.addWidget(self.color_mode)

        operation_layout.addStretch()
        operations_layout.addWidget(operation_group)

        # Right - Output settings
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout(output_group)

        self.output_folder = QLineEdit()
        self.output_folder.setPlaceholderText("Same as source")
        output_layout.addRow("Output Folder:", self.output_folder)

        browse_output_btn = QPushButton("Browse...")
        browse_output_btn.clicked.connect(self._browse_output)
        output_layout.addRow("", browse_output_btn)

        self.naming_pattern = QComboBox()
        self.naming_pattern.addItem("Original name", "original")
        self.naming_pattern.addItem("Original + suffix", "suffix")
        self.naming_pattern.addItem("Prefix + original", "prefix")
        self.naming_pattern.addItem("Sequential numbering", "sequential")
        output_layout.addRow("Naming:", self.naming_pattern)

        self.suffix_text = QLineEdit("_processed")
        output_layout.addRow("Suffix/Prefix:", self.suffix_text)

        self.overwrite_check = QCheckBox("Overwrite existing files")
        output_layout.addRow("", self.overwrite_check)

        self.create_backup = QCheckBox("Create backup before processing")
        self.create_backup.setChecked(config.batch_processor.auto_backup)
        output_layout.addRow("", self.create_backup)

        operations_layout.addWidget(output_group)
        main_layout.addLayout(operations_layout)

        # Watch folder settings
        watch_group = QGroupBox("Watch Folder (Auto-processing)")
        watch_layout = QFormLayout(watch_group)

        self.watch_enabled = QCheckBox("Enable watch folder")
        self.watch_enabled.setChecked(config.batch_processor.watch_folder_enabled)
        watch_layout.addRow("", self.watch_enabled)

        self.watch_folder = QLineEdit(config.batch_processor.watch_folder_path)
        watch_layout.addRow("Folder:", self.watch_folder)

        browse_watch_btn = QPushButton("Browse...")
        browse_watch_btn.clicked.connect(self._browse_watch_folder)
        watch_layout.addRow("", browse_watch_btn)

        main_layout.addWidget(watch_group)

        # Progress and controls
        progress_group = QGroupBox("Processing")
        progress_layout = QVBoxLayout(progress_group)

        self.batch_progress = QProgressBar()
        self.batch_progress.setValue(0)
        progress_layout.addWidget(self.batch_progress)

        self.current_file_label = QLabel("Ready to process")
        progress_layout.addWidget(self.current_file_label)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(120)
        progress_layout.addWidget(self.log_output)

        control_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Batch")
        self.start_btn.setStyleSheet("background-color: #98971a; font-weight: bold; padding: 10px;")
        self.start_btn.clicked.connect(self._start_processing)
        control_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_processing)
        control_layout.addWidget(self.stop_btn)

        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self._clear_log)
        control_layout.addWidget(clear_log_btn)

        progress_layout.addLayout(control_layout)
        main_layout.addWidget(progress_group)

        icon_map = {
            "add files": "add.png",
            "add folder": "add.png",
            "remove": "remove.png",
            "clear": "clear.png",
            "browse...": "action.png",
            "start batch": "apply.png",
            "stop": "clear.png",
            "clear log": "clear.png",
        }
        apply_button_icons(self, icon_map)

    def _add_files(self):
        """Add files to the batch queue."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add Files",
            str(Path.home()),
            "CorelDRAW Files (*.cdr);;All Files (*)"
        )

        for file_path in files:
            if file_path not in self._file_list:
                self._file_list.append(file_path)
                self.file_list_widget.addItem(Path(file_path).name)

        self.status_message.emit(f"Added {len(files)} file(s) to queue")

    def _add_folder(self):
        """Add all CDR files from a folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Add Folder",
            str(Path.home())
        )

        if folder:
            folder_path = Path(folder)
            cdr_files = list(folder_path.glob("*.cdr"))

            for file_path in cdr_files:
                str_path = str(file_path)
                if str_path not in self._file_list:
                    self._file_list.append(str_path)
                    self.file_list_widget.addItem(file_path.name)

            self.status_message.emit(f"Added {len(cdr_files)} file(s) from folder")

    def _remove_selected(self):
        """Remove selected files from queue."""
        selected_items = self.file_list_widget.selectedItems()
        for item in selected_items:
            row = self.file_list_widget.row(item)
            self.file_list_widget.takeItem(row)
            if row < len(self._file_list):
                del self._file_list[row]

        self.status_message.emit(f"Removed {len(selected_items)} file(s)")

    def _clear_list(self):
        """Clear all files from queue."""
        self.file_list_widget.clear()
        self._file_list.clear()
        self.status_message.emit("File queue cleared")

    def _browse_output(self):
        """Browse for output folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder",
            str(Path.home())
        )
        if folder:
            self.output_folder.setText(folder)

    def _browse_watch_folder(self):
        """Browse for watch folder."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Watch Folder",
            str(Path.home())
        )
        if folder:
            self.watch_folder.setText(folder)

    def _start_processing(self):
        """Start batch processing."""
        if not self._file_list:
            QMessageBox.warning(self, "No Files", "Please add files to the queue first.")
            return

        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        total = len(self._file_list)
        self.batch_progress.setMaximum(total)

        curve_fill_enabled = False
        export_enabled = False
        resize_enabled = False
        color_enabled = False

        # Extract enabled operations
        for child in self.findChildren(QCheckBox):
            if child.text() == "Apply Curve Fill Preset":
                curve_fill_enabled = child.isChecked()
            elif child.text() == "Export to Format":
                export_enabled = child.isChecked()
            elif child.text() == "Resize Documents":
                resize_enabled = child.isChecked()
            elif child.text() == "Convert Colors":
                color_enabled = child.isChecked()

        preset_name = self.curve_fill_preset.currentText()
        preset_settings = None
        if curve_fill_enabled and preset_name and preset_name != "Select preset...":
            matches = preset_manager.search_presets(preset_name, tool="curve_filler")
            if matches:
                preset_data = preset_manager.load_preset(matches[0]["id"])
                if preset_data:
                    preset_settings = preset_data.get("settings", {})

        output_dir = self.output_folder.text().strip() or None

        for i, file_path in enumerate(self._file_list):
            self.current_file_label.setText(f"Processing: {Path(file_path).name}")
            self.batch_progress.setValue(i + 1)
            self.progress_updated.emit(i + 1, total)
            self._log(f"Processing: {file_path}")

            try:
                # Backup if enabled
                if self.create_backup.isChecked():
                    backup_path = f"{file_path}.bak"
                    shutil.copy2(file_path, backup_path)

                # Open document
                doc = corel.app.OpenDocument(file_path)

                # Resize document
                if resize_enabled:
                    try:
                        doc.ActivePage.SizeWidth = self.resize_width.value()
                        doc.ActivePage.SizeHeight = self.resize_height.value()
                    except Exception as e:
                        logger.warning(f"Resize failed: {e}")

                # Convert colors (best-effort)
                if color_enabled:
                    try:
                        mode = self.color_mode.currentData()
                        if mode == "cmyk":
                            doc.ConvertToCMYK()
                        elif mode == "rgb":
                            doc.ConvertToRGB()
                        elif mode == "grayscale":
                            doc.ConvertToGrayscale()
                    except Exception as e:
                        logger.warning(f"Color conversion failed: {e}")

                # Apply curve fill preset if possible
                if curve_fill_enabled and preset_settings:
                    try:
                        engine = CurveFillerEngine()
                        container, elements = self._resolve_curve_fill_targets(doc)
                        if container and elements and elements.Count > 0:
                            engine.set_container(container)
                            engine.set_fill_elements(elements)
                            settings = FillSettings(
                                spacing_mode=SpacingMode(preset_settings.get("spacing_mode", "fixed")),
                                spacing_value=preset_settings.get("spacing_value", 10.0),
                                spacing_percentage=preset_settings.get("spacing_percentage", 100.0),
                                spacing_min=preset_settings.get("spacing_min", 5.0),
                                spacing_max=preset_settings.get("spacing_max", 20.0),
                                start_padding=preset_settings.get("start_padding", 0.0),
                                end_padding=preset_settings.get("end_padding", 0.0),
                                angle_mode=AngleMode(preset_settings.get("angle_mode", "follow_curve")),
                                fixed_angle=preset_settings.get("fixed_angle", 0.0),
                                angle_min=preset_settings.get("angle_min", 0.0),
                                angle_max=preset_settings.get("angle_max", 360.0),
                                angle_increment=preset_settings.get("angle_increment", 15.0),
                                element_count=preset_settings.get("element_count", 0),
                                offset_from_curve=preset_settings.get("offset_from_curve", 0.0),
                                collision_detection=preset_settings.get("collision_detection", False),
                                smart_corners=preset_settings.get("smart_corners", True),
                                distribute_evenly=preset_settings.get("distribute_evenly", False),
                                scale_mode=preset_settings.get("scale_mode", "uniform"),
                                scale_factor=preset_settings.get("scale_factor", 1.0),
                                scale_start=preset_settings.get("scale_start", 0.5),
                                scale_end=preset_settings.get("scale_end", 1.5),
                                pattern_mode=PatternMode(preset_settings.get("pattern_mode", "single")),
                            )
                            engine.execute_fill(settings=settings)
                        else:
                            msg = "Curve fill skipped: no valid container/elements."
                            self._log(msg)
                            QMessageBox.warning(self, "Curve Fill Skipped", msg)
                    except Exception as e:
                        self._log(f"Curve fill failed: {e}")

                # Export or save
                if export_enabled:
                    fmt = self.export_format.currentData()
                    src_path = Path(file_path)
                    out_dir = Path(output_dir) if output_dir else src_path.parent
                    out_dir.mkdir(parents=True, exist_ok=True)
                    base = src_path.stem
                    if self.naming_pattern.currentData() == "suffix":
                        name = f"{base}{self.suffix_text.text()}"
                    elif self.naming_pattern.currentData() == "prefix":
                        name = f"{self.suffix_text.text()}{base}"
                    elif self.naming_pattern.currentData() == "sequential":
                        name = f"{base}_{i+1:03d}"
                    else:
                        name = base
                    out_path = out_dir / f"{name}.{fmt}"
                    try:
                        doc.SaveAs(str(out_path))
                    except Exception as e:
                        logger.warning(f"Export failed: {e}")
                else:
                    try:
                        doc.Save()
                    except Exception:
                        pass

                try:
                    doc.Close()
                except Exception:
                    pass

                logger.info(f"Processed: {file_path}")
                self._log(f"Done: {file_path}")

            except Exception as e:
                logger.error(f"Processing error ({file_path}): {e}")
                self._log(f"Error: {file_path} -> {e}")

        self.current_file_label.setText(f"Completed {total} file(s)")
        self.status_message.emit(f"Batch processing completed: {total} files")

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _stop_processing(self):
        """Stop batch processing."""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.current_file_label.setText("Processing stopped")
        self.status_message.emit("Batch processing stopped")
        self._log("Batch processing stopped")

    def _log(self, message: str):
        """Append a message to the batch log output."""
        self.log_output.appendPlainText(message)

    def _clear_log(self):
        """Clear batch log output."""
        self.log_output.clear()

    def _resolve_curve_fill_targets(self, doc):
        """Resolve container and elements for curve fill."""
        # 1) Prefer current selection if valid
        try:
            selection = corel.get_selection()
            if selection.Count >= 2:
                container = selection.Item(1)
                if hasattr(container, "Curve") and container.Curve is not None:
                    elements = corel.app.CreateShapeRange()
                    for idx in range(2, selection.Count + 1):
                        elements.Add(selection.Item(idx))
                    return container, elements
        except Exception:
            pass

        # 2) Auto-select by name/layer
        container_name = self.curve_container_name.text().strip().lower()
        elements_name = self.curve_elements_name.text().strip().lower()
        layer_name = self.curve_layer_name.text().strip().lower()

        if not (container_name or elements_name or layer_name):
            return None, None

        shapes = []
        try:
            page = doc.ActivePage
            if page:
                for i in range(1, page.Shapes.Count + 1):
                    shapes.append(page.Shapes.Item(i))
        except Exception:
            pass

        container = None
        elements = corel.app.CreateShapeRange()

        for shape in shapes:
            try:
                name = (getattr(shape, "Name", "") or "").lower()
                layer = getattr(shape, "Layer", None)
                layer_match = False
                if layer and layer_name:
                    layer_match = (getattr(layer, "Name", "") or "").lower() == layer_name

                if not container:
                    if container_name and container_name in name:
                        if hasattr(shape, "Curve") and shape.Curve is not None:
                            container = shape
                    elif layer_match and hasattr(shape, "Curve") and shape.Curve is not None:
                        container = shape

                if elements_name:
                    if elements_name in name:
                        elements.Add(shape)
                elif layer_match and not (hasattr(shape, "Curve") and shape.Curve is not None):
                    elements.Add(shape)
            except Exception:
                continue

        return container, elements

    def apply_preset(self, settings: Dict[str, Any]):
        """Apply preset settings."""
        self.status_message.emit("Batch processor preset applied")

    def reset_to_defaults(self):
        """Reset to default values."""
        self.file_list_widget.clear()
        self._file_list.clear()
        self.output_folder.clear()
        self.naming_pattern.setCurrentIndex(0)
        self.suffix_text.setText("_processed")
        self.overwrite_check.setChecked(False)
        self.create_backup.setChecked(config.batch_processor.auto_backup)
        self.batch_progress.setValue(0)
        self.current_file_label.setText("Ready to process")
        self.curve_container_name.clear()
        self.curve_elements_name.clear()
        self.curve_layer_name.clear()
        self.log_output.clear()
        self.status_message.emit("Batch processor reset")
