"""
Betburger navigation helpers using Selenium.

Functions here are best-effort and rely on robust XPaths that match
Spanish/English UI labels (contains + translate for case-insensitivity).

Usage example:
    from src.browser.betburger_nav import open_filters_page, open_bookmakers_page
    open_filters_page(driver)

All functions return True on success, False otherwise, and never raise.
"""
from __future__ import annotations

import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..utils.logger import get_module_logger

logger = get_module_logger("betburger_nav")


def _click_sidebar_link(driver, text_candidates: list[str], timeout: int = 15) -> bool:
    """Click a left-sidebar link by visible label.

    Tries several text candidates to handle ES/EN variations.
    """
    try:
        wait = WebDriverWait(driver, timeout)
        for txt in text_candidates:
            # Match any link with the text (case-insensitive) anywhere in the page
            xp = (
                "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÜ', "
                "'abcdefghijklmnopqrstuvwxyzáéíóúü'), "
                f"'{txt.lower()}')]"
            )
            try:
                el = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
                el.click()
                time.sleep(0.5)
                logger.debug("Clicked sidebar link", label=txt)
                return True
            except TimeoutException:
                continue
            except Exception:
                continue
        logger.warning("Sidebar link not found for any candidate", candidates=",".join(text_candidates))
        return False
    except Exception as e:
        logger.error("Error clicking sidebar link", error=str(e))
        return False


def get_selected_saved_filter_name(driver, timeout: int = 10) -> Optional[str]:
    """Best-effort: read the currently selected saved filter name in Betburger UI.

    Heuristics:
    - Try finding a button/label in the header/filters area that shows the active saved filter name.
    - As a fallback, try to open the saved filters dropdown and read the item marked as selected.
    - If not found, return None.
    """
    try:
        wait = WebDriverWait(driver, timeout)
        # 1) Look for a header/toolbar button with a filter label
        candidates = [
            "//div[contains(@class,'filters')]//button[contains(@class,'active') or contains(@class,'selected')][1]",
            "//button[contains(@class,'filters') or contains(.,'Saved') or contains(.,'Guardados')][1]",
            "//div[contains(@class,'header') or contains(@class,'toolbar')]//button[contains(@class,'active') or contains(@class,'selected')][1]",
        ]
        for xp in candidates:
            try:
                btn = wait.until(EC.presence_of_element_located((By.XPATH, xp)))
                txt = (btn.text or "").strip()
                if txt:
                    return txt
            except Exception:
                continue

        # 2) Try open the dropdown and read selected item
        try:
            # Attempt open (reuse triggers from _apply_ui_filter)
            triggers = [
                "//button[contains(., 'Saved') or contains(., 'Guardados') or contains(., 'Filtros')]",
                "//div[contains(@class,'filters')]//button",
                "//span[contains(., 'Saved') or contains(., 'Guardados')]/ancestor::button[1]",
            ]
            opened = False
            for xp in triggers:
                try:
                    el = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
                    driver.execute_script("arguments[0].click();", el)
                    opened = True
                    break
                except Exception:
                    continue
            if opened:
                # Look for selected/checked item
                sel_xps = [
                    "//li[@aria-selected='true']",
                    "//li[contains(@class,'selected') or contains(@class,'active')]",
                    "//*[self::li or self::div or self::a][contains(@class,'selected') or contains(@class,'active')]",
                ]
                for sxp in sel_xps:
                    try:
                        node = wait.until(EC.presence_of_element_located((By.XPATH, sxp)))
                        txt = (node.text or "").strip()
                        if txt:
                            return txt
                    except Exception:
                        continue
        except Exception:
            pass
    except Exception as e:
        logger.warning("Failed to read selected saved filter name", error=str(e))
        return None
    return None


def open_bookmakers_page(driver) -> bool:
    """Navigate to Casas de apuestas page.

    Returns True if navigation likely succeeded.
    """
    return _click_sidebar_link(driver, ["casas de apuestas", "bookmakers"])  # ES/EN


def open_filters_page(driver) -> bool:
    """Navigate to Filtros page.

    Returns True if navigation likely succeeded.
    """
    return _click_sidebar_link(driver, ["filtros", "filters"])  # ES/EN


def _click_filters_tab(driver, tab_candidates: list[str], timeout: int = 10) -> bool:
    """Click a tab inside the Filters page (e.g., Valuebet Prematch)."""
    try:
        wait = WebDriverWait(driver, timeout)
        for txt in tab_candidates:
            xp = (
                "//a[contains(@class,'nav') or contains(@class,'tab')][contains(translate(normalize-space(.), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÜ', 'abcdefghijklmnopqrstuvwxyzáéíóúü'), "
                f"'{txt.lower()}')]"
            )
            try:
                el = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
                el.click()
                time.sleep(0.4)
                logger.debug("Clicked filters tab", tab=txt)
                return True
            except TimeoutException:
                continue
            except Exception:
                continue
        logger.warning("Filters tab not found", candidates=",".join(tab_candidates))
        return False
    except Exception as e:
        logger.error("Error clicking filters tab", error=str(e))
        return False


def open_filters_valuebet_prematch(driver) -> bool:
    """Open the Valuebet Prematch tab within Filters page."""
    return _click_filters_tab(driver, ["valuebet prematch", "valuebet pre", "valuebets prematch"])  # variants


def open_filters_surebets_prematch(driver) -> bool:
    """Open the Surebets Prematch tab within Filters page."""
    return _click_filters_tab(driver, ["surebets prematch", "surebets pre"])  # variants


def open_filter_by_name_or_id(driver, query: str, timeout: int = 10) -> bool:
    """Open a specific filter row by its displayed Name or ID.

    Strategy:
    - Find a table row where any cell contains the query (case-insensitive).
    - Prefer clicking the edit pencil in that row if available; otherwise click the row link.
    """
    try:
        wait = WebDriverWait(driver, timeout)
        # Row that contains the text in any cell
        row_xp = (
            "//table//tr[.//td[contains(translate(normalize-space(.), "
            "'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÜ', 'abcdefghijklmnopqrstuvwxyzáéíóúü'), "
            f"'{query.lower()}')]]"
        )
        row = wait.until(EC.presence_of_element_located((By.XPATH, row_xp)))
        # Try pencil/edit within the row
        try:
            edit = row.find_element(By.XPATH, ".//a[contains(@href,'edit') or contains(@title,'Edit') or contains(@class,'edit')]")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", edit)
            time.sleep(0.1)
            edit.click()
            time.sleep(0.5)
            logger.info("Opened filter via Edit", query=query)
            return True
        except NoSuchElementException:
            pass
        # Fallback: click the row itself
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", row)
            time.sleep(0.1)
            row.click()
            time.sleep(0.5)
            logger.info("Opened filter via row click", query=query)
            return True
        except Exception:
            logger.warning("Could not click filter row", query=query)
            return False
    except TimeoutException:
        logger.warning("Filter row not found", query=query)
        return False
    except Exception as e:
        logger.error("Error opening filter", query=query, error=str(e))
        return False
