"""
Single-process workflow for Surebet (Valuebets):
  1) Login to Surebet
  2) Navigate to Valuebets
  3) Duplicate tabs to SUREBET_TABS (default 3)
  4) Optionally select a saved filter per tab (SUREBET_TAB_<i>_FILTER_NAME)
  5) Parse visible valuebets and send to Telegram channels mapped per profile

Usage (WSL):
  python3 -m scripts.run_surebet_select_and_send_all

Env requirements (.env):
  SUREBET_USERNAME, SUREBET_PASSWORD, TELEGRAM_BOT_TOKEN
  SUREBET_TABS=3
  SUREBET_TAB_1_PROFILE_KEY, SUREBET_TAB_2_PROFILE_KEY, ... (must exist in config.yml -> surebet_profiles)
  Optional per tab UI filter: SUREBET_TAB_1_FILTER_NAME, ... (visible text of Surebet saved filter)

Notes:
- Uses SAME Selenium WebDriver session end-to-end.
- Channel resolution via ConfigManager.get_channel_for_profile('surebet', profile).
- If no items on a tab, we send a concise info message to the channel.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import List, Optional

# Ensure package imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.logger import get_module_logger  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.browser.tab_manager import TabManager  # type: ignore
from src.browser.auth_manager import AuthManager  # type: ignore
from src.browser.surebet_nav import select_saved_filter  # type: ignore
from src.processors.surebet_parser import parse_surebet_valuebets_html  # type: ignore
from src.utils.telegram_notifier import TelegramNotifier  # type: ignore
from src.utils.snapshots import write_snapshot, read_snapshot, compute_hash  # type: ignore

logger = get_module_logger("run_surebet_select_and_send_all")


def _get_env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)) or str(default))
    except Exception:
        return default


def _get_profile_for_tab(i: int) -> Optional[str]:
    return os.environ.get(f"SUREBET_TAB_{i}_PROFILE_KEY")


def _get_filter_for_tab(i: int) -> Optional[str]:
    return os.environ.get(f"SUREBET_TAB_{i}_FILTER_NAME")


def _duplicate_tabs_to(driver, target_count: int) -> None:
    assert target_count >= 1
    while len(driver.window_handles) < target_count:
        driver.execute_script("window.open(window.location.href, '_blank');")
        time.sleep(0.6)
    logger.info("Tabs ready", count=len(driver.window_handles))


def _send_info(notifier: TelegramNotifier, text: str, chat_id: Optional[str]) -> None:
    if chat_id:
        notifier.send_text(text, chat_id=chat_id)
    else:
        notifier.send_text(text)


def _abs_url(base: str, link: Optional[str]) -> Optional[str]:
    if not link:
        return None
    if link.startswith("http://") or link.startswith("https://"):
        return link
    if link.startswith("/"):
        return base.rstrip("/") + link
    return link


def _format_tab_summary(profile: str, tab_no: int, items: list[dict], base_url: str, top_k: int = 10) -> str:
    # Sort by value_pct desc if present
    def _val(it):
        v = it.get("value_pct")
        try:
            return float(v) if v is not None else -1e9
        except Exception:
            return -1e9

    items_sorted = sorted(items, key=_val, reverse=True)
    take = items_sorted[:top_k]

    lines: list[str] = []
    lines.append(f"[surebet] Resumen (perfil: {profile}, tab {tab_no}) — {len(items)} eventos, top {len(take)}")
    for it in take:
        sport = (it.get("sport") or "").title()
        market = it.get("market") or ""
        match = it.get("match") or ""
        value = it.get("value_pct")
        sel_a = it.get("selection_a") or {}
        a_bk = sel_a.get("bookmaker", "?")
        a_od = sel_a.get("odd", "?")
        link = _abs_url(base_url, it.get("target_link"))
        head = f"• {sport} • {market} — {match}"
        metric = f"{value:.2f}% VALUE" if isinstance(value, (int, float)) else ""
        lines.append(head)
        if metric:
            lines.append(f"  {metric}")
        lines.append(f"  {a_bk}: {a_od}")
        if link:
            lines.append(f"  Link: {link}")

    return "\n".join(lines)


def main() -> int:
    cfg = ConfigManager()

    # Default to headless when there is no DISPLAY (e.g., WSL without GUI)
    if not os.environ.get("DISPLAY") and not os.environ.get("BOT_HEADLESS"):
        os.environ["BOT_HEADLESS"] = "true"

    tm = TabManager(cfg.bot)
    if not tm.connect_to_existing_browser():
        logger.error("Unable to start/connect to Firefox")
        return 1

    notifier = TelegramNotifier()
    auth = AuthManager(cfg.bot)

    try:
        # 1) Login
        if not auth.ensure_authenticated(tm.driver, "surebet", cfg.surebet):
            logger.error("Surebet authentication failed")
            return 1

        # 2) Navigate to Valuebets
        target_url = cfg.surebet.valuebets_url or "https://es.surebet.com/valuebets"
        logger.info("Navigating to Surebet Valuebets", url=target_url)
        tm.driver.get(target_url)
        time.sleep(1.0)

        # 3) Duplicate tabs to N
        target_tabs = _get_env_int("SUREBET_TABS", 3)
        _duplicate_tabs_to(tm.driver, target_tabs)
        handles: List[str] = tm.driver.window_handles

        # Snapshot configuration
        snapshot_enabled = (os.environ.get("SNAPSHOT_ENABLED", "false").lower() == "true")
        snapshot_dir = Path(os.environ.get("SNAPSHOT_DIR", str(ROOT / "logs" / "html")))
        run_forever = (os.environ.get("RUN_FOREVER", "false").lower() == "true")
        interval_sec = _get_env_int("SNAPSHOT_INTERVAL_SEC", 60)

        last_hash_by_profile: dict[str, str] = {}

        def process_once() -> None:
            for tab_no in range(1, target_tabs + 1):
                profile_key = os.environ.get(f"SUREBET_TAB_{tab_no}_PROFILE_KEY")
                if not profile_key:
                    logger.warning("Missing profile for tab", tab=tab_no)
                    continue
                chat_id = cfg.get_channel_for_profile("surebet", profile_key)

                # Switch to tab and optionally select filter
                tm.driver.switch_to.window(handles[tab_no - 1])
                filter_name = os.environ.get(f"SUREBET_TAB_{tab_no}_FILTER_NAME")
                logger.info("Processing Surebet tab", tab=tab_no, profile=profile_key)

                if filter_name:
                    try:
                        select_saved_filter(tm.driver, filter_name)
                    except Exception as e:
                        logger.warning("Exception selecting filter", error=str(e))

                # Capture current page source
                html = tm.driver.page_source or ""

                # Optionally persist snapshot and read back from disk for parsing stability
                if snapshot_enabled:
                    try:
                        path = write_snapshot(html, snapshot_dir, "surebet", profile_key)
                        disk_html = read_snapshot(snapshot_dir, "surebet", profile_key) or html
                        snap_hash = compute_hash(disk_html)
                        # Dedup: if hash unchanged for this profile, skip sending
                        if last_hash_by_profile.get(profile_key) == snap_hash:
                            logger.info("No changes since last snapshot; skipping send", tab=tab_no, profile=profile_key)
                            continue
                        last_hash_by_profile[profile_key] = snap_hash
                        html_to_parse = disk_html
                    except Exception as e:
                        logger.warning("Snapshot write/read failed; parsing from memory", error=str(e))
                        html_to_parse = html
                else:
                    html_to_parse = html

                # Parse alerts from chosen HTML
                alerts = parse_surebet_valuebets_html(html_to_parse, profile=profile_key)

                if not alerts:
                    _send_info(notifier, f"[surebet] Sin eventos visibles (tab {tab_no}, perfil {profile_key}).", chat_id)
                    continue

                # Send a single concise summary per tab to avoid spam/flood
                summary = _format_tab_summary(
                    profile_key,
                    tab_no,
                    alerts,
                    cfg.surebet.base_url,
                    top_k=int(os.getenv("SUREBET_SUMMARY_TOP", "10")),
                )
                ok = notifier.send_text(summary, chat_id=chat_id)
                logger.info("Tab completed", tab=tab_no, profile=profile_key, sent=int(bool(ok)), total=len(alerts))

        if run_forever:
            logger.info("Entering persistent loop", interval_sec=interval_sec)
            while True:
                process_once()
                time.sleep(max(1, interval_sec))
        else:
            process_once()
            logger.info("Surebet single-process flow completed")
            return 0

    except Exception as e:
        logger.error("Surebet flow failed", error=str(e))
        return 1
    finally:
        # keep browser open for inspection; comment to auto-close
        pass


if __name__ == "__main__":
    raise SystemExit(main())
