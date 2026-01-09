"""
Context Engineering Example
Demonstrates advanced agent context management, token tracking, and context compression.
"""

from agenticaiframework import Agent, AgentManager, ContextManager

def sample_task():
    """Sample task for demonstration."""
    return "Task completed successfully!"

def main():
    print("=" * 80)
    print("Context Engineering Example")
    print("=" * 80)
    
    # 1. Create agent with context management
    print("\n1. Creating Agent with Context Management")
    print("-" * 40)
    
    agent = Agent(
        name="ContextAwareAgent",
        role="Assistant",
        capabilities=["reasoning", "analysis"],
        config={"temperature": 0.7},
        max_context_tokens=1000  # Small limit for demonstration
    )
    
    print(f"Agent created: {agent.name}")
    print(f"Max context tokens: {agent.context_manager.max_tokens}")
    
    # 2. Add context with varying importance
    print("\n2. Adding Context with Importance Levels")
    print("-" * 40)
    
    # High importance context (system instructions)
    agent.add_context(
        "You are a helpful AI assistant focused on providing accurate information.",
        importance=0.9
    )
    
    # Medium importance context (recent conversation)
    agent.add_context(
        "User asked about machine learning concepts.",
        importance=0.6
    )
    
    # Low importance context (background info)
    agent.add_context(
        "The weather today is sunny with clear skies.",
        importance=0.3
    )
    
    # Multiple context additions to trigger compression
    for i in range(20):
        agent.add_context(
            f"Additional context item {i}: This is some background information.",
            importance=0.4
        )
    
    # Check context stats
    stats = agent.get_context_stats()
    print(f"\nContext Statistics:")
    print(f"  Current tokens: {stats['current_tokens']}")
    print(f"  Max tokens: {stats['max_tokens']}")
    print(f"  Utilization: {stats['utilization']:.2%}")
    print(f"  Context items: {stats['context_items']}")
    print(f"  Important items: {stats['important_items']}")
    print(f"  Compressions performed: {stats['compression_stats']['total_compressions']}")
    print(f"  Tokens saved: {stats['compression_stats']['tokens_saved']}")
    
    # 3. Execute tasks with context tracking
    print("\n3. Executing Tasks with Performance Tracking")
    print("-" * 40)
    
    agent.start()
    
    # Execute multiple tasks
    for i in range(5):
        result = agent.execute_task(sample_task)
        print(f"Task {i+1} result: {result}")
    
    # Get performance metrics
    metrics = agent.get_performance_metrics()
    print(f"\nPerformance Metrics:")
    print(f"  Total tasks: {metrics['total_tasks']}")
    print(f"  Successful: {metrics['successful_tasks']}")
    print(f"  Failed: {metrics['failed_tasks']}")
    print(f"  Success rate: {metrics['success_rate']:.2%}")
    print(f"  Average execution time: {metrics['average_execution_time']:.4f}s")
    
    # 4. Context Manager standalone usage
    print("\n4. Standalone Context Manager Usage")
    print("-" * 40)
    
    ctx_mgr = ContextManager(max_tokens=500)
    
    # Add various contexts
    ctx_mgr.add_context(
        "System: You are an AI assistant.",
        metadata={'type': 'system'},
        importance=1.0
    )
    
    ctx_mgr.add_context(
        "User: What is machine learning?",
        metadata={'type': 'user_query'},
        importance=0.8
    )
    
    ctx_mgr.add_context(
        "Assistant: Machine learning is a subset of AI...",
        metadata={'type': 'assistant_response'},
        importance=0.7
    )
    
    # Add many low-importance items to trigger compression
    for i in range(15):
        ctx_mgr.add_context(
            f"Background info {i}: Lorem ipsum dolor sit amet.",
            importance=0.3
        )
    
    print(f"Context Manager Stats:")
    ctx_stats = ctx_mgr.get_stats()
    print(f"  Current tokens: {ctx_stats['current_tokens']}")
    print(f"  Utilization: {ctx_stats['utilization']:.2%}")
    print(f"  Items: {ctx_stats['context_items']}")
    print(f"  Compressions: {ctx_stats['compression_stats']['total_compressions']}")
    
    # Get context summary
    summary = ctx_mgr.get_context_summary()
    print(f"\nContext Summary (last 5 items):")
    print(summary)
    
    # 5. Agent Manager with multiple agents
    print("\n5. Managing Multiple Context-Aware Agents")
    print("-" * 40)
    
    manager = AgentManager()
    
    # Create multiple agents
    for i in range(3):
        agent = Agent(
            name=f"Agent_{i}",
            role=f"Specialist_{i}",
            capabilities=["analysis"],
            config={},
            max_context_tokens=800
        )
        agent.start()
        
        # Execute some tasks
        for j in range(3):
            agent.execute_task(sample_task)
        
        manager.register_agent(agent)
    
    # Broadcast message to all agents
    manager.broadcast("System update: New features available", importance=0.7)
    
    # Health check
    print("\nAgent Health Check:")
    health = manager.health_check()
    for agent_id, status in health.items():
        print(f"  {status['name']}:")
        print(f"    Status: {status['status']}")
        print(f"    Success rate: {status['success_rate']:.2%}")
        print(f"    Context utilization: {status['context_utilization']:.2%}")
    
    # Aggregate metrics
    print("\nAggregate Metrics:")
    agg_metrics = manager.get_aggregate_metrics()
    print(f"  Total agents: {agg_metrics['total_agents']}")
    print(f"  Active agents: {agg_metrics['active_agents']}")
    print(f"  Total tasks: {agg_metrics['total_tasks']}")
    print(f"  Overall success rate: {agg_metrics['overall_success_rate']:.2%}")
    
    # Stop all agents
    manager.stop_all_agents()
    
    print("\n" + "=" * 80)
    print("Context Engineering Example Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
