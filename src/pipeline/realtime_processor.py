"""
Real-time processor for arbitrage alerts.

Processes intercepted requests from Betburger/Surebet and sends them to Telegram channels
based on profile configuration and filters.
"""
from __future__ import annotations

import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import structlog

from processors.betburger_processor import BetburgerProcessor
from processors.surebet_processor import SurebetProcessor
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
        self.betburger_processor = BetburgerProcessor()
        self.surebet_processor = SurebetProcessor()
        
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
                    f"🧪 **Test de conectividad**\n\nCanal: {channel_name}\nID: {channel_id}\n⏱️ {datetime.now().strftime('%H:%M:%S')}"
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
