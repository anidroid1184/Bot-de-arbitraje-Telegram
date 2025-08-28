#!/usr/bin/env python3
"""
Test simple de conectividad Telegram sin dependencias complejas.
Solo prueba el bot token y canales básicos.
"""
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load environment
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH, override=True)

async def test_telegram_basic():
    """Test básico de Telegram bot."""
    
    # Check bot token
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token or bot_token == "CAMBIAR_TOKEN":
        print("❌ TELEGRAM_BOT_TOKEN no configurado o es placeholder")
        return False
    
    print(f"✅ Bot token encontrado: {bot_token[:10]}...")
    
    # Test basic bot info
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        bot_info = data.get("result", {})
                        print(f"✅ Bot conectado: @{bot_info.get('username', 'unknown')}")
                        return True
                    else:
                        print(f"❌ API error: {data}")
                        return False
                else:
                    print(f"❌ HTTP error: {response.status}")
                    return False
                    
    except Exception as e:
        print(f"❌ Error conectando a Telegram: {e}")
        return False

async def test_channel_send():
    """Test envío a canal de soporte."""
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    support_channel = os.getenv("SUPPORT_CHANNEL_ID")
    
    if not support_channel:
        print("❌ SUPPORT_CHANNEL_ID no configurado")
        return False
    
    print(f"🧪 Probando envío a canal: {support_channel}")
    
    try:
        import aiohttp
        
        message = "🧪 **Test de conectividad**\n\nBot funcionando correctamente ✅"
        
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": support_channel,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            async with session.post(url, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        print("✅ Mensaje enviado exitosamente")
                        return True
                    else:
                        print(f"❌ Error API: {result}")
                        return False
                else:
                    print(f"❌ HTTP error: {response.status}")
                    error_text = await response.text()
                    print(f"Error details: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")
        return False

async def main():
    """Main test function."""
    print("🚀 Iniciando test simple de Telegram...")
    
    # Test 1: Bot connectivity
    bot_ok = await test_telegram_basic()
    if not bot_ok:
        print("❌ Test fallido - bot no conecta")
        return 1
    
    # Test 2: Channel send
    channel_ok = await test_channel_send()
    if not channel_ok:
        print("❌ Test fallido - no se puede enviar a canal")
        return 1
    
    print("✅ Todos los tests pasaron!")
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
