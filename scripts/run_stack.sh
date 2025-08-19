#!/usr/bin/env bash
set -euo pipefail

# Simple launcher for Selenium stack with or without VPN.
# Usage:
#   ./scripts/run_stack.sh [--vpn|--novpn] [--attach] [--once] [--seed-wait <sec>] [--pre-seed-wait <sec>] [--down]
#
# Flags:
#   --vpn              Use the VPN-enabled Selenium image/profile
#   --novpn            Use the non-VPN profile explicitly (default)
#   --attach           Run docker compose in attached mode (foreground)
#   --once             Also run the one-shot test container (bot-once or bot-once-vpn)
#   --seed-wait <sec>  Override SEED_WAIT_SECONDS for the one-shot test
#   --pre-seed-wait <sec>  Override PRE_SEED_WAIT_SECONDS (useful in VPN to click CONNECT)
#   --down             Bring the stack down and exit
#
# Examples:
#   ./scripts/run_stack.sh                 # start normal (no VPN) in background
#   ./scripts/run_stack.sh --vpn           # start VPN profile in background
#   ./scripts/run_stack.sh --vpn --once    # start VPN profile and run the test once
#   ./scripts/run_stack.sh --once --seed-wait 30                 # run one-shot for 30s
#   ./scripts/run_stack.sh --vpn --once --pre-seed-wait 30       # give 30s to click CONNECT
#   ./scripts/run_stack.sh --down          # stop and clean services

PROFILE="novpn"
ATTACH=false
RUN_ONCE=false
SEED_WAIT_OVERRIDE=""
PRE_SEED_WAIT_OVERRIDE=""
BRING_DOWN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vpn)
      PROFILE="vpn"; shift ;;
    --novpn)
      PROFILE="novpn"; shift ;;
    --attach)
      ATTACH=true; shift ;;
    --once)
      RUN_ONCE=true; shift ;;
    --seed-wait)
      SEED_WAIT_OVERRIDE="$2"; shift 2 ;;
    --pre-seed-wait)
      PRE_SEED_WAIT_OVERRIDE="$2"; shift 2 ;;
    --down)
      BRING_DOWN=true; shift ;;
    *)
      echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

COMPOSE_FILE="docker-compose.selenium.yml"

if $BRING_DOWN; then
  docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" down --remove-orphans
  exit 0
fi

if $ATTACH; then
  docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" up --remove-orphans
else
  docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" up -d --remove-orphans
fi

if $RUN_ONCE; then
  if [ "$PROFILE" = "vpn" ]; then
    if [[ -n "$SEED_WAIT_OVERRIDE" && -n "$PRE_SEED_WAIT_OVERRIDE" ]]; then
      docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" run --rm \
        -e SEED_WAIT_SECONDS="$SEED_WAIT_OVERRIDE" \
        -e PRE_SEED_WAIT_SECONDS="$PRE_SEED_WAIT_OVERRIDE" \
        bot-once-vpn
    elif [[ -n "$SEED_WAIT_OVERRIDE" ]]; then
      docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" run --rm \
        -e SEED_WAIT_SECONDS="$SEED_WAIT_OVERRIDE" \
        bot-once-vpn
    elif [[ -n "$PRE_SEED_WAIT_OVERRIDE" ]]; then
      docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" run --rm \
        -e PRE_SEED_WAIT_SECONDS="$PRE_SEED_WAIT_OVERRIDE" \
        bot-once-vpn
    else
      docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" run --rm bot-once-vpn
    fi
  else
    if [[ -n "$SEED_WAIT_OVERRIDE" ]]; then
      docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" run --rm \
        -e SEED_WAIT_SECONDS="$SEED_WAIT_OVERRIDE" \
        bot-once
    else
      docker compose -f "$COMPOSE_FILE" --profile "$PROFILE" run --rm bot-once
    fi
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
