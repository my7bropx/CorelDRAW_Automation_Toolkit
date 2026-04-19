from typing import Dict, Iterable, Tuple

from PyQt5.QtCore import QEvent, QObject, Qt
from PyQt5.QtWidgets import QComboBox, QDoubleSpinBox, QScrollArea, QSlider, QSpinBox, QWidget


class NoWheelInputFilter(QObject):
    """Prevent accidental wheel edits on value controls inside scrollable panels."""

    CONTROL_TYPES = (QComboBox, QSlider, QSpinBox, QDoubleSpinBox)

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Wheel or not isinstance(obj, self.CONTROL_TYPES):
            return False

        if obj.property("allowWheelInput") and obj.hasFocus():
            return False

        scroll_area = self._find_scroll_area(obj)
        if scroll_area is not None:
            self._scroll_parent(scroll_area, event)
        return True

    def _find_scroll_area(self, widget):
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                return parent
            parent = parent.parentWidget()
        return None

    def _scroll_parent(self, scroll_area: QScrollArea, event) -> None:
        delta = event.angleDelta().y() or event.angleDelta().x()
        if delta == 0:
            return
        bar = scroll_area.verticalScrollBar()
        if not bar.isVisible():
            bar = scroll_area.horizontalScrollBar()
        steps = delta // 120 if delta else 0
        if steps == 0:
            steps = 1 if delta > 0 else -1
        bar.setValue(bar.value() - (steps * bar.singleStep()))


DEFAULT_BUTTON_TOOLTIPS: Dict[str, str] = {
    "preview": "Generate a preview so you can inspect the result before writing output.",
    "apply": "Run the operation and write the result into the final output or CorelDRAW document.",
    "export": "Save the current result to an external file without changing other settings.",
    "clear": "Reset the current result or log so you can start again cleanly.",
    "refresh": "Read the latest selection or state from CorelDRAW and update this panel.",
    "stop": "Cancel the current operation as soon as the worker reaches a safe stopping point.",
    "cancel": "Stop the current operation without applying more changes.",
    "load image": "Choose an image file to use as the current source.",
    "use selection": "Capture the current CorelDRAW selection and use it for this tool.",
    "selection": "Use the current CorelDRAW selection for this action or setting.",
    "browse": "Choose a file or folder for this setting.",
    "reset": "Restore this tool to its default settings.",
    "start batch": "Start processing the queued files with the current batch settings.",
    "validate": "Check the current queue and settings before starting a full batch run.",
    "fill path": "Generate stones along the selected path using the current settings.",
    "fill shape": "Generate a fill inside the selected container shape using the current settings.",
    "draw in coreldraw": "Render the current result into the active CorelDRAW document.",
    "check overlaps": "Analyze the current preview for overlapping stones before final output.",
    "collision rule": "Apply the selected collision handling rule to the current preview result.",
    "refresh table": "Rebuild the size reference table using the current fit factor.",
    "create": "Create a new result using the current settings and selection.",
    "center": "Reposition the current selection using the chosen alignment rule.",
    "mirror": "Mirror the current selection using the chosen axis.",
    "align": "Align the current selection using the chosen rule.",
    "place text": "Create text on the selected path using the current typography settings.",
    "fit to path": "Fit the selected text to the selected path.",
    "remove from path": "Detach the selected text from its current path.",
    "convert to curves": "Convert selected text or shapes to curves for final editing or production.",
    "break apart": "Break the selected object into editable pieces.",
    "random": "Apply the selected randomized variation to the current selection.",
}


def install_no_wheel_behavior(host: QWidget, event_filter: NoWheelInputFilter) -> None:
    for widget in host.findChildren(QWidget):
        if isinstance(widget, NoWheelInputFilter.CONTROL_TYPES):
            widget.installEventFilter(event_filter)
            widget.setFocusPolicy(Qt.StrongFocus)


def apply_tooltips(entries: Iterable[Tuple[QWidget, str]]) -> None:
    for widget, text in entries:
        if widget is not None and text:
            widget.setToolTip(text)


def apply_default_button_tooltips(host: QWidget) -> None:
    for button in host.findChildren(QWidget):
        text = getattr(button, "text", lambda: "")().strip().lower()
        if not text or button.toolTip():
            continue
        for key, tooltip in DEFAULT_BUTTON_TOOLTIPS.items():
            if key in text:
                button.setToolTip(tooltip)
                break
