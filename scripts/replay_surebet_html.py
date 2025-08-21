#!/usr/bin/env python3
"""
Replay Surebet Valuebets alerts from a saved HTML snapshot and send them to Telegram.

Usage:
  python scripts/replay_surebet_html.py --profile valuebets --file logs/raw_html/surebet_YYYYMMDD_HHMMSS.html
  python scripts/replay_surebet_html.py --profile valuebets             # uses most recent file automatically
  python scripts/replay_surebet_html.py --profile valuebets --chat-id -1001234567890  # override destination

Requires:
- .env with TELEGRAM_BOT_TOKEN
- config/config.yml with surebet_profiles.<profile>.channel_id (unless --chat-id is used)
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
import time
from typing import Optional

# Make 'src' importable when called directly
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.logger import get_module_logger  # type: ignore
from src.utils.telegram_notifier import TelegramNotifier  # type: ignore
from src.config.settings import ConfigManager  # type: ignore
from src.processors.surebet_parser import parse_surebet_valuebets_html  # type: ignore
from src.formatters.telegram_message import format_alert_telegram  # type: ignore

logger = get_module_logger("scripts.replay_surebet_html")


def find_latest_snapshot() -> Optional[str]:
    pattern = os.path.join(PROJECT_ROOT, "logs", "raw_html", "surebet_*.html")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None


def load_html(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay Surebet Valuebets HTML to Telegram")
    parser.add_argument("--profile", default="valuebets", help="surebet profile name, e.g., valuebets")
    parser.add_argument("--file", help="path to HTML snapshot; if omitted, use latest")
    parser.add_argument("--chat-id", help="override destination chat/channel id")
    args = parser.parse_args()

    cfg = ConfigManager()
    chat_id = args.chat_id or cfg.get_channel_for_profile("surebet", args.profile)
    if not chat_id:
        logger.error("Channel not configured for profile and --chat-id not provided", profile=args.profile)
        return 2

    path = args.file or find_latest_snapshot()
    if not path or not os.path.exists(path):
        logger.error("HTML snapshot not found", path=path)
        return 3

    html = load_html(path)
    t0 = time.perf_counter()
    alerts = parse_surebet_valuebets_html(html, profile=args.profile)
    t_parse = (time.perf_counter() - t0) * 1000

    if not alerts:
        logger.warning("No alerts parsed from snapshot", path=path)
        return 0

    notifier = TelegramNotifier()
    ok = 0
    for alert in alerts:
        msg = format_alert_telegram(alert)
        t1 = time.perf_counter()
        sent = notifier.send_text(msg, chat_id=chat_id)
        t_send = (time.perf_counter() - t1) * 1000
        logger.info(
            "Alert processed",
            sent=sent,
            parse_ms=f"{t_parse:.1f}",
            send_ms=f"{t_send:.1f}",
            profile=args.profile,
            channel=chat_id,
        )
        if sent:
            ok += 1

    logger.info("Replay summary", parsed=len(alerts), delivered=ok, channel=chat_id)
    return 0 if ok == len(alerts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
