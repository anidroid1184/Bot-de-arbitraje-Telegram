"""
Surebet navigation and filter helpers using Selenium.

This module focuses on the right sidebar 'Filtrar apuestas seguras' controls:
- Selecting a saved filter from the 'Filtro' <select>
- Optionally adjusting other controls in the future

APIs return True/False and never raise to keep smoke flows robust.
"""
from __future__ import annotations

import time
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..utils.logger import get_module_logger

logger = get_module_logger("surebet_nav")


def _find_sidebar(driver, timeout: int = 10):
    """Locate the right sidebar container for filters.

    We search for a heading containing 'Filtrar apuestas seguras' (ES) or 'Filter'
    and return its closest container element.
    """
    wait = WebDriverWait(driver, timeout)
    # Find the header element that contains the text
    header_xps = [
        "//div//*[self::h2 or self::h3 or self::div][contains(translate(normalize-space(.), 'FILTRAR Apuestas Seguras', 'filtrar apuestas seguras'), 'filtrar apuestas seguras')]",
        "//div//*[self::h2 or self::h3 or self::div][contains(translate(normalize-space(.), 'FILTER Safe Bets', 'filter safe bets'), 'filter')]",
    ]
    for xp in header_xps:
        try:
            header = wait.until(EC.presence_of_element_located((By.XPATH, xp)))
            container = header.find_element(By.XPATH, "ancestor::div[1]")
            return container
        except TimeoutException:
            continue
        except Exception:
            continue
    return None


def select_saved_filter(driver, filter_name: str, timeout: int = 10) -> bool:
    """Choose a saved filter by its visible name in the right sidebar.

    It looks for a label containing 'Filtro' and then the adjacent <select>.
    """
    try:
        sidebar = _find_sidebar(driver, timeout=timeout)
        if not sidebar:
            logger.warning("Surebet sidebar not found")
            return False

        # Locate the select for 'Filtro'
        # Strategy: find a label with text 'Filtro' then its following select
        label_xp = ".//label[contains(translate(normalize-space(.), 'FILTRO', 'filtro'), 'filtro')]|.//div[contains(@class,'label') and contains(.,'Filtro')]"
        try:
            label_el = sidebar.find_element(By.XPATH, label_xp)
            select_el = label_el.find_element(By.XPATH, "following::select[1]")
        except NoSuchElementException:
            # Fallback: directly find first select inside sidebar
            select_el = sidebar.find_element(By.XPATH, ".//select[1]")

        sel = Select(select_el)
        sel.select_by_visible_text(filter_name)
        time.sleep(0.3)
        logger.info("Surebet filter selected", name=filter_name)
        return True
    except Exception as e:
        logger.error("Failed to select Surebet filter", name=filter_name, error=str(e))
        return False


def apply_modal(driver, button_text_candidates: list[str] = None, timeout: int = 8) -> bool:
    """Click a generic 'Aplicar y filtrar' button when a modal is open.

    Not strictly needed for saved filter selection, but useful for bookmakers/sports selections.
    """
    if button_text_candidates is None:
        button_text_candidates = ["aplicar y filtrar", "apply", "aplicar"]
    try:
        wait = WebDriverWait(driver, timeout)
        for txt in button_text_candidates:
            xp = (
                "//button|//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÜ', "
                "'abcdefghijklmnopqrstuvwxyzáéíóúü'), '" + txt + "')]"
            )
            try:
                btn = wait.until(EC.element_to_be_clickable((By.XPATH, xp)))
                btn.click()
                time.sleep(0.3)
                return True
            except TimeoutException:
                continue
            except Exception:
                continue
        return False
    except Exception:
        return False


def get_selected_filter_name(driver, timeout: int = 10) -> Optional[str]:
    """Return the visible text of the currently selected saved filter.

    Looks up the same 'Filtro' <select> used by select_saved_filter and
    returns the first selected option's visible text.
    """
    try:
        sidebar = _find_sidebar(driver, timeout=timeout)
        if not sidebar:
            logger.warning("Surebet sidebar not found to read selected filter")
            return None

        label_xp = ".//label[contains(translate(normalize-space(.), 'FILTRO', 'filtro'), 'filtro')]|.//div[contains(@class,'label') and contains(.,'Filtro')]"
        try:
            label_el = sidebar.find_element(By.XPATH, label_xp)
            select_el = label_el.find_element(By.XPATH, "following::select[1]")
        except NoSuchElementException:
            select_el = sidebar.find_element(By.XPATH, ".//select[1]")

        sel = Select(select_el)
        try:
            opt = sel.first_selected_option
            name = (opt.text or "").strip()
            return name or None
        except Exception:
            return None
    except Exception as e:
        logger.warning("Failed to read selected filter name", error=str(e))
        return None
