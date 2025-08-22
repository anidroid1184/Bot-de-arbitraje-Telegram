"""
Single-process workflow for Betburger:
  1) Login + open /es/arbs
  2) Duplicate tabs to BETBURGER_TABS
  3) Send results from all tabs to mapped Telegram channels

Usage (WSL):
  python3 -m scripts.run_smoke_select_and_send_all

Notes:
- Uses the SAME Selenium WebDriver session for all steps.
- Requires .env with BETBURGER_USERNAME, BETBURGER_PASSWORD, TELEGRAM_BOT_TOKEN
- Set BETBURGER_TABS and BETBURGER_TAB_<i>_PROFILE_KEY for i=1..N
- Current version does NOT apply per-tab UI filters in the same driver yet.
  If you need filters, run scripts/arbs_select_filters_and_dump.py beforehand
  (different driver) or we can refactor that script to accept a driver next.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Ensure package imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.logger import get_module_logger  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.browser.tab_manager import TabManager  # type: ignore
from scripts.smoke_betburger_arbs_tabs import (  # type: ignore
    login_with_remember_me,
    duplicate_tabs_to,
)
from scripts.betburger_send_all_tabs_results import (  # type: ignore
    send_all_tabs_with_driver,
)

logger = get_module_logger("run_smoke_select_and_send_all")


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
        # 1) Login and ensure we can reach /es/arbs
        username = cfg.betburger.username
        password = cfg.betburger.password
        login_url = cfg.betburger.login_url
        if not (username and password):
            logger.error("Missing BETBURGER credentials in .env")
            return 1

        login_with_remember_me(
            tm.driver,
            username,
            password,
            login_url,
            timeout=cfg.bot.browser_timeout,
        )

        # 2) Navigate to /es/arbs
        target_url = "https://www.betburger.com/es/arbs"
        logger.info("Navigating to target page", url=target_url)
        tm.driver.get(target_url)
        time.sleep(1.0)

        # 3) Duplicate tabs
        tabs = int(os.environ.get("BETBURGER_TABS", "6") or "6")
        duplicate_tabs_to(tm.driver, tabs)
        logger.info("Tabs ensured", count=len(tm.driver.window_handles))

        # 4) Send results from all tabs using the same driver
        rc = send_all_tabs_with_driver(tm.driver, cfg)
        if rc != 0:
            logger.error("Send step finished with non-zero code", return_code=rc)
            return rc

        logger.info("All steps completed successfully - single process")
        return 0

    except Exception as e:
        logger.error("Workflow failed", error=str(e))
        return 1
    finally:
        # Keep the browser session alive for inspection; comment out to auto-close
        pass


if __name__ == "__main__":
    raise SystemExit(main())
