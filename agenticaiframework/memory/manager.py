"""
Memory Manager with multi-tier storage and advanced features.

Provides a comprehensive memory management system with:
- Three-tier storage (short-term, long-term, external)
- TTL support for automatic expiration
- LRU eviction for memory limits
- Priority-based retention
- Memory consolidation
- Search and filtering
"""

from typing import Dict, Any, Optional, List
from collections import OrderedDict
import logging
import time
import json

from .types import MemoryEntry, MemoryStats
from .compat import MemoryCompatMixin

logger = logging.getLogger(__name__)


class MemoryManager(MemoryCompatMixin):
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
        self.stats = MemoryStats()

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
        entry = MemoryEntry(
            key=key, value=value, ttl=ttl, 
            priority=priority, metadata=metadata or {}
        )
        self.short_term[key] = entry
        self.short_term.move_to_end(key)  # Mark as recently used
        
        self.stats.total_stores += 1
        
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
        entry = MemoryEntry(
            key=key, value=value, ttl=ttl, 
            priority=priority, metadata=metadata or {}
        )
        self.long_term[key] = entry
        self.long_term.move_to_end(key)
        
        self.stats.total_stores += 1
        
        # Evict if over limit
        self._evict_if_needed(self.long_term, self.long_term_limit)
        
        self._log(f"Stored long-term memory: {key} (Priority: {priority})")

    def store_external(self, 
                      key: str, 
                      value: Any,
                      metadata: Dict[str, Any] = None):
        """Store in external memory (no limits, no TTL by default)."""
        entry = MemoryEntry(
            key=key, value=value, ttl=None, 
            priority=10, metadata=metadata or {}
        )
        self.external[key] = entry
        
        self.stats.total_stores += 1
        
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
                self.stats.evictions += 1
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
        self.stats.total_retrievals += 1
        
        # Clean expired entries
        self._clean_expired()
        
        # Check short-term
        if key in self.short_term:
            entry = self.short_term[key]
            entry.access()
            self.short_term.move_to_end(key)
            self.stats.cache_hits += 1
            return entry.value
        
        # Check long-term
        if key in self.long_term:
            entry = self.long_term[key]
            entry.access()
            self.long_term.move_to_end(key)
            self.stats.cache_hits += 1
            return entry.value
        
        # Check external
        if key in self.external:
            entry = self.external[key]
            entry.access()
            self.stats.cache_hits += 1
            return entry.value
        
        self.stats.cache_misses += 1
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
                self.stats.expirations += 1
    
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
                if self._matches_query(entry, query):
                    results.append(entry)
        
        return results
    
    def _matches_query(self, entry: MemoryEntry, query: str) -> bool:
        """Check if entry matches search query."""
        query_lower = query.lower()
        
        # Check key
        if query_lower in entry.key.lower():
            return True
        
        # Check value if string
        if isinstance(entry.value, str) and query_lower in entry.value.lower():
            return True
        
        # Check metadata
        for key, value in entry.metadata.items():
            if query_lower in str(key).lower() or query_lower in str(value).lower():
                return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            **self.stats.to_dict(),
            'hit_rate': self.stats.hit_rate,
            'short_term_count': len(self.short_term),
            'long_term_count': len(self.long_term),
            'external_count': len(self.external)
        }
    
    def clear(self, memory_type: str = None):
        """
        Clear memory entries.
        
        Args:
            memory_type: Specific tier or None for all
        """
        if memory_type == "short_term":
            self.short_term.clear()
        elif memory_type == "long_term":
            self.long_term.clear()
        elif memory_type == "external":
            self.external.clear()
        else:
            self.short_term.clear()
            self.long_term.clear()
            self.external.clear()
        
        self._log(f"Cleared memory: {memory_type or 'all'}")
    
    def export_to_json(self, filepath: str):
        """Export all memory to JSON file."""
        data = {
            'short_term': {k: v.to_dict() for k, v in self.short_term.items()},
            'long_term': {k: v.to_dict() for k, v in self.long_term.items()},
            'external': {k: v.to_dict() for k, v in self.external.items()},
            'stats': self.stats.to_dict()
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        self._log(f"Exported memory to {filepath}")
    
    def _log(self, message: str):
        """Log a message."""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [MemoryManager] {message}")
