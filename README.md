# Bot-de-arbitraje-Telegram
Bot para scraping de alertas de arbitraje (Betburger / Surebet) ejecutado localmente en Python (sin Docker, sin VPN).

## Requisitos
- Python 3.11+
- Playwright instalado con navegadores (ver Quickstart Linux)

## Estructura relevante
- `src/`: código fuente del bot.
  - `src/browser/`: conexión Selenium y gestión de pestañas (`TabManager`, `AuthManager`).
  - `src/config/`: carga de `.env` y `channels.yaml` (`ConfigManager`).
  - `src/utils/`: logger y notificador de Telegram.
  - `src/smoke_login_and_scrape.py`: smoke test local de login+scraping.
- `logs/raw_html/`: capturas HTML crudo generadas por los scripts.
- `.env`: variables de entorno (no se versiona). Usa `.env.example` como guía.

## Configuración de entorno (.env)
Completa tu `.env` en la raíz del proyecto con:

```
TELEGRAM_BOT_TOKEN=...            # opcional para notificación
TELEGRAM_SUPPORT_CHANNEL_ID=...   # opcional; usar el chat_id -100...

BETBURGER_USERNAME=...
BETBURGER_PASSWORD=...
SUREBET_USERNAME=...
SUREBET_PASSWORD=...

HEADLESS_MODE=false               # true para ejecución sin UI
BROWSER_TIMEOUT=30
```

## Instalación (local)
```bash
# Crear entorno virtual (ejemplo Linux/macOS)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# En Windows PowerShell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Quickstart (Linux, sin proxy)
```bash
# 1) Clonar y preparar entorno
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# 2) Instalar navegadores de Playwright
python3 -m playwright install chromium

# 3) Configurar .env (mínimo para smoke)
cp .env.example .env
# Edita .env y asegúrate de NO definir PROXY_POOL_FILE para correr sin proxy
# Recomendado para smoke rápido:
# BOT_HEADLESS=true
# SMOKE_PER_TAB=0
# BETBURGER_TABS=2
# SUREBET_TABS=2
# SMOKE_IDLE_SECONDS=45

# 4) Ejecutar smoke test (Betburger; Surebet opcional)
python3 -m scripts.playwright_smoke_betburger_tabs
```

### Qué esperar en logs
- "Launching Playwright ... proxy=None ..." (sin proxy)
- "Tabs opened ... requested=2 count=2"
- Posibles detecciones de `filter_id` en tráfico Betburger (1218070 Codere, 1218528 Betfair).

## Troubleshooting
- "Page.goto: net::ERR_PROXY_CONNECTION_FAILED / net::ERR_TIMED_OUT":
  - Indica proxies inestables. Corre sin proxy (no definas `PROXY_POOL_FILE`), o usa un proxy de pago estable.
  - Si quieres filtrar proxies por esquema: `PROXY_ALLOWED_SCHEMES=http,https`.
- "No browser found" o Playwright no abre Chromium:
  - Ejecuta `python3 -m playwright install chromium` dentro del venv.
- Cuelgues al cerrar con Ctrl+C:
  - Espera unos segundos a que Playwright cierre contextos. Vuelve a ejecutar el comando.

## Ejecución rápida (local)
```bash
# Prueba de login + scraping y guardado de HTML
python -m src.smoke_login_and_scrape

# Prueba de conexión de pestañas y detección de CAPTCHA (opcional)
python test_tab_connection.py
```

## Logs y resultados
- HTML crudo: `logs/raw_html/` (por script, timestamped)
- Logs de ejecución: según configuración en `.env` (`LOG_FILE` por defecto `logs/bot.log`)

## Próximos pasos
- Parsing estructurado de Betburger y Surebet (JSON con campos clave).
- Envío de alertas a Telegram con formato enriquecido.
- Asignación de perfiles/filtros a canales por `config/channels.yaml`.

## Nota sobre Docker/VPN
Este proyecto se ejecuta localmente sin Docker ni VPN. Los artefactos históricos de VPN/Docker se han movido a la carpeta `.vpn/` y están excluidos del repositorio.

