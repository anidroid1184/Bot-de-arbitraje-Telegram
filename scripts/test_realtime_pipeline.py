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
import json
import re
from pathlib import Path
import inspect

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

# Optional: components for dependency-injected constructor variants
try:
    from config.channel_mapper import ChannelMapper
    print("✅ Successfully imported ChannelMapper")
except ImportError as e:
    print(f"❌ Failed to import ChannelMapper: {e}")
    ChannelMapper = None

try:
    from notifications.telegram_sender import TelegramSender
    print("✅ Successfully imported TelegramSender")
except ImportError as e:
    print(f"❌ Failed to import TelegramSender: {e}")
    TelegramSender = None

# Load environment
ENV_PATH = Path(__file__).parent.parent / ".env"
# IMPORTANT: do not override shell exports (like BOT_HEADLESS/BROWSER) with .env
load_dotenv(ENV_PATH, override=False)

logger = structlog.get_logger(__name__)


class RealtimePipelineTest:
    """Test del pipeline completo con requests reales."""
    
    def __init__(self):
        """Initialize test."""
        if RealtimeProcessor is None:
            print("❌ RealtimeProcessor no disponible - creando mock")
            self.processor = None
        else:
            # Create processor with backward-compatible constructor handling
            self.processor = self._create_processor_compat()
        
        self.playwright_manager = None
        self.capture = None
        self.processed_requests = 0
        self.sent_alerts = 0
        # Tabs configuration (can be overridden by CLI)
        def _int_env(*keys: str, default: int = 1) -> int:
            for k in keys:
                v = os.getenv(k)
                if v is not None and str(v).strip() != "":
                    try:
                        return int(str(v).strip())
                    except Exception:
                        pass
            return default
        # Support both the new and the .env.example names
        self.tabs_sb = _int_env("TABS_SB", "SUREBET_TABS", default=1)
        self.tabs_bb = _int_env("TABS_BB", "BETBURGER_TABS", default=1)

    def _create_processor_compat(self):
        """Try multiple constructor signatures for RealtimeProcessor for cross-version compatibility."""
        # 1) Try no-args
        try:
            return RealtimeProcessor()
        except TypeError as e:
            print(f"ℹ️ RealtimeProcessor() failed: {e}")
        except Exception as e:
            print(f"ℹ️ RealtimeProcessor() unexpected error: {e}")

        # 2) Try config_path kw
        try:
            return RealtimeProcessor(config_path=None)
        except TypeError as e:
            print(f"ℹ️ RealtimeProcessor(config_path=None) failed: {e}")
        except Exception as e:
            print(f"ℹ️ RealtimeProcessor(config_path=None) unexpected error: {e}")

        # 3) Try dependency-injected positional args
        try:
            cm = ChannelMapper(None) if ChannelMapper else None
            # Some server versions require a positional bot_token
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            ts = TelegramSender(token) if TelegramSender else None
            # 3.a) Server variant that expects ONLY telegram_sender positional
            if ts is not None:
                try:
                    return RealtimeProcessor(ts)
                except TypeError as e:
                    print(f"ℹ️ RealtimeProcessor(ts) failed: {e}")
            # 3.b) Variant expecting (channel_mapper, telegram_sender)
            if cm is not None and ts is not None:
                return RealtimeProcessor(cm, ts)
        except TypeError as e:
            print(f"ℹ️ RealtimeProcessor(cm, ts) failed: {e}")
        except Exception as e:
            print(f"ℹ️ RealtimeProcessor(cm, ts) unexpected error: {e}")

        # 4) Try dependency-injected keyword args
        try:
            cm = ChannelMapper(None) if ChannelMapper else None
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            ts = TelegramSender(token) if TelegramSender else None
            # 4.a) Keyword with only telegram_sender
            if ts is not None:
                try:
                    return RealtimeProcessor(telegram_sender=ts)
                except TypeError as e:
                    print(f"ℹ️ RealtimeProcessor(telegram_sender=ts) failed: {e}")
            # 4.b) Keyword with both
            if cm is not None and ts is not None:
                return RealtimeProcessor(channel_mapper=cm, telegram_sender=ts)
        except TypeError as e:
            print(f"ℹ️ RealtimeProcessor(channel_mapper=cm, telegram_sender=ts) failed: {e}")
        except Exception as e:
            print(f"ℹ️ RealtimeProcessor(channel_mapper=cm, telegram_sender=ts) unexpected error: {e}")

        raise RuntimeError("Could not instantiate RealtimeProcessor with known signatures. Please ensure versions match.")
        
    async def test_channel_connectivity(self):
        """Test conectividad a todos los canales configurados."""
        print("🧪 Testing channel connectivity...")
        
        if self.processor is None:
            print("❌ No se puede probar conectividad - RealtimeProcessor no disponible")
            return {"error": "RealtimeProcessor not available"}
        
        # If processor provides the helper, use it
        if hasattr(self.processor, "test_channel_connectivity"):
            results = await self.processor.test_channel_connectivity()
        else:
            # Fallback: run connectivity test here using mapper + telegram sender
            if ChannelMapper is None or TelegramSender is None:
                print("❌ Faltan dependencias para test de conectividad (ChannelMapper/TelegramSender)")
                return False

            # Load config
            mapper = ChannelMapper(None)

            # Collect channels from config (bb, sb, support)
            all_channels = []
            for profile_name, cfg in (mapper.config.get('betburger_profiles', {}) or {}).items():
                if cfg and cfg.get('channel_id'):
                    all_channels.append((f"betburger.{profile_name}", cfg['channel_id']))
            for profile_name, cfg in (mapper.config.get('surebet_profiles', {}) or {}).items():
                if cfg and cfg.get('channel_id'):
                    all_channels.append((f"surebet.{profile_name}", cfg['channel_id']))
            for name, cfg in (mapper.config.get('support', {}) or {}).items():
                if cfg and cfg.get('channel_id'):
                    all_channels.append((f"support.{name}", cfg['channel_id']))

            # Sender with token from env
            token = os.getenv("TELEGRAM_BOT_TOKEN")
            sender = TelegramSender(token)

            results = {}
            for channel_name, channel_id in all_channels:
                message = f"🧪 **Test de conectividad**\n\nCanal: {channel_name}\nID: {channel_id}\n⏱️ {time.strftime('%H:%M:%S')}"
                ok = False
                # Try async method if present and coroutine
                if hasattr(sender, "send_test_message_async"):
                    try:
                        method = getattr(sender, "send_test_message_async")
                        if inspect.iscoroutinefunction(method):
                            ok = await method(channel_id, message)
                        else:
                            # In rare cases it's a normal func; run in thread
                            ok = await asyncio.to_thread(method, channel_id, message)
                    except AttributeError:
                        ok = False
                    except Exception as e:
                        logger.error("Channel test failed", channel=channel_name, error=str(e))
                        ok = False
                # Fallback to sync method
                if not ok and hasattr(sender, "send_test_message"):
                    try:
                        ok = await asyncio.to_thread(sender.send_test_message, channel_id, message)
                    except Exception as e:
                        logger.error("Channel test failed", channel=channel_name, error=str(e))
                        ok = False
                results[channel_name] = ok
        
        print("\n📊 Channel Test Results:")
        success_count = 0
        for channel_name, success in results.items():
            status = "✅ OK" if success else "❌ FAILED"
            print(f"  {channel_name:30s} -> {status}")
            if success:
                success_count += 1
        
        print(f"\n📈 Summary: {success_count}/{len(results)} channels OK")
        return success_count == len(results)
    
    async def setup_playwright(self):
        """Setup Playwright manager and capture in a background thread if needed."""
        try:
            # Create config object similar to smoke test
            class Config:
                def __init__(self):
                    self.bot = self
                    # Respect explicit headless setting; default to false for local debug
                    self.headless = os.getenv("BOT_HEADLESS", "false").lower() in ("1", "true", "yes", "on")
                    # Prefer chromium by default in servers
                    self.browser = os.getenv("BROWSER", os.getenv("PLAYWRIGHT_ENGINE", "chromium"))

            config = Config()
            # If no DISPLAY (common on Linux servers), prefer headless unless user explicitly asked for headed
            # Windows/Mac don't use DISPLAY the same way, so don't override there.
            is_linux = sys.platform.startswith("linux")
            display_missing = not os.environ.get("DISPLAY")
            user_explicit_headed = os.getenv("BOT_HEADLESS", "").strip() != "" and os.getenv("BOT_HEADLESS").lower() in ("0", "false", "no", "off")
            if is_linux and display_missing and not config.headless and user_explicit_headed:
                # Warn but allow headed so the user can run under Xvfb or X11 forwarding
                print("⚠️ DISPLAY not set on Linux but BOT_HEADLESS explicitly false. Attempting headed mode. Make sure to run under X11 forwarding or xvfb-run.")
            elif is_linux and display_missing:
                # Safe default: headless on Linux servers when DISPLAY is absent and user didn't force headed
                if not config.headless:
                    os.environ["BOT_HEADLESS"] = "true"
                    config.headless = True
            # Normalize engine
            if config.browser not in ("chromium", "webkit", "firefox"):
                config.browser = "chromium"
            print(f"DEBUG: Resolved browser engine: {config.browser}")
            print(f"DEBUG: Resolved headless: {config.headless}")
            print(f"DEBUG: Resolved browser engine: {config.browser}")
            print(f"DEBUG: Resolved headless: {config.headless}")

            def _setup_sync():
                # If PlaywrightManager is available, use it; else fall back to a minimal inline manager
                if PlaywrightManager is not None:
                    pm = PlaywrightManager(config)
                    # Launch browser and obtain a BrowserContext
                    pm.launch(engine=config.browser)
                    if pm.context is None:
                        raise RuntimeError("Playwright context not initialized after launch")
                    # PlaywrightCapture expects a BrowserContext or Page
                    if PlaywrightCapture is None:
                        raise RuntimeError("PlaywrightCapture module is not available")
                    cap = PlaywrightCapture(pm.context)
                    return pm, cap
                else:
                    # Minimal inline manager using sync_playwright
                    from playwright.sync_api import sync_playwright  # type: ignore
                    import types

                    pl = sync_playwright().start()

                    def _ua() -> str:
                        return (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                        )

                    browser = None
                    context = None
                    if config.browser == "firefox":
                        browser = pl.firefox.launch(headless=config.headless)
                        context = browser.new_context(user_agent=_ua())
                    elif config.browser == "webkit":
                        browser = pl.webkit.launch(headless=config.headless)
                        context = browser.new_context(user_agent=_ua())
                    else:
                        try:
                            browser = pl.chromium.launch(
                                headless=config.headless,
                                args=["--no-sandbox", "--disable-dev-shm-usage"],
                            )
                        except Exception as e:
                            raise RuntimeError(f"Chromium launch failed: {e}")
                        context = browser.new_context(user_agent=_ua())

                    # Apply small defaults
                    try:
                        context.set_default_navigation_timeout(10000)
                        context.set_default_timeout(10000)
                    except Exception:
                        pass

                    # Build a tiny manager-like object with close()
                    pm = types.SimpleNamespace()
                    pm.browser = browser
                    pm.context = context

                    def _close_inline():
                        try:
                            if context:
                                context.close()
                        except Exception:
                            pass
                        try:
                            if browser:
                                browser.close()
                        except Exception:
                            pass
                        try:
                            if pl:
                                pl.stop()
                        except Exception:
                            pass

                    pm.close = _close_inline

                    if PlaywrightCapture is None:
                        raise RuntimeError("PlaywrightCapture module is not available")
                    cap = PlaywrightCapture(context)
                    return pm, cap

            self.playwright_manager, self.capture = await asyncio.to_thread(_setup_sync)

            logger.info("Playwright setup completed")
            return True

        except Exception as e:
            logger.error("Failed to setup Playwright", error=str(e))
            return False
            
        return True

    def process_intercepted_request(self, url: str, response_data: dict, **kwargs):
        """Process one intercepted record via RealtimeProcessor and track counters."""
        try:
            self.processed_requests += 1
            profile = kwargs.get("profile", "unknown")
            if not self.processor:
                return 0
            # Unified entrypoint in processor
            if hasattr(self.processor, "process_and_send"):
                sent = self.processor.process_and_send(url, response_data, profile)
            else:
                # Backward compatibility: try generic process
                sent = 0
                if hasattr(self.processor, "process"):
                    try:
                        alert = self.processor.process(url, response_data, profile)
                        if alert and hasattr(self.processor, "send"):
                            self.processor.send(alert)
                            sent = 1
                    except Exception:
                        sent = 0
            if sent:
                self.sent_alerts += int(sent)
            return sent
        except Exception as e:
            logger.error("process_intercepted_failed", url=url, error=str(e))
            return 0

    async def _consume_capture_loop(self, source: str) -> None:
        """Continuously flush PlaywrightCapture buffer and forward to processor.

        Polls every CAPTURE_POLL_INTERVAL (default 0.3s). Filters Betburger to pro_search.
        """
        if not self.capture:
            return
        poll_interval = float(os.getenv("CAPTURE_POLL_INTERVAL", "0.3"))
        pro_search = re.compile(r"/api/(?:v\\d+/)?pro_search", re.IGNORECASE)
        try:
            while True:
                await asyncio.sleep(poll_interval)
                try:
                    batch = await asyncio.to_thread(self.capture.flush)
                except Exception:
                    batch = []
                if not batch:
                    continue
                for rec in batch:
                    try:
                        if not isinstance(rec, dict):
                            continue
                        url = rec.get("url") or ""
                        rtype = rec.get("type")
                        if not url or rtype != "response":
                            continue
                        if source == "betburger" and not pro_search.search(url):
                            continue
                        payload = rec.get("json") or rec.get("text")
                        if not payload:
                            continue
                        if isinstance(payload, str):
                            try:
                                payload = json.loads(payload)
                            except Exception:
                                continue
                        self.process_intercepted_request(url, payload, profile="unknown")
                    except Exception as e:
                        logger.warning("capture_consume_error", error=str(e))
        except asyncio.CancelledError:
            return
    
    async def run_betburger_test(self):
        """Run Betburger interception test."""
        print("🎯 Starting Betburger pipeline test...")
        
        if not await self.setup_playwright():
            return False
        
        try:
            # Open Betburger page
            ctx = self.playwright_manager.context
            if ctx is None:
                logger.error("Browser context not available")
                return False
            url = "https://betburger.com/es/arbs"
            pages = []
            if PlaywrightManager is not None and hasattr(self.playwright_manager, "open_tabs"):
                pages = await asyncio.to_thread(self.playwright_manager.open_tabs, url, max(1, int(self.tabs_bb)))
            else:
                for _ in range(max(1, int(self.tabs_bb))):
                    p = await asyncio.to_thread(ctx.new_page)
                    await asyncio.to_thread(p.goto, url, timeout=8000, wait_until="domcontentloaded")
                    pages.append(p)
            if pages:
                print(f"✅ Opened {len(pages)} Betburger tab(s). First URL: {pages[0].url}")
            else:
                print("⚠️ No Betburger tabs opened (unexpected)")
            print("🔄 Intercepting requests... (navigate manually to see alerts)")
            print("📊 Press Ctrl+C to stop and see stats")
            
            # Start capture and consumer loop
            await asyncio.to_thread(self.capture.start)
            consumer = asyncio.create_task(self._consume_capture_loop("betburger"))
            
            # Keep running and show periodic stats
            start_time = time.time()
            while True:
                await asyncio.sleep(10)
                
                elapsed = time.time() - start_time
                stats = {"success_rate": 0, "error_count": 0}
                if hasattr(self.processor, "get_stats"):
                    try:
                        stats = self.processor.get_stats()
                    except Exception:
                        pass
                
                print(f"\n📈 Stats after {elapsed:.0f}s:")
                print(f"  Requests processed: {self.processed_requests}")
                print(f"  Alerts sent: {self.sent_alerts}")
                print(f"  Success rate: {stats['success_rate']}%")
                print(f"  Errors: {stats['error_count']}")
                
        except KeyboardInterrupt:
            print("\n⏹️ Stopping test...")
            
        finally:
            if self.capture and hasattr(self.capture, "stop"):
                try:
                    if inspect.iscoroutinefunction(self.capture.stop):
                        await self.capture.stop()
                    else:
                        await asyncio.to_thread(self.capture.stop)
                except Exception:
                    pass
            try:
                if 'consumer' in locals():
                    consumer.cancel()
            except Exception:
                pass
            if self.playwright_manager and hasattr(self.playwright_manager, "close"):
                if inspect.iscoroutinefunction(self.playwright_manager.close):
                    await self.playwright_manager.close()
                else:
                    await asyncio.to_thread(self.playwright_manager.close)
        
        return True


async def main():
    """Main test function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test realtime pipeline with intercepted requests")
    parser.add_argument("--test-channels", action="store_true", help="Only test channel connectivity")
    parser.add_argument("--platform", choices=["surebet", "betburger"], default="surebet", help="Platform to test")
    parser.add_argument("--tabs-bb", type=int, default=None, help="Number of Betburger tabs to open (default from TABS_BB or 1)")
    parser.add_argument("--tabs-sb", type=int, default=None, help="Number of Surebet tabs to open (default from TABS_SB or 1)")
    args = parser.parse_args()
    
    # Check token
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "CAMBIAR_TOKEN":
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not set or still default in .env")
        return 1
    
    test = RealtimePipelineTest()
    # Override tabs from CLI if provided
    if args.tabs_bb is not None:
        test.tabs_bb = max(1, int(args.tabs_bb))
    if args.tabs_sb is not None:
        test.tabs_sb = max(1, int(args.tabs_sb))
    
    if args.test_channels:
        success = await test.test_channel_connectivity()
        return 0 if success else 1
    
    print("🚀 Starting realtime pipeline test...")
    print(f"📱 Platform: {args.platform}")
    print(f"🔑 Token configured: {token[:10]}...")
    # Show resolved tabs for transparency
    try:
        print(f"🧩 Resolved tabs -> Surebet: {test.tabs_sb}, Betburger: {test.tabs_bb}")
    except Exception:
        pass
    
    if args.platform == "surebet":
        success = await test.run_surebet_test()
    else:
        success = await test.run_betburger_test()
    
    # Final stats
    stats = {"success_rate": 0, "error_count": 0}
    if test.processor and hasattr(test.processor, "get_stats"):
        try:
            stats = test.processor.get_stats()
        except Exception:
            pass
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
