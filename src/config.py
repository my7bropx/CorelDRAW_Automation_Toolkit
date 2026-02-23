"""
Application Configuration Module
Handles all application settings, preferences, and configuration management.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class AppSettings:
    """Application-wide settings."""
    theme: str = "dark"
    language: str = "en"
    auto_save: bool = True
    auto_save_interval: int = 300  # seconds
    recent_files_limit: int = 10
    show_tooltips: bool = True
    enable_animations: bool = True
    high_dpi_support: bool = True
    check_updates: bool = True
    auto_connect: bool = True  # Auto-connect to CorelDRAW on startup
    log_level: str = "INFO"
    workspace_path: str = ""
    plugin_directory: str = ""
    window_width: int = 1400
    window_height: int = 900
    window_x: int = -1
    window_y: int = -1
    window_maximized: bool = False
    macros_installed_hash: str = ""


@dataclass
class UnitSettings:
    """Unit and measurement preferences."""
    default_unit: str = "mm"  # mm, inches, pixels, points
    decimal_precision: int = 3
    use_system_units: bool = False


@dataclass
class CurveFillerSettings:
    """Settings specific to the Curve Filler tool."""
    default_spacing: float = 10.0
    default_angle_mode: str = "follow_curve"  # follow_curve, fixed, random
    default_fixed_angle: float = 0.0
    show_preview: bool = True
    preview_quality: str = "medium"  # low, medium, high
    collision_detection: bool = True
    smart_corner_handling: bool = True
    undo_steps: int = 50


@dataclass
class RhinestoneSettings:
    """Settings for Rhinestone Design tool."""
    default_stone_size: str = "SS10"
    default_pattern: str = "hexagonal"
    default_density: float = 0.8
    gap_optimization: bool = True
    enable_multi_size: bool = False


@dataclass
class BatchProcessorSettings:
    """Settings for Batch Processing."""
    watch_folder_enabled: bool = False
    watch_folder_path: str = ""
    auto_backup: bool = True
    backup_versions: int = 5
    parallel_processing: bool = True
    max_threads: int = 4


class ConfigurationManager:
    """
    Central configuration manager for the application.
    Handles loading, saving, and providing access to all settings.
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure single configuration instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the configuration manager."""
        if self._initialized:
            return

        self._initialized = True
        self._config_dir = self._get_config_directory()
        self._config_file = self._config_dir / "settings.json"
        self._presets_dir = self._config_dir / "presets"
        self._cache_dir = self._config_dir / "cache"

        # Initialize settings objects
        self.app = AppSettings()
        self.units = UnitSettings()
        self.curve_filler = CurveFillerSettings()
        self.rhinestone = RhinestoneSettings()
        self.batch_processor = BatchProcessorSettings()

        # Recent files list
        self.recent_files: list = []

        # Favorite presets
        self.favorite_presets: list = []

        # Custom hotkeys
        self.hotkeys: Dict[str, str] = {}

        # Initialize directories and load config
        self._ensure_directories()
        self.load()

        logger.info(f"Configuration manager initialized. Config dir: {self._config_dir}")

    def _get_config_directory(self) -> Path:
        """Get the application configuration directory."""
        if os.name == 'nt':  # Windows
            base = Path(os.environ.get('APPDATA', Path.home()))
        else:
            base = Path.home() / '.config'

        config_dir = base / 'CorelDRAW_Automation_Toolkit'
        return config_dir

    def _ensure_directories(self):
        """Ensure all required directories exist."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._presets_dir.mkdir(exist_ok=True)
        self._cache_dir.mkdir(exist_ok=True)
        (self._config_dir / 'plugins').mkdir(exist_ok=True)
        (self._config_dir / 'templates').mkdir(exist_ok=True)
        (self._config_dir / 'logs').mkdir(exist_ok=True)

    def load(self) -> bool:
        """
        Load configuration from disk.

        Returns:
            bool: True if loaded successfully, False otherwise.
        """
        try:
            if not self._config_file.exists():
                logger.info("No existing config file found. Using defaults.")
                self.save()  # Create default config
                return True

            with open(self._config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Load each section
            if 'app' in data:
                self.app = AppSettings(**data['app'])
            if 'units' in data:
                self.units = UnitSettings(**data['units'])
            if 'curve_filler' in data:
                self.curve_filler = CurveFillerSettings(**data['curve_filler'])
            if 'rhinestone' in data:
                self.rhinestone = RhinestoneSettings(**data['rhinestone'])
            if 'batch_processor' in data:
                self.batch_processor = BatchProcessorSettings(**data['batch_processor'])

            self.recent_files = data.get('recent_files', [])
            self.favorite_presets = data.get('favorite_presets', [])
            self.hotkeys = data.get('hotkeys', self._get_default_hotkeys())

            logger.info("Configuration loaded successfully.")
            return True

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False

    def save(self) -> bool:
        """
        Save current configuration to disk.

        Returns:
            bool: True if saved successfully, False otherwise.
        """
        try:
            data = {
                'app': asdict(self.app),
                'units': asdict(self.units),
                'curve_filler': asdict(self.curve_filler),
                'rhinestone': asdict(self.rhinestone),
                'batch_processor': asdict(self.batch_processor),
                'recent_files': self.recent_files[-self.app.recent_files_limit:],
                'favorite_presets': self.favorite_presets,
                'hotkeys': self.hotkeys,
            }

            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info("Configuration saved successfully.")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def reset_to_defaults(self):
        """Reset all settings to default values."""
        self.app = AppSettings()
        self.units = UnitSettings()
        self.curve_filler = CurveFillerSettings()
        self.rhinestone = RhinestoneSettings()
        self.batch_processor = BatchProcessorSettings()
        self.hotkeys = self._get_default_hotkeys()
        self.save()
        logger.info("Configuration reset to defaults.")

    def add_recent_file(self, file_path: str):
        """Add a file to the recent files list."""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        self.recent_files = self.recent_files[:self.app.recent_files_limit]
        self.save()

    def _get_default_hotkeys(self) -> Dict[str, str]:
        """Get default keyboard shortcuts."""
        return {
            'fill_curve': 'Ctrl+F',
            'preview': 'Ctrl+P',
            'undo': 'Ctrl+Z',
            'redo': 'Ctrl+Y',
            'advanced_fill': 'Ctrl+Shift+F',
            'save_preset': 'Ctrl+S',
            'load_preset': 'Ctrl+O',
            'toggle_preview': 'F5',
            'randomize': 'Ctrl+R',
            'settings': 'Ctrl+,',
        }

    @property
    def presets_directory(self) -> Path:
        """Get the presets directory path."""
        return self._presets_dir

    @property
    def cache_directory(self) -> Path:
        """Get the cache directory path."""
        return self._cache_dir

    @property
    def logs_directory(self) -> Path:
        """Get the logs directory path."""
        return self._config_dir / 'logs'

    @property
    def templates_directory(self) -> Path:
        """Get the templates directory path."""
        return self._config_dir / 'templates'

    @property
    def plugins_directory(self) -> Path:
        """Get the plugins directory path."""
        if self.app.plugin_directory:
            return Path(self.app.plugin_directory)
        return self._config_dir / 'plugins'


# Global configuration instance
config = ConfigurationManager()
