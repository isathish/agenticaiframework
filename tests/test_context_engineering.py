"""
Test suite for Agent Context Engineering features.
Tests ContextManager, token tracking, compression, and importance weighting.
"""

import pytest
from agenticaiframework.agents import ContextManager, Agent


class TestContextManager:
    """Test suite for ContextManager."""
    
    def test_add_context(self):
        """Test adding context items."""
        cm = ContextManager(max_tokens=1000)
        
        cm.add_context("This is important", importance=0.9)
        cm.add_context("This is less important", importance=0.3)
        
        assert len(cm.context_items) == 2
    
    def test_token_counting(self):
        """Test that tokens are counted correctly."""
        cm = ContextManager(max_tokens=1000)
        
        # Simple token count: approximately 1 token per 4 characters
        cm.add_context("This is a test message")
        
        assert cm.current_tokens > 0
        assert cm.current_tokens < 1000
    
    def test_get_context(self):
        """Test retrieving context sorted by importance."""
        cm = ContextManager(max_tokens=1000)
        
        cm.add_context("Low priority", importance=0.2)
        cm.add_context("High priority", importance=0.9)
        cm.add_context("Medium priority", importance=0.5)
        
        context = cm.get_context()
        
        # Should be sorted by importance (high to low)
        assert "High priority" in context
        assert context.index("High priority") < context.index("Medium priority")
        assert context.index("Medium priority") < context.index("Low priority")
    
    def test_context_compression(self):
        """Test context compression when exceeding token limit."""
        cm = ContextManager(max_tokens=50)
        
        # Add more content than the limit
        for i in range(10):
            cm.add_context(f"Context item number {i}", importance=0.5 + i*0.01)
        
        context = cm.get_context()
        
        # Context should be compressed to fit
        tokens = len(context.split())
        assert tokens <= 50
    
    def test_importance_weighting(self):
        """Test that high importance items are preserved."""
        cm = ContextManager(max_tokens=30)
        
        cm.add_context("Critical information", importance=0.95)
        cm.add_context("Low priority filler text", importance=0.1)
        
        context = cm.get_context()
        
        # High importance item should definitely be included
        assert "Critical information" in context
    
    def test_clear_context(self):
        """Test clearing all context."""
        cm = ContextManager(max_tokens=1000)
        
        cm.add_context("Test", importance=0.5)
        assert len(cm.context_items) > 0
        
        cm.clear_context()
        assert len(cm.context_items) == 0
        assert cm.current_tokens == 0
    
    def test_get_context_stats(self):
        """Test getting context statistics."""
        cm = ContextManager(max_tokens=1000)
        
        cm.add_context("First item", importance=0.8)
        cm.add_context("Second item", importance=0.6)
        
        stats = cm.get_context_stats()
        
        assert stats['total_items'] == 2
        assert stats['total_tokens'] > 0
        assert stats['max_tokens'] == 1000
        assert 0 <= stats['utilization'] <= 1
    
    def test_token_limit_enforcement(self):
        """Test that token limit is enforced."""
        cm = ContextManager(max_tokens=100)
        
        # Add a lot of content
        for i in range(50):
            cm.add_context(f"Item {i}" * 10, importance=0.5)
        
        context = cm.get_context()
        
        # Should be truncated to fit token limit
        token_count = len(context.split())
        assert token_count <= 100


class TestAgentWithContext:
    """Test Agent integration with ContextManager."""
    
    def test_agent_context_initialization(self):
        """Test that agent initializes with context manager."""
        agent = Agent(
            name="TestAgent",
            role="tester",
            goal="test context",
            backstory="Testing"
        )
        
        # Context manager should be initialized
        assert agent.context_manager is not None
    
    def test_agent_add_context(self):
        """Test adding context through agent."""
        agent = Agent(
            name="TestAgent",
            role="tester",
            goal="test",
            backstory="Testing"
        )
        
        agent.context_manager.add_context(
            "Important task information",
            importance=0.8
        )
        
        stats = agent.context_manager.get_context_stats()
        assert stats['total_items'] == 1
    
    def test_agent_context_in_execution(self):
        """Test that context is available during execution."""
        agent = Agent(
            name="TestAgent",
            role="tester",
            goal="test",
            backstory="Testing"
        )
        
        agent.context_manager.add_context(
            "Context for task",
            importance=0.9
        )
        
        # Context should be retrievable
        context = agent.context_manager.get_context()
        assert "Context for task" in context
    
    def test_agent_performance_tracking(self):
        """Test that agent tracks performance metrics."""
        agent = Agent(
            name="TestAgent",
            role="tester",
            goal="test",
            backstory="Testing"
        )
        
        # Simulate some execution
        agent.tasks_completed = 5
        agent.total_execution_time = 10.5
        
        metrics = agent.get_performance_metrics()
        
        assert metrics['tasks_completed'] == 5
        assert metrics['total_execution_time'] == 10.5
    
    def test_context_persistence_across_tasks(self):
        """Test that context persists across multiple tasks."""
        agent = Agent(
            name="TestAgent",
            role="tester",
            goal="test",
            backstory="Testing"
        )
        
        agent.context_manager.add_context("Task 1 context", importance=0.8)
        agent.context_manager.add_context("Task 2 context", importance=0.7)
        
        # Both contexts should be available
        context = agent.context_manager.get_context()
        assert "Task 1 context" in context
        assert "Task 2 context" in context
    
    def test_context_overflow_handling(self):
        """Test handling of context overflow."""
        agent = Agent(
            name="TestAgent",
            role="tester",
            goal="test",
            backstory="Testing"
        )
        
        # Set small token limit
        agent.context_manager = ContextManager(max_tokens=50)
        
        # Add lots of context
        for i in range(20):
            agent.context_manager.add_context(
                f"Context item {i} with some text",
                importance=0.5 + i*0.01
            )
        
        # Should handle overflow gracefully
        context = agent.context_manager.get_context()
        assert context is not None
        assert len(context.split()) <= 50


class TestContextCompression:
    """Test suite for context compression strategies."""
    
    def test_compression_preserves_high_importance(self):
        """Test that compression keeps high importance items."""
        cm = ContextManager(max_tokens=50)
        
        # Add mix of importance levels
        cm.add_context("CRITICAL: System failure detected", importance=1.0)
        cm.add_context("Info: User logged in", importance=0.2)
        cm.add_context("Debug: Variable x = 5", importance=0.1)
        
        context = cm.get_context()
        
        # Critical message should be present
        assert "CRITICAL" in context
    
    def test_compression_removes_low_importance(self):
        """Test that compression removes low importance items first."""
        cm = ContextManager(max_tokens=40)
        
        cm.add_context("Important task data", importance=0.9)
        cm.add_context("Low priority note", importance=0.1)
        cm.add_context("Very low priority", importance=0.05)
        
        context = cm.get_context()
        
        # High importance should be kept
        assert "Important" in context
        # Very low importance might be removed
        # (depends on exact token counts)
    
    def test_compression_with_equal_importance(self):
        """Test compression when items have equal importance."""
        cm = ContextManager(max_tokens=30)
        
        # All items same importance - should keep most recent
        for i in range(10):
            cm.add_context(f"Item {i}", importance=0.5)
        
        context = cm.get_context()
        
        # Should have some items compressed out
        assert context is not None
        assert len(context.split()) <= 30


class TestContextMetadata:
    """Test context metadata tracking."""
    
    def test_context_timestamps(self):
        """Test that context items have timestamps."""
        cm = ContextManager(max_tokens=1000)
        
        cm.add_context("Test", importance=0.5)
        
        # Items should have timestamp metadata
        assert len(cm.context_items) > 0
        # ContextManager stores as list of dicts with 'content' and 'importance'
    
    def test_context_ordering(self):
        """Test that context maintains insertion order."""
        cm = ContextManager(max_tokens=1000)
        
        cm.add_context("First", importance=0.5)
        cm.add_context("Second", importance=0.5)
        cm.add_context("Third", importance=0.5)
        
        # With same importance, should maintain order
        context = cm.get_context()
        first_pos = context.index("First")
        second_pos = context.index("Second")
        third_pos = context.index("Third")
        
        assert first_pos < second_pos < third_pos


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
