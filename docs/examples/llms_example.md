# LLMs Example

This example demonstrates how to register, set, and use a language model with the `LLMManager` in the `agenticaiframework` package.

---

## Configuration
No special configuration is required. Ensure `agenticaiframework` is installed and accessible in your Python environment.

---

## Code

```python
from agenticaiframework.llms import LLMManager

if __name__ == "__main__":
    llm_manager = LLMManager()

    # Register a demo LLM model
    llm_manager.register_model("demo-llm", lambda prompt: f"[Demo LLM Response to: {prompt}]")

    # Set the active model
    llm_manager.set_active_model("demo-llm")

    # Generate text using the active model
    print("Generated Text:", llm_manager.generate("Explain the concept of machine learning in simple terms."))

    # List available models
    print("Available Models:", list(llm_manager.models.keys()))
```

---

## Step-by-Step Execution

1. **Import** `LLMManager` from `agenticaiframework.llms`.
2. **Instantiate** the LLM manager.
3. **Register** a model with a name and a callable that generates text.
4. **Set** the active model using `set_active_model`.
5. **Generate** text using the `generate` method with a prompt.
6. **List** all available models.

---

## Expected Input
No user input is required; the script uses hardcoded values for demonstration.

---

## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [LLMManager] Registered LLM model 'demo-llm'
[YYYY-MM-DD HH:MM:SS] [LLMManager] Active LLM model set to 'demo-llm'
Generated Text: [Demo LLM Response to: Explain the concept of machine learning in simple terms.]
Available Models: ['demo-llm']
```

---

## How to Run

```bash
python examples/llms_example.py
