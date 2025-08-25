"""
Telegram command listener to control runtime behavior (/pause, /start).

- Polls Telegram Bot API getUpdates (long polling) in a background thread.
- Accepts commands only from configured sources:
  * TELEGRAM_SUPPORT_CHANNEL_ID (channel/group where the bot is admin)
  * Optional TELEGRAM_ALLOWED_USER_IDS (comma-separated user IDs)
- Exposes a thread-safe pause flag checked by the main loop.

Environment variables:
- TELEGRAM_BOT_TOKEN (required)
- TELEGRAM_SUPPORT_CHANNEL_ID (recommended)
- TELEGRAM_ALLOWED_USER_IDS (optional, comma-separated integers)
- TELEGRAM_POLL_TIMEOUT_SEC (optional, default 25)

Usage:
    ctrl = PauseController()
    listener = BotCommandListener(ctrl)
    listener.start()
    ...
    if ctrl.is_paused():
        time.sleep(1)
"""
from __future__ import annotations

import os
import time
import threading
from typing import Optional, Set

import requests

from .logger import get_module_logger
from .telegram_notifier import TelegramNotifier

logger = get_module_logger("command_controller")


class PauseController:
    """Thread-safe control flags: pause and config_mode, with reason tracking."""

    def __init__(self) -> None:
        self._paused = False
        self._config_mode = False
        self._lock = threading.Lock()
        self._reason: Optional[str] = None

    def pause(self, reason: str = "manual") -> None:
        with self._lock:
            self._paused = True
            self._reason = reason
            logger.info("Bot paused", reason=reason)

    def resume(self) -> None:
        with self._lock:
            self._paused = False
            self._reason = None
            logger.info("Bot resumed")

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def reason(self) -> Optional[str]:
        with self._lock:
            return self._reason

    # --- Config mode ---
    def enable_config(self) -> None:
        with self._lock:
            self._config_mode = True
            logger.info("Config mode enabled")

    def disable_config(self) -> None:
        with self._lock:
            self._config_mode = False
            logger.info("Config mode disabled")

    def is_config_mode(self) -> bool:
        with self._lock:
            return self._config_mode


class BotCommandListener:
    """Background Telegram getUpdates poller that toggles PauseController.

    Supports commands:
      /pause          -> pause actions
      /start          -> resume actions
      /start-config   -> enter configuration mode (no scraping/sending)
      /finish-config  -> exit configuration mode
      /status         -> report current state
    """

    def __init__(self, controller: PauseController) -> None:
        self._controller = controller
        self._token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self._support_chat = (os.getenv("TELEGRAM_SUPPORT_CHANNEL_ID") or "").strip()
        allowed = (os.getenv("TELEGRAM_ALLOWED_USER_IDS") or "").strip()
        self._allowed_users: Set[str] = set(u.strip() for u in allowed.split(",") if u.strip())
        try:
            self._poll_timeout = int(os.getenv("TELEGRAM_POLL_TIMEOUT_SEC", "25"))
        except Exception:
            self._poll_timeout = 25
        self._offset = 0
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._notifier = TelegramNotifier()

        if not self._token:
            logger.warning("TELEGRAM_BOT_TOKEN missing; command listener disabled")

    def start(self) -> None:
        if not self._token:
            return
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="tg-cmd-listener", daemon=True)
        self._thread.start()
        logger.info("Telegram command listener started")

    def stop(self) -> None:
        self._stop.set()

    # --- Internals ---

    def _authorized(self, chat_id: Optional[str], user_id: Optional[str]) -> bool:
        # Channels/supergroups send messages with chat.id; direct messages use from.id
        if self._support_chat and chat_id and str(chat_id) == str(self._support_chat):
            return True
        if user_id and (user_id in self._allowed_users):
            return True
        return False

    def _run(self) -> None:
        url = f"https://api.telegram.org/bot{self._token}/getUpdates"
        while not self._stop.is_set():
            params = {
                "timeout": self._poll_timeout,
                "offset": self._offset + 1 if self._offset else None,
                "allowed_updates": ["message", "channel_post"],
            }
            # Remove None params (requests would serialize as 'None')
            params = {k: v for k, v in params.items() if v is not None}
            try:
                resp = requests.get(url, params=params, timeout=self._poll_timeout + 5)
                if resp.status_code != 200:
                    logger.warning("getUpdates non-200", status=resp.status_code)
                    time.sleep(2)
                    continue
                data = resp.json()
                if not isinstance(data, dict) or not data.get("ok"):
                    time.sleep(1)
                    continue
                updates = data.get("result") or []
                for upd in updates:
                    try:
                        self._offset = max(self._offset, int(upd.get("update_id") or 0))
                    except Exception:
                        pass
                    self._handle_update(upd)
            except requests.RequestException as e:
                logger.warning("getUpdates error", error=str(e))
                time.sleep(2)
            except Exception as e:
                logger.warning("getUpdates unexpected error", error=str(e))
                time.sleep(2)

    def _handle_update(self, upd: dict) -> None:
        # Prefer channel_post for channels, message for groups/DMs
        msg = upd.get("channel_post") or upd.get("message") or {}
        text = str(msg.get("text") or "").strip()
        if not text:
            return
        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id")) if chat.get("id") is not None else None
        frm = msg.get("from") or {}
        user_id = str(frm.get("id")) if frm.get("id") is not None else None

        if not self._authorized(chat_id, user_id):
            return

        cmd = text.split()[0].lower()
        if cmd == "/pause":
            self._controller.pause("telegram")
            self._notifier.send_text("[control] Bot pausado. Usa /start para reanudar.", chat_id=chat_id)
        elif cmd == "/start":
            self._controller.resume()
            self._notifier.send_text("[control] Bot reanudado.", chat_id=chat_id)
        elif cmd == "/start-config":
            self._controller.enable_config()
            self._notifier.send_text("[control] Modo configuración ACTIVADO. El bot no enviará alertas hasta /finish-config.", chat_id=chat_id)
        elif cmd == "/finish-config":
            self._controller.disable_config()
            self._notifier.send_text("[control] Modo configuración DESACTIVADO. Se reanuda el scraping/envío.", chat_id=chat_id)
        elif cmd == "/status":
            if self._controller.is_paused():
                reason = self._controller.reason() or "manual"
                self._notifier.send_text(f"[control] Estado: pausado (razón: {reason})", chat_id=chat_id)
            else:
                if self._controller.is_config_mode():
                    self._notifier.send_text("[control] Estado: en ejecución (modo configuración ACTIVADO)", chat_id=chat_id)
                else:
                    self._notifier.send_text("[control] Estado: en ejecución", chat_id=chat_id)
        else:
            # Ignore other messages
            return
