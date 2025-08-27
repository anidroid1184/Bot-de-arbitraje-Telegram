#!/usr/bin/env python3
"""
Test básico del bot Telegram - verifica que el bot funciona.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
import telegram
from telegram import Bot

load_dotenv()

async def test_bot():
    """Test básico del bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    
    if not token:
        print("❌ No token found")
        return False
    
    print(f"🔑 Testing bot with token: {token[:10]}...")
    
    try:
        bot = Bot(token=token)
        
        # Get bot info
        me = await bot.get_me()
        print(f"✅ Bot connected: @{me.username} ({me.first_name})")
        print(f"   Bot ID: {me.id}")
        
        # Test sending to your own chat (replace with your user ID)
        # To get your user ID, message @userinfobot on Telegram
        
        print("\n📋 To test channels:")
        print("1. Add the bot to each channel as admin")
        print("2. Give permissions: Send Messages, Send Media")
        print("3. For private channels, forward a message from the channel to @userinfobot to get correct ID")
        
        return True
        
    except Exception as e:
        print(f"❌ Bot test failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_bot())
