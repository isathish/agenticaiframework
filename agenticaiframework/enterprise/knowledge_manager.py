"""
Enterprise Knowledge Manager Module.

Knowledge base management, documentation search,
article versioning, and content organization.

Example:
    # Create knowledge manager
    kb = create_knowledge_manager()
    
    # Add article
    article = await kb.add_article(
        title="Getting Started",
        content="Welcome to the platform...",
        category="guides",
    )
    
    # Search
    results = await kb.search("how to configure")
    
    # Get article
    article = await kb.get_article(article.id)
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

logger = logging.getLogger(__name__)


class KnowledgeError(Exception):
    """Knowledge error."""
    pass


class ArticleStatus(str, Enum):
    """Article status."""
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ContentType(str, Enum):
    """Content type."""
    MARKDOWN = "markdown"
    HTML = "html"
    PLAIN_TEXT = "plain_text"
    RICH_TEXT = "rich_text"


class ArticleType(str, Enum):
    """Article type."""
    ARTICLE = "article"
    FAQ = "faq"
    TUTORIAL = "tutorial"
    GUIDE = "guide"
    REFERENCE = "reference"
    TROUBLESHOOTING = "troubleshooting"


@dataclass
class Article:
    """Knowledge article."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    slug: str = ""
    title: str = ""
    content: str = ""
    summary: str = ""
    
    # Classification
    article_type: ArticleType = ArticleType.ARTICLE
    status: ArticleStatus = ArticleStatus.DRAFT
    content_type: ContentType = ContentType.MARKDOWN
    
    # Organization
    category: str = ""
    subcategory: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Versioning
    version: int = 1
    parent_id: Optional[str] = None  # For version history
    
    # Authors
    author: str = ""
    contributors: List[str] = field(default_factory=list)
    
    # Metadata
    featured: bool = False
    pinned: bool = False
    view_count: int = 0
    helpful_count: int = 0
    not_helpful_count: int = 0
    
    # Related
    related_articles: List[str] = field(default_factory=list)
    
    # Dates
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    published_at: Optional[datetime] = None
    
    # Custom
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Category:
    """Knowledge category."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    slug: str = ""
    description: str = ""
    parent_id: Optional[str] = None
    icon: str = ""
    order: int = 0
    article_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SearchResult:
    """Search result."""
    article_id: str = ""
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    highlights: List[str] = field(default_factory=list)


@dataclass
class ArticleVersion:
    """Article version."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    article_id: str = ""
    version: int = 1
    title: str = ""
    content: str = ""
    author: str = ""
    comment: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class KnowledgeStats:
    """Knowledge base statistics."""
    total_articles: int = 0
    published: int = 0
    draft: int = 0
    categories: int = 0
    total_views: int = 0
    most_viewed: List[str] = field(default_factory=list)
    recently_updated: List[str] = field(default_factory=list)


# Article store
class ArticleStore(ABC):
    """Article storage."""
    
    @abstractmethod
    async def save(self, article: Article) -> None:
        pass
    
    @abstractmethod
    async def get(self, article_id: str) -> Optional[Article]:
        pass
    
    @abstractmethod
    async def get_by_slug(self, slug: str) -> Optional[Article]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Article]:
        pass
    
    @abstractmethod
    async def delete(self, article_id: str) -> bool:
        pass
    
    @abstractmethod
    async def search(self, query: str) -> List[SearchResult]:
        pass


class InMemoryArticleStore(ArticleStore):
    """In-memory article store."""
    
    def __init__(self):
        self._articles: Dict[str, Article] = {}
        self._by_slug: Dict[str, str] = {}
    
    async def save(self, article: Article) -> None:
        self._articles[article.id] = article
        if article.slug:
            self._by_slug[article.slug] = article.id
    
    async def get(self, article_id: str) -> Optional[Article]:
        return self._articles.get(article_id)
    
    async def get_by_slug(self, slug: str) -> Optional[Article]:
        article_id = self._by_slug.get(slug)
        if article_id:
            return self._articles.get(article_id)
        return None
    
    async def list_all(self) -> List[Article]:
        return list(self._articles.values())
    
    async def delete(self, article_id: str) -> bool:
        article = self._articles.get(article_id)
        if article:
            del self._articles[article_id]
            if article.slug:
                self._by_slug.pop(article.slug, None)
            return True
        return False
    
    async def search(self, query: str) -> List[SearchResult]:
        results = []
        query_lower = query.lower()
        terms = query_lower.split()
        
        for article in self._articles.values():
            if article.status != ArticleStatus.PUBLISHED:
                continue
            
            score = 0.0
            highlights = []
            
            title_lower = article.title.lower()
            content_lower = article.content.lower()
            
            for term in terms:
                if term in title_lower:
                    score += 10.0
                    highlights.append(f"Title: ...{term}...")
                
                if term in content_lower:
                    score += 1.0
                    # Find snippet
                    idx = content_lower.find(term)
                    if idx >= 0:
                        start = max(0, idx - 30)
                        end = min(len(article.content), idx + len(term) + 30)
                        snippet = article.content[start:end]
                        highlights.append(f"...{snippet}...")
                
                for tag in article.tags:
                    if term in tag.lower():
                        score += 5.0
            
            if score > 0:
                snippet = article.summary or article.content[:200]
                results.append(SearchResult(
                    article_id=article.id,
                    title=article.title,
                    snippet=snippet,
                    score=score,
                    highlights=highlights[:3],
                ))
        
        return sorted(results, key=lambda r: r.score, reverse=True)


# Category store
class CategoryStore(ABC):
    """Category storage."""
    
    @abstractmethod
    async def save(self, category: Category) -> None:
        pass
    
    @abstractmethod
    async def get(self, category_id: str) -> Optional[Category]:
        pass
    
    @abstractmethod
    async def get_by_slug(self, slug: str) -> Optional[Category]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Category]:
        pass


class InMemoryCategoryStore(CategoryStore):
    """In-memory category store."""
    
    def __init__(self):
        self._categories: Dict[str, Category] = {}
        self._by_slug: Dict[str, str] = {}
    
    async def save(self, category: Category) -> None:
        self._categories[category.id] = category
        if category.slug:
            self._by_slug[category.slug] = category.id
    
    async def get(self, category_id: str) -> Optional[Category]:
        return self._categories.get(category_id)
    
    async def get_by_slug(self, slug: str) -> Optional[Category]:
        cat_id = self._by_slug.get(slug)
        if cat_id:
            return self._categories.get(cat_id)
        return None
    
    async def list_all(self) -> List[Category]:
        return sorted(self._categories.values(), key=lambda c: c.order)


# Version store
class VersionStore(ABC):
    """Version storage."""
    
    @abstractmethod
    async def save(self, version: ArticleVersion) -> None:
        pass
    
    @abstractmethod
    async def list_by_article(self, article_id: str) -> List[ArticleVersion]:
        pass
    
    @abstractmethod
    async def get(self, version_id: str) -> Optional[ArticleVersion]:
        pass


class InMemoryVersionStore(VersionStore):
    """In-memory version store."""
    
    def __init__(self):
        self._versions: Dict[str, ArticleVersion] = {}
        self._by_article: Dict[str, List[str]] = {}
    
    async def save(self, version: ArticleVersion) -> None:
        self._versions[version.id] = version
        
        if version.article_id not in self._by_article:
            self._by_article[version.article_id] = []
        
        self._by_article[version.article_id].append(version.id)
    
    async def list_by_article(self, article_id: str) -> List[ArticleVersion]:
        version_ids = self._by_article.get(article_id, [])
        versions = [self._versions[vid] for vid in version_ids if vid in self._versions]
        return sorted(versions, key=lambda v: v.version, reverse=True)
    
    async def get(self, version_id: str) -> Optional[ArticleVersion]:
        return self._versions.get(version_id)


# Text utilities
class TextUtils:
    """Text utilities."""
    
    @staticmethod
    def slugify(text: str) -> str:
        """Convert text to slug."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        return text.strip("-")
    
    @staticmethod
    def generate_summary(content: str, max_length: int = 200) -> str:
        """Generate summary from content."""
        # Strip markdown/html
        text = re.sub(r"[#*_`\[\]()]", "", content)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        
        if len(text) <= max_length:
            return text
        
        # Find sentence boundary
        truncated = text[:max_length]
        last_period = truncated.rfind(".")
        last_space = truncated.rfind(" ")
        
        if last_period > max_length * 0.5:
            return truncated[:last_period + 1]
        elif last_space > 0:
            return truncated[:last_space] + "..."
        
        return truncated + "..."
    
    @staticmethod
    def extract_keywords(content: str, max_keywords: int = 10) -> List[str]:
        """Extract keywords from content."""
        # Simple word frequency
        words = re.findall(r"\b\w{4,}\b", content.lower())
        
        # Filter common words
        stopwords = {
            "this", "that", "with", "from", "have", "been", "will",
            "would", "could", "should", "what", "when", "where", "which",
            "their", "there", "these", "those", "about", "into", "your",
        }
        
        word_freq: Dict[str, int] = {}
        for word in words:
            if word not in stopwords:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:max_keywords]]


# Knowledge manager
class KnowledgeManager:
    """Knowledge manager."""
    
    def __init__(
        self,
        article_store: Optional[ArticleStore] = None,
        category_store: Optional[CategoryStore] = None,
        version_store: Optional[VersionStore] = None,
    ):
        self._article_store = article_store or InMemoryArticleStore()
        self._category_store = category_store or InMemoryCategoryStore()
        self._version_store = version_store or InMemoryVersionStore()
        self._listeners: List[Callable] = []
    
    async def add_article(
        self,
        title: str,
        content: str,
        category: str = "",
        article_type: ArticleType = ArticleType.ARTICLE,
        author: str = "",
        tags: Optional[List[str]] = None,
        status: ArticleStatus = ArticleStatus.DRAFT,
        **kwargs,
    ) -> Article:
        """Add article."""
        slug = TextUtils.slugify(title)
        summary = TextUtils.generate_summary(content)
        
        # Ensure unique slug
        existing = await self._article_store.get_by_slug(slug)
        if existing:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        
        article = Article(
            slug=slug,
            title=title,
            content=content,
            summary=summary,
            category=category,
            article_type=article_type,
            author=author,
            tags=tags or [],
            status=status,
            **kwargs,
        )
        
        await self._article_store.save(article)
        
        # Save initial version
        await self._save_version(article, "Initial version")
        
        # Update category count
        if category:
            cat = await self._category_store.get_by_slug(category)
            if cat:
                cat.article_count += 1
                await self._category_store.save(cat)
        
        logger.info(f"Article added: {title}")
        
        await self._notify("add", article)
        
        return article
    
    async def get_article(
        self,
        article_id: str,
        increment_views: bool = True,
    ) -> Optional[Article]:
        """Get article by ID."""
        article = await self._article_store.get(article_id)
        
        if article and increment_views:
            article.view_count += 1
            await self._article_store.save(article)
        
        return article
    
    async def get_by_slug(self, slug: str) -> Optional[Article]:
        """Get article by slug."""
        return await self._article_store.get_by_slug(slug)
    
    async def update_article(
        self,
        article_id: str,
        author: str = "",
        comment: str = "",
        **updates,
    ) -> Optional[Article]:
        """Update article."""
        article = await self._article_store.get(article_id)
        
        if not article:
            return None
        
        for key, value in updates.items():
            if hasattr(article, key):
                setattr(article, key, value)
        
        # Update summary if content changed
        if "content" in updates:
            article.summary = TextUtils.generate_summary(article.content)
        
        article.version += 1
        article.updated_at = datetime.utcnow()
        
        if author and author not in article.contributors:
            article.contributors.append(author)
        
        await self._article_store.save(article)
        
        # Save version
        await self._save_version(article, comment or "Updated")
        
        logger.info(f"Article updated: {article.title} (v{article.version})")
        
        await self._notify("update", article)
        
        return article
    
    async def publish(self, article_id: str) -> Optional[Article]:
        """Publish article."""
        article = await self._article_store.get(article_id)
        
        if not article:
            return None
        
        article.status = ArticleStatus.PUBLISHED
        article.published_at = datetime.utcnow()
        article.updated_at = datetime.utcnow()
        
        await self._article_store.save(article)
        
        logger.info(f"Article published: {article.title}")
        
        await self._notify("publish", article)
        
        return article
    
    async def archive(self, article_id: str) -> Optional[Article]:
        """Archive article."""
        article = await self._article_store.get(article_id)
        
        if not article:
            return None
        
        article.status = ArticleStatus.ARCHIVED
        article.updated_at = datetime.utcnow()
        
        await self._article_store.save(article)
        
        logger.info(f"Article archived: {article.title}")
        
        return article
    
    async def delete_article(self, article_id: str) -> bool:
        """Delete article."""
        article = await self._article_store.get(article_id)
        
        if not article:
            return False
        
        result = await self._article_store.delete(article_id)
        
        if result:
            logger.info(f"Article deleted: {article.title}")
            await self._notify("delete", article)
        
        return result
    
    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[SearchResult]:
        """Search articles."""
        results = await self._article_store.search(query)
        
        # Filter by category
        if category:
            filtered = []
            for result in results:
                article = await self._article_store.get(result.article_id)
                if article and article.category == category:
                    filtered.append(result)
            results = filtered
        
        # Filter by tags
        if tags:
            filtered = []
            for result in results:
                article = await self._article_store.get(result.article_id)
                if article and any(t in article.tags for t in tags):
                    filtered.append(result)
            results = filtered
        
        return results[:limit]
    
    async def list_articles(
        self,
        category: Optional[str] = None,
        status: Optional[ArticleStatus] = None,
        article_type: Optional[ArticleType] = None,
        author: Optional[str] = None,
        featured: Optional[bool] = None,
    ) -> List[Article]:
        """List articles with filters."""
        articles = await self._article_store.list_all()
        
        if category:
            articles = [a for a in articles if a.category == category]
        if status:
            articles = [a for a in articles if a.status == status]
        if article_type:
            articles = [a for a in articles if a.article_type == article_type]
        if author:
            articles = [a for a in articles if a.author == author]
        if featured is not None:
            articles = [a for a in articles if a.featured == featured]
        
        return sorted(articles, key=lambda a: a.updated_at, reverse=True)
    
    async def add_category(
        self,
        name: str,
        description: str = "",
        parent_id: Optional[str] = None,
        icon: str = "",
        order: int = 0,
    ) -> Category:
        """Add category."""
        slug = TextUtils.slugify(name)
        
        category = Category(
            name=name,
            slug=slug,
            description=description,
            parent_id=parent_id,
            icon=icon,
            order=order,
        )
        
        await self._category_store.save(category)
        
        logger.info(f"Category added: {name}")
        
        return category
    
    async def get_category(self, slug: str) -> Optional[Category]:
        """Get category by slug."""
        return await self._category_store.get_by_slug(slug)
    
    async def list_categories(
        self,
        parent_id: Optional[str] = None,
    ) -> List[Category]:
        """List categories."""
        categories = await self._category_store.list_all()
        
        if parent_id is not None:
            categories = [c for c in categories if c.parent_id == parent_id]
        
        return categories
    
    async def get_versions(self, article_id: str) -> List[ArticleVersion]:
        """Get article versions."""
        return await self._version_store.list_by_article(article_id)
    
    async def restore_version(
        self,
        article_id: str,
        version_id: str,
        author: str = "",
    ) -> Optional[Article]:
        """Restore article to specific version."""
        version = await self._version_store.get(version_id)
        
        if not version or version.article_id != article_id:
            return None
        
        return await self.update_article(
            article_id,
            title=version.title,
            content=version.content,
            author=author,
            comment=f"Restored from version {version.version}",
        )
    
    async def mark_helpful(
        self,
        article_id: str,
        helpful: bool,
    ) -> Optional[Article]:
        """Mark article as helpful/not helpful."""
        article = await self._article_store.get(article_id)
        
        if not article:
            return None
        
        if helpful:
            article.helpful_count += 1
        else:
            article.not_helpful_count += 1
        
        await self._article_store.save(article)
        
        return article
    
    async def get_related(
        self,
        article_id: str,
        limit: int = 5,
    ) -> List[Article]:
        """Get related articles."""
        article = await self._article_store.get(article_id)
        
        if not article:
            return []
        
        # Get explicitly related
        related = []
        for rel_id in article.related_articles:
            rel = await self._article_store.get(rel_id)
            if rel and rel.status == ArticleStatus.PUBLISHED:
                related.append(rel)
        
        # Find similar by category/tags
        if len(related) < limit:
            all_articles = await self._article_store.list_all()
            
            for art in all_articles:
                if art.id == article.id or art in related:
                    continue
                if art.status != ArticleStatus.PUBLISHED:
                    continue
                
                # Same category or shared tags
                if art.category == article.category:
                    related.append(art)
                elif any(t in article.tags for t in art.tags):
                    related.append(art)
                
                if len(related) >= limit:
                    break
        
        return related[:limit]
    
    async def get_stats(self) -> KnowledgeStats:
        """Get knowledge base statistics."""
        articles = await self._article_store.list_all()
        categories = await self._category_store.list_all()
        
        stats = KnowledgeStats(
            total_articles=len(articles),
            categories=len(categories),
        )
        
        published = [a for a in articles if a.status == ArticleStatus.PUBLISHED]
        drafts = [a for a in articles if a.status == ArticleStatus.DRAFT]
        
        stats.published = len(published)
        stats.draft = len(drafts)
        stats.total_views = sum(a.view_count for a in articles)
        
        # Most viewed
        by_views = sorted(articles, key=lambda a: a.view_count, reverse=True)
        stats.most_viewed = [a.id for a in by_views[:5]]
        
        # Recently updated
        by_updated = sorted(articles, key=lambda a: a.updated_at, reverse=True)
        stats.recently_updated = [a.id for a in by_updated[:5]]
        
        return stats
    
    async def _save_version(self, article: Article, comment: str) -> None:
        """Save article version."""
        version = ArticleVersion(
            article_id=article.id,
            version=article.version,
            title=article.title,
            content=article.content,
            author=article.author,
            comment=comment,
        )
        await self._version_store.save(version)
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    async def _notify(self, event: str, article: Article) -> None:
        """Notify listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, article)
                else:
                    listener(event, article)
            except Exception as e:
                logger.error(f"Listener error: {e}")


# Factory functions
def create_knowledge_manager() -> KnowledgeManager:
    """Create knowledge manager."""
    return KnowledgeManager()


def create_article(title: str, content: str, **kwargs) -> Article:
    """Create article."""
    return Article(title=title, content=content, **kwargs)


__all__ = [
    # Exceptions
    "KnowledgeError",
    # Enums
    "ArticleStatus",
    "ContentType",
    "ArticleType",
    # Data classes
    "Article",
    "Category",
    "SearchResult",
    "ArticleVersion",
    "KnowledgeStats",
    # Stores
    "ArticleStore",
    "InMemoryArticleStore",
    "CategoryStore",
    "InMemoryCategoryStore",
    "VersionStore",
    "InMemoryVersionStore",
    # Utilities
    "TextUtils",
    # Manager
    "KnowledgeManager",
    # Factory functions
    "create_knowledge_manager",
    "create_article",
]
