"""Surebet snapshot parser (Valuebets)

Parses saved HTML snapshots from Surebet Valuebets into a normalized list of dicts.
Designed to be resilient to minor DOM changes and safe to run even if selectors
need future adjustment (returns empty list instead of crashing).

Usage (module):
    from src.scrapers.surebet import parse_valuebets_html

Notes:
- This parser works on HTML snapshots (BeautifulSoup + lxml). It does not require Selenium.
- We keep the schema minimal and stable. Fields can be extended later as needed.
- If the DOM changes, please provide a snapshot and we'll tune the selectors.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import re

# Optional: use structlog if available in the project
import structlog
logger = structlog.get_logger("surebet_scraper")


@dataclass
class ValuebetItem:
    source: str  # "surebet"
    profile: str  # e.g., "valuebets"
    event: Optional[str]
    sport: Optional[str]
    league: Optional[str]
    market: Optional[str]
    bookmaker: Optional[str]
    odds: Optional[str]
    value_percent: Optional[float]
    link: Optional[str]

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(strip=True)) if el else ""


def _find_first(soup: BeautifulSoup, selectors: List[str]):
    for sel in selectors:
        found = soup.select_one(sel)
        if found:
            return found
    return None


def parse_valuebets_html(html: str, profile_name: str = "valuebets") -> List[Dict]:
    """Parse Surebet Valuebets HTML snapshot into a list of normalized dicts.

    Args:
        html: Raw HTML content from logs/raw_html/surebet_*.html
        profile_name: Logical profile label (used for channel mapping later)

    Returns:
        List of dicts with normalized fields.
    """
    items: List[ValuebetItem] = []

    try:
        soup = BeautifulSoup(html or "", "lxml")

        # Heuristics for containers that likely hold valuebets rows/cards
        # We try multiple patterns to be resilient
        containers = soup.select(
            ", ".join(
                [
                    "div.valuebets",
                    "section.valuebets",
                    "div[class*='valuebet']",
                    "div[class*='bet-card']",
                    "div[class*='value-card']",
                    "table.valuebets, table[class*='value']",
                ]
            )
        )

        # If not found, scan for generic rows that include keywords
        if not containers:
            containers = [soup]

        # Candidate rows/cards within containers
        row_selectors = [
            "div.valuebet, div.value-bet, div.bet-card, li.valuebet-item",
            "tr",
        ]

        for container in containers:
            rows = []
            for rs in row_selectors:
                rows = container.select(rs)
                if rows:
                    break

            for row in rows:
                # Try find key fields with multiple selectors
                event = _text(
                    _find_first(
                        row,
                        [
                            ".event-name",
                            ".match, .event, .teams, .fixture",
                            "[data-testid='event-name']",
                        ],
                    )
                ) or None

                sport = _text(
                    _find_first(
                        row,
                        [
                            ".sport, .sport-name",
                            "[data-testid='sport']",
                        ],
                    )
                ) or None

                league = _text(
                    _find_first(
                        row,
                        [
                            ".league, .tournament, .competition",
                            "[data-testid='league']",
                        ],
                    )
                ) or None

                market = _text(
                    _find_first(
                        row,
                        [
                            ".market, .market-name",
                            "[data-testid='market']",
                        ],
                    )
                ) or None

                bookmaker = _text(
                    _find_first(
                        row,
                        [
                            ".bookmaker, .bookie, .operator",
                            "img[alt][src*='logo'] + span",
                            "[data-testid='bookmaker']",
                        ],
                    )
                ) or None

                odds_text = _text(
                    _find_first(
                        row,
                        [
                            ".odds, .price, .quote, .coef",
                            "[data-testid='odds']",
                        ],
                    )
                ) or None

                # Value percent may appear like "12%" or "+12%" or just a number
                value_percent = None
                vp_el = _find_first(
                    row,
                    [
                        ".value, .value-percent, .roi, .edge",
                        "[data-testid='value']",
                    ],
                )
                if vp_el:
                    m = re.search(r"([+\-]?\d+[\.,]?\d*)%", _text(vp_el))
                    if m:
                        try:
                            value_percent = float(m.group(1).replace(",", "."))
                        except ValueError:
                            value_percent = None

                link_el = _find_first(
                    row,
                    [
                        "a[href*='http']",
                        "a[href]",
                    ],
                )
                link = link_el.get("href") if link_el else None

                # If we have at least event and odds or value, consider it a valid row
                core_ok = event or odds_text or value_percent is not None
                if not core_ok:
                    continue

                items.append(
                    ValuebetItem(
                        source="surebet",
                        profile=profile_name,
                        event=event,
                        sport=sport,
                        league=league,
                        market=market,
                        bookmaker=bookmaker,
                        odds=odds_text,
                        value_percent=value_percent,
                        link=link,
                    )
                )

    except Exception as e:
        logger.error("parse_valuebets_html failed", error=str(e))
        return []

    logger.info("Parsed valuebets items", count=len(items))
    return [it.to_dict() for it in items]
