"""
Enterprise Cache Manager Module.

Provides cache management, eviction policies,
distributed caching, and cache-aside patterns.

Example:
    # Create cache
    cache = create_cache(ttl=300, max_size=1000)
    
    # Cache operations
    await cache.set("user:123", user_data)
    user = await cache.get("user:123")
    
    # Use decorator
    @cached(ttl=60)
    async def get_user(user_id: str):
        return await db.find_user(user_id)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
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
    Type,
    TypeVar,
)

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')


logger = logging.getLogger(__name__)


class CacheError(Exception):
    """Cache error."""
    pass


class CacheMissError(CacheError):
    """Cache miss error."""
    pass


class CacheFullError(CacheError):
    """Cache full error."""
    pass


class EvictionPolicy(str, Enum):
    """Cache eviction policy."""
    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In First Out
    TTL = "ttl"  # Time To Live
    RANDOM = "random"


class WritePolicy(str, Enum):
    """Cache write policy."""
    WRITE_THROUGH = "write_through"
    WRITE_BACK = "write_back"
    WRITE_AROUND = "write_around"


@dataclass
class CacheEntry(Generic[V]):
    """Cache entry with metadata."""
    key: str
    value: V
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    size_bytes: int = 0
    tags: Set[str] = field(default_factory=set)
    
    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def touch(self) -> None:
        """Update access time and count."""
        self.accessed_at = datetime.now()
        self.access_count += 1


@dataclass
class CacheConfig:
    """Cache configuration."""
    max_size: int = 1000
    ttl: Optional[float] = None  # Default TTL in seconds
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU
    write_policy: WritePolicy = WritePolicy.WRITE_THROUGH
    namespace: str = ""


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    expirations: int = 0
    size: int = 0
    max_size: int = 0
    
    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class Serializer(ABC, Generic[T]):
    """
    Cache value serializer.
    """
    
    @abstractmethod
    def serialize(self, value: T) -> bytes:
        """Serialize value."""
        pass
    
    @abstractmethod
    def deserialize(self, data: bytes) -> T:
        """Deserialize value."""
        pass


class JsonSerializer(Serializer[Any]):
    """JSON serializer."""
    
    def serialize(self, value: Any) -> bytes:
        return json.dumps(value, default=str).encode('utf-8')
    
    def deserialize(self, data: bytes) -> Any:
        return json.loads(data.decode('utf-8'))


class PickleSerializer(Serializer[Any]):
    """Pickle serializer."""
    
    def serialize(self, value: Any) -> bytes:
        import pickle
        return pickle.dumps(value)
    
    def deserialize(self, data: bytes) -> Any:
        import pickle
        return pickle.loads(data)


class Cache(ABC, Generic[K, V]):
    """
    Abstract cache interface.
    """
    
    @abstractmethod
    async def get(self, key: K) -> Optional[V]:
        """Get value from cache."""
        pass
    
    @abstractmethod
    async def set(
        self,
        key: K,
        value: V,
        ttl: Optional[float] = None,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """Set value in cache."""
        pass
    
    @abstractmethod
    async def delete(self, key: K) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    async def exists(self, key: K) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all entries."""
        pass
    
    @abstractmethod
    async def stats(self) -> CacheStats:
        """Get cache statistics."""
        pass


class InMemoryCache(Cache[str, Any]):
    """
    In-memory cache implementation.
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self._config = config or CacheConfig()
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats(max_size=self._config.max_size)
        self._lock = asyncio.Lock()
    
    def _make_key(self, key: str) -> str:
        """Create namespaced key."""
        if self._config.namespace:
            return f"{self._config.namespace}:{key}"
        return key
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            full_key = self._make_key(key)
            entry = self._entries.get(full_key)
            
            if entry is None:
                self._stats.misses += 1
                return None
            
            if entry.is_expired:
                del self._entries[full_key]
                self._stats.expirations += 1
                self._stats.misses += 1
                self._stats.size -= 1
                return None
            
            entry.touch()
            
            # Move to end for LRU
            if self._config.eviction_policy == EvictionPolicy.LRU:
                self._entries.move_to_end(full_key)
            
            self._stats.hits += 1
            return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        tags: Optional[Set[str]] = None,
    ) -> None:
        async with self._lock:
            full_key = self._make_key(key)
            
            # Evict if at capacity
            while len(self._entries) >= self._config.max_size:
                await self._evict()
            
            expires_at = None
            effective_ttl = ttl or self._config.ttl
            if effective_ttl:
                expires_at = datetime.now() + timedelta(seconds=effective_ttl)
            
            entry = CacheEntry(
                key=full_key,
                value=value,
                expires_at=expires_at,
                tags=tags or set(),
            )
            
            self._entries[full_key] = entry
            self._stats.sets += 1
            self._stats.size = len(self._entries)
    
    async def delete(self, key: str) -> bool:
        async with self._lock:
            full_key = self._make_key(key)
            if full_key in self._entries:
                del self._entries[full_key]
                self._stats.deletes += 1
                self._stats.size = len(self._entries)
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        async with self._lock:
            full_key = self._make_key(key)
            entry = self._entries.get(full_key)
            
            if entry is None:
                return False
            
            if entry.is_expired:
                del self._entries[full_key]
                self._stats.expirations += 1
                self._stats.size -= 1
                return False
            
            return True
    
    async def clear(self) -> None:
        async with self._lock:
            self._entries.clear()
            self._stats.size = 0
    
    async def stats(self) -> CacheStats:
        return self._stats
    
    async def _evict(self) -> None:
        """Evict an entry based on policy."""
        if not self._entries:
            return
        
        if self._config.eviction_policy == EvictionPolicy.LRU:
            # Remove least recently used (first item)
            self._entries.popitem(last=False)
        elif self._config.eviction_policy == EvictionPolicy.LFU:
            # Remove least frequently used
            min_entry = min(
                self._entries.items(),
                key=lambda x: x[1].access_count,
            )
            del self._entries[min_entry[0]]
        elif self._config.eviction_policy == EvictionPolicy.FIFO:
            # Remove first inserted
            self._entries.popitem(last=False)
        elif self._config.eviction_policy == EvictionPolicy.RANDOM:
            import random
            key = random.choice(list(self._entries.keys()))
            del self._entries[key]
        else:
            self._entries.popitem(last=False)
        
        self._stats.evictions += 1
        self._stats.size = len(self._entries)
    
    async def get_by_tag(self, tag: str) -> List[Tuple[str, Any]]:
        """Get all entries with a tag."""
        async with self._lock:
            return [
                (e.key, e.value)
                for e in self._entries.values()
                if tag in e.tags and not e.is_expired
            ]
    
    async def delete_by_tag(self, tag: str) -> int:
        """Delete all entries with a tag."""
        async with self._lock:
            keys_to_delete = [
                key for key, entry in self._entries.items()
                if tag in entry.tags
            ]
            for key in keys_to_delete:
                del self._entries[key]
            
            self._stats.deletes += len(keys_to_delete)
            self._stats.size = len(self._entries)
            return len(keys_to_delete)


class TieredCache(Cache[str, Any]):
    """
    Tiered cache with multiple levels.
    """
    
    def __init__(self, caches: List[Cache]):
        self._caches = caches
    
    async def get(self, key: str) -> Optional[Any]:
        for i, cache in enumerate(self._caches):
            value = await cache.get(key)
            if value is not None:
                # Populate upper tiers
                for j in range(i):
                    await self._caches[j].set(key, value)
                return value
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        tags: Optional[Set[str]] = None,
    ) -> None:
        for cache in self._caches:
            await cache.set(key, value, ttl, tags)
    
    async def delete(self, key: str) -> bool:
        deleted = False
        for cache in self._caches:
            if await cache.delete(key):
                deleted = True
        return deleted
    
    async def exists(self, key: str) -> bool:
        for cache in self._caches:
            if await cache.exists(key):
                return True
        return False
    
    async def clear(self) -> None:
        for cache in self._caches:
            await cache.clear()
    
    async def stats(self) -> CacheStats:
        combined = CacheStats()
        for cache in self._caches:
            s = await cache.stats()
            combined.hits += s.hits
            combined.misses += s.misses
            combined.sets += s.sets
            combined.deletes += s.deletes
            combined.evictions += s.evictions
            combined.size += s.size
        return combined


class CacheAside:
    """
    Cache-aside pattern implementation.
    """
    
    def __init__(
        self,
        cache: Cache,
        loader: Callable[[str], Any],
        ttl: Optional[float] = None,
    ):
        self._cache = cache
        self._loader = loader
        self._ttl = ttl
    
    async def get(self, key: str) -> Any:
        """Get from cache or load."""
        value = await self._cache.get(key)
        
        if value is not None:
            return value
        
        # Load from source
        if asyncio.iscoroutinefunction(self._loader):
            value = await self._loader(key)
        else:
            value = self._loader(key)
        
        if value is not None:
            await self._cache.set(key, value, ttl=self._ttl)
        
        return value
    
    async def invalidate(self, key: str) -> None:
        """Invalidate cache entry."""
        await self._cache.delete(key)
    
    async def refresh(self, key: str) -> Any:
        """Refresh cache entry."""
        await self._cache.delete(key)
        return await self.get(key)


class WriteThrough:
    """
    Write-through cache pattern.
    """
    
    def __init__(
        self,
        cache: Cache,
        writer: Callable[[str, Any], Any],
        ttl: Optional[float] = None,
    ):
        self._cache = cache
        self._writer = writer
        self._ttl = ttl
    
    async def write(self, key: str, value: Any) -> None:
        """Write to cache and source."""
        # Write to source first
        if asyncio.iscoroutinefunction(self._writer):
            await self._writer(key, value)
        else:
            self._writer(key, value)
        
        # Then update cache
        await self._cache.set(key, value, ttl=self._ttl)


class CacheManager:
    """
    Cache manager for multiple caches.
    """
    
    def __init__(self):
        self._caches: Dict[str, Cache] = {}
        self._default: Optional[str] = None
    
    def register(
        self,
        name: str,
        cache: Cache,
        default: bool = False,
    ) -> None:
        """Register a cache."""
        self._caches[name] = cache
        if default or self._default is None:
            self._default = name
    
    def get_cache(self, name: Optional[str] = None) -> Cache:
        """Get a cache."""
        name = name or self._default
        if not name or name not in self._caches:
            raise CacheError(f"Cache not found: {name}")
        return self._caches[name]
    
    async def clear_all(self) -> None:
        """Clear all caches."""
        for cache in self._caches.values():
            await cache.clear()
    
    async def stats_all(self) -> Dict[str, CacheStats]:
        """Get stats for all caches."""
        return {
            name: await cache.stats()
            for name, cache in self._caches.items()
        }


# Global manager
_global_manager = CacheManager()


def _generate_cache_key(
    func: Callable,
    args: tuple,
    kwargs: dict,
    key_builder: Optional[Callable] = None,
) -> str:
    """Generate cache key for function call."""
    if key_builder:
        return key_builder(*args, **kwargs)
    
    # Default key generation
    key_parts = [func.__module__, func.__qualname__]
    
    # Add args
    for arg in args:
        key_parts.append(str(hash(str(arg))))
    
    # Add kwargs
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={hash(str(v))}")
    
    key_str = ":".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


# Decorators
def cached(
    ttl: Optional[float] = None,
    cache_name: Optional[str] = None,
    key_builder: Optional[Callable[..., str]] = None,
    tags: Optional[Set[str]] = None,
) -> Callable:
    """
    Decorator to cache function results.
    
    Example:
        @cached(ttl=60)
        async def get_user(user_id: str):
            return await db.find_user(user_id)
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            cache = _global_manager.get_cache(cache_name)
            key = _generate_cache_key(func, args, kwargs, key_builder)
            
            # Try cache
            value = await cache.get(key)
            if value is not None:
                return value
            
            # Execute function
            if asyncio.iscoroutinefunction(func):
                value = await func(*args, **kwargs)
            else:
                value = func(*args, **kwargs)
            
            # Cache result
            if value is not None:
                await cache.set(key, value, ttl=ttl, tags=tags)
            
            return value
        
        wrapper._cached = True
        wrapper._cache_name = cache_name
        return wrapper
    
    return decorator


def cache_invalidate(
    key_builder: Callable[..., str],
    cache_name: Optional[str] = None,
) -> Callable:
    """
    Decorator to invalidate cache on function call.
    
    Example:
        @cache_invalidate(lambda user_id: f"user:{user_id}")
        async def update_user(user_id: str, data: dict):
            ...
    """
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # Execute function first
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Invalidate cache
            cache = _global_manager.get_cache(cache_name)
            key = key_builder(*args, **kwargs)
            await cache.delete(key)
            
            return result
        
        return wrapper
    
    return decorator


# Factory functions
def create_cache(
    max_size: int = 1000,
    ttl: Optional[float] = None,
    eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
    namespace: str = "",
) -> InMemoryCache:
    """Create an in-memory cache."""
    return InMemoryCache(CacheConfig(
        max_size=max_size,
        ttl=ttl,
        eviction_policy=eviction_policy,
        namespace=namespace,
    ))


def create_lru_cache(
    max_size: int = 1000,
    ttl: Optional[float] = None,
) -> InMemoryCache:
    """Create an LRU cache."""
    return create_cache(
        max_size=max_size,
        ttl=ttl,
        eviction_policy=EvictionPolicy.LRU,
    )


def create_lfu_cache(
    max_size: int = 1000,
    ttl: Optional[float] = None,
) -> InMemoryCache:
    """Create an LFU cache."""
    return create_cache(
        max_size=max_size,
        ttl=ttl,
        eviction_policy=EvictionPolicy.LFU,
    )


def create_tiered_cache(
    *caches: Cache,
) -> TieredCache:
    """Create a tiered cache."""
    return TieredCache(list(caches))


def create_cache_aside(
    cache: Cache,
    loader: Callable[[str], Any],
    ttl: Optional[float] = None,
) -> CacheAside:
    """Create a cache-aside pattern."""
    return CacheAside(cache, loader, ttl)


def create_write_through(
    cache: Cache,
    writer: Callable[[str, Any], Any],
    ttl: Optional[float] = None,
) -> WriteThrough:
    """Create a write-through pattern."""
    return WriteThrough(cache, writer, ttl)


def register_cache(
    name: str,
    cache: Cache,
    default: bool = False,
) -> None:
    """Register cache in global manager."""
    _global_manager.register(name, cache, default)


def get_cache(name: Optional[str] = None) -> Cache:
    """Get cache from global manager."""
    return _global_manager.get_cache(name)


__all__ = [
    # Exceptions
    "CacheError",
    "CacheMissError",
    "CacheFullError",
    # Enums
    "EvictionPolicy",
    "WritePolicy",
    # Data classes
    "CacheEntry",
    "CacheConfig",
    "CacheStats",
    # Serializers
    "Serializer",
    "JsonSerializer",
    "PickleSerializer",
    # Cache
    "Cache",
    "InMemoryCache",
    "TieredCache",
    # Patterns
    "CacheAside",
    "WriteThrough",
    # Manager
    "CacheManager",
    # Decorators
    "cached",
    "cache_invalidate",
    # Factory functions
    "create_cache",
    "create_lru_cache",
    "create_lfu_cache",
    "create_tiered_cache",
    "create_cache_aside",
    "create_write_through",
    "register_cache",
    "get_cache",
]
