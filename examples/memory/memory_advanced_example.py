"""
Enhanced Memory Management Example
Demonstrates TTL, priority-based eviction, memory consolidation, and search.
"""

from agenticaiframework import MemoryManager
import time

def main():
    print("=" * 80)
    print("Enhanced Memory Management Example")
    print("=" * 80)
    
    # 1. Create memory manager with limits
    print("\n1. Creating Memory Manager with Limits")
    print("-" * 40)
    
    memory = MemoryManager(
        short_term_limit=5,  # Small limit for demonstration
        long_term_limit=10
    )
    
    print(f"Short-term limit: {memory.short_term_limit}")
    print(f"Long-term limit: {memory.long_term_limit}")
    
    # 2. Store with TTL (Time-To-Live)
    print("\n2. Storing Data with TTL")
    print("-" * 40)
    
    # Short TTL (will expire quickly)
    memory.store_short_term(
        "temp_data",
        "This will expire in 2 seconds",
        ttl=2,
        priority=0
    )
    
    # Longer TTL
    memory.store_short_term(
        "session_data",
        "User session information",
        ttl=300,
        priority=5
    )
    
    print("Stored data with TTL")
    print(f"Initial stats: {memory.get_stats()}")
    
    # Wait and check expiration
    print("\nWaiting 3 seconds for TTL expiration...")
    time.sleep(3)
    
    temp_value = memory.retrieve("temp_data")
    session_value = memory.retrieve("session_data")
    
    print(f"Temp data (should be None): {temp_value}")
    print(f"Session data (should exist): {session_value}")
    
    stats = memory.get_stats()
    print(f"Expirations: {stats['expirations']}")
    
    # 3. Priority-based eviction
    print("\n3. Priority-Based Eviction")
    print("-" * 40)
    
    # Add items with different priorities
    for i in range(8):
        priority = i % 3  # Priorities 0, 1, 2
        memory.store_short_term(
            f"item_{i}",
            f"Data {i}",
            ttl=None,  # No expiration
            priority=priority,
            metadata={"index": i}
        )
        print(f"Stored item_{i} with priority {priority}")
    
    print(f"\nShort-term count: {len(memory.short_term)}")
    print(f"Items in memory: {list(memory.short_term.keys())}")
    
    stats = memory.get_stats()
    print(f"Evictions performed: {stats['evictions']}")
    
    # 4. Long-term storage
    print("\n4. Long-Term Storage")
    print("-" * 40)
    
    important_data = {
        "user_preferences": {"theme": "dark", "language": "en"},
        "system_config": {"version": "2.0", "env": "production"},
        "cache_key": "abc123def456"
    }
    
    for key, value in important_data.items():
        memory.store_long_term(
            key,
            value,
            priority=8,  # High priority
            metadata={"type": "config"}
        )
        print(f"Stored in long-term: {key}")
    
    # 5. Memory consolidation
    print("\n5. Memory Consolidation")
    print("-" * 40)
    
    # Add frequently accessed short-term data
    memory.store_short_term("frequent_access", "Accessed often", ttl=None, priority=3)
    
    # Access it multiple times to trigger consolidation
    for i in range(6):
        memory.retrieve("frequent_access")
    
    print(f"Before consolidation:")
    print(f"  Short-term: {len(memory.short_term)}")
    print(f"  Long-term: {len(memory.long_term)}")
    
    # Perform consolidation
    memory.consolidate()
    
    print(f"After consolidation:")
    print(f"  Short-term: {len(memory.short_term)}")
    print(f"  Long-term: {len(memory.long_term)}")
    
    # 6. Memory search
    print("\n6. Memory Search")
    print("-" * 40)
    
    # Add searchable data
    memory.store("ml_concept", "Machine learning is a subset of AI", "long_term")
    memory.store("dl_concept", "Deep learning uses neural networks", "long_term")
    memory.store("ai_concept", "Artificial intelligence mimics human intelligence", "long_term")
    
    # Search for entries
    search_term = "learning"
    results = memory.search(search_term)
    
    print(f"Search results for '{search_term}':")
    for entry in results:
        print(f"  Key: {entry.key}")
        print(f"  Value: {entry.value}")
        print(f"  Access count: {entry.access_count}")
    
    # Search in specific tier
    long_term_results = memory.search("intelligence", memory_type="long_term")
    print(f"\nLong-term search for 'intelligence': {len(long_term_results)} results")
    
    # 7. External memory
    print("\n7. External Memory (Unlimited)")
    print("-" * 40)
    
    # Store large datasets in external memory
    for i in range(20):
        memory.store_external(
            f"external_data_{i}",
            f"Large dataset {i}",
            metadata={"source": "external_db"}
        )
    
    print(f"External memory count: {len(memory.external)}")
    
    # 8. Comprehensive statistics
    print("\n8. Memory Statistics")
    print("-" * 40)
    
    stats = memory.get_stats()
    print(f"Statistics:")
    print(f"  Total stores: {stats['total_stores']}")
    print(f"  Total retrievals: {stats['total_retrievals']}")
    print(f"  Cache hits: {stats['cache_hits']}")
    print(f"  Cache misses: {stats['cache_misses']}")
    print(f"  Cache hit rate: {stats['cache_hit_rate']:.2%}")
    print(f"  Evictions: {stats['evictions']}")
    print(f"  Expirations: {stats['expirations']}")
    print(f"\nMemory Distribution:")
    print(f"  Short-term: {stats['short_term_count']} items ({stats['short_term_utilization']:.2%} full)")
    print(f"  Long-term: {stats['long_term_count']} items ({stats['long_term_utilization']:.2%} full)")
    print(f"  External: {stats['external_count']} items")
    print(f"  Total: {stats['total_count']} items")
    
    # 9. Export memory
    print("\n9. Exporting Memory")
    print("-" * 40)
    
    export_path = "/tmp/memory_export.json"
    memory.export_memory(export_path)
    print(f"Memory exported to: {export_path}")
    
    # 10. Access patterns
    print("\n10. Access Pattern Analysis")
    print("-" * 40)
    
    # Create memory entries and access them
    test_keys = ["key_a", "key_b", "key_c"]
    for key in test_keys:
        memory.store_short_term(key, f"Value for {key}", ttl=None)
    
    # Different access patterns
    for _ in range(5):
        memory.retrieve("key_a")  # Frequently accessed
    
    for _ in range(2):
        memory.retrieve("key_b")  # Occasionally accessed
    
    # No access for key_c
    
    # Check access counts
    print("Access patterns:")
    for key in test_keys:
        entry = memory.short_term.get(key)
        if entry:
            print(f"  {key}: {entry.access_count} accesses")
    
    # 11. Memory cleanup
    print("\n11. Selective Memory Cleanup")
    print("-" * 40)
    
    print(f"Before cleanup:")
    print(f"  Short-term: {len(memory.short_term)}")
    print(f"  Long-term: {len(memory.long_term)}")
    print(f"  External: {len(memory.external)}")
    
    memory.clear_short_term()
    print(f"\nAfter clearing short-term:")
    print(f"  Short-term: {len(memory.short_term)}")
    print(f"  Long-term: {len(memory.long_term)}")
    print(f"  External: {len(memory.external)}")
    
    print("\n" + "=" * 80)
    print("Enhanced Memory Management Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
