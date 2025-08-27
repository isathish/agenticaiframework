# Guardrails Example

This example demonstrates how to add and validate guardrails using the `GuardrailManager` in the `agenticaiframework` package.

---

## Configuration
No special configuration is required. Ensure `agenticaiframework` is installed and accessible in your Python environment.

---

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

---

## Step-by-Step Execution

1. **Import** `GuardrailManager` from `agenticaiframework.guardrails`.
2. **Instantiate** the guardrail manager.
3. **Add** a guardrail with a name and a validation function.
4. **Validate** a compliant text string.
5. **Validate** a non-compliant text string.

---

## Expected Input
No user input is required; the script uses hardcoded values for demonstration.

---

## Expected Output

```
Compliant Output Valid: True
Non-Compliant Output Valid: False
```

---

## How to Run

```bash
python examples/guardrails_example.py
