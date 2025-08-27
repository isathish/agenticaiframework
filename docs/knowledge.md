# Knowledge Module

## Overview
The `knowledge` module in the AgenticAI Framework manages structured and unstructured knowledge sources for AI agents. It enables retrieval, storage, and querying of domain-specific information to enhance reasoning and contextual understanding.

## Key Classes and Functions
- **KnowledgeBase** — Core class for storing and retrieving knowledge entries.
- **Document** — Represents a single knowledge item with metadata.
- **add_document(document)** — Adds a new document to the knowledge base.
- **search(query, **kwargs)** — Searches the knowledge base for relevant documents.
- **load_from_source(source)** — Loads knowledge from external sources (files, APIs, databases).

## Example Usage
```python
from agenticaiframework.knowledge import KnowledgeBase, Document

# Initialize knowledge base
kb = KnowledgeBase()

# Add a document
doc = Document(content="Python is a high-level programming language.", metadata={"topic": "programming"})
kb.add_document(doc)

# Search for information
results = kb.search("What is Python?")
for r in results:
    print(r.content)
```

## Use Cases
- Enhancing LLM responses with domain-specific facts.
- Building retrieval-augmented generation (RAG) systems.
- Creating searchable internal knowledge repositories.
- Integrating with external data sources for dynamic updates.

## Best Practices
- Keep metadata consistent for better filtering and retrieval.
- Periodically update the knowledge base to maintain relevance.
- Use embeddings for semantic search to improve accuracy.
- Secure sensitive knowledge sources with access controls.

## Related Documentation
- [LLMs Module](llms.md)
- [Prompts Module](prompts.md)
- [Agents Module](agents.md)
