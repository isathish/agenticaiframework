"""
Prompt Versioning and Management System.

Features:
- Version control for prompts
- Semantic versioning
- A/B testing integration
- Rollback capabilities
- Audit trail
- Template inheritance
"""

import uuid
import time
import hashlib
import logging
import json
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


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


class PromptVersionManager:
    """
    Manages versioned prompts with full lifecycle support.
    
    Features:
    - Semantic versioning (major.minor.patch)
    - Draft -> Active -> Deprecated workflow
    - Rollback support
    - Audit logging
    """
    
    def __init__(self, storage_path: str = None):
        self.prompts: Dict[str, Dict[str, PromptVersion]] = {}  # prompt_id -> {version -> PromptVersion}
        self.active_versions: Dict[str, str] = {}  # prompt_id -> active version
        self.audit_log: List[PromptAuditEntry] = []
        self.storage_path = storage_path
        
        self._lock = threading.Lock()
        
        # Load from storage if path provided
        if storage_path:
            self._load_from_storage()
    
    def create_prompt(self,
                     name: str,
                     template: str,
                     variables: List[str] = None,
                     created_by: str = "system",
                     metadata: Dict[str, Any] = None,
                     tags: List[str] = None) -> PromptVersion:
        """
        Create a new prompt (version 1.0.0).
        
        Args:
            name: Prompt name
            template: Prompt template with {variable} placeholders
            variables: List of variable names
            created_by: Creator identifier
            metadata: Additional metadata
            tags: Categorization tags
        """
        prompt_id = str(uuid.uuid4())
        
        # Auto-detect variables if not provided
        if variables is None:
            import re
            variables = list(set(re.findall(r'\{(\w+)\}', template)))
        
        version = PromptVersion(
            prompt_id=prompt_id,
            version="1.0.0",
            name=name,
            template=template,
            variables=variables,
            status=PromptStatus.DRAFT,
            created_at=time.time(),
            created_by=created_by,
            metadata=metadata or {},
            tags=tags or []
        )
        
        with self._lock:
            self.prompts[prompt_id] = {"1.0.0": version}
        
        self._audit("create", prompt_id, "1.0.0", created_by, {
            'name': name,
            'variables': variables
        })
        
        logger.info("Created prompt '%s' (id=%s, v1.0.0)", name, prompt_id)
        
        return version
    
    def create_version(self,
                      prompt_id: str,
                      template: str,
                      version_bump: str = "patch",
                      created_by: str = "system",
                      changelog: str = None,
                      variables: List[str] = None) -> PromptVersion:
        """
        Create a new version of an existing prompt.
        
        Args:
            prompt_id: Existing prompt ID
            template: New template content
            version_bump: 'major', 'minor', or 'patch'
            created_by: Creator identifier
            changelog: Description of changes
            variables: New variables (auto-detected if None)
        """
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        # Get latest version
        versions = sorted(self.prompts[prompt_id].keys(), 
                         key=lambda v: [int(x) for x in v.split('.')])
        latest = versions[-1]
        latest_version = self.prompts[prompt_id][latest]
        
        # Calculate new version
        major, minor, patch = [int(x) for x in latest.split('.')]
        
        if version_bump == "major":
            new_version = f"{major + 1}.0.0"
        elif version_bump == "minor":
            new_version = f"{major}.{minor + 1}.0"
        else:
            new_version = f"{major}.{minor}.{patch + 1}"
        
        # Auto-detect variables
        if variables is None:
            import re
            variables = list(set(re.findall(r'\{(\w+)\}', template)))
        
        version = PromptVersion(
            prompt_id=prompt_id,
            version=new_version,
            name=latest_version.name,
            template=template,
            variables=variables,
            status=PromptStatus.DRAFT,
            created_at=time.time(),
            created_by=created_by,
            metadata={'changelog': changelog} if changelog else {},
            parent_version=latest,
            tags=latest_version.tags.copy()
        )
        
        with self._lock:
            self.prompts[prompt_id][new_version] = version
        
        self._audit("create_version", prompt_id, new_version, created_by, {
            'parent_version': latest,
            'version_bump': version_bump,
            'changelog': changelog
        })
        
        logger.info("Created version %s for prompt '%s'", new_version, prompt_id)
        
        return version
    
    def activate(self, prompt_id: str, version: str, activated_by: str = "system"):
        """
        Activate a prompt version (make it the default).
        
        Deprecates the previously active version.
        """
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        if version not in self.prompts[prompt_id]:
            raise ValueError(f"Version '{version}' not found")
        
        with self._lock:
            # Deprecate current active version
            if prompt_id in self.active_versions:
                old_version = self.active_versions[prompt_id]
                if old_version in self.prompts[prompt_id]:
                    self.prompts[prompt_id][old_version].status = PromptStatus.DEPRECATED
            
            # Activate new version
            self.prompts[prompt_id][version].status = PromptStatus.ACTIVE
            self.active_versions[prompt_id] = version
        
        self._audit("activate", prompt_id, version, activated_by, {})
        logger.info("Activated prompt %s version %s", prompt_id, version)
    
    def deprecate(self, prompt_id: str, version: str, deprecated_by: str = "system"):
        """Deprecate a prompt version."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        with self._lock:
            if version in self.prompts[prompt_id]:
                self.prompts[prompt_id][version].status = PromptStatus.DEPRECATED
        
        self._audit("deprecate", prompt_id, version, deprecated_by, {})
        logger.info("Deprecated prompt %s version %s", prompt_id, version)
    
    def rollback(self, prompt_id: str, target_version: str, rolled_back_by: str = "system"):
        """
        Rollback to a previous version.
        
        Creates a new version based on the target and activates it.
        """
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        if target_version not in self.prompts[prompt_id]:
            raise ValueError(f"Version '{target_version}' not found")
        
        target = self.prompts[prompt_id][target_version]
        
        # Create new version based on target
        new_version = self.create_version(
            prompt_id=prompt_id,
            template=target.template,
            version_bump="patch",
            created_by=rolled_back_by,
            changelog=f"Rollback to version {target_version}",
            variables=target.variables.copy()
        )
        
        # Activate the new version
        self.activate(prompt_id, new_version.version, rolled_back_by)
        
        self._audit("rollback", prompt_id, new_version.version, rolled_back_by, {
            'rolled_back_from': self.active_versions.get(prompt_id),
            'rolled_back_to': target_version
        })
        
        logger.info("Rolled back prompt %s to version %s (new: %s)", 
                   prompt_id, target_version, new_version.version)
        
        return new_version
    
    def get_prompt(self, prompt_id: str, version: str = None) -> Optional[PromptVersion]:
        """
        Get a prompt version.
        
        If version is None, returns the active version.
        """
        if prompt_id not in self.prompts:
            return None
        
        if version is None:
            version = self.active_versions.get(prompt_id)
            if version is None:
                # Return latest
                versions = sorted(self.prompts[prompt_id].keys(),
                                key=lambda v: [int(x) for x in v.split('.')])
                version = versions[-1] if versions else None
        
        return self.prompts[prompt_id].get(version)
    
    def render(self, prompt_id: str, variables: Dict[str, Any], version: str = None) -> str:
        """
        Render a prompt with variables.
        
        Args:
            prompt_id: Prompt ID
            variables: Variables to substitute
            version: Optional specific version
            
        Returns:
            Rendered prompt string
        """
        prompt = self.get_prompt(prompt_id, version)
        if not prompt:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        # Check for missing variables
        missing = set(prompt.variables) - set(variables.keys())
        if missing:
            logger.warning("Missing variables for prompt %s: %s", prompt_id, missing)
        
        result = prompt.template
        for var, value in variables.items():
            result = result.replace(f"{{{var}}}", str(value))
        
        return result
    
    def list_prompts(self, 
                    status: PromptStatus = None,
                    tags: List[str] = None) -> List[Dict[str, Any]]:
        """List all prompts with optional filtering."""
        results = []
        
        for prompt_id, versions in self.prompts.items():
            active_version = self.active_versions.get(prompt_id)
            
            for version, prompt in versions.items():
                # Apply filters
                if status and prompt.status != status:
                    continue
                
                if tags and not any(t in prompt.tags for t in tags):
                    continue
                
                results.append({
                    **prompt.to_dict(),
                    'is_active': version == active_version
                })
        
        return results
    
    def get_version_history(self, prompt_id: str) -> List[Dict[str, Any]]:
        """Get version history for a prompt."""
        if prompt_id not in self.prompts:
            return []
        
        versions = []
        for version, prompt in sorted(
            self.prompts[prompt_id].items(),
            key=lambda x: x[1].created_at
        ):
            versions.append({
                'version': version,
                'status': prompt.status.value,
                'created_at': prompt.created_at,
                'created_by': prompt.created_by,
                'content_hash': prompt.content_hash,
                'parent_version': prompt.parent_version,
                'changelog': prompt.metadata.get('changelog')
            })
        
        return versions
    
    def compare_versions(self, prompt_id: str, 
                        version1: str, version2: str) -> Dict[str, Any]:
        """Compare two versions of a prompt."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        v1 = self.prompts[prompt_id].get(version1)
        v2 = self.prompts[prompt_id].get(version2)
        
        if not v1 or not v2:
            raise ValueError("One or both versions not found")
        
        # Simple diff
        lines1 = v1.template.split('\n')
        lines2 = v2.template.split('\n')
        
        added = [l for l in lines2 if l not in lines1]
        removed = [l for l in lines1 if l not in lines2]
        
        return {
            'version1': version1,
            'version2': version2,
            'template_changed': v1.template != v2.template,
            'variables_changed': set(v1.variables) != set(v2.variables),
            'added_lines': added,
            'removed_lines': removed,
            'added_variables': list(set(v2.variables) - set(v1.variables)),
            'removed_variables': list(set(v1.variables) - set(v2.variables))
        }
    
    def _audit(self, action: str, prompt_id: str, version: str, 
              actor: str, details: Dict[str, Any]):
        """Add audit log entry."""
        entry = PromptAuditEntry(
            entry_id=str(uuid.uuid4()),
            prompt_id=prompt_id,
            version=version,
            action=action,
            actor=actor,
            timestamp=time.time(),
            details=details
        )
        
        self.audit_log.append(entry)
    
    def get_audit_log(self, prompt_id: str = None, 
                     limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit log entries."""
        entries = self.audit_log
        
        if prompt_id:
            entries = [e for e in entries if e.prompt_id == prompt_id]
        
        return [
            {
                'entry_id': e.entry_id,
                'prompt_id': e.prompt_id,
                'version': e.version,
                'action': e.action,
                'actor': e.actor,
                'timestamp': e.timestamp,
                'details': e.details
            }
            for e in entries[-limit:]
        ]
    
    def export_prompt(self, prompt_id: str, version: str = None) -> Dict[str, Any]:
        """Export prompt for sharing/backup."""
        prompt = self.get_prompt(prompt_id, version)
        if not prompt:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        return {
            'export_format': 'prompt_v1',
            'exported_at': time.time(),
            'prompt': prompt.to_dict(),
            'history': self.get_version_history(prompt_id)
        }
    
    def import_prompt(self, data: Dict[str, Any], 
                     created_by: str = "system") -> PromptVersion:
        """Import a prompt from exported data."""
        if data.get('export_format') != 'prompt_v1':
            raise ValueError("Unsupported export format")
        
        prompt_data = data['prompt']
        
        return self.create_prompt(
            name=prompt_data['name'],
            template=prompt_data['template'],
            variables=prompt_data['variables'],
            created_by=created_by,
            metadata=prompt_data.get('metadata', {}),
            tags=prompt_data.get('tags', [])
        )
    
    def save_to_storage(self):
        """Save prompts to storage."""
        if not self.storage_path:
            return
        
        path = Path(self.storage_path)
        path.mkdir(parents=True, exist_ok=True)
        
        data = {
            'prompts': {
                pid: {v: p.to_dict() for v, p in versions.items()}
                for pid, versions in self.prompts.items()
            },
            'active_versions': self.active_versions,
            'saved_at': time.time()
        }
        
        with open(path / 'prompts.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        logger.info("Saved prompts to %s", self.storage_path)
    
    def _load_from_storage(self):
        """Load prompts from storage."""
        if not self.storage_path:
            return
        
        path = Path(self.storage_path) / 'prompts.json'
        if not path.exists():
            return
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for pid, versions in data.get('prompts', {}).items():
            self.prompts[pid] = {}
            for v, pdata in versions.items():
                self.prompts[pid][v] = PromptVersion(
                    prompt_id=pdata['prompt_id'],
                    version=pdata['version'],
                    name=pdata['name'],
                    template=pdata['template'],
                    variables=pdata['variables'],
                    status=PromptStatus(pdata['status']),
                    created_at=pdata['created_at'],
                    created_by=pdata['created_by'],
                    metadata=pdata.get('metadata', {}),
                    parent_version=pdata.get('parent_version'),
                    tags=pdata.get('tags', [])
                )
        
        self.active_versions = data.get('active_versions', {})
        logger.info("Loaded prompts from %s", self.storage_path)


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


# Global instances
prompt_version_manager = PromptVersionManager()
prompt_library = PromptLibrary()
