"""
Enterprise Module Usage Examples

This file demonstrates various ways to use the enterprise module
for building production AI applications with minimal code.
"""

import asyncio
from agenticaiframework.enterprise import (
    # Decorators
    agent,
    workflow,
    step,
    tool,
    guardrail,
    # Factories
    create_agent,
    create_pipeline,
    AgentFactory,
    # Blueprints
    RequirementsAgent,
    DesignAgent,
    get_blueprint,
    # SDLC
    create_sdlc_pipeline,
    # Adapters
    AzureAdapter,
    get_adapter,
    # Presets
    load_preset,
    auto_preset,
)


# =============================================================================
# Example 1: Using Decorators
# =============================================================================

@agent(role="data analyst", model="gpt-4o")
class DataAnalyst:
    """Custom analyst agent using decorator."""
    
    async def analyze(self, data: str) -> str:
        """Analyze data and return insights."""
        return await self.invoke(f"Analyze this data and provide insights:\n\n{data}")


@workflow(name="analysis-pipeline")
class AnalysisPipeline:
    """Custom workflow using decorator."""
    
    @step(order=1)
    async def collect_data(self, source: str) -> str:
        """Collect data from source."""
        return f"Data collected from {source}"
    
    @step(order=2)
    async def process_data(self, data: str) -> str:
        """Process the collected data."""
        return f"Processed: {data}"
    
    @step(order=3)
    async def generate_report(self, data: str) -> str:
        """Generate final report."""
        return f"Report for: {data}"


@tool(name="calculator", description="Perform mathematical calculations")
async def calculator(expression: str) -> float:
    """Calculate mathematical expression."""
    return eval(expression)


# =============================================================================
# Example 2: Using Factories (One-liners)
# =============================================================================

async def factory_examples():
    """Examples using factory methods."""
    
    # Create agent from template
    analyst = create_agent("analyst", model="gpt-4o")
    coder = create_agent("coder", model="gpt-4o")
    
    # Create from factory with more control
    custom_agent = AgentFactory.create(
        "custom",
        name="ProjectManager",
        role="A project manager that coordinates software development",
        model="gpt-4o",
        tools=["calendar", "email"],
    )
    
    # Create SDLC pipeline
    pipeline = create_pipeline(
        "sdlc",
        project="my-app",
        description="Build a REST API",
    )
    
    return analyst, coder, custom_agent, pipeline


# =============================================================================
# Example 3: Using Blueprints (Pre-built Agents)
# =============================================================================

async def blueprint_examples():
    """Examples using blueprint agents."""
    
    # Use SDLC blueprint agents directly
    req_agent = RequirementsAgent()
    design_agent = DesignAgent()
    
    # Analyze requirements
    requirements = await req_agent.analyze(
        "Build a user authentication system with OAuth support"
    )
    
    # Create design based on requirements
    design = await design_agent.design(requirements)
    
    # Get any blueprint by name
    security_agent = get_blueprint("security")
    security_report = await security_agent.analyze(design)
    
    return requirements, design, security_report


# =============================================================================
# Example 4: Using Adapters (Cloud Services)
# =============================================================================

async def adapter_examples():
    """Examples using cloud adapters."""
    
    # Azure adapter (auto-configured from environment)
    azure = AzureAdapter()
    
    # Use storage
    await azure.storage.upload("reports/analysis.txt", "Analysis results...")
    content = await azure.storage.download("reports/analysis.txt")
    
    # Use LLM
    response = await azure.llm.generate("Explain machine learning")
    
    # Auto-detect cloud provider from environment
    adapter = get_adapter()  # Returns Azure/AWS/GCP based on env vars
    
    return content, response


# =============================================================================
# Example 5: Using Presets (Configuration)
# =============================================================================

async def preset_examples():
    """Examples using configuration presets."""
    
    # Load specific preset
    enterprise_config = load_preset("enterprise")
    startup_config = load_preset("startup")
    
    # Auto-detect from environment
    config = auto_preset()  # Based on ENVIRONMENT or ENV variable
    
    # Use preset config with SDLC pipeline
    pipeline = create_sdlc_pipeline(
        "my-project",
        "Build an e-commerce platform",
        **enterprise_config.to_dict(),
    )
    
    return enterprise_config, startup_config, config


# =============================================================================
# Example 6: Complete SDLC in One Call
# =============================================================================

async def sdlc_example():
    """Complete SDLC pipeline example."""
    
    # Create and run SDLC pipeline
    pipeline = create_sdlc_pipeline(
        project="e-commerce-api",
        description="""
        Build a modern e-commerce REST API with:
        - User authentication (JWT)
        - Product catalog management
        - Shopping cart functionality
        - Order processing
        - Payment integration (Stripe)
        - Admin dashboard API
        """,
        model="gpt-4o",
        phases=["requirements", "design", "development", "testing", "security"],
    )
    
    # Run all phases
    result = await pipeline.run(verbose=True)
    
    # Print results
    print(result.summary())
    
    return result


# =============================================================================
# Main
# =============================================================================

async def main():
    """Run all examples."""
    print("=" * 60)
    print("Enterprise Module Examples")
    print("=" * 60)
    
    # Example 1: Decorators
    print("\n1. Decorator Examples")
    print("-" * 40)
    analyst = DataAnalyst()
    # result = await analyst.analyze("Sales data: Q1=$100k, Q2=$150k, Q3=$200k")
    # print(f"Analysis: {result[:200]}...")
    print("DataAnalyst class created with @agent decorator")
    
    # Example 2: Factories
    print("\n2. Factory Examples")
    print("-" * 40)
    # agents = await factory_examples()
    # print(f"Created {len(agents)} components with factories")
    print("Agents can be created with create_agent('template')")
    
    # Example 3: Blueprints
    print("\n3. Blueprint Examples")
    print("-" * 40)
    # results = await blueprint_examples()
    # print(f"Generated {len(results)} outputs with blueprints")
    print("Pre-built agents available: RequirementsAgent, DesignAgent, etc.")
    
    # Example 4: Adapters
    print("\n4. Adapter Examples")
    print("-" * 40)
    # results = await adapter_examples()
    print("Cloud adapters: AzureAdapter, AWSAdapter, GCPAdapter")
    
    # Example 5: Presets
    print("\n5. Preset Examples")
    print("-" * 40)
    # configs = await preset_examples()
    print("Available presets: enterprise, startup, development, production")
    
    # Example 6: SDLC (uncomment to run)
    # print("\n6. SDLC Pipeline Example")
    # print("-" * 40)
    # result = await sdlc_example()
    
    print("\n" + "=" * 60)
    print("Examples complete! Uncomment function calls to run actual examples.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
