"""
Comprehensive tests for context module.

Tests for:
- ContextItem
- ContextWindow
- ContextCompressionStrategy
- SemanticContextIndex
"""

import pytest
from datetime import datetime, timedelta


class TestContextItem:
    """Tests for ContextItem."""
    
    def test_create_basic_item(self):
        """Test creating basic context item."""
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        item = ContextItem(
            id="item1",
            content="Test content",
            context_type=ContextType.USER,
            priority=ContextPriority.MEDIUM,
            tokens=50,
            importance=0.5,
            timestamp=datetime.now()
        )
        
        assert item.id == "item1"
        assert item.content == "Test content"
        assert item.tokens == 50
    
    def test_create_item_with_metadata(self):
        """Test creating item with metadata."""
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        item = ContextItem(
            id="item1",
            content="Test",
            context_type=ContextType.PLAN,
            priority=ContextPriority.HIGH,
            tokens=10,
            importance=0.8,
            timestamp=datetime.now(),
            metadata={"source": "test", "version": 1},
            tags=["important", "test"]
        )
        
        assert item.metadata["source"] == "test"
        assert "important" in item.tags
    
    def test_item_expiration(self):
        """Test item expiration check."""
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        # Item with short TTL (already expired)
        item = ContextItem(
            id="item1",
            content="Test",
            context_type=ContextType.USER,
            priority=ContextPriority.MEDIUM,
            tokens=10,
            importance=0.5,
            timestamp=datetime.now() - timedelta(seconds=10),
            ttl=1  # 1 second TTL, created 10 seconds ago
        )
        
        assert item.is_expired() is True
        
        # Item with long TTL
        item2 = ContextItem(
            id="item2",
            content="Test",
            context_type=ContextType.USER,
            priority=ContextPriority.MEDIUM,
            tokens=10,
            importance=0.5,
            timestamp=datetime.now(),
            ttl=3600
        )
        
        assert item2.is_expired() is False
    
    def test_item_no_ttl(self):
        """Test item without TTL never expires."""
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        item = ContextItem(
            id="item1",
            content="Test",
            context_type=ContextType.USER,
            priority=ContextPriority.MEDIUM,
            tokens=10,
            importance=0.5,
            timestamp=datetime.now() - timedelta(days=365)  # 1 year ago
        )
        
        assert item.is_expired() is False
    
    def test_compute_relevance_score(self):
        """Test relevance score computation."""
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        item = ContextItem(
            id="item1",
            content="Python programming language tutorial",
            context_type=ContextType.KNOWLEDGE,
            priority=ContextPriority.MEDIUM,
            tokens=10,
            importance=0.7,
            timestamp=datetime.now()
        )
        
        # High relevance query
        score = item.compute_relevance_score("python tutorial")
        assert score > 0
        
        # Low relevance query
        score = item.compute_relevance_score("javascript framework")
        assert score < 0.5
    
    def test_compute_relevance_empty_query(self):
        """Test relevance score with empty query."""
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        item = ContextItem(
            id="item1",
            content="Some content",
            context_type=ContextType.USER,
            priority=ContextPriority.MEDIUM,
            tokens=10,
            importance=0.5,
            timestamp=datetime.now()
        )
        
        score = item.compute_relevance_score("")
        assert score == 0.0
    
    def test_mark_accessed(self):
        """Test marking item as accessed."""
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        item = ContextItem(
            id="item1",
            content="Test",
            context_type=ContextType.USER,
            priority=ContextPriority.MEDIUM,
            tokens=10,
            importance=0.5,
            timestamp=datetime.now()
        )
        
        assert item.access_count == 0
        item.mark_accessed()
        assert item.access_count == 1
        assert item.last_accessed is not None
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        item = ContextItem(
            id="item1",
            content="Test",
            context_type=ContextType.USER,
            priority=ContextPriority.MEDIUM,
            tokens=10,
            importance=0.5,
            timestamp=datetime.now()
        )
        
        d = item.to_dict()
        assert d['id'] == "item1"
        assert d['content'] == "Test"


def create_test_item(id: str, tokens: int = 100, priority=None, context_type=None):
    """Helper to create test context items."""
    from agenticaiframework.context.items import ContextItem
    from agenticaiframework.context.types import ContextType, ContextPriority
    
    return ContextItem(
        id=id,
        content=f"Test content {id}",
        context_type=context_type or ContextType.USER,
        priority=priority or ContextPriority.MEDIUM,
        tokens=tokens,
        importance=0.5,
        timestamp=datetime.now()
    )


class TestContextWindow:
    """Tests for ContextWindow."""
    
    def test_init(self):
        """Test window initialization."""
        from agenticaiframework.context.window import ContextWindow
        
        window = ContextWindow(max_tokens=4000, reserve_tokens=500)
        assert window.max_tokens == 4000
        assert window.reserve_tokens == 500
        assert len(window) == 0
    
    def test_add_item(self):
        """Test adding item to window."""
        from agenticaiframework.context.window import ContextWindow
        
        window = ContextWindow(max_tokens=1000)
        item = create_test_item("item1", tokens=100)
        
        result = window.add(item)
        assert result is True
        assert len(window) == 1
    
    def test_add_item_exceeds_capacity(self):
        """Test adding item that exceeds capacity."""
        from agenticaiframework.context.window import ContextWindow
        
        window = ContextWindow(max_tokens=100, reserve_tokens=50)
        item = create_test_item("item1", tokens=100)  # Exceeds available (100 - 50 = 50)
        
        result = window.add(item)
        assert result is False
        assert len(window) == 0
    
    def test_total_tokens(self):
        """Test total tokens calculation."""
        from agenticaiframework.context.window import ContextWindow
        
        window = ContextWindow(max_tokens=1000)
        
        for i in range(5):
            item = create_test_item(f"item{i}", tokens=50)
            window.add(item)
        
        assert window.total_tokens == 250
    
    def test_available_tokens(self):
        """Test available tokens calculation."""
        from agenticaiframework.context.window import ContextWindow
        
        window = ContextWindow(max_tokens=1000, reserve_tokens=100)
        item = create_test_item("item1", tokens=200)
        window.add(item)
        
        # 1000 - 100 (reserve) - 200 (used) = 700
        assert window.available_tokens == 700
    
    def test_utilization(self):
        """Test utilization calculation."""
        from agenticaiframework.context.window import ContextWindow
        
        window = ContextWindow(max_tokens=1000)
        item = create_test_item("item1", tokens=500)
        window.add(item)
        
        assert window.utilization == 0.5
    
    def test_utilization_zero_max(self):
        """Test utilization with zero max tokens."""
        from agenticaiframework.context.window import ContextWindow
        
        window = ContextWindow(max_tokens=0)
        assert window.utilization == 0.0
    
    def test_remove_item(self):
        """Test removing item from window."""
        from agenticaiframework.context.window import ContextWindow
        
        window = ContextWindow(max_tokens=1000)
        item = create_test_item("item1", tokens=100)
        window.add(item)
        
        removed = window.remove("item1")
        assert removed is not None
        assert removed.id == "item1"
        assert len(window) == 0
    
    def test_remove_nonexistent_item(self):
        """Test removing nonexistent item."""
        from agenticaiframework.context.window import ContextWindow
        
        window = ContextWindow(max_tokens=1000)
        removed = window.remove("nonexistent")
        assert removed is None
    
    def test_evict_lowest_priority(self):
        """Test evicting lowest priority item."""
        from agenticaiframework.context.window import ContextWindow
        from agenticaiframework.context.types import ContextPriority
        
        window = ContextWindow(max_tokens=1000)
        
        # Add items with different priorities
        low = create_test_item("low", tokens=100, priority=ContextPriority.LOW)
        high = create_test_item("high", tokens=100, priority=ContextPriority.HIGH)
        
        window.add(low)
        window.add(high)
        
        evicted = window.evict_lowest_priority()
        assert evicted.id == "low"
        assert len(window) == 1
    
    def test_evict_critical_protected(self):
        """Test that critical items are not evicted."""
        from agenticaiframework.context.window import ContextWindow
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        window = ContextWindow(max_tokens=1000)
        
        critical = create_test_item("critical", tokens=100, priority=ContextPriority.CRITICAL)
        window.add(critical)
        
        evicted = window.evict_lowest_priority()
        assert evicted is None
        assert len(window) == 1
    
    def test_evict_until_available(self):
        """Test evicting until required tokens available."""
        from agenticaiframework.context.window import ContextWindow
        from agenticaiframework.context.types import ContextPriority
        
        window = ContextWindow(max_tokens=500, reserve_tokens=100)
        
        # Fill window
        for i in range(4):
            item = create_test_item(f"item{i}", tokens=100, priority=ContextPriority.LOW)
            window.add(item)
        
        # Need 200 tokens, currently have 0 available
        evicted = window.evict_until_available(200)
        assert len(evicted) >= 2
        assert window.available_tokens >= 200
    
    def test_get_by_type(self):
        """Test getting items by type."""
        from agenticaiframework.context.window import ContextWindow
        from agenticaiframework.context.types import ContextType
        
        window = ContextWindow(max_tokens=1000)
        
        user = create_test_item("user", tokens=50, context_type=ContextType.USER)
        plan = create_test_item("plan", tokens=50, context_type=ContextType.PLAN)
        
        window.add(user)
        window.add(plan)
        
        user_items = window.get_by_type(ContextType.USER)
        assert len(user_items) == 1
        assert user_items[0].id == "user"
    
    def test_get_by_priority(self):
        """Test getting items by minimum priority."""
        from agenticaiframework.context.window import ContextWindow
        from agenticaiframework.context.types import ContextPriority
        
        window = ContextWindow(max_tokens=1000)
        
        for priority in [ContextPriority.LOW, ContextPriority.MEDIUM, ContextPriority.HIGH]:
            item = create_test_item(priority.name, tokens=50, priority=priority)
            window.add(item)
        
        high_priority = window.get_by_priority(ContextPriority.HIGH)
        assert len(high_priority) == 1
        
        medium_and_above = window.get_by_priority(ContextPriority.MEDIUM)
        assert len(medium_and_above) == 2
    
    def test_clear(self):
        """Test clearing window."""
        from agenticaiframework.context.window import ContextWindow
        
        window = ContextWindow(max_tokens=1000)
        item = create_test_item("item", tokens=50)
        window.add(item)
        
        window.clear()
        assert len(window) == 0
    
    def test_clear_expired(self):
        """Test clearing expired items."""
        from agenticaiframework.context.window import ContextWindow
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        window = ContextWindow(max_tokens=1000)
        
        # Add expired item (force add to bypass checks)
        expired = ContextItem(
            id="expired",
            content="Expired",
            context_type=ContextType.USER,
            priority=ContextPriority.MEDIUM,
            tokens=50,
            importance=0.5,
            timestamp=datetime.now() - timedelta(hours=1),
            ttl=60  # 60 second TTL but created 1 hour ago
        )
        window.items.append(expired)
        
        # Add non-expired item
        valid = create_test_item("valid", tokens=50)
        window.add(valid)
        
        count = window.clear_expired()
        assert count == 1
        assert len(window) == 1


class TestContextCompressionStrategy:
    """Tests for ContextCompressionStrategy."""
    
    def test_summarize_short_content(self):
        """Test summarize with short content."""
        from agenticaiframework.context.compression import ContextCompressionStrategy
        
        content = "Short content."
        result = ContextCompressionStrategy.summarize(content, max_length=500)
        assert result == content
    
    def test_summarize_long_content(self):
        """Test summarize with long content."""
        from agenticaiframework.context.compression import ContextCompressionStrategy
        
        content = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
        result = ContextCompressionStrategy.summarize(content, max_length=50)
        assert len(result) <= 50
    
    def test_summarize_preserves_sentences(self):
        """Test that summarize preserves complete sentences."""
        from agenticaiframework.context.compression import ContextCompressionStrategy
        
        content = "First sentence. Second sentence. Third sentence."
        result = ContextCompressionStrategy.summarize(content, max_length=40)
        # Should include complete sentences
        assert result.endswith('.')
    
    def test_extract_key_points_bullets(self):
        """Test extracting key points from bullets."""
        from agenticaiframework.context.compression import ContextCompressionStrategy
        
        content = """
        - First important point
        - Second important point
        Some regular text
        - Third important point
        """
        
        result = ContextCompressionStrategy.extract_key_points(content, num_points=5)
        assert "First important" in result
        assert "Second important" in result
    
    def test_extract_key_points_numbered(self):
        """Test extracting key points from numbered list."""
        from agenticaiframework.context.compression import ContextCompressionStrategy
        
        content = """
        1. First step
        2. Second step
        Some text
        3. Third step
        """
        
        result = ContextCompressionStrategy.extract_key_points(content)
        assert "First step" in result
    
    def test_extract_key_points_keywords(self):
        """Test extracting key points with keywords."""
        from agenticaiframework.context.compression import ContextCompressionStrategy
        
        content = """
        Regular line
        Important: This is critical information
        Another line
        Note: Remember this point
        """
        
        result = ContextCompressionStrategy.extract_key_points(content)
        assert "Important" in result or "Note" in result
    
    def test_extract_key_points_limit(self):
        """Test key points extraction respects limit."""
        from agenticaiframework.context.compression import ContextCompressionStrategy
        
        content = "\n".join([f"- Point {i}" for i in range(10)])
        result = ContextCompressionStrategy.extract_key_points(content, num_points=3)
        
        lines = [l for l in result.split('\n') if l.strip()]
        assert len(lines) <= 3
    
    def test_merge_similar_single_item(self):
        """Test merge with single item."""
        from agenticaiframework.context.compression import ContextCompressionStrategy
        
        item = create_test_item("item1", tokens=50)
        
        result = ContextCompressionStrategy.merge_similar([item])
        assert len(result) == 1
        assert result[0].id == "item1"
    
    def test_merge_similar_empty_list(self):
        """Test merge with empty list."""
        from agenticaiframework.context.compression import ContextCompressionStrategy
        
        result = ContextCompressionStrategy.merge_similar([])
        assert result == []
    
    def test_merge_similar_different_items(self):
        """Test merge with different items."""
        from agenticaiframework.context.compression import ContextCompressionStrategy
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        items = [
            ContextItem(
                id="item1",
                content="Python programming tutorial",
                context_type=ContextType.KNOWLEDGE,
                priority=ContextPriority.MEDIUM,
                tokens=50,
                importance=0.5,
                timestamp=datetime.now()
            ),
            ContextItem(
                id="item2",
                content="JavaScript web development",
                context_type=ContextType.KNOWLEDGE,
                priority=ContextPriority.MEDIUM,
                tokens=50,
                importance=0.5,
                timestamp=datetime.now()
            )
        ]
        
        result = ContextCompressionStrategy.merge_similar(items, similarity_threshold=0.9)
        # Different content should not merge
        assert len(result) == 2


class TestSemanticContextIndex:
    """Tests for SemanticContextIndex."""
    
    def test_init(self):
        """Test index initialization."""
        from agenticaiframework.context.index import SemanticContextIndex
        
        index = SemanticContextIndex()
        assert len(index) == 0
    
    def test_add_item(self):
        """Test adding item to index."""
        from agenticaiframework.context.index import SemanticContextIndex
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        index = SemanticContextIndex()
        item = ContextItem(
            id="item1",
            content="Test",
            context_type=ContextType.KNOWLEDGE,
            priority=ContextPriority.MEDIUM,
            tokens=50,
            importance=0.5,
            timestamp=datetime.now(),
            embedding=[0.1, 0.2, 0.3]
        )
        
        index.add(item)
        assert len(index) == 1
        assert "item1" in index.items
    
    def test_add_item_without_embedding(self):
        """Test adding item without embedding."""
        from agenticaiframework.context.index import SemanticContextIndex
        
        index = SemanticContextIndex()
        item = create_test_item("item1", tokens=50)
        
        index.add(item)
        assert len(index) == 1
        assert "item1" not in index._embedding_cache
    
    def test_remove_item(self):
        """Test removing item from index."""
        from agenticaiframework.context.index import SemanticContextIndex
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        index = SemanticContextIndex()
        item = ContextItem(
            id="item1",
            content="Test",
            context_type=ContextType.KNOWLEDGE,
            priority=ContextPriority.MEDIUM,
            tokens=50,
            importance=0.5,
            timestamp=datetime.now(),
            embedding=[0.1, 0.2, 0.3]
        )
        
        index.add(item)
        index.remove("item1")
        
        assert len(index) == 0
        assert "item1" not in index._embedding_cache
    
    def test_clear(self):
        """Test clearing index."""
        from agenticaiframework.context.index import SemanticContextIndex
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        index = SemanticContextIndex()
        
        for i in range(5):
            item = ContextItem(
                id=f"item{i}",
                content="Test",
                context_type=ContextType.KNOWLEDGE,
                priority=ContextPriority.MEDIUM,
                tokens=50,
                importance=0.5,
                timestamp=datetime.now(),
                embedding=[0.1 * i, 0.2, 0.3]
            )
            index.add(item)
        
        index.clear()
        assert len(index) == 0
        assert len(index._embedding_cache) == 0
    
    def test_search_empty_index(self):
        """Test search on empty index."""
        from agenticaiframework.context.index import SemanticContextIndex
        
        index = SemanticContextIndex()
        results = index.search([0.1, 0.2, 0.3])
        assert results == []
    
    def test_search_empty_query(self):
        """Test search with empty query."""
        from agenticaiframework.context.index import SemanticContextIndex
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        index = SemanticContextIndex()
        item = ContextItem(
            id="item1",
            content="Test",
            context_type=ContextType.KNOWLEDGE,
            priority=ContextPriority.MEDIUM,
            tokens=50,
            importance=0.5,
            timestamp=datetime.now(),
            embedding=[0.1, 0.2, 0.3]
        )
        index.add(item)
        
        results = index.search([])
        assert results == []
    
    def test_search_returns_similar(self):
        """Test search returns similar items."""
        from agenticaiframework.context.index import SemanticContextIndex
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        index = SemanticContextIndex()
        
        # Add items with different embeddings
        item1 = ContextItem(
            id="item1",
            content="Python",
            context_type=ContextType.KNOWLEDGE,
            priority=ContextPriority.MEDIUM,
            tokens=50,
            importance=0.5,
            timestamp=datetime.now(),
            embedding=[1.0, 0.0, 0.0]
        )
        item2 = ContextItem(
            id="item2",
            content="JavaScript",
            context_type=ContextType.KNOWLEDGE,
            priority=ContextPriority.MEDIUM,
            tokens=50,
            importance=0.5,
            timestamp=datetime.now(),
            embedding=[0.0, 1.0, 0.0]
        )
        
        index.add(item1)
        index.add(item2)
        
        # Search for vector similar to item1
        results = index.search([0.9, 0.1, 0.0], top_k=2)
        
        assert len(results) == 2
        assert results[0][0].id == "item1"  # Most similar first
    
    def test_search_top_k(self):
        """Test search respects top_k limit."""
        from agenticaiframework.context.index import SemanticContextIndex
        from agenticaiframework.context.items import ContextItem
        from agenticaiframework.context.types import ContextType, ContextPriority
        
        index = SemanticContextIndex()
        
        for i in range(10):
            item = ContextItem(
                id=f"item{i}",
                content="Test",
                context_type=ContextType.KNOWLEDGE,
                priority=ContextPriority.MEDIUM,
                tokens=50,
                importance=0.5,
                timestamp=datetime.now(),
                embedding=[0.1 * i, 0.2, 0.3]
            )
            index.add(item)
        
        results = index.search([0.5, 0.2, 0.3], top_k=3)
        assert len(results) == 3
    
    def test_cosine_similarity_identical(self):
        """Test cosine similarity of identical vectors."""
        from agenticaiframework.context.index import SemanticContextIndex
        
        index = SemanticContextIndex()
        vec = [1.0, 2.0, 3.0]
        
        similarity = index._cosine_similarity(vec, vec)
        assert abs(similarity - 1.0) < 0.0001
    
    def test_cosine_similarity_orthogonal(self):
        """Test cosine similarity of orthogonal vectors."""
        from agenticaiframework.context.index import SemanticContextIndex
        
        index = SemanticContextIndex()
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        
        similarity = index._cosine_similarity(vec1, vec2)
        assert abs(similarity) < 0.0001
    
    def test_cosine_similarity_different_lengths(self):
        """Test cosine similarity with different vector lengths."""
        from agenticaiframework.context.index import SemanticContextIndex
        
        index = SemanticContextIndex()
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        
        similarity = index._cosine_similarity(vec1, vec2)
        assert similarity == 0.0
    
    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector."""
        from agenticaiframework.context.index import SemanticContextIndex
        
        index = SemanticContextIndex()
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        
        similarity = index._cosine_similarity(vec1, vec2)
        assert similarity == 0.0
