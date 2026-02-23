"""
Main Application Window
Central hub for all CorelDRAW automation tools.
"""

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QAction, QToolBar, QStatusBar, QLabel,
    QDockWidget, QListWidget, QMessageBox, QFileDialog,
    QProgressBar, QPushButton, QSplitter, QFrame, QApplication
)
from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon, QKeySequence

from ..config import config
from ..core.corel_interface import corel, CorelDRAWConnectionError
from ..core.preset_manager import preset_manager
from .icon_utils import apply_button_icons
from .widgets.connection_indicator import ConnectionIndicator

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window with tabbed interface for all tools."""

    connection_status_changed = pyqtSignal(bool)

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        self.setWindowTitle("CorelDRAW Automation Toolkit v0.1.0-beta")
        self.setMinimumSize(1200, 800)

        # Restore window geometry
        self._restore_geometry()

        # Initialize components
        self._init_ui()
        self._create_menus()
        self._create_toolbars()
        self._create_status_bar()
        self._create_dock_widgets()
        self._setup_connections()
        self._setup_timers()

        # Try to connect to CorelDRAW (delayed to allow UI to show first)
        if config.app.auto_connect:
            QTimer.singleShot(3000, self._auto_connect_coreldraw)

        logger.info("Main window initialized.")

    def _init_ui(self):
        """Initialize the main user interface."""
        # Central widget with tab interface
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Create tab widget for different tools
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setMinimumHeight(600)

        # Lazy-load tool widgets for faster startup
        self._tool_keys = [
            "curve_filler",
            "rhinestone",
            "batch_processor",
            "object_tools",
            "typography",
        ]
        self._tool_titles = {
            "curve_filler": "Curve Filler",
            "rhinestone": "Rhinestone Designer",
            "batch_processor": "Batch Processor",
            "object_tools": "Object Tools",
            "typography": "Typography",
        }
        self._tool_widgets = {}

        for key in self._tool_keys:
            placeholder = QFrame()
            placeholder_layout = QVBoxLayout(placeholder)
            placeholder_layout.setContentsMargins(10, 10, 10, 10)
            label = QLabel(f"Loading {self._tool_titles[key]}...")
            label.setStyleSheet("color: #aaa;")
            placeholder_layout.addWidget(label)
            placeholder_layout.addStretch()
            self.tab_widget.addTab(placeholder, self._tool_titles[key])

        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self._ensure_tool(self.tab_widget.currentIndex())

        main_layout.addWidget(self.tab_widget)

    def _create_tool_widget(self, key: str):
        """Create a tool widget on demand."""
        if key == "curve_filler":
            from ..tools.curve_filler.curve_filler_widget import CurveFillerWidget
            return CurveFillerWidget()
        if key == "rhinestone":
            from ..tools.rhinestone.rhinestone_widget import RhinestoneWidget
            return RhinestoneWidget()
        if key == "batch_processor":
            from ..tools.batch_processor.batch_widget import BatchProcessorWidget
            return BatchProcessorWidget()
        if key == "object_tools":
            from ..tools.object_manipulation.object_tools_widget import ObjectToolsWidget
            return ObjectToolsWidget()
        if key == "typography":
            from ..tools.typography.typography_widget import TypographyWidget
            return TypographyWidget()
        raise ValueError(f"Unknown tool key: {key}")

    def _connect_tool_signals(self, widget):
        """Connect tool widget signals to main window."""
        if hasattr(widget, "status_message"):
            widget.status_message.connect(self._show_status_message)
        if hasattr(widget, "progress_updated"):
            widget.progress_updated.connect(self._update_progress)

    def _ensure_tool(self, index: int):
        """Ensure the tool for a given tab index is created."""
        if index < 0 or index >= len(self._tool_keys):
            return
        key = self._tool_keys[index]
        if key in self._tool_widgets:
            return
        widget = self._create_tool_widget(key)
        self._tool_widgets[key] = widget

        # Replace placeholder tab
        self.tab_widget.removeTab(index)
        self.tab_widget.insertTab(index, widget, self._tool_titles[key])
        self.tab_widget.setCurrentIndex(index)
        self._connect_tool_signals(widget)

    def _on_tab_changed(self, index: int):
        """Lazy-create tool on first tab visit."""
        self._ensure_tool(index)

    def _get_tool_widget(self, key: str):
        """Get tool widget, creating it if needed."""
        if key not in self._tool_widgets:
            index = self._tool_keys.index(key)
            self._ensure_tool(index)
        return self._tool_widgets.get(key)

    def _create_menus(self):
        """Create application menus."""
        menubar = self.menuBar()

        # File Menu
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

        # Recent files submenu
        self.recent_menu = QMenu("Recent Files", self)
        self._update_recent_files_menu()
        file_menu.addMenu(self.recent_menu)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit Menu
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

        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)
        edit_menu.addAction(settings_action)

        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")

        connect_action = QAction("Connect to CorelDRAW", self)
        connect_action.triggered.connect(self._connect_coreldraw)
        tools_menu.addAction(connect_action)

        disconnect_action = QAction("Disconnect from CorelDRAW", self)
        disconnect_action.triggered.connect(self._disconnect_coreldraw)
        tools_menu.addAction(disconnect_action)

        tools_menu.addSeparator()

        refresh_action = QAction("Refresh CorelDRAW", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_coreldraw)
        tools_menu.addAction(refresh_action)

        # Presets Menu
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

        export_preset_action = QAction("Export Preset...", self)
        export_preset_action.triggered.connect(self._export_preset)
        presets_menu.addAction(export_preset_action)

        # View Menu
        view_menu = menubar.addMenu("&View")

        toggle_preset_browser = QAction("Preset Browser", self, checkable=True)
        toggle_preset_browser.setChecked(True)
        toggle_preset_browser.triggered.connect(self._toggle_preset_browser)
        view_menu.addAction(toggle_preset_browser)
        self.toggle_preset_browser_action = toggle_preset_browser

        view_menu.addSeparator()

        dark_theme_action = QAction("Dark Theme", self, checkable=True)
        dark_theme_action.setChecked(config.app.theme == "dark")
        dark_theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(dark_theme_action)
        self.dark_theme_action = dark_theme_action

        # Help Menu
        help_menu = menubar.addMenu("&Help")

        help_contents_action = QAction("&Help Contents", self)
        help_contents_action.setShortcut("F1")
        help_contents_action.triggered.connect(self._show_help_contents)
        help_menu.addAction(help_contents_action)

        quick_start_action = QAction("&Quick Start Guide", self)
        quick_start_action.triggered.connect(self._show_quick_start)
        help_menu.addAction(quick_start_action)

        help_menu.addSeparator()

        keyboard_shortcuts_action = QAction("&Keyboard Shortcuts", self)
        keyboard_shortcuts_action.setShortcut("Ctrl+/")
        keyboard_shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(keyboard_shortcuts_action)

        help_menu.addSeparator()

        check_updates_action = QAction("Check for Updates...", self)
        check_updates_action.triggered.connect(self._check_updates)
        help_menu.addAction(check_updates_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_toolbars(self):
        """Create application toolbars."""
        # Main toolbar
        main_toolbar = self.addToolBar("Main")
        main_toolbar.setMovable(False)
        main_toolbar.setIconSize(QSize(24, 24))

        # Connection indicator
        self.connection_indicator = ConnectionIndicator()
        main_toolbar.addWidget(self.connection_indicator)
        main_toolbar.addSeparator()

        # Get icon paths
        icons_path = Path(__file__).parent.parent / "resources" / "icons"
        
        # Quick action buttons with icons
        connect_btn = QPushButton("Connect")
        connect_icon_path = icons_path / "connect.png"
        if connect_icon_path.exists():
            connect_btn.setIcon(QIcon(str(connect_icon_path)))
        connect_btn.setToolTip("Connect to CorelDRAW")
        connect_btn.clicked.connect(self._connect_coreldraw)
        main_toolbar.addWidget(connect_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_icon_path = icons_path / "refresh.png"
        if refresh_icon_path.exists():
            refresh_btn.setIcon(QIcon(str(refresh_icon_path)))
        refresh_btn.setToolTip("Refresh CorelDRAW (F5)")
        refresh_btn.clicked.connect(self._refresh_coreldraw)
        main_toolbar.addWidget(refresh_btn)

        main_toolbar.addSeparator()

        # Quick preset access
        preset_label = QLabel("Quick Presets:")
        main_toolbar.addWidget(preset_label)

        self.quick_preset_btn = QPushButton("Load Preset")
        self.quick_preset_btn.clicked.connect(self._quick_load_preset)
        main_toolbar.addWidget(self.quick_preset_btn)

        main_toolbar.addSeparator()

        # Help button
        help_btn = QPushButton("Help")
        help_icon_path = icons_path / "help.png"
        if help_icon_path.exists():
            help_btn.setIcon(QIcon(str(help_icon_path)))
        help_btn.setToolTip("Open Help (F1)")
        help_btn.clicked.connect(self._show_help_contents)
        main_toolbar.addWidget(help_btn)

        icon_map = {
            "load preset": "action.png",
        }
        apply_button_icons(self, icon_map)

    def _create_status_bar(self):
        """Create the status bar."""
        self.status_bar = self.statusBar()

        # Connection status label
        self.connection_label = QLabel("Not Connected")
        self.status_bar.addWidget(self.connection_label)

        # Spacer
        spacer = QWidget()
        spacer.setFixedWidth(20)
        self.status_bar.addWidget(spacer)

        # Selection info
        self.selection_label = QLabel("No Selection")
        self.status_bar.addWidget(self.selection_label)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # Version label
        version_label = QLabel("v0.1.0-beta")
        self.status_bar.addPermanentWidget(version_label)

    def _create_dock_widgets(self):
        """Create dockable widgets."""
        # Preset browser dock
        self.preset_dock = QDockWidget("Preset Browser", self)
        self.preset_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.preset_browser = None
        placeholder = QLabel("Preset browser loading...")
        placeholder.setStyleSheet("color: #aaa; padding: 10px;")
        self.preset_dock.setWidget(placeholder)
        self.preset_dock.visibilityChanged.connect(self._on_preset_dock_visible)

        self.addDockWidget(Qt.RightDockWidgetArea, self.preset_dock)

    def _on_preset_dock_visible(self, visible: bool):
        """Lazy-create preset browser when dock is shown."""
        if not visible or self.preset_browser is not None:
            return
        from .widgets.preset_browser import PresetBrowser
        self.preset_browser = PresetBrowser()
        self.preset_browser.preset_selected.connect(self._apply_preset)
        self.preset_dock.setWidget(self.preset_browser)

    def _setup_connections(self):
        """Setup signal connections."""
        self.connection_status_changed.connect(self._on_connection_status_changed)
        # Tool signals are connected lazily when tools are created

    def _setup_timers(self):
        """Setup periodic timers."""
        # Auto-save timer
        if config.app.auto_save:
            self.auto_save_timer = QTimer(self)
            self.auto_save_timer.timeout.connect(self._auto_save)
            self.auto_save_timer.start(config.app.auto_save_interval * 1000)

        # Selection update timer
        self.selection_timer = QTimer(self)
        self.selection_timer.timeout.connect(self._update_selection_info)
        self.selection_timer.start(2000)  # Every 2 seconds

    def _restore_geometry(self):
        """Restore window size and position from config."""
        width = config.app.window_width or 1400
        height = config.app.window_height or 900
        x = config.app.window_x
        y = config.app.window_y
        
        if x >= 0 and y >= 0:
            self.setGeometry(x, y, width, height)
        else:
            self.resize(width, height)
        
        if config.app.window_maximized:
            self.showMaximized()

    def _save_geometry(self):
        """Save current window geometry to config."""
        if self.isMaximized():
            config.app.window_maximized = True
        else:
            config.app.window_maximized = False
            config.app.window_width = self.width()
            config.app.window_height = self.height()
            config.app.window_x = self.x()
            config.app.window_y = self.y()

    def _auto_connect_coreldraw(self):
        """Attempt to automatically connect to CorelDRAW."""
        try:
            corel.connect()
            self.connection_status_changed.emit(True)
            self._show_status_message("Connected to CorelDRAW")
        except CorelDRAWConnectionError as e:
            logger.info(f"Auto-connect failed: {e}")
            self._show_status_message("CorelDRAW not running - click Connect when ready")

    def _connect_coreldraw(self):
        """Connect to CorelDRAW."""
        try:
            corel.connect()
            self.connection_status_changed.emit(True)
            self._show_status_message(f"Connected to CorelDRAW {corel.version}")
            QMessageBox.information(
                self, "Connected",
                f"Successfully connected to CorelDRAW {corel.version}"
            )
        except CorelDRAWConnectionError as e:
            self.connection_status_changed.emit(False)
            QMessageBox.warning(
                self, "Connection Failed",
                f"Failed to connect to CorelDRAW:\n{e}\n\n"
                "Please ensure CorelDRAW is running."
            )

    def _disconnect_coreldraw(self):
        """Disconnect from CorelDRAW."""
        corel.disconnect()
        self.connection_status_changed.emit(False)
        self._show_status_message("Disconnected from CorelDRAW")

    def _refresh_coreldraw(self):
        """Refresh CorelDRAW display."""
        if corel.is_connected:
            corel.refresh()
            self._show_status_message("CorelDRAW refreshed")
        else:
            self._show_status_message("Not connected to CorelDRAW")

    def _on_connection_status_changed(self, connected: bool):
        """Handle connection status changes."""
        self.connection_indicator.set_connected(connected)
        if connected:
            self.connection_label.setText(f"Connected to CorelDRAW {corel.version}")
            self._update_selection_info()
        else:
            self.connection_label.setText("Not Connected")
            self.selection_label.setText("No Selection")

    def _update_selection_info(self):
        """Update selection information in status bar."""
        if not corel.is_connected:
            return

        try:
            count = corel.get_selection_count()
            if count == 0:
                self.selection_label.setText("No Selection")
            elif count == 1:
                self.selection_label.setText("1 object selected")
            else:
                self.selection_label.setText(f"{count} objects selected")
        except:
            self.selection_label.setText("Selection unavailable")

    def _show_status_message(self, message: str, timeout: int = 5000):
        """Show a message in the status bar."""
        self.status_bar.showMessage(message, timeout)

    def _update_progress(self, value: int, maximum: int = 100):
        """Update progress bar."""
        if value < 0:
            self.progress_bar.setVisible(False)
        else:
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(maximum)
            self.progress_bar.setValue(value)

    def _new_project(self):
        """Create a new project."""
        # Reset all tools to defaults
        for key in self._tool_keys:
            widget = self._get_tool_widget(key)
            if widget and hasattr(widget, "reset_to_defaults"):
                widget.reset_to_defaults()
        self._show_status_message("New project created")

    def _open_project(self):
        """Open an existing project."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Project",
            str(Path.home()),
            "Project Files (*.cdap);;All Files (*)"
        )
        if file_path:
            config.add_recent_file(file_path)
            self._update_recent_files_menu()
            self._show_status_message(f"Opened: {file_path}")

    def _save_project(self):
        """Save current project."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project",
            str(Path.home()),
            "Project Files (*.cdap);;All Files (*)"
        )
        if file_path:
            config.add_recent_file(file_path)
            self._update_recent_files_menu()
            self._show_status_message(f"Saved: {file_path}")

    def _update_recent_files_menu(self):
        """Update the recent files menu."""
        self.recent_menu.clear()
        for file_path in config.recent_files[:10]:
            action = QAction(Path(file_path).name, self)
            action.setData(file_path)
            action.triggered.connect(lambda checked, fp=file_path: self._open_recent_file(fp))
            self.recent_menu.addAction(action)

        if not config.recent_files:
            no_files = QAction("No recent files", self)
            no_files.setEnabled(False)
            self.recent_menu.addAction(no_files)

    def _open_recent_file(self, file_path: str):
        """Open a recent file."""
        if Path(file_path).exists():
            config.add_recent_file(file_path)
            self._update_recent_files_menu()
            self._show_status_message(f"Opened: {file_path}")
        else:
            QMessageBox.warning(
                self, "File Not Found",
                f"The file no longer exists:\n{file_path}"
            )

    def _undo(self):
        """Undo last action."""
        if corel.is_connected:
            try:
                corel.app.ActiveDocument.Undo()
                self._show_status_message("Undo performed")
            except:
                self._show_status_message("Nothing to undo")

    def _redo(self):
        """Redo last undone action."""
        if corel.is_connected:
            try:
                corel.app.ActiveDocument.Redo()
                self._show_status_message("Redo performed")
            except:
                self._show_status_message("Nothing to redo")

    def _show_settings(self):
        """Show settings dialog."""
        from .dialogs.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        if dialog.exec_():
            self._show_status_message("Settings saved")

    def _ensure_preset_browser(self):
        """Ensure preset browser is instantiated."""
        if self.preset_browser is None:
            self._on_preset_dock_visible(True)

    def _save_current_preset(self):
        """Save current tool settings as preset."""
        current_widget = self.tab_widget.currentWidget()
        if hasattr(current_widget, 'save_as_preset'):
            current_widget.save_as_preset()

    def _load_preset(self):
        """Load a preset."""
        # Show preset browser or dialog
        self._ensure_preset_browser()
        self.preset_dock.show()
        self.preset_dock.raise_()

    def _quick_load_preset(self):
        """Quick load favorite preset."""
        favorites = preset_manager.get_favorites()
        if favorites:
            # Load first favorite (could show a popup menu)
            self._apply_preset(favorites[0]['id'])
        else:
            self._show_status_message("No favorite presets available")

    def _apply_preset(self, preset_id: str):
        """Apply a preset to the current tool."""
        preset_data = preset_manager.load_preset(preset_id)
        if preset_data:
            tool = preset_data['metadata']['tool']
            settings = preset_data['settings']

            # Apply to appropriate tool
            if tool == 'curve_filler':
                widget = self._get_tool_widget("curve_filler")
                widget.apply_preset(settings)
                self.tab_widget.setCurrentWidget(widget)
            elif tool == 'rhinestone':
                widget = self._get_tool_widget("rhinestone")
                widget.apply_preset(settings)
                self.tab_widget.setCurrentWidget(widget)

            self._show_status_message(f"Preset '{preset_data['metadata']['name']}' applied")

    def _manage_presets(self):
        """Open preset management dialog."""
        self._ensure_preset_browser()
        self.preset_dock.show()
        self.preset_dock.raise_()

    def _import_preset(self):
        """Import a preset from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Preset",
            str(Path.home()),
            "Preset Files (*.json);;All Files (*)"
        )
        if file_path:
            preset_id = preset_manager.import_preset(Path(file_path))
            if preset_id:
                self._ensure_preset_browser()
                self.preset_browser.refresh()
                self._show_status_message(f"Preset imported successfully")
            else:
                QMessageBox.warning(self, "Import Failed", "Failed to import preset")

    def _export_preset(self):
        """Export a preset to file."""
        # Would show preset selection dialog first
        self._show_status_message("Select a preset to export from the Preset Browser")

    def _toggle_preset_browser(self, checked: bool):
        """Toggle preset browser visibility."""
        if checked:
            self._ensure_preset_browser()
        self.preset_dock.setVisible(checked)

    def _toggle_theme(self, dark: bool):
        """Toggle between dark and light theme."""
        from src.main import apply_theme
        app = QApplication.instance()
        if app:
            apply_theme(app, "dark" if dark else "light")
        config.app.theme = "dark" if dark else "light"
        config.save()

    def _show_help_contents(self):
        """Show comprehensive help dialog."""
        from .dialogs.help_dialog import HelpDialog
        dialog = HelpDialog(self)
        dialog.exec_()

    def _show_quick_start(self):
        """Show quick start guide."""
        from .dialogs.help_dialog import HelpDialog
        dialog = HelpDialog(self)
        dialog.exec_()

    def _show_shortcuts(self):
        """Show keyboard shortcuts."""
        from .dialogs.help_dialog import HelpDialog
        dialog = HelpDialog(self)
        dialog.exec_()

    def _check_updates(self):
        """Check for application updates."""
        QMessageBox.information(
            self, "Check for Updates",
            "You are running the latest version (v0.1.0-beta)"
        )

    def _show_about(self):
        """Show about dialog."""
        from .dialogs.about_dialog import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec_()

    def _auto_save(self):
        """Auto-save current work."""
        config.save()
        logger.debug("Auto-save completed")

    def closeEvent(self, event):
        """Handle window close event."""
        # Save window geometry
        self._save_geometry()
        
        # Save configuration
        config.save()

        # Disconnect from CorelDRAW
        if corel.is_connected:
            corel.disconnect()

        logger.info("Application closing.")
        event.accept()
