# Guardrail Management Example

This guide provides a **professional, step-by-step walkthrough** for adding and validating guardrails using the `GuardrailManager` in the `agenticaiframework` package.  
It is intended for developers who want to enforce content safety, compliance, or quality rules in AI-generated outputs.


## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **No additional configuration** is required for this example.
- **Python Version**: Compatible with Python 3.8+.


## Code

```python
from agenticaiframework.guardrails import GuardrailManager

if __name__ == "__main__":
    guardrail_manager = GuardrailManager()

    # Add a guardrail to prevent profanity
    guardrail_manager.add_guardrail("No profanity", lambda text: "badword" not in text)

    # Validate compliant and non-compliant outputs
    print("Compliant Output Valid:", guardrail_manager.validate("This is clean text."))
    print("Non-Compliant Output Valid:", guardrail_manager.validate("This contains badword."))
```


## Step-by-Step Execution

1. **Import the Class**  
   Import `GuardrailManager` from `agenticaiframework.guardrails`.

2. **Instantiate the Manager**  
   Create an instance of `GuardrailManager` to manage guardrail rules.

3. **Add a Guardrail**  
   Use `add_guardrail` with:
   - `name`: A descriptive name for the guardrail.
   - `validation_fn`: A function that returns `True` if the content passes, `False` otherwise.

4. **Validate Compliant Output**  
   Call `validate` with a text string that should pass the guardrail.

5. **Validate Non-Compliant Output**  
   Call `validate` with a text string that should fail the guardrail.

> **Best Practice:** Keep guardrail functions efficient and deterministic to avoid performance bottlenecks in production.


## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes. In production, guardrails could be dynamically loaded from configuration files or policy management systems.


## Expected Output

```
Compliant Output Valid: True
Non-Compliant Output Valid: False
```


## How to Run

Run the example from the project root:

```bash
python examples/guardrails_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.guardrails_example
```

> **Tip:** Combine `GuardrailManager` with `LLMManager` to automatically validate AI-generated outputs before returning them to users.
