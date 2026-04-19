import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional

from .cache_manager import CacheManager

logger = logging.getLogger(__name__)


class ToolController:
    """Own cached preview/final state and keep preview/apply flows separate."""

    INVALIDATION_RULES = {
        "source": ["load_image", "background_mask", "layout_filter", "decimation", "image_sampling", "color_mapping", "size_assignment", "preview_render"],
        "tone": ["load_image", "background_mask", "decimation", "image_sampling", "color_mapping", "size_assignment", "preview_render"],
        "mask": ["background_mask", "layout_filter", "decimation", "image_sampling", "color_mapping", "size_assignment", "preview_render"],
        "layout": ["stone_layout", "layout_filter", "decimation", "image_sampling", "color_mapping", "size_assignment", "preview_render"],
        "decimation": ["decimation", "image_sampling", "color_mapping", "size_assignment", "preview_render"],
        "sampling": ["image_sampling", "color_mapping", "preview_render"],
        "color": ["color_mapping", "preview_render"],
        "size": ["size_assignment", "preview_render"],
        "view": ["preview_redraw"],
        "final_output": ["export_output", "import_output", "apply_output"],
    }

    def __init__(self, cache_manager: Optional[CacheManager] = None) -> None:
        self.cache = cache_manager or CacheManager()
        self._preview_state: Dict[str, Any] = {}
        self._final_state: Dict[str, Any] = {}

    def preview_result(self, cache_key: str):
        return self._preview_state.get(cache_key)

    def set_preview_result(self, cache_key: str, result: Any) -> Any:
        self._preview_state[cache_key] = result
        return result

    def final_result(self, cache_key: str):
        return self._final_state.get(cache_key)

    def set_final_result(self, cache_key: str, result: Any) -> Any:
        self._final_state[cache_key] = result
        return result

    def invalidate_results(self) -> None:
        self._preview_state.clear()
        self._final_state.clear()

    def affected_stages(self, change_scope: str):
        return list(self.INVALIDATION_RULES.get(change_scope, ["preview_render"]))
