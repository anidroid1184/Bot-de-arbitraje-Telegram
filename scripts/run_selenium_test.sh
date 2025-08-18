#!/usr/bin/env bash
set -euo pipefail

# Root of repo (this script is inside Bot-de-arbitraje-Telegram/scripts)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PROJ_ROOT/.." && pwd)"

# Config
CONTAINER_NAME="selenium-firefox"
SELENIUM_IMAGE="selenium/standalone-firefox:4.23.0"
WEBDRIVER_URL="http://localhost:4444/wd/hub"
VNC_PORT=7900

info() { echo -e "[INFO] $*"; }
warn() { echo -e "[WARN] $*"; }
err()  { echo -e "[ERROR] $*" 1>&2; }

# 1) Ensure Docker available
if ! command -v docker >/dev/null 2>&1; then
  err "Docker no está instalado/en PATH. Instala Docker Desktop y habilita WSL integration."
  exit 1
fi

# 2) Start selenium container if not running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    info "Contenedor existente encontrado. Iniciando ${CONTAINER_NAME}..."
    docker start "$CONTAINER_NAME"
  else
    info "Levantando contenedor ${CONTAINER_NAME} (${SELENIUM_IMAGE})..."
    docker run -d --name "$CONTAINER_NAME" \
      -p 4444:4444 -p ${VNC_PORT}:${VNC_PORT} \
      "$SELENIUM_IMAGE"
  fi
else
  info "Contenedor ${CONTAINER_NAME} ya está corriendo."
fi

# 3) Show VNC URL for debugging
info "noVNC disponible (opcional): http://localhost:${VNC_PORT} (password: secret)"

# 4) Activate virtualenv
if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
  # venv en raíz del repo
  # shellcheck disable=SC1090
  source "$REPO_ROOT/.venv/bin/activate"
elif [ -f "$PROJ_ROOT/.venv/bin/activate" ]; then
  # venv dentro de Bot-de-arbitraje-Telegram
  # shellcheck disable=SC1090
  source "$PROJ_ROOT/.venv/bin/activate"
else
  warn "No se encontró venv en $REPO_ROOT/.venv ni en $PROJ_ROOT/.venv. Continuaré sin activar."
fi

# 5) Export webdriver URL and optional headless flag passthrough
export WEBDRIVER_REMOTE_URL="${WEBDRIVER_URL}"
# Respeta HEADLESS_MODE del usuario si ya está definido; por defecto true para test estable
export HEADLESS_MODE="${HEADLESS_MODE:-true}"
# Sembrar pestañas de prueba para que el test encuentre betburger/surebet en una sesión nueva
export SEED_TEST_TABS="${SEED_TEST_TABS:-true}"

# 6) Run the test
cd "$PROJ_ROOT"
info "Ejecutando test_tab_connection.py con WEBDRIVER_REMOTE_URL=${WEBDRIVER_REMOTE_URL} HEADLESS_MODE=${HEADLESS_MODE}"
python test_tab_connection.py

RC=$?
if [ $RC -eq 0 ]; then
  info "✅ Test PASSED"
else
  err "❌ Test FAILED (rc=$RC)"
  info "Sugerencias:"
  info "- Abre http://localhost:${VNC_PORT} para ver el navegador y verificar pestañas."
  info "- Asegúrate de que el contenedor está sano: docker logs ${CONTAINER_NAME}"
fi
exit $RC
