"""
Send a formatted Betburger alert to a single Telegram channel for validation.

Usage (WSL):
  python3 -m scripts.send_test_betburger_alert \
      --profile bet365_valuebets             # resolves channel from config.yml

  python3 -m scripts.send_test_betburger_alert \
      --channel-id -1001234567890            # overrides target channel directly

Optional:
  --sample samples/betburger_valid.json
  --dry-run  (prints message without sending)

Resolution order for target chat:
  1) --channel-id
  2) --profile -> ConfigManager.get_channel_for_profile("betburger", profile)
  3) TELEGRAM_SUPPORT_CHANNEL_ID (env or YAML)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Ensure package imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.logger import get_module_logger  # type: ignore
from src.utils.telegram_notifier import TelegramNotifier  # type: ignore
from src.config.settings import ConfigManager  # type: ignore

logger = get_module_logger("send_test_betburger_alert")


def load_sample(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Sample JSON must be an object")
    return data


def fmt_pct(v) -> str:
    try:
        return f"{float(v):.2f}%"
    except Exception:
        return str(v)


def format_message(sample: dict) -> str:
    ts = sample.get("timestamp_utc")
    # Human-readable timestamp fallback
    if not ts:
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    sport = sample.get("sport") or ""
    league = sample.get("league") or ""
    match = sample.get("match") or ""
    market = sample.get("market") or ""
    sel_a = sample.get("selection_a") or {}
    sel_b = sample.get("selection_b") or {}

    a_bk = sel_a.get("bookmaker") or "?"
    a_odd = sel_a.get("odd") or "?"
    b_bk = sel_b.get("bookmaker") or "?"
    b_odd = sel_b.get("odd") or "?"

    roi = fmt_pct(sample.get("roi_pct"))
    link = sample.get("target_link") or ""

    header = "📢 Betburger Valuebet"
    lines = [
        f"{header}",
        f"⏱ {ts}",
        f"🏅 {sport} — {league}",
        f"⚔️ {match}",
        f"🎯 Mercado: {market}",
        f"📈 {a_bk}: {a_odd}",
        f"📉 {b_bk}: {b_odd}",
        f"💹 ROI: {roi}",
    ]
    if link:
        lines.append(f"🔗 {link}")
    return "\n".join(lines)


def resolve_target(cfg: ConfigManager, channel_id_cli: str | None, profile: str | None) -> str | None:
    if channel_id_cli:
        return channel_id_cli.strip()
    if profile:
        try:
            cid = cfg.get_channel_for_profile("betburger", profile.strip())
            if cid:
                return cid
        except Exception:
            pass
    return cfg.get_support_channel()


def main() -> int:
    ap = argparse.ArgumentParser(description="Send a formatted Betburger alert to one channel")
    ap.add_argument("--profile", help="Profile key to resolve channel from config.yml", default=None)
    ap.add_argument("--channel-id", help="Target Telegram channel id (overrides profile)", default=None)
    ap.add_argument("--sample", help="Path to sample JSON", default=str(ROOT / "samples" / "betburger_valid.json"))
    ap.add_argument("--dry-run", action="store_true", help="Print message without sending")
    args = ap.parse_args()

    cfg = ConfigManager()
    sample_path = Path(args.sample)
    if not sample_path.exists():
        logger.error("Sample file not found", path=str(sample_path))
        return 2

    sample = load_sample(sample_path)
    text = format_message(sample)

    target = resolve_target(cfg, args.channel_id, args.profile or sample.get("profile"))
    if not target:
        logger.error("No target channel could be resolved. Provide --channel-id or --profile, or set TELEGRAM_SUPPORT_CHANNEL_ID")
        print(text)
        return 2

    if args.dry_run:
        print("--- DRY RUN ---")
        print(f"To: {target}")
        print(text)
        return 0

    notifier = TelegramNotifier()
    ok = notifier.send_text(text, chat_id=target)
    logger.info("Test alert sent", ok=ok, target=target)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
