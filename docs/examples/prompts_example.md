# Prompt Rendering Example

This guide provides a **professional, step-by-step walkthrough** for using the `Prompt` class in the `agenticaiframework` package to create and render dynamic text templates.  
It is intended for developers building AI-driven applications that require flexible, parameterized prompt generation.


## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **No additional configuration** is required for this example.
- **Python Version**: Compatible with Python 3.8+.


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


## Step-by-Step Execution

1. **Import the Class**  
   Import `Prompt` from `agenticaiframework.prompts`.

2. **Create a Prompt Template**  
   Instantiate the `Prompt` class with a template string containing placeholders in `{}` format.

3. **Render the Prompt**  
   Call `render` with keyword arguments matching the placeholders in the template.

4. **Output the Result**  
   Print or log the rendered prompt for use in downstream AI model calls.

> **Best Practice:** Keep prompt templates clear and concise, and use descriptive placeholder names to improve maintainability.


## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes. In production, placeholder values could be dynamically generated from user input, database queries, or API responses.


## Expected Output

```
Rendered Prompt: Write a short paragraph summary about artificial intelligence.
```


## How to Run

Run the example from the project root:

```bash
python examples/prompts_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.prompts_example
```

> **Tip:** Store frequently used prompt templates in a configuration file or database for easy reuse and updates.
