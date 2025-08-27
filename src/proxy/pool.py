"""Proxy pool utilities: read rotating proxies from env or file and provide next proxy.

Environment options:
- PROXY_POOL: semicolon/comma/space separated list of proxies (e.g., http://user:pass@host:port)
- PROXY_POOL_FILE: path to a file with one proxy per line
- PROXY_ROTATE_STRATEGY: per_tab | per_run (default per_tab)

Returned proxy dicts are normalized for Playwright and Selenium Wire.
"""
from __future__ import annotations

import os
import itertools
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional

from ..utils.logger import get_module_logger

logger = get_module_logger("proxy_pool")


def _read_list_from_env(env_name: str) -> list[str]:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return []
    # split by common separators ; , whitespace
    parts = []
    for sep in [";", ",", "\n", "\r", "\t", " "]:
        raw = raw.replace(sep, "\n")
    for line in raw.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            parts.append(s)
    return parts


def _read_list_from_file(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    items: list[str] = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            items.append(s)
    return items


def load_proxy_pool() -> list[str]:
    items: list[str] = []
    items.extend(_read_list_from_env("PROXY_POOL"))
    file_path = os.environ.get("PROXY_POOL_FILE", "").strip()
    if file_path:
        items.extend(_read_list_from_file(file_path))
    # de-dup preserving order
    seen = set()
    uniq: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    if not uniq:
        logger.warning("Proxy pool is empty; running without proxy")
    else:
        logger.info("Loaded proxy pool", count=len(uniq))
    return uniq


class ProxyRotator:
    def __init__(self, proxies: Optional[list[str]] = None):
        self.proxies = proxies or load_proxy_pool()
        self._cycle: Iterator[str] = itertools.cycle(self.proxies) if self.proxies else iter(())

    def next_proxy_url(self) -> Optional[str]:
        try:
            return next(self._cycle)
        except Exception:
            return None

    @staticmethod
    def playwright_proxy_dict(url: Optional[str]) -> Optional[dict]:
        if not url:
            return None
        return {"server": url}

    @staticmethod
    def seleniumwire_options(url: Optional[str]) -> Optional[Dict]:
        if not url:
            return None
        # Selenium Wire can set upstream proxy for all protocols via 'proxy'
        return {"proxy": {"http": url, "https": url}}  # type: ignore[return-value]
