"""
Test script for Tab 1.3 - Script base de acceso a pestañas abiertas
Tests connection to Firefox and lists all open tabs.
"""
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.config.settings import ConfigManager, BotConfig
from src.browser.tab_manager import TabManager
from src.utils.logger import setup_logger

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
        
        # Optional: seed relevant tabs for a fresh Selenium session (e.g., Docker container)
        # This avoids manual steps and makes the test deterministic in CI/containers
        if os.environ.get("SEED_TEST_TABS", "false").lower() in ("1", "true", "yes"): 
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
                logger.info("Seeded test tabs for Betburger and Surebet")
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
