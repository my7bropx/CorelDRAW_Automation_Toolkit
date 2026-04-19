from typing import Iterable, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..ui_helpers import (
    NoWheelInputFilter,
    apply_default_button_tooltips,
    apply_tooltips,
    install_no_wheel_behavior,
)


class ToolBaseWidget(QWidget):
    status_message = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.tool_title = title
        self._context_panel = QWidget()
        self._tool_active = False

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.workspace_outer = QWidget()
        self.workspace_outer_layout = QVBoxLayout(self.workspace_outer)
        self.workspace_outer_layout.setContentsMargins(24, 18, 24, 18)
        self.workspace_outer_layout.setSpacing(0)

        self.workspace = QWidget()
        self.workspace.setMaximumWidth(1040)
        self.workspace_layout = QVBoxLayout(self.workspace)
        self.workspace_layout.setContentsMargins(0, 0, 0, 0)
        self.workspace_layout.setSpacing(12)

        self.workspace_outer_layout.addWidget(self.workspace)
        self.workspace_outer_layout.addStretch()

        self.scroll_area.setWidget(self.workspace_outer)
        root.addWidget(self.scroll_area)
        self._wheel_filter = NoWheelInputFilter(self)

    def set_workspace_widget(self, widget: QWidget) -> None:
        while self.workspace_layout.count():
            item = self.workspace_layout.takeAt(0)
            child = item.widget()
            if child:
                child.setParent(None)
        self.workspace_layout.addWidget(widget)

    def add_widget(self, widget: QWidget) -> None:
        self.workspace_layout.addWidget(widget)

    def add_stretch(self) -> None:
        self.workspace_layout.addStretch()

    def set_context_panel(self, widget: QWidget) -> None:
        self._context_panel = widget

    def context_panel(self) -> QWidget:
        return self._context_panel

    def refresh_selection_state(self, force: bool = False):
        return

    def reset_to_defaults(self):
        return

    def on_tool_activated(self) -> None:
        self._tool_active = True
        self.resume_live_updates()

    def on_tool_deactivated(self) -> None:
        self.suspend_live_updates()
        self.cancel_pending_work()
        self._tool_active = False

    def is_tool_active(self) -> bool:
        return bool(self._tool_active)

    def on_activate(self) -> None:
        self.on_tool_activated()

    def on_deactivate(self) -> None:
        self.on_tool_deactivated()

    def cancel_pending_work(self) -> None:
        return

    def suspend_live_updates(self) -> None:
        self.setUpdatesEnabled(False)

    def resume_live_updates(self) -> None:
        self.setUpdatesEnabled(True)

    def enable_safe_panel_interactions(self) -> None:
        install_no_wheel_behavior(self, self._wheel_filter)

    def apply_tooltips(self, entries: Iterable[Tuple[QWidget, str]]) -> None:
        apply_tooltips(entries)

    def apply_default_button_tooltips(self) -> None:
        apply_default_button_tooltips(self)
