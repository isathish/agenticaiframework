"""
Complete Agent Class Guide with Examples
=========================================

This guide demonstrates all the key features of the Agent class
with practical, runnable examples.
"""

from agenticaiframework.core import Agent
from agenticaiframework.llms import LLMManager
from typing import Dict, Any


# ============================================================================
# EXAMPLE 1: Basic Agent Creation
# ============================================================================

def example_1_basic_agent():
    """Most basic agent creation."""
    print("\n" + "="*70)
    print("EXAMPLE 1: Basic Agent Creation")
    print("="*70)
    
    # Create a simple agent
    agent = Agent(
        name="BasicBot",
        role="A helpful assistant",
        capabilities=["conversation", "task_execution"],
        config={}
    )
    
    # Check agent properties
    print(f"\nAgent ID: {agent.id}")
    print(f"Name: {agent.name}")
    print(f"Role: {agent.role}")
    print(f"Status: {agent.status}")
    print(f"Capabilities: {agent.capabilities}")
    
    # Lifecycle management
    agent.start()
    print(f"Status after start: {agent.status}")
    
    agent.pause()
    print(f"Status after pause: {agent.status}")
    
    agent.resume()
    print(f"Status after resume: {agent.status}")
    
    agent.stop()
    print(f"Status after stop: {agent.status}")


# ============================================================================
# EXAMPLE 2: Quick Agent Factory (Zero Config)
# ============================================================================

def example_2_quick_agent():
    """
    The easiest way to create an agent - uses environment variables
    for LLM configuration automatically.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Quick Agent (Auto-configured)")
    print("="*70)
    
    # One-liner agent creation with auto-configuration
    # Automatically finds LLM credentials from environment variables
    try:
        agent = Agent.quick(
            "Assistant",
            role="assistant",  # Pre-defined role template
            guardrails=True,   # Enable default guardrails
            tracing=True,      # Enable execution tracing
        )
        
        print(f"\n✓ Created agent: {agent.name}")
        print(f"  Role: {agent.role}")
        print(f"  Capabilities: {agent.capabilities}")
        print(f"  Status: {agent.status}")
        
    except Exception as e:
        print(f"\n⚠️  Note: Quick agent needs environment variables set")
        print(f"   (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)")
        print(f"   Error: {e}")


# ============================================================================
# EXAMPLE 3: Agent with LLM Integration
# ============================================================================

def example_3_agent_with_llm():
    """Agent that can call an LLM to generate responses."""
    print("\n" + "="*70)
    print("EXAMPLE 3: Agent with LLM")
    print("="*70)
    
    # Setup LLM Manager
    llm_manager = LLMManager()
    
    # Register a mock LLM (in production, use real API)
    def mock_llm(prompt: str, kwargs: dict) -> str:
        return f"AI Response: I processed your request about '{prompt[:50]}...'"
    
    llm_manager.register_model("mock-gpt", mock_llm)
    llm_manager.set_active_model("mock-gpt")
    
    # Create agent with LLM
    agent = Agent(
        name="SmartAgent",
        role="AI Assistant with LLM capabilities",
        capabilities=["conversation", "reasoning"],
        config={"llm_manager": llm_manager},
        max_context_tokens=4096
    )
    
    agent.start()
    
    # Use the agent's run() method
    result = agent.run(
        "What is machine learning?",
        return_full=True  # Get detailed response
    )
    
    print("\n📤 Prompt: 'What is machine learning?'")
    print(f"📥 Response: {result.get('response')}")
    print(f"⏱️  Latency: {result.get('latency_seconds', 0):.3f}s")
    print(f"✓ Status: {result.get('status')}")
    
    agent.stop()


# ============================================================================
# EXAMPLE 4: Agent with Context Management
# ============================================================================

def example_4_context_management():
    """Demonstrate how agents maintain context across interactions."""
    print("\n" + "="*70)
    print("EXAMPLE 4: Context Management")
    print("="*70)
    
    agent = Agent(
        name="ContextBot",
        role="Agent with memory",
        capabilities=["memory", "context_tracking"],
        config={},
        max_context_tokens=8192  # Larger context window
    )
    
    agent.start()
    
    # Add various context items
    agent.add_context("User is a Python developer", importance=0.9)
    agent.add_context("User prefers concise explanations", importance=0.8)
    agent.add_context("Current project: AI chatbot", importance=0.7)
    agent.add_context("Last topic discussed: async programming", importance=0.6)
    
    # Get context statistics
    stats = agent.get_context_stats()
    
    print("\n📊 Context Statistics:")
    print(f"  Total items: {stats.get('context_items', 0)}")
    print(f"  Important items: {stats.get('important_items', 0)}")
    print(f"  Token usage: {stats.get('current_tokens', 0)}/{stats.get('max_tokens', 0)}")
    print(f"  Utilization: {stats.get('utilization', 0):.1%}")
    
    # Get context summary
    summary = agent.context_manager.get_context_summary()
    print(f"\n📝 Context Summary:")
    print(summary)
    
    agent.stop()


# ============================================================================
# EXAMPLE 5: Agent Executing Tasks
# ============================================================================

def example_5_task_execution():
    """How agents execute different types of tasks."""
    print("\n" + "="*70)
    print("EXAMPLE 5: Task Execution")
    print("="*70)
    
    agent = Agent(
        name="WorkerAgent",
        role="Task executor",
        capabilities=["task_execution", "computation"],
        config={}
    )
    
    agent.start()
    
    # Define various task functions
    def calculate_fibonacci(n: int) -> list:
        """Calculate Fibonacci sequence."""
        if n <= 0:
            return []
        fib = [0, 1]
        for i in range(2, n):
            fib.append(fib[i-1] + fib[i-2])
        return fib[:n]
    
    def process_data(data: dict) -> dict:
        """Process data with transformations."""
        return {
            "input": data,
            "processed": True,
            "timestamp": "2026-01-23"
        }
    
    # Execute tasks
    print("\n📋 Executing Task 1: Fibonacci")
    result1 = agent.execute_task(calculate_fibonacci, 10)
    print(f"   Result: {result1}")
    
    print("\n📋 Executing Task 2: Data Processing")
    result2 = agent.execute_task(process_data, {"value": 42})
    print(f"   Result: {result2}")
    
    # Get performance metrics
    metrics = agent.get_performance_metrics()
    print("\n📈 Performance Metrics:")
    print(f"   Total tasks: {metrics['total_tasks']}")
    print(f"   Successful: {metrics['successful_tasks']}")
    print(f"   Failed: {metrics['failed_tasks']}")
    print(f"   Success rate: {metrics['success_rate']:.1%}")
    print(f"   Avg execution time: {metrics['average_execution_time']:.4f}s")
    
    agent.stop()


# ============================================================================
# EXAMPLE 6: Agent with Role Templates
# ============================================================================

def example_6_role_templates():
    """Using pre-defined role templates."""
    print("\n" + "="*70)
    print("EXAMPLE 6: Role Templates")
    print("="*70)
    
    # Available role templates:
    # - assistant: General helpful assistant
    # - analyst: Data analysis and insights
    # - coder: Programming and code review
    # - writer: Content creation
    # - researcher: Information gathering
    
    roles_to_test = ["assistant", "analyst", "coder", "writer", "researcher"]
    
    for role_name in roles_to_test:
        agent = Agent(
            name=f"{role_name.capitalize()}Bot",
            role=Agent.ROLE_TEMPLATES[role_name],
            capabilities=Agent.ROLE_CAPABILITIES[role_name],
            config={}
        )
        
        print(f"\n🤖 {agent.name}")
        print(f"   Role: {agent.role[:60]}...")
        print(f"   Capabilities: {', '.join(agent.capabilities)}")


# ============================================================================
# EXAMPLE 7: Agent Configuration from Dict
# ============================================================================

def example_7_from_config():
    """Create agent from configuration dictionary."""
    print("\n" + "="*70)
    print("EXAMPLE 7: Agent from Config")
    print("="*70)
    
    # Configuration can come from YAML, JSON, or dict
    config = {
        "name": "ConfiguredAgent",
        "role": "analyst",  # Use role template
        "max_context_tokens": 8192,
        "auto_start": False,  # Don't auto-start
    }
    
    try:
        agent = Agent.from_config(config)
        
        print(f"\n✓ Created agent from config")
        print(f"  Name: {agent.name}")
        print(f"  Role: {agent.role[:60]}...")
        print(f"  Capabilities: {agent.capabilities}")
        print(f"  Status: {agent.status}")
        
        agent.start()
        print(f"  Status after manual start: {agent.status}")
        agent.stop()
        
    except Exception as e:
        print(f"\n⚠️  Note: from_config needs LLM configuration")
        print(f"   Error: {e}")


# ============================================================================
# EXAMPLE 8: Agent Error Handling
# ============================================================================

def example_8_error_handling():
    """How agents handle errors during task execution."""
    print("\n" + "="*70)
    print("EXAMPLE 8: Error Handling")
    print("="*70)
    
    agent = Agent(
        name="RobustAgent",
        role="Error-resilient agent",
        capabilities=["error_handling"],
        config={}
    )
    
    agent.start()
    
    # Task that will fail
    def failing_task(value: int) -> int:
        if value < 0:
            raise ValueError("Value must be positive!")
        return value * 2
    
    # Task that will succeed
    def safe_task(value: int) -> int:
        return abs(value) * 2
    
    print("\n🧪 Test 1: Task with valid input")
    result1 = agent.execute_task(failing_task, 5)
    print(f"   Result: {result1}")
    
    print("\n🧪 Test 2: Task with invalid input (will fail)")
    result2 = agent.execute_task(failing_task, -5)
    print(f"   Result: {result2}")  # Returns None on error
    
    print("\n🧪 Test 3: Safe task")
    result3 = agent.execute_task(safe_task, -5)
    print(f"   Result: {result3}")
    
    # Check error log
    errors = agent.get_error_log()
    print(f"\n📋 Error Log ({len(errors)} errors):")
    for error in errors:
        print(f"   [{error['timestamp']}] {error['message']}")
    
    # Final metrics
    metrics = agent.get_performance_metrics()
    print(f"\n📊 Final Metrics:")
    print(f"   Total tasks: {metrics['total_tasks']}")
    print(f"   Successful: {metrics['successful_tasks']}")
    print(f"   Failed: {metrics['failed_tasks']}")
    print(f"   Error count: {metrics['error_count']}")
    
    agent.stop()


# ============================================================================
# EXAMPLE 9: Agent to Dictionary (Serialization)
# ============================================================================

def example_9_serialization():
    """Convert agent to dictionary for storage/transmission."""
    print("\n" + "="*70)
    print("EXAMPLE 9: Agent Serialization")
    print("="*70)
    
    agent = Agent(
        name="SerializableAgent",
        role="Data serialization example",
        capabilities=["api_integration"],
        config={"api_key": "secret123"}
    )
    
    agent.start()
    
    # Execute some tasks to generate metrics
    agent.execute_task(lambda x: x * 2, 5)
    agent.execute_task(lambda x: x + 10, 3)
    
    # Add context
    agent.add_context("Important information", importance=0.9)
    
    # Convert to dictionary
    agent_dict = agent.to_dict()
    
    print("\n📦 Agent as Dictionary:")
    import json
    print(json.dumps(agent_dict, indent=2))
    
    # This can be:
    # - Saved to file
    # - Sent over network
    # - Stored in database
    # - Used for monitoring dashboards
    
    agent.stop()


# ============================================================================
# EXAMPLE 10: Multi-Agent Pattern
# ============================================================================

def example_10_multi_agent():
    """Multiple agents working together."""
    print("\n" + "="*70)
    print("EXAMPLE 10: Multi-Agent System")
    print("="*70)
    
    # Create specialized agents
    research_agent = Agent(
        name="Researcher",
        role="Gathers and analyzes information",
        capabilities=["research", "analysis"],
        config={}
    )
    
    writer_agent = Agent(
        name="Writer",
        role="Creates content from research",
        capabilities=["writing", "summarization"],
        config={}
    )
    
    reviewer_agent = Agent(
        name="Reviewer",
        role="Reviews and improves content",
        capabilities=["review", "editing"],
        config={}
    )
    
    # Start all agents
    for agent in [research_agent, writer_agent, reviewer_agent]:
        agent.start()
    
    print("\n🤖 Agent Team Created:")
    for agent in [research_agent, writer_agent, reviewer_agent]:
        print(f"   • {agent.name}: {agent.role}")
    
    # Simulate workflow
    print("\n📋 Workflow Simulation:")
    
    # Step 1: Research
    research_data = research_agent.execute_task(
        lambda topic: f"Research findings on {topic}: [data...]",
        "AI trends"
    )
    print(f"   1. {research_agent.name}: {research_data}")
    
    # Step 2: Writing
    draft = writer_agent.execute_task(
        lambda data: f"Article draft based on: {data[:30]}...",
        research_data
    )
    print(f"   2. {writer_agent.name}: {draft}")
    
    # Step 3: Review
    final = reviewer_agent.execute_task(
        lambda draft: f"Reviewed and improved: {draft[:30]}...",
        draft
    )
    print(f"   3. {reviewer_agent.name}: {final}")
    
    # Combined metrics
    print("\n📊 Team Performance:")
    for agent in [research_agent, writer_agent, reviewer_agent]:
        metrics = agent.get_performance_metrics()
        print(f"   {agent.name}: {metrics['total_tasks']} tasks, "
              f"{metrics['success_rate']:.0%} success rate")
    
    # Stop all agents
    for agent in [research_agent, writer_agent, reviewer_agent]:
        agent.stop()


# ============================================================================
# EXAMPLE 11: Agent with Custom Config
# ============================================================================

def example_11_custom_config():
    """Agent with custom configuration options."""
    print("\n" + "="*70)
    print("EXAMPLE 11: Custom Configuration")
    print("="*70)
    
    # Custom config with various options
    custom_config = {
        "api_endpoint": "https://api.example.com",
        "api_key": "sk-...",
        "timeout": 30,
        "retry_attempts": 3,
        "cache_enabled": True,
        "debug_mode": True,
    }
    
    agent = Agent(
        name="CustomAgent",
        role="Demonstrates custom configuration",
        capabilities=["api_calls", "caching"],
        config=custom_config,
        max_context_tokens=16384  # Large context window
    )
    
    print("\n⚙️  Agent Configuration:")
    for key, value in agent.config.items():
        print(f"   {key}: {value}")
    
    print(f"\n📏 Context Window: {agent.context_manager.max_tokens} tokens")
    
    agent.start()
    print(f"\n🔐 Security Context:")
    print(f"   Created: {agent.security_context['created_at']}")
    print(f"   Last activity: {agent.security_context['last_activity']}")
    print(f"   Access count: {agent.security_context['access_count']}")
    
    agent.stop()


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                    AGENT CLASS COMPLETE GUIDE                        ║
║                    11 Progressive Examples                           ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    examples = [
        ("Basic Agent Creation", example_1_basic_agent),
        ("Quick Agent Factory", example_2_quick_agent),
        ("Agent with LLM", example_3_agent_with_llm),
        ("Context Management", example_4_context_management),
        ("Task Execution", example_5_task_execution),
        ("Role Templates", example_6_role_templates),
        ("Agent from Config", example_7_from_config),
        ("Error Handling", example_8_error_handling),
        ("Serialization", example_9_serialization),
        ("Multi-Agent System", example_10_multi_agent),
        ("Custom Configuration", example_11_custom_config),
    ]
    
    try:
        for i, (name, example_func) in enumerate(examples, 1):
            example_func()
            
        print("\n" + "="*70)
        print("✓ ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print("="*70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
