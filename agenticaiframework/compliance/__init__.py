"""
Compliance and Governance Package.

Features:
- Audit Trails (AuditTrailManager)
- Policy Enforcement (PolicyEngine)
- Data Masking (DataMaskingEngine)
- Compliance reporting
"""

# Types and data models
from .types import (
    AuditEventType,
    AuditSeverity,
    AuditEvent,
    PolicyType,
    Policy,
    MaskingType,
    MaskingRule
)

# Core classes
from .audit import AuditTrailManager
from .policy import PolicyEngine
from .masking import DataMaskingEngine

# Decorators
from .decorators import (
    audit_action,
    enforce_policy,
    mask_output
)

# Global instances
audit_trail = AuditTrailManager()
policy_engine = PolicyEngine(audit_trail)
data_masking = DataMaskingEngine(audit_trail)


__all__ = [
    # Types
    'AuditEventType',
    'AuditSeverity',
    'AuditEvent',
    'PolicyType',
    'Policy',
    'MaskingType',
    'MaskingRule',
    # Classes
    'AuditTrailManager',
    'PolicyEngine',
    'DataMaskingEngine',
    # Decorators
    'audit_action',
    'enforce_policy',
    'mask_output',
    # Global instances
    'audit_trail',
    'policy_engine',
    'data_masking'
]
