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
        # Contextos creados por rotación per_tab para facilitar cleanup
        self._rotated_contexts: list[BrowserContext] = []

    def launch(self, engine: str = "chromium", headless: Optional[bool] = None, user_data_dir: Optional[str] = None) -> Tuple[Browser, BrowserContext]:
        headless = self._resolve_headless(headless)
        self._pl = sync_playwright().start()

        # If we are going to rotate per-tab, don't set a base proxy at context level
        per_tab = os.environ.get("SMOKE_PER_TAB", "0").lower() in ("1", "true", "yes", "on")
        proxy_url = None if per_tab else self.proxy_rotator.next_proxy_url()
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
            self.browser = self._pl.webkit.launch(headless=headless)
            self.context = self.browser.new_context(proxy=proxy, user_agent=self._user_agent())
        else:  # chromium default
            self.browser = self._pl.chromium.launch(headless=headless)
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
        if count <= 0:
            logger.info("Requested to open 0 tabs; skipping", url=url, requested=count)
            return pages
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

    def open_tabs_with_context_rotation(self, url: str, count: int = 6, max_attempts: int | None = None) -> list[Page]:
        """Abre `count` pestañas donde cada pestaña vive en un contexto distinto con un proxy distinto.

        - Usa `ProxyRotator.next_proxy_url()` para asignar un proxy por contexto.
        - Registra en logs el proxy asignado a cada pestaña.
        - Mantiene referencia a los contextos en `self._rotated_contexts` para cerrarlos en `close()`.

        Retorna la lista de Pages creadas (una por contexto).
        """
        assert self.browser is not None, "Browser not launched. Call launch() first."
        pages: list[Page] = []
        if count <= 0:
            logger.info("Requested to open 0 rotated tabs; skipping", url=url, requested=count)
            return pages
        attempts = 0
        max_attempts = max_attempts or count * 4  # try a few extra proxies if some fail
        while len(pages) < count and attempts < max_attempts:
            attempts += 1
            idx = len(pages)
            proxy_url = self.proxy_rotator.next_proxy_url()
            proxy = {"server": proxy_url} if proxy_url else None
            try:
                ctx = self.browser.new_context(proxy=proxy, user_agent=self._user_agent())
                # Fail fast on dead proxies
                try:
                    ctx.set_default_navigation_timeout(8000)
                    ctx.set_default_timeout(8000)
                except Exception:
                    pass
                self._rotated_contexts.append(ctx)
                page = ctx.new_page()
                logger.info("Opening tab with rotated proxy", index=idx, proxy=proxy_url, url=url)
                page.goto(url, wait_until="domcontentloaded", timeout=8000)
                pages.append(page)
            except Exception as e:
                logger.warning("Failed to open tab with proxy", proxy=proxy_url, error=str(e))
                # Cleanup context if created but navigation failed
                try:
                    if 'ctx' in locals():
                        ctx.close()
                        self._rotated_contexts = [c for c in self._rotated_contexts if c is not ctx]
                except Exception:
                    pass
                continue
        logger.info("Opened tabs with per_tab proxy rotation", count=len(pages), url=url, attempts=attempts, requested=count)
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
        # Cerrar contextos rotados per_tab
        for ctx in self._rotated_contexts:
            try:
                ctx.close()
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
        self._rotated_contexts = []

    def rotated_contexts(self) -> list[BrowserContext]:
        """Devuelve una copia de la lista de contextos creados por rotación per_tab.

        Se expone con fines de prueba/observabilidad para poder adjuntar capturas de red
        por contexto. No modificar desde fuera.
        """
        return list(self._rotated_contexts)
