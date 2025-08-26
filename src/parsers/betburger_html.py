"""Betburger HTML parser stub.

Extracts basic page info and heuristically infers filter.
This first version is conservative: it looks at <title>, headers, and URL (from meta).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional
try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

from ..utils.logger import get_module_logger

logger = get_module_logger("betburger_html")


@dataclass
class ParsedItem:
    league: str = ""
    match: str = ""
    market: str = ""
    selection_a: str = ""
    odd_a: Optional[float] = None
    selection_b: str = ""
    odd_b: Optional[float] = None
    roi_pct: Optional[float] = None


@dataclass
class ParsedPage:
    platform: str = "betburger"
    filter_name_inferred: Optional[str] = None
    confidence: float = 0.0
    items: List[ParsedItem] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)


VALUEBET_TOKENS = ["valuebet", "valuebets"]
SUREBET_TOKENS = ["surebet", "surebets", "arbs", "arbitrage"]
PREMATCH_TOKENS = ["prematch", "pre-match", "pre match"]
LIVE_TOKENS = ["live", "in-play", "en vivo"]


def _infer_filter_by_text(text: str) -> Optional[str]:
    low = text.lower()
    is_value = any(t in low for t in VALUEBET_TOKENS)
    is_sure = any(t in low for t in SUREBET_TOKENS)
    is_live = any(t in low for t in LIVE_TOKENS)
    is_pre = any(t in low for t in PREMATCH_TOKENS)
    if is_value and is_pre:
        return "valuebets_prematch"
    if is_value and is_live:
        return "valuebets_live"
    if is_sure and is_pre:
        return "surebets_prematch"
    if is_sure and is_live:
        return "surebets_live"
    if is_value:
        return "valuebets"
    if is_sure:
        return "surebets"
    return None


def parse(html: str, url: str = "") -> ParsedPage:
    if BeautifulSoup is None:
        logger.warning("bs4 not installed; returning empty parse result")
        return ParsedPage(filter_name_inferred=None, confidence=0.0, items=[], signals=["no-bs4"])  # type: ignore

    soup = BeautifulSoup(html, "html.parser")
    signals: List[str] = []

    # Collect text signals from title and headers
    title = (soup.title.string if soup.title and soup.title.string else "").strip()
    if title:
        signals.append(f"title:{title}")
    for h in soup.find_all(["h1", "h2", "h3"]):
        t = (h.get_text(strip=True) or "")
        if t:
            signals.append(f"h:{t}")

    if url:
        signals.append(f"url:{url}")

    # Infer coarse filter
    joined = "|".join(signals)
    coarse = _infer_filter_by_text(joined)

    # map coarse -> profile keys if possible
    inferred: Optional[str] = None
    conf = 0.0
    if coarse == "valuebets_prematch":
        inferred = "bet365_valuebets"  # placeholder default; router will remap if present
        conf = 0.5
    elif coarse == "valuebets":
        inferred = "bet365_valuebets"
        conf = 0.4
    elif coarse == "surebets_prematch":
        inferred = "winamax-bet365"
        conf = 0.3
    elif coarse:
        inferred = coarse
        conf = 0.2

    # TODO: item extraction (future iteration)
    items: List[ParsedItem] = []

    return ParsedPage(
        platform="betburger",
        filter_name_inferred=inferred,
        confidence=conf,
        items=items,
        signals=signals,
    )
