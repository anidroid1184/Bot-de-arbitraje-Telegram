"""Surebet processors: Normalize Valuebets HTML into standard alert schema.

This wraps the snapshot parser in src.scrapers.surebet.parse_valuebets_html
and converts items to the unified schema expected by
src.formatters.telegram_message.format_alert_telegram.

Unified schema keys (subset):
- source: str ("surebet")
- profile: str
- value_pct: float | None
- sport: str | None
- market: str | None
- match: str | None
- selection_a: { bookmaker: str, odd: str }
- selection_b: { bookmaker: str, odd: str }  # optional/empty for valuebets
- target_link: str | None
"""
from __future__ import annotations

from typing import Any, Dict, List

from src.scrapers.surebet import parse_valuebets_html


def _norm_item(item: Dict[str, Any], profile: str) -> Dict[str, Any]:
    selection_a = {
        "bookmaker": item.get("bookmaker") or "?",
        "odd": item.get("odds") or "?",
    }
    # For Valuebets we typically only have a single side
    selection_b = {}

    norm: Dict[str, Any] = {
        "source": "surebet",
        "profile": profile,
        "value_pct": item.get("value_percent"),
        "sport": item.get("sport"),
        "market": item.get("market"),
        "match": item.get("event"),
        "selection_a": selection_a,
        "selection_b": selection_b,
        "target_link": item.get("link"),
    }
    return norm


essential_keys = [
    "source",
    "profile",
    "match",
]


def parse_surebet_valuebets_html(html: str, profile: str = "valuebets") -> List[Dict[str, Any]]:
    """Return a list of normalized alerts from a Surebet Valuebets snapshot."""
    raw_items = parse_valuebets_html(html, profile_name=profile) or []
    alerts: List[Dict[str, Any]] = []
    for it in raw_items:
        al = _norm_item(it, profile)
        # Minimal sanity filter: must have at least match or link/value
        if al.get("match") or al.get("value_pct") or al.get("target_link"):
            alerts.append(al)
    return alerts
