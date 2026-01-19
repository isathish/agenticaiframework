---
tags:
  - examples
  - prompts
  - templates
---

# Prompt Manager Example

```python
from agenticaiframework.prompts import Prompt, PromptManager

# Example: Using the Prompt and PromptManager
# --------------------------------------------
# This example demonstrates how to:
# 1. Create prompts
# 2. Register prompts with PromptManager
# 3. Retrieve and use prompts
#
# Expected Output:
# - Display of prompt templates and filled prompts

if __name__ == "__main__":
    # Create a prompt manager
    prompt_manager = PromptManager()

    # Create some prompts
    prompt1 = Prompt(template="Hello, {name}!", metadata={"type": "greeting"})
    prompt2 = Prompt(template="The sum of {a} and {b} is {result}.", metadata={"type": "math"})

    # Register prompts
    prompt_manager.register_prompt("GreetPrompt", prompt1)
    prompt_manager.register_prompt("SumPrompt", prompt2)

    # Retrieve and use prompts
    greet_prompt = prompt_manager.get_prompt("GreetPrompt")
    if greet_prompt:
        print("GreetPrompt filled:", greet_prompt.fill({"name": "Alice"}))

    sum_prompt = prompt_manager.get_prompt("SumPrompt")
    if sum_prompt:
        print("SumPrompt filled:", sum_prompt.fill({"a": 5, "b": 7, "result": 12}))

```
