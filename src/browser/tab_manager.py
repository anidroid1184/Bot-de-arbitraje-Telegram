"""
Tab Manager for connecting to existing Firefox browser sessions.
Handles multiple tabs and profiles for Surebet and Betburger.
"""
import time
import os
from typing import List, Dict, Optional
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

from ..utils.logger import get_module_logger
from .session_store import load_session, attach_to_session, save_session  # type: ignore
from ..config.settings import BotConfig

logger = get_module_logger("tab_manager")

class TabManager:
    """Manages connection to existing Firefox browser tabs"""
    
    def __init__(self, config: BotConfig):
        self.config = config
        self.driver: Optional[webdriver.Firefox] = None
        self.tabs: Dict[str, str] = {}  # tab_name -> window_handle
        
    def connect_to_existing_browser(self) -> bool:
        """
        Connect to an existing Firefox browser session.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Firefox options for connecting to existing session
            options = Options()
            if self.config.headless_mode:
                options.add_argument("--headless")

            # Optional: run entire session in Private Browsing (Incognito)
            # Enabled only when BROWSER_PRIVATE_MODE is truthy (e.g., in VPN profile)
            if os.environ.get("BROWSER_PRIVATE_MODE", "false").lower() in ("1", "true", "yes", "on"): 
                # -private makes all windows private; also set the pref to autostart private mode
                options.add_argument("-private")
                options.set_preference("browser.privatebrowsing.autostart", True)

            # Apply optional proxy configuration via Firefox preferences
            # We use prefs instead of Selenium Proxy object for better compatibility with Remote sessions.
            if getattr(self.config, "proxy_type", None) and getattr(self.config, "proxy_host", None) and getattr(self.config, "proxy_port", None):
                ptype = (self.config.proxy_type or "").lower()
                host = self.config.proxy_host
                port = int(self.config.proxy_port)
                # 1 = Manual proxy config
                options.set_preference("network.proxy.type", 1)
                if ptype == "http":
                    options.set_preference("network.proxy.http", host)
                    options.set_preference("network.proxy.http_port", port)
                    options.set_preference("network.proxy.ssl", host)
                    options.set_preference("network.proxy.ssl_port", port)
                    # Also set for DNS over proxy if desired
                    options.set_preference("network.proxy.socks_remote_dns", True)
                elif ptype in ("socks", "socks5"):
                    options.set_preference("network.proxy.socks", host)
                    options.set_preference("network.proxy.socks_port", port)
                    options.set_preference("network.proxy.socks_version", 5)
                    options.set_preference("network.proxy.socks_remote_dns", True)
                    # Optional SOCKS auth
                    if getattr(self.config, "proxy_username", None):
                        options.set_preference("network.proxy.socks_username", self.config.proxy_username)
                    if getattr(self.config, "proxy_password", None):
                        options.set_preference("network.proxy.socks_password", self.config.proxy_password)
                else:
                    logger.warning("Unsupported proxy type provided; skipping proxy configuration", proxy_type=self.config.proxy_type)

            # If a remote WebDriver URL is provided, try to ATTACH to existing session first
            remote_url = os.environ.get("WEBDRIVER_REMOTE_URL")
            if remote_url:
                try:
                    # Optional session file path
                    session_file = os.environ.get("WEBDRIVER_SESSION_FILE", str((Path.cwd() / "logs" / "session" / "betburger.json")))
                    sess = load_session(session_file)
                    if sess:
                        exec_url, session_id = sess
                        if exec_url and session_id:
                            driver = attach_to_session(exec_url, session_id, options)
                            if driver is not None:
                                self.driver = driver  # type: ignore[assignment]
                                logger.info("Reattached to existing Remote WebDriver session", executor_url=exec_url, session_id=session_id)
                                return True

                    # No session to attach or attach failed -> create new remote session
                    # Try Selenium Wire Remote first if available
                    try:
                        from seleniumwire import webdriver as wire_webdriver  # type: ignore
                        self.driver = wire_webdriver.Remote(command_executor=remote_url, options=options)
                        logger.info("Connected (Selenium Wire) to remote Firefox session", remote_url=remote_url)
                    except Exception:
                        self.driver = webdriver.Remote(command_executor=remote_url, options=options)
                        logger.info("Connected to remote Selenium Firefox session (no wire)", remote_url=remote_url)
                    # Persist session for reuse
                    try:
                        save_session(Path(session_file), self.driver, remote_url)
                    except Exception:
                        pass
                    return True
                except Exception as re:
                    # Fall back to local Firefox if remote is not reachable
                    logger.warning(
                        "Remote WebDriver unavailable; falling back to local Firefox",
                        remote_url=remote_url,
                        error=str(re),
                    )
            
            # Connect to existing local Firefox instance
            # Only enable remote debugging if explicitly requested (debugging)
            if os.environ.get("BROWSER_DEBUG", "false").lower() in ("1", "true", "yes", "on"):
                options.add_argument("--remote-debugging-port=9222")

            # Allow overriding Firefox binary location (useful in WSL where Firefox Snap isn't supported)
            firefox_binary = os.environ.get("FIREFOX_BINARY")
            if firefox_binary:
                try:
                    options.binary_location = firefox_binary
                    logger.info("Using custom Firefox binary", binary=firefox_binary)
                except Exception as be:
                    logger.warning("Failed to set custom Firefox binary; falling back to default", error=str(be))
            
            # Prefer Selenium Wire locally if available, to enable request capture
            try:
                from seleniumwire import webdriver as wire_webdriver  # type: ignore
                seleniumwire_options = {
                    # Do not store large bodies; we only need request bodies
                    'request_storage': 'memory',
                    'verify_ssl': True,
                    # Optionally ignore some hosts; keep empty for now to capture Betburger/Surebet
                    # 'exclude_hosts': ['*.google-analytics.com']
                }
                self.driver = wire_webdriver.Firefox(options=options, seleniumwire_options=seleniumwire_options)
                logger.info("Connected to local Firefox (Selenium Wire enabled)")
            except Exception as we:
                logger.warning("Selenium Wire not available; continuing without network capture", error=str(we))
                self.driver = webdriver.Firefox(options=options)
                logger.info("Connected to local Firefox browser session (no wire)")
            return True
            
        except WebDriverException as e:
            logger.error("Failed to connect to Firefox browser", error=str(e))
            return False
    
    def discover_tabs(self) -> Dict[str, str]:
        """
        Discover and catalog all open tabs.
        
        Returns:
            Dict mapping tab descriptions to window handles
        """
        if not self.driver:
            logger.error("No browser connection available")
            return {}
        
        discovered_tabs = {}
        
        try:
            # Get all window handles
            window_handles = self.driver.window_handles
            logger.info(f"Found {len(window_handles)} open tabs")

            for handle in window_handles:
                try:
                    self.driver.switch_to.window(handle)

                    # Wait for page to load (be tolerant to pages that never reach 'complete')
                    try:
                        WebDriverWait(self.driver, self.config.browser_timeout).until(
                            lambda d: d.execute_script("return document.readyState") == "complete"
                        )
                    except TimeoutException:
                        logger.warning("Timeout waiting for tab to load; proceeding anyway")

                    title = self.driver.title
                    # current_url access may fail on some blocked pages; guard it
                    try:
                        url = self.driver.current_url
                    except WebDriverException as ue:
                        logger.warning("Could not read current_url for a tab", error=str(ue))
                        url = ""

                    # Categorize tabs based on URL
                    if "betburger.com" in url:
                        tab_key = f"betburger_{len([k for k in discovered_tabs.keys() if k.startswith('betburger')])}"
                        discovered_tabs[tab_key] = handle
                        logger.info(f"Found Betburger tab: {title}", tab_key=tab_key, url=url)

                    elif "surebet.com" in url:
                        tab_key = f"surebet_{len([k for k in discovered_tabs.keys() if k.startswith('surebet')])}"
                        discovered_tabs[tab_key] = handle
                        logger.info(f"Found Surebet tab: {title}", tab_key=tab_key, url=url)

                    else:
                        logger.debug(f"Ignoring unrelated tab: {title}", url=url)

                except Exception as per_tab_err:
                    logger.warning("Skipping problematic tab during discovery", error=str(per_tab_err))

            self.tabs = discovered_tabs
            return discovered_tabs

        except Exception as e:
            logger.error("Error discovering tabs (outer)", error=str(e))
            return {}
    
    def switch_to_tab(self, tab_key: str) -> bool:
        """
        Switch to a specific tab by its key.
        
        Args:
            tab_key: Key identifying the tab
            
        Returns:
            bool: True if switch successful, False otherwise
        """
        if tab_key not in self.tabs:
            logger.error(f"Tab not found: {tab_key}")
            return False
        
        try:
            handle = self.tabs[tab_key]
            self.driver.switch_to.window(handle)
            logger.debug(f"Switched to tab: {tab_key}")
            return True
            
        except WebDriverException as e:
            logger.error(f"Failed to switch to tab: {tab_key}", error=str(e))
            return False
    
    def get_page_source(self, tab_key: str) -> Optional[str]:
        """
        Get the HTML source of a specific tab.
        
        Args:
            tab_key: Key identifying the tab
            
        Returns:
            HTML source or None if error
        """
        if not self.switch_to_tab(tab_key):
            return None
        
        try:
            return self.driver.page_source
        except WebDriverException as e:
            logger.error(f"Failed to get page source for tab: {tab_key}", error=str(e))
            return None
    
    def is_tab_active(self, tab_key: str) -> bool:
        """
        Check if a tab is still active and responsive.
        
        Args:
            tab_key: Key identifying the tab
            
        Returns:
            bool: True if tab is active, False otherwise
        """
        try:
            if not self.switch_to_tab(tab_key):
                return False
            
            # Try to execute a simple JavaScript command
            self.driver.execute_script("return document.readyState;")
            return True
            
        except WebDriverException:
            logger.warning(f"Tab appears to be inactive: {tab_key}")
            return False
    
    def refresh_tab(self, tab_key: str) -> bool:
        """
        Refresh a specific tab.
        
        Args:
            tab_key: Key identifying the tab
            
        Returns:
            bool: True if refresh successful, False otherwise
        """
        if not self.switch_to_tab(tab_key):
            return False
        
        try:
            self.driver.refresh()
            # Wait for page to load
            WebDriverWait(self.driver, self.config.browser_timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            logger.info(f"Refreshed tab: {tab_key}")
            return True
            
        except (WebDriverException, TimeoutException) as e:
            logger.error(f"Failed to refresh tab: {tab_key}", error=str(e))
            return False
    
    def close(self):
        """Close the browser connection"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser connection closed")
            except WebDriverException as e:
                logger.error("Error closing browser", error=str(e))
            finally:
                self.driver = None
                self.tabs = {}
