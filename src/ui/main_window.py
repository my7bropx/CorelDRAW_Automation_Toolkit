import logging
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path

from PyQt5.QtCore import QEvent, QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDockWidget,
    QFileDialog,
    QFrame,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..config import config
from ..core.corel_interface import CorelDRAWConnectionError, corel
from ..core.preset_manager import preset_manager
from .dialogs.settings_dialog import SettingsDialog
from .widgets.connection_indicator import ConnectionIndicator
from .widgets.sidebar import Sidebar
from .widgets.tool_base import ToolBaseWidget

logger = logging.getLogger(__name__)


class TopLevelWidgetTraceFilter(QObject):
    """Debug lifecycle filter for unexpected top-level widget activity."""

    def eventFilter(self, watched, event):  # noqa: N802
        if not isinstance(watched, QWidget):
            return False
        if watched.parentWidget() is not None:
            return False
        event_type = event.type()
        if event_type in (QEvent.Show, QEvent.Hide, QEvent.Close):
            logger.info(
                "top-level-widget event=%s class=%s title=%s visible=%s object=%s",
                int(event_type),
                watched.__class__.__name__,
                watched.windowTitle(),
                watched.isVisible(),
                watched.objectName(),
            )
        return False


@dataclass(frozen=True)
class ToolSpec:
    key: str
    title: str
    factory: callable


class SafeContextPanel(QWidget):
    """Minimal right-side info dock that never replaces real tool controls."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Workspace Info")
        title.setObjectName("context_title")
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("context_card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(8)

        self.tool_name_label = QLabel("No tool selected")
        self.tool_name_label.setObjectName("context_tool_name")
        card_layout.addWidget(self.tool_name_label)

        self.tool_hint_label = QLabel(
            "The active tool keeps its real settings and actions in the center workspace. "
            "This panel stays informational only."
        )
        self.tool_hint_label.setWordWrap(True)
        self.tool_hint_label.setObjectName("context_hint")
        card_layout.addWidget(self.tool_hint_label)

        self.connection_label = QLabel("CorelDRAW: Not Connected")
        card_layout.addWidget(self.connection_label)

        self.selection_label = QLabel("Selection: No Selection")
        card_layout.addWidget(self.selection_label)

        layout.addWidget(card)
        layout.addStretch()

    def set_tool(self, title: str) -> None:
        self.tool_name_label.setText(title)

    def set_connection(self, connected: bool) -> None:
        if connected:
            self.connection_label.setText(f"CorelDRAW: Connected ({corel.version})")
        else:
            self.connection_label.setText("CorelDRAW: Not Connected")

    def set_selection_text(self, text: str) -> None:
        self.selection_label.setText(f"Selection: {text}")


class MainWindow(QMainWindow):
    connection_status_changed = pyqtSignal(bool)
    selection_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CorelDRAW Automation Toolkit v0.1.0-beta")
        self.setMinimumSize(1480, 900)
        self.setMaximumSize(1480, 900)
        self.setFixedSize(1480, 900)

        self._tool_specs = self._build_tool_specs()
        self._tool_widgets = {}
        self._tool_order = [spec.key for spec in self._tool_specs]
        self._current_tool_key = None
        self.preset_browser = None
        self.preset_dock = None
        self._tool_switch_timer = QTimer(self)
        self._tool_switch_timer.setSingleShot(True)
        self._tool_switch_timer.timeout.connect(self._finish_pending_tool_activation)
        self._pending_tool_key = None
        self._widget_trace_filter = TopLevelWidgetTraceFilter(self)
        QApplication.instance().installEventFilter(self._widget_trace_filter)

        self._restore_geometry()
        self._init_ui()
        self._apply_window_behavior()
        self._create_menus()
        self._create_toolbars()
        self._create_dock_widgets()
        self._create_status_bar()
        self._setup_connections()
        self._setup_timers()

        if config.app.auto_connect:
            QTimer.singleShot(1200, self._auto_connect_coreldraw)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)

        sidebar_items = [(spec.key, spec.title) for spec in self._tool_specs]
        self.sidebar = Sidebar(sidebar_items)
        self.sidebar.setMinimumWidth(220)
        self.sidebar.setMaximumWidth(260)

        self.workspace_stack = QStackedWidget()

        self.context_host = QWidget()
        self.context_layout = QVBoxLayout(self.context_host)
        self.context_layout.setContentsMargins(0, 0, 0, 0)
        self.context_layout.setSpacing(0)
        self.context_host.setMinimumWidth(320)
        self.context_host.setMaximumWidth(380)
        self.default_context_panel = SafeContextPanel(self)
        self._set_context_widget(self.default_context_panel)

        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.workspace_stack)
        self.splitter.addWidget(self.context_host)
        self.splitter.setSizes([220, 930, 330])
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        root.addWidget(self.splitter)

        self.sidebar.tool_selected.connect(self._activate_tool)
        if self._tool_order:
            self._activate_tool(self._tool_order[0])

    def _build_tool_specs(self):
        return [
            ToolSpec("curve_filler", "Curve Filler", self._create_curve_filler_widget),
            ToolSpec("rhinestone", "Rhinestone Designer", self._create_rhinestone_widget),
            ToolSpec("hexagon", "Hexagon Designer", self._create_hexagon_widget),
            ToolSpec("photo_svg", "Photo Pointillizer", self._create_photo_svg_widget),
            ToolSpec("pattern_fill", "Pattern Fill", self._create_pattern_fill_widget),
            ToolSpec("batch_processor", "Batch Processor", self._create_batch_processor_widget),
            ToolSpec("object_tools", "Object Tools", self._create_object_tools_widget),
            ToolSpec("typography", "Typography", self._create_typography_widget),
        ]

    def _create_curve_filler_widget(self):
        from ..tools.curve_filler.curve_filler_widget import CurveFillerWidget

        return CurveFillerWidget(self)

    def _create_rhinestone_widget(self):
        from ..tools.rhinestone.rhinestone_widget import RhinestoneWidget

        return RhinestoneWidget(self)

    def _create_hexagon_widget(self):
        from ..tools.hexagon.hexagon_widget import HexagonWidget

        return HexagonWidget(self)

    def _create_photo_svg_widget(self):
        from ..tools.photo_to_rhinestone_svg.photo_to_rhinestone_svg_widget import PhotoToRhinestoneSvgWidget

        return PhotoToRhinestoneSvgWidget(self)

    def _create_pattern_fill_widget(self):
        from ..tools.pattern_fill.pattern_fill_widget import PatternFillWidget

        return PatternFillWidget(self)

    def _create_batch_processor_widget(self):
        from ..tools.batch_processor.batch_widget import BatchProcessorWidget

        return BatchProcessorWidget(self)

    def _create_object_tools_widget(self):
        from ..tools.object_manipulation.object_tools_widget import ObjectToolsWidget

        return ObjectToolsWidget(self)

    def _create_typography_widget(self):
        from ..tools.typography.typography_widget import TypographyWidget

        return TypographyWidget(self)

    def _create_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New Project", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.triggered.connect(self._new_project)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Project...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self._open_project)
        file_menu.addAction(open_action)

        save_action = QAction("&Save Project", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._save_project)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        self.recent_menu = QMenu("Recent Files", self)
        self._update_recent_files_menu()
        file_menu.addMenu(self.recent_menu)

        file_menu.addSeparator()

        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut(QKeySequence.Preferences)
        settings_action.triggered.connect(self._open_settings_dialog)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("&Edit")

        undo_action = QAction("&Undo", self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self._undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("&Redo", self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self._redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()
        edit_menu.addAction(settings_action)

        tools_menu = menubar.addMenu("&Tools")

        connect_action = QAction("Connect to CorelDRAW", self)
        connect_action.triggered.connect(self._connect_coreldraw)
        tools_menu.addAction(connect_action)

        disconnect_action = QAction("Disconnect from CorelDRAW", self)
        disconnect_action.triggered.connect(self._disconnect_coreldraw)
        tools_menu.addAction(disconnect_action)

        refresh_action = QAction("Refresh CorelDRAW", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_coreldraw)
        tools_menu.addAction(refresh_action)

        tools_menu.addSeparator()

        for spec in self._tool_specs:
            action = QAction(spec.title, self)
            action.triggered.connect(lambda checked=False, key=spec.key: self._activate_tool(key))
            tools_menu.addAction(action)

        presets_menu = menubar.addMenu("&Presets")

        save_preset_action = QAction("Save Current as Preset...", self)
        save_preset_action.triggered.connect(self._save_current_preset)
        presets_menu.addAction(save_preset_action)

        load_preset_action = QAction("Load Preset...", self)
        load_preset_action.triggered.connect(self._load_preset)
        presets_menu.addAction(load_preset_action)

        presets_menu.addSeparator()

        manage_presets_action = QAction("Manage Presets...", self)
        manage_presets_action.triggered.connect(self._manage_presets)
        presets_menu.addAction(manage_presets_action)

        import_preset_action = QAction("Import Preset...", self)
        import_preset_action.triggered.connect(self._import_preset)
        presets_menu.addAction(import_preset_action)

        export_preset_action = QAction("Export Selected Preset...", self)
        export_preset_action.triggered.connect(self._export_preset)
        presets_menu.addAction(export_preset_action)

        view_menu = menubar.addMenu("&View")

        self.toggle_context_panel_action = QAction("Right Info Panel", self, checkable=True)
        self.toggle_context_panel_action.setChecked(True)
        self.toggle_context_panel_action.toggled.connect(self._toggle_context_panel)
        view_menu.addAction(self.toggle_context_panel_action)

        self.toggle_preset_browser_action = QAction("Preset Browser", self, checkable=True)
        self.toggle_preset_browser_action.setChecked(False)
        self.toggle_preset_browser_action.toggled.connect(self._toggle_preset_browser)
        view_menu.addAction(self.toggle_preset_browser_action)

        help_menu = menubar.addMenu("&Help")

        help_contents_action = QAction("&Help Contents", self)
        help_contents_action.setShortcut("F1")
        help_contents_action.triggered.connect(self._show_help_contents)
        help_menu.addAction(help_contents_action)

        quick_start_action = QAction("&Quick Start Guide", self)
        quick_start_action.triggered.connect(self._show_quick_start)
        help_menu.addAction(quick_start_action)

        help_menu.addSeparator()

        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.setShortcut("Ctrl+/")
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        check_updates_action = QAction("Check for Updates...", self)
        check_updates_action.triggered.connect(self._check_updates)
        help_menu.addAction(check_updates_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_toolbars(self):
        self.main_toolbar = QToolBar("Main", self)
        self.main_toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.main_toolbar)

        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(self._connect_coreldraw)
        self.main_toolbar.addAction(connect_action)

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._refresh_coreldraw)
        self.main_toolbar.addAction(refresh_action)

        self.main_toolbar.addSeparator()

        presets_action = QAction("Presets", self)
        presets_action.triggered.connect(self._load_preset)
        self.main_toolbar.addAction(presets_action)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings_dialog)
        self.main_toolbar.addAction(settings_action)

        self.main_toolbar.addSeparator()

        help_action = QAction("Help", self)
        help_action.triggered.connect(self._show_help_contents)
        self.main_toolbar.addAction(help_action)

    def _create_dock_widgets(self):
        self.preset_dock = QDockWidget("Preset Browser", self)
        self.preset_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        placeholder = QLabel("Preset browser opens on demand.")
        placeholder.setContentsMargins(12, 12, 12, 12)
        self.preset_dock.setWidget(placeholder)
        self.preset_dock.visibilityChanged.connect(self._on_preset_dock_visibility_changed)
        self.addDockWidget(Qt.RightDockWidgetArea, self.preset_dock)
        self.preset_dock.hide()

    def _create_status_bar(self):
        status = QStatusBar()
        self.setStatusBar(status)

        self.connection_indicator = ConnectionIndicator()
        status.addPermanentWidget(self.connection_indicator)

        self.connection_label = QLabel("Not Connected")
        status.addWidget(self.connection_label)

        self.selection_label = QLabel("No Selection")
        status.addWidget(self.selection_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(220)
        self.progress_bar.setVisible(False)
        status.addPermanentWidget(self.progress_bar)

        version_label = QLabel("v0.1.0-beta")
        status.addPermanentWidget(version_label)

    def _setup_connections(self):
        self.connection_status_changed.connect(self._on_connection_status_changed)

    def _setup_timers(self):
        self.connection_timer = QTimer(self)
        self.connection_timer.timeout.connect(self._sync_connection_status)
        self.connection_timer.start(1000)

        self.selection_timer = QTimer(self)
        self.selection_timer.timeout.connect(self._update_selection_info)
        self.selection_timer.start(1500)

    def _connect_tool_signals(self, widget: ToolBaseWidget):
        if hasattr(widget, "status_message"):
            widget.status_message.connect(self._show_status_message)
        if hasattr(widget, "progress_updated"):
            widget.progress_updated.connect(self._update_progress)
        if hasattr(widget, "on_selection_changed"):
            self.selection_changed.connect(widget.on_selection_changed)

    def _activate_tool(self, key: str):
        if key not in self._tool_order:
            return
        self._pending_tool_key = key
        self._tool_switch_timer.start(20)

    def _finish_pending_tool_activation(self):
        key = self._pending_tool_key
        if key is None or key not in self._tool_order:
            return
        import time
        switch_started = time.perf_counter()
        self._pending_tool_key = None

        previous_widget = self._current_tool_widget()
        if previous_widget is not None and previous_widget is not self._tool_widgets.get(key):
            try:
                previous_widget.on_deactivate()
            except Exception as exc:
                logger.warning("Failed to deactivate tool %s: %s", self._current_tool_key, exc)

        widget = self._ensure_tool_widget(key)
        if widget is None:
            return

        self._current_tool_key = key
        self.workspace_stack.setCurrentWidget(widget)
        try:
            widget.on_activate()
        except Exception as exc:
            logger.warning("Failed to activate tool %s: %s", key, exc)
        spec = next((item for item in self._tool_specs if item.key == key), None)
        if spec:
            self.default_context_panel.set_tool(spec.title)
        self._set_context_widget(self._resolve_context_widget(widget))
        logger.info("tool-switch activated key=%s elapsed=%.2fms", key, (time.perf_counter() - switch_started) * 1000.0)
        QTimer.singleShot(35, lambda: self._refresh_current_tool_selection(force=False))

    def _ensure_tool_widget(self, key: str):
        if key in self._tool_widgets:
            return self._tool_widgets[key]

        spec = next((item for item in self._tool_specs if item.key == key), None)
        if spec is None:
            return None

        import time
        started = time.perf_counter()
        widget = spec.factory()
        logger.info("tool-widget created key=%s class=%s elapsed=%.2fms", key, widget.__class__.__name__, (time.perf_counter() - started) * 1000.0)
        self._tool_widgets[key] = widget
        self.workspace_stack.addWidget(widget)
        self._connect_tool_signals(widget)
        return widget

    def _current_tool_widget(self):
        if self._current_tool_key is None:
            return None
        return self._tool_widgets.get(self._current_tool_key)

    def _set_context_widget(self, widget: QWidget):
        if widget is None:
            widget = self.default_context_panel
        while self.context_layout.count():
            item = self.context_layout.takeAt(0)
            child = item.widget()
            if child:
                child.hide()
                if child is not widget:
                    child.setParent(None)
        if widget.parentWidget() is not self.context_host:
            widget.setParent(self.context_host)
        self.context_layout.addWidget(widget)
        widget.setVisible(True)

    def _resolve_context_widget(self, widget: QWidget) -> QWidget:
        if isinstance(widget, ToolBaseWidget):
            panel = widget.context_panel()
            if panel is not None:
                return panel
        return self.default_context_panel

    def _refresh_current_tool_selection(self, force: bool = False):
        if self._current_tool_key is None:
            return
        widget = self._tool_widgets.get(self._current_tool_key)
        if widget and hasattr(widget, "refresh_selection_state"):
            try:
                widget.refresh_selection_state(force=force)
            except Exception as exc:
                logger.warning("Failed to refresh tool selection state: %s", exc)

    def _auto_connect_coreldraw(self):
        try:
            corel.connect(config.app.preferred_corel_version)
            self._sync_connection_status(show_message=True, connected_message="Connected to CorelDRAW")
        except CorelDRAWConnectionError as exc:
            logger.info("Auto-connect failed: %s", exc)
            self.connection_status_changed.emit(False)
            self._show_status_message("CorelDRAW not running")

    def _connect_coreldraw(self):
        try:
            corel.connect(config.app.preferred_corel_version)
            self._sync_connection_status()
            self._refresh_current_tool_selection(force=True)
            QMessageBox.information(self, "Connected", f"Connected to CorelDRAW {corel.version}")
        except CorelDRAWConnectionError as exc:
            self.connection_status_changed.emit(False)
            QMessageBox.warning(self, "Connection Failed", str(exc))

    def _disconnect_coreldraw(self):
        corel.disconnect()
        self.connection_status_changed.emit(False)
        self._show_status_message("Disconnected from CorelDRAW")

    def _refresh_coreldraw(self):
        if corel.is_connected:
            corel.refresh()
            self._update_selection_info(force=True)
            self._show_status_message("CorelDRAW refreshed")
        else:
            self.connection_status_changed.emit(False)
            self._show_status_message("Not connected")

    def _on_connection_status_changed(self, connected: bool):
        self.connection_indicator.set_connected(connected)
        self.default_context_panel.set_connection(connected)
        if connected:
            self.connection_label.setText(f"Connected to CorelDRAW {corel.version}")
            self._update_selection_info(force=True)
        else:
            self.connection_label.setText("Not Connected")
            self.selection_label.setText("No Selection")
            self.default_context_panel.set_selection_text("No Selection")

    def _sync_connection_status(self, show_message: bool = False, connected_message: str = "Connected to CorelDRAW") -> bool:
        connected = corel.is_connected
        self.connection_status_changed.emit(connected)
        if show_message:
            self._show_status_message(connected_message if connected else "Not connected")
        return connected

    def _update_selection_info(self, force: bool = False):
        if not corel.is_connected:
            self.connection_status_changed.emit(False)
            self.selection_label.setText("No Selection")
            self.default_context_panel.set_selection_text("No Selection")
            return
        try:
            count = corel.get_selection_count()
            if count == 0:
                selection_text = "No Selection"
            elif count == 1:
                selection_text = "1 object selected"
            else:
                selection_text = f"{count} objects selected"
            self.selection_label.setText(selection_text)
            self.default_context_panel.set_selection_text(selection_text)
            self.selection_changed.emit(count)
            if force:
                self._refresh_current_tool_selection(force=True)
        except Exception:
            self.selection_label.setText("Selection unavailable")
            self.default_context_panel.set_selection_text("Selection unavailable")

    def _show_status_message(self, message: str, timeout: int = 4000):
        self.statusBar().showMessage(message, timeout)

    def _update_progress(self, value: int, maximum: int = 100):
        if value < 0:
            self.progress_bar.setVisible(False)
            return
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)

    def _new_project(self):
        for widget in self._tool_widgets.values():
            if hasattr(widget, "reset_to_defaults"):
                widget.reset_to_defaults()
        self._show_status_message("New project created")

    def _open_project(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(Path.home()),
            "Project Files (*.cdap);;All Files (*)",
        )
        if file_path:
            config.add_recent_file(file_path)
            self._update_recent_files_menu()
            self._show_status_message(f"Opened: {file_path}")

    def _save_project(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            str(Path.home()),
            "Project Files (*.cdap);;All Files (*)",
        )
        if file_path:
            config.add_recent_file(file_path)
            self._update_recent_files_menu()
            self._show_status_message(f"Saved: {file_path}")

    def _open_settings_dialog(self):
        dialog = SettingsDialog(self)
        dialog.exec_()
        app = QApplication.instance()
        theme_manager = getattr(app, "theme_manager", None) if app is not None else None
        if theme_manager is not None:
            theme_manager.refresh(self)
        self._apply_window_behavior()

    def _apply_window_behavior(self):
        """Apply window-level behavior that can be changed in Settings."""
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(config.app.always_on_top))
        self.show()

    def _update_recent_files_menu(self):
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        if not config.recent_files:
            action = QAction("No recent files", self)
            action.setEnabled(False)
            self.recent_menu.addAction(action)
            return

        for file_path in config.recent_files[: config.app.recent_files_limit]:
            action = QAction(Path(file_path).name, self)
            action.setToolTip(file_path)
            action.triggered.connect(lambda checked=False, fp=file_path: self._open_recent_file(fp))
            self.recent_menu.addAction(action)

    def _open_recent_file(self, file_path: str):
        if Path(file_path).exists():
            config.add_recent_file(file_path)
            self._update_recent_files_menu()
            self._show_status_message(f"Opened: {file_path}")
            return
        QMessageBox.warning(self, "File Not Found", f"The file no longer exists:\n{file_path}")

    def _undo(self):
        if not corel.is_connected:
            self._show_status_message("Not connected")
            return
        try:
            corel.app.ActiveDocument.Undo()
            self._show_status_message("Undo performed")
        except Exception:
            self._show_status_message("Nothing to undo")

    def _redo(self):
        if not corel.is_connected:
            self._show_status_message("Not connected")
            return
        try:
            corel.app.ActiveDocument.Redo()
            self._show_status_message("Redo performed")
        except Exception:
            self._show_status_message("Nothing to redo")

    def _on_preset_dock_visibility_changed(self, visible: bool):
        if visible:
            self._ensure_preset_browser()
        if hasattr(self, "toggle_preset_browser_action"):
            self.toggle_preset_browser_action.blockSignals(True)
            self.toggle_preset_browser_action.setChecked(visible)
            self.toggle_preset_browser_action.blockSignals(False)

    def _ensure_preset_browser(self):
        if self.preset_browser is not None:
            return
        from .widgets.preset_browser import PresetBrowser

        self.preset_browser = PresetBrowser(self)
        self.preset_browser.preset_selected.connect(self._apply_preset)
        self.preset_dock.setWidget(self.preset_browser)

    def _tool_key_from_preset_tool(self, tool_name: str) -> str:
        alias_map = {
            "curve_filler": "curve_filler",
            "rhinestone": "rhinestone",
            "hexagon": "hexagon",
            "photo_svg": "photo_svg",
            "pattern_fill": "pattern_fill",
            "batch": "batch_processor",
            "batch_processor": "batch_processor",
            "object": "object_tools",
            "object_tools": "object_tools",
            "typography": "typography",
        }
        return alias_map.get(tool_name, tool_name)

    def _preset_metadata_for_tool(self, tool_key: str):
        mapping = {
            "curve_filler": ("curve_filler", "curve_filler"),
            "rhinestone": ("rhinestone", "rhinestone"),
            "hexagon": ("hexagon", "custom"),
            "photo_svg": ("photo_svg", "custom"),
            "pattern_fill": ("pattern_fill", "custom"),
            "batch_processor": ("batch", "batch"),
            "object_tools": ("object", "object"),
            "typography": ("typography", "typography"),
        }
        return mapping.get(tool_key, (tool_key, "custom"))

    def _serialize_preset_value(self, value):
        if is_dataclass(value):
            return {key: self._serialize_preset_value(item) for key, item in asdict(value).items()}
        if hasattr(value, "value"):
            return value.value
        if isinstance(value, dict):
            return {key: self._serialize_preset_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._serialize_preset_value(item) for item in value]
        return value

    def _collect_preset_settings(self, widget):
        if hasattr(widget, "_config"):
            return self._serialize_preset_value(widget._config())
        if hasattr(widget, "_build_settings"):
            return self._serialize_preset_value(widget._build_settings())
        return None

    def _save_current_preset(self):
        widget = self._current_tool_widget()
        if widget is None:
            QMessageBox.information(self, "Presets", "Open a tool first.")
            return
        if hasattr(widget, "save_as_preset"):
            widget.save_as_preset()
            return
        settings = self._collect_preset_settings(widget)
        if not settings:
            QMessageBox.information(
                self,
                "Presets",
                "This tool does not expose preset saving yet in the current build. Existing presets can still be loaded and managed.",
            )
            return

        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return

        tool_name, category = self._preset_metadata_for_tool(self._current_tool_key or "")
        preset_manager.save_preset(
            name=name.strip(),
            tool=tool_name,
            settings=settings,
            category=category,
        )
        if self.preset_browser is not None:
            self.preset_browser.refresh()
        self._show_status_message(f"Preset '{name.strip()}' saved")

    def _load_preset(self):
        self._ensure_preset_browser()
        self.preset_dock.show()
        self.preset_dock.raise_()

    def _apply_preset(self, preset_id: str):
        preset_data = preset_manager.load_preset(preset_id)
        if not preset_data:
            QMessageBox.warning(self, "Preset", "Failed to load the selected preset.")
            return

        tool_key = self._tool_key_from_preset_tool(preset_data["metadata"].get("tool", ""))
        widget = self._ensure_tool_widget(tool_key)
        if widget is None:
            QMessageBox.warning(self, "Preset", f"No tool is registered for preset type '{tool_key}'.")
            return
        if not hasattr(widget, "apply_preset"):
            QMessageBox.information(self, "Preset", f"{preset_data['metadata'].get('name', 'Preset')} cannot be applied to this tool yet.")
            return

        widget.apply_preset(preset_data.get("settings", {}))
        self._activate_tool(tool_key)
        self._show_status_message(f"Preset '{preset_data['metadata'].get('name', 'Preset')}' applied")

    def _manage_presets(self):
        self._ensure_preset_browser()
        self.preset_dock.show()
        self.preset_dock.raise_()

    def _import_preset(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Preset",
            str(Path.home()),
            "Preset Files (*.json);;All Files (*)",
        )
        if not file_path:
            return
        preset_id = preset_manager.import_preset(Path(file_path))
        if not preset_id:
            QMessageBox.warning(self, "Import Failed", "Failed to import preset.")
            return
        self._ensure_preset_browser()
        self.preset_browser.refresh()
        self._show_status_message("Preset imported successfully")

    def _export_preset(self):
        self._ensure_preset_browser()
        self.preset_dock.show()
        self.preset_dock.raise_()
        self._show_status_message("Select a preset in the browser to manage export or file copy.")

    def _toggle_preset_browser(self, checked: bool):
        if checked:
            self._ensure_preset_browser()
        if self.preset_dock is not None:
            self.preset_dock.setVisible(checked)

    def _toggle_context_panel(self, visible: bool):
        self.context_host.setVisible(visible)

    def _show_help_contents(self):
        from .dialogs.help_dialog import HelpDialog

        dialog = HelpDialog(self)
        dialog.exec_()

    def _show_quick_start(self):
        self._show_help_contents()

    def _show_shortcuts(self):
        self._show_help_contents()

    def _check_updates(self):
        QMessageBox.information(self, "Check for Updates", "You are running v0.1.0-beta.")

    def _show_about(self):
        from .dialogs.about_dialog import AboutDialog

        dialog = AboutDialog(self)
        dialog.exec_()

    def _restore_geometry(self):
        width = config.app.window_width or 1480
        height = config.app.window_height or 900
        x = config.app.window_x
        y = config.app.window_y
        if x >= 0 and y >= 0:
            self.setGeometry(x, y, width, height)
        else:
            self.resize(width, height)

    def _save_geometry(self):
        if not self.isMaximized():
            config.app.window_width = self.width()
            config.app.window_height = self.height()
            config.app.window_x = self.x()
            config.app.window_y = self.y()

    def closeEvent(self, event):
        for key, widget in list(self._tool_widgets.items()):
            try:
                widget.on_tool_deactivated()
            except Exception as exc:
                logger.warning("Failed to deactivate tool %s during close: %s", key, exc)
        self._save_geometry()
        config.save()
        if corel.is_connected:
            corel.disconnect()
        event.accept()
