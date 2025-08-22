"""
Select one filter per /es/arbs tab and dump HTML/screenshot per tab.

- Assumes you already ran scripts.smoke_betburger_arbs_tabs to open/login and duplicate tabs.
- For each tab i, reads env BETBURGER_TAB_<i>_FILTER (substring match) and selects only that filter.
- Saves HTML and a screenshot per tab for inspection under logs/.

Run:
  python -m scripts.arbs_select_filters_and_dump

Env examples (.env):
  BETBURGER_TABS=6
  BETBURGER_TAB_1_FILTER=Winamax
  BETBURGER_TAB_2_FILTER=Codere
  BETBURGER_TAB_3_FILTER=Betfair
  BETBURGER_TAB_4_FILTER=Bet365
  BETBURGER_TAB_5_FILTER=Wina/Tony
  BETBURGER_TAB_6_FILTER=Filtro 6
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.logger import get_module_logger  # type: ignore
from src.utils.telegram_notifier import TelegramNotifier  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.browser.tab_manager import TabManager  # type: ignore
from src.browser.arbs_sidebar import select_only_filter  # type: ignore

logger = get_module_logger("arbs_select_filters_and_dump")


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def save_artifacts(driver, out_dir: Path, name: str) -> None:
    ts = time.strftime("%Y%m%d_%H%M%S")
    html_path = out_dir / f"{name}_{ts}.html"
    png_path = out_dir / f"{name}_{ts}.png"
    try:
        html_path.write_text(driver.page_source or "", encoding="utf-8")
    except Exception:
        pass
    try:
        driver.save_screenshot(str(png_path))
    except Exception:
        pass
    logger.info("Saved tab artifacts", html=str(html_path), screenshot=str(png_path))


def main() -> int:
    cfg = ConfigManager()
    bot = cfg.bot

    # Do not force headless; reuse whatever was used to open the tabs
    tm = TabManager(bot)
    if not tm.connect_to_existing_browser():
        logger.error("Unable to start/connect to Firefox")
        return 2

    try:
        handles = tm.driver.window_handles
        # Load filters mapping from YAML first (supports spaces), else env
        channels_cfg = getattr(cfg, "channels", {}) or {}
        yaml_map = channels_cfg.get("betburger_tab_filters", [])

        total_env = int(os.environ.get("BETBURGER_TABS", str(len(handles)) or "6"))
        total_yaml = len(yaml_map) if isinstance(yaml_map, list) else (len(yaml_map) if isinstance(yaml_map, dict) else 0)
        total = min(max(total_env, total_yaml, 1), len(handles))
        logger.info("Processing tabs", total=total)

        out = Path.cwd() / "logs" / "raw_html"
        ensure_dir(out)

        notifier = TelegramNotifier()
        send_alerts = os.getenv("ARBS_SEND_OPEN_ALERTS", "true").lower() != "false"

        for i in range(total):
            tm.driver.switch_to.window(handles[i])
            time.sleep(0.4)
            # Defensive: ensure we are on /es/arbs
            if "/es/arbs" not in (tm.driver.current_url or ""):
                tm.driver.get("https://www.betburger.com/es/arbs")
                time.sleep(1.0)

            # Determine mapping based on profile key first, then YAML, then legacy env
            profile_key = os.environ.get(f"BETBURGER_TAB_{i+1}_PROFILE_KEY", "").strip()
            channel_id = None
            filter_name = ""
            if profile_key:
                # New scheme: per-tab profile key selects filter and resolves channel
                filter_name = os.environ.get(f"BETBURGER_PROFILE_{profile_key}_FILTER", "").strip()
                try:
                    channel_id = cfg.get_channel_for_profile("betburger", profile_key)
                except Exception:
                    channel_id = None
            else:
                # YAML-driven (list/dict) mapping of filter names
                if isinstance(yaml_map, list) and i < len(yaml_map):
                    filter_name = str(yaml_map[i] or "").strip()
                elif isinstance(yaml_map, dict):
                    # keys may be strings or ints representing tab numbers starting at 1
                    key_variants = [i + 1, str(i + 1)]
                    for k in key_variants:
                        if k in yaml_map:
                            filter_name = str(yaml_map[k] or "").strip()
                            break
                # Legacy env per-tab filter
                if not filter_name:
                    filter_name = os.environ.get(f"BETBURGER_TAB_{i+1}_FILTER", "").strip()
            if not filter_name:
                logger.warning("No filter configured for tab", tab=i+1)
            else:
                ok = select_only_filter(tm.driver, filter_name)
                logger.info(
                    "Selected filter",
                    tab=i+1,
                    query=filter_name,
                    ok=ok,
                    profile_key=profile_key or None,
                    channel_id=channel_id or None,
                )
                time.sleep(0.8)

                # Notify channel if configured and selection succeeded
                if ok and send_alerts:
                    # Prefer resolved channel_id for the profile; fallback to support channel
                    target_chat = channel_id or cfg.get_support_channel()
                    if target_chat:
                        msg = (
                            f"✅ Betburger: filtro abierto en pestaña {i+1}\n"
                            f"Perfil: {profile_key or 'N/A'}\n"
                            f"Filtro: {filter_name}"
                        )
                        notifier.send_text(msg, chat_id=target_chat)

            # Dump artifacts for inspection
            safe = filter_name.replace("/", "-") if filter_name else f"tab{i+1}"
            save_artifacts(tm.driver, out, f"betburger_arbs_tab{i+1}_{safe}")

        logger.info("Done selecting filters and dumping artifacts")
        return 0

    finally:
        # Keep session open for manual review
        pass


if __name__ == "__main__":
    raise SystemExit(main())
