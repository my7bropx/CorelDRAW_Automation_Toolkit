"""
Preset Management System
Handles saving, loading, importing, and exporting of tool presets.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import uuid

from ..config import config

logger = logging.getLogger(__name__)


@dataclass
class PresetMetadata:
    """Metadata for a preset."""
    id: str
    name: str
    description: str
    category: str
    tool: str
    version: str
    created: str
    modified: str
    author: str
    tags: List[str]
    is_favorite: bool = False


class PresetManager:
    """
    Manages presets for all tools in the application.
    Supports categories, favorites, import/export, and sharing.
    """

    def __init__(self, defer_load: bool = False):
        """Initialize the preset manager."""
        self._presets_dir = config.presets_directory
        self._ensure_directories()
        self._cache: Dict[str, Dict] = {}
        self._loaded = False
        if not defer_load:
            self._load_cache()
            self._loaded = True
        logger.info(f"Preset manager initialized. Presets dir: {self._presets_dir}")

    def _ensure_loaded(self):
        """Ensure preset cache is loaded."""
        if not self._loaded:
            self._load_cache()
            self._loaded = True

    def _ensure_directories(self):
        """Ensure preset directories exist."""
        categories = ['curve_filler', 'rhinestone', 'batch', 'object', 'typography', 'custom']
        for cat in categories:
            (self._presets_dir / cat).mkdir(parents=True, exist_ok=True)

    def _load_cache(self):
        """Load preset metadata into cache."""
        self._cache.clear()
        for preset_file in self._presets_dir.rglob("*.json"):
            try:
                with open(preset_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'metadata' in data:
                        preset_id = data['metadata'].get('id', preset_file.stem)
                        self._cache[preset_id] = {
                            'path': preset_file,
                            'metadata': data['metadata']
                        }
            except Exception as e:
                logger.warning(f"Failed to load preset {preset_file}: {e}")

    def save_preset(self, name: str, tool: str, settings: Dict[str, Any],
                   description: str = "", category: str = "custom",
                   tags: List[str] = None, author: str = "User") -> str:
        """
        Save a new preset.

        Args:
            name: Preset name.
            tool: Tool this preset is for (e.g., 'curve_filler').
            settings: Dictionary of tool settings.
            description: Preset description.
            category: Preset category.
            tags: List of tags.
            author: Author name.

        Returns:
            str: Preset ID.
        """
        self._ensure_loaded()
        preset_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        metadata = PresetMetadata(
            id=preset_id,
            name=name,
            description=description,
            category=category,
            tool=tool,
            version="1.0",
            created=now,
            modified=now,
            author=author,
            tags=tags or [],
            is_favorite=False
        )

        preset_data = {
            'metadata': asdict(metadata),
            'settings': settings
        }
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        preset_file = self._presets_dir / category / f"{safe_name}_{preset_id}.json"
        try:
            with open(preset_file, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)
            self._cache[preset_id] = {
                'path': preset_file,
                'metadata': asdict(metadata)
            }

            logger.info(f"Preset saved: {name} (ID: {preset_id})")
            return preset_id
        except Exception as e:
            logger.error(f"Failed to save preset: {e}")
            raise
    def load_preset(self, preset_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a preset by ID.
        Args:
            preset_id: The preset ID.
        Returns:
            Dictionary containing metadata and settings, or None if not found.
        """
        self._ensure_loaded()
        if preset_id not in self._cache:
            logger.warning(f"Preset not found: {preset_id}")
            return None
        preset_path = self._cache[preset_id]['path']
        try:
            with open(preset_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load preset {preset_id}: {e}")
            return None
    def update_preset(self, preset_id: str, settings: Dict[str, Any] = None,
                     metadata_updates: Dict[str, Any] = None) -> bool:
        """
        Update an existing preset.

        Args:
            preset_id: The preset ID.
            settings: New settings (optional).
            metadata_updates: Metadata fields to update (optional).

        Returns:
            bool: True if successful.
        """
        self._ensure_loaded()
        preset_data = self.load_preset(preset_id)
        if not preset_data:
            return False

        if settings:
            preset_data['settings'] = settings

        if metadata_updates:
            preset_data['metadata'].update(metadata_updates)

        preset_data['metadata']['modified'] = datetime.now().isoformat()

        try:
            preset_path = self._cache[preset_id]['path']
            with open(preset_path, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)

            self._cache[preset_id]['metadata'] = preset_data['metadata']
            logger.info(f"Preset updated: {preset_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update preset {preset_id}: {e}")
            return False

    def delete_preset(self, preset_id: str) -> bool:
        """
        Delete a preset.

        Args:
            preset_id: The preset ID.

        Returns:
            bool: True if deleted successfully.
        """
        self._ensure_loaded()
        if preset_id not in self._cache:
            return False

        try:
            preset_path = self._cache[preset_id]['path']
            preset_path.unlink()
            del self._cache[preset_id]
            logger.info(f"Preset deleted: {preset_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete preset {preset_id}: {e}")
            return False

    def get_presets_by_tool(self, tool: str) -> List[Dict[str, Any]]:
        """Get all presets for a specific tool."""
        self._ensure_loaded()
        result = []
        for preset_id, info in self._cache.items():
            if info['metadata'].get('tool') == tool:
                result.append({
                    'id': preset_id,
                    **info['metadata']
                })
        return sorted(result, key=lambda x: x.get('name', ''))

    def get_presets_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all presets in a category."""
        self._ensure_loaded()
        result = []
        for preset_id, info in self._cache.items():
            if info['metadata'].get('category') == category:
                result.append({
                    'id': preset_id,
                    **info['metadata']
                })
        return sorted(result, key=lambda x: x.get('name', ''))

    def get_favorites(self) -> List[Dict[str, Any]]:
        """Get all favorite presets."""
        self._ensure_loaded()
        result = []
        for preset_id, info in self._cache.items():
            if info['metadata'].get('is_favorite', False):
                result.append({
                    'id': preset_id,
                    **info['metadata']
                })
        return sorted(result, key=lambda x: x.get('name', ''))

    def toggle_favorite(self, preset_id: str) -> bool:
        """Toggle favorite status of a preset."""
        self._ensure_loaded()
        if preset_id not in self._cache:
            return False

        current = self._cache[preset_id]['metadata'].get('is_favorite', False)
        return self.update_preset(preset_id, metadata_updates={'is_favorite': not current})

    def search_presets(self, query: str, tool: str = None) -> List[Dict[str, Any]]:
        """
        Search presets by name, description, or tags.

        Args:
            query: Search query string.
            tool: Optional tool filter.

        Returns:
            List of matching preset metadata.
        """
        self._ensure_loaded()
        query_lower = query.lower()
        result = []

        for preset_id, info in self._cache.items():
            metadata = info['metadata']

            if tool and metadata.get('tool') != tool:
                continue

            # Search in name, description, and tags
            name_match = query_lower in metadata.get('name', '').lower()
            desc_match = query_lower in metadata.get('description', '').lower()
            tags = metadata.get('tags', [])
            tag_match = any(query_lower in tag.lower() for tag in tags)

            if name_match or desc_match or tag_match:
                result.append({
                    'id': preset_id,
                    **metadata
                })
        return sorted(result, key=lambda x: x.get('name', ''))
    def export_preset(self, preset_id: str, export_path: Path) -> bool:
        """
        Export a preset to a file.

        Args:
            preset_id: The preset ID.
            export_path: Path to export to.

        Returns:
            bool: True if exported successfully.
        """
        self._ensure_loaded()
        preset_data = self.load_preset(preset_id)
        if not preset_data:
            return False
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Preset exported to: {export_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export preset: {e}")
            return False
    def import_preset(self, import_path: Path) -> Optional[str]:
        """
        Import a preset from a file.

        Args:
            import_path: Path to import from.

        Returns:
            str: Imported preset ID, or None if failed.
        """
        self._ensure_loaded()
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
            if 'metadata' not in preset_data or 'settings' not in preset_data:
                logger.error("Invalid preset file format.")
                return None
            metadata = preset_data['metadata']
            new_id = self.save_preset(
                name=metadata.get('name', 'Imported'),
                tool=metadata.get('tool', 'custom'),
                settings=preset_data['settings'],
                description=metadata.get('description', ''),
                category=metadata.get('category', 'custom'),
                tags=metadata.get('tags', []),
                author=metadata.get('author', 'Imported')
            )

            logger.info(f"Preset imported from: {import_path}")
            return new_id

        except Exception as e:
            logger.error(f"Failed to import preset: {e}")
            return None

    def create_builtin_presets(self):
        """Create default built-in presets for all tools."""
        self._ensure_loaded()
        curve_filler_presets = [
            {
                'name': 'Basic Grid Fill',
                'description': 'Simple grid pattern with uniform spacing',
                'settings': {
                    'spacing_mode': 'fixed',
                    'spacing_value': 10.0,
                    'angle_mode': 'fixed',
                    'fixed_angle': 0.0,
                    'alignment': 'center',
                    'collision_detection': False
                },
                'tags': ['basic', 'grid', 'uniform']
            },
            {
                'name': 'Path Following',
                'description': 'Elements rotate to follow curve tangent',
                'settings': {
                    'spacing_mode': 'fixed',
                    'spacing_value': 15.0,
                    'angle_mode': 'follow_curve',
                    'alignment': 'center',
                    'collision_detection': True
                },
                'tags': ['path', 'tangent', 'rotate']
            },
            {
                'name': 'Decorative Scatter',
                'description': 'Randomized spacing and rotation for organic look',
                'settings': {
                    'spacing_mode': 'random',
                    'spacing_min': 8.0,
                    'spacing_max': 20.0,
                    'angle_mode': 'random',
                    'angle_min': 0,
                    'angle_max': 360,
                    'collision_detection': True
                },
                'tags': ['random', 'scatter', 'decorative']
            },
            {
                'name': 'Dense Fill',
                'description': 'High density with small spacing',
                'settings': {
                    'spacing_mode': 'fixed',
                    'spacing_value': 3.0,
                    'angle_mode': 'fixed',
                    'fixed_angle': 0.0,
                    'collision_detection': True
                },
                'tags': ['dense', 'tight', 'compact']
            },
            {
                'name': 'Gradient Scale',
                'description': 'Elements scale from small to large along path',
                'settings': {
                    'spacing_mode': 'percentage',
                    'spacing_percentage': 120,
                    'angle_mode': 'follow_curve',
                    'scale_mode': 'gradient',
                    'scale_start': 0.5,
                    'scale_end': 1.5
                },
                'tags': ['gradient', 'scale', 'growth']
            }
        ]
        rhinestone_presets = [
            {
                'name': 'SS10 Hexagonal Dense',
                'description': 'Standard SS10 stones in hexagonal pattern - dense fill',
                'settings': {
                    'stone_size': 'SS10',
                    'pattern': 'hexagonal',
                    'density': 0.9,
                    'min_gap': 0.3,
                    'gap_optimization': True,
                    'rotation': 0,
                    'random_rotation': False,
                },
                'tags': ['SS10', 'hex', 'dense', 'standard']
            },
            {
                'name': 'SS16 Hexagonal Standard',
                'description': 'Larger SS16 stones in hexagonal pattern',
                'settings': {
                    'stone_size': 'SS16',
                    'pattern': 'hexagonal',
                    'density': 0.85,
                    'min_gap': 0.5,
                    'gap_optimization': True,
                    'rotation': 0,
                    'random_rotation': False,
                },
                'tags': ['SS16', 'hex', 'large', 'standard']
            },
            {
                'name': 'SS6 Fine Detail',
                'description': 'Small SS6 stones for fine detail work',
                'settings': {
                    'stone_size': 'SS6',
                    'pattern': 'hexagonal',
                    'density': 0.8,
                    'min_gap': 0.2,
                    'gap_optimization': True,
                    'rotation': 0,
                    'random_rotation': False,
                },
                'tags': ['SS6', 'hex', 'fine', 'detail']
            },
            {
                'name': 'Random Scatter',
                'description': 'Randomly scattered stones for organic look',
                'settings': {
                    'stone_size': 'SS10',
                    'pattern': 'random',
                    'density': 0.6,
                    'min_gap': 0.5,
                    'gap_optimization': False,
                    'rotation': 0,
                    'random_rotation': True,
                },
                'tags': ['random', 'scatter', 'organic', 'decorative']
            },
            {
                'name': 'Circular Pattern',
                'description': 'Circular/radial pattern from center',
                'settings': {
                    'stone_size': 'SS10',
                    'pattern': 'circular',
                    'density': 0.85,
                    'min_gap': 0.3,
                    'gap_optimization': True,
                    'rotation': 0,
                    'random_rotation': False,
                },
                'tags': ['circular', 'radial', 'center', 'star']
            },
            {
                'name': 'Outline Border',
                'description': 'Stones placed along outline only',
                'settings': {
                    'stone_size': 'SS12',
                    'pattern': 'outline',
                    'density': 0.85,
                    'min_gap': 0.5,
                    'gap_optimization': True,
                    'rotation': 0,
                    'random_rotation': False,
                },
                'tags': ['outline', 'border', 'edge', 'frame']
            }
        ]
        for preset in curve_filler_presets:
            existing = self.search_presets(preset['name'], tool='curve_filler')
            if not existing:
                self.save_preset(
                    name=preset['name'],
                    tool='curve_filler',
                    settings=preset['settings'],
                    description=preset['description'],
                    category='curve_filler',
                    tags=preset['tags'],
                    author='CorelDRAW Automation Toolkit'
                )
        for preset in rhinestone_presets:
            existing = self.search_presets(preset['name'], tool='rhinestone')
            if not existing:
                self.save_preset(
                    name=preset['name'],
                    tool='rhinestone',
                    settings=preset['settings'],
                    description=preset['description'],
                    category='rhinestone',
                    tags=preset['tags'],
                    author='CorelDRAW Automation Toolkit'
                )
        logger.info("Built-in presets created.")
preset_manager = PresetManager(defer_load=True)
