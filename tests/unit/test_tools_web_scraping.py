"""
Tests for web scraping tools module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from agenticaiframework.tools.web_scraping.basic_scraping import (
    ScrapeWebsiteTool,
    ScrapeElementTool,
)
from agenticaiframework.tools.base import ToolConfig


class TestScrapeWebsiteTool:
    """Tests for ScrapeWebsiteTool."""
    
    def test_init_default(self):
        """Test default initialization."""
        tool = ScrapeWebsiteTool()
        assert tool.config.name == "ScrapeWebsiteTool"
        assert 'Mozilla' in tool.user_agent
    
    def test_init_custom_user_agent(self):
        """Test initialization with custom user agent."""
        tool = ScrapeWebsiteTool(user_agent="CustomBot/1.0")
        assert tool.user_agent == "CustomBot/1.0"
    
    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = ToolConfig(name="CustomScraper", description="Custom scraper")
        tool = ScrapeWebsiteTool(config=config)
        assert tool.config.name == "CustomScraper"


class TestScrapeElementTool:
    """Tests for ScrapeElementTool."""
    
    def test_init_default(self):
        """Test default initialization."""
        tool = ScrapeElementTool()
        assert tool.config.name == "ScrapeElementTool"
    
    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = ToolConfig(name="ElementExtractor", description="Extract elements")
        tool = ScrapeElementTool(config=config)
        assert tool.config.name == "ElementExtractor"


class TestAdvancedScrapingTools:
    """Tests for advanced scraping tools."""
    
    def test_advanced_scraping_import(self):
        """Test that advanced scraping tools can be imported."""
        from agenticaiframework.tools.web_scraping.advanced_scraping import (
            ScrapflyScrapeWebsiteTool,
            ScrapegraphScrapeTool,
            SpiderScraperTool,
            OxylabsScraperTool,
            BrightDataTool,
        )
        assert ScrapflyScrapeWebsiteTool is not None
        assert ScrapegraphScrapeTool is not None
        assert SpiderScraperTool is not None
        assert OxylabsScraperTool is not None
        assert BrightDataTool is not None
    
    def test_scrapfly_init(self):
        """Test ScrapflyScrapeWebsiteTool initialization."""
        from agenticaiframework.tools.web_scraping.advanced_scraping import ScrapflyScrapeWebsiteTool
        tool = ScrapflyScrapeWebsiteTool()
        assert tool.config.name == "ScrapflyScrapeWebsiteTool"
    
    def test_scrapegraph_init(self):
        """Test ScrapegraphScrapeTool initialization."""
        from agenticaiframework.tools.web_scraping.advanced_scraping import ScrapegraphScrapeTool
        tool = ScrapegraphScrapeTool()
        assert tool.config.name == "ScrapegraphScrapeTool"
    
    def test_spider_init(self):
        """Test SpiderScraperTool initialization."""
        from agenticaiframework.tools.web_scraping.advanced_scraping import SpiderScraperTool
        tool = SpiderScraperTool()
        assert tool.config.name == "SpiderScraperTool"


class TestBrowserTools:
    """Tests for browser automation tools."""
    
    def test_browser_tools_import(self):
        """Test that browser tools can be imported."""
        from agenticaiframework.tools.web_scraping.browser_tools import (
            BrowserbaseWebLoaderTool,
            HyperbrowserLoadTool,
            StagehandTool,
        )
        assert BrowserbaseWebLoaderTool is not None
        assert HyperbrowserLoadTool is not None
        assert StagehandTool is not None
    
    def test_browserbase_init(self):
        """Test BrowserbaseWebLoaderTool initialization."""
        from agenticaiframework.tools.web_scraping.browser_tools import BrowserbaseWebLoaderTool
        tool = BrowserbaseWebLoaderTool()
        assert tool.config.name == "BrowserbaseWebLoaderTool"
    
    def test_hyperbrowser_init(self):
        """Test HyperbrowserLoadTool initialization."""
        from agenticaiframework.tools.web_scraping.browser_tools import HyperbrowserLoadTool
        tool = HyperbrowserLoadTool()
        assert tool.config.name == "HyperbrowserLoadTool"
    
    def test_stagehand_init(self):
        """Test StagehandTool initialization."""
        from agenticaiframework.tools.web_scraping.browser_tools import StagehandTool
        tool = StagehandTool()
        assert tool.config.name == "StagehandTool"


class TestSeleniumTools:
    """Tests for Selenium tools."""
    
    def test_selenium_tools_import(self):
        """Test that Selenium tools can be imported."""
        from agenticaiframework.tools.web_scraping.selenium_tools import (
            SeleniumScraperTool,
        )
        assert SeleniumScraperTool is not None
    
    def test_selenium_scraping_init(self):
        """Test SeleniumScraperTool initialization."""
        from agenticaiframework.tools.web_scraping.selenium_tools import SeleniumScraperTool
        tool = SeleniumScraperTool()
        assert tool.config.name == "SeleniumScraperTool"


class TestFirecrawlTools:
    """Tests for Firecrawl tools."""
    
    def test_firecrawl_import(self):
        """Test that Firecrawl tools can be imported."""
        from agenticaiframework.tools.web_scraping.firecrawl_tools import (
            FirecrawlCrawlWebsiteTool,
            FirecrawlScrapeWebsiteTool,
        )
        assert FirecrawlCrawlWebsiteTool is not None
        assert FirecrawlScrapeWebsiteTool is not None
    
    def test_firecrawl_crawl_init(self):
        """Test FirecrawlCrawlWebsiteTool initialization."""
        from agenticaiframework.tools.web_scraping.firecrawl_tools import FirecrawlCrawlWebsiteTool
        tool = FirecrawlCrawlWebsiteTool()
        assert tool.config.name == "FirecrawlCrawlWebsiteTool"
    
    def test_firecrawl_init_with_api_key(self):
        """Test FirecrawlScrapeWebsiteTool initialization with API key."""
        from agenticaiframework.tools.web_scraping.firecrawl_tools import FirecrawlScrapeWebsiteTool
        config = ToolConfig(name="FirecrawlScrapeWebsiteTool", api_key="test-api-key")
        tool = FirecrawlScrapeWebsiteTool(config=config)
        assert tool.config.api_key == "test-api-key"
    
    def test_firecrawl_scrape_init(self):
        """Test FirecrawlScrapeWebsiteTool initialization."""
        from agenticaiframework.tools.web_scraping.firecrawl_tools import FirecrawlScrapeWebsiteTool
        tool = FirecrawlScrapeWebsiteTool()
        assert tool.config.name == "FirecrawlScrapeWebsiteTool"


class TestWebScrapingPackageInit:
    """Tests for web scraping package initialization."""
    
    def test_package_exports(self):
        """Test that package exports main classes."""
        from agenticaiframework.tools.web_scraping import (
            ScrapeWebsiteTool,
            ScrapeElementTool,
            ScrapflyScrapeWebsiteTool,
            BrowserbaseWebLoaderTool,
            FirecrawlCrawlWebsiteTool,
            SeleniumScraperTool,
        )
        assert ScrapeWebsiteTool is not None
        assert ScrapeElementTool is not None
        assert ScrapflyScrapeWebsiteTool is not None
        assert BrowserbaseWebLoaderTool is not None
        assert FirecrawlCrawlWebsiteTool is not None
        assert SeleniumScraperTool is not None


class TestScrapingToolExecution:
    """Tests for scraping tool execution."""
    
    def test_scrape_element_basic(self):
        """Test basic element scraping setup."""
        tool = ScrapeElementTool()
        # Test that tool has expected interface
        assert hasattr(tool, '_execute') or hasattr(tool, '_execute_async')


class TestToolConfigDefaults:
    """Tests for tool configuration defaults."""
    
    def test_scrape_tool_has_description(self):
        """Test ScrapeWebsiteTool has description."""
        tool = ScrapeWebsiteTool()
        assert tool.config.description is not None
        assert len(tool.config.description) > 0
    
    def test_element_tool_has_description(self):
        """Test ScrapeElementTool has description."""
        tool = ScrapeElementTool()
        assert tool.config.description is not None
        assert len(tool.config.description) > 0
    
    def test_tools_have_default_timeout(self):
        """Test tools have default timeout."""
        tool = ScrapeWebsiteTool()
        assert tool.config.timeout == 30.0


class TestWebScrapingInheritance:
    """Tests for web scraping tool inheritance."""
    
    def test_scrape_website_inherits_async_base(self):
        """Test ScrapeWebsiteTool inherits from AsyncBaseTool."""
        from agenticaiframework.tools.base import AsyncBaseTool
        tool = ScrapeWebsiteTool()
        assert isinstance(tool, AsyncBaseTool)
    
    def test_scrape_element_inherits_base(self):
        """Test ScrapeElementTool inherits from BaseTool."""
        from agenticaiframework.tools.base import BaseTool
        tool = ScrapeElementTool()
        assert isinstance(tool, BaseTool)
