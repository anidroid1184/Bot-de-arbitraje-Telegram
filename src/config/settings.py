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
    
    @staticmethod
    def _sanitize_url(value: Optional[str], default: str) -> str:
        """Return value if it looks like an HTTP(S) URL; otherwise return default.

        Prevents accidental Windows/WSL file paths (e.g., ".venv/bin/python") from
        being used as navigation targets by Selenium (which would turn them into
        file:/// URLs).
        """
        if value and value.strip().lower().startswith(("http://", "https://")):
            return value.strip()
        return default

    def _load_telegram_config(self) -> TelegramConfig:
        """Load Telegram configuration from environment"""
        return TelegramConfig(
            bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            support_channel_id=os.getenv("TELEGRAM_SUPPORT_CHANNEL_ID", "")
        )
    
    def _load_betburger_config(self) -> BetburgerConfig:
        """Load Betburger web scraping configuration from environment"""
        env_base = os.getenv("BETBURGER_BASE_URL")
        env_login = os.getenv("BETBURGER_LOGIN_URL")
        return BetburgerConfig(
            username=os.getenv("BETBURGER_USERNAME"),
            password=os.getenv("BETBURGER_PASSWORD"),
            base_url=self._sanitize_url(env_base, "https://betburger.com"),
            login_url=self._sanitize_url(env_login, "https://betburger.com/users/sign_in"),
        )
    
    def _load_surebet_config(self) -> SurebetConfig:
        """Load Surebet web scraping configuration from environment"""
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
        # Preferred path: src/config/config.yml (co-located with this module)
        src_dir = os.path.dirname(__file__)
        project_root = os.path.abspath(os.path.join(src_dir, os.pardir))
        preferred = os.path.join(src_dir, "config.yml")
        # Secondary preferred path: project root config.yml (repo_root/config.yml)
        root_config = os.path.join(project_root, "config.yml")
        # Backward-compatible fallback: repo_root/config/channels.yaml
        fallback = os.path.join(project_root, self.config_dir, "channels.yaml")

        for path in (preferred, root_config, fallback):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data:
                        return data
            except FileNotFoundError:
                continue
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
