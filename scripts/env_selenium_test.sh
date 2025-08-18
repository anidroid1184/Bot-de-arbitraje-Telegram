#!/usr/bin/env bash
# Uso: source ./scripts/env_selenium_test.sh
# Luego: ./scripts/run_selenium_test.sh
#
# Nota: Es preferible "source" para que las variables queden en tu shell actual.

# 1) Selenium Grid (contenedor docker de navegador)
export WEBDRIVER_URL="http://localhost:4444/wd/hub"

# 2) Modo headless o con GUI (noVNC)
#   true  = sin interfaz (rápido)
#   false = con interfaz (http://localhost:7900, password: secret)
export HEADLESS_MODE="false"

# 3) Sembrar pestañas de prueba automáticamente
export SEED_TEST_TABS="true"

# 4) Ventana de depuración manual tras abrir pestañas (segundos)
#    Permite aceptar advertencias SSL o resolver intersticiales
export SEED_WAIT_SECONDS="0"

# 5) URLs de seeding (usa dominios más "suaves" para evitar intersticiales)
export TEST_BETBURGER_URL="https://betburger.com"
export TEST_SUREBET_URL="https://es.surebet.com"

# 6) (Opcional) Proxy del navegador para enrutar tráfico (útil si Surebet requiere VPN/proxy)
# Tipos soportados: http | socks5
# Descomenta y completa para activar:
# export BROWSER_PROXY_TYPE="socks5"
# export BROWSER_PROXY_HOST="127.0.0.1"
# export BROWSER_PROXY_PORT="1080"
# export BROWSER_PROXY_USERNAME=""
# export BROWSER_PROXY_PASSWORD=""

# 6.1) (Opcional) Cargar proxy automáticamente desde un JSON (e.g., ./proxies.txt)
# Usa el primer proxy "alive" que coincida con protocolo deseado (PROXY_PROTOCOL_FILTER)
# Variables:
PROXY_JSON_PATH=./proxies.txt
PROXY_PROTOCOL_FILTER=socks5   # o socks5
#   PROXY_TAKE=1                 # cuántos tomar (por defecto 1)
if [[ -n "${PROXY_JSON_PATH}" && -f "${PROXY_JSON_PATH}" ]]; then
  python3 - <<'PY'
import json, os, sys, re
path = os.environ.get('PROXY_JSON_PATH')
proto_filter = (os.environ.get('PROXY_PROTOCOL_FILTER') or '').lower() or None
take_n = int(os.environ.get('PROXY_TAKE','1'))
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    items = data.get('proxies') or []
except Exception as e:
    print(f"# [env] No se pudo leer {path}: {e}")
    sys.exit(0)

def parse_proxy(p):
    # 'proxy' como 'http://ip:port' o 'socks5://ip:port'
    url = p.get('proxy') or ''
    m = re.match(r'^(?P<scheme>https?|socks5?)://(?P<host>[^:]+):(?P<port>\d+)$', url)
    if not m:
        return None
    scheme, host, port = m.group('scheme').lower(), m.group('host'), int(m.group('port'))
    if scheme == 'https':
        scheme = 'http'  # tratar https como http proxy para Firefox prefs
    return scheme, host, port

picked = []
for p in items:
    if not p.get('alive'):
        continue
    parsed = parse_proxy(p)
    if not parsed:
        continue
    scheme, host, port = parsed
    if proto_filter and scheme != proto_filter:
        continue
    picked.append((scheme, host, port))
    if len(picked) >= take_n:
        break

if picked:
    scheme, host, port = picked[0]
    print(f"export BROWSER_PROXY_TYPE=\"{scheme}\"")
    print(f"export BROWSER_PROXY_HOST=\"{host}\"")
    print(f"export BROWSER_PROXY_PORT=\"{port}\"")
    # Nota: proxies públicos no suelen requerir auth; si tienes user/pass, expórtalos manualmente.
else:
    print("# [env] No se encontró proxy vivo que cumpla el filtro; omitiendo.")
PY
fi

# Mensaje resumen
cat <<EOF
[env_selenium_test] Variables exportadas:
  WEBDRIVER_URL=${WEBDRIVER_URL}
  HEADLESS_MODE=${HEADLESS_MODE}
  SEED_TEST_TABS=${SEED_TEST_TABS}
  SEED_WAIT_SECONDS=${SEED_WAIT_SECONDS}
  TEST_BETBURGER_URL=${TEST_BETBURGER_URL}
  TEST_SUREBET_URL=${TEST_SUREBET_URL}
  BROWSER_PROXY_TYPE=${BROWSER_PROXY_TYPE:-}
  BROWSER_PROXY_HOST=${BROWSER_PROXY_HOST:-}
  BROWSER_PROXY_PORT=${BROWSER_PROXY_PORT:-}
  PROXY_JSON_PATH=${PROXY_JSON_PATH:-}
  PROXY_PROTOCOL_FILTER=${PROXY_PROTOCOL_FILTER:-}

Para ejecutar:
  1) source ./scripts/env_selenium_test.sh
  2) ./scripts/run_selenium_test.sh

Si usas GUI:
  - Abre http://localhost:7900 (password: secret) para ver el navegador.
EOF
