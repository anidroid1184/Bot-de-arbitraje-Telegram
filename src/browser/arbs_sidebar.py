"""
Helpers for Betburger /es/arbs left sidebar interactions (Filtros section).

Functions are tolerant to ES/EN UI. They attempt not to raise; return bools.
"""
from __future__ import annotations

import time
from typing import Optional
from selenium.webdriver.common.by import By  # type: ignore
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
from selenium.webdriver.support import expected_conditions as EC  # type: ignore
from selenium.common.exceptions import TimeoutException, NoSuchElementException  # type: ignore

from ..utils.logger import get_module_logger

logger = get_module_logger("arbs_sidebar")


def _find_filters_container(driver, timeout: int = 10):
    """Locate the Filtros container element in the /es/arbs sidebar."""
    wait = WebDriverWait(driver, timeout)
    # Look for a heading/span containing Filtros/Filters and get nearest container
    try:
        heading = wait.until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    "//div[contains(@class,'left') or contains(@class,'sidebar')]//*[contains(translate(normalize-space(.), 'FILTERSFILTROS', 'filtersfiltros'), 'filtros') or contains(translate(normalize-space(.), 'FILTERSFILTROS', 'filtersfiltros'), 'filters')][1]"
                )
            )
        )
        # Climb to a reasonable container
        container = heading.find_element(By.XPATH, ".//ancestor::div[contains(@class,'left') or contains(@class,'sidebar')][1]")
        return container
    except Exception:
        # Fallback to any area that lists checkboxes for filters
        try:
            return driver.find_element(By.XPATH, "//div[contains(@class,'sidebar')]//input[@type='checkbox']/ancestor::div[1]")
        except Exception:
            return None


def list_filters(driver, timeout: int = 10) -> list[tuple[str, object]]:
    """Return list of (label_text, checkbox_element) for visible filters."""
    container = _find_filters_container(driver, timeout)
    if not container:
        logger.warning("Filters container not found")
        return []
    results: list[tuple[str, object]] = []
    # Each filter appears as a label + checkbox; collect pairs
    items = container.find_elements(By.XPATH, ".//label|.//span|.//div")
    for el in items:
        try:
            # Skip empty labels
            txt = (el.text or "").strip()
            if not txt:
                continue
            # Nearest checkbox to this label
            try:
                cb = el.find_element(By.XPATH, ".//preceding::input[@type='checkbox'][1]")
            except NoSuchElementException:
                try:
                    cb = el.find_element(By.XPATH, ".//following::input[@type='checkbox'][1]")
                except NoSuchElementException:
                    continue
            results.append((txt, cb))
        except Exception:
            continue
    # Deduplicate by label text
    seen = set()
    uniq: list[tuple[str, object]] = []
    for txt, cb in results:
        key = txt.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append((txt, cb))
    return uniq


def select_only_filter(driver, name_query: str, timeout: int = 10) -> bool:
    """Ensure exactly one filter is selected by approximate label match; others off.

    name_query: substring to match (case-insensitive)
    """
    try:
        wait = WebDriverWait(driver, timeout)
        # Wait for at least one checkbox to exist
        wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='checkbox']")))
        filters = list_filters(driver, timeout)
        if not filters:
            logger.warning("No filters listed")
            return False
        target = None
        for label, cb in filters:
            if name_query.lower() in label.lower():
                target = (label, cb)
                break
        if not target:
            logger.warning("Filter not found", query=name_query)
            return False
        # Uncheck all others
        for label, cb in filters:
            try:
                if cb.is_selected() and label != target[0]:
                    driver.execute_script("arguments[0].click();", cb)
                    time.sleep(0.1)
            except Exception:
                continue
        # Ensure target checked
        try:
            if not target[1].is_selected():
                driver.execute_script("arguments[0].click();", target[1])
                time.sleep(0.2)
        except Exception:
            return False
        # Validate exactly one checked
        checked = [1 for _, cb in filters if cb.is_selected()]
        ok = sum(checked) == 1
        if not ok:
            logger.warning("More than one filter appears selected")
        return ok
    except Exception as e:
        logger.error("Error selecting filter", query=name_query, error=str(e))
        return False
