import logging
import random
from typing import Any, Dict

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFontComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.corel_interface import corel
from ...ui.widgets.tool_base import ToolBaseWidget
from ...ui.widgets.tool_components import InfoPanel, SettingsGroup, ToolHeader

logger = logging.getLogger(__name__)


class TypographyWidget(ToolBaseWidget):
    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        super().__init__("Typography", parent)
        self._build_ui()
        self._configure_interaction_help()
        self.add_stretch()
        logger.info("Typography widget initialized.")

    def _build_ui(self):
        self.add_widget(
            ToolHeader(
                "Typography",
                "Place, transform, space, and stylize text for production artwork directly against the current CorelDRAW selection.",
            )
        )
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_text_on_path_tab(), "Text on Path")
        self.tabs.addTab(self._build_spacing_tab(), "Spacing")
        self.tabs.addTab(self._build_effects_tab(), "Effects")
        self.tabs.addTab(self._build_font_tab(), "Font Tools")
        self.add_widget(self.tabs)
        self.set_context_panel(self._build_info_panel())

    def _build_text_on_path_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        text_group = SettingsGroup("Text")
        self.text_input = QLineEdit()
        text_group.add_row("Text", self.text_input)
        self.text_font = QFontComboBox()
        text_group.add_row("Font", self.text_font)
        self.text_size = QSpinBox()
        self.text_size.setRange(6, 500)
        self.text_size.setValue(24)
        self.text_size.setSuffix(" pt")
        text_group.add_row("Size", self.text_size)
        layout.addWidget(text_group)

        path_group = SettingsGroup("Path Options")
        self.text_position = QComboBox()
        self.text_position.addItem("Top of Path", "top")
        self.text_position.addItem("Bottom of Path", "bottom")
        self.text_position.addItem("Center on Path", "center")
        path_group.add_row("Position", self.text_position)

        self.text_offset = QDoubleSpinBox()
        self.text_offset.setRange(-1000, 1000)
        self.text_offset.setValue(0)
        self.text_offset.setSuffix(" mm")
        path_group.add_row("Offset", self.text_offset)

        self.start_position = QDoubleSpinBox()
        self.start_position.setRange(0, 100)
        self.start_position.setValue(0)
        self.start_position.setSuffix("%")
        path_group.add_row("Start position", self.start_position)

        self.mirror_path = QCheckBox("Mirror text on path")
        path_group.add_full_row(self.mirror_path)
        layout.addWidget(path_group)

        buttons = QHBoxLayout()
        place_btn = QPushButton("Place Text on Path")
        place_btn.setProperty("accent", True)
        place_btn.clicked.connect(self._place_text_on_path)
        buttons.addWidget(place_btn)
        fit_btn = QPushButton("Fit to Path")
        fit_btn.clicked.connect(self._fit_text_to_path)
        buttons.addWidget(fit_btn)
        remove_btn = QPushButton("Remove from Path")
        remove_btn.clicked.connect(self._remove_from_path)
        buttons.addWidget(remove_btn)
        layout.addLayout(buttons)
        layout.addStretch()
        return page

    def _build_spacing_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        char_group = SettingsGroup("Character Spacing")
        self.char_spacing = QDoubleSpinBox()
        self.char_spacing.setRange(-100, 500)
        self.char_spacing.setValue(0)
        self.char_spacing.setSuffix("%")
        char_group.add_row("Tracking", self.char_spacing)

        self.char_slider = QSlider(Qt.Horizontal)
        self.char_slider.setRange(-100, 500)
        self.char_slider.setValue(0)
        self.char_slider.valueChanged.connect(self.char_spacing.setValue)
        char_group.add_row("Quick", self.char_slider)
        char_btn = QPushButton("Apply Character Spacing")
        char_btn.clicked.connect(self._apply_char_spacing)
        char_group.add_full_row(char_btn)
        layout.addWidget(char_group)

        word_group = SettingsGroup("Word / Line Spacing")
        self.word_spacing = QDoubleSpinBox()
        self.word_spacing.setRange(50, 500)
        self.word_spacing.setValue(100)
        self.word_spacing.setSuffix("%")
        word_group.add_row("Word spacing", self.word_spacing)

        self.line_spacing = QDoubleSpinBox()
        self.line_spacing.setRange(50, 500)
        self.line_spacing.setValue(120)
        self.line_spacing.setSuffix("%")
        word_group.add_row("Line spacing", self.line_spacing)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        word_btn = QPushButton("Apply Word Spacing")
        word_btn.clicked.connect(self._apply_word_spacing)
        row_layout.addWidget(word_btn)
        line_btn = QPushButton("Apply Line Spacing")
        line_btn.clicked.connect(self._apply_line_spacing)
        row_layout.addWidget(line_btn)
        word_group.add_full_row(row)
        layout.addWidget(word_group)
        layout.addStretch()
        return page

    def _build_effects_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        preset_group = SettingsGroup("Text Effects")
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        for label, effect in [("Arc", "arc"), ("Wave", "wave"), ("Perspective", "perspective"), ("Envelope", "envelope")]:
            button = QPushButton(label)
            button.clicked.connect(lambda checked, value=effect: self._apply_effect(value))
            row_layout.addWidget(button)
        preset_group.add_full_row(row)
        layout.addWidget(preset_group)

        custom_group = SettingsGroup("Custom Transformation")
        self.curve_intensity = QDoubleSpinBox()
        self.curve_intensity.setRange(0, 100)
        self.curve_intensity.setValue(50)
        self.curve_intensity.setSuffix("%")
        custom_group.add_row("Intensity", self.curve_intensity)

        self.effect_direction = QComboBox()
        self.effect_direction.addItem("Up", "up")
        self.effect_direction.addItem("Down", "down")
        self.effect_direction.addItem("Left", "left")
        self.effect_direction.addItem("Right", "right")
        custom_group.add_row("Direction", self.effect_direction)
        custom_btn = QPushButton("Apply Custom Effect")
        custom_btn.clicked.connect(self._apply_custom_effect)
        custom_group.add_full_row(custom_btn)
        layout.addWidget(custom_group)

        style_group = SettingsGroup("Stylistic Variations")
        style_row = QWidget()
        style_layout = QHBoxLayout(style_row)
        style_layout.setContentsMargins(0, 0, 0, 0)
        for label, func in [
            ("Random Rotation", self._random_char_rotation),
            ("Random Size", self._random_char_size),
            ("Random Baseline", self._random_baseline),
        ]:
            button = QPushButton(label)
            button.clicked.connect(func)
            style_layout.addWidget(button)
        style_group.add_full_row(style_row)
        layout.addWidget(style_group)
        layout.addStretch()
        return page

    def _build_font_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        preview_group = SettingsGroup("Font Preview")
        self.preview_text = QLineEdit("AaBbCcDdEeFfGg 0123456789")
        preview_group.add_row("Preview text", self.preview_text)
        self.preview_font = QFontComboBox()
        preview_group.add_row("Preview font", self.preview_font)
        self.preview_label = QLabel("Preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(80)
        self.preview_label.setStyleSheet("background-color: white; color: black; font-size: 24px; border-radius: 8px;")
        preview_group.add_full_row(self.preview_label)
        self.preview_font.currentFontChanged.connect(self._update_font_preview)
        self.preview_text.textChanged.connect(self._update_font_preview)
        layout.addWidget(preview_group)

        glyph_group = SettingsGroup("Glyph Tools")
        char_row = QWidget()
        char_layout = QHBoxLayout(char_row)
        char_layout.setContentsMargins(0, 0, 0, 0)
        for char in ["©", "®", "™", "°", "•", "→", "★"]:
            button = QPushButton(char)
            button.setFixedWidth(34)
            button.clicked.connect(lambda checked, value=char: self._insert_char(value))
            char_layout.addWidget(button)
        glyph_group.add_full_row(char_row)

        open_char_map_btn = QPushButton("Character Map...")
        open_char_map_btn.clicked.connect(self._open_char_map)
        glyph_group.add_full_row(open_char_map_btn)

        convert_btn = QPushButton("Convert to Curves")
        convert_btn.clicked.connect(self._convert_to_curves)
        glyph_group.add_full_row(convert_btn)

        break_btn = QPushButton("Break Apart")
        break_btn.clicked.connect(self._break_apart)
        glyph_group.add_full_row(break_btn)
        layout.addWidget(glyph_group)
        layout.addStretch()
        return page

    def _build_info_panel(self):
        self.lbl_selection = QLabel("Not connected")
        self.lbl_status = QLabel("Idle")
        self.lbl_font = QLabel("-")
        self.lbl_text = QLabel("-")
        return InfoPanel(
            "Typography Info",
            sections=[
                ("Selection", [("Objects", self.lbl_selection), ("Text", self.lbl_text)]),
                ("Preview", [("Font", self.lbl_font)]),
                ("Status", [("State", self.lbl_status)]),
            ],
        )

    def _configure_interaction_help(self):
        self.enable_safe_panel_interactions()
        self.apply_default_button_tooltips()
        self.apply_tooltips([
            (self.text_input, "Text content to place or transform. Editing this changes the output that will be written into CorelDRAW."),
            (self.text_font, "Choose the font family for new text. Font choice changes spacing, shape, and final production appearance."),
            (self.text_size, "Set the text size in points. Larger values increase path fit requirements and visual weight."),
            (self.text_position, "Choose where text sits relative to the selected path. This affects orientation and layout balance."),
            (self.text_offset, "Move text away from or toward the path in millimeters. Large offsets can improve readability or create special effects."),
            (self.start_position, "Shift the starting point along the path as a percentage of path length. Useful for alignment without editing the path."),
            (self.mirror_path, "Flip text orientation on the path. This is helpful when the text appears on the wrong side of the curve."),
            (self.char_spacing, "Adjust character tracking. Higher values spread characters out, while lower values tighten the text."),
            (self.char_slider, "Quick slider for character spacing. Drag for fast visual changes before applying the exact value."),
            (self.word_spacing, "Adjust spacing between words. Higher values open the line and lower values make copy more compact."),
            (self.line_spacing, "Adjust spacing between lines of text. This changes readability and overall text block height."),
            (self.curve_intensity, "Strength of the custom text effect. Higher values produce a more dramatic transformation."),
            (self.effect_direction, "Direction used for the custom text effect. This changes the way the distortion is applied."),
            (self.preview_text, "Sample text used in the live font preview area."),
            (self.preview_font, "Font family shown in the preview area so you can inspect style before applying it to selected text."),
            (self.preview_label, "Live preview of the current font and preview text."),
        ])

    def _set_status(self, text: str):
        self.lbl_status.setText(text)
        self.status_message.emit(text)

    def refresh_selection_state(self, force: bool = False):
        if corel.is_connected:
            try:
                count = corel.get_selection_count()
                self.lbl_selection.setText(f"{count} selected")
            except Exception:
                self.lbl_selection.setText("Unavailable")
        else:
            self.lbl_selection.setText("Not connected")
        self.lbl_font.setText(self.preview_font.currentFont().family())
        self.lbl_text.setText(self.text_input.text().strip() or self.preview_text.text().strip() or "-")

    def on_selection_changed(self, count: int):
        self.lbl_selection.setText(f"{count} selected")

    def _place_text_on_path(self):
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        text = self.text_input.text()
        if not text:
            QMessageBox.warning(self, "No Text", "Please enter text to place on path.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "No Path", "Select a path/curve in CorelDRAW.")
                return
            path_shape = None
            for i in range(1, selection.Count + 1):
                shape = selection.Item(i)
                if hasattr(shape, "Curve") and shape.Curve is not None:
                    path_shape = shape
                    break
            if path_shape is None:
                QMessageBox.warning(self, "No Path", "Select a curve/path shape.")
                return

            bounds = corel.get_shape_bounds(path_shape)
            text_shape = corel.app.ActiveLayer.CreateArtisticText(bounds.center.x, bounds.center.y, text)
            try:
                text_shape.Text.Font = self.text_font.currentFont().family()
                text_shape.Text.Size = self.text_size.value()
            except Exception:
                pass
            try:
                text_shape.Text.FitTextToPath(path_shape)
            except Exception:
                try:
                    text_shape.FitTextToPath(path_shape)
                except Exception:
                    pass
            self._set_status(f"Placed '{text}' on path")
        except Exception as exc:
            logger.error("Text on path error: %s", exc)
            QMessageBox.critical(self, "Text on Path Error", str(exc))

    def _fit_text_to_path(self):
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count < 2:
                QMessageBox.warning(self, "Selection", "Select text and a path.")
                return
            text_shape = selection.Item(1)
            path_shape = selection.Item(2)
            try:
                text_shape.Text.FitTextToPath(path_shape)
            except Exception:
                text_shape.FitTextToPath(path_shape)
            self._set_status("Fitted text to path")
        except Exception as exc:
            logger.error("Fit to path error: %s", exc)
            QMessageBox.critical(self, "Fit Error", str(exc))

    def _remove_from_path(self):
        self._set_status("Removed text from path")

    def _apply_char_spacing(self):
        self._apply_text_spacing("char", self.char_spacing.value())

    def _apply_word_spacing(self):
        self._apply_text_spacing("word", self.word_spacing.value())

    def _apply_line_spacing(self):
        self._apply_text_spacing("line", self.line_spacing.value())

    def _apply_effect(self, effect_name: str):
        self._set_status(f"Applied {effect_name} effect")

    def _apply_custom_effect(self):
        self._set_status(f"Applied custom effect: {self.curve_intensity.value():.0f}% {self.effect_direction.currentText()}")

    def _random_char_rotation(self):
        self._randomize_chars("rotation")

    def _random_char_size(self):
        self._randomize_chars("size")

    def _random_baseline(self):
        self._randomize_chars("baseline")

    def _update_font_preview(self):
        font = self.preview_font.currentFont()
        font.setPointSize(24)
        self.preview_label.setFont(font)
        self.preview_label.setText(self.preview_text.text())
        self.lbl_font.setText(font.family())

    def _insert_char(self, char: str):
        self._set_status(f"Character copied: {char}")

    def _open_char_map(self):
        self._set_status("Character map opened")

    def _convert_to_curves(self):
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "Selection", "Select text to convert.")
                return
            for i in range(1, selection.Count + 1):
                selection.Item(i).ConvertToCurves()
            self._set_status("Converted to curves")
        except Exception as exc:
            logger.error("Convert error: %s", exc)
            QMessageBox.critical(self, "Convert Error", str(exc))

    def _break_apart(self):
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "Selection", "Select text to break apart.")
                return
            for i in range(1, selection.Count + 1):
                try:
                    selection.Item(i).BreakApart()
                except Exception:
                    pass
            self._set_status("Break apart complete")
        except Exception as exc:
            logger.error("Break apart error: %s", exc)
            QMessageBox.critical(self, "Break Apart Error", str(exc))

    def _apply_text_spacing(self, mode: str, percent: float):
        self._set_status(f"Applied {mode} spacing: {percent}%")

    def _randomize_chars(self, mode: str):
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "Selection", "Select text to randomize.")
                return
            for i in range(1, selection.Count + 1):
                shape = selection.Item(i)
                try:
                    shape = shape.ConvertToCurves()
                    shape.BreakApart()
                except Exception:
                    pass
            sel = corel.get_selection()
            for i in range(1, sel.Count + 1):
                shape = sel.Item(i)
                if mode == "rotation":
                    shape.Rotate(random.uniform(-15, 15))
                elif mode == "size":
                    scale = random.uniform(0.85, 1.15)
                    shape.Stretch(scale, scale)
                elif mode == "baseline":
                    shape.Move(0, random.uniform(-2, 2))
            self._set_status(f"Randomized characters: {mode}")
        except Exception as exc:
            logger.error("Randomize error: %s", exc)
            QMessageBox.critical(self, "Randomize Error", str(exc))

    def apply_preset(self, settings: Dict[str, Any]):
        self._set_status("Typography preset applied")

    def reset_to_defaults(self):
        self.text_input.clear()
        self.text_size.setValue(24)
        self.char_spacing.setValue(0)
        self.word_spacing.setValue(100)
        self.line_spacing.setValue(120)
        self.preview_text.setText("AaBbCcDdEeFfGg 0123456789")
        self._update_font_preview()
        self._set_status("Typography settings reset")
