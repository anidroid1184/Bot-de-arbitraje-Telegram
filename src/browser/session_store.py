"""Utilities to persist and reattach Selenium Remote sessions between processes.

This is intended for Remote WebDriver (e.g., Selenium Grid / Standalone in Docker).
It will not work for purely local Firefox sessions because those are not exposed
via a remote executor URL.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional, Tuple

import requests  # type: ignore

from ..utils.logger import get_module_logger

logger = get_module_logger("session_store")


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_session(session_file: Path | str, driver, executor_url: str) -> None:
    """Persist executor URL and current session_id to a JSON file.

    Only call this for Remote WebDriver sessions.
    """
    try:
        p = Path(session_file)
        _ensure_dir(p)
        data = {
            "executor_url": executor_url,
            "session_id": getattr(driver, "session_id", None),
        }
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Saved WebDriver session", file=str(p), session_id=data.get("session_id"))
    except Exception as e:
        logger.warning("Failed to save WebDriver session", error=str(e))


def load_session(session_file: Path | str) -> Optional[Tuple[str, str]]:
    """Load (executor_url, session_id) from JSON file, if available."""
    try:
        p = Path(session_file)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        executor_url = data.get("executor_url")
        session_id = data.get("session_id")
        if not executor_url or not session_id:
            return None
        return executor_url, session_id
    except Exception as e:
        logger.warning("Failed to load WebDriver session file", error=str(e))
        return None


def session_alive(executor_url: str, session_id: str) -> bool:
    """Ping the remote session to confirm it exists."""
    try:
        url = executor_url.rstrip("/") + f"/session/{session_id}"
        resp = requests.get(url, timeout=3)
        return resp.status_code in (200, 404) or (resp.status_code >= 200 and resp.status_code < 500)
    except Exception:
        return False


def attach_to_session(executor_url: str, session_id: str, options=None):
    """Best-effort attach to an existing Remote session without creating a new one.

    Returns a webdriver instance or None on failure.
    """
    try:
        from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver  # type: ignore
        from selenium.webdriver.remote.remote_connection import RemoteConnection  # type: ignore

        class _AttachRemote(RemoteWebDriver):  # type: ignore
            def start_session(self, capabilities=None, browser_profile=None):  # type: ignore
                # Prevent newSession command to reuse existing session
                return

        remote = RemoteConnection(executor_url, resolve_ip=False)
        driver = _AttachRemote(command_executor=remote, desired_capabilities={})  # type: ignore[arg-type]
        driver.session_id = session_id  # type: ignore[attr-defined]
        driver.w3c = True  # Selenium 4 uses W3C mode
        # Quick no-op command to verify it's responsive
        driver.title  # type: ignore[attr-defined]
        return driver
    except Exception as e:
        logger.warning("Failed to attach to existing WebDriver session", error=str(e))
        return None
