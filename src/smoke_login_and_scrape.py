"""
Smoke test (sin Docker):
- Inicia Selenium Firefox local (o remoto si WEBDRIVER_REMOTE_URL está definido)
- Autentica en Betburger y Surebet usando AuthManager
- Guarda HTML crudo de cada plataforma en logs/raw_html/
- Envía un resumen por Telegram (canal de soporte si está configurado)

Requisitos de entorno (.env):
- TELEGRAM_BOT_TOKEN, TELEGRAM_SUPPORT_CHANNEL_ID (opcional para notificación)
- BETBURGER_USERNAME, BETBURGER_PASSWORD
- SUREBET_USERNAME, SUREBET_PASSWORD

Ejecución:
  python -m src.smoke_login_and_scrape
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Optional

# Asegurar import como paquete 'src'
CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.logger import get_module_logger  # type: ignore
from src.utils.telegram_notifier import TelegramNotifier  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.browser.tab_manager import TabManager  # type: ignore
from src.browser.auth_manager import AuthManager  # type: ignore
from src.browser.betburger_nav import (  # type: ignore
    open_bookmakers_page,
    open_filters_page,
    open_filters_valuebet_prematch,
    open_filter_by_name_or_id,
)
from src.browser.surebet_nav import select_saved_filter  # type: ignore

logger = get_module_logger("smoke_login_and_scrape")


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def save_html(out_dir: Path, name: str, html: str) -> Path:
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"{name}_{ts}.html"
    path.write_text(html, encoding="utf-8")
    logger.info("Saved HTML", file=str(path))
    return path


def main() -> int:
    cfg = ConfigManager()
    bot_cfg = cfg.bot
    notifier = TelegramNotifier()

    # Validación básica de credenciales
    missing: list[str] = []
    if not cfg.betburger.username or not cfg.betburger.password:
        missing.append("BETBURGER_USERNAME/PASSWORD")
    if not cfg.surebet.username or not cfg.surebet.password:
        missing.append("SUREBET_USERNAME/PASSWORD")
    if missing:
        logger.error("Faltan variables en .env", missing=",".join(missing))

    logger.info("==== INICIO: Smoke test de login y scraping ====")
    logger.info(
        "Browser config",
        headless=bot_cfg.headless_mode,
        timeout=bot_cfg.browser_timeout,
    )
    logger.info(
        "Resolved URLs",
        betburger_login=cfg.betburger.login_url,
        betburger_base=cfg.betburger.base_url,
        surebet_login=cfg.surebet.login_url,
        surebet_base=cfg.surebet.base_url,
        surebet_valuebets=cfg.surebet.valuebets_url,
    )
    tm = TabManager(bot_cfg)
    if not tm.connect_to_existing_browser():
        logger.error("No fue posible iniciar/conectar Firefox (Selenium)")
        notifier.send_text("❌ Smoke: no fue posible iniciar/conectar Firefox (Selenium)")
        return 2

    auth = AuthManager(bot_cfg)
    out_dir = Path(os.getcwd()) / "logs" / "raw_html"
    ensure_dir(out_dir)

    bet_ok = False
    sure_ok = False
    bet_path: Optional[Path] = None
    sure_path: Optional[Path] = None

    try:
        # --- Betburger ---
        try:
            # Navegar a login/base y asegurar autenticación
            logger.info("Navigating to Betburger login", url=cfg.betburger.login_url or cfg.betburger.base_url)
            tm.driver.get(cfg.betburger.login_url or cfg.betburger.base_url)
            if auth.ensure_authenticated(tm.driver, "betburger", cfg.betburger):
                bet_ok = True
                # Navegación opcional vía sidebar según variables de entorno
                nav_target = os.getenv("SMOKE_BETBURGER_NAV", "base").lower()
                filt_query = os.getenv("SMOKE_BETBURGER_FILTER", "").strip()
                logger.info("Betburger nav target", target=nav_target, filter=filt_query or "<none>")

                if nav_target == "filters":
                    if open_filters_page(tm.driver):
                        # Abrimos la pestaña de Valuebet Prematch por defecto
                        open_filters_valuebet_prematch(tm.driver)
                        # Si se indica, intentamos abrir un filtro específico
                        if filt_query:
                            open_filter_by_name_or_id(tm.driver, filt_query)
                    time.sleep(2)
                    bet_html = tm.driver.page_source
                    bet_path = save_html(out_dir, "betburger_filters", bet_html)
                elif nav_target == "bookmakers":
                    if open_bookmakers_page(tm.driver):
                        time.sleep(2)
                    bet_html = tm.driver.page_source
                    bet_path = save_html(out_dir, "betburger_bookmakers", bet_html)
                else:
                    # Después de login, ir a base_url para capturar HTML
                    logger.info("Navigating to Betburger base", url=cfg.betburger.base_url)
                    tm.driver.get(cfg.betburger.base_url)
                    time.sleep(2)
                    bet_html = tm.driver.page_source
                    bet_path = save_html(out_dir, "betburger", bet_html)
            else:
                logger.error("Login Betburger fallido")
        except Exception as e:
            logger.error("Error en flujo Betburger", error=str(e))

        # --- Surebet ---
        try:
            logger.info("Navigating to Surebet login", url=cfg.surebet.login_url or cfg.surebet.base_url)
            tm.driver.get(cfg.surebet.login_url or cfg.surebet.base_url)
            if auth.ensure_authenticated(tm.driver, "surebet", cfg.surebet):
                sure_ok = True
                # Ir a valuebets o base_url
                target_url = cfg.surebet.valuebets_url or cfg.surebet.base_url
                logger.info("Navigating to Surebet target", url=target_url)
                tm.driver.get(target_url)
                time.sleep(2)
                # Si se especifica un filtro guardado, seleccionarlo en el sidebar
                sb_filter = os.getenv("SMOKE_SUREBET_FILTER", "").strip()
                if sb_filter:
                    logger.info("Surebet selecting saved filter", name=sb_filter)
                    select_saved_filter(tm.driver, sb_filter)
                    time.sleep(1.5)
                # Capturar HTML resultante
                sure_html = tm.driver.page_source
                name = "surebet_filtered" if sb_filter else "surebet"
                sure_path = save_html(out_dir, name, sure_html)
            else:
                logger.error("Login Surebet fallido")
        except Exception as e:
            logger.error("Error en flujo Surebet", error=str(e))

        # Notificación resumen
        status_emoji = "✅" if (bet_ok and sure_ok) else "⚠️" if (bet_ok or sure_ok) else "❌"
        summary_lines = [
            f"{status_emoji} Smoke test: login/scraping",
            f"Betburger: {'OK' if bet_ok else 'FAIL'}" + (f" → {bet_path.name}" if bet_path else ""),
            f"Surebet: {'OK' if sure_ok else 'FAIL'}" + (f" → {sure_path.name}" if sure_path else ""),
        ]
        notifier.send_text("\n".join(summary_lines))

        logger.info("==== FIN: Smoke test completado ====")
        return 0 if (bet_ok and sure_ok) else 1

    finally:
        # Mantener sesión abierta para depuración? Aquí cerramos para smoke aislado.
        try:
            tm.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
