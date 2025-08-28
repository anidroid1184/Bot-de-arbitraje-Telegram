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

# Contenido de notifications/telegram_sender.py (FUNCIONALIDAD COMPLETA)
TELEGRAM_SENDER = '''"""
Telegram sender for arbitrage alerts with rich formatting.

Sends formatted arbitrage alerts to specific Telegram channels based on filters,
with enhanced formatting including timing, urgency, and direct bookmaker links.
"""
from __future__ import annotations

import os
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
import structlog

try:
    import telegram
    from telegram import Bot
    from telegram.constants import ParseMode
except ImportError:
    telegram = None

logger = structlog.get_logger(__name__)


class TelegramSender:
    """Sends arbitrage alerts to Telegram channels."""
    
    def __init__(self, bot_token: str = None):
        """Initialize Telegram sender."""
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.bot = None
        
        if not self.bot_token:
            logger.warning("No Telegram bot token provided")
            return
        
        if telegram is None:
            logger.error("python-telegram-bot not installed. Install with: pip install python-telegram-bot")
            return
        
        try:
            self.bot = Bot(token=self.bot_token)
            logger.info("Telegram bot initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize Telegram bot", error=str(e))
    
    def format_arbitrage_message(self, arb_data) -> str:
        """Format arbitrage data into rich Telegram message."""
        from processors.arbitrage_data import ArbitrageData
        
        if not isinstance(arb_data, ArbitrageData):
            return "❌ Invalid arbitrage data"
        
        # Urgency emoji
        urgency_emojis = {
            "critical": "🚨",
            "high": "⚡",
            "medium": "⏰", 
            "low": "📅",
            "unknown": "❓"
        }
        
        urgency_emoji = urgency_emojis.get(arb_data.urgency_level, "❓")
        
        # Source emoji
        source_emoji = "🎯" if arb_data.source == "betburger" else "💎"
        
        # Build message
        lines = []
        
        # Header with urgency
        lines.append(f"{urgency_emoji} {source_emoji} **{arb_data.source.upper()} ALERT**")
        lines.append("")
        
        # Event info
        if arb_data.sport:
            lines.append(f"🏆 **Sport:** {arb_data.sport.title()}")
        
        if arb_data.league:
            lines.append(f"🏟️ **League:** {arb_data.league}")
        
        if arb_data.match:
            lines.append(f"⚽ **Match:** {arb_data.match}")
        
        if arb_data.market:
            market_text = arb_data.market_details or arb_data.market
            lines.append(f"📊 **Market:** {market_text}")
        
        lines.append("")
        
        # Timing info (CRITICAL)
        if arb_data.event_start:
            lines.append(f"📅 **Event Start:** {arb_data.event_start}")
        
        minutes = arb_data.minutes_to_start
        if minutes is not None:
            if minutes <= 5:
                lines.append(f"⏰ **URGENT:** Starts in {minutes} minutes!")
            elif minutes <= 60:
                lines.append(f"⏰ **Time to Start:** {minutes} minutes")
            else:
                hours = minutes // 60
                mins = minutes % 60
                lines.append(f"⏰ **Time to Start:** {hours}h {mins}m")
        
        lines.append("")
        
        # Bookmaker info
        if arb_data.selection_a:
            lines.append(f"🏪 **{arb_data.selection_a.bookmaker.title()}:** {arb_data.selection_a.odd}")
        
        if arb_data.selection_b:
            lines.append(f"🏪 **{arb_data.selection_b.bookmaker.title()}:** {arb_data.selection_b.odd}")
        
        lines.append("")
        
        # Profit info
        profit = arb_data.profit_percentage
        if profit:
            profit_emoji = "💰" if profit >= 5 else "💵"
            profit_type = "ROI" if arb_data.roi_pct else "Value"
            lines.append(f"{profit_emoji} **{profit_type}:** {profit:.2f}%")
        
        if arb_data.stake_recommendation:
            lines.append(f"💸 **Recommended Stake:** ${arb_data.stake_recommendation:.0f}")
        
        lines.append("")
        
        # Links (CRITICAL)
        if arb_data.bookmaker_links:
            lines.append("🔗 **Direct Links:**")
            for bookmaker, link in arb_data.bookmaker_links.items():
                lines.append(f"   • [{bookmaker.title()}]({link})")
        elif arb_data.target_link:
            lines.append(f"🔗 [**Open Bet**]({arb_data.target_link})")
        
        lines.append("")
        
        # Footer
        lines.append(f"🏷️ **Profile:** {arb_data.profile}")
        if arb_data.filter_id:
            lines.append(f"🔍 **Filter ID:** {arb_data.filter_id}")
        
        lines.append(f"⏱️ **Detected:** {datetime.now().strftime('%H:%M:%S')}")
        
        return "\\n".join(lines)
    
    async def send_alert_async(self, arb_data, channel_id: str) -> bool:
        """Send alert to Telegram channel asynchronously."""
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False
        
        try:
            message = self.format_arbitrage_message(arb_data)
            
            await self.bot.send_message(
                chat_id=channel_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=False
            )
            
            logger.info(
                "Alert sent to Telegram",
                channel=channel_id,
                source=arb_data.source,
                filter_id=arb_data.filter_id,
                profit=arb_data.profit_percentage
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to send Telegram alert",
                channel=channel_id,
                error=str(e),
                source=arb_data.source
            )
            return False
    
    def send_alert(self, arb_data, channel_id: str) -> bool:
        """Send alert to Telegram channel (synchronous wrapper)."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.send_alert_async(arb_data, channel_id))
    
    async def send_test_message_async(self, channel_id: str, message: str = None) -> bool:
        """Send test message to verify bot works."""
        if not self.bot:
            logger.error("Telegram bot not initialized")
            return False
        
        test_message = message or f"🧪 **Test Message**\\n\\nBot is working correctly!\\n⏱️ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        try:
            await self.bot.send_message(
                chat_id=channel_id,
                text=test_message,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info("Test message sent successfully", channel=channel_id)
            return True
            
        except Exception as e:
            logger.error("Failed to send test message", channel=channel_id, error=str(e))
            return False
    
    def send_test_message(self, channel_id: str, message: str = None) -> bool:
        """Send test message (synchronous wrapper)."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.send_test_message_async(channel_id, message))


    """Factory function to create Telegram sender."""
    return TelegramSender(bot_token)


# Contenido de pipeline/realtime_processor.py
REALTIME_PROCESSOR = '''"""Real-time processor for arbitrage alerts.

Processes intercepted requests from Betburger/Surebet and sends them to Telegram channels
based on profile configuration and filters.
"""
from __future__ import annotations

import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import structlog

from processors.betburger_parser import BetburgerParser
from processors.surebet_parser import SurebetParser
from processors.arbitrage_data import ArbitrageData
from config.channel_mapper import ChannelMapper
from notifications.telegram_sender import TelegramSender

logger = structlog.get_logger(__name__)


class RealtimeProcessor:
    """Processes intercepted requests and sends alerts to Telegram in real-time."""
    
    def __init__(self, config_path: str = None):
        """Initialize real-time processor."""
        self.channel_mapper = ChannelMapper(config_path)
        self.telegram_sender = TelegramSender()
        
        # Initialize processors
        self.betburger_processor = BetburgerParser()
        self.surebet_processor = SurebetParser()
        
        # Stats
        self.processed_count = 0
        self.sent_count = 0
        self.error_count = 0
        
        logger.info("RealtimeProcessor initialized")
    
    def process_request(self, url: str, response_data: Dict[str, Any], profile: str = None) -> List[ArbitrageData]:
        """Process a single intercepted request and return arbitrage data."""
        try:
            # Determine source platform
            if "betburger.com" in url:
                source = "betburger"
                processor = self.betburger_processor
            elif "surebet.com" in url:
                source = "surebet"
                processor = self.surebet_processor
            else:
                logger.warning("Unknown platform in URL", url=url)
                return []
            
            # Process the response data
            arbitrage_alerts = processor.process_response(response_data, profile=profile)
            
            if arbitrage_alerts:
                logger.info(
                    "Processed request successfully",
                    source=source,
                    url=url,
                    alerts_count=len(arbitrage_alerts),
                    profile=profile
                )
                self.processed_count += len(arbitrage_alerts)
            
            return arbitrage_alerts
            
        except Exception as e:
            logger.error("Failed to process request", url=url, error=str(e))
            self.error_count += 1
            return []
    
    async def send_alerts_async(self, arbitrage_alerts: List[ArbitrageData]) -> int:
        """Send multiple alerts to appropriate channels asynchronously."""
        sent_count = 0
        
        for arb_data in arbitrage_alerts:
            try:
                # Get matching channels for this alert
                channels = self.channel_mapper.get_channels_for_arbitrage(arb_data)
                
                if not channels:
                    # Fallback: try to get channel by profile name
                    channel_id = self.channel_mapper.get_channel_for_profile(arb_data.source, arb_data.profile)
                    if channel_id:
                        channels = [channel_id]
                
                if not channels:
                    logger.warning(
                        "No channels found for alert",
                        source=arb_data.source,
                        profile=arb_data.profile,
                        filter_id=arb_data.filter_id
                    )
                    continue
                
                # Send to all matching channels
                for channel_id in channels:
                    success = await self.telegram_sender.send_alert_async(arb_data, channel_id)
                    if success:
                        sent_count += 1
                        logger.info(
                            "Alert sent successfully",
                            channel=channel_id,
                            source=arb_data.source,
                            profile=arb_data.profile,
                            profit=arb_data.profit_percentage
                        )
                    else:
                        self.error_count += 1
                        
            except Exception as e:
                logger.error("Failed to send alert", error=str(e), source=arb_data.source)
                self.error_count += 1
        
        self.sent_count += sent_count
        return sent_count
    
    def send_alerts(self, arbitrage_alerts: List[ArbitrageData]) -> int:
        """Send alerts synchronously (wrapper for async method)."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.send_alerts_async(arbitrage_alerts))
    
    def process_and_send(self, url: str, response_data: Dict[str, Any], profile: str = None) -> int:
        """Process request and immediately send alerts to Telegram."""
        start_time = datetime.now()
        
        # Process the request
        arbitrage_alerts = self.process_request(url, response_data, profile)
        
        if not arbitrage_alerts:
            return 0
        
        # Send alerts
        sent_count = self.send_alerts(arbitrage_alerts)
        
        # Calculate latency
        latency = (datetime.now() - start_time).total_seconds()
        
        logger.info(
            "Process and send completed",
            alerts_processed=len(arbitrage_alerts),
            alerts_sent=sent_count,
            latency_seconds=round(latency, 3),
            profile=profile
        )
        
        return sent_count
    
    async def test_channel_connectivity(self) -> Dict[str, bool]:
        """Test connectivity to all configured channels."""
        results = {}
        
        # Get all channels from config
        all_channels = []
        
        # Betburger channels
        betburger_profiles = self.channel_mapper.config.get('betburger_profiles', {})
        for profile_name, config in betburger_profiles.items():
            channel_id = config.get('channel_id')
            if channel_id:
                all_channels.append((f"betburger.{profile_name}", channel_id))
        
        # Surebet channels
        surebet_profiles = self.channel_mapper.config.get('surebet_profiles', {})
        for profile_name, config in surebet_profiles.items():
            channel_id = config.get('channel_id')
            if channel_id:
                all_channels.append((f"surebet.{profile_name}", channel_id))
        
        # Support channels
        support = self.channel_mapper.config.get('support', {})
        for support_name, config in support.items():
            channel_id = config.get('channel_id')
            if channel_id:
                all_channels.append((f"support.{support_name}", channel_id))
        
        # Test each channel
        for channel_name, channel_id in all_channels:
            try:
                success = await self.telegram_sender.send_test_message_async(
                    channel_id, 
                    f"🧪 **Test de conectividad**\\n\\nCanal: {channel_name}\\nID: {channel_id}\\n⏱️ {datetime.now().strftime('%H:%M:%S')}"
                )
                results[channel_name] = success
                
            except Exception as e:
                logger.error("Channel test failed", channel=channel_name, error=str(e))
                results[channel_name] = False
        
        return results
    
    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return {
            "processed_count": self.processed_count,
            "sent_count": self.sent_count,
            "error_count": self.error_count,
            "success_rate": round((self.sent_count / max(self.processed_count, 1)) * 100, 2)
        }


def create_processor(config_path: str = None) -> RealtimeProcessor:
    """Factory function to create real-time processor."""
    return RealtimeProcessor(config_path)


# Contenido de browser/playwright_manager.py
PLAYWRIGHT_MANAGER = '''"""Playwright browser manager with full configuration support.

Manages Playwright browser instances with proxy support, user profiles,
and optimized settings for web scraping.
"""
from __future__ import annotations

import os
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path
import structlog

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
except ImportError:
    sync_playwright = None

logger = structlog.get_logger(__name__)


class PlaywrightManager:
    """Manages Playwright browser instances with advanced configuration."""
    
    def __init__(self, config):
        """Initialize Playwright manager with configuration."""
        self.config = config
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.pages: List[Page] = []
        
        if sync_playwright is None:
            logger.error("Playwright not installed. Install with: pip install playwright")
            raise ImportError("Playwright not available")
    
    def launch(self, engine: str = "chromium") -> BrowserContext:
        """Launch browser with specified engine and configuration."""
        try:
            self.playwright = sync_playwright().start()
            
            # Browser launch options
            launch_options = {
                "headless": self.config.bot.headless_mode,
                "args": [
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-web-security",
                    "--disable-features=VizDisplayCompositor",
                    "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ]
            }
            
            # Add proxy if configured
            if self.config.bot.proxy_host and self.config.bot.proxy_port:
                proxy_config = {
                    "server": f"{self.config.bot.proxy_type or 'http'}://{self.config.bot.proxy_host}:{self.config.bot.proxy_port}"
                }
                if self.config.bot.proxy_username:
                    proxy_config["username"] = self.config.bot.proxy_username
                if self.config.bot.proxy_password:
                    proxy_config["password"] = self.config.bot.proxy_password
                
                launch_options["proxy"] = proxy_config
                logger.info("Using proxy configuration", proxy=proxy_config["server"])
            
            # Launch browser
            if engine == "chromium":
                self.browser = self.playwright.chromium.launch(**launch_options)
            elif engine == "firefox":
                self.browser = self.playwright.firefox.launch(**launch_options)
            elif engine == "webkit":
                self.browser = self.playwright.webkit.launch(**launch_options)
            else:
                raise ValueError(f"Unsupported browser engine: {engine}")
            
            # Create context with additional options
            context_options = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "java_script_enabled": True,
                "accept_downloads": False,
                "ignore_https_errors": True,
            }
            
            self.context = self.browser.new_context(**context_options)
            
            # Set default timeout
            self.context.set_default_timeout(self.config.bot.browser_timeout * 1000)
            
            logger.info("Browser launched successfully", engine=engine, headless=self.config.bot.headless_mode)
            return self.context
            
        except Exception as e:
            logger.error("Failed to launch browser", engine=engine, error=str(e))
            self.close()
            raise
    
    def new_page(self, url: str = None) -> Page:
        """Create a new page in the current context."""
        if not self.context:
            raise RuntimeError("Browser context not initialized. Call launch() first.")
        
        page = self.context.new_page()
        self.pages.append(page)
        
        # Navigate to URL if provided
        if url:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                logger.info("Navigated to URL", url=url)
            except Exception as e:
                logger.error("Failed to navigate to URL", url=url, error=str(e))
        
        return page
    
    def close_page(self, page: Page):
        """Close a specific page."""
        try:
            page.close()
            if page in self.pages:
                self.pages.remove(page)
            logger.debug("Page closed successfully")
        except Exception as e:
            logger.error("Failed to close page", error=str(e))
    
    def close(self):
        """Close all browser resources."""
        try:
            # Close all pages
            for page in self.pages[:]:
                self.close_page(page)
            
            # Close context
            if self.context:
                self.context.close()
                self.context = None
                logger.debug("Browser context closed")
            
            # Close browser
            if self.browser:
                self.browser.close()
                self.browser = None
                logger.debug("Browser closed")
            
            # Stop playwright
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
                logger.debug("Playwright stopped")
                
        except Exception as e:
            logger.error("Error during browser cleanup", error=str(e))
    
    def is_running(self) -> bool:
        """Check if browser is running."""
        return self.browser is not None and self.context is not None
    
    def get_page_count(self) -> int:
        """Get number of open pages."""
        return len(self.pages)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Contenido de network/playwright_capture.py
PLAYWRIGHT_CAPTURE = '''"""Network request capture using Playwright with advanced filtering.

Captures and processes network requests from Betburger and Surebet platforms,
with intelligent filtering and response processing.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional, Dict, Any, List, Set
from datetime import datetime
import structlog

try:
    from playwright.sync_api import BrowserContext, Request, Response
except ImportError:
    BrowserContext = Request = Response = None

logger = structlog.get_logger(__name__)


class PlaywrightCapture:
    """Captures and processes network requests using Playwright."""
    
    def __init__(self, context: BrowserContext):
        """Initialize request capture."""
        self.context = context
        self.request_handler: Optional[Callable] = None
        self.response_handler: Optional[Callable] = None
        
        # Request filtering patterns
        self.betburger_patterns = [
            r'/api/',
            r'/arbs',
            r'/valuebets',
            r'/surebets',
            r'/filters',
            r'/users/'
        ]
        
        self.surebet_patterns = [
            r'/api/',
            r'/valuebets',
            r'/surebets',
            r'/arbs',
            r'/users/',
            r'/filters'
        ]
        
        # Statistics
        self.captured_requests = 0
        self.processed_responses = 0
        self.filtered_requests = 0
        
        logger.info("PlaywrightCapture initialized")
    
    def set_request_handler(self, handler: Callable[[Request], None]):
        """Set handler for captured requests."""
        self.request_handler = handler
        self.context.on("request", self._handle_request)
        logger.info("Request handler set")
    
    def set_response_handler(self, handler: Callable[[Response, Dict[str, Any]], None]):
        """Set handler for captured responses with JSON data."""
        self.response_handler = handler
        self.context.on("response", self._handle_response)
        logger.info("Response handler set")
    
    def _handle_request(self, request: Request):
        """Handle intercepted request."""
        try:
            url = request.url
            method = request.method
            
            # Filter relevant requests
            if not self._is_relevant_request(url):
                self.filtered_requests += 1
                return
            
            self.captured_requests += 1
            
            logger.debug(
                "Request captured",
                method=method,
                url=url,
                headers=dict(request.headers)
            )
            
            # Call custom handler if set
            if self.request_handler:
                self.request_handler(request)
                
        except Exception as e:
            logger.error("Error handling request", error=str(e), url=request.url)
    
    def _handle_response(self, response: Response):
        """Handle intercepted response."""
        try:
            url = response.url
            status = response.status
            
            # Filter relevant responses
            if not self._is_relevant_request(url):
                return
            
            # Only process successful JSON responses
            if status != 200:
                logger.debug("Non-200 response ignored", url=url, status=status)
                return
            
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                logger.debug("Non-JSON response ignored", url=url, content_type=content_type)
                return
            
            # Extract JSON data
            try:
                json_data = response.json()
                self.processed_responses += 1
                
                logger.info(
                    "Response captured",
                    url=url,
                    status=status,
                    data_keys=list(json_data.keys()) if isinstance(json_data, dict) else "non-dict"
                )
                
                # Call custom handler if set
                if self.response_handler:
                    self.response_handler(response, json_data)
                    
            except Exception as e:
                logger.debug("Failed to parse JSON response", url=url, error=str(e))
                
        except Exception as e:
            logger.error("Error handling response", error=str(e), url=response.url)
    
    def _is_relevant_request(self, url: str) -> bool:
        """Check if request URL matches filtering patterns."""
        # Check Betburger patterns
        if "betburger.com" in url:
            return any(re.search(pattern, url) for pattern in self.betburger_patterns)
        
        # Check Surebet patterns
        if "surebet.com" in url:
            return any(re.search(pattern, url) for pattern in self.surebet_patterns)
        
        return False
    
    def extract_filter_id(self, url: str) -> Optional[str]:
        """Extract filter ID from URL if present."""
        # Common patterns for filter IDs
        patterns = [
            r'filter[_-]?id[=:]([^&\\s]+)',
            r'filterId[=:]([^&\\s]+)',
            r'filter[=:]([^&\\s]+)',
            r'/filters/([^/?]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def get_stats(self) -> Dict[str, int]:
        """Get capture statistics."""
        return {
            "captured_requests": self.captured_requests,
            "processed_responses": self.processed_responses,
            "filtered_requests": self.filtered_requests,
            "total_requests": self.captured_requests + self.filtered_requests
        }
    
    def reset_stats(self):
        """Reset capture statistics."""
        self.captured_requests = 0
        self.processed_responses = 0
        self.filtered_requests = 0
        logger.info("Capture statistics reset")


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
