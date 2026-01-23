"""
Enterprise API Versioning Module.

API version management, routing, deprecation
tracking, and migration support.

Example:
    # Create versioned API
    api = create_versioned_api("users")
    
    # Register version handlers
    @api.version("v1")
    async def get_users_v1(request):
        return {"users": [...]}
    
    @api.version("v2")
    async def get_users_v2(request):
        return {"data": {"users": [...]}, "meta": {...}}
    
    # Route request
    response = await api.route(request, version="v2")
    
    # Deprecate version
    api.deprecate("v1", sunset_date="2024-12-31")
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')
RequestHandler = Callable[..., Awaitable[Any]]


logger = logging.getLogger(__name__)


class VersionError(Exception):
    """Version error."""
    pass


class VersionNotFoundError(VersionError):
    """Version not found."""
    pass


class DeprecatedVersionError(VersionError):
    """Deprecated version warning."""
    pass


class SunsetVersionError(VersionError):
    """Version has been sunset."""
    pass


class VersionFormat(str, Enum):
    """Version format types."""
    SEMANTIC = "semantic"  # v1.2.3
    MAJOR = "major"  # v1, v2
    DATE = "date"  # 2024-01-15
    HEADER = "header"  # Via header
    PATH = "path"  # /v1/resource
    QUERY = "query"  # ?version=v1


class VersionStatus(str, Enum):
    """Version status."""
    CURRENT = "current"
    STABLE = "stable"
    DEPRECATED = "deprecated"
    SUNSET = "sunset"
    BETA = "beta"
    ALPHA = "alpha"


class VersionExtractionStrategy(str, Enum):
    """How to extract version from request."""
    URL_PATH = "url_path"
    QUERY_PARAM = "query_param"
    HEADER = "header"
    ACCEPT_HEADER = "accept_header"


@dataclass
class Version:
    """API version."""
    name: str
    status: VersionStatus = VersionStatus.STABLE
    release_date: Optional[date] = None
    deprecation_date: Optional[date] = None
    sunset_date: Optional[date] = None
    description: str = ""
    changelog: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_deprecated(self) -> bool:
        """Check if deprecated."""
        if self.status == VersionStatus.DEPRECATED:
            return True
        
        if self.deprecation_date:
            return date.today() >= self.deprecation_date
        
        return False
    
    def is_sunset(self) -> bool:
        """Check if sunset."""
        if self.status == VersionStatus.SUNSET:
            return True
        
        if self.sunset_date:
            return date.today() >= self.sunset_date
        
        return False


@dataclass
class VersionMapping:
    """Version to handler mapping."""
    version: Version
    handler: RequestHandler
    transformers: List[Callable] = field(default_factory=list)


@dataclass
class RoutingResult:
    """Routing result."""
    version: Version
    handler: RequestHandler
    warnings: List[str] = field(default_factory=list)


@dataclass
class MigrationGuide:
    """Migration guide between versions."""
    from_version: str
    to_version: str
    breaking_changes: List[str] = field(default_factory=list)
    new_features: List[str] = field(default_factory=list)
    removed_features: List[str] = field(default_factory=list)
    migration_steps: List[str] = field(default_factory=list)


@dataclass
class VersionStats:
    """Version statistics."""
    version: str
    request_count: int = 0
    error_count: int = 0
    avg_latency_ms: float = 0.0
    last_accessed: Optional[datetime] = None


# Version parser
class VersionParser:
    """Parse version strings."""
    
    @staticmethod
    def parse(version: str) -> Tuple[int, int, int]:
        """Parse semantic version."""
        # Handle v prefix
        v = version.lstrip("vV")
        
        parts = v.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        
        return (major, minor, patch)
    
    @staticmethod
    def compare(v1: str, v2: str) -> int:
        """Compare versions. Returns -1, 0, or 1."""
        p1 = VersionParser.parse(v1)
        p2 = VersionParser.parse(v2)
        
        if p1 < p2:
            return -1
        elif p1 > p2:
            return 1
        return 0
    
    @staticmethod
    def is_compatible(required: str, actual: str) -> bool:
        """Check if versions are compatible."""
        r = VersionParser.parse(required)
        a = VersionParser.parse(actual)
        
        # Same major version
        return r[0] == a[0]


# Version extractor
class VersionExtractor:
    """Extract version from request."""
    
    def __init__(
        self,
        strategy: VersionExtractionStrategy = VersionExtractionStrategy.URL_PATH,
        header_name: str = "X-API-Version",
        query_param: str = "version",
        path_pattern: str = r"/v(\d+(?:\.\d+)?(?:\.\d+)?)",
        accept_pattern: str = r"application/vnd\.api\.v(\d+)\+json",
    ):
        self._strategy = strategy
        self._header_name = header_name
        self._query_param = query_param
        self._path_pattern = re.compile(path_pattern)
        self._accept_pattern = re.compile(accept_pattern)
    
    def extract(
        self,
        path: str = "",
        headers: Optional[Dict[str, str]] = None,
        query: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """Extract version from request."""
        headers = headers or {}
        query = query or {}
        
        if self._strategy == VersionExtractionStrategy.URL_PATH:
            match = self._path_pattern.search(path)
            if match:
                return f"v{match.group(1)}"
        
        elif self._strategy == VersionExtractionStrategy.HEADER:
            return headers.get(self._header_name)
        
        elif self._strategy == VersionExtractionStrategy.QUERY_PARAM:
            return query.get(self._query_param)
        
        elif self._strategy == VersionExtractionStrategy.ACCEPT_HEADER:
            accept = headers.get("Accept", "")
            match = self._accept_pattern.search(accept)
            if match:
                return f"v{match.group(1)}"
        
        return None


# Response transformer
class ResponseTransformer(ABC):
    """Abstract response transformer."""
    
    @abstractmethod
    async def transform(
        self,
        response: Any,
        from_version: str,
        to_version: str,
    ) -> Any:
        """Transform response between versions."""
        pass


class FieldMappingTransformer(ResponseTransformer):
    """Transform response by mapping fields."""
    
    def __init__(
        self,
        mapping: Dict[str, str],
        remove: Optional[List[str]] = None,
    ):
        self._mapping = mapping
        self._remove = set(remove or [])
    
    async def transform(
        self,
        response: Any,
        from_version: str,
        to_version: str,
    ) -> Any:
        if not isinstance(response, dict):
            return response
        
        result = {}
        
        for key, value in response.items():
            if key in self._remove:
                continue
            
            new_key = self._mapping.get(key, key)
            result[new_key] = value
        
        return result


# Versioned API
class VersionedAPI:
    """
    Versioned API manager.
    """
    
    def __init__(
        self,
        name: str,
        default_version: str = "v1",
        extraction_strategy: VersionExtractionStrategy = VersionExtractionStrategy.URL_PATH,
    ):
        self.name = name
        self._default_version = default_version
        self._versions: Dict[str, Version] = {}
        self._handlers: Dict[str, Dict[str, VersionMapping]] = defaultdict(dict)
        self._transformers: Dict[Tuple[str, str], ResponseTransformer] = {}
        self._migration_guides: Dict[Tuple[str, str], MigrationGuide] = {}
        self._stats: Dict[str, VersionStats] = {}
        self._extractor = VersionExtractor(strategy=extraction_strategy)
    
    def register_version(
        self,
        name: str,
        status: VersionStatus = VersionStatus.STABLE,
        release_date: Optional[date] = None,
        description: str = "",
    ) -> Version:
        """
        Register API version.
        
        Args:
            name: Version name (e.g., "v1")
            status: Version status
            release_date: Release date
            description: Version description
            
        Returns:
            Version object
        """
        version = Version(
            name=name,
            status=status,
            release_date=release_date or date.today(),
            description=description,
        )
        
        self._versions[name] = version
        self._stats[name] = VersionStats(version=name)
        
        return version
    
    def version(
        self,
        version_name: str,
        endpoint: str = "default",
    ) -> Callable:
        """
        Decorator to register versioned handler.
        
        Args:
            version_name: Version name
            endpoint: Endpoint name
            
        Returns:
            Decorator
        """
        def decorator(func: RequestHandler) -> RequestHandler:
            self.register_handler(endpoint, version_name, func)
            return func
        
        return decorator
    
    def register_handler(
        self,
        endpoint: str,
        version_name: str,
        handler: RequestHandler,
    ) -> None:
        """Register handler for endpoint version."""
        if version_name not in self._versions:
            self.register_version(version_name)
        
        version = self._versions[version_name]
        
        self._handlers[endpoint][version_name] = VersionMapping(
            version=version,
            handler=handler,
        )
    
    async def route(
        self,
        endpoint: str,
        version: Optional[str] = None,
        path: str = "",
        headers: Optional[Dict[str, str]] = None,
        query: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Any:
        """
        Route request to versioned handler.
        
        Args:
            endpoint: Endpoint name
            version: Explicit version
            path: Request path (for extraction)
            headers: Request headers
            query: Query parameters
            **kwargs: Handler arguments
            
        Returns:
            Handler response
        """
        # Extract version
        if version is None:
            version = self._extractor.extract(path, headers, query)
        
        if version is None:
            version = self._default_version
        
        # Get routing result
        result = self._resolve_handler(endpoint, version)
        
        # Check sunset
        if result.version.is_sunset():
            raise SunsetVersionError(
                f"Version {version} has been sunset"
            )
        
        # Track stats
        self._record_access(version)
        
        # Execute handler
        import time
        start = time.perf_counter()
        
        try:
            response = await result.handler(**kwargs)
            
            latency = (time.perf_counter() - start) * 1000
            self._record_latency(version, latency)
            
            return response
            
        except Exception as e:
            self._record_error(version)
            raise
    
    def _resolve_handler(
        self,
        endpoint: str,
        version: str,
    ) -> RoutingResult:
        """Resolve handler for version."""
        endpoint_handlers = self._handlers.get(endpoint, {})
        
        if version in endpoint_handlers:
            mapping = endpoint_handlers[version]
            warnings = []
            
            if mapping.version.is_deprecated():
                warnings.append(
                    f"Version {version} is deprecated"
                )
            
            return RoutingResult(
                version=mapping.version,
                handler=mapping.handler,
                warnings=warnings,
            )
        
        # Find compatible version
        for v_name, mapping in sorted(
            endpoint_handlers.items(),
            key=lambda x: VersionParser.parse(x[0]),
            reverse=True,
        ):
            if VersionParser.is_compatible(version, v_name):
                return RoutingResult(
                    version=mapping.version,
                    handler=mapping.handler,
                    warnings=[f"Falling back to version {v_name}"],
                )
        
        raise VersionNotFoundError(f"No handler for version {version}")
    
    def deprecate(
        self,
        version: str,
        deprecation_date: Optional[date] = None,
        sunset_date: Optional[date] = None,
    ) -> None:
        """
        Deprecate a version.
        
        Args:
            version: Version to deprecate
            deprecation_date: When deprecated
            sunset_date: When to sunset
        """
        if version in self._versions:
            v = self._versions[version]
            v.status = VersionStatus.DEPRECATED
            v.deprecation_date = deprecation_date or date.today()
            v.sunset_date = sunset_date
    
    def sunset(self, version: str) -> None:
        """Sunset a version."""
        if version in self._versions:
            v = self._versions[version]
            v.status = VersionStatus.SUNSET
            v.sunset_date = date.today()
    
    def add_transformer(
        self,
        from_version: str,
        to_version: str,
        transformer: ResponseTransformer,
    ) -> None:
        """Add response transformer."""
        self._transformers[(from_version, to_version)] = transformer
    
    async def transform_response(
        self,
        response: Any,
        from_version: str,
        to_version: str,
    ) -> Any:
        """Transform response between versions."""
        key = (from_version, to_version)
        
        if key in self._transformers:
            return await self._transformers[key].transform(
                response, from_version, to_version
            )
        
        return response
    
    def add_migration_guide(
        self,
        from_version: str,
        to_version: str,
        guide: MigrationGuide,
    ) -> None:
        """Add migration guide."""
        self._migration_guides[(from_version, to_version)] = guide
    
    def get_migration_guide(
        self,
        from_version: str,
        to_version: str,
    ) -> Optional[MigrationGuide]:
        """Get migration guide."""
        return self._migration_guides.get((from_version, to_version))
    
    def _record_access(self, version: str) -> None:
        """Record version access."""
        if version in self._stats:
            self._stats[version].request_count += 1
            self._stats[version].last_accessed = datetime.utcnow()
    
    def _record_latency(self, version: str, latency_ms: float) -> None:
        """Record request latency."""
        if version in self._stats:
            stats = self._stats[version]
            count = stats.request_count
            
            # Running average
            stats.avg_latency_ms = (
                (stats.avg_latency_ms * (count - 1) + latency_ms) / count
            )
    
    def _record_error(self, version: str) -> None:
        """Record error."""
        if version in self._stats:
            self._stats[version].error_count += 1
    
    def get_versions(self) -> List[Version]:
        """Get all versions."""
        return list(self._versions.values())
    
    def get_version(self, name: str) -> Optional[Version]:
        """Get version by name."""
        return self._versions.get(name)
    
    def get_current_version(self) -> Optional[Version]:
        """Get current (latest stable) version."""
        stable = [
            v for v in self._versions.values()
            if v.status == VersionStatus.STABLE
        ]
        
        if not stable:
            return None
        
        return max(
            stable,
            key=lambda v: VersionParser.parse(v.name)
        )
    
    def get_stats(self, version: Optional[str] = None) -> Union[VersionStats, Dict[str, VersionStats]]:
        """Get version statistics."""
        if version:
            return self._stats.get(version, VersionStats(version=version))
        return dict(self._stats)


# Decorator for simple versioning
def versioned(
    api: VersionedAPI,
    endpoint: str = "default",
):
    """
    Create versioned endpoint decorator.
    
    Args:
        api: Versioned API
        endpoint: Endpoint name
    """
    def version_decorator(version_name: str):
        def decorator(func: RequestHandler) -> RequestHandler:
            api.register_handler(endpoint, version_name, func)
            return func
        return decorator
    
    return version_decorator


# Factory functions
def create_versioned_api(
    name: str,
    default_version: str = "v1",
    extraction_strategy: VersionExtractionStrategy = VersionExtractionStrategy.URL_PATH,
) -> VersionedAPI:
    """Create versioned API."""
    return VersionedAPI(
        name=name,
        default_version=default_version,
        extraction_strategy=extraction_strategy,
    )


def create_version_extractor(
    strategy: VersionExtractionStrategy = VersionExtractionStrategy.URL_PATH,
    **kwargs,
) -> VersionExtractor:
    """Create version extractor."""
    return VersionExtractor(strategy=strategy, **kwargs)


def create_migration_guide(
    from_version: str,
    to_version: str,
    breaking_changes: Optional[List[str]] = None,
    new_features: Optional[List[str]] = None,
) -> MigrationGuide:
    """Create migration guide."""
    return MigrationGuide(
        from_version=from_version,
        to_version=to_version,
        breaking_changes=breaking_changes or [],
        new_features=new_features or [],
    )


__all__ = [
    # Exceptions
    "VersionError",
    "VersionNotFoundError",
    "DeprecatedVersionError",
    "SunsetVersionError",
    # Enums
    "VersionFormat",
    "VersionStatus",
    "VersionExtractionStrategy",
    # Data classes
    "Version",
    "VersionMapping",
    "RoutingResult",
    "MigrationGuide",
    "VersionStats",
    # Parser
    "VersionParser",
    # Extractor
    "VersionExtractor",
    # Transformer
    "ResponseTransformer",
    "FieldMappingTransformer",
    # Main class
    "VersionedAPI",
    # Decorators
    "versioned",
    # Factory functions
    "create_versioned_api",
    "create_version_extractor",
    "create_migration_guide",
]
