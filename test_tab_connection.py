"""
Test script for Tab 1.3 - Script base de acceso a pestañas abiertas
Tests connection to Firefox and lists all open tabs.
"""
import sys
import os
import time
from pathlib import Path

# Ensure we can import as package 'src' when running directly
base_dir: Path
try:
    # Preferred: directory of this script
    base_dir = Path(__file__).resolve(strict=False).parent
except Exception as e1:
    try:
        # Fallback: directory of the invoked script path
        base_dir = Path(sys.argv[0]).resolve(strict=False).parent
    except Exception as e2:
        # Last resort: resolve current directory token without calling os.getcwd()
        # (Path('.').resolve() does not raise if CWD is temporarily invalid in some shells)
        base_dir = Path('.').resolve()

PROJECT_ROOT = str(base_dir)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.settings import ConfigManager, BotConfig
from src.browser.tab_manager import TabManager
from src.utils.logger import setup_logger
from src.utils.telegram_notifier import TelegramNotifier
from selenium.webdriver.support.ui import WebDriverWait

def _detect_robot_check(tab_manager: TabManager) -> str:
    """Return a short reason string if a human/robot check is detected, else ''.
    Heuristics only, non-invasive.
    """
    try:
        d = tab_manager.driver
        page_text = (d.find_element("tag name", "body").text or "").lower()
        title = (d.title or "").lower()
        # Common markers
        markers = [
            "i'm not a robot", "im not a robot", "no soy un robot", "captcha",
            "verify you are human", "are you a human", "hcaptcha", "recaptcha",
            "please verify", "solve the challenge"
        ]
        if any(m in page_text or m in title for m in markers):
            return "Text markers of CAPTCHA/verification detected"
        # Look for common recaptcha/hcaptcha containers/iframes
        try:
            iframes = d.find_elements("tag name", "iframe")
            for f in iframes:
                src = (f.get_attribute("src") or "").lower()
                if "recaptcha" in src or "hcaptcha" in src:
                    return "reCAPTCHA/hCaptcha iframe detected"
        except Exception:
            pass
        # hCaptcha/reCAPTCHA widgets as divs
        try:
            widgets = d.find_elements("css selector", "div.g-recaptcha, div.hcaptcha, div#captcha, form#captcha")
            if widgets:
                return "CAPTCHA widget container detected"
        except Exception:
            pass
    except Exception:
        return ""
    return ""

def test_tab_connection():
    """Test connecting to existing Firefox tabs and listing them"""
    
    # Setup logging
    logger = setup_logger(log_level="INFO", service_name="tab_test")
    notifier = TelegramNotifier()
    
    logger.info("Starting tab connection test")
    
    # Load configuration
    config = BotConfig()
    tab_manager = TabManager(config)
    
    try:
        # Step 1: Connect to existing browser
        logger.info("Attempting to connect to existing Firefox browser...")
        if not tab_manager.connect_to_existing_browser():
            logger.error("Failed to connect to Firefox browser")
            logger.info("Make sure Firefox is running with: firefox --remote-debugging-port=9222")
            return False
        
        # Optional pre-wait: allow user to interact with the browser (e.g., click CONNECT on VPN UI)
        pre_wait_seconds = int(os.environ.get("PRE_SEED_WAIT_SECONDS", "0"))
        if pre_wait_seconds > 0:
            logger.info(f"Pre-waiting {pre_wait_seconds}s before opening tabs (manual VPN connect window)")
            time.sleep(pre_wait_seconds)

        # Seed relevant tabs by default (Betburger and Surebet) for remote sessions (e.g., Docker Selenium)
        # Controlled via SEED_TEST_TABS env var; default: true
        if os.environ.get("SEED_TEST_TABS", "true").lower() in ("1", "true", "yes"): 
            try:
                urls_to_open = [
                    os.environ.get("TEST_BETBURGER_URL", "https://betburger.com"),
                    os.environ.get("TEST_SUREBET_URL", "https://es.surebet.com"),
                ]
                for idx, url in enumerate(urls_to_open):
                    if idx == 0:
                        # Use current tab for first URL
                        tab_manager.driver.get(url)
                    else:
                        # Open subsequent URLs in new tabs
                        tab_manager.driver.execute_script(f"window.open('{url}', '_blank');")
                        # Switch to the newest tab
                        tab_manager.driver.switch_to.window(tab_manager.driver.window_handles[-1])

                    # Wait for the page to load
                    try:
                        WebDriverWait(tab_manager.driver, 30).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
                    except Exception:
                        logger.warning("Timeout waiting for seeded tab to load; continuing anyway", url=url)
                logger.info("Seeded test tabs for Betburger and Surebet")

                # Optional wait to allow manual debugging before discovery
                wait_seconds = int(os.environ.get("SEED_WAIT_SECONDS", "300"))
                if wait_seconds > 0:
                    logger.info(f"Waiting {wait_seconds}s before discovering tabs (manual debug window)")
                    time.sleep(wait_seconds)
            except Exception as se:
                logger.warning("Could not seed test tabs automatically", error=str(se))
        
        # Step 2: Discover all tabs
        logger.info("Discovering open tabs...")
        tabs = tab_manager.discover_tabs()
        
        if not tabs:
            logger.warning("No relevant tabs found (Betburger or Surebet)")
            logger.info("Please open tabs for betburger.com and/or surebet.com")
            return False
        
        # Step 3: Display discovered tabs
        logger.info(f"Successfully discovered {len(tabs)} relevant tabs:")
        for tab_key, handle in tabs.items():
            logger.info(f"  - {tab_key}: {handle}")
            
            # Test switching to each tab
            if tab_manager.switch_to_tab(tab_key):
                # Get basic page info
                try:
                    title = tab_manager.driver.title
                    url = tab_manager.driver.current_url
                    logger.info(f"    Title: {title}")
                    logger.info(f"    URL: {url}")

                    # Heuristic detection of robot checks / captcha
                    reason = _detect_robot_check(tab_manager)
                    if reason:
                        msg = (
                            "⚠️ Verificación humana detectada (CAPTCHA/anti-bot)\n"
                            f"Motivo: {reason}\n"
                            f"Título: {title}\n"
                            f"URL: {url}"
                        )
                        logger.warning("Robot-check detected; notifying support", reason=reason)
                        notifier.send_text(msg)
                except Exception as e:
                    logger.error(f"    Error getting tab info: {str(e)}")
        
        logger.info("Tab connection test completed successfully!")
        return True
        
    except Exception as e:
        logger.error("Unexpected error during tab connection test", error=str(e))
        return False
        
    finally:
        # Clean up
        tab_manager.close()

if __name__ == "__main__":
    success = test_tab_connection()
    if success:
        print("\n✅ Test PASSED: Successfully connected to Firefox and listed tabs")
        sys.exit(0)
    else:
        print("\n❌ Test FAILED: Could not connect to Firefox or find relevant tabs")
        print("Next steps:")
        print("1. Start Firefox with: firefox --remote-debugging-port=9222")
        print("2. Open tabs for betburger.com and surebet.com")
        print("3. Run this test again")
        sys.exit(1)
