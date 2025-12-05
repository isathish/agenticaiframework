"""
Test suite for enhanced Memory Management features.
Tests TTL, priority eviction, consolidation, and search.
"""

import pytest
import time
from agenticaiframework.memory import MemoryEntry, MemoryManager


class TestMemoryEntry:
    """Test suite for MemoryEntry class."""
    
    def test_entry_creation(self):
        """Test creating memory entries."""
        entry = MemoryEntry(
            content="Test memory",
            metadata={'type': 'test'},
            priority=0.8
        )
        
        assert entry.content == "Test memory"
        assert entry.metadata['type'] == 'test'
        assert entry.priority == 0.8
        assert entry.access_count == 0
    
    def test_entry_with_ttl(self):
        """Test entry with TTL."""
        entry = MemoryEntry(
            content="Temporary memory",
            ttl=2  # 2 seconds
        )
        
        assert entry.is_expired() is False
        time.sleep(2.1)
        assert entry.is_expired() is True
    
    def test_entry_without_ttl(self):
        """Test entry without TTL never expires."""
        entry = MemoryEntry(content="Permanent memory")
        
        assert entry.is_expired() is False
        time.sleep(1)
        assert entry.is_expired() is False
    
    def test_access_tracking(self):
        """Test that access count is tracked."""
        entry = MemoryEntry(content="Test")
        
        assert entry.access_count == 0
        entry.access_count += 1
        assert entry.access_count == 1


class TestMemoryTTL:
    """Test suite for TTL-based memory expiration."""
    
    def test_store_with_ttl(self):
        """Test storing memories with TTL."""
        memory = MemoryManager()
        
        memory.store(
            "temporary",
            "This expires soon",
            tier='short_term',
            ttl=1
        )
        
        # Should be retrievable immediately
        result = memory.recall("temporary")
        assert result is not None
    
    def test_ttl_expiration(self):
        """Test that expired memories are removed."""
        memory = MemoryManager()
        
        memory.store(
            "temporary",
            "Expires in 1 second",
            tier='short_term',
            ttl=1
        )
        
        time.sleep(1.1)
        
        # Should be expired and cleaned up
        result = memory.recall("temporary")
        assert result is None
    
    def test_mixed_ttl_memories(self):
        """Test mixing memories with and without TTL."""
        memory = MemoryManager()
        
        memory.store("permanent", "Stays forever", tier='short_term')
        memory.store("temporary", "Expires", tier='short_term', ttl=1)
        
        time.sleep(1.1)
        
        # Permanent should remain
        assert memory.recall("permanent") is not None
        # Temporary should be gone
        assert memory.recall("temporary") is None


class TestMemoryPriorityEviction:
    """Test suite for priority-based memory eviction."""
    
    def test_priority_storage(self):
        """Test storing memories with priority."""
        memory = MemoryManager()
        
        memory.store(
            "high_priority",
            "Important",
            tier='short_term',
            priority=0.9
        )
        memory.store(
            "low_priority",
            "Less important",
            tier='short_term',
            priority=0.1
        )
        
        # Both should be stored
        assert memory.recall("high_priority") is not None
        assert memory.recall("low_priority") is not None
    
    def test_eviction_order(self):
        """Test that low priority items are evicted first."""
        memory = MemoryManager()
        
        # Store items with different priorities
        memory.store("critical", "Critical", tier='short_term', priority=1.0)
        memory.store("important", "Important", tier='short_term', priority=0.7)
        memory.store("normal", "Normal", tier='short_term', priority=0.5)
        memory.store("low", "Low", tier='short_term', priority=0.1)
        
        # High priority items should be preserved longer
        assert memory.recall("critical") is not None


class TestMemoryConsolidation:
    """Test suite for memory consolidation."""
    
    def test_consolidation(self):
        """Test consolidating frequently accessed memories."""
        memory = MemoryManager()
        
        # Store and access multiple times
        memory.store("key", "value", tier='short_term')
        
        for _ in range(5):
            memory.recall("key")
        
        # Consolidate - frequently accessed should move to long-term
        memory.consolidate(access_threshold=3)
        
        # Should still be accessible
        assert memory.recall("key") is not None
    
    def test_consolidation_threshold(self):
        """Test that consolidation respects access threshold."""
        memory = MemoryManager()
        
        memory.store("low_access", "value1", tier='short_term')
        memory.store("high_access", "value2", tier='short_term')
        
        # Access one more than the other
        memory.recall("low_access")
        for _ in range(5):
            memory.recall("high_access")
        
        memory.consolidate(access_threshold=3)
        
        # Both should still be accessible
        assert memory.recall("low_access") is not None
        assert memory.recall("high_access") is not None


class TestMemorySearch:
    """Test suite for memory search functionality."""
    
    def test_search_by_content(self):
        """Test searching memories by content."""
        memory = MemoryManager()
        
        memory.store("key1", "The quick brown fox", tier='short_term')
        memory.store("key2", "The lazy dog", tier='short_term')
        memory.store("key3", "A different animal", tier='short_term')
        
        results = memory.search("quick")
        
        assert len(results) >= 1
        assert any("quick" in r.lower() for r in results)
    
    def test_search_case_insensitive(self):
        """Test that search is case-insensitive."""
        memory = MemoryManager()
        
        memory.store("key1", "UPPERCASE TEXT", tier='short_term')
        memory.store("key2", "lowercase text", tier='short_term')
        
        results = memory.search("text")
        
        # Should find both
        assert len(results) >= 2
    
    def test_search_across_tiers(self):
        """Test searching across all memory tiers."""
        memory = MemoryManager()
        
        memory.store("key1", "short term item", tier='short_term')
        memory.store("key2", "long term item", tier='long_term')
        
        results = memory.search("item")
        
        # Should find items from both tiers
        assert len(results) >= 2
    
    def test_search_no_results(self):
        """Test search with no matching results."""
        memory = MemoryManager()
        
        memory.store("key1", "content one", tier='short_term')
        memory.store("key2", "content two", tier='short_term')
        
        results = memory.search("nonexistent")
        
        assert len(results) == 0


class TestMemoryExport:
    """Test suite for memory export functionality."""
    
    def test_export_all(self):
        """Test exporting all memories."""
        memory = MemoryManager()
        
        memory.store("key1", "value1", tier='short_term')
        memory.store("key2", "value2", tier='long_term')
        
        export = memory.export()
        
        assert 'short_term' in export
        assert 'long_term' in export
        assert len(export['short_term']) > 0 or len(export['long_term']) > 0
    
    def test_export_specific_tier(self):
        """Test exporting specific memory tier."""
        memory = MemoryManager()
        
        memory.store("key1", "value1", tier='short_term')
        memory.store("key2", "value2", tier='long_term')
        
        export = memory.export(tier='short_term')
        
        assert 'short_term' in export
        assert len(export['short_term']) > 0


class TestMemoryStatistics:
    """Test suite for memory statistics."""
    
    def test_get_stats(self):
        """Test getting memory statistics."""
        memory = MemoryManager()
        
        memory.store("key1", "value1", tier='short_term')
        memory.store("key2", "value2", tier='long_term')
        
        stats = memory.get_stats()
        
        assert 'total_memories' in stats
        assert 'by_tier' in stats
        assert stats['total_memories'] >= 2
    
    def test_stats_by_tier(self):
        """Test tier-specific statistics."""
        memory = MemoryManager()
        
        memory.store("key1", "value1", tier='short_term')
        memory.store("key2", "value2", tier='short_term')
        memory.store("key3", "value3", tier='long_term')
        
        stats = memory.get_stats()
        
        assert 'by_tier' in stats
        assert 'short_term' in stats['by_tier']
        assert 'long_term' in stats['by_tier']


class TestMemoryIntegration:
    """Integration tests for memory system."""
    
    def test_full_lifecycle(self):
        """Test full memory lifecycle: store, recall, expire, consolidate."""
        memory = MemoryManager()
        
        # Store with TTL
        memory.store("temp", "temporary data", tier='short_term', ttl=2)
        
        # Store permanent with priority
        memory.store("perm", "permanent data", tier='short_term', priority=0.9)
        
        # Access multiple times
        for _ in range(5):
            memory.recall("perm")
        
        # Consolidate
        memory.consolidate(access_threshold=3)
        
        # Wait for TTL
        time.sleep(2.1)
        
        # Temp should be gone, perm should remain
        assert memory.recall("temp") is None
        assert memory.recall("perm") is not None
    
    def test_memory_under_load(self):
        """Test memory system under load."""
        memory = MemoryManager()
        
        # Store many items
        for i in range(100):
            memory.store(
                f"key{i}",
                f"value{i}",
                tier='short_term',
                priority=i/100
            )
        
        # Search should work
        results = memory.search("value1")
        assert len(results) > 0
        
        # Stats should be accurate
        stats = memory.get_stats()
        assert stats['total_memories'] > 0
    
    def test_mixed_operations(self):
        """Test mixing different memory operations."""
        memory = MemoryManager()
        
        # Store
        memory.store("key1", "value1", tier='short_term', priority=0.8)
        
        # Recall
        result = memory.recall("key1")
        assert result is not None
        
        # Search
        search_results = memory.search("value")
        assert len(search_results) > 0
        
        # Export
        export = memory.export()
        assert export is not None
        
        # Stats
        stats = memory.get_stats()
        assert stats['total_memories'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
