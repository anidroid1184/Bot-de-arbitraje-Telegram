"""
Tarea 2.1 - Scraping de Betburger (HTML crudo)
- Conecta al navegador (Selenium remoto si WEBDRIVER_REMOTE_URL está definido)
- Descubre pestañas abiertas
- Selecciona la primera pestaña de Betburger y imprime el HTML crudo
- Guarda una copia en logs/raw_html/betburger_<timestamp>.html
"""
from __future__ import annotations
import os
import sys
import time
from typing import Optional

# Asegurar que podemos importar como paquete 'src' al ejecutar directamente
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logger import get_module_logger  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.browser.tab_manager import TabManager  # type: ignore

logger = get_module_logger("scrape_betburger_raw")


def ensure_dirs(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def pick_first_betburger_tab(tabs: dict[str, str]) -> Optional[str]:
    for key in tabs.keys():
        if key.startswith("betburger"):
            return key
    return None


def main() -> int:
    cfg = ConfigManager()
    bot_cfg = cfg.bot

    tm = TabManager(bot_cfg)
    if not tm.connect_to_existing_browser():
        logger.error("No fue posible conectar con el navegador (Selenium)")
        return 2

    try:
        tabs = tm.discover_tabs()
        if not tabs:
            logger.error("No se detectaron pestañas abiertas")
            return 3

        tab_key = pick_first_betburger_tab(tabs)
        if not tab_key:
            logger.error("No se encontró una pestaña de Betburger abierta")
            logger.info(f"Pestañas detectadas: {list(tabs.keys())}")
            return 4

        html = tm.get_page_source(tab_key)
        if not html:
            logger.error("No se pudo obtener el HTML de la pestaña de Betburger")
            return 5

        # Imprimir a stdout (validación rápida)
        print(html)

        # Guardar copia en disco para inspección
        out_dir = os.path.join(os.getcwd(), "logs", "raw_html")
        ensure_dirs(out_dir)
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(out_dir, f"betburger_{ts}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("HTML crudo de Betburger guardado", path=out_path)
        return 0

    finally:
        # No cerramos el navegador para mantener la sesión; solo liberamos referencia
        tm.close()


if __name__ == "__main__":
    raise SystemExit(main())
