"""
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
    # Optional proxy configuration for the browser (HTTP or SOCKS5)
    proxy_type: Optional[str] = None  # "http" | "socks5"
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
    
    def _load_telegram_config(self) -> TelegramConfig:
        """Load Telegram configuration from environment"""
        return TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            support_channel_id=os.getenv("TELEGRAM_SUPPORT_CHANNEL_ID", "")
        )
    
    def _load_betburger_config(self) -> BetburgerConfig:
        """Load Betburger web scraping configuration from environment"""
        return BetburgerConfig(
            username=os.getenv("BETBURGER_USERNAME"),
            password=os.getenv("BETBURGER_PASSWORD"),
            base_url=os.getenv("BETBURGER_BASE_URL", "https://betburger.com"),
            login_url=os.getenv("BETBURGER_LOGIN_URL", "https://betburger.com/users/sign_in")
        )
    
    def _load_surebet_config(self) -> SurebetConfig:
        """Load Surebet web scraping configuration from environment"""
        return SurebetConfig(
            username=os.getenv("SUREBET_USERNAME"),
            password=os.getenv("SUREBET_PASSWORD"),
            base_url=os.getenv("SUREBET_BASE_URL", "https://es.surebet.com"),
            login_url=os.getenv("SUREBET_LOGIN_URL", "https://es.surebet.com/users/sign_in"),
            valuebets_url=os.getenv("SUREBET_VALUEBETS_URL", "https://es.surebet.com/valuebets")
        )
    
    def _load_bot_config(self) -> BotConfig:
        """Load general bot configuration from environment"""
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
        """Load channel mapping from YAML file"""
        channels_file = os.path.join(self.config_dir, "channels.yaml")
        try:
            with open(channels_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                # yaml.safe_load returns None for empty files
                return data or {}
        except FileNotFoundError:
            return {}
    
    def get_channel_for_profile(self, platform: str, profile: str) -> Optional[str]:
        """Get Telegram channel ID for a specific profile"""
        if platform == "betburger":
            return self.channels.get("betburger_profiles", {}).get(profile, {}).get("channel_id")
        elif platform == "surebet":
            return self.channels.get("surebet_profiles", {}).get(profile, {}).get("channel_id")
        return None
    
    def get_support_channel(self) -> Optional[str]:
        """Get technical support channel ID"""
        return self.channels.get("support", {}).get("technical_alerts", {}).get("channel_id")
