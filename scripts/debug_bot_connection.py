#!/usr/bin/env python3
"""
Debug script para diagnosticar problemas de conectividad del bot Telegram.
Compara funcionamiento local vs servidor.
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from telegram import Bot
import aiohttp
import json

# Cargar .env desde raíz del proyecto
repo_root = Path(__file__).parent.parent
env_path = repo_root / ".env"
load_dotenv(env_path)

async def test_network_connectivity():
    """Prueba conectividad básica a internet y Telegram API."""
    print("🌐 Testing network connectivity...")
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test basic internet
            async with session.get('https://httpbin.org/ip', timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ Internet OK - IP: {data.get('origin', 'unknown')}")
                else:
                    print(f"❌ Internet test failed: {resp.status}")
                    return False
            
            # Test Telegram API directly
            async with session.get('https://api.telegram.org/bot/getMe', timeout=10) as resp:
                print(f"📡 Telegram API reachable: {resp.status}")
                return True
                
    except Exception as e:
        print(f"❌ Network connectivity failed: {e}")
        return False

async def test_bot_token_validation():
    """Valida el token del bot directamente con la API."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    
    if not token:
        print("❌ No token found in environment")
        return False
        
    print(f"🔑 Testing token: {token[:10]}...{token[-10:]}")
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{token}/getMe"
            async with session.get(url, timeout=10) as resp:
                data = await resp.json()
                
                if resp.status == 200 and data.get('ok'):
                    bot_info = data['result']
                    print(f"✅ Bot valid: @{bot_info['username']} ({bot_info['first_name']})")
                    print(f"   Bot ID: {bot_info['id']}")
                    return True
                else:
                    print(f"❌ Bot token invalid: {data}")
                    return False
                    
    except Exception as e:
        print(f"❌ Bot validation failed: {e}")
        return False

async def test_channel_access():
    """Prueba acceso a un canal específico."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    
    if not token:
        return False
        
    # Usar el canal de soporte técnico como prueba
    test_channel = "-1002922469529"  # support.technical_alerts
    
    try:
        async with aiohttp.ClientSession() as session:
            # Primero intentar obtener info del chat
            url = f"https://api.telegram.org/bot{token}/getChat"
            params = {"chat_id": test_channel}
            
            async with session.get(url, params=params, timeout=10) as resp:
                data = await resp.json()
                
                if resp.status == 200 and data.get('ok'):
                    chat_info = data['result']
                    print(f"✅ Channel accessible: {chat_info.get('title', 'Unknown')}")
                    print(f"   Type: {chat_info.get('type', 'unknown')}")
                    return True
                else:
                    error_desc = data.get('description', 'Unknown error')
                    print(f"❌ Channel access failed: {error_desc}")
                    
                    if "bot is not a member" in error_desc.lower():
                        print("   → Bot no está agregado al canal")
                    elif "not found" in error_desc.lower():
                        print("   → Canal no encontrado o ID incorrecto")
                    elif "forbidden" in error_desc.lower():
                        print("   → Bot sin permisos suficientes")
                        
                    return False
                    
    except Exception as e:
        print(f"❌ Channel test failed: {e}")
        return False

async def test_environment_info():
    """Muestra información del entorno."""
    print("🔧 Environment info:")
    print(f"   Python: {sys.version}")
    print(f"   Platform: {sys.platform}")
    print(f"   Working dir: {os.getcwd()}")
    print(f"   .env path: {env_path}")
    print(f"   .env exists: {env_path.exists()}")
    
    # Variables de entorno relevantes
    relevant_vars = [
        "TELEGRAM_BOT_TOKEN",
        "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
        "NO_PROXY", "no_proxy"
    ]
    
    for var in relevant_vars:
        value = os.getenv(var)
        if value:
            if "TOKEN" in var:
                print(f"   {var}: {value[:10]}...{value[-10:] if len(value) > 20 else value[10:]}")
            else:
                print(f"   {var}: {value}")

async def main():
    """Ejecuta todas las pruebas de diagnóstico."""
    print("🔍 Telegram Bot Connection Diagnostics")
    print("=" * 50)
    
    await test_environment_info()
    print()
    
    # Test 1: Conectividad de red
    network_ok = await test_network_connectivity()
    print()
    
    # Test 2: Validación del token
    if network_ok:
        token_ok = await test_bot_token_validation()
        print()
        
        # Test 3: Acceso a canales
        if token_ok:
            await test_channel_access()
    
    print("\n" + "=" * 50)
    print("Diagnóstico completado.")

if __name__ == "__main__":
    asyncio.run(main())
