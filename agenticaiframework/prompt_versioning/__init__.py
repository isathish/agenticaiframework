"""
Prompt Versioning Package.

Version control and management for prompts:
- Version control for prompts
- Semantic versioning
- A/B testing integration
- Rollback capabilities
- Audit trail
- Template inheritance
"""

from .types import (
    PromptStatus,
    PromptVersion,
    PromptAuditEntry,
)
from .manager import PromptVersionManager
from .library import PromptLibrary

# Global instances
prompt_version_manager = PromptVersionManager()
prompt_library = PromptLibrary()

__all__ = [
    # Types
    'PromptStatus',
    'PromptVersion',
    'PromptAuditEntry',
    # Classes
    'PromptVersionManager',
    'PromptLibrary',
    # Global instances
    'prompt_version_manager',
    'prompt_library',
]
