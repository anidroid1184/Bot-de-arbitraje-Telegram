"""
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
        
        return "\n".join(lines)
    
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
        
        test_message = message or f"🧪 **Test Message**\n\nBot is working correctly!\n⏱️ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
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


def create_sender(bot_token: str = None) -> TelegramSender:
    """Factory function to create Telegram sender."""
    return TelegramSender(bot_token)
