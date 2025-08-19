"""
Simple Telegram notifier using python-telegram-bot.
Reads TELEGRAM_BOT_TOKEN and TELEGRAM_SUPPORT_CHANNEL_ID from env.
If configuration is missing, it logs and no-ops.
"""
from __future__ import annotations

import os
from typing import Optional
from dataclasses import dataclass

from .logger import get_module_logger

logger = get_module_logger("telegram_notifier")

try:
    # Lazy import to avoid hard dependency at module import time
    from telegram import Bot
except Exception:  # pragma: no cover
    Bot = None  # type: ignore


@dataclass
class NotifierConfig:
    bot_token: str
    default_chat_id: Optional[str] = None


class TelegramNotifier:
    """Minimal wrapper to send text messages to Telegram."""

    def __init__(self, config: Optional[NotifierConfig] = None) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_SUPPORT_CHANNEL_ID")
        if config is not None:
            token = config.bot_token or token
            chat_id = config.default_chat_id or chat_id
        self.token = token
        self.default_chat_id = chat_id
        self._bot = None
        if not token:
            logger.warning("TELEGRAM_BOT_TOKEN missing; notifier will no-op")
        else:
            if Bot is None:
                logger.warning("python-telegram-bot not available; notifier will no-op")
            else:
                try:
                    self._bot = Bot(token=token)
                except Exception as e:
                    logger.error("Failed to initialize Telegram Bot", error=str(e))
                    self._bot = None

    def send_text(self, text: str, chat_id: Optional[str] = None) -> bool:
        if not self._bot or not self.token:
            return False
        target = chat_id or self.default_chat_id
        if not target:
            logger.warning("No chat_id provided and TELEGRAM_SUPPORT_CHANNEL_ID is missing")
            return False
        try:
            self._bot.send_message(chat_id=target, text=text, disable_web_page_preview=True)
            logger.info("Sent Telegram message", length=len(text))
            return True
        except Exception as e:
            logger.error("Failed to send Telegram message", error=str(e))
            return False
