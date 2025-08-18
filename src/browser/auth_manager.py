"""
Authentication manager for web scraping platforms.
Handles automatic login and session management for Betburger and Surebet.
"""
import time
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
                "//div[contains(@class, 'user-info')]",
                "//span[contains(@class, 'user-name')]",
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
            if "/valuebets" in current_url or "/account" in current_url:
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
            
            # Wait for redirect
            time.sleep(3)
            
            # Verify login success
            if self.is_logged_in_surebet(driver):
                logger.info("Surebet login successful")
                return True
            else:
                logger.error("Surebet login failed - credentials may be incorrect")
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
