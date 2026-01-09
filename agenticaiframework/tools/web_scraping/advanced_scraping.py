"""
Advanced Web Scraping Tools with API integrations.
"""

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseTool, AsyncBaseTool, ToolConfig

logger = logging.getLogger(__name__)


class ScrapflyScrapeWebsiteTool(AsyncBaseTool):
    """
    Tool for scraping websites using Scrapfly API.
    
    Features:
    - Anti-bot bypass
    - JavaScript rendering
    - Proxy rotation
    - Screenshot capture
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="ScrapflyScrapeWebsiteTool",
            description="Scrape websites using Scrapfly API"
        ))
        self.api_key = api_key or self.config.api_key
    
    async def _execute_async(
        self,
        url: str,
        render_js: bool = True,
        proxy_pool: str = 'residential',
        country: Optional[str] = None,
        screenshot: bool = False,
    ) -> Dict[str, Any]:
        """Scrape using Scrapfly."""
        if not self.api_key:
            raise ValueError("Scrapfly API key required")
        
        try:
            import aiohttp
        except ImportError:
            raise ImportError("Requires: pip install aiohttp")
        
        params = {
            'key': self.api_key,
            'url': url,
            'render_js': str(render_js).lower(),
            'proxy_pool': proxy_pool,
        }
        
        if country:
            params['country'] = country
        if screenshot:
            params['screenshot'] = 'true'
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.scrapfly.io/scrape',
                params=params,
            ) as response:
                data = await response.json()
        
        return {
            'url': url,
            'status': 'success' if response.status == 200 else 'error',
            'content': data.get('result', {}).get('content'),
            'screenshot': data.get('result', {}).get('screenshot'),
            'log': data.get('result', {}).get('log'),
        }
    
    def _execute(self, **kwargs) -> Any:
        import asyncio
        return asyncio.run(self._execute_async(**kwargs))


class ScrapegraphScrapeTool(BaseTool):
    """
    Tool for AI-powered web scraping using ScrapeGraph.
    
    Features:
    - Natural language queries
    - Structured data extraction
    - Schema-based extraction
    """
    
    def __init__(self, config: Optional[ToolConfig] = None):
        super().__init__(config or ToolConfig(
            name="ScrapegraphScrapeTool",
            description="AI-powered web scraping"
        ))
    
    def _execute(
        self,
        url: str,
        query: str,
        output_schema: Optional[Dict] = None,
        llm_model: str = 'gpt-4',
    ) -> Dict[str, Any]:
        """Scrape using AI-powered extraction."""
        try:
            from scrapegraphai.graphs import SmartScraperGraph
        except ImportError:
            raise ImportError("Requires: pip install scrapegraphai")
        
        graph_config = {
            "llm": {
                "model": llm_model,
                "api_key": self.config.api_key,
            },
        }
        
        if output_schema:
            graph_config["schema"] = output_schema
        
        scraper = SmartScraperGraph(
            prompt=query,
            source=url,
            config=graph_config,
        )
        
        result = scraper.run()
        
        return {
            'url': url,
            'query': query,
            'status': 'success',
            'data': result,
        }


class SpiderScraperTool(AsyncBaseTool):
    """
    Tool for web scraping using Spider API.
    
    Features:
    - High-speed scraping
    - Automatic rate limiting
    - Structured data extraction
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="SpiderScraperTool",
            description="High-speed web scraping"
        ))
        self.api_key = api_key or self.config.api_key
    
    async def _execute_async(
        self,
        url: str,
        mode: str = 'scrape',
        depth: int = 1,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Scrape using Spider API."""
        if not self.api_key:
            raise ValueError("Spider API key required")
        
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
            'mode': mode,
            'depth': depth,
            'limit': limit,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.spider.cloud/scrape',
                headers=headers,
                json=payload,
            ) as response:
                data = await response.json()
        
        return {
            'url': url,
            'status': 'success' if response.status == 200 else 'error',
            'pages': data.get('pages', []),
            'total': data.get('total', 0),
        }
    
    def _execute(self, **kwargs) -> Any:
        import asyncio
        return asyncio.run(self._execute_async(**kwargs))


class OxylabsScraperTool(AsyncBaseTool):
    """
    Tool for web scraping using Oxylabs API.
    
    Features:
    - SERP scraping
    - E-commerce scraping
    - Real-time results
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="OxylabsScraperTool",
            description="Professional web scraping with Oxylabs"
        ))
        self.username = username or self.config.extra_config.get('username')
        self.password = password or self.config.api_key
    
    async def _execute_async(
        self,
        url: str,
        source: str = 'universal',
        render: bool = False,
        geo_location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Scrape using Oxylabs."""
        if not self.username or not self.password:
            raise ValueError("Oxylabs credentials required")
        
        try:
            import aiohttp
        except ImportError:
            raise ImportError("Requires: pip install aiohttp")
        
        payload = {
            'source': source,
            'url': url,
            'render': 'html' if render else None,
        }
        
        if geo_location:
            payload['geo_location'] = geo_location
        
        auth = aiohttp.BasicAuth(self.username, self.password)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://realtime.oxylabs.io/v1/queries',
                auth=auth,
                json=payload,
            ) as response:
                data = await response.json()
        
        return {
            'url': url,
            'status': 'success' if response.status == 200 else 'error',
            'results': data.get('results', []),
        }
    
    def _execute(self, **kwargs) -> Any:
        import asyncio
        return asyncio.run(self._execute_async(**kwargs))


class BrightDataTool(AsyncBaseTool):
    """
    Tool for web scraping using Bright Data.
    
    Features:
    - Proxy network access
    - Web unlocker
    - SERP API
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        customer_id: Optional[str] = None,
        zone: str = 'web_unlocker',
    ):
        super().__init__(config or ToolConfig(
            name="BrightDataTool",
            description="Web scraping with Bright Data proxy network"
        ))
        self.customer_id = customer_id or self.config.extra_config.get('customer_id')
        self.zone = zone
    
    async def _execute_async(
        self,
        url: str,
        country: Optional[str] = None,
        render_js: bool = False,
    ) -> Dict[str, Any]:
        """Scrape using Bright Data."""
        if not self.customer_id or not self.config.api_key:
            raise ValueError("Bright Data credentials required")
        
        try:
            import aiohttp
        except ImportError:
            raise ImportError("Requires: pip install aiohttp")
        
        # Build proxy URL
        proxy_url = (
            f"http://{self.customer_id}-zone-{self.zone}"
            f":{self.config.api_key}@brd.superproxy.io:22225"
        )
        
        if country:
            proxy_url = proxy_url.replace(
                f'-zone-{self.zone}',
                f'-zone-{self.zone}-country-{country}'
            )
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                proxy=proxy_url,
                headers=headers,
            ) as response:
                content = await response.text()
        
        return {
            'url': url,
            'status': 'success' if response.status == 200 else 'error',
            'content': content,
            'content_length': len(content),
        }
    
    def _execute(self, **kwargs) -> Any:
        import asyncio
        return asyncio.run(self._execute_async(**kwargs))


__all__ = [
    'ScrapflyScrapeWebsiteTool',
    'ScrapegraphScrapeTool',
    'SpiderScraperTool',
    'OxylabsScraperTool',
    'BrightDataTool',
]
