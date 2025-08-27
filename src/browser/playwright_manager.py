"""Playwright manager with proxy rotation and persistent session support.

Uses sync API for simplicity. Designed to open a context with a rotating proxy
(read from PROXY_POOL/PROXY_POOL_FILE) and reuse a user_data_dir for sessions.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page  # type: ignore

from ..utils.logger import get_module_logger
from ..config.settings import BotConfig
from ..proxy.pool import ProxyRotator

logger = get_module_logger("playwright_manager")


class PlaywrightManager:
    def __init__(self, bot_cfg: BotConfig):
        self.bot_cfg = bot_cfg
        self._pl = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.proxy_rotator = ProxyRotator()

    def launch(self, engine: str = "chromium", headless: Optional[bool] = None, user_data_dir: Optional[str] = None) -> Tuple[Browser, BrowserContext]:
        headless = self._resolve_headless(headless)
        self._pl = sync_playwright().start()

        proxy_url = self.proxy_rotator.next_proxy_url()
        proxy = {"server": proxy_url} if proxy_url else None

        # Default user_data_dir
        if not user_data_dir:
            user_data_dir = str(Path.cwd() / "logs" / "playwright_profile")
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)

        logger.info("Launching Playwright", engine=engine, headless=headless, proxy=proxy_url, user_data_dir=user_data_dir)
        if engine == "firefox":
            self.browser = self._pl.firefox.launch_persistent_context(user_data_dir=user_data_dir, headless=headless, proxy=proxy)  # type: ignore
            # When using launch_persistent_context, the return is actually a Context
            self.context = self.browser  # type: ignore[assignment]
            self.browser = self.context.browser
        elif engine == "webkit":
            self.browser = self._pl.webkit.launch()
            self.context = self.browser.new_context(proxy=proxy)
        else:  # chromium default
            self.browser = self._pl.chromium.launch()
            self.context = self.browser.new_context(proxy=proxy, user_agent=self._user_agent())

        return self.browser, self.context

    def _resolve_headless(self, headless: Optional[bool]) -> bool:
        if headless is not None:
            return headless
        env = os.environ.get("BOT_HEADLESS")
        if env is None:
            # default to headless true in servers
            return True
        return env.lower() in ("1", "true", "yes", "on")

    def _user_agent(self) -> str:
        # Simple disguise: desktop Chrome UA; can be randomized later
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

    def open_tabs(self, url: str, count: int = 6) -> list[Page]:
        assert self.context is not None, "Context not initialized. Call launch() first."
        pages: list[Page] = []
        # First page
        p0 = self.context.new_page()
        p0.goto(url)
        pages.append(p0)
        for _ in range(count - 1):
            p = self.context.new_page()
            p.goto(url)
            pages.append(p)
        logger.info("Opened tabs", count=len(pages), url=url)
        return pages

    def rotate_proxy_for_new_context(self) -> BrowserContext:
        assert self.browser is not None, "Browser not launched"
        proxy_url = self.proxy_rotator.next_proxy_url()
        proxy = {"server": proxy_url} if proxy_url else None
        self.context = self.browser.new_context(proxy=proxy, user_agent=self._user_agent())
        logger.info("Rotated proxy for new context", proxy=proxy_url)
        return self.context

    def close(self) -> None:
        try:
            if self.context:
                self.context.close()
        except Exception:
            pass
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self._pl:
                self._pl.stop()
        except Exception:
            pass
        self.context = None
        self.browser = None
        self._pl = None
