"""
Firecrawl Web Scraping Tools.
"""

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseTool, AsyncBaseTool, ToolConfig

logger = logging.getLogger(__name__)


class FirecrawlCrawlWebsiteTool(AsyncBaseTool):
    """
    Tool for crawling websites using Firecrawl.
    
    Features:
    - Deep website crawling
    - Link following
    - Structured extraction
    - Rate limiting
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="FirecrawlCrawlWebsiteTool",
            description="Crawl websites using Firecrawl"
        ))
        self.api_key = api_key or self.config.api_key
        self.base_url = "https://api.firecrawl.dev/v0"
    
    async def _execute_async(
        self,
        url: str,
        max_pages: int = 10,
        include_paths: Optional[List[str]] = None,
        exclude_paths: Optional[List[str]] = None,
        wait_for_results: bool = True,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        Crawl website.
        
        Args:
            url: Starting URL
            max_pages: Maximum pages to crawl
            include_paths: Paths to include
            exclude_paths: Paths to exclude
            wait_for_results: Wait for crawl to complete
            timeout: Timeout in seconds
            
        Returns:
            Dict with crawl results
        """
        if not self.api_key:
            raise ValueError("Firecrawl API key required")
        
        try:
            import aiohttp
        except ImportError:
            raise ImportError("Requires: pip install aiohttp")
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        
        payload = {
            'url': url,
            'crawlerOptions': {
                'maxDepth': max_pages,
                'includes': include_paths or [],
                'excludes': exclude_paths or [],
            },
            'pageOptions': {
                'onlyMainContent': True,
            },
        }
        
        async with aiohttp.ClientSession() as session:
            # Start crawl
            async with session.post(
                f'{self.base_url}/crawl',
                headers=headers,
                json=payload,
            ) as response:
                start_data = await response.json()
            
            if not wait_for_results:
                return {
                    'url': url,
                    'status': 'started',
                    'job_id': start_data.get('jobId'),
                }
            
            job_id = start_data.get('jobId')
            
            if not job_id:
                return {
                    'url': url,
                    'status': 'error',
                    'error': 'No job ID returned',
                }
            
            # Poll for results
            import asyncio
            elapsed = 0
            poll_interval = 5
            
            while elapsed < timeout:
                async with session.get(
                    f'{self.base_url}/crawl/status/{job_id}',
                    headers=headers,
                ) as status_response:
                    status_data = await status_response.json()
                
                if status_data.get('status') == 'completed':
                    return {
                        'url': url,
                        'status': 'success',
                        'pages': status_data.get('data', []),
                        'total_pages': len(status_data.get('data', [])),
                    }
                
                if status_data.get('status') == 'failed':
                    return {
                        'url': url,
                        'status': 'error',
                        'error': status_data.get('error'),
                    }
                
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
            
            return {
                'url': url,
                'status': 'timeout',
                'job_id': job_id,
            }
    
    def _execute(self, **kwargs) -> Any:
        import asyncio
        return asyncio.run(self._execute_async(**kwargs))


class FirecrawlScrapeWebsiteTool(AsyncBaseTool):
    """
    Tool for scraping single pages using Firecrawl.
    
    Features:
    - Single page extraction
    - Markdown conversion
    - Clean content extraction
    - Screenshot capture
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="FirecrawlScrapeWebsiteTool",
            description="Scrape single pages using Firecrawl"
        ))
        self.api_key = api_key or self.config.api_key
        self.base_url = "https://api.firecrawl.dev/v0"
    
    async def _execute_async(
        self,
        url: str,
        format: str = 'markdown',
        only_main_content: bool = True,
        include_html: bool = False,
        screenshot: bool = False,
        wait_for: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Scrape single page.
        
        Args:
            url: URL to scrape
            format: Output format (markdown, html, text)
            only_main_content: Extract only main content
            include_html: Include raw HTML
            screenshot: Capture screenshot
            wait_for: CSS selector to wait for
            
        Returns:
            Dict with scraped content
        """
        if not self.api_key:
            raise ValueError("Firecrawl API key required")
        
        try:
            import aiohttp
        except ImportError:
            raise ImportError("Requires: pip install aiohttp")
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        
        formats = []
        if format == 'markdown':
            formats.append('markdown')
        if format == 'html' or include_html:
            formats.append('html')
        if format == 'text':
            formats.append('text')
        if screenshot:
            formats.append('screenshot')
        
        payload = {
            'url': url,
            'pageOptions': {
                'onlyMainContent': only_main_content,
                'includeHtml': include_html,
            },
        }
        
        if wait_for:
            payload['pageOptions']['waitFor'] = wait_for
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{self.base_url}/scrape',
                headers=headers,
                json=payload,
            ) as response:
                data = await response.json()
        
        if response.status != 200:
            return {
                'url': url,
                'status': 'error',
                'error': data.get('error', 'Unknown error'),
            }
        
        page_data = data.get('data', {})
        
        return {
            'url': url,
            'status': 'success',
            'title': page_data.get('metadata', {}).get('title'),
            'description': page_data.get('metadata', {}).get('description'),
            'markdown': page_data.get('markdown'),
            'html': page_data.get('html') if include_html else None,
            'text': page_data.get('text'),
            'screenshot': page_data.get('screenshot'),
            'links': page_data.get('links', []),
            'metadata': page_data.get('metadata', {}),
        }
    
    def _execute(self, **kwargs) -> Any:
        import asyncio
        return asyncio.run(self._execute_async(**kwargs))


__all__ = [
    'FirecrawlCrawlWebsiteTool',
    'FirecrawlScrapeWebsiteTool',
]
