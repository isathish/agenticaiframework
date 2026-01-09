"""
Basic Web Scraping Tools.
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from ..base import BaseTool, AsyncBaseTool, ToolConfig

logger = logging.getLogger(__name__)


class ScrapeWebsiteTool(AsyncBaseTool):
    """
    Tool for scraping website content.
    
    Supports:
    - HTML content extraction
    - Text extraction
    - Link extraction
    - Metadata extraction
    - Custom headers and cookies
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        user_agent: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="ScrapeWebsiteTool",
            description="Scrape content from websites"
        ))
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    
    async def _execute_async(
        self,
        url: str,
        extract_text: bool = True,
        extract_links: bool = True,
        extract_metadata: bool = True,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Scrape website content.
        
        Args:
            url: URL to scrape
            extract_text: Extract text content
            extract_links: Extract links
            extract_metadata: Extract metadata
            headers: Custom headers
            timeout: Request timeout
            
        Returns:
            Dict with scraped content
        """
        try:
            import aiohttp
        except ImportError:
            raise ImportError("Web scraping requires: pip install aiohttp")
        
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("Web scraping requires: pip install beautifulsoup4")
        
        request_headers = {
            'User-Agent': self.user_agent,
            **(headers or {}),
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                response.raise_for_status()
                html = await response.text()
                content_type = response.headers.get('Content-Type', '')
        
        soup = BeautifulSoup(html, 'html.parser')
        
        result = {
            'url': url,
            'status': 'success',
            'content_type': content_type,
        }
        
        if extract_text:
            # Remove script and style elements
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            text = soup.get_text(separator='\n', strip=True)
            # Clean up whitespace
            text = re.sub(r'\n\s*\n', '\n\n', text)
            result['text'] = text
        
        if extract_links:
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                absolute_url = urljoin(url, href)
                links.append({
                    'text': a.get_text(strip=True),
                    'url': absolute_url,
                })
            result['links'] = links
        
        if extract_metadata:
            result['metadata'] = {
                'title': soup.title.string if soup.title else None,
                'description': self._get_meta(soup, 'description'),
                'keywords': self._get_meta(soup, 'keywords'),
                'author': self._get_meta(soup, 'author'),
                'og_title': self._get_meta(soup, 'og:title', 'property'),
                'og_description': self._get_meta(soup, 'og:description', 'property'),
            }
        
        return result
    
    def _get_meta(
        self,
        soup,
        name: str,
        attr: str = 'name'
    ) -> Optional[str]:
        """Get meta tag content."""
        tag = soup.find('meta', attrs={attr: name})
        return tag.get('content') if tag else None
    
    def _execute(self, **kwargs) -> Any:
        """Sync wrapper."""
        import asyncio
        return asyncio.run(self._execute_async(**kwargs))


class ScrapeElementTool(BaseTool):
    """
    Tool for scraping specific elements from web pages.
    
    Supports:
    - CSS selector targeting
    - XPath targeting
    - Multiple element extraction
    - Attribute extraction
    """
    
    def __init__(self, config: Optional[ToolConfig] = None):
        super().__init__(config or ToolConfig(
            name="ScrapeElementTool",
            description="Scrape specific elements from web pages"
        ))
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36"
        )
    
    def _execute(
        self,
        url: str,
        selector: str,
        selector_type: str = 'css',
        attributes: Optional[List[str]] = None,
        multiple: bool = False,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Scrape specific elements.
        
        Args:
            url: URL to scrape
            selector: CSS selector or XPath
            selector_type: 'css' or 'xpath'
            attributes: List of attributes to extract
            multiple: Extract all matches or just first
            timeout: Request timeout
            
        Returns:
            Dict with extracted elements
        """
        try:
            import requests
        except ImportError:
            raise ImportError("Requires: pip install requests")
        
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("Requires: pip install beautifulsoup4")
        
        response = requests.get(
            url,
            headers={'User-Agent': self.user_agent},
            timeout=timeout,
        )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        if selector_type == 'css':
            if multiple:
                elements = soup.select(selector)
            else:
                element = soup.select_one(selector)
                elements = [element] if element else []
        elif selector_type == 'xpath':
            try:
                from lxml import etree
                tree = etree.HTML(response.text)
                if multiple:
                    elements = tree.xpath(selector)
                else:
                    result = tree.xpath(selector)
                    elements = [result[0]] if result else []
            except ImportError:
                raise ImportError("XPath requires: pip install lxml")
        else:
            raise ValueError(f"Unknown selector type: {selector_type}")
        
        results = []
        for elem in elements:
            item = {'text': self._get_text(elem)}
            
            if attributes:
                item['attributes'] = {}
                for attr in attributes:
                    item['attributes'][attr] = self._get_attr(elem, attr)
            
            results.append(item)
        
        return {
            'url': url,
            'selector': selector,
            'selector_type': selector_type,
            'count': len(results),
            'elements': results if multiple else (results[0] if results else None),
        }
    
    def _get_text(self, element) -> str:
        """Get text from element."""
        if hasattr(element, 'get_text'):
            return element.get_text(strip=True)
        elif hasattr(element, 'text'):
            return element.text or ''
        return str(element)
    
    def _get_attr(self, element, attr: str) -> Optional[str]:
        """Get attribute from element."""
        if hasattr(element, 'get'):
            return element.get(attr)
        elif hasattr(element, 'attrib'):
            return element.attrib.get(attr)
        return None


__all__ = ['ScrapeWebsiteTool', 'ScrapeElementTool']
