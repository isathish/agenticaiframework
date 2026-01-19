---
tags:
  - examples
  - knowledge
  - retrieval
---

# Knowledge Retriever Example

```python
from agenticaiframework.knowledge import KnowledgeRetriever

# Example: Using the KnowledgeRetriever
# --------------------------------------
# This example demonstrates how to:
# 1. Create a KnowledgeRetriever
# 2. Add knowledge entries
# 3. Retrieve knowledge based on a query
#
# Expected Output:
# - Retrieved knowledge entries matching the query

if __name__ == "__main__":
    # Create a knowledge retriever
    retriever = KnowledgeRetriever()

    # Add some knowledge entries
    retriever.add_knowledge("Python", "Python is a versatile programming language.")
    retriever.add_knowledge("AI", "Artificial Intelligence enables machines to learn.")

    # Retrieve knowledge
    query = "Python"
    results = retriever.retrieve(query)

    print(f"Knowledge results for '{query}':", results)

```
