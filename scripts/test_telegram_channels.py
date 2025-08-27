#!/usr/bin/env python3
"""
Test Telegram delivery to all channels defined in configuration.

- Loads .env (TELEGRAM_BOT_TOKEN is required)
- Reads channel mappings from src/config/config.yml if present,
  otherwise from config/channels.yaml
- Sends a short ping message to each channel and reports the result

Usage:
  python3 scripts/test_telegram_channels.py
  python3 scripts/test_telegram_channels.py --only betburger    # only betburger profiles
  python3 scripts/test_telegram_channels.py --dry-run           # list without sending

Notes:
- Ensure the bot is added to each channel with permission to send messages
- Channel IDs should be strings; for public channels, @username also works
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys
from typing import Dict, List, Tuple, Iterable

import yaml
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode


REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
PREFERRED_CONFIG = os.path.join(REPO_ROOT, "src", "config", "config-configurada.yml")
FALLBACK_CONFIG = os.path.join(REPO_ROOT, "deprecated", "config-configurada.yml")


def load_env() -> None:
    """Load environment variables from .env located at repo root."""
    repo_root = os.path.dirname(os.path.dirname(__file__))
    env_path = os.path.join(repo_root, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)


def _pick_config_path() -> str:
    if os.path.exists(PREFERRED_CONFIG):
        return PREFERRED_CONFIG
    return FALLBACK_CONFIG


def load_channels() -> List[Tuple[str, str]]:
    """Parse config and return a flat list of (name, channel_id) pairs.

    Returns:
        List of tuples like [("betburger.profile_1", "-100123"), ("support.technical_alerts", "-100456"), ...]
    """
    config_path = _pick_config_path()
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    pairs: List[Tuple[str, str]] = []

    # betburger_profiles
    for key, node in (data.get("betburger_profiles") or {}).items():
        cid = str(node.get("channel_id", "")).strip()
        if cid:
            pairs.append((f"betburger.{key}", cid))

    # surebet_profiles
    for key, node in (data.get("surebet_profiles") or {}).items():
        cid = str(node.get("channel_id", "")).strip()
        if cid:
            pairs.append((f"surebet.{key}", cid))

    # support
    for key, node in (data.get("support") or {}).items():
        cid = str(node.get("channel_id", "")).strip()
        if cid:
            pairs.append((f"support.{key}", cid))

    return pairs


def _filter_pairs(pairs: Iterable[Tuple[str, str]], only: str | None) -> List[Tuple[str, str]]:
    """Filter by top-level group and deduplicate by (name, id).

    Args:
        pairs: iterable of (name, id) like "betburger.profile_1"
        only: optional filter: "betburger", "surebet", or "support"
    """
    filtered: List[Tuple[str, str]] = []
    seen: set[Tuple[str, str]] = set()
    for name, cid in pairs:
        if only and not name.startswith(f"{only}."):
            continue
        key = (name, cid)
        if key in seen:
            continue
        seen.add(key)
        filtered.append((name, cid))
    # Sort for stable output
    filtered.sort(key=lambda x: x[0])
    return filtered


async def ping_channel(bot: Bot, name: str, channel_id: str) -> Tuple[str, str, str]:
    """Send a ping message to a single channel.

    Returns a tuple (name, channel_id, result) where result is "OK" or error message.
    """
    try:
        ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        text = (
            f"Ping de prueba ✅\n"
            f"Canal: {name}\n"
            f"ID: {channel_id}\n"
            f"Hora: {ts}"
        )
        await bot.send_message(chat_id=channel_id, text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        return (name, channel_id, "OK")
    except Exception as e:  # noqa: BLE001 - we want to report raw error here
        return (name, channel_id, f"ERROR: {e}")


async def main_async() -> int:
    load_env()
    import argparse
    parser = argparse.ArgumentParser(description="Test Telegram delivery to configured channels")
    parser.add_argument("--only", choices=["betburger", "surebet", "support"], help="Filter channel group")
    parser.add_argument("--dry-run", action="store_true", help="List channels without sending messages")
    args = parser.parse_args()

    # If not dry-run, we require the token
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not args.dry_run and not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env", file=sys.stderr)
        return 2

    channels = _filter_pairs(load_channels(), args.only)
    if not channels:
        print(f"WARN: No channels found in {_pick_config_path()}")
        return 0

    bot = Bot(token=token) if not args.dry_run else None  # type: ignore[assignment]

    print("Testing Telegram delivery to the following channels:")
    for name, cid in channels:
        print(f" - {name}: {cid}")

    if args.dry_run:
        print("\nDry run: no messages sent.")
        return 0

    tasks = [ping_channel(bot, name, cid) for name, cid in channels]  # type: ignore[arg-type]
    results = await asyncio.gather(*tasks)

    print("\nResults:")
    ok_count = 0
    for name, cid, res in results:
        print(f" - {name:30s} -> {res}")
        if res == "OK":
            ok_count += 1

    print(f"\nSummary: {ok_count}/{len(results)} channels OK")
    return 0 if ok_count == len(results) else 1


def main() -> None:
    try:
        exit_code = asyncio.run(main_async())
    except KeyboardInterrupt:
        exit_code = 130
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
