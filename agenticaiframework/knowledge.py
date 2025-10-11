from typing import List, Dict, Any, Callable
import time


class KnowledgeRetriever:
    def __init__(self):
        self.sources: Dict[str, Callable[[str], List[Dict[str, Any]]]] = {}
        self.cache: Dict[str, Any] = {}
        self.knowledge_base: Dict[str, str] = {}  # Simple in-memory knowledge store

    def register_source(self, name: str, retrieval_fn: Callable[[str], List[Dict[str, Any]]]):
        self.sources[name] = retrieval_fn
        self._log(f"Registered knowledge source '{name}'")

    def add_knowledge(self, key: str, content: str):
        """Add knowledge to the internal knowledge base"""
        self.knowledge_base[key] = content
        self._log(f"Added knowledge for key '{key}'")

    def retrieve(self, query: str, use_cache: bool = True) -> List[Dict[str, Any]]:
        if use_cache and query in self.cache:
            self._log(f"Cache hit for query '{query}'")
            return self.cache[query]

        results = []
        for name, fn in self.sources.items():
            try:
                source_results = fn(query)
                results.extend(source_results)
                self._log(f"Retrieved {len(source_results)} items from source '{name}'")
            except Exception as e:
                self._log(f"Error retrieving from source '{name}': {e}")

        self.cache[query] = results
        return results

    def clear_cache(self):
        self.cache.clear()
        self._log("Knowledge cache cleared")

    def _log(self, message: str):
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [KnowledgeRetriever] {message}")
