"""
Browser Automation Tools.
"""

import logging
from typing import Any, Dict, List, Optional

from ..base import BaseTool, AsyncBaseTool, ToolConfig

logger = logging.getLogger(__name__)


class BrowserbaseWebLoaderTool(AsyncBaseTool):
    """
    Tool for loading web pages using Browserbase.
    
    Features:
    - Cloud browser infrastructure
    - Session management
    - Anti-detection
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="BrowserbaseWebLoaderTool",
            description="Load web pages using Browserbase"
        ))
        self.api_key = api_key or self.config.api_key
        self.project_id = project_id or self.config.extra_config.get('project_id')
    
    async def _execute_async(
        self,
        url: str,
        wait_time: float = 3.0,
        extract_text: bool = True,
        screenshot: bool = False,
    ) -> Dict[str, Any]:
        """Load page using Browserbase."""
        if not self.api_key:
            raise ValueError("Browserbase API key required")
        
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
            'wait': int(wait_time * 1000),
            'extractText': extract_text,
            'screenshot': screenshot,
        }
        
        if self.project_id:
            payload['projectId'] = self.project_id
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.browserbase.com/v1/pages',
                headers=headers,
                json=payload,
            ) as response:
                data = await response.json()
        
        return {
            'url': url,
            'status': 'success' if response.status == 200 else 'error',
            'text': data.get('text'),
            'title': data.get('title'),
            'screenshot': data.get('screenshot'),
        }
    
    def _execute(self, **kwargs) -> Any:
        import asyncio
        return asyncio.run(self._execute_async(**kwargs))


class HyperbrowserLoadTool(AsyncBaseTool):
    """
    Tool for loading web pages using Hyperbrowser.
    
    Features:
    - Fast page loading
    - Intelligent caching
    - Content extraction
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="HyperbrowserLoadTool",
            description="Load web pages using Hyperbrowser"
        ))
        self.api_key = api_key or self.config.api_key
    
    async def _execute_async(
        self,
        url: str,
        render_js: bool = True,
        extract_links: bool = True,
        extract_metadata: bool = True,
    ) -> Dict[str, Any]:
        """Load page using Hyperbrowser."""
        if not self.api_key:
            raise ValueError("Hyperbrowser API key required")
        
        try:
            import aiohttp
        except ImportError:
            raise ImportError("Requires: pip install aiohttp")
        
        headers = {
            'X-API-Key': self.api_key,
            'Content-Type': 'application/json',
        }
        
        payload = {
            'url': url,
            'renderJs': render_js,
            'extractLinks': extract_links,
            'extractMetadata': extract_metadata,
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.hyperbrowser.ai/v1/load',
                headers=headers,
                json=payload,
            ) as response:
                data = await response.json()
        
        return {
            'url': url,
            'status': 'success' if response.status == 200 else 'error',
            'content': data.get('content'),
            'links': data.get('links', []),
            'metadata': data.get('metadata', {}),
        }
    
    def _execute(self, **kwargs) -> Any:
        import asyncio
        return asyncio.run(self._execute_async(**kwargs))


class StagehandTool(BaseTool):
    """
    Tool for browser automation using Stagehand.
    
    Features:
    - AI-powered automation
    - Natural language commands
    - Multi-step workflows
    """
    
    def __init__(
        self,
        config: Optional[ToolConfig] = None,
        api_key: Optional[str] = None,
    ):
        super().__init__(config or ToolConfig(
            name="StagehandTool",
            description="AI-powered browser automation"
        ))
        self.api_key = api_key or self.config.api_key
        self._page = None
    
    def _execute(
        self,
        url: str,
        actions: List[Dict[str, Any]],
        extract_result: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute browser automation.
        
        Args:
            url: Starting URL
            actions: List of actions to perform
            extract_result: Extract final page content
            
        Returns:
            Dict with automation results
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError("Stagehand requires: pip install playwright")
        
        results = []
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(url)
                
                for action in actions:
                    action_type = action.get('type')
                    result = self._execute_action(page, action)
                    results.append({
                        'action': action_type,
                        'result': result,
                    })
                
                final_content = None
                if extract_result:
                    final_content = {
                        'url': page.url,
                        'title': page.title(),
                        'text': page.inner_text('body'),
                    }
                
                return {
                    'start_url': url,
                    'final_url': page.url,
                    'status': 'success',
                    'actions_executed': len(results),
                    'results': results,
                    'final_content': final_content,
                }
                
            finally:
                browser.close()
    
    def _execute_action(self, page, action: Dict) -> Any:
        """Execute a single action."""
        action_type = action.get('type')
        selector = action.get('selector')
        value = action.get('value')
        
        if action_type == 'click':
            page.click(selector)
            return {'clicked': selector}
        
        elif action_type == 'type':
            page.fill(selector, value)
            return {'typed': value, 'into': selector}
        
        elif action_type == 'wait':
            page.wait_for_timeout(int(value * 1000))
            return {'waited': value}
        
        elif action_type == 'wait_for':
            page.wait_for_selector(selector)
            return {'found': selector}
        
        elif action_type == 'screenshot':
            path = value or 'screenshot.png'
            page.screenshot(path=path)
            return {'screenshot': path}
        
        elif action_type == 'scroll':
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            return {'scrolled': 'bottom'}
        
        elif action_type == 'extract':
            if selector:
                elements = page.query_selector_all(selector)
                texts = [el.inner_text() for el in elements]
                return {'extracted': texts}
            return {'extracted': page.inner_text('body')}
        
        elif action_type == 'navigate':
            page.goto(value)
            return {'navigated': value}
        
        else:
            return {'unknown_action': action_type}


__all__ = [
    'BrowserbaseWebLoaderTool',
    'HyperbrowserLoadTool',
    'StagehandTool',
]
