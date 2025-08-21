"""
CLI to validate required_fields per profile against a provided alert JSON (or a dummy alert),
optionally notifying the support channel on failures via TelegramNotifier.

Usage examples:
  python scripts/test_required_fields.py --platform betburger --profile winamax-bet365 --dry-run
  python scripts/test_required_fields.py --platform surebet --profile bet365_valuebets --json sample_alert.json
  python scripts/test_required_fields.py --platform betburger --profile winamax-bet365 --notify

Notes:
- --dry-run: never sends Telegram notifications (default behavior is also no notify unless --notify is set)
- If --json not provided, a minimal dummy alert is used to help verify the validator behavior.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

# Ensure project root is on sys.path so 'src' package is importable when running as a script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.settings import ConfigManager
from src.processing.required_fields import get_required_fields, validate_alert_fields
from src.utils.telegram_notifier import TelegramNotifier, NotifierConfig


def _dummy_alert(platform: str, profile: str) -> Dict[str, Any]:
    # Minimal alert likely to fail for most profiles so we can see missing fields
    return {
        "source": platform,
        "profile": profile,
        "sport": "soccer",
        "market": "1X2",
        "match": "Team A vs Team B",
        "selection_a": {"bookmaker": "Winamax", "odd": 2.0},
        "selection_b": {"bookmaker": "bet365", "odd": 1.8},
        "roi_pct": 3.2,
        "event_start": None,
        "target_link": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate required_fields for a profile")
    parser.add_argument("--platform", required=True, choices=["betburger", "surebet"], help="Platform")
    parser.add_argument("--profile", required=True, help="Profile name as in config.yml")
    parser.add_argument("--json", dest="json_path", help="Path to alert JSON to validate")
    parser.add_argument("--notify", action="store_true", help="Send failure message to support channel")
    parser.add_argument("--dry-run", action="store_true", help="Do not send notifications (overrides --notify)")
    parser.add_argument("--only-missing", action="store_true", help="Print only missing fields")
    args = parser.parse_args()

    cfg = ConfigManager()

    req = get_required_fields(cfg, args.platform, args.profile)
    if not req:
        print(f"[WARN] No required_fields configured for {args.platform}/{args.profile}")

    if args.json_path:
        with open(args.json_path, "r", encoding="utf-8") as f:
            alert = json.load(f)
    else:
        alert = _dummy_alert(args.platform, args.profile)

    ok, missing = validate_alert_fields(alert, req)

    print("Profile:", args.profile)
    print("Platform:", args.platform)
    print("Required fields:", req)
    if args.only_missing:
        print("Missing:", missing)
    else:
        print("Alert:", json.dumps(alert, ensure_ascii=False))
        print("Missing:", missing)
    print("Valid:", ok)

    if args.notify and not args.dry_run and not ok:
        notifier = TelegramNotifier(NotifierConfig(bot_token=cfg.telegram.bot_token, default_chat_id=None))
        msg = (
            f"[VALIDATION ERROR] {args.platform}/{args.profile}: missing fields: {', '.join(missing)}"
        )
        sent = notifier.send_text(msg)
        print("Notified support:", sent)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
