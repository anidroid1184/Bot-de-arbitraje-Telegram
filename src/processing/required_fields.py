"""
Utilities to retrieve and validate required fields for alerts per profile
based on the channel configuration in src/config/config.yml.

Follows PEP8/PEP257 and avoids global state.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from src.config.settings import ConfigManager


def get_required_fields(cfg: ConfigManager, platform: str, profile: str) -> List[str]:
    """Return the list of required fields for the given platform/profile.

    Looks up src/config/config.yml under betburger_profiles/surebet_profiles.
    Returns an empty list if not found or not specified.
    """
    platform_key = "betburger_profiles" if platform == "betburger" else "surebet_profiles"
    prof = cfg.channels.get(platform_key, {}).get(profile, {})
    fields = prof.get("required_fields") or []
    raw = [str(f).strip() for f in fields if str(f).strip()]
    return _translate_required_fields(platform, raw)


def _translate_required_fields(platform: str, fields: List[str]) -> List[str]:
    """Translate generic YAML field names to actual alert schema keys.

    Handles expansions:
      - selection  -> selection_a.bookmaker, selection_b.bookmaker
      - odds       -> selection_a.odd, selection_b.odd

    Per-platform mappings:
      Betburger: event->match, start_time->event_start, roi->roi_pct
      Surebet:   event->match, start_time->event_start, value->value_pct, bookmaker->selection_a.bookmaker
    """
    translated: List[str] = []
    for f in fields:
        base = f.lower()
        # shared mappings
        if base == "event":
            translated.append("match")
            continue
        if base == "start_time":
            translated.append("event_start")
            continue
        if base == "selection":
            translated.extend(["selection_a.bookmaker", "selection_b.bookmaker"])
            continue
        if base == "odds":
            translated.extend(["selection_a.odd", "selection_b.odd"])
            continue

        if platform == "betburger":
            if base == "roi":
                translated.append("roi_pct")
                continue
        elif platform == "surebet":
            if base == "value":
                translated.append("value_pct")
                continue
            if base == "bookmaker":
                translated.append("selection_a.bookmaker")
                continue

        # default: keep as-is
        translated.append(f)
    return translated


def validate_alert_fields(alert: Dict, required_fields: Iterable[str]) -> Tuple[bool, List[str]]:
    """Validate that alert contains all required fields (non-empty / not None).

    A field may refer to nested keys using dot notation, e.g., "selection_a.bookmaker".

    Returns:
        (is_valid, missing_fields)
    """
    missing: List[str] = []
    for field in required_fields:
        if not _has_field(alert, field):
            missing.append(field)
    return (len(missing) == 0, missing)


def _has_field(obj: Dict, dotted: str) -> bool:
    cur: Optional[object] = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return False
        if part not in cur:
            return False
        cur = cur.get(part)
    # consider empty string or None as missing
    return cur is not None and cur != ""
