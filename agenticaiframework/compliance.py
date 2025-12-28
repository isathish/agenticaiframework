"""
Compliance and Governance Module.

Features:
- Audit Trails
- Policy Enforcement
- Data Masking
- Compliance reporting
"""

import uuid
import time
import logging
import json
import re
import hashlib
import threading
from typing import Dict, Any, List, Optional, Callable, Pattern, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


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


class AuditTrailManager:
    """
    Comprehensive audit trail system.
    
    Features:
    - Event logging
    - Tamper-evident storage
    - Query and filtering
    - Compliance reporting
    - Event correlation
    """
    
    def __init__(self, storage_path: str = None):
        self.events: List[AuditEvent] = []
        self.storage_path = storage_path
        self.event_handlers: List[Callable[[AuditEvent], None]] = []
        self.retention_days: int = 365
        self._lock = threading.Lock()
        self._event_index: Dict[str, List[int]] = defaultdict(list)
        
        # Initialize hash chain for tamper evidence
        self._chain_hash: str = hashlib.sha256(b"genesis").hexdigest()
    
    def log(self,
           event_type: AuditEventType,
           actor: str,
           resource: str,
           action: str,
           details: Dict[str, Any] = None,
           outcome: str = "success",
           severity: AuditSeverity = AuditSeverity.INFO,
           **kwargs) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            actor: Who performed the action
            resource: What was acted upon
            action: What action was performed
            details: Additional details
            outcome: success/failure/denied
            severity: Event severity
        """
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            timestamp=time.time(),
            actor=actor,
            resource=resource,
            action=action,
            details=details or {},
            outcome=outcome,
            ip_address=kwargs.get('ip_address'),
            user_agent=kwargs.get('user_agent'),
            tenant_id=kwargs.get('tenant_id'),
            correlation_id=kwargs.get('correlation_id'),
            metadata=kwargs.get('metadata', {})
        )
        
        # Add to chain for tamper evidence
        event.metadata['chain_hash'] = self._update_chain(event)
        
        with self._lock:
            idx = len(self.events)
            self.events.append(event)
            
            # Index for fast lookups
            self._event_index[f"actor:{actor}"].append(idx)
            self._event_index[f"resource:{resource}"].append(idx)
            self._event_index[f"type:{event_type.value}"].append(idx)
            if event.tenant_id:
                self._event_index[f"tenant:{event.tenant_id}"].append(idx)
        
        # Notify handlers
        for handler in self.event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Audit handler failed: %s", e)
        
        logger.debug("Audit event: %s %s %s by %s - %s",
                    event_type.value, action, resource, actor, outcome)
        
        return event
    
    def _update_chain(self, event: AuditEvent) -> str:
        """Update hash chain for tamper evidence."""
        event_data = json.dumps({
            'event_id': event.event_id,
            'timestamp': event.timestamp,
            'actor': event.actor,
            'action': event.action,
            'previous_hash': self._chain_hash
        }, sort_keys=True)
        
        new_hash = hashlib.sha256(event_data.encode()).hexdigest()
        self._chain_hash = new_hash
        
        return new_hash
    
    def verify_integrity(self) -> Dict[str, Any]:
        """Verify audit trail integrity."""
        if not self.events:
            return {'valid': True, 'checked': 0}
        
        current_hash = hashlib.sha256(b"genesis").hexdigest()
        
        for i, event in enumerate(self.events):
            event_data = json.dumps({
                'event_id': event.event_id,
                'timestamp': event.timestamp,
                'actor': event.actor,
                'action': event.action,
                'previous_hash': current_hash
            }, sort_keys=True)
            
            expected_hash = hashlib.sha256(event_data.encode()).hexdigest()
            actual_hash = event.metadata.get('chain_hash')
            
            if expected_hash != actual_hash:
                return {
                    'valid': False,
                    'tampered_at_index': i,
                    'event_id': event.event_id,
                    'checked': i + 1
                }
            
            current_hash = expected_hash
        
        return {'valid': True, 'checked': len(self.events)}
    
    def query(self,
             actor: str = None,
             resource: str = None,
             event_type: AuditEventType = None,
             tenant_id: str = None,
             start_time: float = None,
             end_time: float = None,
             outcome: str = None,
             limit: int = 100) -> List[AuditEvent]:
        """
        Query audit events.
        
        Args:
            actor: Filter by actor
            resource: Filter by resource
            event_type: Filter by event type
            tenant_id: Filter by tenant
            start_time: Start of time range
            end_time: End of time range
            outcome: Filter by outcome
            limit: Maximum results
        """
        # Use index for initial filtering if possible
        candidate_indices = None
        
        if actor:
            candidate_indices = set(self._event_index.get(f"actor:{actor}", []))
        if resource:
            indices = set(self._event_index.get(f"resource:{resource}", []))
            candidate_indices = indices if candidate_indices is None else candidate_indices & indices
        if event_type:
            indices = set(self._event_index.get(f"type:{event_type.value}", []))
            candidate_indices = indices if candidate_indices is None else candidate_indices & indices
        if tenant_id:
            indices = set(self._event_index.get(f"tenant:{tenant_id}", []))
            candidate_indices = indices if candidate_indices is None else candidate_indices & indices
        
        # Filter events
        if candidate_indices is not None:
            events = [self.events[i] for i in sorted(candidate_indices)]
        else:
            events = self.events
        
        results = []
        for event in events:
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            if outcome and event.outcome != outcome:
                continue
            
            results.append(event)
            
            if len(results) >= limit:
                break
        
        return results
    
    def add_handler(self, handler: Callable[[AuditEvent], None]):
        """Add event handler."""
        self.event_handlers.append(handler)
    
    def generate_report(self,
                       start_time: float,
                       end_time: float,
                       tenant_id: str = None) -> Dict[str, Any]:
        """Generate compliance report."""
        events = self.query(
            tenant_id=tenant_id,
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )
        
        report = {
            'report_id': str(uuid.uuid4()),
            'generated_at': time.time(),
            'period': {
                'start': datetime.fromtimestamp(start_time).isoformat(),
                'end': datetime.fromtimestamp(end_time).isoformat()
            },
            'tenant_id': tenant_id,
            'total_events': len(events),
            'by_type': defaultdict(int),
            'by_outcome': defaultdict(int),
            'by_severity': defaultdict(int),
            'by_actor': defaultdict(int),
            'security_events': [],
            'failed_actions': [],
            'integrity_check': self.verify_integrity()
        }
        
        for event in events:
            report['by_type'][event.event_type.value] += 1
            report['by_outcome'][event.outcome] += 1
            report['by_severity'][event.severity.value] += 1
            report['by_actor'][event.actor] += 1
            
            if event.event_type == AuditEventType.SECURITY_EVENT:
                report['security_events'].append(event.to_dict())
            
            if event.outcome in ['failure', 'denied']:
                report['failed_actions'].append(event.to_dict())
        
        # Convert defaultdicts
        report['by_type'] = dict(report['by_type'])
        report['by_outcome'] = dict(report['by_outcome'])
        report['by_severity'] = dict(report['by_severity'])
        report['by_actor'] = dict(report['by_actor'])
        
        return report
    
    def export(self, filepath: str, format: str = "json"):
        """Export audit trail."""
        events_data = [e.to_dict() for e in self.events]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            if format == "json":
                json.dump(events_data, f, indent=2)
            elif format == "jsonl":
                for event in events_data:
                    f.write(json.dumps(event) + '\n')
        
        logger.info("Exported %d audit events to %s", len(events_data), filepath)


class PolicyType(Enum):
    """Types of policies."""
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE = "require"
    AUDIT = "audit"


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


class PolicyEngine:
    """
    Policy enforcement engine.
    
    Features:
    - Rule-based policies
    - Pattern matching
    - Conditional evaluation
    - Policy composition
    """
    
    def __init__(self, audit_manager: AuditTrailManager = None):
        self.policies: Dict[str, Policy] = {}
        self.audit_manager = audit_manager
        self._compiled_patterns: Dict[str, Tuple[Pattern, Pattern]] = {}
        self._lock = threading.Lock()
    
    def add_policy(self, policy: Policy):
        """Add a policy."""
        with self._lock:
            self.policies[policy.policy_id] = policy
            
            # Compile patterns
            self._compiled_patterns[policy.policy_id] = (
                re.compile(policy.resource_pattern),
                re.compile(policy.action_pattern)
            )
        
        logger.info("Added policy: %s (%s)", policy.name, policy.policy_type.value)
    
    def remove_policy(self, policy_id: str):
        """Remove a policy."""
        with self._lock:
            if policy_id in self.policies:
                del self.policies[policy_id]
                del self._compiled_patterns[policy_id]
    
    def evaluate(self,
                resource: str,
                action: str,
                context: Dict[str, Any] = None,
                actor: str = None) -> Dict[str, Any]:
        """
        Evaluate policies for a resource/action.
        
        Returns:
            Decision with allowed/denied and reason
        """
        context = context or {}
        matching_policies = []
        
        # Find matching policies
        for policy_id, policy in self.policies.items():
            if not policy.enabled:
                continue
            
            resource_pattern, action_pattern = self._compiled_patterns[policy_id]
            
            if resource_pattern.match(resource) and action_pattern.match(action):
                # Check conditions
                if self._evaluate_conditions(policy.conditions, context):
                    matching_policies.append(policy)
        
        # Sort by priority
        matching_policies.sort(key=lambda p: p.priority, reverse=True)
        
        result = {
            'allowed': True,
            'reason': None,
            'matched_policies': [],
            'requires': []
        }
        
        for policy in matching_policies:
            result['matched_policies'].append({
                'policy_id': policy.policy_id,
                'name': policy.name,
                'type': policy.policy_type.value
            })
            
            if policy.policy_type == PolicyType.DENY:
                result['allowed'] = False
                result['reason'] = f"Denied by policy: {policy.name}"
                break
            
            elif policy.policy_type == PolicyType.REQUIRE:
                requirement = policy.conditions.get('requirement')
                if requirement and not context.get(requirement):
                    result['requires'].append(requirement)
            
            elif policy.policy_type == PolicyType.AUDIT:
                if self.audit_manager:
                    self.audit_manager.log(
                        event_type=AuditEventType.ACCESS,
                        actor=actor or 'unknown',
                        resource=resource,
                        action=action,
                        details={'policy': policy.name, 'context': context},
                        severity=AuditSeverity.INFO
                    )
        
        # Check requirements
        if result['requires']:
            result['allowed'] = False
            result['reason'] = f"Requirements not met: {result['requires']}"
        
        return result
    
    def _evaluate_conditions(self, 
                            conditions: Dict[str, Any],
                            context: Dict[str, Any]) -> bool:
        """Evaluate policy conditions."""
        for key, expected in conditions.items():
            if key == 'requirement':
                continue  # Handled separately
            
            if key.startswith('context.'):
                context_key = key[8:]
                actual = context.get(context_key)
            else:
                actual = context.get(key)
            
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        
        return True
    
    def create_allow_policy(self,
                           name: str,
                           resource_pattern: str,
                           action_pattern: str,
                           conditions: Dict[str, Any] = None,
                           priority: int = 100) -> Policy:
        """Create an allow policy."""
        policy = Policy(
            policy_id=str(uuid.uuid4()),
            name=name,
            description=f"Allow {action_pattern} on {resource_pattern}",
            policy_type=PolicyType.ALLOW,
            resource_pattern=resource_pattern,
            action_pattern=action_pattern,
            conditions=conditions or {},
            priority=priority,
            enabled=True,
            created_at=time.time()
        )
        
        self.add_policy(policy)
        return policy
    
    def create_deny_policy(self,
                          name: str,
                          resource_pattern: str,
                          action_pattern: str,
                          conditions: Dict[str, Any] = None,
                          priority: int = 200) -> Policy:
        """Create a deny policy."""
        policy = Policy(
            policy_id=str(uuid.uuid4()),
            name=name,
            description=f"Deny {action_pattern} on {resource_pattern}",
            policy_type=PolicyType.DENY,
            resource_pattern=resource_pattern,
            action_pattern=action_pattern,
            conditions=conditions or {},
            priority=priority,
            enabled=True,
            created_at=time.time()
        )
        
        self.add_policy(policy)
        return policy
    
    def list_policies(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """List all policies."""
        policies = list(self.policies.values())
        
        if enabled_only:
            policies = [p for p in policies if p.enabled]
        
        return [
            {
                'policy_id': p.policy_id,
                'name': p.name,
                'type': p.policy_type.value,
                'resource_pattern': p.resource_pattern,
                'action_pattern': p.action_pattern,
                'priority': p.priority,
                'enabled': p.enabled
            }
            for p in sorted(policies, key=lambda x: x.priority, reverse=True)
        ]


class MaskingType(Enum):
    """Types of data masking."""
    FULL = "full"  # Replace entirely
    PARTIAL = "partial"  # Mask part of value
    HASH = "hash"  # One-way hash
    TOKENIZE = "tokenize"  # Replace with token
    ENCRYPT = "encrypt"  # Reversible encryption
    REDACT = "redact"  # Remove entirely


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


class DataMaskingEngine:
    """
    Data masking and PII protection engine.
    
    Features:
    - Pattern-based detection
    - Multiple masking strategies
    - Tokenization
    - Audit integration
    """
    
    def __init__(self, audit_manager: AuditTrailManager = None):
        self.rules: Dict[str, MaskingRule] = {}
        self.audit_manager = audit_manager
        self._compiled_rules: Dict[str, Pattern] = {}
        self._token_map: Dict[str, str] = {}
        self._reverse_token_map: Dict[str, str] = {}
        self._lock = threading.Lock()
        
        # Add default rules
        self._add_default_rules()
    
    def _add_default_rules(self):
        """Add default PII detection rules."""
        default_rules = [
            MaskingRule(
                rule_id="email",
                name="Email Address",
                pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                data_type="email",
                masking_type=MaskingType.PARTIAL,
                visible_chars=3
            ),
            MaskingRule(
                rule_id="ssn",
                name="Social Security Number",
                pattern=r'\b\d{3}-\d{2}-\d{4}\b',
                data_type="ssn",
                masking_type=MaskingType.PARTIAL,
                visible_chars=4
            ),
            MaskingRule(
                rule_id="credit_card",
                name="Credit Card Number",
                pattern=r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
                data_type="credit_card",
                masking_type=MaskingType.PARTIAL,
                visible_chars=4
            ),
            MaskingRule(
                rule_id="phone",
                name="Phone Number",
                pattern=r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
                data_type="phone",
                masking_type=MaskingType.PARTIAL,
                visible_chars=4
            ),
            MaskingRule(
                rule_id="api_key",
                name="API Key",
                pattern=r'\b(?:sk|pk|api)[-_][A-Za-z0-9]{20,}\b',
                data_type="api_key",
                masking_type=MaskingType.FULL,
                replacement="[REDACTED_API_KEY]"
            )
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    def add_rule(self, rule: MaskingRule):
        """Add a masking rule."""
        with self._lock:
            self.rules[rule.rule_id] = rule
            self._compiled_rules[rule.rule_id] = re.compile(rule.pattern, re.IGNORECASE)
        
        logger.info("Added masking rule: %s", rule.name)
    
    def remove_rule(self, rule_id: str):
        """Remove a masking rule."""
        with self._lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                del self._compiled_rules[rule_id]
    
    def mask(self, 
            text: str,
            rules: List[str] = None,
            actor: str = None) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Mask sensitive data in text.
        
        Args:
            text: Text to mask
            rules: Specific rules to apply (None = all)
            actor: Who requested masking (for audit)
            
        Returns:
            Tuple of (masked_text, list of detections)
        """
        detections = []
        masked_text = text
        
        rules_to_apply = self.rules.values() if rules is None else [
            self.rules[r] for r in rules if r in self.rules
        ]
        
        for rule in rules_to_apply:
            if not rule.enabled:
                continue
            
            pattern = self._compiled_rules[rule.rule_id]
            matches = pattern.finditer(masked_text)
            
            for match in matches:
                original = match.group()
                masked = self._apply_masking(original, rule)
                
                detections.append({
                    'rule_id': rule.rule_id,
                    'data_type': rule.data_type,
                    'position': match.start(),
                    'original_length': len(original),
                    'masked': masked != original
                })
                
                masked_text = masked_text.replace(original, masked, 1)
        
        # Audit if requested
        if self.audit_manager and detections:
            self.audit_manager.log(
                event_type=AuditEventType.DATA_ACCESS,
                actor=actor or 'system',
                resource='data_masking',
                action='mask',
                details={
                    'detections': len(detections),
                    'data_types': list(set(d['data_type'] for d in detections))
                },
                severity=AuditSeverity.INFO
            )
        
        return masked_text, detections
    
    def _apply_masking(self, value: str, rule: MaskingRule) -> str:
        """Apply masking to a value."""
        if rule.masking_type == MaskingType.FULL:
            return rule.replacement or "[REDACTED]"
        
        elif rule.masking_type == MaskingType.PARTIAL:
            visible = rule.visible_chars
            if len(value) <= visible:
                return '*' * len(value)
            return '*' * (len(value) - visible) + value[-visible:]
        
        elif rule.masking_type == MaskingType.HASH:
            return hashlib.sha256(value.encode()).hexdigest()[:16]
        
        elif rule.masking_type == MaskingType.TOKENIZE:
            return self._tokenize(value)
        
        elif rule.masking_type == MaskingType.REDACT:
            return ""
        
        return value
    
    def _tokenize(self, value: str) -> str:
        """Replace value with reversible token."""
        if value in self._token_map:
            return self._token_map[value]
        
        token = f"TOKEN_{uuid.uuid4().hex[:12]}"
        
        with self._lock:
            self._token_map[value] = token
            self._reverse_token_map[token] = value
        
        return token
    
    def detokenize(self, token: str, actor: str = None) -> Optional[str]:
        """Reverse tokenization (requires authorization)."""
        original = self._reverse_token_map.get(token)
        
        if self.audit_manager and original:
            self.audit_manager.log(
                event_type=AuditEventType.DATA_ACCESS,
                actor=actor or 'system',
                resource='data_masking',
                action='detokenize',
                details={'token': token},
                severity=AuditSeverity.WARNING
            )
        
        return original
    
    def detect_pii(self, text: str) -> List[Dict[str, Any]]:
        """Detect PII without masking."""
        detections = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            pattern = self._compiled_rules[rule.rule_id]
            matches = pattern.finditer(text)
            
            for match in matches:
                detections.append({
                    'rule_id': rule.rule_id,
                    'data_type': rule.data_type,
                    'start': match.start(),
                    'end': match.end(),
                    'value': '*' * len(match.group())  # Don't expose actual value
                })
        
        return detections
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all masking rules."""
        return [
            {
                'rule_id': r.rule_id,
                'name': r.name,
                'data_type': r.data_type,
                'masking_type': r.masking_type.value,
                'enabled': r.enabled
            }
            for r in self.rules.values()
        ]


# Global instances
audit_trail = AuditTrailManager()
policy_engine = PolicyEngine(audit_trail)
data_masking = DataMaskingEngine(audit_trail)


# Convenience decorators
def audit_action(event_type: AuditEventType = AuditEventType.EXECUTE,
                resource: str = None):
    """Decorator to audit function calls."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            func_resource = resource or f"{func.__module__}.{func.__name__}"
            
            audit_trail.log(
                event_type=event_type,
                actor=kwargs.get('actor', 'system'),
                resource=func_resource,
                action=func.__name__,
                details={'args_count': len(args), 'kwargs_keys': list(kwargs.keys())},
                outcome='started'
            )
            
            try:
                result = func(*args, **kwargs)
                
                audit_trail.log(
                    event_type=event_type,
                    actor=kwargs.get('actor', 'system'),
                    resource=func_resource,
                    action=func.__name__,
                    details={},
                    outcome='success'
                )
                
                return result
            except Exception as e:
                audit_trail.log(
                    event_type=event_type,
                    actor=kwargs.get('actor', 'system'),
                    resource=func_resource,
                    action=func.__name__,
                    details={'error': str(e)},
                    outcome='failure',
                    severity=AuditSeverity.ERROR
                )
                raise
        
        return wrapper
    return decorator


def enforce_policy(resource: str, action: str):
    """Decorator to enforce policies."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            context = kwargs.get('policy_context', {})
            actor = kwargs.get('actor', 'system')
            
            result = policy_engine.evaluate(resource, action, context, actor)
            
            if not result['allowed']:
                raise PermissionError(f"Policy denied: {result['reason']}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def mask_output(rules: List[str] = None):
    """Decorator to mask sensitive data in function output."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            if isinstance(result, str):
                masked, _ = data_masking.mask(result, rules)
                return masked
            
            return result
        
        return wrapper
    return decorator
