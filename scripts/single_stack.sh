#!/usr/bin/env bash
set -euo pipefail

COMPOSE="docker-compose.single.yml"
SERVICE="selenium-bot"

usage() {
  cat <<EOF
Uso: $0 <comando> [args]

Comandos:
  up                 Construye y levanta el contenedor único (${SERVICE})
  rebuild            Reconstruye la imagen y reinicia el servicio
  down               Apaga y limpia contenedor y volumen de perfil
  logs               Muestra logs del servicio
  status             Muestra estado de Selenium Grid y contenedor
  seed [pre wait] [seed wait]
                     Abre pestañas (Betburger/Surebet) y termina rápido.
                     Defaults: pre=30s, seed=10s
  snapshot           Ejecuta src/scrape_snapshot.py (guarda HTML y abre índice)

Ejemplos:
  $0 up
  $0 seed 30 10
  $0 snapshot
  $0 logs
  $0 down
EOF
}

cmd=${1:-}
case "$cmd" in
  up)
    docker compose -f "$COMPOSE" up -d --build
    echo "GUI: http://localhost:7900  |  Selenium: http://localhost:4444/status"
    ;;
  rebuild)
    docker compose -f "$COMPOSE" build --no-cache
    docker compose -f "$COMPOSE" up -d
    ;;
  down)
    docker compose -f "$COMPOSE" down -v --remove-orphans || true
    echo "Stack detenido y volumen de perfil eliminado (firefox_profile)."
    ;;
  logs)
    docker compose -f "$COMPOSE" logs -f "$SERVICE"
    ;;
  status)
    echo "--- Contenedores ---"
    docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E "NAME|$SERVICE" || true
    echo "--- Selenium status ---"
    curl -sf http://localhost:4444/status || echo "No responde aún"
    ;;
  seed)
    PRE=${2:-30}
    SEED=${3:-10}
    # Ensure runtime dependencies are present (self-heal if needed)
    docker compose -f "$COMPOSE" exec "$SERVICE" python3 -u scripts/ensure_runtime_deps.py || true
    docker compose -f "$COMPOSE" exec -e SEED_TEST_TABS=true \
      -e PRE_SEED_WAIT_SECONDS="$PRE" -e SEED_WAIT_SECONDS="$SEED" "$SERVICE" \
      python3 -u test_tab_connection.py
    ;;
  snapshot)
    # Ensure runtime dependencies are present (self-heal if needed)
    docker compose -f "$COMPOSE" exec "$SERVICE" python3 -u scripts/ensure_runtime_deps.py || true
    docker compose -f "$COMPOSE" exec "$SERVICE" python3 -u src/scrape_snapshot.py
    ;;
  *)
    usage
    exit 1
    ;;
 esac
