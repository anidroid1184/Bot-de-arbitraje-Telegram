#!/usr/bin/env python3
"""
Test script para pipeline completo: interceptar requests reales → enviar a Telegram.

Basado en simple_surebet_login_test.py pero integra el RealtimeProcessor
para enviar automáticamente las alertas interceptadas a canales Telegram.

Usage:
    python scripts/test_realtime_pipeline.py
    python scripts/test_realtime_pipeline.py --test-channels  # solo test conectividad
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# Add src to path
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

print(f"DEBUG: Added to sys.path: {src_path}")
print(f"DEBUG: Current working directory: {os.getcwd()}")
print(f"DEBUG: sys.path: {sys.path[:3]}...")

from dotenv import load_dotenv

# Import modules one by one to identify specific failures
try:
    from pipeline.realtime_processor import RealtimeProcessor
    print("✅ Successfully imported RealtimeProcessor")
except ImportError as e:
    print(f"❌ Failed to import RealtimeProcessor: {e}")
    RealtimeProcessor = None

try:
    from browser.playwright_manager import PlaywrightManager
    print("✅ Successfully imported PlaywrightManager")
except ImportError as e:
    print(f"❌ Failed to import PlaywrightManager: {e}")
    PlaywrightManager = None

try:
    from network.playwright_capture import PlaywrightCapture
    print("✅ Successfully imported PlaywrightCapture")
except ImportError as e:
    print(f"❌ Failed to import PlaywrightCapture: {e}")
    PlaywrightCapture = None
import structlog

# Load environment
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH, override=True)

logger = structlog.get_logger(__name__)


class RealtimePipelineTest:
    """Test del pipeline completo con requests reales."""
    
    def __init__(self):
        """Initialize test."""
        self.processor = RealtimeProcessor()
        self.playwright_manager = None
        self.capture = None
        self.processed_requests = 0
        self.sent_alerts = 0
        
    async def test_channel_connectivity(self):
        """Test conectividad a todos los canales configurados."""
        print("🧪 Testing channel connectivity...")
        
        results = await self.processor.test_channel_connectivity()
        
        print("\n📊 Channel Test Results:")
        success_count = 0
        for channel_name, success in results.items():
            status = "✅ OK" if success else "❌ FAILED"
            print(f"  {channel_name:30s} -> {status}")
            if success:
                success_count += 1
        
        print(f"\n📈 Summary: {success_count}/{len(results)} channels OK")
        return success_count == len(results)
    
    def setup_playwright(self):
        """Setup Playwright manager and capture."""
        try:
            # Create config object similar to smoke test
            class Config:
                def __init__(self):
                    self.bot = self
                    self.headless = os.getenv("BOT_HEADLESS", "false").lower() == "true"
                    self.browser = os.getenv("BROWSER", "firefox")
            
            config = Config()
            
            # Initialize Playwright manager
            self.playwright_manager = PlaywrightManager(config)
            self.playwright_manager.launch(engine=config.browser)
            
            # Setup capture with request processing
            self.capture = PlaywrightCapture(
                self.playwright_manager,
                patterns=["/api/", "/valuebets", "/surebets", "/arbs", "/users/"],
                process_response_callback=self.process_intercepted_request
            )
            
            logger.info("Playwright setup completed")
            return True
            
        except Exception as e:
            logger.error("Failed to setup Playwright", error=str(e))
            return False
    
    def process_intercepted_request(self, url: str, response_data: dict, **kwargs):
        """Process intercepted request through pipeline."""
        try:
            profile = kwargs.get('profile', 'unknown')
            
            logger.info("Processing intercepted request", url=url, profile=profile)
            
            # Use RealtimeProcessor to process and send
            sent_count = self.processor.process_and_send(url, response_data, profile)
            
            self.processed_requests += 1
            self.sent_alerts += sent_count
            
            if sent_count > 0:
                print(f"📤 Sent {sent_count} alerts from {url}")
            
        except Exception as e:
            logger.error("Failed to process intercepted request", url=url, error=str(e))
    
    async def run_surebet_test(self):
        """Run Surebet interception test."""
        print("🎯 Starting Surebet pipeline test...")
        
        if not self.setup_playwright():
            return False
        
        try:
            # Open Surebet tab
            tab_info = await self.capture.open_tab(
                url="https://es.surebet.com/valuebets",
                profile="ev-surebets"
            )
            
            if not tab_info:
                logger.error("Failed to open Surebet tab")
                return False
            
            print(f"✅ Opened Surebet tab: {tab_info['url']}")
            print("🔄 Intercepting requests... (navigate manually to see alerts)")
            print("📊 Press Ctrl+C to stop and see stats")
            
            # Start capture
            await self.capture.start_capture()
            
            # Keep running and show periodic stats
            start_time = time.time()
            while True:
                await asyncio.sleep(10)
                
                elapsed = time.time() - start_time
                stats = self.processor.get_stats()
                
                print(f"\n📈 Stats after {elapsed:.0f}s:")
                print(f"  Requests processed: {self.processed_requests}")
                print(f"  Alerts sent: {self.sent_alerts}")
                print(f"  Success rate: {stats['success_rate']}%")
                print(f"  Errors: {stats['error_count']}")
                
        except KeyboardInterrupt:
            print("\n⏹️ Stopping test...")
            
        finally:
            if self.capture:
                await self.capture.stop_capture()
            if self.playwright_manager:
                await self.playwright_manager.close()
        
        return True
    
    async def run_betburger_test(self):
        """Run Betburger interception test."""
        print("🎯 Starting Betburger pipeline test...")
        
        if not self.setup_playwright():
            return False
        
        try:
            # Open Betburger tab
            tab_info = await self.capture.open_tab(
                url="https://betburger.com/es/arbs",
                profile="bet365_valuebets"
            )
            
            if not tab_info:
                logger.error("Failed to open Betburger tab")
                return False
            
            print(f"✅ Opened Betburger tab: {tab_info['url']}")
            print("🔄 Intercepting requests... (navigate manually to see alerts)")
            print("📊 Press Ctrl+C to stop and see stats")
            
            # Start capture
            await self.capture.start_capture()
            
            # Keep running and show periodic stats
            start_time = time.time()
            while True:
                await asyncio.sleep(10)
                
                elapsed = time.time() - start_time
                stats = self.processor.get_stats()
                
                print(f"\n📈 Stats after {elapsed:.0f}s:")
                print(f"  Requests processed: {self.processed_requests}")
                print(f"  Alerts sent: {self.sent_alerts}")
                print(f"  Success rate: {stats['success_rate']}%")
                print(f"  Errors: {stats['error_count']}")
                
        except KeyboardInterrupt:
            print("\n⏹️ Stopping test...")
            
        finally:
            if self.capture:
                await self.capture.stop_capture()
            if self.playwright_manager:
                await self.playwright_manager.close()
        
        return True


async def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test realtime pipeline with intercepted requests")
    parser.add_argument("--test-channels", action="store_true", help="Only test channel connectivity")
    parser.add_argument("--platform", choices=["surebet", "betburger"], default="surebet", help="Platform to test")
    args = parser.parse_args()
    
    # Check token
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "CAMBIAR_TOKEN":
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not set or still default in .env")
        return 1
    
    test = RealtimePipelineTest()
    
    if args.test_channels:
        success = await test.test_channel_connectivity()
        return 0 if success else 1
    
    print("🚀 Starting realtime pipeline test...")
    print(f"📱 Platform: {args.platform}")
    print(f"🔑 Token configured: {token[:10]}...")
    
    if args.platform == "surebet":
        success = await test.run_surebet_test()
    else:
        success = await test.run_betburger_test()
    
    # Final stats
    stats = test.processor.get_stats()
    print(f"\n📊 Final Stats:")
    print(f"  Total requests: {test.processed_requests}")
    print(f"  Total alerts sent: {test.sent_alerts}")
    print(f"  Success rate: {stats['success_rate']}%")
    print(f"  Errors: {stats['error_count']}")
    
    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except KeyboardInterrupt:
        exit_code = 130
    sys.exit(exit_code)
