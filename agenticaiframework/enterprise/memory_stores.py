"""
Enterprise Memory Stores Module.

Provides persistent memory, session storage, vector stores,
and memory management patterns for agents.

Example:
    # Create memory store
    store = InMemoryStore()
    await store.save("key", {"data": "value"})
    data = await store.load("key")
    
    # Session memory
    session = SessionMemory("session-123")
    session.add_message("user", "Hello")
    
    # Vector store
    vectors = SimpleVectorStore(embedding_fn=get_embedding)
    await vectors.add("doc1", "Document text")
    results = await vectors.search("query", k=5)
"""

from __future__ import annotations

import asyncio
import json
import hashlib
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import logging
import time
import pickle

logger = logging.getLogger(__name__)

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')


class MemoryError(Exception):
    """Memory operation error."""
    pass


class MemoryType(str, Enum):
    """Types of memory."""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


@dataclass
class MemoryItem:
    """A single memory item."""
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl: Optional[int] = None  # seconds
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_expired(self) -> bool:
        """Check if item is expired."""
        if self.ttl is None:
            return False
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl
    
    def touch(self) -> None:
        """Update access time."""
        self.accessed_at = datetime.now()
        self.access_count += 1


@dataclass
class Message:
    """A conversation message."""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
        )


@dataclass
class VectorRecord:
    """A vector record with embedding."""
    id: str
    text: str
    vector: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SearchResult:
    """Vector search result."""
    id: str
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemoryStore(ABC, Generic[K, V]):
    """Abstract memory store interface."""
    
    @abstractmethod
    async def save(self, key: K, value: V, **kwargs: Any) -> None:
        """Save a value."""
        pass
    
    @abstractmethod
    async def load(self, key: K) -> Optional[V]:
        """Load a value."""
        pass
    
    @abstractmethod
    async def delete(self, key: K) -> bool:
        """Delete a value."""
        pass
    
    @abstractmethod
    async def exists(self, key: K) -> bool:
        """Check if key exists."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all values."""
        pass


class InMemoryStore(MemoryStore[str, Any]):
    """In-memory key-value store."""
    
    def __init__(self, max_size: Optional[int] = None):
        self._data: Dict[str, MemoryItem] = {}
        self._max_size = max_size
    
    async def save(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Save a value."""
        if self._max_size and len(self._data) >= self._max_size:
            await self._evict()
        
        now = datetime.now()
        
        if key in self._data:
            item = self._data[key]
            item.value = value
            item.updated_at = now
            if ttl is not None:
                item.ttl = ttl
            if metadata:
                item.metadata.update(metadata)
        else:
            self._data[key] = MemoryItem(
                key=key,
                value=value,
                ttl=ttl,
                metadata=metadata or {},
            )
    
    async def load(self, key: str) -> Optional[Any]:
        """Load a value."""
        item = self._data.get(key)
        
        if item is None:
            return None
        
        if item.is_expired:
            del self._data[key]
            return None
        
        item.touch()
        return item.value
    
    async def delete(self, key: str) -> bool:
        """Delete a value."""
        if key in self._data:
            del self._data[key]
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        item = self._data.get(key)
        if item is None:
            return False
        if item.is_expired:
            del self._data[key]
            return False
        return True
    
    async def clear(self) -> None:
        """Clear all values."""
        self._data.clear()
    
    async def keys(self) -> List[str]:
        """Get all keys."""
        self._cleanup_expired()
        return list(self._data.keys())
    
    async def values(self) -> List[Any]:
        """Get all values."""
        self._cleanup_expired()
        return [item.value for item in self._data.values()]
    
    async def items(self) -> List[Tuple[str, Any]]:
        """Get all items."""
        self._cleanup_expired()
        return [(k, item.value) for k, item in self._data.items()]
    
    def _cleanup_expired(self) -> None:
        """Remove expired items."""
        expired = [k for k, v in self._data.items() if v.is_expired]
        for key in expired:
            del self._data[key]
    
    async def _evict(self) -> None:
        """Evict oldest item (LRU)."""
        if not self._data:
            return
        
        oldest_key = min(
            self._data.keys(),
            key=lambda k: self._data[k].accessed_at
        )
        del self._data[oldest_key]


class FileStore(MemoryStore[str, Any]):
    """File-based persistent store."""
    
    def __init__(
        self,
        directory: Union[str, Path],
        serializer: str = "json",
    ):
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._serializer = serializer
    
    def _get_path(self, key: str) -> Path:
        """Get file path for key."""
        safe_key = hashlib.md5(key.encode()).hexdigest()
        ext = ".json" if self._serializer == "json" else ".pkl"
        return self._directory / f"{safe_key}{ext}"
    
    async def save(
        self,
        key: str,
        value: Any,
        **kwargs: Any,
    ) -> None:
        """Save a value to file."""
        path = self._get_path(key)
        
        data = {
            "key": key,
            "value": value,
            "metadata": kwargs,
            "timestamp": datetime.now().isoformat(),
        }
        
        if self._serializer == "json":
            path.write_text(json.dumps(data, default=str))
        else:
            path.write_bytes(pickle.dumps(data))
    
    async def load(self, key: str) -> Optional[Any]:
        """Load a value from file."""
        path = self._get_path(key)
        
        if not path.exists():
            return None
        
        try:
            if self._serializer == "json":
                data = json.loads(path.read_text())
            else:
                data = pickle.loads(path.read_bytes())
            
            return data.get("value")
        except Exception as e:
            logger.error(f"Failed to load {key}: {e}")
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete a file."""
        path = self._get_path(key)
        
        if path.exists():
            path.unlink()
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        """Check if file exists."""
        return self._get_path(key).exists()
    
    async def clear(self) -> None:
        """Delete all files."""
        for path in self._directory.glob("*"):
            if path.is_file():
                path.unlink()


class SessionMemory:
    """
    Session-based conversation memory.
    """
    
    def __init__(
        self,
        session_id: str,
        max_messages: int = 100,
        store: Optional[MemoryStore] = None,
    ):
        self._session_id = session_id
        self._max_messages = max_messages
        self._messages: List[Message] = []
        self._store = store
        self._metadata: Dict[str, Any] = {}
    
    @property
    def session_id(self) -> str:
        return self._session_id
    
    @property
    def messages(self) -> List[Message]:
        return self._messages
    
    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """Add a message to the session."""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        
        self._messages.append(message)
        
        # Trim if exceeds max
        if len(self._messages) > self._max_messages:
            self._messages = self._messages[-self._max_messages:]
        
        return message
    
    def add_user_message(self, content: str) -> Message:
        """Add a user message."""
        return self.add_message("user", content)
    
    def add_assistant_message(self, content: str) -> Message:
        """Add an assistant message."""
        return self.add_message("assistant", content)
    
    def add_system_message(self, content: str) -> Message:
        """Add a system message."""
        return self.add_message("system", content)
    
    def get_messages(
        self,
        limit: Optional[int] = None,
        roles: Optional[List[str]] = None,
    ) -> List[Message]:
        """Get messages with optional filtering."""
        messages = self._messages
        
        if roles:
            messages = [m for m in messages if m.role in roles]
        
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    def to_openai_messages(self) -> List[Dict[str, str]]:
        """Convert to OpenAI message format."""
        return [
            {"role": m.role, "content": m.content}
            for m in self._messages
        ]
    
    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()
    
    async def save(self) -> None:
        """Persist session to store."""
        if self._store:
            data = {
                "messages": [m.to_dict() for m in self._messages],
                "metadata": self._metadata,
            }
            await self._store.save(self._session_id, data)
    
    async def load(self) -> bool:
        """Load session from store."""
        if not self._store:
            return False
        
        data = await self._store.load(self._session_id)
        if data:
            self._messages = [
                Message.from_dict(m)
                for m in data.get("messages", [])
            ]
            self._metadata = data.get("metadata", {})
            return True
        
        return False


class VectorStore(ABC):
    """Abstract vector store interface."""
    
    @abstractmethod
    async def add(
        self,
        id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a document."""
        pass
    
    @abstractmethod
    async def search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Search for similar documents."""
        pass
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete a document."""
        pass
    
    @abstractmethod
    async def clear(self) -> None:
        """Clear all documents."""
        pass


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)


class SimpleVectorStore(VectorStore):
    """
    Simple in-memory vector store.
    """
    
    def __init__(
        self,
        embedding_fn: Callable[[str], List[float]],
    ):
        self._embedding_fn = embedding_fn
        self._records: Dict[str, VectorRecord] = {}
    
    async def add(
        self,
        id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a document with embedding."""
        if asyncio.iscoroutinefunction(self._embedding_fn):
            vector = await self._embedding_fn(text)
        else:
            vector = self._embedding_fn(text)
        
        self._records[id] = VectorRecord(
            id=id,
            text=text,
            vector=vector,
            metadata=metadata or {},
        )
    
    async def add_with_vector(
        self,
        id: str,
        text: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a document with pre-computed embedding."""
        self._records[id] = VectorRecord(
            id=id,
            text=text,
            vector=vector,
            metadata=metadata or {},
        )
    
    async def search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Search for similar documents."""
        if asyncio.iscoroutinefunction(self._embedding_fn):
            query_vector = await self._embedding_fn(query)
        else:
            query_vector = self._embedding_fn(query)
        
        return await self.search_by_vector(query_vector, k, filter)
    
    async def search_by_vector(
        self,
        vector: List[float],
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Search by vector."""
        scores = []
        
        for record in self._records.values():
            # Apply filter
            if filter:
                match = all(
                    record.metadata.get(key) == value
                    for key, value in filter.items()
                )
                if not match:
                    continue
            
            similarity = _cosine_similarity(vector, record.vector)
            scores.append((record, similarity))
        
        # Sort by similarity
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return [
            SearchResult(
                id=record.id,
                text=record.text,
                score=score,
                metadata=record.metadata,
            )
            for record, score in scores[:k]
        ]
    
    async def delete(self, id: str) -> bool:
        """Delete a document."""
        if id in self._records:
            del self._records[id]
            return True
        return False
    
    async def clear(self) -> None:
        """Clear all documents."""
        self._records.clear()
    
    async def get(self, id: str) -> Optional[VectorRecord]:
        """Get a document by ID."""
        return self._records.get(id)
    
    async def count(self) -> int:
        """Get document count."""
        return len(self._records)


class SlidingWindowMemory:
    """
    Sliding window memory with token counting.
    """
    
    def __init__(
        self,
        max_tokens: int = 4000,
        token_counter: Optional[Callable[[str], int]] = None,
    ):
        self._max_tokens = max_tokens
        self._token_counter = token_counter or (lambda s: len(s) // 4)
        self._messages: List[Message] = []
        self._current_tokens = 0
    
    def add(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """Add a message, evicting old ones if needed."""
        tokens = self._token_counter(content)
        
        # Evict until we have room
        while self._current_tokens + tokens > self._max_tokens and self._messages:
            evicted = self._messages.pop(0)
            self._current_tokens -= self._token_counter(evicted.content)
        
        message = Message(role=role, content=content, metadata=metadata or {})
        self._messages.append(message)
        self._current_tokens += tokens
        
        return message
    
    @property
    def messages(self) -> List[Message]:
        return self._messages
    
    @property
    def current_tokens(self) -> int:
        return self._current_tokens
    
    def clear(self) -> None:
        """Clear memory."""
        self._messages.clear()
        self._current_tokens = 0


class SummarizedMemory:
    """
    Memory that summarizes old messages.
    """
    
    def __init__(
        self,
        summarizer: Callable[[List[Message]], str],
        max_messages: int = 20,
        summary_threshold: int = 15,
    ):
        self._summarizer = summarizer
        self._max_messages = max_messages
        self._summary_threshold = summary_threshold
        self._messages: List[Message] = []
        self._summary: Optional[str] = None
    
    async def add(
        self,
        role: str,
        content: str,
    ) -> Message:
        """Add a message, summarizing if needed."""
        message = Message(role=role, content=content)
        self._messages.append(message)
        
        if len(self._messages) >= self._max_messages:
            await self._summarize()
        
        return message
    
    async def _summarize(self) -> None:
        """Summarize older messages."""
        to_summarize = self._messages[:self._summary_threshold]
        to_keep = self._messages[self._summary_threshold:]
        
        if asyncio.iscoroutinefunction(self._summarizer):
            summary = await self._summarizer(to_summarize)
        else:
            summary = self._summarizer(to_summarize)
        
        # Update summary
        if self._summary:
            self._summary = f"{self._summary}\n\n{summary}"
        else:
            self._summary = summary
        
        self._messages = to_keep
    
    @property
    def summary(self) -> Optional[str]:
        return self._summary
    
    @property
    def messages(self) -> List[Message]:
        return self._messages
    
    def get_context(self) -> str:
        """Get full context with summary."""
        parts = []
        
        if self._summary:
            parts.append(f"Previous conversation summary:\n{self._summary}")
        
        if self._messages:
            parts.append("Recent messages:")
            for m in self._messages:
                parts.append(f"{m.role}: {m.content}")
        
        return "\n\n".join(parts)


# Factory functions
def create_memory_store(
    store_type: str = "memory",
    **kwargs: Any,
) -> MemoryStore:
    """
    Factory function to create a memory store.
    
    Args:
        store_type: Type of store ('memory', 'file')
        **kwargs: Store-specific arguments
    """
    if store_type == "memory":
        return InMemoryStore(**kwargs)
    elif store_type == "file":
        return FileStore(**kwargs)
    else:
        raise ValueError(f"Unknown store type: {store_type}")


def create_session_memory(
    session_id: str,
    persistent: bool = False,
    store_path: Optional[str] = None,
    **kwargs: Any,
) -> SessionMemory:
    """
    Factory function to create session memory.
    """
    store = None
    if persistent and store_path:
        store = FileStore(store_path)
    
    return SessionMemory(session_id, store=store, **kwargs)


__all__ = [
    # Exceptions
    "MemoryError",
    # Enums
    "MemoryType",
    # Data classes
    "MemoryItem",
    "Message",
    "VectorRecord",
    "SearchResult",
    # Stores
    "MemoryStore",
    "InMemoryStore",
    "FileStore",
    # Session memory
    "SessionMemory",
    # Vector stores
    "VectorStore",
    "SimpleVectorStore",
    # Window memory
    "SlidingWindowMemory",
    "SummarizedMemory",
    # Factory
    "create_memory_store",
    "create_session_memory",
]
