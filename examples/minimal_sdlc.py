"""
Minimal SDLC Example - Complete software development lifecycle in 20 lines.

This example demonstrates the power of the enterprise module by creating
a complete SDLC pipeline with minimal code.

Usage:
    $ python -m examples.minimal_sdlc
    
    Or:
    $ cd examples && python minimal_sdlc.py
"""

import asyncio
from agenticaiframework.enterprise import create_sdlc_pipeline


async def main():
    # Create SDLC pipeline in one line
    pipeline = create_sdlc_pipeline(
        project="my-ecommerce-app",
        description="Build a modern e-commerce platform with user authentication, product catalog, shopping cart, and payment processing",
        model="gpt-4o",
    )
    
    # Run the complete SDLC
    result = await pipeline.run(verbose=True)
    
    # Print summary
    print(result.summary())
    
    # Access individual artifacts
    if result.success:
        print("\n📦 Generated Artifacts:")
        for phase, content in result.artifacts.items():
            print(f"  • {phase}: {len(content)} characters")


if __name__ == "__main__":
    asyncio.run(main())
