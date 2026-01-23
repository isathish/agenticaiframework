"""
Enterprise Dedup Module.

Provides deduplication, idempotency keys, and duplicate
detection for reliable message processing.

Example:
    # Create deduplicator
    dedup = create_deduplicator()
    
    # Check and mark as processed
    if await dedup.is_duplicate("message_123"):
        return  # Skip duplicate
    
    await process_message(message)
    await dedup.mark_processed("message_123")
    
    # With decorator for idempotency
    @idempotent(key_extractor=lambda msg: msg["id"])
    async def process_message(message: dict):
        ...
    
    # Content-based deduplication
    content_dedup = create_content_deduplicator()
    fingerprint = content_dedup.fingerprint(document)
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
from functools import wraps
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

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DedupError(Exception):
    """Dedup error."""
    pass


class DuplicateError(DedupError):
    """Duplicate detected."""
    pass


class DedupStrategy(str, Enum):
    """Deduplication strategies."""
    EXACT = "exact"  # Exact key match
    CONTENT = "content"  # Content hash
    FUZZY = "fuzzy"  # Similarity-based
    WINDOW = "window"  # Time-windowed


class DedupAction(str, Enum):
    """Action on duplicate detection."""
    SKIP = "skip"
    ERROR = "error"
    UPDATE = "update"
    MERGE = "merge"


@dataclass
class DedupConfig:
    """Dedup configuration."""
    ttl_seconds: int = 3600  # 1 hour
    max_entries: int = 100000
    strategy: DedupStrategy = DedupStrategy.EXACT
    action: DedupAction = DedupAction.SKIP


@dataclass
class DedupEntry:
    """Dedup entry record."""
    key: str
    first_seen: datetime
    last_seen: datetime
    count: int = 1
    fingerprint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DedupResult:
    """Result of dedup check."""
    is_duplicate: bool
    key: str
    first_seen: Optional[datetime] = None
    count: int = 0
    fingerprint: Optional[str] = None


@dataclass
class DedupStats:
    """Dedup statistics."""
    total_checks: int = 0
    duplicates_found: int = 0
    entries_count: int = 0
    hit_rate: float = 0.0


class DedupStore(ABC):
    """Abstract dedup storage."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[DedupEntry]:
        """Get entry by key."""
        pass
    
    @abstractmethod
    async def put(self, entry: DedupEntry) -> None:
        """Store entry."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete entry."""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    async def cleanup_expired(self, ttl_seconds: int) -> int:
        """Remove expired entries."""
        pass


class InMemoryDedupStore(DedupStore):
    """In-memory dedup store with LRU eviction."""
    
    def __init__(self, max_entries: int = 100000):
        self._entries: OrderedDict[str, DedupEntry] = OrderedDict()
        self._max_entries = max_entries
    
    async def get(self, key: str) -> Optional[DedupEntry]:
        """Get entry."""
        entry = self._entries.get(key)
        
        if entry:
            # Move to end (LRU)
            self._entries.move_to_end(key)
        
        return entry
    
    async def put(self, entry: DedupEntry) -> None:
        """Store entry."""
        if entry.key in self._entries:
            self._entries.move_to_end(entry.key)
        
        self._entries[entry.key] = entry
        
        # Evict oldest if over limit
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
    
    async def delete(self, key: str) -> bool:
        """Delete entry."""
        if key in self._entries:
            del self._entries[key]
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        """Check existence."""
        return key in self._entries
    
    async def cleanup_expired(self, ttl_seconds: int) -> int:
        """Remove expired entries."""
        cutoff = datetime.now() - timedelta(seconds=ttl_seconds)
        expired = [
            key for key, entry in self._entries.items()
            if entry.last_seen < cutoff
        ]
        
        for key in expired:
            del self._entries[key]
        
        return len(expired)
    
    def __len__(self) -> int:
        return len(self._entries)


class Deduplicator:
    """
    Main deduplication service.
    """
    
    def __init__(
        self,
        store: Optional[DedupStore] = None,
        config: Optional[DedupConfig] = None,
    ):
        self._store = store or InMemoryDedupStore()
        self._config = config or DedupConfig()
        self._stats = DedupStats()
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def is_duplicate(
        self,
        key: str,
        update_if_exists: bool = True,
    ) -> DedupResult:
        """
        Check if a key is a duplicate.
        """
        self._stats.total_checks += 1
        
        entry = await self._store.get(key)
        
        if entry:
            self._stats.duplicates_found += 1
            
            if update_if_exists:
                entry.last_seen = datetime.now()
                entry.count += 1
                await self._store.put(entry)
            
            return DedupResult(
                is_duplicate=True,
                key=key,
                first_seen=entry.first_seen,
                count=entry.count,
                fingerprint=entry.fingerprint,
            )
        
        return DedupResult(
            is_duplicate=False,
            key=key,
        )
    
    async def mark_processed(
        self,
        key: str,
        fingerprint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DedupEntry:
        """
        Mark a key as processed.
        """
        now = datetime.now()
        
        existing = await self._store.get(key)
        
        if existing:
            existing.last_seen = now
            existing.count += 1
            if fingerprint:
                existing.fingerprint = fingerprint
            if metadata:
                existing.metadata.update(metadata)
            await self._store.put(existing)
            return existing
        
        entry = DedupEntry(
            key=key,
            first_seen=now,
            last_seen=now,
            fingerprint=fingerprint,
            metadata=metadata or {},
        )
        
        await self._store.put(entry)
        return entry
    
    async def remove(self, key: str) -> bool:
        """Remove a key from the dedup store."""
        return await self._store.delete(key)
    
    async def check_and_mark(
        self,
        key: str,
        fingerprint: Optional[str] = None,
    ) -> DedupResult:
        """
        Check if duplicate and mark as processed atomically.
        """
        result = await self.is_duplicate(key, update_if_exists=False)
        
        if result.is_duplicate:
            return result
        
        await self.mark_processed(key, fingerprint)
        return result
    
    async def cleanup(self) -> int:
        """Clean up expired entries."""
        count = await self._store.cleanup_expired(self._config.ttl_seconds)
        logger.debug(f"Cleaned up {count} expired dedup entries")
        return count
    
    async def start_cleanup_task(self, interval: int = 300) -> None:
        """Start background cleanup task."""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    await self.cleanup()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Dedup cleanup error: {e}")
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    def get_stats(self) -> DedupStats:
        """Get statistics."""
        if hasattr(self._store, '__len__'):
            self._stats.entries_count = len(self._store)
        
        if self._stats.total_checks > 0:
            self._stats.hit_rate = self._stats.duplicates_found / self._stats.total_checks
        
        return self._stats


class ContentFingerprinter:
    """
    Generate content fingerprints for deduplication.
    """
    
    def __init__(
        self,
        algorithm: str = "sha256",
        normalize: bool = True,
    ):
        self._algorithm = algorithm
        self._normalize = normalize
    
    def fingerprint(
        self,
        content: Any,
        fields: Optional[List[str]] = None,
    ) -> str:
        """
        Generate fingerprint for content.
        """
        # Extract relevant fields
        if fields and isinstance(content, dict):
            content = {k: v for k, v in content.items() if k in fields}
        
        # Normalize
        if self._normalize:
            content = self._normalize_content(content)
        
        # Serialize to JSON
        serialized = json.dumps(content, sort_keys=True, default=str)
        
        # Hash
        hasher = hashlib.new(self._algorithm)
        hasher.update(serialized.encode())
        
        return hasher.hexdigest()
    
    def _normalize_content(self, content: Any) -> Any:
        """Normalize content for consistent fingerprinting."""
        if isinstance(content, str):
            return content.strip().lower()
        
        if isinstance(content, dict):
            return {
                k: self._normalize_content(v)
                for k, v in sorted(content.items())
            }
        
        if isinstance(content, list):
            return [self._normalize_content(item) for item in content]
        
        return content
    
    def are_similar(
        self,
        content1: Any,
        content2: Any,
        threshold: float = 0.9,
    ) -> bool:
        """Check if two contents are similar."""
        fp1 = self.fingerprint(content1)
        fp2 = self.fingerprint(content2)
        
        if fp1 == fp2:
            return True
        
        # For fuzzy matching, would need more sophisticated comparison
        return False


class ContentDeduplicator:
    """
    Content-based deduplication using fingerprints.
    """
    
    def __init__(
        self,
        fingerprinter: Optional[ContentFingerprinter] = None,
        store: Optional[DedupStore] = None,
        config: Optional[DedupConfig] = None,
    ):
        self._fingerprinter = fingerprinter or ContentFingerprinter()
        self._dedup = Deduplicator(store, config)
    
    async def is_duplicate_content(
        self,
        content: Any,
        fields: Optional[List[str]] = None,
    ) -> DedupResult:
        """
        Check if content is a duplicate.
        """
        fingerprint = self._fingerprinter.fingerprint(content, fields)
        return await self._dedup.is_duplicate(fingerprint)
    
    async def mark_content_processed(
        self,
        content: Any,
        fields: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DedupEntry:
        """
        Mark content as processed.
        """
        fingerprint = self._fingerprinter.fingerprint(content, fields)
        return await self._dedup.mark_processed(fingerprint, fingerprint, metadata)
    
    def fingerprint(
        self,
        content: Any,
        fields: Optional[List[str]] = None,
    ) -> str:
        """Get fingerprint for content."""
        return self._fingerprinter.fingerprint(content, fields)


class IdempotencyKey:
    """
    Generate idempotency keys for operations.
    """
    
    @staticmethod
    def generate(*parts: Any) -> str:
        """Generate key from parts."""
        serialized = "|".join(str(p) for p in parts)
        return hashlib.sha256(serialized.encode()).hexdigest()[:32]
    
    @staticmethod
    def from_request(
        method: str,
        path: str,
        body: Optional[Any] = None,
    ) -> str:
        """Generate key from HTTP request."""
        parts = [method.upper(), path]
        
        if body:
            if isinstance(body, dict):
                body_str = json.dumps(body, sort_keys=True)
            else:
                body_str = str(body)
            parts.append(body_str)
        
        return IdempotencyKey.generate(*parts)


class IdempotentExecutor:
    """
    Execute operations idempotently.
    """
    
    def __init__(
        self,
        dedup: Optional[Deduplicator] = None,
        store_result: bool = True,
    ):
        self._dedup = dedup or Deduplicator()
        self._store_result = store_result
        self._results: Dict[str, Any] = {}
    
    async def execute(
        self,
        key: str,
        operation: Callable[[], Any],
    ) -> Tuple[Any, bool]:
        """
        Execute operation idempotently.
        
        Returns:
            Tuple of (result, was_executed)
        """
        result = await self._dedup.is_duplicate(key, update_if_exists=False)
        
        if result.is_duplicate:
            # Return cached result if available
            cached = self._results.get(key)
            return cached, False
        
        # Execute operation
        if asyncio.iscoroutinefunction(operation):
            op_result = await operation()
        else:
            op_result = operation()
        
        # Store result
        await self._dedup.mark_processed(key)
        
        if self._store_result:
            self._results[key] = op_result
        
        return op_result, True
    
    def get_cached_result(self, key: str) -> Optional[Any]:
        """Get cached result for a key."""
        return self._results.get(key)
    
    def clear_cache(self) -> None:
        """Clear result cache."""
        self._results.clear()


class WindowedDeduplicator:
    """
    Time-windowed deduplication.
    Only considers duplicates within a time window.
    """
    
    def __init__(
        self,
        window_seconds: int = 300,  # 5 minutes
        max_entries: int = 10000,
    ):
        self._window_seconds = window_seconds
        self._entries: Dict[str, float] = {}  # key -> timestamp
        self._max_entries = max_entries
    
    def is_duplicate(self, key: str) -> bool:
        """Check if duplicate within window."""
        self._cleanup()
        
        now = time.time()
        
        if key in self._entries:
            entry_time = self._entries[key]
            if now - entry_time < self._window_seconds:
                return True
        
        return False
    
    def mark(self, key: str) -> None:
        """Mark key as seen."""
        self._entries[key] = time.time()
        self._cleanup()
    
    def check_and_mark(self, key: str) -> bool:
        """Check and mark atomically. Returns True if duplicate."""
        if self.is_duplicate(key):
            return True
        
        self.mark(key)
        return False
    
    def _cleanup(self) -> None:
        """Remove expired and excess entries."""
        now = time.time()
        cutoff = now - self._window_seconds
        
        # Remove expired
        self._entries = {
            k: v for k, v in self._entries.items()
            if v >= cutoff
        }
        
        # Remove oldest if over limit
        if len(self._entries) > self._max_entries:
            sorted_items = sorted(self._entries.items(), key=lambda x: x[1])
            excess = len(self._entries) - self._max_entries
            
            for key, _ in sorted_items[:excess]:
                del self._entries[key]


# Decorators
def idempotent(
    key_extractor: Callable[[Any], str],
    dedup: Optional[Deduplicator] = None,
    on_duplicate: Optional[Callable] = None,
) -> Callable:
    """
    Decorator to make a function idempotent.
    
    Example:
        @idempotent(key_extractor=lambda msg: msg["id"])
        async def process_message(message: dict):
            ...
    """
    _dedup = dedup
    
    def decorator(func: Callable) -> Callable:
        executor = IdempotentExecutor(_dedup)
        
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract key
            if args:
                key = key_extractor(args[0])
            else:
                key = key_extractor(kwargs)
            
            async def operation():
                return await func(*args, **kwargs)
            
            result, was_executed = await executor.execute(key, operation)
            
            if not was_executed and on_duplicate:
                return on_duplicate(key, result)
            
            return result
        
        return wrapper
    
    return decorator


def deduplicate(
    key_field: str = "id",
    action: DedupAction = DedupAction.SKIP,
) -> Callable:
    """
    Decorator for simple deduplication.
    
    Example:
        @deduplicate(key_field="message_id")
        async def handle_message(data: dict):
            ...
    """
    dedup = Deduplicator()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract key
            data = args[0] if args else kwargs
            key = data.get(key_field) if isinstance(data, dict) else str(data)
            
            if not key:
                key = hashlib.sha256(str(data).encode()).hexdigest()
            
            result = await dedup.check_and_mark(key)
            
            if result.is_duplicate:
                if action == DedupAction.ERROR:
                    raise DuplicateError(f"Duplicate detected: {key}")
                elif action == DedupAction.SKIP:
                    logger.debug(f"Skipping duplicate: {key}")
                    return None
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_deduplicator(
    ttl_seconds: int = 3600,
    max_entries: int = 100000,
    **kwargs: Any,
) -> Deduplicator:
    """Create a deduplicator."""
    config = DedupConfig(ttl_seconds=ttl_seconds, max_entries=max_entries, **kwargs)
    store = InMemoryDedupStore(max_entries)
    return Deduplicator(store, config)


def create_content_deduplicator(
    algorithm: str = "sha256",
    normalize: bool = True,
    **kwargs: Any,
) -> ContentDeduplicator:
    """Create a content-based deduplicator."""
    fingerprinter = ContentFingerprinter(algorithm, normalize)
    return ContentDeduplicator(fingerprinter, **kwargs)


def create_windowed_deduplicator(
    window_seconds: int = 300,
    max_entries: int = 10000,
) -> WindowedDeduplicator:
    """Create a windowed deduplicator."""
    return WindowedDeduplicator(window_seconds, max_entries)


def create_idempotent_executor(
    store_result: bool = True,
    **kwargs: Any,
) -> IdempotentExecutor:
    """Create an idempotent executor."""
    dedup = create_deduplicator(**kwargs)
    return IdempotentExecutor(dedup, store_result)


__all__ = [
    # Exceptions
    "DedupError",
    "DuplicateError",
    # Enums
    "DedupStrategy",
    "DedupAction",
    # Data classes
    "DedupConfig",
    "DedupEntry",
    "DedupResult",
    "DedupStats",
    # Core classes
    "DedupStore",
    "InMemoryDedupStore",
    "Deduplicator",
    "ContentFingerprinter",
    "ContentDeduplicator",
    "IdempotencyKey",
    "IdempotentExecutor",
    "WindowedDeduplicator",
    # Decorators
    "idempotent",
    "deduplicate",
    # Factory
    "create_deduplicator",
    "create_content_deduplicator",
    "create_windowed_deduplicator",
    "create_idempotent_executor",
]
