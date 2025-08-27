"""Playwright network capture helpers for Betburger/Surebet.

- Attaches listeners to a BrowserContext or Page to record requests/responses
  matching certain URL patterns (e.g., Betburger pro_search).
- Extracts JSON payloads and exposes a simple in-memory buffer.

Usage:
  cap = PlaywrightCapture(context)
  cap.start()
  # ... navigate, actions ...
  data = cap.flush()
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from playwright.sync_api import BrowserContext, Page, Request, Response  # type: ignore

from ..utils.logger import get_module_logger

logger = get_module_logger("playwright_capture")


PRO_SEARCH_REGEX = re.compile(r"/api/(?:v\d+/)?pro_search", re.IGNORECASE)


class PlaywrightCapture:
    def __init__(self, target: BrowserContext | Page, url_patterns: Optional[list[str]] = None):
        self.target = target
        self.buffer: list[dict[str, Any]] = []
        self._enabled = False
        # custom string patterns OR defaults to pro_search
        self.patterns = [re.compile(p, re.IGNORECASE) for p in (url_patterns or [])] or [PRO_SEARCH_REGEX]

    def _match(self, url: str) -> bool:
        return any(p.search(url) for p in self.patterns)

    def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True

        def on_request(req: Request) -> None:
            try:
                if not self._match(req.url):
                    return
                rec: dict[str, Any] = {
                    "type": "request",
                    "url": req.url,
                    "method": req.method,
                }
                post_data = None
                try:
                    post_data = req.post_data
                except Exception:
                    pass
                if post_data:
                    # try parse json
                    try:
                        rec["json"] = json.loads(post_data)
                    except Exception:
                        rec["body"] = post_data
                self.buffer.append(rec)
                logger.debug("Captured request", url=req.url)
            except Exception as e:
                logger.warning("on_request handler error", error=str(e))

        def on_response(res: Response) -> None:
            try:
                if not self._match(res.url):
                    return
                rec: dict[str, Any] = {
                    "type": "response",
                    "url": res.url,
                    "status": res.status,
                }
                try:
                    # may raise if not JSON
                    rec["json"] = res.json()
                except Exception:
                    try:
                        rec["text"] = res.text()
                    except Exception:
                        pass
                self.buffer.append(rec)
                logger.debug("Captured response", url=res.url, status=res.status)
            except Exception as e:
                logger.warning("on_response handler error", error=str(e))

        # Attach to context or single page
        if isinstance(self.target, BrowserContext):
            self.target.on("request", on_request)
            self.target.on("response", on_response)
        else:
            self.target.on("request", on_request)
            self.target.on("response", on_response)

    def flush(self) -> list[dict[str, Any]]:
        data = list(self.buffer)
        self.buffer.clear()
        return data
