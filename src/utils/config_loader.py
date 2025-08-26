"""Config loader that reads your existing YAML without modifying it.

Search order:
1) ENV CONFIG_YAML if set
2) ./config/config.yml
3) ./deprecated/config-configurada.yml

Returns a dict with keys like 'betburger_profiles', 'surebet_profiles', 'defaults', etc.
Handles missing PyYAML gracefully.
"""
from __future__ import annotations

import os
import json
from typing import Any, Dict, Optional

from .logger import get_module_logger

logger = get_module_logger("config_loader")

_DEFAULT_CANDIDATES = [
    os.getenv("CONFIG_YAML", "").strip(),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "config.yml"),
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "deprecated", "config-configurada.yml"),
]


def _load_yaml(path: str) -> Optional[Dict[str, Any]]:
    try:
        import yaml  # type: ignore
    except Exception:
        logger.warning("PyYAML not installed; cannot read YAML config", path=path)
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            logger.warning("YAML root is not a mapping", path=path)
            return None
        return data
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error("Failed to read YAML config", path=path, error=str(e))
        return None


def load_config() -> Dict[str, Any]:
    """Load the first available config among candidates.

    Never raises; returns {} on failure.
    """
    for cand in _DEFAULT_CANDIDATES:
        if not cand:
            continue
        data = _load_yaml(cand)
        if data is not None:
            logger.info("Loaded YAML config", path=cand)
            return data
    logger.warning("No YAML config found; using empty config")
    return {}


def find_channel_id_for_filter(cfg: Dict[str, Any], platform: str, filter_key: str) -> Optional[str]:
    """Resolve channel_id from config by platform and filter key.

    Example:
      platform='betburger', filter_key='bet365_valuebets' -> cfg['betburger_profiles']['bet365_valuebets']['channel_id']
    """
    section = None
    if platform == "betburger":
        section = cfg.get("betburger_profiles", {})
    elif platform == "surebet":
        section = cfg.get("surebet_profiles", {})
    else:
        section = {}
    prof = section.get(filter_key) if isinstance(section, dict) else None
    if isinstance(prof, dict):
        cid = prof.get("channel_id")
        if cid:
            return str(cid)
    # fallback to defaults.notifications.error_channel
    defaults = cfg.get("defaults", {}) if isinstance(cfg, dict) else {}
    notif = defaults.get("notifications", {}) if isinstance(defaults, dict) else {}
    err = notif.get("error_channel")
    return str(err) if err else None
