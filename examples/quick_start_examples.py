#!/usr/bin/env python3
"""
Quick Start Examples - Minimal Boilerplate API
===============================================

This file demonstrates the new developer-friendly APIs that require
minimal code to get started with the AgenticAI Framework.

Before:  50+ lines of setup code
After:   1-5 lines to create a production-ready agent
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agenticaiframework as aaf

# ============================================================================
# EXAMPLE 1: One-Line Agent Creation with Agent.quick()
# ============================================================================

def example_quick_agent():
    """
    Create a fully configured agent in ONE LINE.
    
    Agent.quick() handles:
    - LLM detection from environment (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
    - Default guardrails (safety, length limits)
    - Role-appropriate system prompt
    - Tracing and monitoring
    """
    print("\n" + "="*60)
    print("EXAMPLE 1: One-Line Agent with Agent.quick()")
    print("="*60)
    
    # Before (old way - 30+ lines):
    # -----------------------------
    # llm = LLMManager()
    # llm.add_provider("openai", OpenAIConfig(...))
    # context = ContextManager()
    # guardrails = GuardrailPipeline()
    # guardrails.add(InputLengthGuardrail(...))
    # guardrails.add(OutputGuardrail(...))
    # memory = Memory()
    # tracer = AgentStepTracer()
    # agent = Agent(
    #     name="Assistant",
    #     llm=llm,
    #     context=context,
    #     guardrails=guardrails,
    #     memory=memory,
    #     tracer=tracer,
    # )
    
    # After (new way - 1 line):
    # -------------------------
    agent = aaf.Agent.quick("Assistant")
    
    print(f"Created agent: {agent.name}")
    print(f"  - Role: {agent.role}")
    print(f"  - Has context manager: {agent.context_manager is not None}")
    print(f"  - Capabilities: {agent.capabilities}")
    print("  - Ready to use immediately!")
    
    return agent


# ============================================================================
# EXAMPLE 2: Role-Based Agents with Automatic Configuration
# ============================================================================

def example_role_based_agents():
    """
    Create specialized agents with role-appropriate defaults.
    
    Available roles:
    - "researcher": Deep analysis, web search, document retrieval
    - "coder": Code generation, debugging, testing
    - "analyst": Data analysis, visualization, reporting
    - "writer": Content creation, editing, formatting
    - "assistant": General purpose (default)
    """
    print("\n" + "="*60)
    print("EXAMPLE 2: Role-Based Agents")
    print("="*60)
    
    # Each role gets appropriate system prompt and tool recommendations
    roles = ["researcher", "coder", "analyst", "writer", "assistant"]
    
    for role in roles:
        agent = aaf.Agent.quick(f"{role.title()}Bot", role=role)
        print(f"\n  {role.upper()} Agent:")
        print(f"    - Name: {agent.name}")
        print(f"    - Role: {agent.role[:80]}...")
        print(f"    - Capabilities: {agent.capabilities}")


# ============================================================================
# EXAMPLE 3: Agent from Configuration Dictionary
# ============================================================================

def example_from_config():
    """
    Create an agent from a configuration dictionary.
    
    Perfect for:
    - Loading from YAML/JSON files
    - Environment-specific configurations
    - Dynamic agent creation
    """
    print("\n" + "="*60)
    print("EXAMPLE 3: Agent from Config Dictionary")
    print("="*60)
    
    # Configuration can come from YAML, JSON, environment, etc.
    config = {
        "name": "ProductionAgent",
        "role": "analyst",
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 2000,
        "guardrails": "enterprise",  # Use enterprise preset
        "tools": ["calculator", "web_search"],
        "memory": {
            "type": "conversation",
            "max_history": 50
        }
    }
    
    agent = aaf.Agent.from_config(config)
    
    print(f"Created from config: {agent.name}")
    print(f"  - Configuration applied successfully")


# ============================================================================
# EXAMPLE 4: Global Framework Configuration
# ============================================================================

def example_global_configure():
    """
    Configure the entire framework globally with one call.
    
    aaf.configure() sets:
    - Default LLM provider
    - Default guardrails preset
    - Default tracing settings
    - Default memory configuration
    
    After calling configure(), ALL new agents inherit these defaults.
    """
    print("\n" + "="*60)
    print("EXAMPLE 4: Global Framework Configuration")
    print("="*60)
    
    # Configure entire framework once at application startup
    aaf.configure(
        # LLM provider (auto-detects API key from environment)
        provider="openai",
        model="gpt-4",
        
        # Guardrails preset: "minimal", "safety", or "enterprise"
        guardrails="safety",
        
        # Enable tracing
        tracing=True,
        
        # Memory configuration
        memory={"type": "conversation", "max_history": 100},
    )
    
    print("Framework configured globally!")
    print(f"  - Is configured: {aaf.is_configured()}")
    
    # Get the current config
    config = aaf.get_config()
    print(f"  - Provider: {config.default_provider}")
    print(f"  - Model: {config.default_model}")
    print(f"  - Guardrails: {config.guardrails_preset}")
    
    # Now all agents automatically use these defaults
    agent1 = aaf.Agent.quick("Agent1")
    agent2 = aaf.Agent.quick("Agent2")
    
    print("  - All new agents inherit global configuration")
    
    # Reset for other examples
    aaf.reset_config()


# ============================================================================
# EXAMPLE 5: Guardrail Pipeline Presets
# ============================================================================

def example_guardrail_presets():
    """
    Use pre-configured guardrail pipelines.
    
    Presets:
    - minimal(): Basic length limits only
    - safety_only(): PII detection + prompt injection protection
    - enterprise_defaults(): Full security suite
    """
    print("\n" + "="*60)
    print("EXAMPLE 5: Guardrail Pipeline Presets")
    print("="*60)
    
    from agenticaiframework.guardrails import GuardrailPipeline
    
    # Before (old way - many lines):
    # pipeline = GuardrailPipeline()
    # pipeline.add(PromptInjectionGuardrail(...))
    # pipeline.add(PIIDetectionGuardrail(...))
    # pipeline.add(InputLengthGuardrail(...))
    # ...
    
    # After (new way - 1 line each):
    minimal = GuardrailPipeline.minimal()
    safety = GuardrailPipeline.safety_only()
    enterprise = GuardrailPipeline.enterprise_defaults()
    
    print("\nAvailable Presets:")
    print("  - minimal(): Basic input/output length limits")
    print("  - safety_only(): PII + Prompt Injection protection")
    print("  - enterprise_defaults(): Full security suite")
    
    # Custom combination
    from agenticaiframework.guardrails.specialized import (
        PromptInjectionGuardrail, PIIDetectionGuardrail, InputLengthGuardrail
    )
    custom = GuardrailPipeline.custom(
        name="my_custom_pipeline",
        guardrails=[
            PIIDetectionGuardrail(),
            PromptInjectionGuardrail(),
            InputLengthGuardrail(max_length=5000),
        ],
    )
    print("  - custom(...): Build your own combination")


# ============================================================================
# EXAMPLE 6: Tool Auto-Discovery
# ============================================================================

def example_tool_discovery():
    """
    Automatically discover and register tools from modules.
    
    Just point to a module and the registry finds all BaseTool subclasses.
    """
    print("\n" + "="*60)
    print("EXAMPLE 6: Tool Auto-Discovery")
    print("="*60)
    
    from agenticaiframework.tools import ToolRegistry
    
    # Create a registry
    registry = ToolRegistry()
    
    # Before (old way - register each tool manually):
    # registry.register(CalculatorTool())
    # registry.register(WebSearchTool())
    # registry.register(FileReaderTool())
    # ... (repeat for every tool)
    
    # After (new way - auto-discover from modules):
    # registry.discover("mypackage.tools")  # Finds all BaseTool subclasses
    
    # Discover from the framework's built-in tools
    discovered = registry.discover("agenticaiframework.tools")
    
    print(f"Auto-discovered {len(discovered)} tools from module")
    for tool_name in discovered[:5]:  # Show first 5
        print(f"  - {tool_name}")
    if len(discovered) > 5:
        print(f"  ... and {len(discovered) - 5} more")


# ============================================================================
# EXAMPLE 7: LLM Provider Auto-Detection
# ============================================================================

def example_llm_auto_detection():
    """
    LLMManager automatically detects and configures providers from environment.
    
    Checks for:
    - OPENAI_API_KEY
    - ANTHROPIC_API_KEY
    - GOOGLE_API_KEY / GEMINI_API_KEY
    """
    print("\n" + "="*60)
    print("EXAMPLE 7: LLM Provider Auto-Detection")
    print("="*60)
    
    from agenticaiframework.llms import LLMManager
    
    # Before (old way):
    # manager = LLMManager()
    # if os.getenv("OPENAI_API_KEY"):
    #     from agenticaiframework.llms.providers import OpenAIProvider
    #     provider = OpenAIProvider.from_env()
    #     manager.register_provider("openai", provider)
    # if os.getenv("ANTHROPIC_API_KEY"):
    #     ...
    
    # After (new way - 1 line):
    manager = LLMManager.from_environment()
    
    print("LLM Manager auto-configured from environment!")
    print("Detected API keys will auto-register providers:")
    print("  - OPENAI_API_KEY -> OpenAI (GPT-4, GPT-4o)")
    print("  - ANTHROPIC_API_KEY -> Claude (Claude 3)")
    print("  - GOOGLE_API_KEY -> Gemini (Gemini Pro)")


# ============================================================================
# EXAMPLE 8: Complete Production Setup in 5 Lines
# ============================================================================

def example_production_setup():
    """
    A complete production-ready agent in just 5 lines.
    """
    print("\n" + "="*60)
    print("EXAMPLE 8: Complete Production Setup (5 Lines)")
    print("="*60)
    
    code = '''
# Line 1: Import
import agenticaiframework as aaf

# Line 2: Global configuration
aaf.configure(provider="openai", guardrails="enterprise", tracing=True)

# Line 3: Create agent
agent = aaf.Agent.quick("ProductionAssistant", role="assistant")

# Line 4: Add specialized tools
agent.add_tool(aaf.tools.PythonCodeExecutor())

# Line 5: Run
result = agent.run("Analyze the data and create a report")
'''
    
    print("Complete production setup:")
    print("-" * 40)
    print(code)
    print("-" * 40)
    print("\nThis gives you:")
    print("  - Enterprise guardrails (PII, injection protection)")
    print("  - Automatic LLM detection")
    print("  - Full tracing and monitoring")
    print("  - Code execution capability")
    print("  - Memory and context management")


# ============================================================================
# MAIN: Run all examples
# ============================================================================

if __name__ == "__main__":
    print("\n" + "#"*60)
    print("#  AgenticAI Framework - Quick Start Examples")
    print("#  Minimal Boilerplate, Maximum Productivity")
    print("#"*60)
    
    # Run each example
    example_quick_agent()
    example_role_based_agents()
    example_from_config()
    example_global_configure()
    example_guardrail_presets()
    example_tool_discovery()
    example_llm_auto_detection()
    example_production_setup()
    
    print("\n" + "="*60)
    print("All examples completed successfully!")
    print("="*60)
    print("\nKey Takeaways:")
    print("  1. Agent.quick() - One-line agent creation")
    print("  2. Agent.from_config() - Dictionary/YAML configuration")
    print("  3. aaf.configure() - Global framework setup")
    print("  4. GuardrailPipeline.enterprise_defaults() - Security presets")
    print("  5. ToolRegistry.discover() - Auto-find tools")
    print("  6. LLMManager.from_environment() - Auto-detect providers")
    print("\nWrite less code. Build faster. Ship with confidence!")
