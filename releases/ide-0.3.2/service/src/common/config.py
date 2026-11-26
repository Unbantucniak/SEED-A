from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


# 加载.env环境变量文件（如果存在）
try:
    from dotenv import load_dotenv
    env_path = _project_root() / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)  # override=False表示不覆盖已有的系统环境变量
except ImportError:
    # 没有安装python-dotenv时忽略，直接使用系统环境变量
    pass


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
    data = value if isinstance(value, dict) else (default or {})

    # 统一读取环境变量，避免配置声明与运行行为脱节。
    if section == "llm":
        if "api_key" not in data or not data.get("api_key"):
            env_key = os.getenv("GLM_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            if env_key:
                data = {**data, "api_key": env_key}
        if "base_url" not in data or not data.get("base_url"):
            env_base_url = os.getenv("GLM_BASE_URL") or os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL")
            if env_base_url:
                data = {**data, "base_url": env_base_url}

    if section == "redis":
        env_redis_url = os.getenv("REDIS_URL")
        if env_redis_url and ("redis_url" not in data or not data.get("redis_url")):
            data = {**data, "redis_url": env_redis_url}

    return data
