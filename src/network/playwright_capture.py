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
import os
import random
from typing import Any, Dict, List, Optional
from playwright.sync_api import BrowserContext, Page, Request, Response, WebSocket  # type: ignore

import structlog

logger = structlog.get_logger(__name__)

PRO_SEARCH_REGEX = re.compile(r"/api/(?:v\d+/)?pro_search", re.IGNORECASE)


class PlaywrightCapture:
    def __init__(
        self,
        target: BrowserContext | Page,
        url_patterns: Optional[list[str]] = None,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
        persist_path: Optional[str] = None,
        persist_fields: Optional[list[str]] = None,
        sample_rate: float = 1.0,
        max_buffer: int = 1000,
        drop_policy: str = "drop_oldest",  # or "drop_new"
        max_body_chars: int = 2000,
    ):
        self.target = target
        self.buffer: list[dict[str, Any]] = []
        self._enabled = False
        # custom string patterns OR defaults to pro_search
        self.patterns = [re.compile(p, re.IGNORECASE) for p in (url_patterns or [])] or [PRO_SEARCH_REGEX]

        # Advanced filtering from args or environment
        # Env vars (comma-separated regex): CAPTURE_INCLUDE, CAPTURE_EXCLUDE
        env_inc = os.getenv("CAPTURE_INCLUDE")
        env_exc = os.getenv("CAPTURE_EXCLUDE")
        self.include = [re.compile(p.strip(), re.IGNORECASE) for p in (include_patterns or [])]
        if env_inc:
            self.include.extend(re.compile(p.strip(), re.IGNORECASE) for p in env_inc.split(",") if p.strip())
        self.exclude = [re.compile(p.strip(), re.IGNORECASE) for p in (exclude_patterns or [])]
        if env_exc:
            self.exclude.extend(re.compile(p.strip(), re.IGNORECASE) for p in env_exc.split(",") if p.strip())

        # If no explicit url_patterns were given but we do have include filters, use them as base patterns.
        # This lets CAPTURE_INCLUDE fully define what to capture (e.g., Surebet valuebets AND Betburger pro_search).
        if not url_patterns and self.include:
            self.patterns = list(self.include)

        # Sampling and buffer protection
        try:
            self.sample_rate = float(os.getenv("CAPTURE_SAMPLE", str(sample_rate)))
        except Exception:
            self.sample_rate = sample_rate
        try:
            self.max_buffer = int(os.getenv("CAPTURE_MAX_BUFFER", str(max_buffer)))
        except Exception:
            self.max_buffer = max_buffer
        self.drop_policy = os.getenv("CAPTURE_DROP_POLICY", drop_policy)
        try:
            self.max_body_chars = int(os.getenv("CAPTURE_MAX_BODY_CHARS", str(max_body_chars)))
        except Exception:
            self.max_body_chars = max_body_chars

        # Optional persistence
        self.persist_path = os.getenv("CAPTURE_JSONL_PATH", persist_path or "") or None
        fields_env = os.getenv("CAPTURE_PERSIST_FIELDS")
        self.persist_fields = [f.strip() for f in (persist_fields or []) if f.strip()]
        if fields_env:
            self.persist_fields.extend(f.strip() for f in fields_env.split(",") if f.strip())
        self._fh = None  # file handle for persistence
        # Flush policy: flush on every write if enabled via env CAPTURE_FLUSH_EVERY=1/true
        self._flush_every = os.environ.get("CAPTURE_FLUSH_EVERY", "0").lower() in ("1", "true", "yes", "on")

    def _match(self, url: str) -> bool:
        # Base match against primary patterns
        if not any(p.search(url) for p in self.patterns):
            return False
        # Include (if provided) must match
        if self.include and not any(p.search(url) for p in self.include):
            return False
        # Exclude (if provided) must NOT match
        if self.exclude and any(p.search(url) for p in self.exclude):
            return False
        # Sampling
        if self.sample_rate < 1.0 and random.random() > self.sample_rate:
            return False
        return True

    def _append_record(self, rec: dict[str, Any]) -> None:
        # If capture is disabled, ignore new records (can happen during shutdown race)
        if not self._enabled:
            return
        # Trim large bodies
        if "body" in rec and isinstance(rec["body"], str) and len(rec["body"]) > self.max_body_chars:
            rec["body"] = rec["body"][: self.max_body_chars] + "…"
        # Buffer protection
        if len(self.buffer) >= self.max_buffer:
            if self.drop_policy == "drop_oldest" and self.buffer:
                self.buffer.pop(0)
            elif self.drop_policy == "drop_new":
                # skip enqueueing
                pass
            else:
                # default to dropping oldest
                if self.buffer:
                    self.buffer.pop(0)
        # Enqueue
        if len(self.buffer) < self.max_buffer:
            self.buffer.append(rec)
        # Persistence (best-effort, non-fatal)
        if self.persist_path and self._fh is not None and self._enabled:
            try:
                to_write = rec
                if self.persist_fields:
                    to_write = {k: rec.get(k) for k in self.persist_fields}
                self._fh.write(json.dumps(to_write, ensure_ascii=False) + "\n")
                # Optionally force flush for real-time durability in case of abrupt termination
                if self._flush_every:
                    try:
                        self._fh.flush()
                    except Exception:
                        pass
            except Exception as e:
                logger.warning("capture_persist_write_error", error=str(e))

    def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        # Diagnostics: optionally log all requests/responses regardless of match
        log_all = os.environ.get("CAPTURE_LOG_ALL", "0").lower() in ("1", "true", "yes", "on")
        # Open persistence file if configured
        if self.persist_path:
            try:
                os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)
                # Use line-buffered I/O so each line is pushed to OS buffers immediately
                # Note: line buffering is only honored in text mode; we are using text mode here.
                self._fh = open(self.persist_path, "a", encoding="utf-8", buffering=1)
                logger.info("capture_persist_open", path=self.persist_path)
            except Exception as e:
                logger.warning("capture_persist_open_error", error=str(e), path=self.persist_path)
                self._fh = None

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
                self._append_record(rec)
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
                self._append_record(rec)
                logger.debug("Captured response", url=res.url, status=res.status)
            except Exception as e:
                logger.warning("on_response handler error", error=str(e))

        # Optional: capture websockets (URL match-based)
        def on_ws(ws: WebSocket) -> None:
            try:
                if not self._match(ws.url):
                    return
                self._append_record({
                    "type": "ws_open",
                    "url": ws.url,
                })
                logger.debug("Captured ws open", url=ws.url)

                def _on_frame_sent(payload: str) -> None:
                    try:
                        self._append_record({
                            "type": "ws_frame_sent",
                            "url": ws.url,
                            "size": len(payload) if payload else 0,
                        })
                    except Exception:
                        pass

                def _on_frame_received(payload: str) -> None:
                    try:
                        self._append_record({
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

    def stop(self) -> None:
        """Close persistence handle if any. Does not detach listeners (Playwright lacks simple off())."""
        try:
            # Disable capture first to avoid races with event handlers
            self._enabled = False
            if self._fh:
                self._fh.flush()
                self._fh.close()
                self._fh = None
        except Exception:
            pass
