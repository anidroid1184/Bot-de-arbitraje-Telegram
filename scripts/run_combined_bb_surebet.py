"""
Combined single-process workflow:
  1) Betburger: login, /es/arbs, duplicate tabs, send results.
  2) Surebet: ensure auth, /valuebets, duplicate tabs, snapshot (optional), parse, send per-tab summary.

Usage:
  python3 -m scripts.run_combined_bb_surebet

Env:
  - Betburger: BETBURGER_USERNAME, BETBURGER_PASSWORD, BETBURGER_TABS, BETBURGER_TAB_<i>_PROFILE_KEY
  - Surebet: SUREBET_TABS, SUREBET_TAB_<i>_PROFILE_KEY, optional SUREBET_TAB_<i>_FILTER_NAME
  - Telegram: TELEGRAM_BOT_TOKEN
  - Snapshots (optional): SNAPSHOT_ENABLED, SNAPSHOT_DIR, SNAPSHOT_INTERVAL_SEC (not used here), RUN_FOREVER (ignored here)
  - Formatting: SUREBET_SUMMARY_TOP
"""
from __future__ import annotations

import os
import sys
import time
import json
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
from scripts.smoke_betburger_arbs_tabs import (  # type: ignore
    login_with_remember_me,
    duplicate_tabs_to as bb_duplicate_tabs_to,
)
from scripts.betburger_send_all_tabs_results import (  # type: ignore
    send_all_tabs_with_driver,
)
from scripts.process_snapshots import process_file as process_snapshot_file  # type: ignore

logger = get_module_logger("run_combined_bb_surebet")


def _get_env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)) or str(default))
    except Exception:
        return default


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

    try:
        # ========= Betburger phase =========
        username = cfg.betburger.username
        password = cfg.betburger.password
        login_url = cfg.betburger.login_url

        # Try to go directly to target page. If redirected to sign_in, then login.
        target_url_bb = "https://www.betburger.com/es/arbs"
        logger.info("Navigating to Betburger page", url=target_url_bb)
        tm.driver.get(target_url_bb)
        time.sleep(1.0)

        cur = tm.driver.current_url or ""
        if "/users/sign_in" in cur:
            logger.info("Sign-in required. Proceeding to login form")
            if not (username and password):
                logger.error("Missing BETBURGER credentials in .env")
                return 1
            login_with_remember_me(
                tm.driver,
                username,
                password,
                login_url,
                timeout=max(30, cfg.bot.browser_timeout),
            )
            # Ensure we land on arbs after login
            tm.driver.get(target_url_bb)
            time.sleep(1.0)
        else:
            logger.info("Already authenticated on Betburger; skipping login")

        tabs_bb = int(os.environ.get("BETBURGER_TABS", "6") or "6")
        bb_duplicate_tabs_to(tm.driver, tabs_bb)
        logger.info("Betburger tabs ensured", count=len(tm.driver.window_handles))

        rc = send_all_tabs_with_driver(tm.driver, cfg)
        if rc != 0:
            logger.error("Betburger send step finished with non-zero code", return_code=rc)
            return rc

        # ========= Surebet phase =========
        notifier = TelegramNotifier()
        auth = AuthManager(cfg.bot)
        if not auth.ensure_authenticated(tm.driver, "surebet", cfg.surebet):
            logger.error("Surebet authentication failed")
            return 1

        target_url_sb = cfg.surebet.valuebets_url or "https://es.surebet.com/valuebets"
        logger.info("Navigating to Surebet Valuebets", url=target_url_sb)
        tm.driver.get(target_url_sb)
        time.sleep(1.0)

        target_tabs = _get_env_int("SUREBET_TABS", 3)
        # Ensure we have at least target_tabs by opening new ones of current url
        while len(tm.driver.window_handles) < target_tabs:
            tm.driver.execute_script("window.open(window.location.href, '_blank');")
            time.sleep(0.6)
        handles: List[str] = tm.driver.window_handles
        logger.info("Surebet tabs ready", count=len(handles))

        # Snapshot config (optional)
        snapshot_enabled = (os.environ.get("SNAPSHOT_ENABLED", "false").lower() == "true")
        snapshot_dir = Path(os.environ.get("SNAPSHOT_DIR", str(ROOT / "logs" / "html")))
        last_hash_by_profile: dict[str, str] = {}

        for tab_no in range(1, target_tabs + 1):
            profile_key = os.environ.get(f"SUREBET_TAB_{tab_no}_PROFILE_KEY")
            if not profile_key:
                logger.warning("Missing profile for tab", tab=tab_no)
                continue
            chat_id = cfg.get_channel_for_profile("surebet", profile_key)

            tm.driver.switch_to.window(handles[tab_no - 1])
            filter_name = os.environ.get(f"SUREBET_TAB_{tab_no}_FILTER_NAME")
            logger.info("Processing Surebet tab", tab=tab_no, profile=profile_key)

            if filter_name:
                try:
                    select_saved_filter(tm.driver, filter_name)
                except Exception as e:
                    logger.warning("Exception selecting filter", error=str(e))

            html = tm.driver.page_source or ""

            if snapshot_enabled:
                try:
                    path = write_snapshot(html, snapshot_dir, "surebet", profile_key)
                    disk_html = read_snapshot(snapshot_dir, "surebet", profile_key) or html
                    snap_hash = compute_hash(disk_html)
                    if last_hash_by_profile.get(profile_key) == snap_hash:
                        logger.info("No changes since last snapshot; skipping send", tab=tab_no, profile=profile_key)
                        continue
                    last_hash_by_profile[profile_key] = snap_hash

                    # Process snapshot to JSON latest
                    try:
                        process_snapshot_file(Path(path), source="surebet", profile=profile_key)
                    except Exception as pe:
                        logger.warning("Failed processing Surebet snapshot to JSON; will fallback to HTML parsing", error=str(pe))

                    parsed_dir = Path(os.getenv("PARSED_OUTPUT_DIR", str(ROOT / "logs" / "snapshots_parsed")))
                    latest = parsed_dir / f"surebet-{profile_key}-latest.json"
                    if latest.exists():
                        try:
                            data = json.loads(latest.read_text(encoding="utf-8", errors="ignore"))
                            # Optional: send raw JSON message for visual supervision
                            send_json = (os.environ.get("SEND_JSON_MESSAGE", "false").lower() == "true")
                            if send_json:
                                pretty = json.dumps(data, ensure_ascii=False, indent=2)
                                msg = f"[surebet] Última alerta (perfil: {profile_key}, tab {tab_no})\n```json\n{pretty}\n```"
                                notifier.send_text(msg, chat_id=chat_id)
                                logger.info("Surebet JSON message sent", tab=tab_no, profile=profile_key)
                                continue  # done with this tab
                            sport = (data.get("sport") or "").title()
                            market = data.get("market") or ""
                            match = data.get("match") or ""
                            value = data.get("value_pct")
                            sel_a = data.get("selection_a") or {}
                            a_bk = sel_a.get("bookmaker", "?")
                            a_od = sel_a.get("odd", "?")
                            link = _abs_url(cfg.surebet.base_url, data.get("target_link"))
                            lines = [f"[surebet] Última alerta (perfil: {profile_key}, tab {tab_no})"]
                            head = f"{sport} • {market} — {match}".strip()
                            if head:
                                lines.append(head)
                            if isinstance(value, (int, float)):
                                lines.append(f"VALUE: {value:.2f}%")
                            lines.append(f"{a_bk}: {a_od}")
                            if link:
                                lines.append(f"Link: {link}")
                            msg = "\n".join(lines)
                            notifier.send_text(msg, chat_id=chat_id)
                            logger.info("Surebet JSON-based message sent", tab=tab_no, profile=profile_key)
                            continue  # done with this tab
                        except Exception as je:
                            logger.warning("Failed to read/format Surebet latest JSON; fallback to HTML parsing", error=str(je))

                    html_to_parse = disk_html
                except Exception as e:
                    logger.warning("Snapshot write/read failed; parsing from memory", error=str(e))
                    html_to_parse = html
            else:
                html_to_parse = html

            # Fallback path using existing parser and summary
            alerts = parse_surebet_valuebets_html(html_to_parse, profile=profile_key)
            if not alerts:
                if chat_id:
                    notifier.send_text(f"[surebet] Sin eventos visibles (tab {tab_no}, perfil {profile_key}).", chat_id=chat_id)
                else:
                    notifier.send_text(f"[surebet] Sin eventos visibles (tab {tab_no}, perfil {profile_key}).")
                continue

            summary = _format_tab_summary(
                profile_key,
                tab_no,
                alerts,
                cfg.surebet.base_url,
                top_k=int(os.getenv("SUREBET_SUMMARY_TOP", "10")),
            )
            notifier.send_text(summary, chat_id=chat_id)
            logger.info("Surebet tab completed", tab=tab_no, profile=profile_key, total=len(alerts))

        logger.info("Combined flow completed successfully")
        return 0

    except Exception as e:
        logger.error("Combined workflow failed", error=str(e))
        return 1
    finally:
        # Keep session alive for inspection
        pass


if __name__ == "__main__":
    raise SystemExit(main())
