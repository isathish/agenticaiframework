"""
Policy Engine.

Rule-based policy enforcement with:
- Pattern matching
- Conditional evaluation
- Policy composition
"""

import uuid
import time
import logging
import re
import threading
from typing import Dict, Any, List, Tuple, Pattern

from .types import Policy, PolicyType, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Policy enforcement engine.
    
    Features:
    - Rule-based policies
    - Pattern matching
    - Conditional evaluation
    - Policy composition
    """
    
    def __init__(self, audit_manager=None):
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


__all__ = ['PolicyEngine']
