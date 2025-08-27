"""
Parser for Betburger HTML snapshots.

This is a heuristic parser that attempts to extract alerts from raw HTML snapshots
saved under logs/raw_html/betburger_*.html. It does not rely on heavy dependencies
and uses regex-based extraction to keep runtime light.

Output schema per alert (dict):
{
    "source": "betburger",
    "profile": str,
    "timestamp_utc": str (ISO),
    "sport": Optional[str],
    "league": Optional[str],
    "match": Optional[str],
    "market": Optional[str],
    "selection_a": {"bookmaker": str, "odd": float} | None,
    "selection_b": {"bookmaker": str, "odd": float} | None,
    "roi_pct": Optional[float],          # For Betburger
    "value_pct": None,                   # Reserved for Surebet parser
    "event_start": Optional[str],        # ISO string if available
    "target_link": Optional[str],
}

NOTE: Given page variability, this parser is best-effort. It logs what it finds
and returns an empty list if no alert-like patterns are detected.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


def _to_float(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", "."))
    except Exception:
        return None


def _iso_now() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def parse_betburger_html(html: str, profile: str = "profile_1") -> List[Dict[str, Any]]:
    """Parse a Betburger HTML snapshot and return a list of alert dicts.

    Heuristic approach:
    - Find blocks that look like matches/rows containing two odds and two bookmakers.
    - Extract ROI percentage if present (e.g., "3.4%" or "ROI 3.4%"), market, sport.

    Args:
        html: Raw HTML string from a Betburger tab
        profile: Profile name used to route alerts

    Returns:
        A list of alert dictionaries following the schema described above.
    """
    alerts: List[Dict[str, Any]] = []

    # Simple normalization to ease regex
    text = re.sub(r"\s+", " ", html)

    # Try to split potential alert cards by common separators (rows, cards, list-items)
    # This is a heuristic split to reduce false positives scope
    chunks = re.split(r"(?i)<(?:div|tr|li)[^>]*class=\"(?:row|card|item|arbitrage)[^\"]*\"[^>]*>", html)
    if len(chunks) < 2:
        # fallback: single-chunk parsing
        chunks = [html]

    # Regex patterns (heuristic)
    pat_sport = re.compile(r"(?i)\b(sport|deporte)[:\s]*([A-Za-z ]{3,30})")
    pat_market = re.compile(r"(?i)\b(1x2|match winner|ganador|over/under|total(?:s)?|handicap)\b")
    pat_roi = re.compile(r"(?i)(?:roi|value)[:\s]*([0-9]+(?:[\.,][0-9]+)?)%")
    pat_match = re.compile(r"(?i)([A-Za-z0-9 .,'\-/]{3,40})\s+vs\s+([A-Za-z0-9 .,'\-/]{3,40})")

    # bookmaker and odds: try to detect two pairs like "Pinnacle 1.85" and "Winamax 2.10"
    pat_book_odds = re.compile(
        r"(?i)([A-Za-z][A-Za-z0-9 _\-]{2,32})\D([0-9]+(?:[\.,][0-9]+)?)"
    )

    # link candidates (non-Pinnacle preferred but we don't enforce here)
    pat_link = re.compile(r"https?://[\w\-./?=&%#]+", re.I)

    found_count = 0
    for raw in chunks:
        t = re.sub(r"\s+", " ", raw)

        # Must contain at least two bookmaker-odd pairs to be considered
        pairs = pat_book_odds.findall(t)
        if len(pairs) < 2:
            continue

        # pick top two distinct pairs
        seen = []
        sel = []
        for bk, odd in pairs:
            key = (bk.strip().title(), odd)
            if key in seen:
                continue
            seen.append(key)
            sel.append((bk.strip().title(), _to_float(odd)))
            if len(sel) >= 2:
                break
        if len(sel) < 2:
            continue

        sport = None
        m_sport = pat_sport.search(t)
        if m_sport:
            sport = m_sport.group(2).strip().lower()

        market = None
        m_market = pat_market.search(t)
        if m_market:
            market = m_market.group(0).upper()

        roi = None
        m_roi = pat_roi.search(t)
        if m_roi:
            roi = _to_float(m_roi.group(1))

        match_name = None
        m_match = pat_match.search(t)
        if m_match:
            match_name = f"{m_match.group(1).strip()} vs {m_match.group(2).strip()}"

        link = None
        m_link = pat_link.search(t)
        if m_link:
            link = m_link.group(0)

        alert = {
            "source": "betburger",
            "profile": profile,
            "timestamp_utc": _iso_now(),
            "sport": sport,
            "league": None,
            "match": match_name,
            "market": market,
            "selection_a": {"bookmaker": sel[0][0], "odd": sel[0][1]},
            "selection_b": {"bookmaker": sel[1][0], "odd": sel[1][1]},
            "roi_pct": roi,
            "value_pct": None,
            "event_start": None,
            "target_link": link,
        }
        alerts.append(alert)
        found_count += 1

    if found_count == 0:
        logger.info("No alert-like blocks detected in Betburger HTML")
    else:
        logger.info("Parsed Betburger alerts", count=found_count)

    return alerts
