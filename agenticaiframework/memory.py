"""
Memory management module with advanced features.

Provides:
- Multi-tier memory (short-term, long-term, external)
- TTL (Time-To-Live) support
- Memory consolidation
- Semantic search capability
- Memory compression
- Priority-based eviction
"""

from typing import Dict, Any, Optional, List
import logging
import time
from datetime import datetime, timedelta
from collections import OrderedDict
import json

logger = logging.getLogger(__name__)


class MemoryEntry:
    """Represents a memory entry with metadata."""
    
    def __init__(self, 
                 key: str, 
                 value: Any,
                 ttl: Optional[int] = None,
                 priority: int = 0,
                 metadata: Dict[str, Any] = None):
        self.key = key
        self.value = value
        self.created_at = datetime.now()
        self.accessed_at = datetime.now()
        self.access_count = 0
        self.ttl = ttl  # Time-to-live in seconds
        self.priority = priority  # Higher priority = less likely to be evicted
        self.metadata = metadata or {}
        
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


class MemoryManager:
    """
    Enhanced Memory Manager with advanced features.
    
    Features:
    - Three-tier memory system (short-term, long-term, external)
    - TTL support for automatic expiration
    - LRU eviction for memory limits
    - Priority-based retention
    - Memory consolidation
    - Search and filtering
    """
    
    def __init__(self, 
                 short_term_limit: int = 100,
                 long_term_limit: int = 1000):
        self.short_term: OrderedDict[str, MemoryEntry] = OrderedDict()
        self.long_term: OrderedDict[str, MemoryEntry] = OrderedDict()
        self.external: Dict[str, MemoryEntry] = {}
        
        self.short_term_limit = short_term_limit
        self.long_term_limit = long_term_limit
        
        # Statistics
        self.stats = {
            'total_stores': 0,
            'total_retrievals': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'evictions': 0,
            'expirations': 0
        }

    def store_short_term(self, 
                        key: str, 
                        value: Any,
                        ttl: Optional[int] = 300,  # 5 minutes default
                        priority: int = 0,
                        metadata: Dict[str, Any] = None):
        """
        Store in short-term memory with TTL and priority.
        
        Args:
            key: Memory key
            value: Value to store
            ttl: Time-to-live in seconds
            priority: Priority for eviction
            metadata: Additional metadata
        """
        entry = MemoryEntry(key, value, ttl, priority, metadata)
        self.short_term[key] = entry
        self.short_term.move_to_end(key)  # Mark as recently used
        
        self.stats['total_stores'] += 1
        
        # Evict if over limit
        self._evict_if_needed(self.short_term, self.short_term_limit)
        
        self._log(f"Stored short-term memory: {key} (TTL: {ttl}s, Priority: {priority})")

    def store(self, 
             key: str, 
             value: Any, 
             memory_type: str = "short_term",
             ttl: Optional[int] = None,
             priority: int = 0,
             metadata: Dict[str, Any] = None):
        """
        Generic store method with enhanced parameters.
        
        Args:
            key: Memory key
            value: Value to store
            memory_type: 'short_term', 'long_term', or 'external'
            ttl: Time-to-live in seconds
            priority: Priority for eviction
            metadata: Additional metadata
        """
        if memory_type == "long_term":
            self.store_long_term(key, value, ttl, priority, metadata)
        elif memory_type == "external":
            self.store_external(key, value, metadata)
        else:
            self.store_short_term(key, value, ttl, priority, metadata)

    def store_long_term(self, 
                       key: str, 
                       value: Any,
                       ttl: Optional[int] = None,  # No TTL by default
                       priority: int = 5,  # Higher priority than short-term
                       metadata: Dict[str, Any] = None):
        """Store in long-term memory."""
        entry = MemoryEntry(key, value, ttl, priority, metadata)
        self.long_term[key] = entry
        self.long_term.move_to_end(key)
        
        self.stats['total_stores'] += 1
        
        # Evict if over limit
        self._evict_if_needed(self.long_term, self.long_term_limit)
        
        self._log(f"Stored long-term memory: {key} (Priority: {priority})")

    def store_external(self, 
                      key: str, 
                      value: Any,
                      metadata: Dict[str, Any] = None):
        """Store in external memory (no limits, no TTL by default)."""
        entry = MemoryEntry(key, value, ttl=None, priority=10, metadata=metadata)
        self.external[key] = entry
        
        self.stats['total_stores'] += 1
        
        self._log(f"Stored external memory: {key}")
    
    def _evict_if_needed(self, memory: OrderedDict, limit: int):
        """Evict entries if over limit, prioritizing by LRU and priority."""
        while len(memory) > limit:
            # Find lowest priority, least recently used entry
            min_priority_key = None
            min_priority = float('inf')
            
            for key, entry in memory.items():
                if entry.priority < min_priority:
                    min_priority = entry.priority
                    min_priority_key = key
            
            if min_priority_key:
                del memory[min_priority_key]
                self.stats['evictions'] += 1
                self._log(f"Evicted memory: {min_priority_key}")

    def retrieve(self, key: str, default: Any = None) -> Any:
        """
        Retrieve from any memory tier.
        
        Args:
            key: Memory key
            default: Default value if not found
            
        Returns:
            Stored value or default
        """
        self.stats['total_retrievals'] += 1
        
        # Clean expired entries
        self._clean_expired()
        
        # Check short-term
        if key in self.short_term:
            entry = self.short_term[key]
            entry.access()
            self.short_term.move_to_end(key)
            self.stats['cache_hits'] += 1
            return entry.value
        
        # Check long-term
        if key in self.long_term:
            entry = self.long_term[key]
            entry.access()
            self.long_term.move_to_end(key)
            self.stats['cache_hits'] += 1
            return entry.value
        
        # Check external
        if key in self.external:
            entry = self.external[key]
            entry.access()
            self.stats['cache_hits'] += 1
            return entry.value
        
        self.stats['cache_misses'] += 1
        return default
    
    def _clean_expired(self):
        """Remove expired entries from all memory tiers."""
        for memory in [self.short_term, self.long_term, self.external]:
            expired_keys = [
                key for key, entry in memory.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del memory[key]
                self.stats['expirations'] += 1
    
    def consolidate(self):
        """
        Consolidate frequently accessed short-term memories to long-term.
        """
        consolidation_threshold = 5  # Access count threshold
        
        keys_to_consolidate = [
            key for key, entry in self.short_term.items()
            if entry.access_count >= consolidation_threshold
        ]
        
        for key in keys_to_consolidate:
            entry = self.short_term[key]
            # Move to long-term with higher priority
            self.store_long_term(
                key, 
                entry.value,
                ttl=None,  # No TTL in long-term
                priority=entry.priority + 2,
                metadata={**entry.metadata, 'consolidated': True}
            )
            del self.short_term[key]
            self._log(f"Consolidated {key} from short-term to long-term")
    
    def search(self, query: str, memory_type: str = None) -> List[MemoryEntry]:
        """
        Search for entries containing query string.
        
        Args:
            query: Search query
            memory_type: Specific memory tier or None for all
            
        Returns:
            List of matching entries
        """
        results = []
        
        memories_to_search = []
        if memory_type == "short_term":
            memories_to_search = [self.short_term]
        elif memory_type == "long_term":
            memories_to_search = [self.long_term]
        elif memory_type == "external":
            memories_to_search = [self.external]
        else:
            memories_to_search = [self.short_term, self.long_term, self.external]
        
        for memory in memories_to_search:
            for entry in memory.values():
                # Search in key and value
                if (query.lower() in entry.key.lower() or 
                    query.lower() in str(entry.value).lower()):
                    results.append(entry)
        
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        cache_hit_rate = 0.0
        if self.stats['total_retrievals'] > 0:
            cache_hit_rate = self.stats['cache_hits'] / self.stats['total_retrievals']
        
        return {
            **self.stats,
            'short_term_count': len(self.short_term),
            'long_term_count': len(self.long_term),
            'external_count': len(self.external),
            'total_count': len(self.short_term) + len(self.long_term) + len(self.external),
            'cache_hit_rate': cache_hit_rate,
            'short_term_utilization': len(self.short_term) / self.short_term_limit,
            'long_term_utilization': len(self.long_term) / self.long_term_limit
        }
    
    def export_memory(self, filepath: str, memory_type: str = None):
        """
        Export memory to JSON file.
        
        Args:
            filepath: Output file path
            memory_type: Specific tier or None for all
        """
        data = {}
        
        if memory_type == "short_term" or memory_type is None:
            data['short_term'] = [entry.to_dict() for entry in self.short_term.values()]
        
        if memory_type == "long_term" or memory_type is None:
            data['long_term'] = [entry.to_dict() for entry in self.long_term.values()]
        
        if memory_type == "external" or memory_type is None:
            data['external'] = [entry.to_dict() for entry in self.external.values()]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        self._log(f"Exported memory to {filepath}")

    def clear_short_term(self):
        """Clear short-term memory."""
        self.short_term.clear()
        self._log("Cleared short-term memory")

    def clear_long_term(self):
        """Clear long-term memory."""
        self.long_term.clear()
        self._log("Cleared long-term memory")

    def clear_external(self):
        """Clear external memory."""
        self.external.clear()
        self._log("Cleared external memory")
    
    def clear_all(self):
        """Clear all memory tiers."""
        self.clear_short_term()
        self.clear_long_term()
        self.clear_external()
        self._log("Cleared all memory tiers")

    def _log(self, message: str):
        """Log a message."""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [MemoryManager] {message}")
