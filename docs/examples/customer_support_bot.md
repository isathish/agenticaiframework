---
title: Customer Support Bot
description: Build an automated customer support bot with LLMs, guardrails, and monitoring
tags:
  - example
  - customer-support
  - chatbot
  - advanced
---

# Customer Support Bot Example

This example demonstrates building an automated customer support bot using the AgenticAI Framework.

!!! success "Enterprise-Ready Pattern"
    Part of **400+ modules** with **237 enterprise features** including multi-tenant support, compliance guardrails, and advanced monitoring.

## Overview

The customer support bot combines LLMs, guardrails, and monitoring to provide helpful, policy-compliant responses to customer inquiries.

## Key Features

- Polite and professional responses
- Guardrails for data privacy
- Real-time monitoring
- Context-aware assistance

## Code

```python
from agenticaiframework.agents import Agent
from agenticaiframework.tasks import Task
from agenticaiframework.llms import LLMManager
from agenticaiframework.guardrails import Guardrail
from agenticaiframework.monitoring import Monitor

# Example: Automated Customer Support Bot
if __name__ == "__main__":
    # Initialize components
    llm = LLMManager()
    llm.register_model("gpt-4", lambda prompt, kwargs: f"[Simulated GPT-4 Support Response to: {prompt}]")
    llm.set_active_model("gpt-4")
    guardrail = Guardrail(rules=["Be polite", "Do not provide personal data", "Stay on topic"])
    monitor = Monitor()

    # Create agent
    support_agent = Agent(
        name="CustomerSupportBot",
        llm=llm,
        guardrail=guardrail,
        monitor=monitor
    )

    # Define task
    support_task = Task(
        description="Respond to a customer asking about the refund policy for defective products.",
        expected_output="A polite, clear explanation of the refund policy."
    )

    # Run task
    result = support_agent.run_task(support_task)

    # Output result
    logger.info("=== Customer Support Response ===")
    logger.info(result)
