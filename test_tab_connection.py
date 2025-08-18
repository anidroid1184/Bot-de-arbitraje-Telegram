"""
Test script for Tab 1.3 - Script base de acceso a pestañas abiertas
Tests connection to Firefox and lists all open tabs.
"""
import sys
import os
import time

# Ensure we can import as package 'src' when running directly
try:
    _this_file = __file__  # may fail in some invocation contexts
    CURRENT_DIR = os.path.dirname(os.path.abspath(_this_file))
except Exception as e:
    # Fall back to current working directory
    print(e)
    CURRENT_DIR = os.getcwd()
    
PROJECT_ROOT = os.path.abspath(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config.settings import ConfigManager, BotConfig
from src.browser.tab_manager import TabManager
from src.utils.logger import setup_logger
from selenium.webdriver.support.ui import WebDriverWait

def test_tab_connection():
    """Test connecting to existing Firefox tabs and listing them"""
    
    # Setup logging
    logger = setup_logger(log_level="INFO", service_name="tab_test")
    
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
