"""
Scrape snapshot for Betburger and Surebet.
- Connects to the existing Selenium Firefox (remote via WEBDRIVER_REMOTE_URL)
- Finds first Betburger and first Surebet tab
- Saves raw HTML of each into logs/raw_html/
- Builds an index HTML linking to the saved files and opens it as a new tab,
  so you can visually confirm from noVNC without inspecting terminal output.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional, Dict

# Ensure package import when running directly
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import get_module_logger  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.browser.tab_manager import TabManager  # type: ignore

logger = get_module_logger("scrape_snapshot")


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def pick_first(keys: Dict[str, str], prefix: str) -> Optional[str]:
    for k in keys:
        if k.startswith(prefix):
            return k
    return None


def log_all_tabs(tm: TabManager) -> None:
    try:
        handles = tm.driver.window_handles if tm.driver else []
        logger.info(f"Ventanas detectadas: {len(handles)}")
        for h in handles:
            try:
                tm.driver.switch_to.window(h)
                title = tm.driver.title
                try:
                    url = tm.driver.current_url
                except Exception as ue:
                    url = f"<sin current_url> ({ue})"
                logger.info("TAB", handle=h, title=title, url=url)
            except Exception as e:
                logger.warning("No se pudo inspeccionar una pestaña", error=str(e))
    except Exception as e:
        logger.warning("Fallo al listar pestañas", error=str(e))


def find_or_add_by_domain(tm: TabManager, domain_sub: str, key_prefix: str) -> Optional[str]:
    """Busca una pestaña cuyo URL contenga domain_sub y la añade a tm.tabs con un key_prefix si la encuentra."""
    try:
        if not tm.driver:
            return None
        for h in tm.driver.window_handles:
            try:
                tm.driver.switch_to.window(h)
                try:
                    url = tm.driver.current_url
                except Exception:
                    url = ""
                if domain_sub in url:
                    # Generar key único y registrar
                    existing = [k for k in tm.tabs.keys() if k.startswith(key_prefix)]
                    tab_key = f"{key_prefix}_{len(existing)}"
                    tm.tabs[tab_key] = h
                    logger.info("Asignado tab por dominio", tab_key=tab_key, url=url)
                    return tab_key
            except Exception:
                continue
    except Exception:
        return None
    return None


def save_html(out_dir: Path, name: str, html: str) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"{name}_{ts}.html"
    path.write_text(html, encoding="utf-8")
    logger.info("Saved HTML", file=str(path))
    return path


def write_index(out_dir: Path, bet_path: Optional[Path], sure_path: Optional[Path]) -> Path:
    idx = out_dir / "index.html"
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    def link_or_na(path: Optional[Path], label: str) -> str:
        if not path:
            return f"<li>{label}: <em>no disponible</em></li>"
        return f"<li>{label}: <a href='{path.name}' target='_blank'>{path.name}</a></li>"

    html = f"""
<!doctype html>
<html lang='es'>
<head>
<meta charset='utf-8'>
<title>Scrape Snapshot Index</title>
<style>
 body {{ font-family: Arial, sans-serif; margin: 24px; }}
 h1 {{ margin-bottom: 8px; }}
 .meta {{ color: #666; margin-bottom: 16px; }}
 li {{ margin: 6px 0; }}
</style>
</head>
<body>
  <h1>Scrape Snapshot</h1>
  <div class='meta'>Generado: {ts}</div>
  <ul>
    {link_or_na(bet_path, 'Betburger')}
    {link_or_na(sure_path, 'Surebet')}
  </ul>
  <p>Los archivos se guardan en <code>{out_dir.as_posix()}</code>.</p>
</body>
</html>
"""
    idx.write_text(html, encoding="utf-8")
    logger.info("Wrote index", file=str(idx))
    return idx


def main() -> int:
    cfg = ConfigManager()
    bot_cfg = cfg.bot

    logger.info("==== INICIO: Snapshot de scraping (Betburger y Surebet) ====")
    tm = TabManager(bot_cfg)
    if not tm.connect_to_existing_browser():
        logger.error("No fue posible conectar con el navegador (Selenium)")
        return 2

    bet_path: Optional[Path] = None
    sure_path: Optional[Path] = None
    out_dir = Path(os.getcwd()) / "logs" / "raw_html"
    ensure_dir(out_dir)

    try:
        logger.info("Descubriendo pestañas abiertas...")
        tabs = tm.discover_tabs()
        # Loguear todas las pestañas con título y URL para diagnóstico
        log_all_tabs(tm)
        if not tabs:
            logger.error("No se detectaron pestañas abiertas")
            return 3

        bet_key = pick_first(tabs, "betburger")
        sure_key = pick_first(tabs, "surebet")

        # Fallback: si no se detectaron por discover_tabs, intentar por URL directamente
        if not bet_key:
            bet_key = find_or_add_by_domain(tm, "betburger.com", "betburger")
        if not sure_key:
            sure_key = find_or_add_by_domain(tm, "surebet.com", "surebet")

        if bet_key:
            logger.info("Comenzando scraping: Betburger")
            html = tm.get_page_source(bet_key)
            if html:
                bet_path = save_html(out_dir, "betburger", html)
            else:
                logger.warning("No se pudo obtener HTML de Betburger")
        else:
            logger.warning("No se encontró pestaña de Betburger")

        if sure_key:
            logger.info("Comenzando scraping: Surebet")
            html = tm.get_page_source(sure_key)
            if html:
                sure_path = save_html(out_dir, "surebet", html)
            else:
                logger.warning("No se pudo obtener HTML de Surebet")
        else:
            logger.warning("No se encontró pestaña de Surebet")

        logger.info("Construyendo índice de resultados...")
        idx = write_index(out_dir, bet_path, sure_path)

        # Abrir el índice: 1) intentar file:// si el FS es compartido; 2) siempre abrir pestaña inline con el HTML.
        # Nota: en Docker, el runner y el contenedor Selenium no comparten necesariamente el mismo FS.
        try:
            file_url = idx.resolve().as_uri()
            tm.driver.execute_script(f"window.open('{file_url}', '_blank');")
            logger.info("Opened index via file URL", url=file_url)
        except Exception as e:
            logger.warning("No se pudo abrir el índice por file:// (es normal en entornos Docker aislados)", error=str(e))

        # Abrir pestaña inline con el contenido del índice para asegurar visualización desde noVNC
        try:
            html = idx.read_text(encoding="utf-8")
            tm.driver.execute_script(
                "var w=window.open('about:blank','_blank');"
                "w.document.open();"
                "w.document.write(arguments[0]);"
                "w.document.close();",
                html,
            )
            logger.info("Opened inline index in browser tab")
        except Exception as e:
            logger.warning("No se pudo abrir el índice inline", error=str(e))

        logger.info("==== FIN: Snapshot de scraping completado ====")
        return 0

    finally:
        # Mantener la sesión abierta; solo liberar driver
        tm.close()


if __name__ == "__main__":
    raise SystemExit(main())
