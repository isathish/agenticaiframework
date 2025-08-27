# LLMs Module

## Overview
The `llms` module in the AgenticAI Framework provides integration with Large Language Models (LLMs) for natural language understanding, generation, and reasoning. It abstracts away the complexity of interacting with different LLM providers, enabling developers to easily plug in and use models for various AI-driven tasks.

## Key Classes and Functions
- **LLMClient** — A unified client interface for interacting with supported LLM providers.
- **LLMConfig** — Configuration object for specifying model parameters, API keys, and provider-specific settings.
- **generate_text(prompt, **kwargs)** — Generates text based on a given prompt.
- **stream_text(prompt, **kwargs)** — Streams generated text in real-time for interactive applications.
- **embed_text(text, **kwargs)** — Generates vector embeddings for semantic search and similarity tasks.

## Example Usage
```python
from agenticaiframework.llms import LLMClient, LLMConfig

# Configure the LLM
config = LLMConfig(
    provider="openai",
    model="gpt-4",
    api_key="your_api_key_here"
)

# Initialize the client
llm = LLMClient(config)

# Generate text
response = llm.generate_text("Explain quantum computing in simple terms.")
print(response)
```

## Use Cases
- Conversational AI agents
- Automated content generation
- Code generation and completion
- Semantic search and retrieval
- Summarization and paraphrasing

## Best Practices
- Use streaming for interactive chatbots to improve responsiveness.
- Cache embeddings for repeated semantic search queries.
- Handle API rate limits and errors gracefully.
- Keep API keys secure using environment variables or secret managers.

## Related Documentation
- [Prompts Module](prompts.md)
- [Knowledge Module](knowledge.md)
- [Agents Module](agents.md)
