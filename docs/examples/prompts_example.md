# Prompts Example

This example demonstrates how to use the `Prompt` class in the `agenticaiframework` package to render dynamic text templates.

---

## Configuration
No special configuration is required. Ensure `agenticaiframework` is installed and accessible in your Python environment.

---

## Code

```python
from agenticaiframework.prompts import Prompt

if __name__ == "__main__":
    # Create a prompt template
    prompt_instance = Prompt(
        template="Write a {length} paragraph summary about {topic}."
    )

    # Render the prompt with variables
    rendered_prompt = prompt_instance.render(length="short", topic="artificial intelligence")
    print("Rendered Prompt:", rendered_prompt)
```

---

## Step-by-Step Execution

1. **Import** `Prompt` from `agenticaiframework.prompts`.
2. **Instantiate** the `Prompt` class with a template string containing placeholders.
3. **Render** the prompt by passing keyword arguments matching the placeholders.
4. **Print** the rendered prompt.

---

## Expected Input
No user input is required; the script uses hardcoded values for demonstration.

---

## Expected Output

```
Rendered Prompt: Write a short paragraph summary about artificial intelligence.
```

---

## How to Run

```bash
python examples/prompts_example.py
