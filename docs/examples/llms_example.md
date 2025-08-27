# Language Model Management Example

This guide provides a **professional, step-by-step walkthrough** for registering, setting, and using a language model with the `LLMManager` in the `agenticaiframework` package.  
It is intended for developers integrating custom or third-party LLMs into their applications.

---

## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **No additional configuration** is required for this example.
- **Python Version**: Compatible with Python 3.8+.

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

1. **Import the Class**  
   Import `LLMManager` from `agenticaiframework.llms`.

2. **Instantiate the Manager**  
   Create an instance of `LLMManager` to handle model registration and usage.

3. **Register a Model**  
   Use `register_model` with:
   - `name`: Unique identifier for the model.
   - `callable`: A function or lambda that takes a prompt and returns generated text.

4. **Set the Active Model**  
   Use `set_active_model` to select which model will be used for generation.

5. **Generate Text**  
   Call `generate` with a prompt to produce output from the active model.

6. **List Available Models**  
   Access the `models` dictionary to see all registered models.

> **Best Practice:** Wrap third-party LLM APIs in a callable function to standardize the interface for `LLMManager`.

---

## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes. In production, prompts could be dynamically generated from user input, workflows, or other runtime data.

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

Run the example from the project root:

```bash
python examples/llms_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.llms_example
```

> **Tip:** Use `LLMManager` to manage multiple models and switch between them dynamically based on task requirements.
