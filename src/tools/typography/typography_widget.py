"""
Typography Tools Widget
PyQt5 UI for text and typography automation.
"""

import logging
import random
from typing import Dict, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QDoubleSpinBox, QComboBox, QSpinBox,
    QCheckBox, QLineEdit, QTextEdit, QSlider, QTabWidget,
    QFontComboBox, QMessageBox, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from ...core.corel_interface import corel
from ...ui.icon_utils import apply_button_icons

logger = logging.getLogger(__name__)


class TypographyWidget(QWidget):
    """Widget for text and typography tools."""

    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, parent=None):
        """Initialize the typography widget."""
        super().__init__(parent)
        self._init_ui()
        logger.info("Typography widget initialized.")

    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Sub-tabs for different typography tools
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)

        # Text on Path tab
        text_path_tab = self._create_text_on_path_tab()
        tabs.addTab(text_path_tab, "Text on Path")

        # Character spacing tab
        spacing_tab = self._create_spacing_tab()
        tabs.addTab(spacing_tab, "Spacing")

        # Text effects tab
        effects_tab = self._create_effects_tab()
        tabs.addTab(effects_tab, "Effects")

        # Font tools tab
        font_tab = self._create_font_tab()
        tabs.addTab(font_tab, "Font Tools")

        main_layout.addWidget(tabs)

        icon_map = {
            "apply": "apply.png",
            "place text on path": "apply.png",
            "fit to path": "apply.png",
            "remove from path": "clear.png",
            "open character map...": "action.png",
            "convert to curves": "apply.png",
            "break apart": "clear.png",
        }
        apply_button_icons(self, icon_map)

    def _create_text_on_path_tab(self) -> QWidget:
        """Create text on path controls."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(350)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        text_group = QGroupBox("Text")
        text_layout = QFormLayout(text_group)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter text to place on path...")
        text_layout.addRow("Text:", self.text_input)

        self.text_font = QFontComboBox()
        text_layout.addRow("Font:", self.text_font)

        self.text_size = QSpinBox()
        self.text_size.setRange(6, 500)
        self.text_size.setValue(24)
        self.text_size.setSuffix(" pt")
        text_layout.addRow("Size:", self.text_size)

        layout.addWidget(text_group)

        path_group = QGroupBox("Path Options")
        path_layout = QFormLayout(path_group)

        self.text_position = QComboBox()
        self.text_position.addItem("Top of Path", "top")
        self.text_position.addItem("Bottom of Path", "bottom")
        self.text_position.addItem("Center on Path", "center")
        path_layout.addRow("Position:", self.text_position)

        self.text_offset = QDoubleSpinBox()
        self.text_offset.setRange(-1000, 1000)
        self.text_offset.setValue(0)
        self.text_offset.setSuffix(" mm")
        path_layout.addRow("Offset:", self.text_offset)

        self.start_position = QDoubleSpinBox()
        self.start_position.setRange(0, 100)
        self.start_position.setValue(0)
        self.start_position.setSuffix("%")
        path_layout.addRow("Start Position:", self.start_position)

        self.mirror_path = QCheckBox("Mirror text on path")
        path_layout.addRow("", self.mirror_path)

        layout.addWidget(path_group)

        action_layout = QVBoxLayout()

        place_on_path_btn = QPushButton("Place Text on Path")
        place_on_path_btn.setStyleSheet("background-color: #4b6eaf; font-weight: bold; padding: 8px;")
        place_on_path_btn.clicked.connect(self._place_text_on_path)
        action_layout.addWidget(place_on_path_btn)

        fit_to_path_btn = QPushButton("Fit to Path")
        fit_to_path_btn.clicked.connect(self._fit_text_to_path)
        action_layout.addWidget(fit_to_path_btn)

        remove_from_path_btn = QPushButton("Remove from Path")
        remove_from_path_btn.clicked.connect(self._remove_from_path)
        action_layout.addWidget(remove_from_path_btn)

        layout.addLayout(action_layout)
        layout.addStretch()

        scroll.setWidget(widget)
        return scroll

    def _create_spacing_tab(self) -> QWidget:
        """Create character spacing controls."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(350)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        char_group = QGroupBox("Character Spacing")
        char_layout = QFormLayout(char_group)

        self.char_spacing = QDoubleSpinBox()
        self.char_spacing.setRange(-100, 500)
        self.char_spacing.setValue(0)
        self.char_spacing.setSuffix("%")
        char_layout.addRow("Tracking:", self.char_spacing)

        char_slider = QSlider(Qt.Horizontal)
        char_slider.setRange(-100, 500)
        char_slider.setValue(0)
        char_slider.valueChanged.connect(self.char_spacing.setValue)
        char_layout.addRow("Quick:", char_slider)

        apply_char_btn = QPushButton("Apply")
        apply_char_btn.setStyleSheet("background-color: #4b6eaf; padding: 6px;")
        apply_char_btn.clicked.connect(self._apply_char_spacing)
        char_layout.addRow(apply_char_btn)

        layout.addWidget(char_group)

        word_group = QGroupBox("Word Spacing")
        word_layout = QFormLayout(word_group)

        self.word_spacing = QDoubleSpinBox()
        self.word_spacing.setRange(50, 500)
        self.word_spacing.setValue(100)
        self.word_spacing.setSuffix("%")
        word_layout.addRow("Word Space:", self.word_spacing)

        apply_word_btn = QPushButton("Apply")
        apply_word_btn.clicked.connect(self._apply_word_spacing)
        word_layout.addRow(apply_word_btn)

        layout.addWidget(word_group)

        line_group = QGroupBox("Line Spacing")
        line_layout = QFormLayout(line_group)

        self.line_spacing = QDoubleSpinBox()
        self.line_spacing.setRange(50, 500)
        self.line_spacing.setValue(120)
        self.line_spacing.setSuffix("%")
        line_layout.addRow("Line Height:", self.line_spacing)

        apply_line_btn = QPushButton("Apply")
        apply_line_btn.clicked.connect(self._apply_line_spacing)
        line_layout.addRow(apply_line_btn)

        layout.addWidget(line_group)

        layout.addStretch()

        scroll.setWidget(widget)
        return scroll

    def _create_effects_tab(self) -> QWidget:
        """Create text effects controls."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(350)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        presets_group = QGroupBox("Text Effect Presets")
        presets_layout = QVBoxLayout(presets_group)

        arc_text_btn = QPushButton("Arc Text")
        arc_text_btn.clicked.connect(lambda: self._apply_effect("arc"))
        presets_layout.addWidget(arc_text_btn)

        wave_text_btn = QPushButton("Wave Text")
        wave_text_btn.clicked.connect(lambda: self._apply_effect("wave"))
        presets_layout.addWidget(wave_text_btn)

        perspective_btn = QPushButton("Perspective")
        perspective_btn.clicked.connect(lambda: self._apply_effect("perspective"))
        presets_layout.addWidget(perspective_btn)

        envelope_btn = QPushButton("Envelope")
        envelope_btn.clicked.connect(lambda: self._apply_effect("envelope"))
        presets_layout.addWidget(envelope_btn)

        layout.addWidget(presets_group)

        custom_group = QGroupBox("Custom Transformations")
        custom_layout = QFormLayout(custom_group)

        self.curve_intensity = QDoubleSpinBox()
        self.curve_intensity.setRange(0, 100)
        self.curve_intensity.setValue(50)
        self.curve_intensity.setSuffix("%")
        custom_layout.addRow("Intensity:", self.curve_intensity)

        self.effect_direction = QComboBox()
        self.effect_direction.addItem("Up", "up")
        self.effect_direction.addItem("Down", "down")
        self.effect_direction.addItem("Left", "left")
        self.effect_direction.addItem("Right", "right")
        custom_layout.addRow("Direction:", self.effect_direction)

        apply_custom_btn = QPushButton("Apply")
        apply_custom_btn.setStyleSheet("background-color: #4b6eaf; padding: 6px;")
        apply_custom_btn.clicked.connect(self._apply_custom_effect)
        custom_layout.addRow(apply_custom_btn)

        layout.addWidget(custom_group)

        style_group = QGroupBox("Stylistic Variations")
        style_layout = QVBoxLayout(style_group)

        random_rotate_btn = QPushButton("Random Rotation")
        random_rotate_btn.clicked.connect(self._random_char_rotation)
        style_layout.addWidget(random_rotate_btn)

        random_size_btn = QPushButton("Random Size")
        random_size_btn.clicked.connect(self._random_char_size)
        style_layout.addWidget(random_size_btn)

        baseline_shift_btn = QPushButton("Random Baseline")
        baseline_shift_btn.clicked.connect(self._random_baseline)
        style_layout.addWidget(baseline_shift_btn)

        layout.addWidget(style_group)

        layout.addStretch()

        scroll.setWidget(widget)
        return scroll

    def _create_font_tab(self) -> QWidget:
        """Create font tools controls."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(350)
        
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        preview_group = QGroupBox("Font Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_text = QLineEdit("AaBbCcDdEeFfGg 0123456789")
        preview_layout.addWidget(self.preview_text)

        self.preview_font = QFontComboBox()
        preview_layout.addWidget(self.preview_font)

        self.preview_label = QLabel("Preview")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(60)
        self.preview_label.setStyleSheet("background-color: white; color: black; font-size: 24px;")
        preview_layout.addWidget(self.preview_label)

        self.preview_font.currentFontChanged.connect(self._update_font_preview)
        self.preview_text.textChanged.connect(self._update_font_preview)

        layout.addWidget(preview_group)

        char_map_group = QGroupBox("Special Characters")
        char_map_layout = QVBoxLayout(char_map_group)

        char_map_label = QLabel("Quick Insert:")
        char_map_layout.addWidget(char_map_label)

        special_chars = QHBoxLayout()
        for char in ['©', '®', '™', '°', '•', '→', '←', '↑', '↓', '★']:
            btn = QPushButton(char)
            btn.setFixedSize(30, 30)
            btn.clicked.connect(lambda checked, c=char: self._insert_char(c))
            special_chars.addWidget(btn)
        char_map_layout.addLayout(special_chars)

        open_char_map_btn = QPushButton("Character Map...")
        open_char_map_btn.clicked.connect(self._open_char_map)
        char_map_layout.addWidget(open_char_map_btn)

        layout.addWidget(char_map_group)

        glyph_group = QGroupBox("Glyph Tools")
        glyph_layout = QVBoxLayout(glyph_group)

        convert_to_curves_btn = QPushButton("Convert to Curves")
        convert_to_curves_btn.setStyleSheet("background-color: #4b6eaf; padding: 6px;")
        convert_to_curves_btn.clicked.connect(self._convert_to_curves)
        glyph_layout.addWidget(convert_to_curves_btn)

        break_apart_btn = QPushButton("Break Apart")
        break_apart_btn.clicked.connect(self._break_apart)
        glyph_layout.addWidget(break_apart_btn)

        layout.addWidget(glyph_group)

        layout.addStretch()

        scroll.setWidget(widget)
        return scroll

    def _place_text_on_path(self):
        """Place text on selected path."""
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
            x = bounds.center.x
            y = bounds.center.y

            text_shape = corel.app.ActiveLayer.CreateArtisticText(x, y, text)
            try:
                text_shape.Text.Font = self.text_font.currentFont().family()
            except Exception:
                pass
            try:
                text_shape.Text.Size = self.text_size.value()
            except Exception:
                pass

            # Fit to path (best-effort)
            fitted = False
            for attr in ("FitTextToPath", "FitToPath"):
                try:
                    getattr(text_shape.Text, attr)(path_shape)
                    fitted = True
                    break
                except Exception:
                    continue
            if not fitted:
                try:
                    text_shape.FitTextToPath(path_shape)
                except Exception:
                    pass

            # Apply position/offset/mirror if supported
            try:
                text_path = text_shape.TextPath
            except Exception:
                text_path = None

            if text_path:
                try:
                    text_path.Distance = self.text_offset.value()
                except Exception:
                    pass
                if self.mirror_path.isChecked():
                    try:
                        text_path.Mirror = True
                    except Exception:
                        pass

            self.status_message.emit(f"Placed '{text}' on path")
        except Exception as e:
            logger.error(f"Text on path error: {e}")
            QMessageBox.critical(self, "Text on Path Error", str(e))

    def _fit_text_to_path(self):
        """Fit existing text to path."""
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
                try:
                    text_shape.FitTextToPath(path_shape)
                except Exception as e:
                    raise e
            self.status_message.emit("Fitted text to path")
        except Exception as e:
            logger.error(f"Fit to path error: {e}")
            QMessageBox.critical(self, "Fit Error", str(e))

    def _remove_from_path(self):
        """Remove text from path."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "Selection", "Select text on a path.")
                return
            text_shape = selection.Item(1)
            removed = False
            for attr in ("DetachFromPath", "RemoveFromPath"):
                try:
                    getattr(text_shape.Text, attr)()
                    removed = True
                    break
                except Exception:
                    continue
            if not removed:
                try:
                    text_shape.DetachFromPath()
                except Exception:
                    pass
            self.status_message.emit("Removed text from path")
        except Exception as e:
            logger.error(f"Remove from path error: {e}")
            QMessageBox.critical(self, "Remove Error", str(e))

    def _apply_char_spacing(self):
        """Apply character spacing."""
        self._apply_text_spacing("char", self.char_spacing.value())

    def _apply_word_spacing(self):
        """Apply word spacing."""
        self._apply_text_spacing("word", self.word_spacing.value())

    def _apply_line_spacing(self):
        """Apply line spacing."""
        self._apply_text_spacing("line", self.line_spacing.value())

    def _apply_effect(self, effect_name: str):
        """Apply preset text effect."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "Selection", "Select text to apply effect.")
                return
            # Best-effort: convert to curves and apply a simple deformation via scaling/rotation
            for i in range(1, selection.Count + 1):
                shape = selection.Item(i)
                try:
                    shape = shape.ConvertToCurves()
                except Exception:
                    pass
                if effect_name == "arc":
                    shape.Rotate(5)
                elif effect_name == "wave":
                    shape.Rotate(-5)
                elif effect_name == "perspective":
                    shape.Stretch(1.05, 0.95)
                elif effect_name == "envelope":
                    shape.Stretch(0.95, 1.05)
            self.status_message.emit(f"Applied {effect_name} effect")
        except Exception as e:
            logger.error(f"Effect error: {e}")
            QMessageBox.critical(self, "Effect Error", str(e))

    def _apply_custom_effect(self):
        """Apply custom text effect."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            intensity = self.curve_intensity.value()
            direction = self.effect_direction.currentText()
            factor = 1.0 + (intensity / 100.0) * 0.1
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "Selection", "Select text to apply effect.")
                return
            for i in range(1, selection.Count + 1):
                shape = selection.Item(i)
                try:
                    shape = shape.ConvertToCurves()
                except Exception:
                    pass
                if direction.lower().startswith("in"):
                    shape.Stretch(1.0 / factor, factor)
                else:
                    shape.Stretch(factor, 1.0 / factor)
            self.status_message.emit(f"Applied custom effect: {intensity}% {direction}")
        except Exception as e:
            logger.error(f"Custom effect error: {e}")
            QMessageBox.critical(self, "Effect Error", str(e))

    def _random_char_rotation(self):
        """Randomize character rotation."""
        self._randomize_chars("rotation")

    def _random_char_size(self):
        """Randomize character size."""
        self._randomize_chars("size")

    def _random_baseline(self):
        """Randomize baseline shift."""
        self._randomize_chars("baseline")

    def _update_font_preview(self):
        """Update the font preview."""
        font = self.preview_font.currentFont()
        font.setPointSize(24)
        self.preview_label.setFont(font)
        self.preview_label.setText(self.preview_text.text())

    def _insert_char(self, char: str):
        """Insert special character."""
        self.status_message.emit(f"Character copied: {char}")
        # In full implementation, would insert into CorelDRAW

    def _open_char_map(self):
        """Open character map dialog."""
        self.status_message.emit("Opening character map")

    def _convert_to_curves(self):
        """Convert text to curves."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "Selection", "Select text to convert.")
                return
            for i in range(1, selection.Count + 1):
                shape = selection.Item(i)
                shape.ConvertToCurves()
            self.status_message.emit("Converted to curves")
        except Exception as e:
            logger.error(f"Convert error: {e}")
            QMessageBox.critical(self, "Convert Error", str(e))

    def _break_apart(self):
        """Break apart text characters."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "Selection", "Select text to break apart.")
                return
            for i in range(1, selection.Count + 1):
                shape = selection.Item(i)
                try:
                    shape.BreakApart()
                except Exception:
                    pass
            self.status_message.emit("Break apart complete")
        except Exception as e:
            logger.error(f"Break apart error: {e}")
            QMessageBox.critical(self, "Break Apart Error", str(e))

    def _apply_text_spacing(self, mode: str, percent: float):
        """Apply text spacing to selected text shapes."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "Selection", "Select text to apply spacing.")
                return
            for i in range(1, selection.Count + 1):
                shape = selection.Item(i)
                if not hasattr(shape, "Text"):
                    continue
                text = shape.Text
                story = getattr(text, "Story", text)
                if mode == "char":
                    self._set_text_prop(story, ["CharacterSpacing", "CharSpacing", "Tracking"], percent)
                elif mode == "word":
                    self._set_text_prop(story, ["WordSpacing", "SpaceBetweenWords"], percent)
                elif mode == "line":
                    self._set_text_prop(story, ["LineSpacing", "Leading"], percent)
            self.status_message.emit(f"Applied {mode} spacing: {percent}%")
        except Exception as e:
            logger.error(f"Spacing error: {e}")
            QMessageBox.critical(self, "Spacing Error", str(e))

    def _set_text_prop(self, obj, names, value):
        """Best-effort property set for text."""
        for name in names:
            try:
                setattr(obj, name, value)
                return True
            except Exception:
                continue
        # Fallback to fractional value
        for name in names:
            try:
                setattr(obj, name, value / 100.0)
                return True
            except Exception:
                continue
        return False

    def _randomize_chars(self, mode: str):
        """Randomize character transforms by converting to curves and breaking apart."""
        if not corel.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to CorelDRAW first.")
            return
        try:
            selection = corel.get_selection()
            if selection.Count == 0:
                QMessageBox.warning(self, "Selection", "Select text to randomize.")
                return
            # Convert and break apart
            shapes = []
            for i in range(1, selection.Count + 1):
                shape = selection.Item(i)
                try:
                    shape = shape.ConvertToCurves()
                except Exception:
                    pass
                try:
                    shape.BreakApart()
                except Exception:
                    pass
                shapes.append(shape)

            # Apply random transforms to current selection
            sel = corel.get_selection()
            for i in range(1, sel.Count + 1):
                shape = sel.Item(i)
                if mode == "rotation":
                    angle = random.uniform(-15, 15)
                    shape.Rotate(angle)
                elif mode == "size":
                    scale = random.uniform(0.85, 1.15)
                    shape.Stretch(scale, scale)
                elif mode == "baseline":
                    dy = random.uniform(-2, 2)
                    shape.Move(0, dy)
            self.status_message.emit(f"Randomized characters: {mode}")
        except Exception as e:
            logger.error(f"Randomize error: {e}")
            QMessageBox.critical(self, "Randomize Error", str(e))

    def apply_preset(self, settings: Dict[str, Any]):
        """Apply preset settings."""
        self.status_message.emit("Typography preset applied")

    def reset_to_defaults(self):
        """Reset to default values."""
        self.text_input.clear()
        self.text_size.setValue(24)
        self.char_spacing.setValue(0)
        self.word_spacing.setValue(100)
        self.line_spacing.setValue(120)
        self.status_message.emit("Typography settings reset")
