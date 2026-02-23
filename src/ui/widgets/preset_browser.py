"""
Preset Browser Widget
Allows browsing, searching, and managing presets.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLineEdit, QComboBox, QLabel, QMenu, QAction,
    QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

from ...core.preset_manager import preset_manager
from ..icon_utils import apply_button_icons


class PresetBrowser(QWidget):
    """Browser widget for managing and selecting presets."""

    preset_selected = pyqtSignal(str)  # Emits preset ID
    preset_applied = pyqtSignal(str)   # Emits preset ID

    def __init__(self, parent=None):
        """Initialize the preset browser."""
        super().__init__(parent)
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search presets...")
        self.search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Filter by tool
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        filter_layout.addWidget(filter_label)

        self.tool_filter = QComboBox()
        self.tool_filter.addItem("All Tools", "")
        self.tool_filter.addItem("Curve Filler", "curve_filler")
        self.tool_filter.addItem("Rhinestone", "rhinestone")
        self.tool_filter.addItem("Batch Processor", "batch")
        self.tool_filter.addItem("Object Tools", "object")
        self.tool_filter.addItem("Typography", "typography")
        self.tool_filter.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.tool_filter)
        layout.addLayout(filter_layout)

        # Preset tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Name", "Tool", "Tags"])
        self.tree.setColumnWidth(0, 150)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 100)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree)

        # Action buttons
        button_layout = QHBoxLayout()

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._apply_selected)
        button_layout.addWidget(self.apply_btn)

        self.favorite_btn = QPushButton("Toggle Favorite")
        self.favorite_btn.clicked.connect(self._toggle_favorite)
        button_layout.addWidget(self.favorite_btn)

        layout.addLayout(button_layout)

        # Info section
        self.info_label = QLabel("Select a preset to see details")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("font-size: 10px; color: #888;")
        layout.addWidget(self.info_label)

        icon_map = {
            "apply": "apply.png",
            "toggle favorite": "action.png",
        }
        apply_button_icons(self, icon_map)

    def refresh(self):
        """Refresh the preset list."""
        self.tree.clear()

        tool_filter = self.tool_filter.currentData()
        search_text = self.search_input.text().strip()

        if search_text:
            presets = preset_manager.search_presets(search_text, tool_filter or None)
        elif tool_filter:
            presets = preset_manager.get_presets_by_tool(tool_filter)
        else:
            # Get all presets
            presets = []
            for tool in ['curve_filler', 'rhinestone', 'batch', 'object', 'typography']:
                presets.extend(preset_manager.get_presets_by_tool(tool))

        # Group by category
        categories = {}
        for preset in presets:
            cat = preset.get('category', 'custom')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(preset)

        # Add to tree
        for category, cat_presets in sorted(categories.items()):
            cat_item = QTreeWidgetItem([category.replace('_', ' ').title()])
            cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsSelectable)

            for preset in cat_presets:
                preset_item = QTreeWidgetItem([
                    ("★ " if preset.get('is_favorite') else "") + preset['name'],
                    preset['tool'].replace('_', ' ').title(),
                    ", ".join(preset.get('tags', [])[:3])
                ])
                preset_item.setData(0, Qt.UserRole, preset['id'])
                preset_item.setToolTip(0, preset.get('description', ''))
                cat_item.addChild(preset_item)

            self.tree.addTopLevelItem(cat_item)
            cat_item.setExpanded(True)

    def _on_search(self, text: str):
        """Handle search input changes."""
        self.refresh()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double-click on preset item."""
        preset_id = item.data(0, Qt.UserRole)
        if preset_id:
            self.preset_applied.emit(preset_id)

    def _get_selected_preset_id(self) -> str:
        """Get the ID of the selected preset."""
        current = self.tree.currentItem()
        if current:
            return current.data(0, Qt.UserRole)
        return None

    def _apply_selected(self):
        """Apply the selected preset."""
        preset_id = self._get_selected_preset_id()
        if preset_id:
            self.preset_selected.emit(preset_id)
        else:
            QMessageBox.warning(self, "No Selection", "Please select a preset to apply.")

    def _toggle_favorite(self):
        """Toggle favorite status of selected preset."""
        preset_id = self._get_selected_preset_id()
        if preset_id:
            preset_manager.toggle_favorite(preset_id)
            self.refresh()

    def _show_context_menu(self, pos):
        """Show context menu for preset actions."""
        item = self.tree.itemAt(pos)
        if not item:
            return

        preset_id = item.data(0, Qt.UserRole)
        if not preset_id:
            return

        menu = QMenu(self)

        apply_action = QAction("Apply Preset", self)
        apply_action.triggered.connect(lambda: self.preset_selected.emit(preset_id))
        menu.addAction(apply_action)

        menu.addSeparator()

        favorite_action = QAction("Toggle Favorite", self)
        favorite_action.triggered.connect(self._toggle_favorite)
        menu.addAction(favorite_action)

        rename_action = QAction("Rename...", self)
        rename_action.triggered.connect(lambda: self._rename_preset(preset_id))
        menu.addAction(rename_action)

        menu.addSeparator()

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self._delete_preset(preset_id))
        menu.addAction(delete_action)

        menu.exec_(self.tree.mapToGlobal(pos))

    def _rename_preset(self, preset_id: str):
        """Rename a preset."""
        preset_data = preset_manager.load_preset(preset_id)
        if not preset_data:
            return

        new_name, ok = QInputDialog.getText(
            self, "Rename Preset",
            "New name:",
            text=preset_data['metadata']['name']
        )
        if ok and new_name:
            preset_manager.update_preset(preset_id, metadata_updates={'name': new_name})
            self.refresh()

    def _delete_preset(self, preset_id: str):
        """Delete a preset."""
        reply = QMessageBox.question(
            self, "Delete Preset",
            "Are you sure you want to delete this preset?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            preset_manager.delete_preset(preset_id)
            self.refresh()
