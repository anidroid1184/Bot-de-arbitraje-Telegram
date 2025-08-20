#!/usr/bin/env python3
"""
Test Telegram delivery to all channels defined in config/channels.yaml.

- Loads .env (TELEGRAM_BOT_TOKEN is required)
- Reads channel mappings from config/channels.yaml
- Sends a short ping message to each channel and reports the result

Usage:
  python3 scripts/test_telegram_channels.py

Notes:
- This script uses python-telegram-bot v22+ (async API)
- Ensure the bot is added to each channel with permission to send messages
- Channel IDs should be strings, usually negative for channels (e.g., -100XXXXXXXXXX)
"""
from __future__ import annotations

import asyncio
import datetime as dt
import os
import sys
from typing import Dict, List, Tuple

import yaml
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode


CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "channels.yaml")


def load_env() -> None:
    """Load environment variables from .env located at repo root."""
    repo_root = os.path.dirname(os.path.dirname(__file__))
    env_path = os.path.join(repo_root, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)


def load_channels() -> List[Tuple[str, str]]:
    """Parse channels.yaml and return a flat list of (name, channel_id) pairs.

    Returns:
        List of tuples like [("betburger.profile_1", "-100123"), ("support.technical_alerts", "-100456"), ...]
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
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
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env", file=sys.stderr)
        return 2

    channels = load_channels()
    if not channels:
        print(f"WARN: No channels found in {CONFIG_PATH}")
        return 0

    bot = Bot(token=token)

    print("Testing Telegram delivery to the following channels:")
    for name, cid in channels:
        print(f" - {name}: {cid}")

    tasks = [ping_channel(bot, name, cid) for name, cid in channels]
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
