"""
Authentication manager for web scraping platforms.
Handles automatic login and session management for Betburger and Surebet.
"""
import os
import time
from pathlib import Path
from typing import Optional, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from ..utils.logger import get_module_logger
from ..config.settings import BetburgerConfig, SurebetConfig, BotConfig

logger = get_module_logger("auth_manager")

class AuthManager:
    """Manages authentication for web scraping platforms"""
    
    def __init__(self, bot_config: BotConfig):
        self.bot_config = bot_config
        self.login_timeout = 30  # seconds to wait for login elements

    # --- helpers ---------------------------------------------------------
    def _ensure_dir(self, p: Path) -> None:
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def _debug_capture(self, driver, prefix: str) -> None:
        """Save page HTML and screenshot to logs for diagnostics."""
        try:
            root = Path(os.getcwd())
            html_dir = root / "logs" / "raw_html"
            png_dir = root / "logs" / "screenshots"
            self._ensure_dir(html_dir)
            self._ensure_dir(png_dir)
            ts = time.strftime("%Y%m%d_%H%M%S")
            html_path = html_dir / f"{prefix}_{ts}.html"
            png_path = png_dir / f"{prefix}_{ts}.png"
            # Write HTML
            try:
                src = driver.page_source
                html_path.write_text(src or "", encoding="utf-8")
            except Exception:
                pass
            # Save screenshot
            try:
                driver.save_screenshot(str(png_path))
            except Exception:
                pass
            logger.info("Saved debug artifacts", html=str(html_path), screenshot=str(png_path))
        except Exception:
            # Best-effort; do not raise
            pass

    def _dismiss_cookies_banner_surebet(self, driver) -> None:
        """Best-effort cookie consent dismissal for Surebet.

        Tries multiple common selectors/texts in ES/EN. Safe to call even if not present.
        """
        try:
            # Common buttons/links for cookie consent
            candidates = [
                "//button[contains(translate(., 'ACEPTAR', 'aceptar'), 'acept') or contains(translate(., 'ACEPTO', 'acepto'), 'acepto') or contains(translate(., 'AGREE', 'agree'), 'agree')]",
                "//button[contains(., 'OK') or contains(., 'Ok') or contains(., 'ok')]",
                "//button[contains(translate(., 'CONTINUAR', 'continuar'), 'continuar')]",
                "//a[contains(translate(., 'ACEPTAR', 'aceptar'), 'acept') or contains(., 'Agree')]",
                "//div[contains(@class,'cookie') or contains(@id,'cookie')]//button",
            ]
            for xp in candidates:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    el.click()
                    time.sleep(0.3)
                    break
                except Exception:
                    continue
        except Exception:
            pass
    
    def is_logged_in_betburger(self, driver) -> bool:
        """
        Check if currently logged into Betburger.
        
        Args:
            driver: Selenium WebDriver instance
            
        Returns:
            bool: True if logged in, False otherwise
        """
        try:
            # Check for login indicators (adjust selectors based on actual site)
            # Common indicators: user menu, logout button, or absence of login form
            
            # Method 1: Check for user menu or dashboard elements
            user_indicators = [
                "//a[contains(@href, '/logout')]",  # Logout link
                "//div[contains(@class, 'user-menu')]",  # User menu
                "//span[contains(@class, 'username')]",  # Username display
            ]
            
            for selector in user_indicators:
                try:
                    driver.find_element(By.XPATH, selector)
                    logger.debug("Betburger login confirmed via user indicator")
                    return True
                except NoSuchElementException:
                    continue
            
            # Method 2: Check URL patterns that indicate logged-in state
            current_url = driver.current_url
            if "/dashboard" in current_url or "/account" in current_url:
                logger.debug("Betburger login confirmed via URL pattern")
                return True
            
            # Method 3: Check if login form is NOT present
            try:
                driver.find_element(By.XPATH, "//input[@type='email' or @name='email']")
                logger.debug("Betburger login form detected - not logged in")
                return False
            except NoSuchElementException:
                # No login form found, likely logged in
                logger.debug("Betburger no login form found - likely logged in")
                return True
                
        except Exception as e:
            logger.error("Error checking Betburger login status", error=str(e))
            return False
    
    def login_betburger(self, driver, config: BetburgerConfig) -> bool:
        """
        Perform login to Betburger.
        
        Args:
            driver: Selenium WebDriver instance
            config: Betburger configuration with credentials
            
        Returns:
            bool: True if login successful, False otherwise
        """
        if not config.username or not config.password:
            logger.error("Betburger credentials not configured")
            return False
        
        try:
            logger.info("Attempting Betburger login")
            
            # Navigate to login page
            driver.get(config.login_url)
            
            # Wait for login form to load
            wait = WebDriverWait(driver, self.login_timeout)
            
            # Find and fill email field
            email_field = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='email' or @name='email']"))
            )
            email_field.clear()
            email_field.send_keys(config.username)
            
            # Find and fill password field
            password_field = driver.find_element(By.XPATH, "//input[@type='password' or @name='password']")
            password_field.clear()
            password_field.send_keys(config.password)
            
            # Submit login form
            submit_button = driver.find_element(By.XPATH, "//button[@type='submit'] | //input[@type='submit']")
            submit_button.click()
            
            # Wait for redirect or dashboard to load
            time.sleep(3)
            
            # Verify login success
            if self.is_logged_in_betburger(driver):
                logger.info("Betburger login successful")
                return True
            else:
                logger.error("Betburger login failed - credentials may be incorrect")
                return False
                
        except TimeoutException:
            logger.error("Betburger login timeout - page elements not found")
            return False
        except Exception as e:
            logger.error("Unexpected error during Betburger login", error=str(e))
            return False
    
    def is_logged_in_surebet(self, driver) -> bool:
        """
        Check if currently logged into Surebet.
        
        Args:
            driver: Selenium WebDriver instance
            
        Returns:
            bool: True if logged in, False otherwise
        """
        try:
            # Check for Surebet-specific login indicators
            user_indicators = [
                "//a[contains(@href, '/logout')]",
                "//div[contains(@class, 'user-info') or contains(@class,'user-menu')]",
                "//span[contains(@class, 'user-name') or contains(@class,'username')]",
            ]
            
            for selector in user_indicators:
                try:
                    driver.find_element(By.XPATH, selector)
                    logger.debug("Surebet login confirmed via user indicator")
                    return True
                except NoSuchElementException:
                    continue
            
            # Check URL patterns
            current_url = driver.current_url
            if "/valuebets" in current_url or "/account" in current_url or "/users/" in current_url:
                logger.debug("Surebet login confirmed via URL pattern")
                return True
            
            # Check if login form is NOT present
            try:
                driver.find_element(By.XPATH, "//input[@name='user[email]' or @type='email']")
                logger.debug("Surebet login form detected - not logged in")
                return False
            except NoSuchElementException:
                logger.debug("Surebet no login form found - likely logged in")
                return True
                
        except Exception as e:
            logger.error("Error checking Surebet login status", error=str(e))
            return False
    
    def login_surebet(self, driver, config: SurebetConfig) -> bool:
        """
        Perform login to Surebet.
        
        Args:
            driver: Selenium WebDriver instance
            config: Surebet configuration with credentials
            
        Returns:
            bool: True if login successful, False otherwise
        """
        if not config.username or not config.password:
            logger.error("Surebet credentials not configured")
            return False
        
        try:
            logger.info("Attempting Surebet login")
            
            # Navigate to login page
            driver.get(config.login_url)
            
            # Wait for login form to load
            wait = WebDriverWait(driver, self.login_timeout)

            # Dismiss cookies banner if present
            self._dismiss_cookies_banner_surebet(driver)

            # Find and fill email field (Surebet uses user[email])
            email_field = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@name='user[email]' or @type='email']"))
            )
            email_field.clear()
            email_field.send_keys(config.username)
            
            # Find and fill password field
            password_field = driver.find_element(By.XPATH, "//input[@name='user[password]' or @type='password']")
            password_field.clear()
            password_field.send_keys(config.password)
            
            # Submit login form
            submit_button = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
            submit_button.click()
            
            # Wait for redirect or authenticated indicators
            end_time = time.time() + 20
            success = False
            while time.time() < end_time:
                try:
                    if self.is_logged_in_surebet(driver):
                        success = True
                        break
                except Exception:
                    pass
                time.sleep(0.5)

            # Verify login success
            if success:
                logger.info("Surebet login successful")
                return True
            else:
                # Try to detect common blockers
                try:
                    # Captcha presence heuristic
                    if driver.find_elements(By.XPATH, "//iframe[contains(@src,'captcha') or contains(@class,'captcha')] | //div[contains(@class,'g-recaptcha')]"):
                        logger.warning("Surebet login may be blocked by CAPTCHA")
                except Exception:
                    pass

                self._debug_capture(driver, "surebet_login_FAIL")
                logger.error("Surebet login failed - credentials may be incorrect or blocked by consent/captcha")
                return False
                
        except TimeoutException:
            logger.error("Surebet login timeout - page elements not found")
            return False
        except Exception as e:
            logger.error("Unexpected error during Surebet login", error=str(e))
            return False
    
    def ensure_authenticated(self, driver, platform: str, config) -> bool:
        """
        Ensure the driver is authenticated for the specified platform.
        
        Args:
            driver: Selenium WebDriver instance
            platform: "betburger" or "surebet"
            config: Platform-specific configuration
            
        Returns:
            bool: True if authenticated, False otherwise
        """
        if platform == "betburger":
            if self.is_logged_in_betburger(driver):
                return True
            return self.login_betburger(driver, config)
            
        elif platform == "surebet":
            if self.is_logged_in_surebet(driver):
                return True
            return self.login_surebet(driver, config)
            
        else:
            logger.error(f"Unknown platform: {platform}")
            return False
