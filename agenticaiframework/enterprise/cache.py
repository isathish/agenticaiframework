"""
Enterprise Cache Module.

Provides LRU, TTL, and distributed caching with Redis/Memcached adapters.

Example:
    # In-memory LRU cache
    cache = LRUCache(max_size=1000)
    
    @cached(cache, ttl=300)
    async def get_user(user_id: str) -> dict:
        return await db.fetch_user(user_id)
    
    # Distributed Redis cache
    redis_cache = RedisCache(url="redis://localhost:6379")
    
    @cached(redis_cache, ttl=3600, key_func=lambda x: f"data:{x}")
    async def get_data(key: str) -> dict:
        return await fetch_data(key)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import pickle
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
    Union,
)
from functools import wraps
from enum import Enum
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
F = TypeVar("F", bound=Callable[..., Any])


class CacheError(Exception):
    """Base exception for cache errors."""
    pass


class CacheMiss(CacheError):
    """Raised when item not found in cache."""
    pass


class SerializationError(CacheError):
    """Raised when serialization fails."""
    pass


@dataclass
class CacheEntry(Generic[V]):
    """Entry in cache with metadata."""
    value: V
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    hits: int = 0
    last_accessed: float = field(default_factory=time.time)
    
    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def touch(self) -> None:
        """Update last access time and hit count."""
        self.last_accessed = time.time()
        self.hits += 1


@dataclass
class CacheStats:
    """Statistics for cache operations."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "hit_rate": self.hit_rate,
        }


class Serializer(ABC):
    """Abstract base class for cache serializers."""
    
    @abstractmethod
    def serialize(self, value: Any) -> bytes:
        """Serialize value to bytes."""
        pass
    
    @abstractmethod
    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to value."""
        pass


class PickleSerializer(Serializer):
    """Pickle-based serializer."""
    
    def serialize(self, value: Any) -> bytes:
        """Serialize using pickle."""
        try:
            return pickle.dumps(value)
        except Exception as e:
            raise SerializationError(f"Pickle serialization failed: {e}")
    
    def deserialize(self, data: bytes) -> Any:
        """Deserialize using pickle."""
        try:
            return pickle.loads(data)
        except Exception as e:
            raise SerializationError(f"Pickle deserialization failed: {e}")


class JSONSerializer(Serializer):
    """JSON-based serializer."""
    
    def serialize(self, value: Any) -> bytes:
        """Serialize using JSON."""
        try:
            return json.dumps(value).encode("utf-8")
        except Exception as e:
            raise SerializationError(f"JSON serialization failed: {e}")
    
    def deserialize(self, data: bytes) -> Any:
        """Deserialize using JSON."""
        try:
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            raise SerializationError(f"JSON deserialization failed: {e}")


class Cache(ABC, Generic[K, V]):
    """Abstract base class for caches."""
    
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
    ) -> None:
        """Set value in cache."""
        pass
    
    @abstractmethod
    async def delete(self, key: K) -> bool:
        """Delete value from cache."""
        pass
    
    @abstractmethod
    async def exists(self, key: K) -> bool:
        """Check if key exists in cache."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all entries from cache."""
        pass
    
    @abstractmethod
    async def size(self) -> int:
        """Get number of entries in cache."""
        pass
    
    async def get_or_set(
        self,
        key: K,
        factory: Callable[[], Union[V, Any]],
        ttl: Optional[float] = None,
    ) -> V:
        """Get value from cache or compute and store it."""
        value = await self.get(key)
        if value is not None:
            return value
        
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
        
        await self.set(key, value, ttl)
        return value
    
    async def get_many(self, keys: List[K]) -> Dict[K, V]:
        """Get multiple values from cache."""
        results = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                results[key] = value
        return results
    
    async def set_many(
        self,
        items: Dict[K, V],
        ttl: Optional[float] = None,
    ) -> None:
        """Set multiple values in cache."""
        for key, value in items.items():
            await self.set(key, value, ttl)
    
    async def delete_many(self, keys: List[K]) -> int:
        """Delete multiple keys from cache."""
        count = 0
        for key in keys:
            if await self.delete(key):
                count += 1
        return count


class LRUCache(Cache[str, Any]):
    """
    In-memory LRU (Least Recently Used) cache.
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[float] = None,
    ):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats()
        self._lock = asyncio.Lock()
    
    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None
            
            entry = self._cache[key]
            
            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._stats.hits += 1
            
            return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Set value in cache."""
        async with self._lock:
            expires_at = None
            actual_ttl = ttl or self.default_ttl
            if actual_ttl is not None:
                expires_at = time.time() + actual_ttl
            
            # Check if we need to evict
            if key not in self._cache and len(self._cache) >= self.max_size:
                # Evict oldest (first) entry
                self._cache.popitem(last=False)
                self._stats.evictions += 1
            
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=expires_at,
            )
            self._cache.move_to_end(key)
            self._stats.sets += 1
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.deletes += 1
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        async with self._lock:
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired:
                del self._cache[key]
                return False
            
            return True
    
    async def clear(self) -> None:
        """Clear all entries from cache."""
        async with self._lock:
            self._cache.clear()
    
    async def size(self) -> int:
        """Get number of entries in cache."""
        async with self._lock:
            # Clean expired entries
            expired = [
                k for k, v in self._cache.items()
                if v.is_expired
            ]
            for key in expired:
                del self._cache[key]
            
            return len(self._cache)


class TTLCache(Cache[str, Any]):
    """
    In-memory cache with TTL-based expiration.
    """
    
    def __init__(
        self,
        default_ttl: float = 300.0,
        max_size: Optional[int] = None,
        cleanup_interval: float = 60.0,
    ):
        """
        Initialize TTL cache.
        
        Args:
            default_ttl: Default TTL in seconds
            max_size: Optional maximum size
            cleanup_interval: Interval for background cleanup
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.cleanup_interval = cleanup_interval
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats
    
    async def start_cleanup(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop_cleanup(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            self._cleanup_task = None
    
    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while True:
            await asyncio.sleep(self.cleanup_interval)
            await self._cleanup_expired()
    
    async def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        async with self._lock:
            expired = [
                k for k, v in self._cache.items()
                if v.is_expired
            ]
            for key in expired:
                del self._cache[key]
                self._stats.evictions += 1
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None
            
            entry = self._cache[key]
            
            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                return None
            
            entry.touch()
            self._stats.hits += 1
            return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Set value in cache."""
        async with self._lock:
            actual_ttl = ttl if ttl is not None else self.default_ttl
            expires_at = time.time() + actual_ttl
            
            # Check max size
            if self.max_size and key not in self._cache:
                if len(self._cache) >= self.max_size:
                    # Remove oldest entry by expiration
                    oldest_key = min(
                        self._cache.keys(),
                        key=lambda k: self._cache[k].expires_at or float('inf')
                    )
                    del self._cache[oldest_key]
                    self._stats.evictions += 1
            
            self._cache[key] = CacheEntry(
                value=value,
                expires_at=expires_at,
            )
            self._stats.sets += 1
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.deletes += 1
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        async with self._lock:
            if key not in self._cache:
                return False
            
            if self._cache[key].is_expired:
                del self._cache[key]
                return False
            
            return True
    
    async def clear(self) -> None:
        """Clear all entries from cache."""
        async with self._lock:
            self._cache.clear()
    
    async def size(self) -> int:
        """Get number of entries in cache."""
        await self._cleanup_expired()
        return len(self._cache)


class RedisCache(Cache[str, Any]):
    """
    Distributed cache using Redis.
    """
    
    def __init__(
        self,
        url: str = "redis://localhost:6379",
        prefix: str = "cache",
        default_ttl: Optional[float] = None,
        serializer: Optional[Serializer] = None,
    ):
        """
        Initialize Redis cache.
        
        Args:
            url: Redis connection URL
            prefix: Key prefix for namespacing
            default_ttl: Default TTL in seconds
            serializer: Serializer for values
        """
        self.url = url
        self.prefix = prefix
        self.default_ttl = default_ttl
        self.serializer = serializer or PickleSerializer()
        self._redis = None
        self._stats = CacheStats()
    
    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats
    
    async def _get_redis(self):
        """Get Redis connection lazily."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
                self._redis = redis.from_url(self.url)
            except ImportError:
                raise ImportError(
                    "redis package required for RedisCache. "
                    "Install with: pip install redis"
                )
        return self._redis
    
    def _make_key(self, key: str) -> str:
        """Create prefixed Redis key."""
        return f"{self.prefix}:{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis."""
        redis = await self._get_redis()
        redis_key = self._make_key(key)
        
        data = await redis.get(redis_key)
        
        if data is None:
            self._stats.misses += 1
            return None
        
        self._stats.hits += 1
        return self.serializer.deserialize(data)
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Set value in Redis."""
        redis = await self._get_redis()
        redis_key = self._make_key(key)
        data = self.serializer.serialize(value)
        
        actual_ttl = ttl or self.default_ttl
        if actual_ttl:
            await redis.setex(redis_key, int(actual_ttl), data)
        else:
            await redis.set(redis_key, data)
        
        self._stats.sets += 1
    
    async def delete(self, key: str) -> bool:
        """Delete value from Redis."""
        redis = await self._get_redis()
        redis_key = self._make_key(key)
        
        result = await redis.delete(redis_key)
        if result:
            self._stats.deletes += 1
        return bool(result)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        redis = await self._get_redis()
        redis_key = self._make_key(key)
        return bool(await redis.exists(redis_key))
    
    async def clear(self) -> None:
        """Clear all entries with prefix."""
        redis = await self._get_redis()
        pattern = f"{self.prefix}:*"
        
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break
    
    async def size(self) -> int:
        """Get approximate number of entries."""
        redis = await self._get_redis()
        pattern = f"{self.prefix}:*"
        
        count = 0
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=100)
            count += len(keys)
            if cursor == 0:
                break
        return count
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from Redis."""
        redis = await self._get_redis()
        redis_keys = [self._make_key(k) for k in keys]
        
        values = await redis.mget(redis_keys)
        
        results = {}
        for key, value in zip(keys, values):
            if value is not None:
                results[key] = self.serializer.deserialize(value)
                self._stats.hits += 1
            else:
                self._stats.misses += 1
        
        return results
    
    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


class TieredCache(Cache[str, Any]):
    """
    Multi-tier cache (e.g., memory + Redis).
    
    Checks faster caches first, populates on miss.
    """
    
    def __init__(self, caches: List[Cache[str, Any]]):
        """
        Initialize tiered cache.
        
        Args:
            caches: List of caches from fastest to slowest
        """
        self.caches = caches
        self._stats = CacheStats()
    
    @property
    def stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats
    
    async def get(self, key: str) -> Optional[Any]:
        """Get from first cache with value."""
        for i, cache in enumerate(self.caches):
            value = await cache.get(key)
            if value is not None:
                # Populate faster caches
                for j in range(i):
                    await self.caches[j].set(key, value)
                self._stats.hits += 1
                return value
        
        self._stats.misses += 1
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Set value in all caches."""
        for cache in self.caches:
            await cache.set(key, value, ttl)
        self._stats.sets += 1
    
    async def delete(self, key: str) -> bool:
        """Delete from all caches."""
        result = False
        for cache in self.caches:
            if await cache.delete(key):
                result = True
        if result:
            self._stats.deletes += 1
        return result
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in any cache."""
        for cache in self.caches:
            if await cache.exists(key):
                return True
        return False
    
    async def clear(self) -> None:
        """Clear all caches."""
        for cache in self.caches:
            await cache.clear()
    
    async def size(self) -> int:
        """Get size of largest cache."""
        sizes = []
        for cache in self.caches:
            sizes.append(await cache.size())
        return max(sizes) if sizes else 0


def make_cache_key(*args: Any, **kwargs: Any) -> str:
    """
    Generate cache key from function arguments.
    
    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments
        
    Returns:
        Hash-based cache key
    """
    key_parts = []
    
    for arg in args:
        key_parts.append(repr(arg))
    
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={repr(v)}")
    
    key_str = ":".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(
    cache: Cache,
    ttl: Optional[float] = None,
    key_func: Optional[Callable[..., str]] = None,
    prefix: Optional[str] = None,
    condition: Optional[Callable[[Any], bool]] = None,
) -> Callable[[F], F]:
    """
    Decorator for caching function results.
    
    Args:
        cache: Cache to use
        ttl: TTL for cached values
        key_func: Function to generate cache key
        prefix: Key prefix (defaults to function name)
        condition: Function to determine if result should be cached
        
    Returns:
        Decorated function
        
    Example:
        cache = LRUCache(max_size=1000)
        
        @cached(cache, ttl=300)
        async def get_user(user_id: str) -> dict:
            return await db.fetch_user(user_id)
    """
    def decorator(func: F) -> F:
        func_prefix = prefix or func.__name__
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = make_cache_key(*args, **kwargs)
            
            full_key = f"{func_prefix}:{key}"
            
            # Try cache
            cached_value = await cache.get(full_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result if condition passes
            if condition is None or condition(result):
                await cache.set(full_key, result, ttl)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, run async cache operations
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def cache_invalidate(
    cache: Cache,
    key_func: Optional[Callable[..., str]] = None,
    prefix: Optional[str] = None,
) -> Callable[[F], F]:
    """
    Decorator to invalidate cache on function call.
    
    Args:
        cache: Cache to invalidate
        key_func: Function to generate cache key to invalidate
        prefix: Key prefix
        
    Returns:
        Decorated function
    """
    def decorator(func: F) -> F:
        func_prefix = prefix or ""
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Execute function first
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            # Invalidate cache
            if key_func:
                key = key_func(*args, **kwargs)
                full_key = f"{func_prefix}:{key}" if func_prefix else key
                await cache.delete(full_key)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(async_wrapper(*args, **kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class CacheMiddleware:
    """
    Middleware for caching agent responses.
    """
    
    def __init__(
        self,
        cache: Cache,
        ttl: Optional[float] = None,
        key_func: Optional[Callable[[Dict[str, Any]], str]] = None,
    ):
        """
        Initialize middleware.
        
        Args:
            cache: Cache to use
            ttl: TTL for cached responses
            key_func: Function to generate cache key from context
        """
        self.cache = cache
        self.ttl = ttl
        self.key_func = key_func or self._default_key_func
    
    def _default_key_func(self, context: Dict[str, Any]) -> str:
        """Default key function based on input."""
        input_str = json.dumps(context.get("input", ""), sort_keys=True)
        return hashlib.md5(input_str.encode()).hexdigest()
    
    async def __call__(
        self,
        context: Dict[str, Any],
        next_handler: Callable[[Dict[str, Any]], Any],
    ) -> Any:
        """Process with caching."""
        key = self.key_func(context)
        
        # Check cache
        cached = await self.cache.get(key)
        if cached is not None:
            context["cache_hit"] = True
            return cached
        
        # Execute handler
        context["cache_hit"] = False
        result = await next_handler(context)
        
        # Cache result
        await self.cache.set(key, result, self.ttl)
        
        return result


# Global default cache
_default_cache: Optional[Cache] = None


def get_default_cache() -> Cache:
    """Get default cache."""
    global _default_cache
    if _default_cache is None:
        _default_cache = LRUCache(max_size=10000)
    return _default_cache


def set_default_cache(cache: Cache) -> None:
    """Set default cache."""
    global _default_cache
    _default_cache = cache


__all__ = [
    # Exceptions
    "CacheError",
    "CacheMiss",
    "SerializationError",
    # Data classes
    "CacheEntry",
    "CacheStats",
    # Serializers
    "Serializer",
    "PickleSerializer",
    "JSONSerializer",
    # Base class
    "Cache",
    # Implementations
    "LRUCache",
    "TTLCache",
    "RedisCache",
    "TieredCache",
    # Decorators
    "cached",
    "cache_invalidate",
    # Middleware
    "CacheMiddleware",
    # Functions
    "make_cache_key",
    "get_default_cache",
    "set_default_cache",
]
