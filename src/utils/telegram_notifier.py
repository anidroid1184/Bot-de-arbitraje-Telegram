"""
Simple Telegram notifier.

This implementation uses direct HTTP requests to the Telegram Bot API to avoid
asyncio event loop coupling issues observed with python-telegram-bot in
short-lived scripts ("Event loop is closed").

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_SUPPORT_CHANNEL_ID from env.
If configuration is missing, it logs and no-ops.
"""
from __future__ import annotations

import os
import time
from typing import Optional
from dataclasses import dataclass

import requests

import structlog

logger = structlog.get_logger("telegram_notifier")


@dataclass
class NotifierConfig:
    bot_token: str
    default_chat_id: Optional[str] = None


class TelegramNotifier:
    """Minimal wrapper to send text messages to Telegram."""

    def __init__(self, config: Optional[NotifierConfig] = None) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_SUPPORT_CHANNEL_ID")
        if not chat_id:
            # Fallback to YAML configuration if env var is missing
            yaml_chat_id = self._load_support_channel_from_yaml()
            if yaml_chat_id:
                chat_id = yaml_chat_id
        if config is not None:
            token = config.bot_token or token
            chat_id = config.default_chat_id or chat_id
        self.token = token
        self.default_chat_id = chat_id
        # rate limiting between messages (seconds). Helps reduce flood control.
        try:
            self.min_interval = float(os.getenv("TELEGRAM_MIN_INTERVAL_SEC", "0.20"))
        except Exception:
            self.min_interval = 0.20
        self._last_sent_ts = 0.0
        if not token:
            logger.warning("TELEGRAM_BOT_TOKEN missing; notifier will no-op")

    @staticmethod
    def _load_support_channel_from_yaml() -> Optional[str]:
        """Try to read support channel from src/config/config.yml.

        Preference order:
        1) defaults.notifications.error_channel
        2) support.technical_alerts.channel_id
        """
        try:
            import yaml  # local import to avoid hard dependency elsewhere
            here = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(here, os.pardir, "config", "config.yml")
            config_path = os.path.abspath(config_path)
            if not os.path.exists(config_path):
                return None
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            # 1) defaults.notifications.error_channel
            defaults = data.get("defaults") or {}
            notifications = defaults.get("notifications") or {}
            error_channel = notifications.get("error_channel")
            if error_channel:
                return str(error_channel).strip()
            # 2) support.technical_alerts.channel_id
            support = data.get("support") or {}
            tech = support.get("technical_alerts") or {}
            cid = tech.get("channel_id")
            if cid:
                return str(cid).strip()
        except Exception:
            return None
        return None

    def send_text(self, text: str, chat_id: Optional[str] = None) -> bool:
        """Send a Telegram message synchronously via HTTP API.

        Handles flood control (HTTP 429) with retry-after, simple backoff for
        transient errors, and minimal pacing between messages.
        """
        if not self.token:
            return False
        target = chat_id or self.default_chat_id
        if not target:
            logger.warning("No chat_id provided and TELEGRAM_SUPPORT_CHANNEL_ID is missing")
            return False

        def _pace():
            now = time.time()
            delta = now - self._last_sent_ts
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)

        def _post_message(body_text: str) -> bool:
            _pace()
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": str(target),
                "text": body_text,
                "disable_web_page_preview": True,
            }

            max_attempts = 4  # ensures at least 2 retries after first attempt
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                try:
                    resp = requests.post(url, json=payload, timeout=15)
                except Exception as e:
                    logger.error("Telegram POST failed", error=str(e))
                    time.sleep(1.0)
                    continue

                if resp.status_code == 200:
                    self._last_sent_ts = time.time()
                    logger.info("Sent Telegram message", length=len(body_text))
                    return True

                try:
                    data = resp.json()
                except Exception:
                    data = {}

                if resp.status_code == 429:
                    retry_after = 1
                    try:
                        retry_after = int((data.get("parameters") or {}).get("retry_after", 1))
                    except Exception:
                        pass
                    logger.error("Flood control: retrying later", retry_after=retry_after)
                    time.sleep(retry_after + 1)
                    continue

                if resp.status_code == 400 and isinstance(data, dict) and (
                    str(data.get("description", "")).lower().find("too long") >= 0
                ):
                    # message too long: caller will handle chunking
                    return False

                if resp.status_code >= 500:
                    logger.error("Telegram server error", status=resp.status_code)
                    time.sleep(1.5)
                    continue

                logger.error("Failed to send Telegram message", status=resp.status_code, response=data)
                return False

            return False

        # Try first send; if message too long, split into chunks and send sequentially
        ok = _post_message(text)
        if ok:
            return True

        # Heuristic: if single send failed due to size, chunk by newline respecting 4096 limit
        max_len = 4000  # leave headroom for formatting
        parts: list[str] = []
        current: list[str] = []
        current_len = 0
        for line in text.split("\n"):
            line_len = len(line) + 1  # account for newline
            if current_len + line_len > max_len and current:
                parts.append("\n".join(current))
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += line_len
        if current:
            parts.append("\n".join(current))

        if len(parts) <= 1:
            # Nothing to chunk or still failing
            return False

        total = len(parts)
        for idx, part in enumerate(parts, start=1):
            header = f"[parte {idx}/{total}]\n"
            if not _post_message(header + part):
                return False
        return True
