"""
Help Dialog
Comprehensive help and usage instructions for the application.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QTextEdit, QScrollArea, QListWidget,
    QListWidgetItem
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from ..icon_utils import apply_button_icons

class HelpDialog(QDialog):
    """Dialog showing comprehensive help and usage instructions."""

    def __init__(self, parent=None):
        """Initialize the help dialog."""
        super().__init__(parent)
        self.setWindowTitle("Help - CorelDRAW Automation Toolkit")
        self.setMinimumSize(800, 600)
        self._init_ui()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("CorelDRAW Automation Toolkit - Help")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Tab widget for help sections
        tabs = QTabWidget()

        # Quick Start tab
        tabs.addTab(self._create_quick_start(), "Quick Start")

        # Getting Started tab
        tabs.addTab(self._create_getting_started(), "Getting Started")

        # Curve Filler tab
        tabs.addTab(self._create_curve_filler_help(), "Curve Filler")

        # Presets tab
        tabs.addTab(self._create_presets_help(), "Presets")

        # Keyboard Shortcuts tab
        tabs.addTab(self._create_shortcuts_help(), "Shortcuts")

        # Troubleshooting tab
        tabs.addTab(self._create_troubleshooting(), "Troubleshooting")

        layout.addWidget(tabs)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

        apply_button_icons(self, {"close": "clear.png"})

    def _create_quick_start(self):
        """Create Quick Start tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>Quick Start Guide</h2>
        
        <h3>1. Launch the Application</h3>
        <ul>
            <li>Run CorelDRAW Automation Toolkit</li>
            <li>The application will automatically try to connect to CorelDRAW</li>
        </ul>
        
        <h3>2. Connect to CorelDRAW</h3>
        <ul>
            <li>Make sure CorelDRAW is running</li>
            <li>Click "Connect" in the toolbar if not connected</li>
            <li>Status indicator shows connection state (green = connected)</li>
        </ul>
        
        <h3>3. Using Curve Filler</h3>
        <ol>
            <li><b>Select a curve/path</b> in CorelDRAW that you want to fill</li>
            <li><b>Click "Set Container"</b> in the Curve Filler tab</li>
            <li><b>Select element(s)</b> to repeat along the path</li>
            <li><b>Click "Set Fill Elements"</b></li>
            <li><b>Adjust settings</b> (spacing, angle, pattern)</li>
            <li><b>Click "Fill Curve"</b> to execute</li>
        </ol>
        
        <h3>4. Saving Presets</h3>
        <ul>
            <li>Configure your desired settings</li>
            <li>Click "Save" in the Presets section</li>
            <li>Enter a name for your preset</li>
            <li>Load it later with one click</li>
        </ul>
        
        <h3>5. Tips</h3>
        <ul>
            <li>Use Preview to test settings before applying</li>
            <li>Enable collision detection to prevent overlaps</li>
            <li>Use "Follow Curve" angle mode for natural results</li>
            <li>Save your favorite settings as presets for quick access</li>
        </ul>
        """)
        layout.addWidget(text)
        return widget

    def _create_getting_started(self):
        """Create Getting Started tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>Getting Started</h2>
        
        <h3>System Requirements</h3>
        <ul>
            <li>Windows 10 or Windows 11 (64-bit)</li>
            <li>CorelDRAW 2018, 2019, 2020, 2021, 2022, 2023, or 2024</li>
            <li>4 GB RAM minimum (8 GB recommended)</li>
            <li>100 MB disk space</li>
        </ul>
        
        <h3>Installation</h3>
        <ol>
            <li>Download the installer (CorelDRAW_Automation_Toolkit_Setup_*.exe)</li>
            <li>Run the installer</li>
            <li>Follow the installation wizard</li>
            <li>Launch the application from Start Menu or Desktop shortcut</li>
        </ol>
        
        <h3>First Time Setup</h3>
        <ol>
            <li><b>Launch CorelDRAW first</b> - The automation toolkit needs CorelDRAW to be running</li>
            <li><b>Launch the Automation Toolkit</b></li>
            <li><b>Connect</b> - Click the Connect button if not auto-connected</li>
            <li><b>Test</b> - Open a document in CorelDRAW and try the Curve Filler</li>
        </ol>
        
        <h3>Interface Overview</h3>
        <ul>
            <li><b>Toolbar</b> - Quick access to connect, refresh, and presets</li>
            <li><b>Tab Widget</b> - Switch between different tools</li>
            <li><b>Preset Browser</b> - Dockable panel for managing presets</li>
            <li><b>Status Bar</b> - Shows connection status and selection info</li>
        </ul>
        
        <h3>Theme</h3>
        <p>Switch between dark and light themes via <b>View > Dark Theme</b></p>
        
        <h3>Settings</h3>
        <p>Access settings via <b>Edit > Settings</b> to configure:</p>
        <ul>
            <li>Auto-save interval</li>
            <li>Default spacing and angles</li>
            <li>Language and theme</li>
            <li>Recent files management</li>
        </ul>
        """)
        layout.addWidget(text)
        return widget

    def _create_curve_filler_help(self):
        """Create Curve Filler help tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>Curve Filler Tool</h2>
        
        <h3>Overview</h3>
        <p>The Curve Filler tool places selected elements along a path or curve at specified intervals. 
        It's perfect for creating borders, patterns, sequins, rhinestone designs, and more.</p>
        
        <h3>Basic Steps</h3>
        <ol>
            <li>Select a curve/path in CorelDRAW</li>
            <li>Click "Set Container" to define the path</li>
            <li>Select the element(s) to repeat</li>
            <li>Click "Set Fill Elements"</li>
            <li>Configure spacing and angle settings</li>
            <li>Click "Fill Curve"</li>
        </ol>
        
        <h3>Spacing Modes</h3>
        <ul>
            <li><b>Fixed Distance</b> - Place elements at exact intervals (e.g., every 10mm)</li>
            <li><b>Percentage</b> - Space as percentage of element size</li>
            <li><b>Auto-fit</b> - Automatically fit a specific number of elements</li>
            <li><b>Random</b> - Random spacing within a range (min/max)</li>
        </ul>
        
        <h3>Angle Modes</h3>
        <ul>
            <li><b>Follow Curve</b> - Elements rotate to follow path direction</li>
            <li><b>Fixed Angle</b> - All elements at the same angle</li>
            <li><b>Random</b> - Random rotation within a range</li>
            <li><b>Incremental</b> - Each element rotated by a set amount</li>
            <li><b>Perpendicular</b> - Elements perpendicular to path</li>
        </ul>
        
        <h3>Pattern Modes</h3>
        <ul>
            <li><b>Single Element</b> - Repeat the same element</li>
            <li><b>Sequence</b> - Use elements in order</li>
            <li><b>Random</b> - Random selection from elements</li>
            <li><b>Alternating</b> - Alternate between elements</li>
        </ul>
        
        <h3>Advanced Options</h3>
        <ul>
            <li><b>Collision Detection</b> - Prevents elements from overlapping</li>
            <li><b>Smart Corner Handling</b> - Better placement on sharp corners</li>
            <li><b>Start/End Padding</b> - Leave space at curve ends</li>
            <li><b>Offset from Curve</b> - Place elements away from path</li>
            <li><b>Scale Gradient</b> - Scale elements gradually along path</li>
        </ul>
        
        <h3>Post-Fill Operations</h3>
        <ul>
            <li><b>+10 / -10</b> - Quickly add or remove elements</li>
            <li><b>Group Results</b> - Group all placed elements</li>
            <li><b>Select All Placed</b> - Select all placed elements in CorelDRAW</li>
            <li><b>Clear All</b> - Remove all placed elements</li>
        </ul>
        """)
        layout.addWidget(text)
        return widget

    def _create_presets_help(self):
        """Create Presets help tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>Presets System</h2>
        
        <h3>What are Presets?</h3>
        <p>Presets save your tool settings so you can quickly apply them later. 
        They include spacing, angles, patterns, and other configuration options.</p>
        
        <h3>Saving a Preset</h3>
        <ol>
            <li>Configure your desired settings in the tool</li>
            <li>Click the "Save" button in the Presets section</li>
            <li>Enter a name for your preset</li>
            <li>Your preset is now saved and will appear in the Preset Browser</li>
        </ol>
        
        <h3>Loading a Preset</h3>
        <ul>
            <li><b>Method 1:</b> Double-click a preset in the Preset Browser</li>
            <li><b>Method 2:</b> Right-click > Apply</li>
            <li><b>Method 3:</b> Use Presets menu > Load Preset</li>
        </ul>
        
        <h3>Managing Presets</h3>
        <ul>
            <li><b>Favorites:</b> Star a preset to add it to favorites</li>
            <li><b>Search:</b> Use the search box to find presets by name</li>
            <li><b>Categories:</b> Presets are organized by tool type</li>
            <li><b>Delete:</b> Right-click > Delete to remove a preset</li>
        </ul>
        
        <h3>Importing Presets</h3>
        <ol>
            <li>Go to Presets > Import Preset</li>
            <li>Select a .json preset file</li>
            <li>The preset will be added to your library</li>
        </ol>
        
        <h3>Exporting Presets</h3>
        <ol>
            <li>Right-click a preset in the Preset Browser</li>
            <li>Select "Export"</li>
            <li>Choose a location and filename</li>
            <li>Share the .json file with others</li>
        </ol>
        
        <h3>Built-in Presets</h3>
        <p>The application comes with several built-in presets:</p>
        <ul>
            <li><b>Basic Grid Fill</b> - Simple uniform spacing</li>
            <li><b>Path Following</b> - Elements follow curve tangent</li>
            <li><b>Decorative Scatter</b> - Random placement for organic look</li>
            <li><b>Dense Fill</b> - High density with small spacing</li>
            <li><b>Gradient Scale</b> - Elements scale from small to large</li>
        </ul>
        """)
        layout.addWidget(text)
        return widget

    def _create_shortcuts_help(self):
        """Create Keyboard Shortcuts help tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>Keyboard Shortcuts</h2>
        
        <h3>General Shortcuts</h3>
        <table border="1" cellpadding="5">
            <tr><th>Action</th><th>Shortcut</th></tr>
            <tr><td>New Project</td><td>Ctrl+N</td></tr>
            <tr><td>Open Project</td><td>Ctrl+O</td></tr>
            <tr><td>Save Project</td><td>Ctrl+S</td></tr>
            <tr><td>Settings</td><td>Ctrl+,</td></tr>
            <tr><td>Undo</td><td>Ctrl+Z</td></tr>
            <tr><td>Redo</td><td>Ctrl+Y</td></tr>
            <tr><td>Refresh</td><td>F5</td></tr>
            <tr><td>Help</td><td>F1</td></tr>
        </table>
        
        <h3>Curve Filler Shortcuts</h3>
        <table border="1" cellpadding="5">
            <tr><th>Action</th><th>Shortcut</th></tr>
            <tr><td>Fill Curve</td><td>Ctrl+F</td></tr>
            <tr><td>Preview</td><td>Ctrl+P</td></tr>
            <tr><td>Toggle Preview</td><td>F5</td></tr>
            <tr><td>Randomize</td><td>Ctrl+R</td></tr>
            <tr><td>Advanced Fill</td><td>Ctrl+Shift+F</td></tr>
            <tr><td>Save Preset</td><td>Ctrl+S</td></tr>
            <tr><td>Load Preset</td><td>Ctrl+O</td></tr>
        </table>
        
        <h3>Quick Tips</h3>
        <ul>
            <li>Press <b>Ctrl+Click</b> on preset to apply</li>
            <li>Use <b>Mouse Wheel</b> to zoom in preview</li>
            <li><b>Double-click</b> presets in browser to apply</li>
        </ul>
        
        <h3>Customizing Shortcuts</h3>
        <p>Currently, keyboard shortcuts are fixed. Future versions will allow customization.</p>
        """)
        layout.addWidget(text)
        return widget

    def _create_troubleshooting(self):
        """Create Troubleshooting help tab content."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>Troubleshooting</h2>
        
        <h3>Connection Issues</h3>
        
        <h4>"Cannot connect to CorelDRAW"</h4>
        <ul>
            <li>Make sure CorelDRAW is running before starting the toolkit</li>
            <li>Try clicking "Connect" manually in the toolbar</li>
            <li>Check that CorelDRAW is not in safe mode or trial mode</li>
            <li>Try running both applications as Administrator</li>
            <li>Ensure you're using CorelDRAW 2018 or newer</li>
        </ul>
        
        <h4>"No documents open"</h4>
        <ul>
            <li>Open a document in CorelDRAW before using tools</li>
            <li>Create a new document if needed (File > New in CorelDRAW)</li>
        </ul>
        
        <h3>Curve Filler Issues</h3>
        
        <h4>"No elements placed"</h4>
        <ul>
            <li>Make sure you set both container and elements</li>
            <li>Check that spacing is not too large for the curve length</li>
            <li>Try reducing spacing value</li>
        </ul>
        
        <h4>"Elements overlap or collide"</h4>
        <ul>
            <li>Enable "Collision Detection" in Advanced Options</li>
            <li>Reduce spacing value</li>
            <li>Try different angle mode</li>
        </ul>
        
        <h4>"Elements not following curve"</h4>
        <ul>
            <li>Select "Follow Curve" angle mode</li>
            <li>Ensure your path is a curve (not a shape)</li>
            <li>Convert shapes to curves if needed</li>
        </ul>
        
        <h3>Preset Issues</h3>
        
        <h4>"Preset not applying"</h4>
        <ul>
            <li>Check you're on the correct tool tab</li>
            <li>Verify preset was created for the current tool</li>
            <li>Try resetting to defaults and reapplying</li>
        </ul>
        
        <h3>Application Issues</h3>
        
        <h4>"Application crashes"</h4>
        <ul>
            <li>Try running as Administrator</li>
            <li>Check for Windows updates</li>
            <li>Ensure all Windows Visual C++ runtimes are installed</li>
            <li>Try reinstalling the application</li>
        </ul>
        
        <h4>"Window displays incorrectly"</h4>
        <ul>
            <li>Try changing theme (View > Dark Theme toggle)</li>
            <li>Adjust window size - it should remember your preference</li>
            <li>Try on a different monitor if using multiple displays</li>
        </ul>
        
        <h3>Getting Help</h3>
        <ul>
            <li>Check the documentation in the docs folder</li>
            <li>Review CorelDRAW automation settings</li>
            <li>Ensure pywin32 is properly installed</li>
            <li>Check application logs for detailed error messages</li>
        </ul>
        
        <h3>Log Files</h3>
        <p>Log files are stored in:</p>
        <pre>%APPDATA%\\CorelDRAW_Automation_Toolkit\\logs\\</pre>
        <p>Check these files for detailed error information.</p>
        """)
        layout.addWidget(text)
        return widget
