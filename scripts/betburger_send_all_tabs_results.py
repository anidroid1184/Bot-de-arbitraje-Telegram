"""
Scrape visible results from ALL Betburger /es/arbs tabs and send summaries
to their respective Telegram channels based on profile mapping.

Usage (WSL):
  python3 -m scripts.betburger_send_all_tabs_results

Env it uses:
  BETBURGER_TAB_<i>_PROFILE_KEY  -> resolves channel via config.yml for each tab
  TELEGRAM_SUPPORT_CHANNEL_ID    -> fallback channel

Notes:
- Reads live DOM from existing browser session opened by smoke script
- Processes all available tabs (up to BETBURGER_TABS count)
- Sends formatted summary to each tab's mapped channel
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import List

# Imports setup
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup  # type: ignore

from src.utils.logger import get_module_logger  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.browser.tab_manager import TabManager  # type: ignore
from src.utils.telegram_notifier import TelegramNotifier  # type: ignore

logger = get_module_logger("betburger_send_all_tabs_results")


def _extract_rows(html: str, max_items: int = 5) -> List[dict]:
    """Extract top arbitrage/valuebet rows from Betburger listing."""
    soup = BeautifulSoup(html, "lxml")
    percent_re = re.compile(r"\b\d{1,2}(?:[\.,]\d{1,2})?\s*%\b")

    candidates = []
    for tag in soup.find_all(string=percent_re):
        try:
            el = tag.parent
            row = el
            for _ in range(4):
                if row and row.name in ("li", "tr", "div") and (row.find_all("a") or row.find_all("span")):
                    break
                row = row.parent
            if not row:
                continue
            text = " ".join(row.get_text(" ", strip=True).split())
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
    for row, text in uniq[: max_items * 2]:
        try:
            m_pct = percent_re.search(text)
            percent = m_pct.group(0) if m_pct else ""

            # Match name: contains ' vs ' or ' - '
            m_match = re.search(r"([A-Za-z0-9\.\-\'\s]+\svs\s[A-Za-z0-9\.\-\'\s]+)|([A-Za-z0-9\.\-\'\s]+\s-\s[A-Za-z0-9\.\-\'\s]+)", text)
            match_name = m_match.group(0) if m_match else ""

            # Sport header near the row
            sport = ""
            try:
                head = row.find_previous(lambda t: t.name in ("h1","h2","h3","div","span") and any(k in t.get_text() for k in ("Fútbol","Football","Tenis","Tennis")))
                if head:
                    sport = head.get_text(" ", strip=True)
            except Exception:
                pass

            # Bookmakers and odds
            books = []
            for bk, odd in re.findall(r"([A-Za-z][A-Za-z0-9_\-\.]{2,})\s*[:\-]?\s*(\d{1,3}[\.,]\d{1,2})", text):
                books.append(f"{bk}:{odd}")
            books_line = ", ".join(books[:3])

            # Meta time/league hints
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


def _format_summary(items: List[dict], tab_num: int, profile_key: str) -> str:
    lines = [f"📢 Betburger | Pestaña {tab_num} ({profile_key})"]
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

        total_tabs = int(os.getenv("BETBURGER_TABS", "6"))
        actual_tabs = min(total_tabs, len(handles))
        
        notifier = TelegramNotifier()
        success_count = 0

        for i in range(actual_tabs):
            tab_num = i + 1
            logger.info(f"Processing tab {tab_num}/{actual_tabs}")
            
            try:
                tm.driver.switch_to.window(handles[i])
                time.sleep(0.5)
                
                # Ensure we're on /es/arbs
                if "/es/arbs" not in (tm.driver.current_url or ""):
                    tm.driver.get("https://www.betburger.com/es/arbs")
                    time.sleep(1.0)

                # Get profile and channel for this tab
                profile_key = os.getenv(f"BETBURGER_TAB_{tab_num}_PROFILE_KEY", "").strip()
                if not profile_key:
                    logger.warning(f"No profile key for tab {tab_num}, skipping")
                    continue

                channel_id = cfg.get_channel_for_profile("betburger", profile_key)
                target = channel_id or cfg.get_support_channel()
                if not target:
                    logger.warning(f"No target channel for tab {tab_num} profile {profile_key}")
                    continue

                # Extract and send results
                time.sleep(1.0)  # Allow content to render
                html = tm.driver.page_source or ""
                items = _extract_rows(html, max_items=5)
                text = _format_summary(items, tab_num, profile_key)

                ok = notifier.send_text(text, chat_id=target)
                logger.info(f"Tab {tab_num} summary sent", ok=ok, target=target, items=len(items), profile=profile_key)
                
                if ok:
                    success_count += 1
                    
                time.sleep(0.5)  # Brief pause between tabs
                
            except Exception as e:
                logger.error(f"Error processing tab {tab_num}", error=str(e))
                continue

        logger.info(f"Completed processing all tabs", success=success_count, total=actual_tabs)
        return 0 if success_count > 0 else 1
        
    finally:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
