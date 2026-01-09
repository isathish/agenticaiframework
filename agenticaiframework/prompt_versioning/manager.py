"""
Prompt Version Manager.

Manages versioned prompts with full lifecycle support:
- Semantic versioning (major.minor.patch)
- Draft -> Active -> Deprecated workflow
- Rollback support
- Audit logging
"""

import uuid
import time
import json
import logging
import re
import threading
from typing import Dict, Any, List, Optional
from pathlib import Path

from .types import PromptStatus, PromptVersion, PromptAuditEntry

logger = logging.getLogger(__name__)


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
        self.prompts: Dict[str, Dict[str, PromptVersion]] = {}
        self.active_versions: Dict[str, str] = {}
        self.audit_log: List[PromptAuditEntry] = []
        self.storage_path = storage_path
        
        self._lock = threading.Lock()
        
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
        
        if variables is None:
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
        """Create a new version of an existing prompt."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        versions = sorted(self.prompts[prompt_id].keys(), 
                         key=lambda v: [int(x) for x in v.split('.')])
        latest = versions[-1]
        latest_version = self.prompts[prompt_id][latest]
        
        major, minor, patch = [int(x) for x in latest.split('.')]
        
        if version_bump == "major":
            new_version = f"{major + 1}.0.0"
        elif version_bump == "minor":
            new_version = f"{major}.{minor + 1}.0"
        else:
            new_version = f"{major}.{minor}.{patch + 1}"
        
        if variables is None:
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
        """Activate a prompt version (make it the default)."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        if version not in self.prompts[prompt_id]:
            raise ValueError(f"Version '{version}' not found")
        
        with self._lock:
            if prompt_id in self.active_versions:
                old_version = self.active_versions[prompt_id]
                if old_version in self.prompts[prompt_id]:
                    self.prompts[prompt_id][old_version].status = PromptStatus.DEPRECATED
            
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
        """Rollback to a previous version."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        if target_version not in self.prompts[prompt_id]:
            raise ValueError(f"Version '{target_version}' not found")
        
        target = self.prompts[prompt_id][target_version]
        
        new_version = self.create_version(
            prompt_id=prompt_id,
            template=target.template,
            version_bump="patch",
            created_by=rolled_back_by,
            changelog=f"Rollback to version {target_version}",
            variables=target.variables.copy()
        )
        
        self.activate(prompt_id, new_version.version, rolled_back_by)
        
        self._audit("rollback", prompt_id, new_version.version, rolled_back_by, {
            'rolled_back_from': self.active_versions.get(prompt_id),
            'rolled_back_to': target_version
        })
        
        logger.info("Rolled back prompt %s to version %s (new: %s)", 
                   prompt_id, target_version, new_version.version)
        
        return new_version
    
    def get_prompt(self, prompt_id: str, version: str = None) -> Optional[PromptVersion]:
        """Get a prompt version."""
        if prompt_id not in self.prompts:
            return None
        
        if version is None:
            version = self.active_versions.get(prompt_id)
            if version is None:
                versions = sorted(self.prompts[prompt_id].keys(),
                                key=lambda v: [int(x) for x in v.split('.')])
                version = versions[-1] if versions else None
        
        return self.prompts[prompt_id].get(version)
    
    def render(self, prompt_id: str, variables: Dict[str, Any], version: str = None) -> str:
        """Render a prompt with variables."""
        prompt = self.get_prompt(prompt_id, version)
        if not prompt:
            raise ValueError(f"Prompt '{prompt_id}' not found")
        
        missing = set(prompt.variables) - set(variables.keys())
        if missing:
            logger.warning("Missing variables for prompt %s: %s", prompt_id, missing)
        
        result = prompt.template
        for var, value in variables.items():
            result = result.replace(f"{{{var}}}", str(value))
        
        return result
    
    def list_prompts(self, status: PromptStatus = None, 
                    tags: List[str] = None) -> List[Dict[str, Any]]:
        """List all prompts with optional filtering."""
        results = []
        
        for prompt_id, versions in self.prompts.items():
            active_version = self.active_versions.get(prompt_id)
            
            for version, prompt in versions.items():
                if status and prompt.status != status:
                    continue
                
                if tags and not any(t in prompt.tags for t in tags):
                    continue
                
                results.append({
                    **prompt.to_dict(),
                    'is_active': version == active_version
                })
        
        return results
    
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


__all__ = ['PromptVersionManager']
