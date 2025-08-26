"""Routing utilities: map ParsedPage (platform, inferred filter) -> Telegram channel.

Uses the existing YAML config via config_loader.load_config and
config_loader.find_channel_id_for_filter.
"""
from __future__ import annotations

from typing import Optional

from ..utils.logger import get_module_logger
from ..utils.config_loader import load_config, find_channel_id_for_filter

logger = get_module_logger("router")


def resolve_channel(platform: str, inferred_filter_key: Optional[str]) -> Optional[str]:
    cfg = load_config()
    if inferred_filter_key:
        cid = find_channel_id_for_filter(cfg, platform=platform, filter_key=inferred_filter_key)
        if cid:
            return cid
    # Fallback to defaults.notifications.error_channel
    defaults = cfg.get("defaults", {}) if isinstance(cfg, dict) else {}
    notif = defaults.get("notifications", {}) if isinstance(defaults, dict) else {}
    err = notif.get("error_channel")
    return str(err) if err else None
