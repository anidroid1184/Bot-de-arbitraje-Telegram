"""Smoke test: open Betburger tabs using Playwright with proxy rotation.

Usage:
  python -m scripts.playwright_smoke_betburger_tabs

Env:
  BOT_HEADLESS=true|false
  PROXY_POOL / PROXY_POOL_FILE
  BETBURGER_BASE=https://www.betburger.com
  BETBURGER_PATH=/es/arbs
  PLAYWRIGHT_ENGINE=chromium|firefox|webkit
"""
from __future__ import annotations

import os
import time
from typing import Optional

from src.browser.playwright_manager import PlaywrightManager
from src.network.playwright_capture import PlaywrightCapture
from src.config.settings import ConfigManager
from src.utils.logger import get_module_logger

logger = get_module_logger("playwright_smoke")


def main() -> int:
    base = os.environ.get("BETBURGER_BASE", "https://www.betburger.com")
    path = os.environ.get("BETBURGER_PATH", "/es/arbs")
    url = f"{base}{path}"
    engine = os.environ.get("PLAYWRIGHT_ENGINE", "chromium").lower()

    cfg_mgr = ConfigManager()
    pm = PlaywrightManager(cfg_mgr.bot)
    try:
        pm.launch(engine=engine)
        pages = pm.open_tabs(url, count=6)
        logger.info("Tabs opened", engine=engine, url=url)

        # Attach network capture on context
        assert pm.context is not None
        cap = PlaywrightCapture(pm.context)
        cap.start()

        # keep for a short while so user can login manually if needed, while capturing
        sleep_sec = int(os.environ.get("SMOKE_IDLE_SECONDS", "90"))
        logger.info("Idle to allow login/manual checks (capturing pro_search)", seconds=sleep_sec)

        seen_filters: set[int] = set()
        t0 = time.time()
        while time.time() - t0 < sleep_sec:
            data = cap.flush()
            for rec in data:
                if rec.get("type") == "request" and isinstance(rec.get("json"), dict):
                    j = rec["json"]
                    fid = j.get("filter_id") or j.get("filterId")
                    if isinstance(fid, int) and fid not in seen_filters:
                        seen_filters.add(fid)
                        label = "unknown"
                        if fid == 1218070:
                            label = "Codere"
                        elif fid == 1218528:
                            label = "Betfair"
                        logger.info("Detected pro_search filter_id", filter_id=fid, label=label)
            time.sleep(1.0)
        return 0
    except Exception as e:
        logger.exception("Playwright smoke failed", error=str(e))
        return 2
    finally:
        pm.close()


if __name__ == "__main__":
    raise SystemExit(main())
