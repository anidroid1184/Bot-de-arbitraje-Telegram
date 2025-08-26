"""Surebet HTML parser stub.

Heuristically extracts the selected filter and a minimal list of items.
Focuses on visible titles, sidebar labels, and simple patterns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

from ..utils.logger import get_module_logger

logger = get_module_logger("surebet_html")


@dataclass
class ParsedItem:
    league: str = ""
    match: str = ""
    market: str = ""
    selection: str = ""
    odd: Optional[float] = None
    value_pct: Optional[float] = None


@dataclass
class ParsedPage:
    platform: str = "surebet"
    filter_name_inferred: Optional[str] = None
    confidence: float = 0.0
    items: List[ParsedItem] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)


def parse(html: str, url: str = "") -> ParsedPage:
    signals: List[str] = []
    if BeautifulSoup is None:
        logger.warning("bs4 not installed; returning empty parse result")
        return ParsedPage(filter_name_inferred=None, confidence=0.0, items=[], signals=["no-bs4"])  # type: ignore

    soup = BeautifulSoup(html, "html.parser")

    title = (soup.title.string if soup.title and soup.title.string else "").strip()
    if title:
        signals.append(f"title:{title}")
    if url:
        signals.append(f"url:{url}")

    # Try to locate a sidebar label 'Filtro' and read nearby selected option text
    filter_name: Optional[str] = None
    sel_conf = 0.0
    try:
        # common patterns for a 'Filtro' select
        label = soup.find(lambda tag: tag.name in ("label", "div") and "filtro" in (tag.get_text(" ", strip=True) or "").lower())
        if label:
            # find first following select option[selected]
            sel = label.find_next("select")
            if sel:
                opt = sel.find("option", selected=True) or sel.find("option")
                if opt and opt.get_text(strip=True):
                    filter_name = opt.get_text(strip=True)
                    sel_conf = 0.6
    except Exception:
        pass

    # Fallback: look for visible headers indicating page type
    if not filter_name:
        headers = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]
        signals.extend([f"h:{h}" for h in headers])
        joined = "|".join(headers).lower()
        if "valuebets" in joined:
            filter_name = "ev-surebets"
            sel_conf = 0.4
        elif "apuestas seguras" in joined or "surebets" in joined:
            filter_name = "ev-surebets"
            sel_conf = 0.3

    return ParsedPage(
        platform="surebet",
        filter_name_inferred=filter_name,
        confidence=sel_conf,
        items=[],
        signals=signals,
    )
