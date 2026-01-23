---
title: LLM Manager Example
description: Register and use LLM providers with LLMManager for text generation
tags:
  - examples
  - llms
  - models
---

# 🧠 LLM Manager Example

!!! success "18+ LLM Providers"
    Part of **380+ modules** supporting OpenAI, Anthropic, Gemini, Azure, AWS Bedrock, and more. See [LLM Documentation](../llms.md).

```python
from agenticaiframework.llms import LLMManager

# Example: Using the LLMManager
# -----------------------------
# This example demonstrates how to:
# 1. Create an LLMManager
# 2. Register LLM models
# 3. Generate text using a registered model
#
# Expected Output:
# - Generated text from the selected model

if __name__ == "__main__":
    # Create an LLM manager
    llm_manager = LLMManager()

    # Define a mock LLM function
    def mock_llm(prompt):
        return f"Generated response for: {prompt}"

    # Register the mock LLM
    llm_manager.register_model("MockLLM", mock_llm)

    # Generate text using the registered model
    prompt_text = "What is the capital of France?"
    response = llm_manager.generate("MockLLM", prompt_text)
    print("LLM Response:", response)

```
