"""
Headless login script for Betburger using Playwright (Python).

- Reads credentials from .env: BETBURGER_EMAIL, BETBURGER_PASSWORD
- Uses persistent user data dir at logs/playwright_profile to store cookies/session
- Navigates to login page, submits credentials, and verifies login by
  redirect or disappearance of the login form.

Usage:
  python -m scripts.betburger_headless_login

Prerequisites:
  - Set credentials in .env
  - Playwright installed with Chromium browsers

Notes:
  - This script uses launch_persistent_context to ensure the session persists
    across runs and is reused by the smoke test.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


def load_env_file(env_path: Path) -> None:
    """Lightweight loader for KEY=VALUE pairs from a .env file if present.
    Does not overwrite existing environment variables.
    """
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        # Best-effort; continue if parsing fails
        pass


def env_bool(name: str, default: bool = True) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def log(level: str, msg: str, **fields: object) -> None:
    parts = [f"[{level:<7}]", msg]
    if fields:
        extra = " ".join(f"{k}={v}" for k, v in fields.items())
        parts.append(extra)
    print(" ".join(parts))


def guess_login_urls(base: str) -> list[str]:
    candidates = [
        f"{base}/login",
        f"{base}/signin",
        f"{base}/es/login",
        f"{base}/es/signin",
    ]
    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for u in candidates:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq


def wait_for_login_success(page, login_url: str, arbs_url: str, timeout_ms: int = 20000) -> bool:
    """Heuristics to detect successful login.
    - Either we navigate away from login_url to arbs_url or any non-login page
    - Or the login form disappears.
    """
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass

    # If we are on arbs_url (or redirected there), consider it success
    current = page.url
    if current.startswith(arbs_url):
        return True

    # Try to detect if login form disappeared
    try:
        email_vis = page.is_visible('input[name="email"]')
        pwd_vis = page.is_visible('input[name="password"]')
        # If both are not visible anymore, likely logged in or different page
        if not (email_vis or pwd_vis):
            return True
    except Exception:
        # If selectors query errored, could also indicate we're on a different page
        return True

    # As a last attempt, wait a little longer for a redirect
    try:
        page.wait_for_url("**/arbs*", timeout=5000)
        return True
    except PlaywrightTimeoutError:
        return False


def do_login(email: str, password: str, base_url: str, arbs_path: str, user_data_dir: Path, headless: bool = True) -> int:
    arbs_url = base_url.rstrip("/") + arbs_path
    login_urls = guess_login_urls(base_url.rstrip("/"))

    with sync_playwright() as p:
        log("info", "Launching persistent context", engine="chromium", headless=headless, user_data_dir=str(user_data_dir))
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=headless,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()

            # Try candidate login URLs until we find the form
            found_form = False
            for url in login_urls:
                log("info", "Navigating to login candidate", url=url)
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                try:
                    page.wait_for_selector('input[name="email"]', timeout=5000)
                    page.wait_for_selector('input[name="password"]', timeout=5000)
                    found_form = True
                    break
                except PlaywrightTimeoutError:
                    continue

            if not found_form:
                log("error", "Login form not found on any candidate URLs. Aborting.")
                return 2

            # Fill and submit
            log("info", "Filling credentials")
            page.fill('input[name="email"]', email)
            page.fill('input[name="password"]', password)

            # Try different submit strategies
            submitted = False
            for selector in [
                'button[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("Sign in")',
                'button:has-text("Iniciar sesión")',
            ]:
                try:
                    if page.is_visible(selector):
                        page.click(selector, timeout=5000)
                        submitted = True
                        break
                except Exception:
                    continue
            if not submitted:
                # Fallback: press Enter in password field
                page.press('input[name="password"]', "Enter")

            # Wait for success
            ok = wait_for_login_success(page, login_url=page.url, arbs_url=arbs_url, timeout_ms=20000)
            if not ok:
                log("error", "Login not confirmed. Check credentials or potential captcha.")
                return 3

            # Optionally navigate to arbs to warm session
            try:
                page.goto(arbs_url, timeout=20000, wait_until="domcontentloaded")
            except Exception:
                pass

            log("info", "Login completed and session persisted.")
            return 0
        finally:
            try:
                context.close()
            except Exception:
                pass


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    load_env_file(env_path)

    email = os.environ.get("BETBURGER_EMAIL", "").strip()
    password = os.environ.get("BETBURGER_PASSWORD", "").strip()
    base = os.environ.get("BETBURGER_BASE", "https://betburger.com").strip()
    arbs_path = os.environ.get("BETBURGER_PATH", "/es/arbs").strip()

    if not email or not password:
        log("error", "Missing BETBURGER_EMAIL or BETBURGER_PASSWORD in environment/.env")
        return 1

    user_data_dir = project_root / "logs" / "playwright_profile"
    user_data_dir.mkdir(parents=True, exist_ok=True)

    headless = env_bool("BOT_HEADLESS", True)
    code = do_login(email=email, password=password, base_url=base, arbs_path=arbs_path, user_data_dir=user_data_dir, headless=headless)
    return code


if __name__ == "__main__":
    sys.exit(main())
