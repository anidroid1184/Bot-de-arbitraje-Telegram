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
        return 2

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
        tabs = _get_env_int("SUREBET_TABS", 3)
        _duplicate_tabs_to(tm.driver, tabs)
        handles: List[str] = tm.driver.window_handles

        # 4) Iterate tabs, optionally select filter, parse and send
        for idx in range(tabs):
            tab_no = idx + 1
            profile_key = _get_profile_for_tab(tab_no)
            if not profile_key:
                logger.warning("Missing SUREBET_TAB_<i>_PROFILE_KEY; skipping tab", tab=tab_no)
                # Still switch to keep tabs warm
                tm.driver.switch_to.window(handles[idx])
                continue

            chat_id = cfg.get_channel_for_profile("surebet", profile_key)
            if not chat_id:
                logger.warning("No Telegram channel found for profile", profile=profile_key)

            tm.driver.switch_to.window(handles[idx])
            logger.info("Processing Surebet tab", tab=tab_no, profile=profile_key)

            # Optional filter selection by visible name
            filter_name = _get_filter_for_tab(tab_no)
            if filter_name:
                try:
                    ok = select_saved_filter(tm.driver, filter_name, timeout=cfg.bot.browser_timeout)
                    if not ok:
                        logger.warning("Filter selection failed", filter=filter_name, tab=tab_no)
                        _send_info(notifier, f"[surebet] No se pudo aplicar el filtro '{filter_name}' (tab {tab_no}, perfil {profile_key}).", chat_id)
                    else:
                        time.sleep(0.5)  # small settle time after filter
                except Exception as e:
                    logger.warning("Exception selecting filter", error=str(e))

            # Snapshot and parse
            html = tm.driver.page_source or ""
            alerts = parse_surebet_valuebets_html(html, profile=profile_key)

            if not alerts:
                _send_info(notifier, f"[surebet] Sin eventos visibles (tab {tab_no}, perfil {profile_key}).", chat_id)
                continue

            # Send a single concise summary per tab to avoid spam/flood
            summary = _format_tab_summary(profile_key, tab_no, alerts, cfg.surebet.base_url, top_k=int(os.getenv("SUREBET_SUMMARY_TOP", "10")))
            ok = notifier.send_text(summary, chat_id=chat_id)
            logger.info("Tab completed", tab=tab_no, profile=profile_key, sent=int(bool(ok)), total=len(alerts))

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
