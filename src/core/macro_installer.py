"""
Macro installer for CorelDRAW (.gms).
Copies bundled macros into CorelDRAW macro folders.
"""

import hashlib
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MacroInstallResult:
    installed: int
    targets: List[Path]
    source: Optional[Path]
    skipped: bool
    reason: str


def _get_resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def _get_macro_source_dir() -> Optional[Path]:
    override = os.environ.get("CDAT_MACRO_SOURCE")
    if override:
        p = Path(override)
        return p if p.exists() else None
    resources_root = _get_resource_root()
    candidate = resources_root / "resources" / "macros"
    return candidate if candidate.exists() else None


def _hash_macro_files(files: Iterable[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted(files):
        h.update(path.name.lower().encode("utf-8"))
        try:
            h.update(path.read_bytes())
        except Exception:
            continue
    return h.hexdigest()


def _iter_corel_macro_dirs(root: Path, max_depth: int = 5) -> Iterable[Path]:
    if not root.exists():
        return []
    results = []
    root = root.resolve()
    root_depth = len(root.parts)
    for current, dirs, _files in os.walk(root):
        depth = len(Path(current).parts) - root_depth
        if depth > max_depth:
            dirs[:] = []
            continue
        if Path(current).name.lower() == "gms":
            results.append(Path(current))
    return results


def _find_corel_macro_dirs() -> List[Path]:
    roots = []
    for env_name in ("APPDATA", "LOCALAPPDATA", "PROGRAMDATA"):
        env_val = os.environ.get(env_name)
        if env_val:
            roots.append(Path(env_val))

    candidate_roots = []
    for base in roots:
        candidate_roots.append(base / "Corel")
        candidate_roots.append(base / "Corel Corporation")
        candidate_roots.append(base / "CorelDRAW")

    macro_dirs = []
    for root in candidate_roots:
        macro_dirs.extend(_iter_corel_macro_dirs(root))

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for d in macro_dirs:
        key = str(d).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(d)
    return unique


def install_macros_if_needed(config) -> MacroInstallResult:
    """
    Install bundled .gms macros into CorelDRAW macro folders.
    Uses config.app.macros_installed_hash to avoid repeated installs.
    """
    source_dir = _get_macro_source_dir()
    if not source_dir:
        return MacroInstallResult(0, [], None, True, "no_source_dir")

    macro_files = list(source_dir.glob("*.gms"))
    if not macro_files:
        return MacroInstallResult(0, [], source_dir, True, "no_macros_found")

    current_hash = _hash_macro_files(macro_files)
    if getattr(config.app, "macros_installed_hash", "") == current_hash:
        return MacroInstallResult(0, [], source_dir, True, "already_installed")

    target_dirs = _find_corel_macro_dirs()
    if not target_dirs:
        return MacroInstallResult(0, [], source_dir, True, "no_corel_macro_dirs")

    installed_count = 0
    for target in target_dirs:
        try:
            target.mkdir(parents=True, exist_ok=True)
            for macro in macro_files:
                dest = target / macro.name
                dest.write_bytes(macro.read_bytes())
                installed_count += 1
        except Exception as e:
            logger.warning(f"Failed to install macros to {target}: {e}")

    if installed_count > 0:
        config.app.macros_installed_hash = current_hash
        try:
            config.save()
        except Exception as e:
            logger.warning(f"Failed to persist macro install state: {e}")

    return MacroInstallResult(installed_count, target_dirs, source_dir, False, "installed")

