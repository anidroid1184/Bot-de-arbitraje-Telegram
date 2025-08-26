"""OCR utilities to extract text from screenshots (optional dependency).

- Requires system package `tesseract-ocr` installed (Ubuntu/Debian: sudo apt install -y tesseract-ocr)
- Requires Python packages: pillow, pytesseract

APIs are resilient: if OCR is not available, functions return empty strings and log warnings.
"""
from __future__ import annotations

import io
import os
import shutil
from typing import Optional

try:
    from PIL import Image  # type: ignore
    import pytesseract  # type: ignore
except Exception:  # Packages may not be installed
    Image = None  # type: ignore
    pytesseract = None  # type: ignore

from ..utils.logger import get_module_logger

logger = get_module_logger("ocr_utils")


def _ocr_available() -> bool:
    if Image is None or pytesseract is None:
        return False
    if not shutil.which("tesseract"):
        return False
    return True


def ocr_png_bytes(png_bytes: bytes, lang: str = "eng") -> str:
    """Run OCR on a PNG image (bytes). Returns extracted text or empty string if unavailable.
    """
    try:
        if not _ocr_available():
            return ""
        with Image.open(io.BytesIO(png_bytes)) as im:  # type: ignore
            # Convert to grayscale to improve OCR
            im = im.convert("L")
            text = pytesseract.image_to_string(im, lang=lang)  # type: ignore
            return (text or "").strip()
    except Exception as e:
        logger.warning("OCR failed on PNG bytes", error=str(e))
        return ""


def ocr_webelement(element, lang: str = "eng") -> str:
    """Screenshot a Selenium WebElement and OCR it. Returns extracted text or empty string.
    The element should be scrolled into view before calling this.
    """
    try:
        if not _ocr_available():
            return ""
        png = element.screenshot_as_png  # type: ignore[attr-defined]
        return ocr_png_bytes(png, lang=lang)
    except Exception as e:
        logger.warning("OCR failed on WebElement", error=str(e))
        return ""


def ocr_fullpage(driver, lang: str = "eng") -> str:
    """Take a full-page screenshot and OCR it. Returns extracted text or empty string."""
    try:
        if not _ocr_available():
            return ""
        png = driver.get_screenshot_as_png()
        return ocr_png_bytes(png, lang=lang)
    except Exception as e:
        logger.warning("OCR failed on fullpage screenshot", error=str(e))
        return ""
