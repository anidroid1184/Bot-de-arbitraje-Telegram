"""
Simple Telegram notifier using python-telegram-bot.
Reads TELEGRAM_BOT_TOKEN and TELEGRAM_SUPPORT_CHANNEL_ID from env.
If configuration is missing, it logs and no-ops.
"""
from __future__ import annotations

import os
import asyncio
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
        if not self._bot or not self.token:
            return False
        target = chat_id or self.default_chat_id
        if not target:
            logger.warning("No chat_id provided and TELEGRAM_SUPPORT_CHANNEL_ID is missing")
            return False
        
        async def _async_send() -> None:
            await self._bot.send_message(chat_id=target, text=text, disable_web_page_preview=True)

        try:
            try:
                loop = asyncio.get_running_loop()
                # If we're already in an event loop, schedule the task and do not block
                loop.create_task(_async_send())
            except RuntimeError:
                # No running loop; run synchronously
                asyncio.run(_async_send())
            logger.info("Sent Telegram message", length=len(text))
            return True
        except Exception as e:
            logger.error("Failed to send Telegram message", error=str(e))
            return False
