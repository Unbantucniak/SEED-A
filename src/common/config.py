from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import tomllib


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_config_paths() -> list[Path]:
    root = _project_root()
    return [root / "config.toml"]


def _load_from_path(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}

    suffix = path.suffix.lower()
    if suffix == ".toml":
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return data if isinstance(data, dict) else {}

    return {}


@lru_cache(maxsize=1)
def load_project_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load project config from TOML files (default: config.toml)."""
    if config_path:
        return _load_from_path(Path(config_path))

    for path in _default_config_paths():
        cfg = _load_from_path(path)
        if cfg:
            return cfg

    return {}


def get_config_section(section: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = load_project_config()
    value = cfg.get(section, default or {})
    return value if isinstance(value, dict) else (default or {})
