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
from playwright.sync_api import BrowserContext, Page, Request, Response, WebSocket  # type: ignore

import structlog

logger = structlog.get_logger(__name__)

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
        # Diagnostics: optionally log all requests/responses regardless of match
        import os
        log_all = os.environ.get("CAPTURE_LOG_ALL", "0").lower() in ("1", "true", "yes", "on")

        def on_request(req: Request) -> None:
            try:
                if log_all:
                    logger.info("[req*]", method=req.method, url=req.url)
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
                if log_all:
                    logger.info("[res*]", status=res.status, url=res.url)
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

        # Optional: capture websockets (URL match-based)
        def on_ws(ws: WebSocket) -> None:
            try:
                if not self._match(ws.url):
                    return
                self.buffer.append({
                    "type": "ws_open",
                    "url": ws.url,
                })
                logger.debug("Captured ws open", url=ws.url)

                def _on_frame_sent(payload: str) -> None:
                    try:
                        self.buffer.append({
                            "type": "ws_frame_sent",
                            "url": ws.url,
                            "size": len(payload) if payload else 0,
                        })
                    except Exception:
                        pass

                def _on_frame_received(payload: str) -> None:
                    try:
                        self.buffer.append({
                            "type": "ws_frame_received",
                            "url": ws.url,
                            "size": len(payload) if payload else 0,
                        })
                    except Exception:
                        pass

                ws.on("framesent", _on_frame_sent)
                ws.on("framereceived", _on_frame_received)
            except Exception as e:
                logger.warning("on_ws handler error", error=str(e))

        # Attach to context or single page
        if isinstance(self.target, BrowserContext):
            self.target.on("request", on_request)
            self.target.on("response", on_response)
            self.target.on("websocket", on_ws)
        else:
            self.target.on("request", on_request)
            self.target.on("response", on_response)
            self.target.on("websocket", on_ws)

    def flush(self) -> list[dict[str, Any]]:
        data = list(self.buffer)
        self.buffer.clear()
        return data
