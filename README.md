# Bot-de-arbitraje-Telegram
Bot para scraping de alertas de arbitraje (Betburger / Surebet) con ejecución dockerizada, perfiles con/ sin VPN y pruebas rápidas.

## Requisitos
- Docker y Docker Compose
- Python 3.11 (solo si ejecutarás scripts fuera de contenedor)

## Estructura relevante
- `docker-compose.selenium.yml`: servicios Selenium (Firefox) y bot (`bot-once`, `bot-once-vpn`).
- `Dockerfile.firefox-vpn`: imagen Firefox con política que instala la extensión SandVPN.
- `Dockerfile.bot`: imagen runner de Python con dependencias cacheadas (instala `requirements.txt` en build-time).
- `firefox-policies/policies.json`: instala `extensions/sandvpn-*.xpi` dentro del contenedor.
- `scripts/run_stack.sh`: lanzador con flags `--vpn`, `--attach`, `--once`.
- `test_tab_connection.py`: prueba de conexión y siembra de pestañas.

## Perfiles de ejecución
- __novpn__: Selenium Firefox estándar. Útil para desarrollo básico.
- __vpn__: Selenium Firefox con extensión SandVPN instalada y perfil persistente.

## Build inicial
```bash
# Desde Bot-de-arbitraje-Telegram
docker compose -f docker-compose.selenium.yml --profile novpn build selenium-firefox bot-once
docker compose -f docker-compose.selenium.yml --profile vpn   build selenium-firefox-vpn bot-once-vpn
```

## Ejecución rápida
- Sin VPN (normal):
```bash
./scripts/run_stack.sh --once
# GUI noVNC: http://localhost:7900  | Selenium: http://localhost:4444/wd/hub
```

- Con VPN (sin incógnito, pre‑espera para conectar SandVPN):
```bash
./scripts/run_stack.sh --vpn --once
# Tendrás PRE_SEED_WAIT_SECONDS (por defecto 60s) para pulsar CONNECT en la UI de SandVPN.
# Luego se abren 2 pestañas (Betburger/Surebet) y el script espera SEED_WAIT_SECONDS (300s por defecto).
```

## Variables de entorno principales
- `WEBDRIVER_REMOTE_URL`: URL del Selenium remoto (configurada en compose).
- `SEED_TEST_TABS` (true/false): abrir pestañas de prueba.
- `PRE_SEED_WAIT_SECONDS`: pausa previa para conectar VPN manualmente.
- `SEED_WAIT_SECONDS`: espera posterior para depuración en noVNC.
- `TEST_BETBURGER_URL`, `TEST_SUREBET_URL`: URLs objetivo.
- `BROWSER_PRIVATE_MODE` (opcional): si se activa, Firefox arranca en privado (no activo por defecto).

## Persistencia del perfil (VPN)
El servicio `selenium-firefox-vpn` monta `selenium_profile_vpn:/home/seluser`, por lo que ajustes (permisos de extensión, preferencias) persisten entre reinicios.

## Próximos pasos
- Scraping básico de Betburger/Surebet desde pestañas activas.
- Automatizar “CONNECT” de SandVPN y validar IP pública.

