#!/usr/bin/env python3
"""
Script para crear todos los archivos faltantes en el servidor Linux.
Ejecutar: python create_missing_files.py
"""
import os
from pathlib import Path

# Contenido de config/settings.py
CONFIG_SETTINGS = '''"""
Configuration management for the arbitrage bot.
Handles environment variables, channel mappings, and bot settings.
"""
import os
import yaml
from dataclasses import dataclass
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class TelegramConfig:
    """Telegram bot configuration"""
    bot_token: str
    support_channel_id: str

@dataclass
class BetburgerConfig:
    """Betburger web scraping configuration"""
    username: Optional[str] = None
    password: Optional[str] = None
    base_url: str = "https://betburger.com"
    login_url: str = "https://betburger.com/users/sign_in"

@dataclass
class SurebetConfig:
    """Surebet web scraping configuration"""
    username: Optional[str] = None
    password: Optional[str] = None
    base_url: str = "https://es.surebet.com"
    login_url: str = "https://es.surebet.com/users/sign_in"
    valuebets_url: str = "https://es.surebet.com/valuebets"

@dataclass
class BotConfig:
    """General bot configuration"""
    scraping_interval: int = 5
    max_retries: int = 3
    alert_timeout: int = 2
    log_level: str = "INFO"
    log_file: str = "logs/bot.log"
    headless_mode: bool = False
    browser_timeout: int = 30
    proxy_type: Optional[str] = None
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_username: Optional[str] = None
    proxy_password: Optional[str] = None

class ConfigManager:
    """Manages all bot configuration"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.telegram = self._load_telegram_config()
        self.betburger = self._load_betburger_config()
        self.surebet = self._load_surebet_config()
        self.bot = self._load_bot_config()
        self.channels = self._load_channel_mapping()
    
    @staticmethod
    def _sanitize_url(value: Optional[str], default: str) -> str:
        if value and value.strip().lower().startswith(("http://", "https://")):
            return value.strip()
        return default

    def _load_telegram_config(self) -> TelegramConfig:
        return TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            support_channel_id=os.getenv("TELEGRAM_SUPPORT_CHANNEL_ID", "")
        )
    
    def _load_betburger_config(self) -> BetburgerConfig:
        env_base = os.getenv("BETBURGER_BASE_URL")
        env_login = os.getenv("BETBURGER_LOGIN_URL")
        return BetburgerConfig(
            username=os.getenv("BETBURGER_USERNAME"),
            password=os.getenv("BETBURGER_PASSWORD"),
            base_url=self._sanitize_url(env_base, "https://betburger.com"),
            login_url=self._sanitize_url(env_login, "https://betburger.com/users/sign_in"),
        )
    
    def _load_surebet_config(self) -> SurebetConfig:
        env_base = os.getenv("SUREBET_BASE_URL")
        env_login = os.getenv("SUREBET_LOGIN_URL")
        env_valuebets = os.getenv("SUREBET_VALUEBETS_URL")
        return SurebetConfig(
            username=os.getenv("SUREBET_USERNAME"),
            password=os.getenv("SUREBET_PASSWORD"),
            base_url=self._sanitize_url(env_base, "https://es.surebet.com"),
            login_url=self._sanitize_url(env_login, "https://es.surebet.com/users/sign_in"),
            valuebets_url=self._sanitize_url(env_valuebets, "https://es.surebet.com/valuebets"),
        )
    
    def _load_bot_config(self) -> BotConfig:
        return BotConfig(
            scraping_interval=int(os.getenv("SCRAPING_INTERVAL", "5")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            alert_timeout=int(os.getenv("ALERT_TIMEOUT", "2")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE", "logs/bot.log"),
            headless_mode=os.getenv("HEADLESS_MODE", "false").lower() == "true",
            browser_timeout=int(os.getenv("BROWSER_TIMEOUT", "30")),
            proxy_type=os.getenv("BROWSER_PROXY_TYPE"),
            proxy_host=os.getenv("BROWSER_PROXY_HOST"),
            proxy_port=int(os.getenv("BROWSER_PROXY_PORT", "0")) or None,
            proxy_username=os.getenv("BROWSER_PROXY_USERNAME"),
            proxy_password=os.getenv("BROWSER_PROXY_PASSWORD"),
        )
    
    def _load_channel_mapping(self) -> Dict:
        src_dir = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(src_dir, os.pardir))
        configured = os.path.join(src_dir, "config-configurada.yml")
        preferred = os.path.join(src_dir, "config.yml")
        root_config = os.path.join(project_root, "config.yml")
        fallback = os.path.join(project_root, self.config_dir, "channels.yaml")

        for path in (configured, preferred, root_config, fallback):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data:
                        return data
            except FileNotFoundError:
                continue
        return {}
    
    def get_channel_for_profile(self, platform: str, profile: str) -> Optional[str]:
        if platform == "betburger":
            return self.channels.get("betburger_profiles", {}).get(profile, {}).get("channel_id")
        elif platform == "surebet":
            return self.channels.get("surebet_profiles", {}).get(profile, {}).get("channel_id")
        return None
    
    def get_support_channel(self) -> Optional[str]:
        return self.channels.get("support", {}).get("technical_alerts", {}).get("channel_id")

    def get_profile_defaults(self, platform: str, profile: str) -> Dict:
        key = f"{platform}_profiles"
        return self.channels.get(key, {}).get(profile, {}).get("defaults", {}) or {}

    def get_profile_ui_filter_name(self, platform: str, profile: str) -> Optional[str]:
        key = f"{platform}_profiles"
        value = self.channels.get(key, {}).get(profile, {}).get("ui_filter_name")
        if isinstance(value, str):
            v = value.strip()
            return v or None
        return None
'''

# Contenido simplificado de processors/arbitrage_data.py
ARBITRAGE_DATA = '''"""
Normalized data structure for arbitrage alerts from all platforms.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)

@dataclass
class BookmakerSelection:
    bookmaker: str
    odd: float

@dataclass
class ArbitrageData:
    source: str
    profile: str
    timestamp_utc: str
    sport: Optional[str] = None
    league: Optional[str] = None
    match: Optional[str] = None
    market: Optional[str] = None
    selection_a: Optional[BookmakerSelection] = None
    selection_b: Optional[BookmakerSelection] = None
    roi_pct: Optional[float] = None
    value_pct: Optional[float] = None
    event_start: Optional[str] = None
    target_link: Optional[str] = None
    filter_id: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None
'''

# Contenido de notifications/telegram_sender.py
TELEGRAM_SENDER = '''"""
Telegram message sender for arbitrage alerts.
"""
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import structlog

logger = structlog.get_logger(__name__)

class TelegramSender:
    def __init__(self, bot_token: str):
        self.bot = Bot(token=bot_token)
    
    async def send_message(self, channel_id: str, message: str) -> bool:
        try:
            await self.bot.send_message(chat_id=channel_id, text=message, parse_mode='HTML')
            return True
        except TelegramError as e:
            logger.error("Failed to send message", channel=channel_id, error=str(e))
            return False
'''

# Contenido de pipeline/realtime_processor.py
REALTIME_PROCESSOR = '''"""
Real-time processor for arbitrage alerts.
"""
import asyncio
from typing import List, Optional
import structlog
from processors.arbitrage_data import ArbitrageData
from notifications.telegram_sender import TelegramSender

logger = structlog.get_logger(__name__)

class RealtimeProcessor:
    def __init__(self, telegram_sender: TelegramSender):
        self.telegram_sender = telegram_sender
    
    async def process_alert(self, alert_data: ArbitrageData, channels: List[str]) -> bool:
        message = self._format_alert(alert_data)
        success = True
        
        for channel in channels:
            result = await self.telegram_sender.send_message(channel, message)
            if not result:
                success = False
        
        return success
    
    def _format_alert(self, alert: ArbitrageData) -> str:
        return f"🚨 {alert.source.upper()} Alert\\n{alert.match}\\n{alert.market}"
'''

# Contenido de browser/playwright_manager.py
PLAYWRIGHT_MANAGER = '''"""
Playwright browser manager.
"""
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
import structlog

logger = structlog.get_logger(__name__)

class PlaywrightManager:
    def __init__(self, config):
        self.config = config
        self.playwright = None
        self.browser = None
        self.context = None
    
    def launch(self, engine="chromium"):
        self.playwright = sync_playwright().start()
        if engine == "chromium":
            self.browser = self.playwright.chromium.launch(headless=self.config.bot.headless_mode)
        self.context = self.browser.new_context()
        return self.context
    
    def close(self):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
'''

# Contenido de network/playwright_capture.py
PLAYWRIGHT_CAPTURE = '''"""
Network request capture using Playwright.
"""
import asyncio
from typing import Callable, Optional
import structlog

logger = structlog.get_logger(__name__)

class PlaywrightCapture:
    def __init__(self, context):
        self.context = context
        self.request_handler = None
    
    def set_request_handler(self, handler: Callable):
        self.request_handler = handler
        self.context.on("request", self._handle_request)
    
    def _handle_request(self, request):
        if self.request_handler:
            self.request_handler(request)
'''

def create_file(filepath: str, content: str):
    """Create file with content, creating directories if needed."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✅ Created: {filepath}")

def main():
    """Create all missing files."""
    print("🚀 Creating missing files...")
    
    files_to_create = [
        ("src/config/settings.py", CONFIG_SETTINGS),
        ("src/processors/arbitrage_data.py", ARBITRAGE_DATA),
        ("src/notifications/telegram_sender.py", TELEGRAM_SENDER),
        ("src/pipeline/realtime_processor.py", REALTIME_PROCESSOR),
        ("src/browser/playwright_manager.py", PLAYWRIGHT_MANAGER),
        ("src/network/playwright_capture.py", PLAYWRIGHT_CAPTURE),
    ]
    
    for filepath, content in files_to_create:
        create_file(filepath, content)
    
    print("\\n✅ All files created successfully!")
    print("\\nNow run: python scripts/test_imports_debug.py")

if __name__ == "__main__":
    main()
