"""
Scrape visible results from the first Betburger /es/arbs tab and send a compact summary
message to the Telegram channel mapped to the first tab's profile.

Usage (WSL):
  python3 -m scripts.betburger_send_first_tab_results

Env it uses:
  BETBURGER_TAB_1_PROFILE_KEY  -> resolves channel via config.yml
  TELEGRAM_SUPPORT_CHANNEL_ID  -> fallback channel

Notes:
- This reads the live DOM from the existing browser session opened by the smoke script.
- Parsing is heuristic/tolerant to minor UI changes and extracts top N entries.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import List, Tuple

# Imports setup
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup  # type: ignore

from src.utils.logger import get_module_logger  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.browser.tab_manager import TabManager  # type: ignore
from src.utils.telegram_notifier import TelegramNotifier  # type: ignore

logger = get_module_logger("betburger_send_first_tab_results")


def _extract_rows(html: str, max_items: int = 5) -> List[dict]:
    """Best-effort extraction of top arbitrage/valuebet rows from Betburger listing.

    Returns a list of dicts with keys: sport, match, meta, percent, books.
    This is intentionally tolerant and may not capture every field.
    """
    soup = BeautifulSoup(html, "lxml")

    # Find candidate blocks that contain a percent label (e.g., 1.00%)
    percent_re = re.compile(r"\b\d{1,2}(?:[\.,]\d{1,2})?\s*%\b")

    candidates = []
    for tag in soup.find_all(text=percent_re):
        try:
            el = tag.parent
            # climb to a row-like container: the nearest div/li with multiple inline spans/links
            row = el
            for _ in range(4):
                if row and row.name in ("li", "tr", "div") and (row.find_all("a") or row.find_all("span")):
                    break
                row = row.parent
            if not row:
                continue
            # collect visible text, collapse whitespace
            text = " ".join(row.get_text(" ", strip=True).split())
            # Deduplicate by normalized text
            candidates.append((row, text))
        except Exception:
            continue

    # Unique by text
    seen = set()
    uniq = []
    for row, text in candidates:
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((row, text))

    items = []
    for row, text in uniq[: max_items * 2]:  # sample extra, then trim later
        try:
            # Extract fields heuristically
            m_pct = percent_re.search(text)
            percent = m_pct.group(0) if m_pct else ""

            # Try to find a match name: often contains ' vs ' or hyphen with two teams
            m_match = re.search(r"([A-Za-z0-9\.\-\'\s]+\svs\s[A-Za-z0-9\.\-\'\s]+)|([A-Za-z0-9\.\-\'\s]+\s-\s[A-Za-z0-9\.\-\'\s]+)", text)
            match_name = m_match.group(0) if m_match else ""

            # Attempt to capture sport from nearby headings
            sport = ""
            try:
                head = row.find_previous(lambda t: t.name in ("h1","h2","h3","div","span") and ("Fútbol" in t.get_text() or "Football" in t.get_text() or "Tenis" in t.get_text() or "Tennis" in t.get_text()))
                if head:
                    sport = head.get_text(" ", strip=True)
            except Exception:
                pass

            # Bookmakers and odds: look for sequences like "bookie: odd"
            books = []
            for bk, odd in re.findall(r"([A-Za-z][A-Za-z0-9_\-\.]{2,})\s*[:\-]?\s*(\d{1,3}[\.,]\d{1,2})", text):
                books.append(f"{bk}:{odd}")
            books_line = ", ".join(books[:3])

            # Meta: pick some time/league hints if present
            m_time = re.search(r"\b\d{1,2}[:h]\d{2}\b|\b\d+\s*(min|minutes?)\b", text, flags=re.I)
            meta = m_time.group(0) if m_time else ""

            items.append({
                "sport": sport,
                "match": match_name,
                "percent": percent,
                "books": books_line,
                "meta": meta,
            })
        except Exception:
            continue

    return items[:max_items]


def _format_summary(items: List[dict]) -> str:
    lines = ["📢 Betburger | Resumen pestaña 1"]
    if not items:
        lines.append("No se detectaron eventos visibles.")
        return "\n".join(lines)
    for i, it in enumerate(items, 1):
        lines.append(
            f"{i}. {it.get('sport') or ''} {it.get('match') or ''}\n   {it.get('percent') or ''}  {it.get('books') or ''}  {it.get('meta') or ''}"
        )
    return "\n".join(lines)


def main() -> int:
    cfg = ConfigManager()
    tm = TabManager(cfg.bot)

    if not tm.connect_to_existing_browser():
        logger.error("Unable to connect to existing Firefox session")
        return 2

    try:
        handles = tm.driver.window_handles
        if not handles:
            logger.error("No browser tabs available")
            return 2
        tm.driver.switch_to.window(handles[0])
        time.sleep(0.5)
        if "/es/arbs" not in (tm.driver.current_url or ""):
            tm.driver.get("https://www.betburger.com/es/arbs")
            time.sleep(1.0)

        # Allow content to render
        time.sleep(1.0)
        html = tm.driver.page_source or ""
        items = _extract_rows(html, max_items=5)
        text = _format_summary(items)

        # Resolve channel: first tab's profile -> channel
        profile_key = os.getenv("BETBURGER_TAB_1_PROFILE_KEY", "").strip()
        channel_id = cfg.get_channel_for_profile("betburger", profile_key) if profile_key else None
        target = channel_id or cfg.get_support_channel()
        if not target:
            logger.error("No target channel resolved. Set BETBURGER_TAB_1_PROFILE_KEY or TELEGRAM_SUPPORT_CHANNEL_ID.")
            print(text)
            return 2

        notifier = TelegramNotifier()
        ok = notifier.send_text(text, chat_id=target)
        logger.info("Summary sent", ok=ok, target=target, items=len(items))
        return 0 if ok else 1
    finally:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
