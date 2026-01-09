"""
Compliance Types Module.

Contains all enums and dataclasses for the compliance package.
"""

import uuid
import time
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum


class AuditEventType(Enum):
    """Types of audit events."""
    ACCESS = "access"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    LOGIN = "login"
    LOGOUT = "logout"
    PERMISSION_CHANGE = "permission_change"
    CONFIG_CHANGE = "config_change"
    SECURITY_EVENT = "security_event"
    DATA_ACCESS = "data_access"
    EXPORT = "export"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PolicyType(Enum):
    """Types of policies."""
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE = "require"
    AUDIT = "audit"


class MaskingType(Enum):
    """Types of data masking."""
    FULL = "full"  # Replace entirely
    PARTIAL = "partial"  # Mask part of value
    HASH = "hash"  # One-way hash
    TOKENIZE = "tokenize"  # Replace with token
    ENCRYPT = "encrypt"  # Reversible encryption
    REDACT = "redact"  # Remove entirely


@dataclass
class AuditEvent:
    """Represents an audit trail event."""
    event_id: str
    event_type: AuditEventType
    severity: AuditSeverity
    timestamp: float
    actor: str
    resource: str
    action: str
    details: Dict[str, Any]
    outcome: str  # success, failure, denied
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    tenant_id: Optional[str] = None
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'severity': self.severity.value,
            'timestamp': self.timestamp,
            'timestamp_iso': datetime.fromtimestamp(self.timestamp).isoformat(),
            'actor': self.actor,
            'resource': self.resource,
            'action': self.action,
            'details': self.details,
            'outcome': self.outcome,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'tenant_id': self.tenant_id,
            'correlation_id': self.correlation_id,
            'metadata': self.metadata
        }


@dataclass
class Policy:
    """Represents a policy rule."""
    policy_id: str
    name: str
    description: str
    policy_type: PolicyType
    resource_pattern: str  # Regex pattern
    action_pattern: str  # Regex pattern
    conditions: Dict[str, Any]
    priority: int
    enabled: bool
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MaskingRule:
    """Data masking rule."""
    rule_id: str
    name: str
    pattern: str  # Regex pattern to match
    data_type: str  # email, ssn, phone, credit_card, custom
    masking_type: MaskingType
    replacement: Optional[str] = None  # For FULL type
    visible_chars: int = 4  # For PARTIAL type
    enabled: bool = True


__all__ = [
    'AuditEventType',
    'AuditSeverity',
    'AuditEvent',
    'PolicyType',
    'Policy',
    'MaskingType',
    'MaskingRule'
]
