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
    # Betburger env normalization: prefer BETBURGER_BASE; fallback to BETBURGER_BASE_URL
    base = os.environ.get("BETBURGER_BASE") or os.environ.get("BETBURGER_BASE_URL", "https://betburger.com")
    path = os.environ.get("BETBURGER_PATH", "/es/arbs")
    url = f"{base}{path}"
    engine = os.environ.get("PLAYWRIGHT_ENGINE", "chromium").lower()
    include_surebet = os.environ.get("SMOKE_INCLUDE_SUREBET", "0").lower() in ("1", "true", "yes", "on")
    surebet_url = os.environ.get("SUREBET_VALUEBETS_URL", "https://es.surebet.com/valuebets")
    surebet_tabs = int(os.environ.get("SUREBET_TABS", "3"))
    betburger_tabs = int(os.environ.get("BETBURGER_TABS", "3"))

    cfg_mgr = ConfigManager()
    pm = PlaywrightManager(cfg_mgr.bot)
    try:
        pm.launch(engine=engine)
        per_tab = os.environ.get("SMOKE_PER_TAB", "0").lower() in ("1", "true", "yes", "on")
        captures: list[PlaywrightCapture] = []

        if per_tab:
            pages = pm.open_tabs_with_context_rotation(url, count=betburger_tabs)
            logger.info("Tabs opened (per_tab rotation)", engine=engine, url=url, requested=betburger_tabs, count=len(pages))
            # Attach one capture per rotated context
            for idx, ctx in enumerate(pm.rotated_contexts()):
                cap = PlaywrightCapture(ctx)
                cap.start()
                captures.append(cap)
                logger.info("Capture started for context", index=idx)
        else:
            pages = pm.open_tabs(url, count=betburger_tabs)
            logger.info("Tabs opened", engine=engine, url=url, requested=betburger_tabs, count=len(pages))
            # Attach single capture on shared context
            assert pm.context is not None
            cap = PlaywrightCapture(pm.context)
            cap.start()
            captures.append(cap)

        # Optionally include Surebet: open tabs and attach captures with basic patterns
        if include_surebet:
            if per_tab:
                pages_sb = pm.open_tabs_with_context_rotation(surebet_url, count=surebet_tabs)
                logger.info("Surebet tabs opened (per_tab rotation)", url=surebet_url, count=len(pages_sb))
                for idx, ctx in enumerate(pm.rotated_contexts()[-len(pages_sb):]):
                    cap_sb = PlaywrightCapture(ctx, url_patterns=[r"/valuebets", r"/api/"])
                    cap_sb.start()
                    captures.append(cap_sb)
                    logger.info("Surebet capture started for context", index=idx)
            else:
                pages_sb = pm.open_tabs(surebet_url, count=surebet_tabs)
                logger.info("Surebet tabs opened", url=surebet_url, count=len(pages_sb))
                assert pm.context is not None
                cap_sb = PlaywrightCapture(pm.context, url_patterns=[r"/valuebets", r"/api/"])
                cap_sb.start()
                captures.append(cap_sb)

        # keep for a short while so user can login manually if needed, while capturing
        sleep_sec = int(os.environ.get("SMOKE_IDLE_SECONDS", "90"))
        logger.info("Idle to allow login/manual checks (capturing pro_search)", seconds=sleep_sec)

        seen_filters: set[int] = set()
        t0 = time.time()
        total_matched = 0
        total_req = 0
        total_res = 0
        last_summary = t0
        while time.time() - t0 < sleep_sec:
            for cap in captures:
                data = cap.flush()
                for rec in data:
                    rtype = rec.get("type")
                    url = rec.get("url")
                    if not url:
                        continue
                    total_matched += 1
                    if rtype == "request":
                        total_req += 1
                        # Log one-liners for every pro_search match
                        method = rec.get("method", "?")
                        has_json = isinstance(rec.get("json"), dict)
                        logger.info("[capture] request", method=method, url=url, json=has_json)
                        if has_json:
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
                    elif rtype == "response":
                        total_res += 1
                        status = rec.get("status")
                        logger.info("[capture] response", status=status, url=url)
            # periodic summary every ~10s
            now = time.time()
            if now - last_summary >= 10:
                logger.info("Capture summary", matched=total_matched, requests=total_req, responses=total_res, elapsed=int(now - t0))
                last_summary = now
            time.sleep(1.0)

        # final summary
        logger.info("Capture finished", matched=total_matched, requests=total_req, responses=total_res, duration=int(time.time() - t0))
        if total_matched == 0:
            logger.warning("No pro_search traffic matched. If not logged in, Betburger may not emit pro_search. Try logging in (headed) and retry.")
        return 0
    except Exception as e:
        logger.exception("Playwright smoke failed", error=str(e))
        return 2
    finally:
        pm.close()


if __name__ == "__main__":
    raise SystemExit(main())
