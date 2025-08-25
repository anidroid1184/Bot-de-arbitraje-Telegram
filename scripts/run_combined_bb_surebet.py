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
import json
import os
import time
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
import sys

# Ensure package imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.logger import get_module_logger  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.browser.tab_manager import TabManager  # type: ignore
from src.browser.auth_manager import AuthManager  # type: ignore
from src.browser.surebet_nav import select_saved_filter, get_selected_filter_name  # type: ignore
from src.processors.surebet_parser import parse_surebet_valuebets_html  # type: ignore
from src.utils.telegram_notifier import TelegramNotifier  # type: ignore
from src.utils.snapshots import write_snapshot, read_snapshot, compute_hash  # type: ignore
from src.utils.command_controller import PauseController, BotCommandListener  # type: ignore
from src.formatters.message_templates import EventCard, Selection, format_surebet_card  # type: ignore
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


def _safe_parse_dt(val: Optional[str]) -> Optional[datetime]:
    """Parse ISO8601-like string to aware UTC datetime; return None if invalid."""
    if not val:
        return None
    try:
        s = val.strip()
        # Support trailing 'Z'
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _safe_float(val) -> Optional[float]:
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return None
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
        # ===== Control plane: Telegram commands (/pause, /start, /status) =====
        controller = PauseController()
        cmd_listener = BotCommandListener(controller)
        cmd_listener.start()
        # Notify support channel that the bot is connected
        try:
            startup_notifier = TelegramNotifier()
            startup_notifier.send_text(
                "[control] Bot conectado y en ejecución.\n"
                "Comandos disponibles: /status, /pause, /start, /start-config, /finish-config"
            )
        except Exception as e:
            logger.warning("Failed to send startup notification", error=str(e))

        # ========= Betburger phase (one-time setup) =========
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

        # ========= Surebet phase (one-time setup) =========
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
        # Ensure we have at least `target_tabs` TABS ON SUREBET (not just total tabs)
        # 1) Build current list of Surebet handles
        all_handles: List[str] = tm.driver.window_handles
        surebet_handles: List[str] = []
        for h in all_handles:
            try:
                tm.driver.switch_to.window(h)
                url = tm.driver.current_url
            except Exception:
                url = ""
            if "surebet.com" in (url or ""):
                surebet_handles.append(h)

        # 2) Open new tabs duplicating the current Surebet URL until we reach target_tabs
        # Make sure current tab is on Surebet URL
        tm.driver.get(target_url_sb)
        time.sleep(0.5)
        while len(surebet_handles) < target_tabs:
            tm.driver.execute_script("window.open(arguments[0], '_blank');", target_url_sb)
            time.sleep(0.6)
            # The newly opened handle is at the end
            new_handles = tm.driver.window_handles
            new_h = [h for h in new_handles if h not in all_handles]
            if new_h:
                surebet_handles.append(new_h[0])
                all_handles = new_handles

        logger.info("Surebet tabs ready", count=len(surebet_handles))

        # Optional: give operator time to login/apply filters manually in Surebet tabs
        try:
            wait_sec = int(os.environ.get("MANUAL_SUREBET_SETUP_WAIT_SEC", "0") or "0")
        except Exception:
            wait_sec = 0
        if wait_sec > 0:
            logger.info("Waiting for manual Surebet setup (login/filters)", seconds=wait_sec)
            time.sleep(wait_sec)

        # Snapshot config (optional)
        snapshot_enabled = (os.environ.get("SNAPSHOT_ENABLED", "false").lower() == "true")
        snapshot_dir = Path(os.environ.get("SNAPSHOT_DIR", str(ROOT / "logs" / "html")))
        last_hash_by_profile: dict[str, str] = {}

        # ========= Determine tab -> profile mapping =========
        # Priority 1: Environment variables SUREBET_TAB_<i>_PROFILE_KEY
        # Priority 2: YAML order (surebet_profiles mapping order)
        env_profiles: list[str] = []
        for i in range(1, target_tabs + 1):
            v = os.environ.get(f"SUREBET_TAB_{i}_PROFILE_KEY")
            if v:
                env_profiles.append(v)
        if len(env_profiles) == target_tabs:
            tab_profiles = env_profiles
        else:
            # Use YAML order (dict preserves order in Python 3.7+)
            yaml_profiles = list((cfg.channels.get("surebet_profiles") or {}).keys())
            tab_profiles = yaml_profiles[:target_tabs]
        logger.info("Surebet tab->profile mapping", mapping={i+1: p for i, p in enumerate(tab_profiles)})

        # ========= Build UI filter -> profile mapping (from YAML) =========
        yaml_profiles_map = (cfg.channels.get("surebet_profiles") or {})
        ui_to_profile: dict[str, str] = {}
        for prof_key, prof_data in yaml_profiles_map.items():
            try:
                ui_name = (prof_data.get("ui_filter_name") or "").strip()
                if ui_name:
                    ui_to_profile[ui_name] = prof_key
            except Exception:
                continue

        # ========= Main loop =========
        run_forever = (os.environ.get("RUN_FOREVER", "false").lower() == "true")
        # Default poll interval: 30s (can be overridden via POLL_INTERVAL_SEC)
        poll_sec = _get_env_int("POLL_INTERVAL_SEC", 30)
        iteration = 0
        while True:
            iteration += 1
            # Global pause/config check (allows operator to configure manually)
            if controller.is_paused() or controller.is_config_mode():
                if iteration % 10 == 1:
                    if controller.is_paused():
                        logger.info("Execution paused by operator; sleeping")
                    else:
                        logger.info("Config mode active; sleeping (no scraping/sending)")
                try:
                    time.sleep(2)
                except KeyboardInterrupt:
                    logger.info("Interrupted by user while paused")
                    return 0
                continue
            # --- Betburger iteration ---
            try:
                rc = send_all_tabs_with_driver(tm.driver, cfg)
                if rc != 0:
                    logger.warning("Betburger send step returned non-zero", return_code=rc)
            except Exception as e:
                logger.warning("Betburger iteration failed", error=str(e))

            # --- Surebet iteration ---
            for tab_no in range(1, target_tabs + 1):
                # Switch to the corresponding Surebet tab handle first
                tm.driver.switch_to.window(surebet_handles[tab_no - 1])

                # Resolve filter: ENV override > YAML default > UI selected
                # First get tentative profile mapping by config
                try:
                    configured_profile = tab_profiles[tab_no - 1]
                except Exception:
                    configured_profile = None
                env_filter = os.environ.get(f"SUREBET_TAB_{tab_no}_FILTER_NAME")
                default_yaml_filter = cfg.get_profile_ui_filter_name("surebet", configured_profile) if configured_profile else None
                ui_selected_filter = get_selected_filter_name(tm.driver) or None
                # Pick effective filter name to log and try selecting (if provided by env/default)
                filter_name = env_filter or default_yaml_filter
                # If no filter provided to select, keep whatever UI has (ui_selected_filter)
                effective_ui_filter = filter_name or ui_selected_filter

                # If env/default filter is specified, attempt to select it
                if filter_name:
                    try:
                        select_saved_filter(tm.driver, filter_name)
                    except Exception as e:
                        logger.warning("Exception selecting filter", error=str(e))

                # Determine profile by UI selected filter (preferred), fallback to configured mapping
                ui_now = get_selected_filter_name(tm.driver) or effective_ui_filter or ""
                profile_key = ui_to_profile.get(ui_now) or configured_profile
                if not profile_key:
                    logger.warning("Cannot resolve profile for tab; skipping", tab=tab_no, ui_filter=ui_now)
                    continue
                chat_id = cfg.get_channel_for_profile("surebet", profile_key)
                logger.info("Processing Surebet tab", tab=tab_no, profile=profile_key, ui_filter=ui_now)

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
                                # Build formatted card (Europe/Madrid, comma pct)
                                sel_a = data.get("selection_a") or {}
                                sel_b = data.get("selection_b") or {}
                                # Load per-profile defaults (does not affect channel_id)
                                defaults = cfg.get_profile_defaults("surebet", profile_key) or {}
                                def_a = (defaults.get("selection_a") or {})
                                def_b = (defaults.get("selection_b") or {})
                                def_market = defaults.get("market_label") or ""
                                # Many Surebet snapshots don't include per-selection labels; fallback to global market
                                global_market = data.get("market") or ""
                                market_a = sel_a.get("market_label") or sel_a.get("market") or global_market or def_market or ""
                                market_b = sel_b.get("market_label") or sel_b.get("market") or global_market or def_market or ""
                                card = EventCard(
                                    source_prefix="SU",
                                    selection_a=Selection(
                                        bookmaker=(sel_a.get("bookmaker") or def_a.get("bookmaker") or ""),
                                        label=market_a,
                                        odd=sel_a.get("odd", "?")
                                    ),
                                    selection_b=Selection(
                                        bookmaker=(sel_b.get("bookmaker") or def_b.get("bookmaker") or ""),
                                        label=market_b,
                                        odd=sel_b.get("odd", "?")
                                    ),
                                    sport=(data.get("sport") or "Fútbol"),
                                    league=(data.get("league") or data.get("competition") or ""),
                                    start_time=_safe_parse_dt(data.get("event_start") or data.get("start_time_utc")),
                                    match=(data.get("match") or ""),
                                    value_pct=_safe_float(data.get("value_pct") or data.get("roi_pct")),
                                    reference_time=_safe_parse_dt(data.get("timestamp_utc")),
                                )
                                msg = format_surebet_card(card)
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

            logger.info("Combined iteration completed", iteration=iteration)
            if not run_forever:
                logger.info("Single pass mode finished")
                return 0
            # Sleep until next poll
            try:
                time.sleep(max(5, poll_sec))
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                return 0

    except Exception as e:
        logger.error("Combined workflow failed", error=str(e))
        return 1
    finally:
        # Keep session alive for inspection
        pass


if __name__ == "__main__":
    raise SystemExit(main())
