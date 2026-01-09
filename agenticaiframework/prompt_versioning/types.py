"""
Prompt Versioning Types.

Common types, enums, and dataclasses for prompt versioning.
"""

import hashlib
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


class PromptStatus(Enum):
    """Status of a prompt version."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class PromptVersion:
    """Represents a versioned prompt."""
    prompt_id: str
    version: str
    name: str
    template: str
    variables: List[str]
    status: PromptStatus
    created_at: float
    created_by: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_version: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    @property
    def content_hash(self) -> str:
        """Get hash of template content."""
        return hashlib.sha256(self.template.encode()).hexdigest()[:12]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'prompt_id': self.prompt_id,
            'version': self.version,
            'name': self.name,
            'template': self.template,
            'variables': self.variables,
            'status': self.status.value,
            'created_at': self.created_at,
            'created_by': self.created_by,
            'metadata': self.metadata,
            'parent_version': self.parent_version,
            'tags': self.tags,
            'content_hash': self.content_hash
        }


@dataclass
class PromptAuditEntry:
    """Audit trail entry for prompt changes."""
    entry_id: str
    prompt_id: str
    version: str
    action: str
    actor: str
    timestamp: float
    details: Dict[str, Any] = field(default_factory=dict)


__all__ = [
    'PromptStatus',
    'PromptVersion',
    'PromptAuditEntry',
]
