"""
Enterprise Release Manager Module.

Release planning, version management, release notes,
deployment coordination, and rollback management.

Example:
    # Create release manager
    releases = create_release_manager()
    
    # Create release
    release = await releases.create(
        name="v2.0.0",
        version="2.0.0",
        release_type=ReleaseType.MAJOR,
    )
    
    # Add features
    await releases.add_item(
        release_name="v2.0.0",
        title="New authentication system",
        item_type=ReleaseItemType.FEATURE,
    )
    
    # Finalize and publish
    await releases.finalize(release.id)
    await releases.publish(release.id)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)


class ReleaseError(Exception):
    """Release error."""
    pass


class ReleaseType(str, Enum):
    """Release type."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    HOTFIX = "hotfix"
    RC = "rc"  # Release candidate
    BETA = "beta"
    ALPHA = "alpha"


class ReleaseStatus(str, Enum):
    """Release status."""
    DRAFT = "draft"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    READY = "ready"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    RECALLED = "recalled"


class ReleaseItemType(str, Enum):
    """Release item type."""
    FEATURE = "feature"
    BUG_FIX = "bug_fix"
    IMPROVEMENT = "improvement"
    BREAKING_CHANGE = "breaking_change"
    DEPRECATION = "deprecation"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    OTHER = "other"


@dataclass
class ReleaseItem:
    """Release item (changelog entry)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    item_type: ReleaseItemType = ReleaseItemType.FEATURE
    issue_refs: List[str] = field(default_factory=list)
    pr_refs: List[str] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)
    breaking: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticVersion:
    """Semantic version."""
    major: int = 0
    minor: int = 0
    patch: int = 0
    prerelease: str = ""
    build: str = ""
    
    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        if self.build:
            version += f"+{self.build}"
        return version
    
    @classmethod
    def parse(cls, version_string: str) -> SemanticVersion:
        """Parse version string."""
        pattern = r'^(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9.-]+))?(?:\+([a-zA-Z0-9.-]+))?$'
        match = re.match(pattern, version_string)
        
        if not match:
            raise ValueError(f"Invalid version: {version_string}")
        
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4) or "",
            build=match.group(5) or "",
        )
    
    def bump(self, bump_type: str) -> SemanticVersion:
        """Bump version."""
        if bump_type == "major":
            return SemanticVersion(self.major + 1, 0, 0)
        elif bump_type == "minor":
            return SemanticVersion(self.major, self.minor + 1, 0)
        elif bump_type == "patch":
            return SemanticVersion(self.major, self.minor, self.patch + 1)
        return self
    
    def __lt__(self, other: SemanticVersion) -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)


@dataclass
class Artifact:
    """Release artifact."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    path: str = ""
    checksum: str = ""
    size: int = 0
    content_type: str = ""
    uploaded_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Environment:
    """Deployment environment."""
    name: str = ""
    deployed_version: str = ""
    deployed_at: Optional[datetime] = None
    status: str = "pending"
    url: str = ""


@dataclass
class Release:
    """Release."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    version: str = ""
    parsed_version: Optional[SemanticVersion] = None
    release_type: ReleaseType = ReleaseType.MINOR
    status: ReleaseStatus = ReleaseStatus.DRAFT
    
    # Content
    summary: str = ""
    description: str = ""
    items: List[ReleaseItem] = field(default_factory=list)
    
    # Artifacts
    artifacts: List[Artifact] = field(default_factory=list)
    
    # Environments
    environments: Dict[str, Environment] = field(default_factory=dict)
    
    # Dependencies
    previous_version: str = ""
    dependencies: List[str] = field(default_factory=list)
    
    # Dates
    created_at: datetime = field(default_factory=datetime.utcnow)
    planned_date: Optional[datetime] = None
    finalized_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    
    # Ownership
    owner: str = ""
    approvers: List[str] = field(default_factory=list)
    
    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.version and not self.parsed_version:
            try:
                self.parsed_version = SemanticVersion.parse(self.version)
            except ValueError:
                pass
    
    @property
    def has_breaking_changes(self) -> bool:
        return any(item.breaking for item in self.items)
    
    @property
    def changelog(self) -> str:
        """Generate changelog."""
        lines = [f"# {self.name}", ""]
        
        if self.summary:
            lines.extend([self.summary, ""])
        
        # Group items by type
        by_type: Dict[str, List[ReleaseItem]] = {}
        for item in self.items:
            item_type = item.item_type.value
            if item_type not in by_type:
                by_type[item_type] = []
            by_type[item_type].append(item)
        
        type_titles = {
            "breaking_change": "Breaking Changes",
            "security": "Security",
            "feature": "Features",
            "bug_fix": "Bug Fixes",
            "improvement": "Improvements",
            "performance": "Performance",
            "deprecation": "Deprecations",
            "documentation": "Documentation",
            "other": "Other Changes",
        }
        
        for item_type, title in type_titles.items():
            if item_type in by_type:
                lines.extend([f"## {title}", ""])
                for item in by_type[item_type]:
                    line = f"- {item.title}"
                    if item.issue_refs:
                        line += f" ({', '.join(item.issue_refs)})"
                    lines.append(line)
                lines.append("")
        
        return "\n".join(lines)


@dataclass
class ReleaseStats:
    """Release statistics."""
    total_releases: int = 0
    published_releases: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_status: Dict[str, int] = field(default_factory=dict)
    avg_items_per_release: float = 0.0


# Release store
class ReleaseStore(ABC):
    """Release storage."""
    
    @abstractmethod
    async def save(self, release: Release) -> None:
        pass
    
    @abstractmethod
    async def get(self, release_id: str) -> Optional[Release]:
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Release]:
        pass
    
    @abstractmethod
    async def get_by_version(self, version: str) -> Optional[Release]:
        pass
    
    @abstractmethod
    async def list_releases(
        self,
        status: Optional[List[ReleaseStatus]] = None,
        limit: int = 100,
    ) -> List[Release]:
        pass
    
    @abstractmethod
    async def delete(self, release_id: str) -> bool:
        pass


class InMemoryReleaseStore(ReleaseStore):
    """In-memory release store."""
    
    def __init__(self):
        self._releases: Dict[str, Release] = {}
        self._by_name: Dict[str, str] = {}
        self._by_version: Dict[str, str] = {}
    
    async def save(self, release: Release) -> None:
        self._releases[release.id] = release
        self._by_name[release.name] = release.id
        self._by_version[release.version] = release.id
    
    async def get(self, release_id: str) -> Optional[Release]:
        return self._releases.get(release_id)
    
    async def get_by_name(self, name: str) -> Optional[Release]:
        release_id = self._by_name.get(name)
        if release_id:
            return self._releases.get(release_id)
        return None
    
    async def get_by_version(self, version: str) -> Optional[Release]:
        release_id = self._by_version.get(version)
        if release_id:
            return self._releases.get(release_id)
        return None
    
    async def list_releases(
        self,
        status: Optional[List[ReleaseStatus]] = None,
        limit: int = 100,
    ) -> List[Release]:
        results = []
        
        for release in self._releases.values():
            if status and release.status not in status:
                continue
            results.append(release)
        
        results.sort(key=lambda r: r.created_at, reverse=True)
        return results[:limit]
    
    async def delete(self, release_id: str) -> bool:
        release = self._releases.get(release_id)
        if release:
            del self._releases[release_id]
            self._by_name.pop(release.name, None)
            self._by_version.pop(release.version, None)
            return True
        return False


# Release manager
class ReleaseManager:
    """Release manager."""
    
    def __init__(
        self,
        release_store: Optional[ReleaseStore] = None,
    ):
        self._release_store = release_store or InMemoryReleaseStore()
        self._listeners: List[Callable] = []
    
    async def create(
        self,
        name: str,
        version: str,
        release_type: Union[str, ReleaseType] = ReleaseType.MINOR,
        summary: str = "",
        description: str = "",
        owner: str = "",
        planned_date: Optional[datetime] = None,
        previous_version: str = "",
        **metadata,
    ) -> Release:
        """Create release."""
        if isinstance(release_type, str):
            release_type = ReleaseType(release_type)
        
        # Parse version
        parsed_version = None
        try:
            parsed_version = SemanticVersion.parse(version)
        except ValueError:
            pass
        
        release = Release(
            name=name,
            version=version,
            parsed_version=parsed_version,
            release_type=release_type,
            summary=summary,
            description=description,
            owner=owner,
            planned_date=planned_date,
            previous_version=previous_version,
            metadata=metadata,
        )
        
        await self._release_store.save(release)
        
        logger.info(f"Release created: {name} ({version})")
        
        await self._notify_listeners("created", release)
        
        return release
    
    async def get(self, release_id: str) -> Optional[Release]:
        """Get release by ID."""
        return await self._release_store.get(release_id)
    
    async def get_by_name(self, name: str) -> Optional[Release]:
        """Get release by name."""
        return await self._release_store.get_by_name(name)
    
    async def get_by_version(self, version: str) -> Optional[Release]:
        """Get release by version."""
        return await self._release_store.get_by_version(version)
    
    async def update(
        self,
        release_id: str,
        **updates,
    ) -> Optional[Release]:
        """Update release."""
        release = await self._release_store.get(release_id)
        
        if not release:
            return None
        
        if release.status in (ReleaseStatus.PUBLISHED, ReleaseStatus.DEPRECATED):
            raise ReleaseError("Cannot update published or deprecated release")
        
        for key, value in updates.items():
            if hasattr(release, key):
                setattr(release, key, value)
        
        await self._release_store.save(release)
        
        return release
    
    async def add_item(
        self,
        release_name: str,
        title: str,
        item_type: Union[str, ReleaseItemType] = ReleaseItemType.FEATURE,
        description: str = "",
        issue_refs: Optional[List[str]] = None,
        pr_refs: Optional[List[str]] = None,
        authors: Optional[List[str]] = None,
        breaking: bool = False,
    ) -> Optional[ReleaseItem]:
        """Add item to release."""
        release = await self._release_store.get_by_name(release_name)
        
        if not release:
            return None
        
        if isinstance(item_type, str):
            item_type = ReleaseItemType(item_type)
        
        item = ReleaseItem(
            title=title,
            description=description,
            item_type=item_type,
            issue_refs=issue_refs or [],
            pr_refs=pr_refs or [],
            authors=authors or [],
            breaking=breaking,
        )
        
        release.items.append(item)
        
        await self._release_store.save(release)
        
        return item
    
    async def remove_item(
        self,
        release_name: str,
        item_id: str,
    ) -> bool:
        """Remove item from release."""
        release = await self._release_store.get_by_name(release_name)
        
        if not release:
            return False
        
        original_count = len(release.items)
        release.items = [i for i in release.items if i.id != item_id]
        
        if len(release.items) < original_count:
            await self._release_store.save(release)
            return True
        
        return False
    
    async def add_artifact(
        self,
        release_name: str,
        name: str,
        path: str,
        checksum: str = "",
        size: int = 0,
        content_type: str = "",
    ) -> Optional[Artifact]:
        """Add artifact to release."""
        release = await self._release_store.get_by_name(release_name)
        
        if not release:
            return None
        
        artifact = Artifact(
            name=name,
            path=path,
            checksum=checksum,
            size=size,
            content_type=content_type,
        )
        
        release.artifacts.append(artifact)
        
        await self._release_store.save(release)
        
        return artifact
    
    async def update_status(
        self,
        release_id: str,
        status: Union[str, ReleaseStatus],
    ) -> Optional[Release]:
        """Update release status."""
        if isinstance(status, str):
            status = ReleaseStatus(status)
        
        release = await self._release_store.get(release_id)
        
        if not release:
            return None
        
        old_status = release.status
        release.status = status
        
        await self._release_store.save(release)
        
        logger.info(f"Release {release.name} status: {old_status.value} -> {status.value}")
        
        await self._notify_listeners("status_changed", release)
        
        return release
    
    async def finalize(self, release_id: str) -> Optional[Release]:
        """Finalize release (lock for publishing)."""
        release = await self._release_store.get(release_id)
        
        if not release:
            return None
        
        if release.status == ReleaseStatus.PUBLISHED:
            raise ReleaseError("Release already published")
        
        release.status = ReleaseStatus.READY
        release.finalized_at = datetime.utcnow()
        
        await self._release_store.save(release)
        
        await self._notify_listeners("finalized", release)
        
        return release
    
    async def publish(
        self,
        release_id: str,
    ) -> Optional[Release]:
        """Publish release."""
        release = await self._release_store.get(release_id)
        
        if not release:
            return None
        
        if release.status not in (ReleaseStatus.READY, ReleaseStatus.DRAFT):
            raise ReleaseError(f"Cannot publish release in {release.status.value} status")
        
        release.status = ReleaseStatus.PUBLISHED
        release.published_at = datetime.utcnow()
        
        await self._release_store.save(release)
        
        logger.info(f"Release published: {release.name}")
        
        await self._notify_listeners("published", release)
        
        return release
    
    async def deprecate(
        self,
        release_id: str,
        reason: str = "",
    ) -> Optional[Release]:
        """Deprecate release."""
        release = await self._release_store.get(release_id)
        
        if not release:
            return None
        
        release.status = ReleaseStatus.DEPRECATED
        release.metadata["deprecation_reason"] = reason
        release.metadata["deprecated_at"] = datetime.utcnow().isoformat()
        
        await self._release_store.save(release)
        
        await self._notify_listeners("deprecated", release)
        
        return release
    
    async def recall(
        self,
        release_id: str,
        reason: str,
    ) -> Optional[Release]:
        """Recall a published release."""
        release = await self._release_store.get(release_id)
        
        if not release:
            return None
        
        if release.status != ReleaseStatus.PUBLISHED:
            raise ReleaseError("Can only recall published releases")
        
        release.status = ReleaseStatus.RECALLED
        release.metadata["recall_reason"] = reason
        release.metadata["recalled_at"] = datetime.utcnow().isoformat()
        
        await self._release_store.save(release)
        
        logger.warning(f"Release recalled: {release.name} - {reason}")
        
        await self._notify_listeners("recalled", release)
        
        return release
    
    async def deploy_to_environment(
        self,
        release_id: str,
        environment: str,
        url: str = "",
    ) -> Optional[Release]:
        """Deploy release to environment."""
        release = await self._release_store.get(release_id)
        
        if not release:
            return None
        
        release.environments[environment] = Environment(
            name=environment,
            deployed_version=release.version,
            deployed_at=datetime.utcnow(),
            status="deployed",
            url=url,
        )
        
        await self._release_store.save(release)
        
        logger.info(f"Release {release.name} deployed to {environment}")
        
        await self._notify_listeners("deployed", release)
        
        return release
    
    async def list_releases(
        self,
        status: Optional[List[ReleaseStatus]] = None,
        limit: int = 100,
    ) -> List[Release]:
        """List releases."""
        return await self._release_store.list_releases(status, limit)
    
    async def get_latest(self) -> Optional[Release]:
        """Get latest published release."""
        releases = await self._release_store.list_releases(
            status=[ReleaseStatus.PUBLISHED],
            limit=1,
        )
        return releases[0] if releases else None
    
    async def get_changelog(
        self,
        from_version: Optional[str] = None,
        to_version: Optional[str] = None,
    ) -> str:
        """Get combined changelog."""
        releases = await self._release_store.list_releases(
            status=[ReleaseStatus.PUBLISHED],
        )
        
        # Sort by version
        releases = sorted(
            releases,
            key=lambda r: r.parsed_version or SemanticVersion(0, 0, 0),
            reverse=True,
        )
        
        # Filter by version range
        if from_version:
            from_v = SemanticVersion.parse(from_version)
            releases = [r for r in releases if r.parsed_version and r.parsed_version > from_v]
        
        if to_version:
            to_v = SemanticVersion.parse(to_version)
            releases = [r for r in releases if r.parsed_version and r.parsed_version <= to_v]
        
        changelogs = [release.changelog for release in releases]
        return "\n---\n\n".join(changelogs)
    
    async def suggest_next_version(
        self,
        bump_type: Optional[str] = None,
    ) -> str:
        """Suggest next version based on latest release."""
        latest = await self.get_latest()
        
        if not latest or not latest.parsed_version:
            return "1.0.0"
        
        bump = bump_type or "patch"
        next_version = latest.parsed_version.bump(bump)
        
        return str(next_version)
    
    async def get_stats(self) -> ReleaseStats:
        """Get release statistics."""
        releases = await self._release_store.list_releases(limit=10000)
        
        stats = ReleaseStats(total_releases=len(releases))
        
        total_items = 0
        
        for release in releases:
            # By status
            status = release.status.value
            stats.by_status[status] = stats.by_status.get(status, 0) + 1
            
            if release.status == ReleaseStatus.PUBLISHED:
                stats.published_releases += 1
            
            # By type
            rtype = release.release_type.value
            stats.by_type[rtype] = stats.by_type.get(rtype, 0) + 1
            
            total_items += len(release.items)
        
        if releases:
            stats.avg_items_per_release = total_items / len(releases)
        
        return stats
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    async def _notify_listeners(self, event: str, release: Release) -> None:
        """Notify listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, release)
                else:
                    listener(event, release)
            except Exception as e:
                logger.error(f"Listener error: {e}")


# Factory functions
def create_release_manager() -> ReleaseManager:
    """Create release manager."""
    return ReleaseManager()


def create_release(
    name: str,
    version: str,
    **kwargs,
) -> Release:
    """Create release."""
    return Release(name=name, version=version, **kwargs)


def parse_version(version_string: str) -> SemanticVersion:
    """Parse semantic version."""
    return SemanticVersion.parse(version_string)


__all__ = [
    # Exceptions
    "ReleaseError",
    # Enums
    "ReleaseType",
    "ReleaseStatus",
    "ReleaseItemType",
    # Data classes
    "ReleaseItem",
    "SemanticVersion",
    "Artifact",
    "Environment",
    "Release",
    "ReleaseStats",
    # Stores
    "ReleaseStore",
    "InMemoryReleaseStore",
    # Manager
    "ReleaseManager",
    # Factory functions
    "create_release_manager",
    "create_release",
    "parse_version",
]
