import hashlib
import json
import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class CacheManager:
    """Stage-level in-memory cache with readable hit/miss logging."""

    def __init__(self) -> None:
        self._store: Dict[Tuple[str, str], Any] = {}
        self._stats = {"hits": 0, "misses": 0, "stage_hits": {}, "stage_misses": {}}

    def build_key(self, stage: str, payload: Any) -> str:
        if is_dataclass(payload):
            payload = asdict(payload)
        serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        digest = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
        return f"{stage}:{digest}"

    def get(self, stage: str, key: str) -> Optional[Any]:
        hit = (stage, key) in self._store
        if hit:
            self._stats["hits"] += 1
            self._stats["stage_hits"][stage] = self._stats["stage_hits"].get(stage, 0) + 1
        else:
            self._stats["misses"] += 1
            self._stats["stage_misses"][stage] = self._stats["stage_misses"].get(stage, 0) + 1
        logger.debug("cache %s %s", "hit" if hit else "miss", key)
        return self._store.get((stage, key))

    def set(self, stage: str, key: str, value: Any) -> Any:
        self._store[(stage, key)] = value
        return value

    def invalidate_stage(self, stage: str) -> None:
        keys = [item for item in self._store if item[0] == stage]
        for item in keys:
            self._store.pop(item, None)

    def clear(self) -> None:
        self._store.clear()

    def snapshot_stats(self) -> Dict[str, Any]:
        return {
            "hits": int(self._stats["hits"]),
            "misses": int(self._stats["misses"]),
            "stage_hits": dict(self._stats["stage_hits"]),
            "stage_misses": dict(self._stats["stage_misses"]),
        }
