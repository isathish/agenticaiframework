"""
Enterprise Content Manager Module.

CMS, content versioning, rich media handling,
drafts, publishing, and content lifecycle.

Example:
    # Create content manager
    cms = create_content_manager()
    
    # Create content
    content = await cms.create(
        title="Getting Started Guide",
        type="article",
        body="Welcome to our platform...",
        author_id="user_123",
    )
    
    # Create draft
    draft = await cms.create_draft(content.id, body="Updated content...")
    
    # Publish
    await cms.publish(content.id)
    
    # Get published content
    article = await cms.get_published(content.slug)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class ContentError(Exception):
    """Content error."""
    pass


class ContentNotFoundError(ContentError):
    """Content not found."""
    pass


class VersionNotFoundError(ContentError):
    """Version not found."""
    pass


class ContentStatus(str, Enum):
    """Content status."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    SCHEDULED = "scheduled"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ContentType(str, Enum):
    """Content type."""
    ARTICLE = "article"
    PAGE = "page"
    POST = "post"
    NEWS = "news"
    FAQ = "faq"
    DOCUMENTATION = "documentation"
    PRODUCT = "product"
    LANDING_PAGE = "landing_page"


class MediaType(str, Enum):
    """Media type."""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    FILE = "file"


@dataclass
class Media:
    """Media asset."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: MediaType = MediaType.IMAGE
    mime_type: str = ""
    url: str = ""
    thumbnail_url: str = ""
    size: int = 0
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    alt_text: str = ""
    caption: str = ""
    folder: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    uploaded_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ContentVersion:
    """Content version."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content_id: str = ""
    version: int = 1
    title: str = ""
    body: str = ""
    excerpt: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    author_id: str = ""
    change_log: str = ""
    checksum: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Content:
    """Content item."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: ContentType = ContentType.ARTICLE
    title: str = ""
    slug: str = ""
    body: str = ""
    excerpt: str = ""
    status: ContentStatus = ContentStatus.DRAFT
    author_id: str = ""
    featured_image: Optional[Media] = None
    media: List[Media] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    seo_title: str = ""
    seo_description: str = ""
    seo_keywords: List[str] = field(default_factory=list)
    version: int = 1
    draft_version: Optional[int] = None
    locale: str = "en"
    translations: Dict[str, str] = field(default_factory=dict)
    template: str = ""
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    published_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ContentFilter:
    """Content query filter."""
    type: Optional[ContentType] = None
    status: Optional[ContentStatus] = None
    author_id: Optional[str] = None
    category: Optional[str] = None
    tag: Optional[str] = None
    locale: Optional[str] = None
    search: Optional[str] = None


@dataclass
class ContentStats:
    """Content statistics."""
    total_content: int = 0
    published: int = 0
    drafts: int = 0
    total_media: int = 0


# Content store
class ContentStore(ABC):
    """Content storage."""
    
    @abstractmethod
    async def save(self, content: Content) -> None:
        pass
    
    @abstractmethod
    async def get(self, content_id: str) -> Optional[Content]:
        pass
    
    @abstractmethod
    async def get_by_slug(self, slug: str) -> Optional[Content]:
        pass
    
    @abstractmethod
    async def query(self, filter: ContentFilter) -> List[Content]:
        pass
    
    @abstractmethod
    async def delete(self, content_id: str) -> bool:
        pass


class InMemoryContentStore(ContentStore):
    """In-memory content store."""
    
    def __init__(self):
        self._content: Dict[str, Content] = {}
        self._slug_index: Dict[str, str] = {}
    
    async def save(self, content: Content) -> None:
        content.updated_at = datetime.utcnow()
        self._content[content.id] = content
        self._slug_index[content.slug] = content.id
    
    async def get(self, content_id: str) -> Optional[Content]:
        return self._content.get(content_id)
    
    async def get_by_slug(self, slug: str) -> Optional[Content]:
        content_id = self._slug_index.get(slug)
        return self._content.get(content_id) if content_id else None
    
    async def query(self, filter: ContentFilter) -> List[Content]:
        results = list(self._content.values())
        
        if filter.type:
            results = [c for c in results if c.type == filter.type]
        if filter.status:
            results = [c for c in results if c.status == filter.status]
        if filter.author_id:
            results = [c for c in results if c.author_id == filter.author_id]
        if filter.category:
            results = [c for c in results if filter.category in c.categories]
        if filter.tag:
            results = [c for c in results if filter.tag in c.tags]
        if filter.locale:
            results = [c for c in results if c.locale == filter.locale]
        if filter.search:
            search_lower = filter.search.lower()
            results = [
                c for c in results
                if search_lower in c.title.lower() or search_lower in c.body.lower()
            ]
        
        return sorted(results, key=lambda c: c.updated_at, reverse=True)
    
    async def delete(self, content_id: str) -> bool:
        if content_id in self._content:
            content = self._content[content_id]
            del self._slug_index[content.slug]
            del self._content[content_id]
            return True
        return False


# Content manager
class ContentManager:
    """Content manager."""
    
    def __init__(
        self,
        content_store: Optional[ContentStore] = None,
    ):
        self._content = content_store or InMemoryContentStore()
        self._versions: Dict[str, List[ContentVersion]] = {}
        self._media: Dict[str, Media] = {}
        self._stats = ContentStats()
    
    async def create(
        self,
        title: str,
        type: ContentType = ContentType.ARTICLE,
        body: str = "",
        author_id: str = "",
        slug: Optional[str] = None,
        **kwargs,
    ) -> Content:
        """Create content."""
        # Generate slug
        content_slug = slug or self._generate_slug(title)
        
        # Ensure unique slug
        existing = await self._content.get_by_slug(content_slug)
        if existing:
            content_slug = f"{content_slug}-{uuid.uuid4().hex[:6]}"
        
        content = Content(
            type=type,
            title=title,
            slug=content_slug,
            body=body,
            author_id=author_id,
            status=ContentStatus.DRAFT,
            **kwargs,
        )
        
        await self._content.save(content)
        
        # Create initial version
        await self._create_version(content, "Initial creation")
        
        self._stats.total_content += 1
        self._stats.drafts += 1
        
        logger.info(f"Content created: {content.slug}")
        
        return content
    
    async def get(self, content_id: str) -> Optional[Content]:
        """Get content by ID."""
        return await self._content.get(content_id)
    
    async def get_by_slug(self, slug: str) -> Optional[Content]:
        """Get content by slug."""
        return await self._content.get_by_slug(slug)
    
    async def get_published(self, slug: str) -> Optional[Content]:
        """Get published content by slug."""
        content = await self._content.get_by_slug(slug)
        if content and content.status == ContentStatus.PUBLISHED:
            return content
        return None
    
    async def update(
        self,
        content_id: str,
        change_log: str = "",
        **updates,
    ) -> Optional[Content]:
        """Update content."""
        content = await self._content.get(content_id)
        if not content:
            return None
        
        for key, value in updates.items():
            if hasattr(content, key):
                setattr(content, key, value)
        
        content.version += 1
        
        await self._content.save(content)
        await self._create_version(content, change_log)
        
        return content
    
    async def create_draft(
        self,
        content_id: str,
        **updates,
    ) -> Optional[Content]:
        """Create draft version."""
        content = await self._content.get(content_id)
        if not content:
            return None
        
        # Store draft data in metadata
        draft_data = {
            "title": updates.get("title", content.title),
            "body": updates.get("body", content.body),
            "excerpt": updates.get("excerpt", content.excerpt),
            **updates,
        }
        
        content.metadata["draft"] = draft_data
        content.draft_version = content.version + 1
        
        await self._content.save(content)
        
        return content
    
    async def discard_draft(self, content_id: str) -> bool:
        """Discard draft changes."""
        content = await self._content.get(content_id)
        if not content:
            return False
        
        if "draft" in content.metadata:
            del content.metadata["draft"]
        content.draft_version = None
        
        await self._content.save(content)
        
        return True
    
    async def publish(
        self,
        content_id: str,
        publish_draft: bool = True,
    ) -> Optional[Content]:
        """Publish content."""
        content = await self._content.get(content_id)
        if not content:
            return None
        
        # Apply draft if exists
        if publish_draft and "draft" in content.metadata:
            draft = content.metadata["draft"]
            for key, value in draft.items():
                if hasattr(content, key):
                    setattr(content, key, value)
            del content.metadata["draft"]
            content.draft_version = None
        
        content.status = ContentStatus.PUBLISHED
        content.published_at = datetime.utcnow()
        content.version += 1
        
        await self._content.save(content)
        await self._create_version(content, "Published")
        
        self._stats.published += 1
        self._stats.drafts -= 1
        
        logger.info(f"Content published: {content.slug}")
        
        return content
    
    async def unpublish(self, content_id: str) -> Optional[Content]:
        """Unpublish content."""
        content = await self._content.get(content_id)
        if not content:
            return None
        
        content.status = ContentStatus.DRAFT
        
        await self._content.save(content)
        
        self._stats.published -= 1
        self._stats.drafts += 1
        
        return content
    
    async def schedule(
        self,
        content_id: str,
        publish_at: datetime,
    ) -> Optional[Content]:
        """Schedule content for publishing."""
        content = await self._content.get(content_id)
        if not content:
            return None
        
        content.status = ContentStatus.SCHEDULED
        content.scheduled_at = publish_at
        
        await self._content.save(content)
        
        logger.info(f"Content scheduled: {content.slug} at {publish_at}")
        
        return content
    
    async def archive(self, content_id: str) -> Optional[Content]:
        """Archive content."""
        content = await self._content.get(content_id)
        if not content:
            return None
        
        content.status = ContentStatus.ARCHIVED
        
        await self._content.save(content)
        
        return content
    
    async def delete(self, content_id: str, soft: bool = True) -> bool:
        """Delete content."""
        if soft:
            content = await self._content.get(content_id)
            if not content:
                return False
            
            content.status = ContentStatus.DELETED
            await self._content.save(content)
            return True
        
        return await self._content.delete(content_id)
    
    async def restore(self, content_id: str) -> Optional[Content]:
        """Restore deleted content."""
        content = await self._content.get(content_id)
        if not content:
            return None
        
        content.status = ContentStatus.DRAFT
        await self._content.save(content)
        
        return content
    
    async def query(
        self,
        type: Optional[ContentType] = None,
        status: Optional[ContentStatus] = None,
        author_id: Optional[str] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Content]:
        """Query content."""
        filter = ContentFilter(
            type=type,
            status=status,
            author_id=author_id,
            category=category,
            tag=tag,
            search=search,
        )
        return await self._content.query(filter)
    
    # Version management
    async def _create_version(
        self,
        content: Content,
        change_log: str = "",
    ) -> ContentVersion:
        """Create content version."""
        version = ContentVersion(
            content_id=content.id,
            version=content.version,
            title=content.title,
            body=content.body,
            excerpt=content.excerpt,
            metadata=dict(content.metadata),
            author_id=content.author_id,
            change_log=change_log,
            checksum=self._compute_checksum(content),
        )
        
        if content.id not in self._versions:
            self._versions[content.id] = []
        self._versions[content.id].append(version)
        
        return version
    
    async def get_versions(self, content_id: str) -> List[ContentVersion]:
        """Get content versions."""
        return sorted(
            self._versions.get(content_id, []),
            key=lambda v: v.version,
            reverse=True,
        )
    
    async def get_version(
        self,
        content_id: str,
        version: int,
    ) -> Optional[ContentVersion]:
        """Get specific version."""
        versions = self._versions.get(content_id, [])
        for v in versions:
            if v.version == version:
                return v
        return None
    
    async def revert_to_version(
        self,
        content_id: str,
        version: int,
    ) -> Optional[Content]:
        """Revert to specific version."""
        content = await self._content.get(content_id)
        if not content:
            return None
        
        target = await self.get_version(content_id, version)
        if not target:
            raise VersionNotFoundError(f"Version not found: {version}")
        
        content.title = target.title
        content.body = target.body
        content.excerpt = target.excerpt
        content.version += 1
        
        await self._content.save(content)
        await self._create_version(content, f"Reverted to version {version}")
        
        return content
    
    async def diff_versions(
        self,
        content_id: str,
        version1: int,
        version2: int,
    ) -> Dict[str, Any]:
        """Compare two versions."""
        v1 = await self.get_version(content_id, version1)
        v2 = await self.get_version(content_id, version2)
        
        if not v1 or not v2:
            return {}
        
        return {
            "title_changed": v1.title != v2.title,
            "body_changed": v1.body != v2.body,
            "from_version": version1,
            "to_version": version2,
        }
    
    # Media management
    async def upload_media(
        self,
        name: str,
        url: str,
        type: MediaType = MediaType.IMAGE,
        mime_type: str = "",
        size: int = 0,
        uploaded_by: str = "",
        **kwargs,
    ) -> Media:
        """Upload media."""
        media = Media(
            name=name,
            url=url,
            type=type,
            mime_type=mime_type,
            size=size,
            uploaded_by=uploaded_by,
            **kwargs,
        )
        self._media[media.id] = media
        self._stats.total_media += 1
        
        return media
    
    async def get_media(self, media_id: str) -> Optional[Media]:
        """Get media."""
        return self._media.get(media_id)
    
    async def list_media(
        self,
        type: Optional[MediaType] = None,
        folder: Optional[str] = None,
    ) -> List[Media]:
        """List media."""
        media = list(self._media.values())
        
        if type:
            media = [m for m in media if m.type == type]
        if folder:
            media = [m for m in media if m.folder == folder]
        
        return sorted(media, key=lambda m: m.created_at, reverse=True)
    
    async def attach_media(
        self,
        content_id: str,
        media_id: str,
    ) -> bool:
        """Attach media to content."""
        content = await self._content.get(content_id)
        media = self._media.get(media_id)
        
        if not content or not media:
            return False
        
        content.media.append(media)
        await self._content.save(content)
        
        return True
    
    def _generate_slug(self, title: str) -> str:
        """Generate URL slug from title."""
        slug = title.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')
    
    def _compute_checksum(self, content: Content) -> str:
        """Compute content checksum."""
        data = f"{content.title}:{content.body}:{content.excerpt}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def get_stats(self) -> ContentStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_content_manager() -> ContentManager:
    """Create content manager."""
    return ContentManager()


def create_content(
    title: str,
    type: ContentType = ContentType.ARTICLE,
    **kwargs,
) -> Content:
    """Create content."""
    return Content(title=title, type=type, **kwargs)


def create_media(
    name: str,
    url: str,
    type: MediaType = MediaType.IMAGE,
    **kwargs,
) -> Media:
    """Create media."""
    return Media(name=name, url=url, type=type, **kwargs)


__all__ = [
    # Exceptions
    "ContentError",
    "ContentNotFoundError",
    "VersionNotFoundError",
    # Enums
    "ContentStatus",
    "ContentType",
    "MediaType",
    # Data classes
    "Media",
    "ContentVersion",
    "Content",
    "ContentFilter",
    "ContentStats",
    # Stores
    "ContentStore",
    "InMemoryContentStore",
    # Manager
    "ContentManager",
    # Factory functions
    "create_content_manager",
    "create_content",
    "create_media",
]
