"""
Prompt Library.

Library of reusable prompt components and templates:
- Template inheritance
- Component composition
- Category organization
- Search and discovery
"""

import uuid
import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class PromptLibrary:
    """
    Library of reusable prompt components and templates.
    
    Features:
    - Template inheritance
    - Component composition
    - Category organization
    - Search and discovery
    """
    
    def __init__(self):
        self.components: Dict[str, Dict[str, Any]] = {}
        self.categories: Dict[str, List[str]] = {}
    
    def register_component(self,
                          name: str,
                          content: str,
                          category: str = "general",
                          description: str = None):
        """Register a reusable prompt component."""
        component = {
            'id': str(uuid.uuid4()),
            'name': name,
            'content': content,
            'category': category,
            'description': description or "",
            'created_at': time.time()
        }
        
        self.components[name] = component
        
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(name)
        
        logger.info("Registered component '%s' in category '%s'", name, category)
    
    def compose(self, components: List[str], separator: str = "\n\n") -> str:
        """Compose multiple components into a single prompt."""
        parts = []
        for comp_name in components:
            if comp_name in self.components:
                parts.append(self.components[comp_name]['content'])
            else:
                logger.warning("Component '%s' not found", comp_name)
        
        return separator.join(parts)
    
    def extend(self, base_component: str, 
              extensions: Dict[str, str]) -> str:
        """
        Extend a base component with additional content.
        
        Extensions can include:
        - 'prefix': Content to add before
        - 'suffix': Content to add after
        - 'replace_{placeholder}': Replace {placeholder} in base
        """
        if base_component not in self.components:
            raise ValueError(f"Component '{base_component}' not found")
        
        content = self.components[base_component]['content']
        
        # Apply replacements
        for key, value in extensions.items():
            if key.startswith('replace_'):
                placeholder = key[8:]
                content = content.replace(f"{{{placeholder}}}", value)
        
        # Apply prefix/suffix
        if 'prefix' in extensions:
            content = extensions['prefix'] + "\n\n" + content
        
        if 'suffix' in extensions:
            content = content + "\n\n" + extensions['suffix']
        
        return content
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search components by name or description."""
        query_lower = query.lower()
        results = []
        
        for name, component in self.components.items():
            if (query_lower in name.lower() or 
                query_lower in component.get('description', '').lower()):
                results.append(component)
        
        return results
    
    def list_by_category(self, category: str) -> List[Dict[str, Any]]:
        """List components in a category."""
        names = self.categories.get(category, [])
        return [self.components[n] for n in names if n in self.components]
    
    def get_categories(self) -> List[str]:
        """Get all categories."""
        return list(self.categories.keys())
    
    def get_component(self, name: str) -> Dict[str, Any]:
        """Get a component by name."""
        if name not in self.components:
            raise ValueError(f"Component '{name}' not found")
        return self.components[name]


__all__ = ['PromptLibrary']
