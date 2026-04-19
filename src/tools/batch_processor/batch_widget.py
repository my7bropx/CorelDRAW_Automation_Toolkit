import logging
import shutil
from pathlib import Path
from typing import Any, Dict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...config import config
from ...core.corel_interface import corel
from ...core.preset_manager import preset_manager
from ...tools.curve_filler.curve_filler_engine import AngleMode, CurveFillerEngine, FillSettings, PatternMode, SpacingMode
from ...ui.widgets.collapsible_section import CollapsibleSection
from ...ui.widgets.tool_base import ToolBaseWidget
from ...ui.widgets.tool_components import ActionBar, InfoPanel, SettingsGroup, ToolHeader

logger = logging.getLogger(__name__)


class BatchProcessorWidget(ToolBaseWidget):
    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__("Batch Processor", parent)
        self._file_list = []
        self._build_ui()
        self._configure_interaction_help()
        self.add_stretch()
        logger.info("Batch processor widget initialized.")

    def _build_ui(self):
        self.add_widget(
            ToolHeader(
                "Batch Processor",
                "Run repetitive CorelDRAW operations across queued files with export, conversion, and optional curve-fill automation.",
            )
        )
        self.add_widget(self._build_queue_section())
        self.add_widget(self._build_operations_section())
        self.add_widget(self._build_output_section())
        self.add_widget(self._build_watch_section())
        self.add_widget(self._build_processing_section())
        self.set_context_panel(self._build_info_panel())

    def _build_queue_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.file_list_widget = QListWidget()
        self.file_list_widget.setMinimumHeight(180)
        layout.addWidget(self.file_list_widget)

        row = QHBoxLayout()
        self.add_files_btn = QPushButton("Add Files")
        add_files_btn = self.add_files_btn
        add_files_btn.clicked.connect(self._add_files)
        row.addWidget(add_files_btn)

        self.add_folder_btn = QPushButton("Add Folder")
        add_folder_btn = self.add_folder_btn
        add_folder_btn.clicked.connect(self._add_folder)
        row.addWidget(add_folder_btn)

        self.remove_btn = QPushButton("Remove")
        remove_btn = self.remove_btn
        remove_btn.clicked.connect(self._remove_selected)
        row.addWidget(remove_btn)

        self.clear_queue_btn = QPushButton("Clear Queue")
        clear_btn = self.clear_queue_btn
        clear_btn.clicked.connect(self._clear_list)
        row.addWidget(clear_btn)

        layout.addLayout(row)
        return CollapsibleSection("File Queue", content, True)

    def _build_operations_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)

        curve_group = SettingsGroup("Curve Fill Operation")
        self.chk_curve_fill = QCheckBox("Apply Curve Fill Preset")
        curve_group.add_full_row(self.chk_curve_fill)

        self.curve_fill_preset = QComboBox()
        self.curve_fill_preset.addItem("Select preset...")
        self.curve_fill_preset.addItem("Basic Grid Fill")
        self.curve_fill_preset.addItem("Path Following")
        self.curve_fill_preset.addItem("Decorative Scatter")
        curve_group.add_row("Preset", self.curve_fill_preset)

        self.curve_container_name = QLineEdit()
        curve_group.add_row("Container name", self.curve_container_name)
        self.curve_elements_name = QLineEdit()
        curve_group.add_row("Elements name", self.curve_elements_name)
        self.curve_layer_name = QLineEdit()
        curve_group.add_row("Layer name", self.curve_layer_name)
        layout.addWidget(curve_group)

        doc_group = SettingsGroup("Document Operations")
        self.chk_export = QCheckBox("Export processed files")
        doc_group.add_full_row(self.chk_export)
        self.export_format = QComboBox()
        self.export_format.addItem("PDF", "pdf")
        self.export_format.addItem("SVG", "svg")
        self.export_format.addItem("AI", "ai")
        self.export_format.addItem("EPS", "eps")
        self.export_format.addItem("PNG", "png")
        self.export_format.addItem("JPEG", "jpg")
        doc_group.add_row("Format", self.export_format)

        self.chk_resize = QCheckBox("Resize page")
        doc_group.add_full_row(self.chk_resize)
        self.resize_width = QSpinBox()
        self.resize_width.setRange(100, 10000)
        self.resize_width.setValue(1000)
        self.resize_width.setSuffix(" mm")
        doc_group.add_row("Page width", self.resize_width)

        self.resize_height = QSpinBox()
        self.resize_height.setRange(100, 10000)
        self.resize_height.setValue(1000)
        self.resize_height.setSuffix(" mm")
        doc_group.add_row("Page height", self.resize_height)

        self.chk_color = QCheckBox("Convert color mode")
        doc_group.add_full_row(self.chk_color)
        self.color_mode = QComboBox()
        self.color_mode.addItem("CMYK", "cmyk")
        self.color_mode.addItem("RGB", "rgb")
        self.color_mode.addItem("Grayscale", "grayscale")
        doc_group.add_row("Color mode", self.color_mode)
        layout.addWidget(doc_group)

        return CollapsibleSection("Operations", content, True)

    def _build_output_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)

        group = SettingsGroup("Output Rules")
        self.output_folder = QLineEdit()
        group.add_row("Output folder", self.output_folder)

        self.browse_output_btn = QPushButton("Browse...")
        browse_output_btn = self.browse_output_btn
        browse_output_btn.clicked.connect(self._browse_output)
        group.add_full_row(browse_output_btn)

        self.naming_pattern = QComboBox()
        self.naming_pattern.addItem("Original name", "original")
        self.naming_pattern.addItem("Original + suffix", "suffix")
        self.naming_pattern.addItem("Prefix + original", "prefix")
        self.naming_pattern.addItem("Sequential numbering", "sequential")
        group.add_row("Naming", self.naming_pattern)

        self.suffix_text = QLineEdit("_processed")
        group.add_row("Suffix / Prefix", self.suffix_text)

        self.overwrite_check = QCheckBox("Overwrite existing files")
        group.add_full_row(self.overwrite_check)

        self.create_backup = QCheckBox("Create backup before processing")
        self.create_backup.setChecked(config.batch_processor.auto_backup)
        group.add_full_row(self.create_backup)
        layout.addWidget(group)

        return CollapsibleSection("Output Settings", content, True)

    def _build_watch_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)

        group = SettingsGroup("Watch Folder")
        self.watch_enabled = QCheckBox("Enable watch folder")
        self.watch_enabled.setChecked(config.batch_processor.watch_folder_enabled)
        group.add_full_row(self.watch_enabled)

        self.watch_folder = QLineEdit(config.batch_processor.watch_folder_path)
        group.add_row("Folder", self.watch_folder)

        self.browse_watch_btn = QPushButton("Browse...")
        browse_watch_btn = self.browse_watch_btn
        browse_watch_btn.clicked.connect(self._browse_watch_folder)
        group.add_full_row(browse_watch_btn)
        layout.addWidget(group)

        return CollapsibleSection("Watch Folder", content, False)

    def _build_processing_section(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.batch_progress = QProgressBar()
        self.batch_progress.setValue(0)
        layout.addWidget(self.batch_progress)

        self.current_file_label = QLabel("Ready to process")
        layout.addWidget(self.current_file_label)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(150)
        layout.addWidget(self.log_output)

        actions = ActionBar("Validate", "Start Batch", "Clear Log", "Stop")
        actions.preview_btn.clicked.connect(self._validate_queue)
        actions.apply_btn.clicked.connect(self._start_processing)
        actions.clear_btn.clicked.connect(self._clear_log)
        actions.export_btn.clicked.connect(self._stop_processing)
        self.start_btn = actions.apply_btn
        self.stop_btn = actions.export_btn
        self.stop_btn.setEnabled(False)
        layout.addWidget(actions)

        return CollapsibleSection("Processing", content, True)

    def _build_info_panel(self):
        self.lbl_queue = QLabel("0 file(s)")
        self.lbl_output_rule = QLabel("Original name")
        self.lbl_backup = QLabel("Enabled" if self.create_backup.isChecked() else "Disabled")
        self.lbl_status = QLabel("Idle")
        self.lbl_current = QLabel("-")
        self.lbl_watch = QLabel("Disabled")

        return InfoPanel(
            "Batch Processor Info",
            sections=[
                ("Queue", [("Files", self.lbl_queue), ("Current", self.lbl_current)]),
                ("Output", [("Naming", self.lbl_output_rule), ("Backups", self.lbl_backup)]),
                ("Automation", [("Watch folder", self.lbl_watch), ("Status", self.lbl_status)]),
            ],
        )

    def _refresh_info(self, status: str = None):
        self.lbl_queue.setText(f"{len(self._file_list)} file(s)")
        self.lbl_output_rule.setText(self.naming_pattern.currentText())
        self.lbl_backup.setText("Enabled" if self.create_backup.isChecked() else "Disabled")
        self.lbl_watch.setText(self.watch_folder.text().strip() or "Disabled")
        self.lbl_current.setText(self.current_file_label.text())
        if status is not None:
            self.lbl_status.setText(status)

    def _configure_interaction_help(self):
        self.enable_safe_panel_interactions()
        self.apply_default_button_tooltips()
        self.apply_tooltips([
            (self.file_list_widget, "Queue of files that will be processed in order. Review this list before starting a batch run."),
            (self.add_files_btn, "Add one or more files to the batch queue."),
            (self.add_folder_btn, "Add all matching files from a folder to the batch queue."),
            (self.remove_btn, "Remove the currently selected entries from the batch queue."),
            (self.clear_queue_btn, "Clear every queued file so you can rebuild the batch list."),
            (self.chk_curve_fill, "Apply a curve fill preset after each file is opened. This adds automation but depends on matching object names."),
            (self.curve_fill_preset, "Preset used for automated curve fill processing. Different presets change spacing, pattern, and curve behavior."),
            (self.curve_container_name, "Name of the object that should be used as the curve fill container during batch processing."),
            (self.curve_elements_name, "Name of the object or group used as the fill element source during batch processing."),
            (self.curve_layer_name, "Layer name to target when looking up or writing curve fill content."),
            (self.chk_export, "Export each processed file after automation completes. This adds output files but increases run time."),
            (self.export_format, "Choose the export format written for each processed document. Some formats preserve vectors better than others."),
            (self.chk_resize, "Resize the page before export. Useful for normalization, but it changes final document dimensions."),
            (self.resize_width, "Target page width in millimeters when resize is enabled."),
            (self.resize_height, "Target page height in millimeters when resize is enabled."),
            (self.chk_color, "Convert document color mode before export. Use this when production output requires a specific color space."),
            (self.color_mode, "Target color mode for conversion. This affects output compatibility and color appearance."),
            (self.output_folder, "Folder where exported and processed files are written."),
            (self.browse_output_btn, "Choose the output folder used for processed files."),
            (self.naming_pattern, "Rule used to name processed files. This changes how easy results are to track and sort."),
            (self.suffix_text, "Text added as a suffix or prefix when the naming rule requires it."),
            (self.overwrite_check, "Allow new output files to replace existing files with the same name."),
            (self.create_backup, "Copy the original file before processing so you can recover if the batch result is not correct."),
            (self.watch_enabled, "Enable folder watching so new files in the folder can be processed automatically."),
            (self.watch_folder, "Folder monitored for incoming files when watch mode is enabled."),
            (self.browse_watch_btn, "Choose the folder monitored by watch mode."),
            (self.batch_progress, "Shows overall progress for the current batch run."),
            (self.current_file_label, "Displays the file currently being validated or processed."),
            (self.log_output, "Detailed processing log for validation, batch execution, and stop events."),
        ])

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Files",
            str(Path.home()),
            "CorelDRAW Files (*.cdr);;All Files (*)",
        )

        for file_path in files:
            if file_path not in self._file_list:
                self._file_list.append(file_path)
                self.file_list_widget.addItem(Path(file_path).name)

        self._refresh_info(status="Files queued")
        self.status_message.emit(f"Added {len(files)} file(s) to queue")

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Add Folder", str(Path.home()))
        if folder:
            folder_path = Path(folder)
            cdr_files = list(folder_path.glob("*.cdr"))
            for file_path in cdr_files:
                str_path = str(file_path)
                if str_path not in self._file_list:
                    self._file_list.append(str_path)
                    self.file_list_widget.addItem(file_path.name)

            self._refresh_info(status="Folder imported")
            self.status_message.emit(f"Added {len(cdr_files)} file(s) from folder")

    def _remove_selected(self):
        selected_items = self.file_list_widget.selectedItems()
        for item in selected_items:
            row = self.file_list_widget.row(item)
            self.file_list_widget.takeItem(row)
            if row < len(self._file_list):
                del self._file_list[row]

        self._refresh_info(status="Queue updated")
        self.status_message.emit(f"Removed {len(selected_items)} file(s)")

    def _clear_list(self):
        self.file_list_widget.clear()
        self._file_list.clear()
        self._refresh_info(status="Queue cleared")
        self.status_message.emit("File queue cleared")

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder", str(Path.home()))
        if folder:
            self.output_folder.setText(folder)
            self._refresh_info(status="Output updated")

    def _browse_watch_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Watch Folder", str(Path.home()))
        if folder:
            self.watch_folder.setText(folder)
            self._refresh_info(status="Watch folder updated")

    def _validate_queue(self):
        if not self._file_list:
            QMessageBox.information(self, "Queue Empty", "Add files or a folder to start batch work.")
            return
        self._refresh_info(status="Ready")
        self._log(f"Queue validated: {len(self._file_list)} file(s)")

    def _start_processing(self):
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

        preset_name = self.curve_fill_preset.currentText()
        preset_settings = None
        if self.chk_curve_fill.isChecked() and preset_name and preset_name != "Select preset...":
            matches = preset_manager.search_presets(preset_name, tool="curve_filler")
            if matches:
                preset_data = preset_manager.load_preset(matches[0]["id"])
                if preset_data:
                    preset_settings = preset_data.get("settings", {})

        output_dir = self.output_folder.text().strip() or None
        self._refresh_info(status="Running")

        for i, file_path in enumerate(self._file_list):
            self.current_file_label.setText(f"Processing: {Path(file_path).name}")
            self.batch_progress.setValue(i + 1)
            self.progress_updated.emit(i + 1, total)
            self._refresh_info()
            self._log(f"Processing: {file_path}")

            try:
                if self.create_backup.isChecked():
                    shutil.copy2(file_path, f"{file_path}.bak")

                doc = corel.app.OpenDocument(file_path)

                if self.chk_resize.isChecked():
                    try:
                        doc.ActivePage.SizeWidth = self.resize_width.value()
                        doc.ActivePage.SizeHeight = self.resize_height.value()
                    except Exception as exc:
                        logger.warning("Resize failed: %s", exc)

                if self.chk_color.isChecked():
                    try:
                        mode = self.color_mode.currentData()
                        if mode == "cmyk":
                            doc.ConvertToCMYK()
                        elif mode == "rgb":
                            doc.ConvertToRGB()
                        elif mode == "grayscale":
                            doc.ConvertToGrayscale()
                    except Exception as exc:
                        logger.warning("Color conversion failed: %s", exc)

                if self.chk_curve_fill.isChecked() and preset_settings:
                    try:
                        engine = CurveFillerEngine()
                        container, elements = self._resolve_curve_fill_targets(doc)
                        if container and elements and elements.Count > 0:
                            engine.set_container(container)
                            engine.set_fill_elements(elements)
                            settings = FillSettings(
                                spacing_mode=SpacingMode(preset_settings.get("spacing_mode", "fixed")),
                                spacing_value=preset_settings.get("spacing_value", 10.0),
                                angle_mode=AngleMode(preset_settings.get("angle_mode", "follow_curve")),
                                fixed_angle=preset_settings.get("fixed_angle", 0.0),
                                pattern_mode=PatternMode(preset_settings.get("pattern_mode", "single")),
                            )
                            engine.execute_fill(settings=settings)
                        else:
                            self._log("Curve fill skipped: no valid container/elements.")
                    except Exception as exc:
                        self._log(f"Curve fill failed: {exc}")

                if self.chk_export.isChecked():
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
                        name = f"{base}_{i + 1:03d}"
                    else:
                        name = base
                    out_path = out_dir / f"{name}.{fmt}"
                    try:
                        doc.SaveAs(str(out_path))
                    except Exception as exc:
                        logger.warning("Export failed: %s", exc)
                else:
                    try:
                        doc.Save()
                    except Exception:
                        pass

                try:
                    doc.Close()
                except Exception:
                    pass

                self._log(f"Done: {file_path}")
            except Exception as exc:
                logger.error("Processing error (%s): %s", file_path, exc)
                self._log(f"Error: {file_path} -> {exc}")

        self.current_file_label.setText(f"Completed {total} file(s)")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._refresh_info(status="Completed")
        self.status_message.emit(f"Batch processing completed: {total} files")

    def _stop_processing(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.current_file_label.setText("Processing stopped")
        self._refresh_info(status="Stopped")
        self.status_message.emit("Batch processing stopped")
        self._log("Batch processing stopped")

    def _log(self, message: str):
        self.log_output.appendPlainText(message)

    def _clear_log(self):
        self.log_output.clear()
        self._refresh_info(status="Idle")

    def _resolve_curve_fill_targets(self, doc):
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
                    if container_name and container_name in name and hasattr(shape, "Curve") and shape.Curve is not None:
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
        self.status_message.emit("Batch processor preset applied")

    def reset_to_defaults(self):
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
        self._refresh_info(status="Idle")
        self.status_message.emit("Batch processor reset")
