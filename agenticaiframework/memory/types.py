"""
Memory types and data structures.

Provides the foundational types for the memory management system.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field


@dataclass
class MemoryEntry:
    """Represents a memory entry with metadata."""
    
    key: str
    value: Any
    ttl: Optional[int] = None  # Time-to-live in seconds
    priority: int = 0  # Higher priority = less likely to be evicted
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        expiry_time = self.created_at + timedelta(seconds=self.ttl)
        return datetime.now() > expiry_time
    
    def access(self):
        """Mark entry as accessed."""
        self.accessed_at = datetime.now()
        self.access_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'key': self.key,
            'value': self.value,
            'created_at': self.created_at.isoformat(),
            'accessed_at': self.accessed_at.isoformat(),
            'access_count': self.access_count,
            'ttl': self.ttl,
            'priority': self.priority,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """Create MemoryEntry from dictionary."""
        entry = cls(
            key=data['key'],
            value=data['value'],
            ttl=data.get('ttl'),
            priority=data.get('priority', 0),
            metadata=data.get('metadata', {})
        )
        if 'created_at' in data:
            entry.created_at = datetime.fromisoformat(data['created_at'])
        if 'accessed_at' in data:
            entry.accessed_at = datetime.fromisoformat(data['accessed_at'])
        if 'access_count' in data:
            entry.access_count = data['access_count']
        return entry


@dataclass
class MemoryStats:
    """Statistics for memory management."""
    total_stores: int = 0
    total_retrievals: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    evictions: int = 0
    expirations: int = 0
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            'total_stores': self.total_stores,
            'total_retrievals': self.total_retrievals,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'evictions': self.evictions,
            'expirations': self.expirations
        }
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_retrievals == 0:
            return 0.0
        return self.cache_hits / self.total_retrievals
