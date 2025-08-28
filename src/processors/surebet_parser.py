"""Surebet processors: Normalize Valuebets HTML into standard alert schema.

This wraps the snapshot parser in src.scrapers.surebet.parse_valuebets_html
and converts items to the unified schema expected by
src.formatters.telegram_message.format_alert_telegram.

Unified schema keys (subset):
- source: str ("surebet")
- profile: str
- timestamp_utc: str (ISO UTC when parsed)
- value_pct: float | None
- sport: str | None
- league: str | None
- market: str | None
- match: str | None
- selection_a: { bookmaker: str, odd: str }
- selection_b: { bookmaker: str, odd: str }  # optional/empty for valuebets
- target_link: str | None
"""
from __future__ import annotations

from typing import Any, Dict, List
import datetime as dt

from scrapers.surebet import parse_valuebets_html


def _now_iso_utc() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class SurebetParser:
    """Parser for Surebet responses."""
    
    def process_response(self, response_data: Dict[str, Any], profile: str = None) -> List[Dict[str, Any]]:
        """Process Surebet response data."""
        if isinstance(response_data, str):
            return parse_surebet_html(response_data, profile or "valuebets")
        return []


def parse_surebet_html(html: str, profile: str = "valuebets") -> List[Dict[str, Any]]:
    """Parse Surebet HTML and return normalized alerts."""
    try:
        raw_items = parse_valuebets_html(html)
        return [_norm_item(item, profile) for item in raw_items]
    except Exception as e:
        logger.error("Failed to parse Surebet HTML", error=str(e))
        return []


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
        "timestamp_utc": _now_iso_utc(),
        "value_pct": item.get("value_percent"),
        "sport": item.get("sport"),
        "league": item.get("league"),
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
