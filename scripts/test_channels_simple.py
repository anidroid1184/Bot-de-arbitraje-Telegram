#!/usr/bin/env python3
"""
Test simple de conectividad a canales Telegram sin dependencias complejas.

Solo testa la conectividad básica a todos los canales configurados.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from config.channel_mapper import ChannelMapper
from notifications.telegram_sender import TelegramSender

# Load environment from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


async def test_channel_connectivity():
    """Test conectividad a todos los canales configurados."""
    print("🧪 Testing Telegram channel connectivity...")
    
    # Check token
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "CAMBIAR_TOKEN":
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not set or still default in .env")
        return False
    
    print(f"🔑 Token configured: {token[:10]}...")
    
    # Initialize components
    channel_mapper = ChannelMapper()
    telegram_sender = TelegramSender()
    
    if not telegram_sender.bot:
        print("❌ ERROR: Failed to initialize Telegram bot")
        return False
    
    # Get all channels from config
    all_channels = []
    
    # Betburger channels
    betburger_profiles = channel_mapper.config.get('betburger_profiles', {})
    for profile_name, config in betburger_profiles.items():
        channel_id = config.get('channel_id')
        if channel_id:
            all_channels.append((f"betburger.{profile_name}", channel_id))
    
    # Surebet channels
    surebet_profiles = channel_mapper.config.get('surebet_profiles', {})
    for profile_name, config in surebet_profiles.items():
        channel_id = config.get('channel_id')
        if channel_id:
            all_channels.append((f"surebet.{profile_name}", channel_id))
    
    # Support channels
    support = channel_mapper.config.get('support', {})
    for support_name, config in support.items():
        channel_id = config.get('channel_id')
        if channel_id:
            all_channels.append((f"support.{support_name}", channel_id))
    
    if not all_channels:
        print("❌ ERROR: No channels found in configuration")
        return False
    
    print(f"\n📋 Found {len(all_channels)} channels to test:")
    for channel_name, channel_id in all_channels:
        print(f"  - {channel_name}: {channel_id}")
    
    print("\n🚀 Testing connectivity...")
    
    # Test each channel
    results = {}
    success_count = 0
    
    for channel_name, channel_id in all_channels:
        try:
            success = await telegram_sender.send_test_message_async(
                channel_id, 
                f"🧪 **Test de conectividad**\n\nCanal: {channel_name}\nID: {channel_id}\n⏱️ Test completado"
            )
            
            results[channel_name] = success
            status = "✅ OK" if success else "❌ FAILED"
            print(f"  {channel_name:30s} -> {status}")
            
            if success:
                success_count += 1
                
        except Exception as e:
            print(f"  {channel_name:30s} -> ❌ ERROR: {str(e)}")
            results[channel_name] = False
    
    print(f"\n📊 Summary: {success_count}/{len(all_channels)} channels OK")
    
    if success_count == len(all_channels):
        print("🎉 All channels working correctly!")
        return True
    else:
        print("⚠️ Some channels failed. Check bot permissions and channel IDs.")
        return False


async def main():
    """Main function."""
    try:
        success = await test_channel_connectivity()
        return 0 if success else 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        exit_code = 130
    sys.exit(exit_code)
