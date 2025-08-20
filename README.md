# Bot-de-arbitraje-Telegram
Bot para scraping de alertas de arbitraje (Betburger / Surebet) ejecutado localmente en Python (sin Docker, sin VPN).

## Requisitos
- Python 3.11+
- Firefox instalado (Selenium Manager descargará geckodriver automáticamente)

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

