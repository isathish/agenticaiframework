"""
Enterprise API Lifecycle Manager Module.

API version lifecycle management, deprecation policies,
migration paths, and consumer notification.

Example:
    # Create API lifecycle manager
    api_mgr = create_api_lifecycle_manager()
    
    # Register API version
    await api_mgr.register_version(
        api="users",
        version="2.0",
        status=VersionStatus.STABLE,
    )
    
    # Deprecate old version
    await api_mgr.deprecate_version(
        api="users",
        version="1.0",
        sunset_date=datetime(2025, 1, 1),
        migration_guide="Use /v2/users instead",
    )
    
    # Check version status
    info = await api_mgr.get_version_info("users", "1.0")
"""

from __future__ import annotations

import asyncio
import logging
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
)

logger = logging.getLogger(__name__)


class APILifecycleError(Exception):
    """API lifecycle error."""
    pass


class VersionNotFoundError(APILifecycleError):
    """Version not found error."""
    pass


class APINotFoundError(APILifecycleError):
    """API not found error."""
    pass


class VersionStatus(str, Enum):
    """API version status."""
    PREVIEW = "preview"
    BETA = "beta"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    RETIRED = "retired"


class BreakingChangeType(str, Enum):
    """Breaking change types."""
    REMOVED_ENDPOINT = "removed_endpoint"
    REMOVED_FIELD = "removed_field"
    TYPE_CHANGE = "type_change"
    REQUIRED_FIELD = "required_field"
    BEHAVIOR_CHANGE = "behavior_change"
    AUTH_CHANGE = "auth_change"


class MigrationDifficulty(str, Enum):
    """Migration difficulty levels."""
    TRIVIAL = "trivial"
    EASY = "easy"
    MODERATE = "moderate"
    DIFFICULT = "difficult"
    COMPLEX = "complex"


@dataclass
class BreakingChange:
    """Breaking change description."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    change_type: BreakingChangeType = BreakingChangeType.BEHAVIOR_CHANGE
    
    # Location
    endpoint: str = ""
    field_path: str = ""
    
    # Description
    description: str = ""
    migration_steps: List[str] = field(default_factory=list)
    
    # Impact
    difficulty: MigrationDifficulty = MigrationDifficulty.MODERATE
    estimated_effort_hours: float = 0.0


@dataclass
class MigrationPath:
    """Migration path between versions."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    from_version: str = ""
    to_version: str = ""
    
    # Changes
    breaking_changes: List[BreakingChange] = field(default_factory=list)
    
    # Guide
    migration_guide: str = ""
    code_samples: Dict[str, str] = field(default_factory=dict)
    documentation_url: str = ""
    
    # Effort
    estimated_hours: float = 0.0
    difficulty: MigrationDifficulty = MigrationDifficulty.MODERATE
    
    # Automation
    automated_migration_available: bool = False
    migration_script_url: str = ""


@dataclass
class DeprecationNotice:
    """Deprecation notice."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    api_name: str = ""
    version: str = ""
    
    # Dates
    deprecated_at: datetime = field(default_factory=datetime.utcnow)
    sunset_date: Optional[datetime] = None
    
    # Reason
    reason: str = ""
    
    # Migration
    recommended_version: str = ""
    migration_guide: str = ""
    
    # Notifications
    notified_consumers: Set[str] = field(default_factory=set)


@dataclass
class APIVersion:
    """API version."""
    api_name: str = ""
    version: str = ""
    
    # Status
    status: VersionStatus = VersionStatus.PREVIEW
    
    # Dates
    created_at: datetime = field(default_factory=datetime.utcnow)
    released_at: Optional[datetime] = None
    deprecated_at: Optional[datetime] = None
    sunset_date: Optional[datetime] = None
    retired_at: Optional[datetime] = None
    
    # Info
    description: str = ""
    changelog: str = ""
    documentation_url: str = ""
    
    # Deprecation
    deprecation_notice: Optional[DeprecationNotice] = None
    
    # Metrics
    request_count: int = 0
    unique_consumers: Set[str] = field(default_factory=set)
    last_request_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIDefinition:
    """API definition."""
    name: str = ""
    description: str = ""
    
    # Versions
    versions: Dict[str, APIVersion] = field(default_factory=dict)
    current_version: str = ""
    
    # Owner
    owner: str = ""
    team: str = ""
    
    # Policies
    min_deprecation_days: int = 90
    min_sunset_days: int = 180
    
    # Metadata
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Consumer:
    """API consumer."""
    id: str = ""
    name: str = ""
    
    # Contact
    email: str = ""
    team: str = ""
    
    # Usage
    apis_used: Dict[str, Set[str]] = field(default_factory=dict)  # api -> versions
    
    # Preferences
    notification_preferences: Dict[str, bool] = field(default_factory=dict)


@dataclass
class VersionStats:
    """Version statistics."""
    api_name: str = ""
    version: str = ""
    
    request_count: int = 0
    unique_consumers: int = 0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    
    last_request_at: Optional[datetime] = None
    days_since_last_request: int = 0


# Storage
class APILifecycleStore(ABC):
    """API lifecycle storage."""
    
    @abstractmethod
    async def save_api(self, api: APIDefinition) -> None:
        pass
    
    @abstractmethod
    async def get_api(self, name: str) -> Optional[APIDefinition]:
        pass
    
    @abstractmethod
    async def list_apis(self) -> List[APIDefinition]:
        pass
    
    @abstractmethod
    async def save_migration_path(self, path: MigrationPath) -> None:
        pass
    
    @abstractmethod
    async def get_migration_path(self, api: str, from_version: str, to_version: str) -> Optional[MigrationPath]:
        pass
    
    @abstractmethod
    async def save_consumer(self, consumer: Consumer) -> None:
        pass
    
    @abstractmethod
    async def get_consumers_for_api(self, api: str, version: str) -> List[Consumer]:
        pass


class InMemoryAPILifecycleStore(APILifecycleStore):
    """In-memory storage."""
    
    def __init__(self):
        self._apis: Dict[str, APIDefinition] = {}
        self._migration_paths: Dict[str, MigrationPath] = {}
        self._consumers: Dict[str, Consumer] = {}
    
    async def save_api(self, api: APIDefinition) -> None:
        self._apis[api.name] = api
    
    async def get_api(self, name: str) -> Optional[APIDefinition]:
        return self._apis.get(name)
    
    async def list_apis(self) -> List[APIDefinition]:
        return list(self._apis.values())
    
    async def save_migration_path(self, path: MigrationPath) -> None:
        key = f"{path.from_version}:{path.to_version}"
        self._migration_paths[key] = path
    
    async def get_migration_path(self, api: str, from_version: str, to_version: str) -> Optional[MigrationPath]:
        key = f"{from_version}:{to_version}"
        return self._migration_paths.get(key)
    
    async def save_consumer(self, consumer: Consumer) -> None:
        self._consumers[consumer.id] = consumer
    
    async def get_consumers_for_api(self, api: str, version: str) -> List[Consumer]:
        consumers = []
        
        for consumer in self._consumers.values():
            api_versions = consumer.apis_used.get(api, set())
            if version in api_versions:
                consumers.append(consumer)
        
        return consumers


# Notification service
class NotificationService(ABC):
    """Notification service."""
    
    @abstractmethod
    async def notify_deprecation(
        self,
        consumer: Consumer,
        notice: DeprecationNotice,
    ) -> bool:
        pass
    
    @abstractmethod
    async def notify_sunset(
        self,
        consumer: Consumer,
        api: str,
        version: str,
        sunset_date: datetime,
    ) -> bool:
        pass


class LoggingNotificationService(NotificationService):
    """Logging notification service."""
    
    async def notify_deprecation(
        self,
        consumer: Consumer,
        notice: DeprecationNotice,
    ) -> bool:
        logger.info(
            f"Notifying {consumer.email} about deprecation of "
            f"{notice.api_name} v{notice.version}"
        )
        return True
    
    async def notify_sunset(
        self,
        consumer: Consumer,
        api: str,
        version: str,
        sunset_date: datetime,
    ) -> bool:
        logger.info(
            f"Notifying {consumer.email} about sunset of "
            f"{api} v{version} on {sunset_date}"
        )
        return True


# Version checker
class VersionChecker:
    """Check API version status."""
    
    def __init__(self, store: APILifecycleStore):
        self._store = store
    
    async def check_version(self, api: str, version: str) -> Dict[str, Any]:
        """Check version status and recommendations."""
        api_def = await self._store.get_api(api)
        
        if not api_def:
            return {"error": f"API not found: {api}"}
        
        ver = api_def.versions.get(version)
        
        if not ver:
            return {"error": f"Version not found: {version}"}
        
        result: Dict[str, Any] = {
            "api": api,
            "version": version,
            "status": ver.status.value,
            "is_stable": ver.status == VersionStatus.STABLE,
            "is_deprecated": ver.status in (VersionStatus.DEPRECATED, VersionStatus.SUNSET),
            "current_version": api_def.current_version,
            "needs_upgrade": version != api_def.current_version,
        }
        
        if ver.status == VersionStatus.DEPRECATED:
            result["deprecation"] = {
                "deprecated_at": ver.deprecated_at.isoformat() if ver.deprecated_at else None,
                "sunset_date": ver.sunset_date.isoformat() if ver.sunset_date else None,
                "days_until_sunset": (ver.sunset_date - datetime.utcnow()).days if ver.sunset_date else None,
            }
            
            if ver.deprecation_notice:
                result["migration"] = {
                    "recommended_version": ver.deprecation_notice.recommended_version,
                    "migration_guide": ver.deprecation_notice.migration_guide,
                }
        
        if ver.status == VersionStatus.SUNSET:
            result["warning"] = "This version has been sunset and should not be used"
        
        return result
    
    async def get_upgrade_path(self, api: str, from_version: str) -> List[str]:
        """Get upgrade path to current version."""
        api_def = await self._store.get_api(api)
        
        if not api_def:
            return []
        
        target = api_def.current_version
        
        if from_version == target:
            return [from_version]
        
        # Find path (simplified - direct upgrade)
        return [from_version, target]


# API lifecycle manager
class APILifecycleManager:
    """API lifecycle manager."""
    
    def __init__(
        self,
        store: Optional[APILifecycleStore] = None,
        notification_service: Optional[NotificationService] = None,
    ):
        self._store = store or InMemoryAPILifecycleStore()
        self._notifications = notification_service or LoggingNotificationService()
        self._checker = VersionChecker(self._store)
        self._listeners: List[Callable] = []
    
    async def register_api(
        self,
        name: str,
        description: str = "",
        owner: str = "",
        **kwargs,
    ) -> APIDefinition:
        """Register an API."""
        api = APIDefinition(
            name=name,
            description=description,
            owner=owner,
            **kwargs,
        )
        
        await self._store.save_api(api)
        await self._emit_event("api_registered", {"api": name})
        
        logger.info(f"API registered: {name}")
        
        return api
    
    async def register_version(
        self,
        api: str,
        version: str,
        status: VersionStatus = VersionStatus.PREVIEW,
        description: str = "",
        **kwargs,
    ) -> APIVersion:
        """Register an API version."""
        api_def = await self._store.get_api(api)
        
        if not api_def:
            api_def = await self.register_api(api)
        
        ver = APIVersion(
            api_name=api,
            version=version,
            status=status,
            description=description,
            **kwargs,
        )
        
        if status == VersionStatus.STABLE:
            ver.released_at = datetime.utcnow()
        
        api_def.versions[version] = ver
        
        # Update current version if stable
        if status == VersionStatus.STABLE:
            api_def.current_version = version
        
        await self._store.save_api(api_def)
        await self._emit_event("version_registered", {"api": api, "version": version})
        
        logger.info(f"API version registered: {api} v{version}")
        
        return ver
    
    async def release_version(
        self,
        api: str,
        version: str,
    ) -> APIVersion:
        """Release a version (mark as stable)."""
        api_def = await self._store.get_api(api)
        
        if not api_def:
            raise APINotFoundError(f"API not found: {api}")
        
        ver = api_def.versions.get(version)
        
        if not ver:
            raise VersionNotFoundError(f"Version not found: {version}")
        
        ver.status = VersionStatus.STABLE
        ver.released_at = datetime.utcnow()
        api_def.current_version = version
        
        await self._store.save_api(api_def)
        await self._emit_event("version_released", {"api": api, "version": version})
        
        logger.info(f"API version released: {api} v{version}")
        
        return ver
    
    async def deprecate_version(
        self,
        api: str,
        version: str,
        sunset_date: Optional[datetime] = None,
        reason: str = "",
        recommended_version: str = "",
        migration_guide: str = "",
    ) -> DeprecationNotice:
        """Deprecate a version."""
        api_def = await self._store.get_api(api)
        
        if not api_def:
            raise APINotFoundError(f"API not found: {api}")
        
        ver = api_def.versions.get(version)
        
        if not ver:
            raise VersionNotFoundError(f"Version not found: {version}")
        
        # Default sunset date
        if not sunset_date:
            sunset_date = datetime.utcnow() + timedelta(days=api_def.min_sunset_days)
        
        # Default recommended version
        if not recommended_version:
            recommended_version = api_def.current_version
        
        notice = DeprecationNotice(
            api_name=api,
            version=version,
            sunset_date=sunset_date,
            reason=reason,
            recommended_version=recommended_version,
            migration_guide=migration_guide,
        )
        
        ver.status = VersionStatus.DEPRECATED
        ver.deprecated_at = datetime.utcnow()
        ver.sunset_date = sunset_date
        ver.deprecation_notice = notice
        
        await self._store.save_api(api_def)
        
        # Notify consumers
        consumers = await self._store.get_consumers_for_api(api, version)
        
        for consumer in consumers:
            await self._notifications.notify_deprecation(consumer, notice)
            notice.notified_consumers.add(consumer.id)
        
        await self._emit_event("version_deprecated", {"api": api, "version": version})
        
        logger.info(f"API version deprecated: {api} v{version}, sunset: {sunset_date}")
        
        return notice
    
    async def sunset_version(
        self,
        api: str,
        version: str,
    ) -> None:
        """Mark version as sunset (no longer supported)."""
        api_def = await self._store.get_api(api)
        
        if not api_def:
            raise APINotFoundError(f"API not found: {api}")
        
        ver = api_def.versions.get(version)
        
        if not ver:
            raise VersionNotFoundError(f"Version not found: {version}")
        
        ver.status = VersionStatus.SUNSET
        
        await self._store.save_api(api_def)
        await self._emit_event("version_sunset", {"api": api, "version": version})
        
        logger.info(f"API version sunset: {api} v{version}")
    
    async def retire_version(
        self,
        api: str,
        version: str,
    ) -> None:
        """Retire a version (completely disabled)."""
        api_def = await self._store.get_api(api)
        
        if not api_def:
            raise APINotFoundError(f"API not found: {api}")
        
        ver = api_def.versions.get(version)
        
        if not ver:
            raise VersionNotFoundError(f"Version not found: {version}")
        
        ver.status = VersionStatus.RETIRED
        ver.retired_at = datetime.utcnow()
        
        await self._store.save_api(api_def)
        await self._emit_event("version_retired", {"api": api, "version": version})
        
        logger.info(f"API version retired: {api} v{version}")
    
    async def add_migration_path(
        self,
        api: str,
        from_version: str,
        to_version: str,
        breaking_changes: Optional[List[BreakingChange]] = None,
        migration_guide: str = "",
        **kwargs,
    ) -> MigrationPath:
        """Add migration path between versions."""
        path = MigrationPath(
            from_version=from_version,
            to_version=to_version,
            breaking_changes=breaking_changes or [],
            migration_guide=migration_guide,
            **kwargs,
        )
        
        await self._store.save_migration_path(path)
        
        logger.info(f"Migration path added: {api} {from_version} -> {to_version}")
        
        return path
    
    async def get_version_info(self, api: str, version: str) -> Optional[APIVersion]:
        """Get version information."""
        api_def = await self._store.get_api(api)
        
        if not api_def:
            return None
        
        return api_def.versions.get(version)
    
    async def check_version(self, api: str, version: str) -> Dict[str, Any]:
        """Check version status."""
        return await self._checker.check_version(api, version)
    
    async def get_migration_path(
        self,
        api: str,
        from_version: str,
        to_version: str,
    ) -> Optional[MigrationPath]:
        """Get migration path."""
        return await self._store.get_migration_path(api, from_version, to_version)
    
    async def list_apis(self) -> List[APIDefinition]:
        """List all APIs."""
        return await self._store.list_apis()
    
    async def list_versions(self, api: str) -> List[APIVersion]:
        """List versions for an API."""
        api_def = await self._store.get_api(api)
        
        if not api_def:
            return []
        
        return list(api_def.versions.values())
    
    async def get_deprecated_versions(self) -> List[APIVersion]:
        """Get all deprecated versions."""
        deprecated = []
        
        apis = await self._store.list_apis()
        
        for api in apis:
            for ver in api.versions.values():
                if ver.status == VersionStatus.DEPRECATED:
                    deprecated.append(ver)
        
        return deprecated
    
    async def get_sunset_schedule(self) -> List[Dict[str, Any]]:
        """Get sunset schedule."""
        schedule = []
        
        apis = await self._store.list_apis()
        
        for api in apis:
            for ver in api.versions.values():
                if ver.sunset_date and ver.status == VersionStatus.DEPRECATED:
                    schedule.append({
                        "api": api.name,
                        "version": ver.version,
                        "sunset_date": ver.sunset_date,
                        "days_remaining": (ver.sunset_date - datetime.utcnow()).days,
                    })
        
        return sorted(schedule, key=lambda x: x["sunset_date"])
    
    async def record_request(
        self,
        api: str,
        version: str,
        consumer_id: str,
    ) -> None:
        """Record API request for usage tracking."""
        api_def = await self._store.get_api(api)
        
        if not api_def:
            return
        
        ver = api_def.versions.get(version)
        
        if ver:
            ver.request_count += 1
            ver.unique_consumers.add(consumer_id)
            ver.last_request_at = datetime.utcnow()
            await self._store.save_api(api_def)
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    async def _emit_event(self, event: str, data: Dict[str, Any]) -> None:
        """Emit event to listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, data)
                else:
                    listener(event, data)
            except Exception as e:
                logger.error(f"Listener error: {e}")


# Middleware
class VersionMiddleware:
    """API version middleware."""
    
    def __init__(
        self,
        manager: APILifecycleManager,
        header_name: str = "X-API-Version",
        deprecation_header: str = "Deprecation",
        sunset_header: str = "Sunset",
    ):
        self._manager = manager
        self._header_name = header_name
        self._deprecation_header = deprecation_header
        self._sunset_header = sunset_header
    
    async def process_request(
        self,
        api: str,
        version: str,
        consumer_id: str = "",
    ) -> Dict[str, str]:
        """Process request and return headers to add."""
        headers: Dict[str, str] = {}
        
        await self._manager.record_request(api, version, consumer_id)
        
        info = await self._manager.check_version(api, version)
        
        if info.get("is_deprecated"):
            deprecation = info.get("deprecation", {})
            
            if deprecation.get("deprecated_at"):
                headers[self._deprecation_header] = deprecation["deprecated_at"]
            
            if deprecation.get("sunset_date"):
                headers[self._sunset_header] = deprecation["sunset_date"]
            
            migration = info.get("migration", {})
            
            if migration.get("recommended_version"):
                headers["X-Upgrade-To"] = migration["recommended_version"]
        
        return headers


# Factory functions
def create_api_lifecycle_manager() -> APILifecycleManager:
    """Create API lifecycle manager."""
    return APILifecycleManager()


def create_breaking_change(
    change_type: BreakingChangeType,
    description: str,
    **kwargs,
) -> BreakingChange:
    """Create breaking change."""
    return BreakingChange(
        change_type=change_type,
        description=description,
        **kwargs,
    )


def create_version_middleware(
    manager: APILifecycleManager,
) -> VersionMiddleware:
    """Create version middleware."""
    return VersionMiddleware(manager)


__all__ = [
    # Exceptions
    "APILifecycleError",
    "VersionNotFoundError",
    "APINotFoundError",
    # Enums
    "VersionStatus",
    "BreakingChangeType",
    "MigrationDifficulty",
    # Data classes
    "BreakingChange",
    "MigrationPath",
    "DeprecationNotice",
    "APIVersion",
    "APIDefinition",
    "Consumer",
    "VersionStats",
    # Store
    "APILifecycleStore",
    "InMemoryAPILifecycleStore",
    # Notification
    "NotificationService",
    "LoggingNotificationService",
    # Checker
    "VersionChecker",
    # Manager
    "APILifecycleManager",
    # Middleware
    "VersionMiddleware",
    # Factory functions
    "create_api_lifecycle_manager",
    "create_breaking_change",
    "create_version_middleware",
]
