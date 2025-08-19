#!/usr/bin/env bash
set -euo pipefail

# Simple launcher for Selenium stack with or without VPN.
# Usage:
#   ./scripts/run_stack.sh [--vpn] [--attach] [--once]
#
# Flags:
#   --vpn     Use the VPN-enabled Selenium image/profile
#   --attach  Run docker compose in attached mode (foreground)
#   --once    Also run the one-shot test container (bot-once or bot-once-vpn)
#
# Examples:
#   ./scripts/run_stack.sh                 # start normal (no VPN) in background
#   ./scripts/run_stack.sh --vpn           # start VPN profile in background
#   ./scripts/run_stack.sh --vpn --once    # start VPN profile and run the test once
#   ./scripts/run_stack.sh --attach        # start normal profile attached

PROFILE="novpn"
ATTACH=false
RUN_ONCE=false

for arg in "$@"; do
  case "$arg" in
    --vpn)
      PROFILE="vpn"
      shift
      ;;
    --attach)
      ATTACH=true
      shift
      ;;
    --once)
      RUN_ONCE=true
      shift
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

COMPOSE_FILE="docker-compose.selenium.yml"

if $ATTACH; then
  docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" up --remove-orphans
else
  docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" up -d --remove-orphans
fi

if $RUN_ONCE; then
  if [ "$PROFILE" = "vpn" ]; then
    docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" run --rm bot-once-vpn
  else
    docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" run --rm bot-once
  fi
fi

# Hints
if [ "$PROFILE" = "vpn" ]; then
  echo "\n[INFO] VPN profile started. Services: selenium-firefox-vpn (+ bot-once-vpn if --once)."
else
  echo "\n[INFO] No-VPN profile started. Services: selenium-firefox (+ bot-once if --once)."
fi

echo "GUI (noVNC): http://localhost:7900  (password: secret unless changed)"
echo "Selenium URL: http://localhost:4444/wd/hub"
