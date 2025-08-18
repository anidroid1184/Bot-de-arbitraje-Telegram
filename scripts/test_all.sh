#!/usr/bin/env bash
set -euo pipefail

# Test unificado y auto-contenido: con o sin VPN
# Uso:
#   bash scripts/test_all.sh --vpn        # usa docker-compose.vpn.yml + .env.vpn
#   bash scripts/test_all.sh --no-vpn     # usa docker-compose.selenium.yml
#   TEARDOWN=1 bash scripts/test_all.sh --vpn   # baja el stack al terminar
#
# Requisitos:
#   - Docker/Compose
#   - Para --vpn: .env.vpn válido y archivo .ovpn en gluetun/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJ_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJ_ROOT"

MODE="--vpn"  # por defecto
if [[ ${1:-} == "--no-vpn" ]]; then MODE="--no-vpn"; fi

info() { echo -e "[INFO] $*"; }
warn() { echo -e "[WARN] $*"; }
err()  { echo -e "[ERROR] $*" 1>&2; }

if ! command -v docker >/dev/null 2>&1; then
  err "Docker no está instalado/en PATH."
  exit 1
fi

wait_for_selenium() {
  local url="http://localhost:4444/wd/hub/status"
  local tries=0 max=30
  info "Esperando a Selenium en ${url}..."
  until curl -fsS "$url" >/dev/null 2>&1; do
    tries=$((tries+1))
    [[ $tries -ge $max ]] && return 1
    sleep 2
    [[ $((tries%5)) -eq 0 ]] && info "...aún esperando (${tries}/${max})"
  done
  info "Selenium OK."
}

bring_up_vpn() {
  # Limpieza mínima para evitar conflictos de nombres
  docker compose -f docker-compose.vpn.yml down || true
  for cname in gluetun selenium-firefox; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${cname}$"; then
      docker rm -f "$cname" || true
    fi
  done
  # Validación .ovpn
  if ! ls gluetun/*.ovpn >/dev/null 2>&1; then
    warn "No se encontró archivo .ovpn en gluetun/. Asegúrate de copiarlo (p.ej., gluetun/vpngate-us-udp.ovpn)."
  fi
  info "Levantando stack VPN..."
  docker compose -f docker-compose.vpn.yml --env-file .env.vpn up -d --remove-orphans
}

bring_up_no_vpn() {
  info "Levantando Selenium sin VPN..."
  docker compose -f docker-compose.selenium.yml up -d --remove-orphans
}

teardown_vpn() {
  info "Bajando stack VPN..."
  docker compose -f docker-compose.vpn.yml down || true
}

teardown_no_vpn() {
  info "Bajando Selenium sin VPN..."
  docker compose -f docker-compose.selenium.yml down || true
}

# 0) Activar venv si existe (en raíz o en este proyecto)
if [ -f "$PROJ_ROOT/../.venv/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$PROJ_ROOT/../.venv/bin/activate"
elif [ -f "$PROJ_ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$PROJ_ROOT/.venv/bin/activate"
fi

# 1) Levantar modo seleccionado
if [[ "$MODE" == "--vpn" ]]; then
  bring_up_vpn
else
  bring_up_no_vpn
fi

# 2) Esperar Selenium
if ! wait_for_selenium; then
  err "Selenium no respondió a tiempo. Logs recientes:"
  docker logs --tail 100 gluetun 2>/dev/null || true
  docker logs --tail 200 selenium-firefox 2>/dev/null || true
  [[ "${TEARDOWN:-0}" == "1" ]] && { [[ "$MODE" == "--vpn" ]] && teardown_vpn || teardown_no_vpn; }
  exit 1
fi

# 3) Exportar variables del test (vía script dedicado) y ejecutar el runner del test
# shellcheck disable=SC1090
source "$SCRIPT_DIR/env_selenium_test.sh"

"$SCRIPT_DIR/run_selenium_test.sh"
RC=$?

# 4) Teardown opcional
if [[ "${TEARDOWN:-0}" == "1" ]]; then
  if [[ "$MODE" == "--vpn" ]]; then
    teardown_vpn || true
  else
    teardown_no_vpn || true
  fi
fi

exit $RC
