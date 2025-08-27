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
import re
import sys
import time
from typing import Optional

# Bootstrap sys.path to allow running either:
#  - python -m scripts.playwright_smoke_betburger_tabs
#  - python scripts/playwright_smoke_betburger_tabs.py
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_this_dir, os.pardir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

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
    # Surebet: por defecto 1 pestaña para enfoque en una sola ventana de diagnóstico
    surebet_tabs = int(os.environ.get("SUREBET_TABS", "1"))
    betburger_tabs = int(os.environ.get("BETBURGER_TABS", "3"))

    cfg_mgr = ConfigManager()
    pm = PlaywrightManager(cfg_mgr.bot)
    try:
        pm.launch(engine=engine)
        per_tab = os.environ.get("SMOKE_PER_TAB", "0").lower() in ("1", "true", "yes", "on")
        captures: list[PlaywrightCapture] = []

        # Optional: broaden capture via env CAPTURE_PATTERNS (semicolon separated regexes)
        raw_patterns = os.environ.get("CAPTURE_PATTERNS", "").strip()
        cap_patterns = [p for p in (raw_patterns.split(";") if raw_patterns else []) if p]
        if cap_patterns:
            logger.info("Using custom capture patterns", patterns=cap_patterns)

        # local counter for optional route-all diagnostics
        route_counter = {"count": 0}

        if per_tab:
            pages = pm.open_tabs_with_context_rotation(url, count=betburger_tabs)
            logger.info("Tabs opened (per_tab rotation)", engine=engine, url=url, requested=betburger_tabs, count=len(pages))
            # Attach one capture per rotated context
            for idx, ctx in enumerate(pm.rotated_contexts()):
                cap = PlaywrightCapture(ctx, url_patterns=cap_patterns if cap_patterns else None)
                cap.start()
                captures.append(cap)
                logger.info("Capture started for context", index=idx)
        else:
            # Attach single capture on shared context BEFORE navigation to catch early requests
            assert pm.context is not None
            cap = PlaywrightCapture(pm.context, url_patterns=cap_patterns if cap_patterns else None)
            cap.start()
            captures.append(cap)
            pages = pm.open_tabs(url, count=betburger_tabs)
            logger.info("Tabs opened", engine=engine, url=url, requested=betburger_tabs, count=len(pages))

        # Optionally include Surebet: env-driven config + capture attachment
        if include_surebet:
            # Allow custom patterns via env for Surebet API per docs
            sb_pattern_env = os.environ.get("SUREBET_PATTERNS", "").strip()
            sb_patterns = [p for p in re.split(r"[,|]", sb_pattern_env) if p] if sb_pattern_env else [r"/valuebets", r"/api/", r"/arbs", r"/surebets"]
            if per_tab:
                pages_sb = pm.open_tabs_with_context_rotation(surebet_url, count=surebet_tabs)
                logger.info("Surebet tabs opened (per_tab rotation)", url=surebet_url, count=len(pages_sb))
                # Attach one capture per rotated context (after rotation, best-effort for per-tab mode)
                for idx, ctx in enumerate(pm.rotated_contexts()[-len(pages_sb):]):
                    cap_sb = PlaywrightCapture(ctx, url_patterns=sb_patterns)
                    cap_sb.start()
                    captures.append(cap_sb)
            else:
                # Shared context: attach capture BEFORE navigation to avoid missing early requests
                assert pm.context is not None
                cap_sb = PlaywrightCapture(pm.context, url_patterns=sb_patterns)
                cap_sb.start()
                captures.append(cap_sb)
                pages_sb = pm.open_tabs(surebet_url, count=surebet_tabs)
                logger.info("Surebet tabs opened", url=surebet_url, count=len(pages_sb))

            # Optional route-all for Surebet pages
            route_all_sb = os.environ.get("SMOKE_ROUTE_ALL_SUREBET", "0").lower() in ("1", "true", "yes", "on")
            if route_all_sb:
                def _log_and_continue_sb(route: Route, request: Request) -> None:
                    route_counter["count"] += 1
                    logger.info("[route*][SB]", method=request.method, url=request.url)
                    route.continue_()
                for p in pages_sb:
                    p.route("**/*", _log_and_continue_sb)
                logger.info("Surebet route-all enabled", pages=len(pages_sb), routed_count=route_counter["count"]) 

        # keep for a short while so user can login manually if needed, while capturing
        # Aumentar tiempo de idle para capturar tráfico y permitir copiar logs
        sleep_sec = int(os.environ.get("SMOKE_IDLE_SECONDS", "180"))
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
        # Mantener la terminal abierta opcionalmente para copiar logs
        if os.environ.get("SMOKE_HOLD", "0").lower() in ("1", "true", "yes", "on"):
            try:
                input("[SMOKE_HOLD] Presiona Enter para salir...")
            except Exception:
                # Entornos no interactivos (systemd) pueden fallar en input(); ignorar
                pass
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
