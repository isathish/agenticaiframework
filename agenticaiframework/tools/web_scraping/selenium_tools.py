"""
Selenium-based Web Scraping Tools.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from pathlib import Path

from ..base import BaseTool, ToolConfig

logger = logging.getLogger(__name__)


class SeleniumScraperTool(BaseTool):
    """
    Tool for scraping dynamic websites using Selenium.
    
    Supports:
    - JavaScript rendering
    - Dynamic content loading
    - User interactions (click, scroll, type)
    - Screenshots
    - Multiple browser support
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        browser: str = 'chrome',
        headless: bool = True,
    ):
        super().__init__(config or ToolConfig(
            name="SeleniumScraperTool",
            description="Scrape dynamic websites with Selenium"
        ))
        self.browser = browser
        self.headless = headless
        self._driver = None
    
    def _get_driver(self):
        """Get or create Selenium WebDriver."""
        if self._driver:
            return self._driver
        
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
        except ImportError:
            raise ImportError("Selenium requires: pip install selenium")
        
        if self.browser == 'chrome':
            options = ChromeOptions()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            self._driver = webdriver.Chrome(options=options)
        elif self.browser == 'firefox':
            options = FirefoxOptions()
            if self.headless:
                options.add_argument('--headless')
            self._driver = webdriver.Firefox(options=options)
        else:
            raise ValueError(f"Unsupported browser: {self.browser}")
        
        return self._driver
    
    def _execute(
        self,
        url: str,
        wait_time: float = 3.0,
        wait_for_element: Optional[str] = None,
        extract_text: bool = True,
        scroll_to_bottom: bool = False,
        screenshot: bool = False,
        screenshot_path: Optional[str] = None,
        actions: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Scrape dynamic website.
        
        Args:
            url: URL to scrape
            wait_time: Time to wait for page load
            wait_for_element: CSS selector to wait for
            extract_text: Extract page text
            scroll_to_bottom: Scroll to load lazy content
            screenshot: Take screenshot
            screenshot_path: Path to save screenshot
            actions: List of actions to perform
            
        Returns:
            Dict with scraped content
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        driver = self._get_driver()
        
        try:
            driver.get(url)
            
            # Wait for page load
            if wait_for_element:
                WebDriverWait(driver, wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_element))
                )
            else:
                time.sleep(wait_time)
            
            # Perform actions
            if actions:
                self._perform_actions(driver, actions)
            
            # Scroll to bottom
            if scroll_to_bottom:
                self._scroll_to_bottom(driver)
            
            result = {
                'url': driver.current_url,
                'title': driver.title,
                'status': 'success',
            }
            
            # Extract text
            if extract_text:
                body = driver.find_element(By.TAG_NAME, 'body')
                result['text'] = body.text
            
            # Take screenshot
            if screenshot:
                if screenshot_path:
                    path = Path(screenshot_path)
                else:
                    path = Path(f"screenshot_{int(time.time())}.png")
                driver.save_screenshot(str(path))
                result['screenshot'] = str(path.absolute())
            
            # Get page source
            result['html_length'] = len(driver.page_source)
            
            return result
            
        except Exception as e:
            logger.error(f"Selenium scraping error: {e}")
            return {
                'url': url,
                'status': 'error',
                'error': str(e),
            }
    
    def _perform_actions(self, driver, actions: List[Dict]):
        """Perform a sequence of actions."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        for action in actions:
            action_type = action.get('type')
            selector = action.get('selector')
            value = action.get('value')
            
            if selector:
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
            
            if action_type == 'click':
                element.click()
            elif action_type == 'type':
                element.clear()
                element.send_keys(value)
            elif action_type == 'submit':
                element.send_keys(Keys.RETURN)
            elif action_type == 'wait':
                time.sleep(float(value or 1))
            elif action_type == 'scroll':
                driver.execute_script(
                    "arguments[0].scrollIntoView();", element
                )
    
    def _scroll_to_bottom(self, driver, scroll_pause: float = 0.5):
        """Scroll to the bottom of the page."""
        last_height = driver.execute_script(
            "return document.body.scrollHeight"
        )
        
        while True:
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(scroll_pause)
            
            new_height = driver.execute_script(
                "return document.body.scrollHeight"
            )
            
            if new_height == last_height:
                break
            last_height = new_height
    
    def find_elements(
        self,
        selector: str,
        by: str = 'css',
        multiple: bool = True,
    ) -> List[Dict]:
        """Find elements on the current page."""
        from selenium.webdriver.common.by import By
        
        driver = self._get_driver()
        
        by_map = {
            'css': By.CSS_SELECTOR,
            'xpath': By.XPATH,
            'id': By.ID,
            'class': By.CLASS_NAME,
            'tag': By.TAG_NAME,
        }
        
        by_method = by_map.get(by, By.CSS_SELECTOR)
        
        if multiple:
            elements = driver.find_elements(by_method, selector)
        else:
            element = driver.find_element(by_method, selector)
            elements = [element] if element else []
        
        return [
            {
                'text': elem.text,
                'tag': elem.tag_name,
                'attributes': {
                    'href': elem.get_attribute('href'),
                    'src': elem.get_attribute('src'),
                    'class': elem.get_attribute('class'),
                },
            }
            for elem in elements
        ]
    
    def close(self):
        """Close the browser."""
        if self._driver:
            self._driver.quit()
            self._driver = None
    
    def __del__(self):
        """Cleanup on deletion."""
        self.close()


__all__ = ['SeleniumScraperTool']
