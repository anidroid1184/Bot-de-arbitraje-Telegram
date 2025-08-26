"""
Smoke: Betburger -> login (with "Recordarme"), go to /es/arbs, duplicate tabs to N.

- Uses local Firefox by default (headful if BOT_HEADLESS=false)
- Honors WEBDRIVER_REMOTE_URL if set
- Tab count controlled by BETBURGER_TABS (default 6)

Run:
  python -m scripts.smoke_betburger_arbs_tabs

Requirements (.env):
  BETBURGER_USERNAME, BETBURGER_PASSWORD
  BOT_HEADLESS=false (to supervise visually)
Optional:
  BETBURGER_TABS=6
  WEBDRIVER_REMOTE_URL=<http://host:4444/wd/hub>
  FIREFOX_BINARY=<path> (when needed)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional

# Ensure package imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.logger import get_module_logger  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.browser.tab_manager import TabManager  # type: ignore
from src.browser.session_store import save_session  # type: ignore
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException  # type: ignore
from selenium.webdriver.common.keys import Keys  # type: ignore

logger = get_module_logger("smoke_betburger_arbs_tabs")


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def save_debug_html(prefix: str, driver) -> None:
    try:
        root = Path.cwd() / "logs" / "raw_html"
        root.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        p = root / f"{prefix}_{ts}.html"
        p.write_text(driver.page_source or "", encoding="utf-8")
        logger.info("Saved debug HTML", file=str(p))
    except Exception:
        pass


def dismiss_cookies_banner(driver) -> None:
    """Best-effort cookie consent dismissal for Betburger."""
    try:
        candidates = [
            "//button[contains(translate(., 'ACEPTAR', 'aceptar'), 'acept')]",
            "//button[contains(translate(., 'AGREE', 'agree'), 'agree')]",
            "//button[contains(., 'OK') or contains(., 'Ok') or contains(., 'ok')]",
            "//div[contains(@class,'cookie') or contains(@id,'cookie')]//button",
        ]
        for xp in candidates:
            try:
                el = driver.find_element(By.XPATH, xp)
                driver.execute_script("arguments[0].click();", el)
                time.sleep(0.3)
                break
            except Exception:
                continue
    except Exception:
        pass


def click_remember_me_if_present(driver) -> None:
    """Best-effort to tick the 'Recordarme' checkbox on Betburger login page."""
    try:
        # Try common selectors around the login form
        candidates = [
            "//input[@type='checkbox' and (contains(@id,'remember') or contains(@name,'remember'))]",
            "//label[contains(translate(., 'RECORDARME', 'recordarme'), 'recordarme')]/preceding::input[@type='checkbox'][1]",
            "//label[contains(translate(., 'RECORDARME', 'recordarme'), 'recordarme')]/following::input[@type='checkbox'][1]",
        ]
        for xp in candidates:
            try:
                cb = driver.find_element(By.XPATH, xp)
                # Only click if not already selected
                if not cb.is_selected():
                    driver.execute_script("arguments[0].click();", cb)
                    time.sleep(0.2)
                logger.info("Remember-me checkbox ensured ON")
                return
            except Exception:
                continue
    except Exception:
        pass


def login_with_remember_me(driver, username: str, password: str, login_url: str, timeout: int = 45) -> None:
    logger.info("Opening Betburger login page", url=login_url)
    driver.get(login_url)

    wait = WebDriverWait(driver, timeout)
    # Give a chance to close cookie banner
    dismiss_cookies_banner(driver)

    # Email (tolerant selectors)
    email_field = wait.until(
        EC.presence_of_element_located((By.XPATH, "//input[contains(@type,'email') or contains(@name,'email')]"))
    )
    email_field.clear()
    email_field.send_keys(username)

    # Password
    pwd_field = driver.find_element(By.XPATH, "//input[contains(@type,'password') or contains(@name,'password')]")
    pwd_field.clear()
    pwd_field.send_keys(password)

    # Remember me (optional): requested to skip for now
    # click_remember_me_if_present(driver)

    # Submit (robust against cookie overlays)
    submit = driver.find_element(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
    # Run banner dismiss again in case it appeared late
    dismiss_cookies_banner(driver)
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit)
        submit.click()
    except ElementClickInterceptedException:
        # Fallback 1: press ENTER on password field
        try:
            pwd_field.send_keys(Keys.ENTER)
        except Exception:
            # Fallback 2: JS form submit
            try:
                driver.execute_script("document.querySelector('form').submit();")
            except Exception:
                raise

    # Wait for redirect or disappearance of login form, allow extra time
    end_time = time.time() + timeout
    success = False
    while time.time() < end_time:
        try:
            # Heuristics for success:
            # 1) Email field no longer present
            driver.find_element(By.XPATH, "//input[contains(@type,'email') or contains(@name,'email')]")
        except NoSuchElementException:
            success = True
            break
        except Exception:
            pass

        # 2) URL indicates we left the sign_in page or reached target area
        cur = driver.current_url or ""
        if "/users/sign_in" not in cur or "/es/arbs" in cur:
            success = True
            break
        time.sleep(0.5)

    # If still not successful, try to navigate directly to /es/arbs and accept if reached
    if not success:
        try:
            driver.get("https://www.betburger.com/es/arbs")
            WebDriverWait(driver, 10).until(lambda d: "/es/arbs" in (d.current_url or ""))
            success = True
        except Exception:
            success = False
    if not success:
        save_debug_html("betburger_login_FAIL", driver)
    _assert(success, "Login did not complete within expected time")
    logger.info("Login completed")


def duplicate_tabs_to(driver, target_count: int) -> None:
    """Duplicate current tab until window_handles reaches target_count."""
    _assert(target_count >= 1, "target_count must be >= 1")
    while len(driver.window_handles) < target_count:
        # Duplicate: open the same URL in a new window (tab)
        driver.execute_script("window.open(window.location.href, '_blank');")
        time.sleep(0.6)  # allow new tab to initialize
    logger.info("Tabs ready", count=len(driver.window_handles))


def main() -> int:
    cfg = ConfigManager()
    bot = cfg.bot

    # Default to headless when there is no DISPLAY (e.g., WSL without GUI)
    if not os.environ.get("DISPLAY") and not os.environ.get("BOT_HEADLESS"):
        os.environ["BOT_HEADLESS"] = "true"

    tm = TabManager(bot)
    if not tm.connect_to_existing_browser():
        logger.error("Unable to start/connect to Firefox")
        return 2

    try:
        # 1) Login with remember-me
        _assert(cfg.betburger.username and cfg.betburger.password, "Missing BETBURGER credentials in .env")
        login_with_remember_me(
            tm.driver,
            cfg.betburger.username,
            cfg.betburger.password,
            cfg.betburger.login_url,
            timeout=bot.browser_timeout,
        )

        # 2) Navigate directly to /es/arbs
        target_url = "https://www.betburger.com/es/arbs"
        logger.info("Navigating to target page", url=target_url)
        tm.driver.get(target_url)
        # Basic load wait
        try:
            WebDriverWait(tm.driver, bot.browser_timeout).until(
                lambda d: "betburger.com/es/arbs" in d.current_url
            )
        except TimeoutException:
            pass
        _assert("/es/arbs" in tm.driver.current_url, "Did not reach /es/arbs page")

        # 3) Duplicate tabs to N
        tabs = int(os.environ.get("BETBURGER_TABS", "6") or "6")
        duplicate_tabs_to(tm.driver, tabs)
        _assert(len(tm.driver.window_handles) == tabs, f"Expected {tabs} tabs, got {len(tm.driver.window_handles)}")

        # Save session for reuse by other processes if running against Remote
        try:
            remote_url = os.environ.get("WEBDRIVER_REMOTE_URL")
            if remote_url:
                sess_file = os.environ.get("WEBDRIVER_SESSION_FILE", str((Path.cwd() / "logs" / "session" / "betburger.json")))
                save_session(Path(sess_file), tm.driver, remote_url)
        except Exception as se:
            logger.warning("Could not persist WebDriver session (non-fatal)", error=str(se))

        logger.info("Smoke completed: login + /es/arbs + duplicated tabs", tabs=len(tm.driver.window_handles))
        # Keep the browser open for manual supervision; comment out to auto-close
        return 0

    except Exception as e:
        logger.error("Smoke failed", error=str(e))
        return 1
    finally:
        # Do NOT close to allow visual inspection when running interactively.
        # If you need auto-close, uncomment below.
        # try:
        #     tm.close()
        # except Exception:
        #     pass
        pass


if __name__ == "__main__":
    raise SystemExit(main())
