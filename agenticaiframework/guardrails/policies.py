"""
Agent Policy Framework.

Provides:
- PolicyScope: Scope of policy application
- PolicyEnforcement: Enforcement levels
- AgentPolicy: Policy definition
- BehaviorPolicy: Agent behavior constraints
- ResourcePolicy: Resource access control
- SafetyPolicy: Critical safety constraints
- AgentPolicyManager: Centralized policy management
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .content_safety import ContentSafetyGuardrail

logger = logging.getLogger(__name__)


class PolicyScope(Enum):
    """Scope of agent policy application."""
    GLOBAL = "global"
    AGENT_TYPE = "agent_type"
    AGENT = "agent"
    TASK = "task"
    TOOL = "tool"
    RESOURCE = "resource"


class PolicyEnforcement(Enum):
    """How strictly policy is enforced."""
    STRICT = "strict"
    ADVISORY = "advisory"
    AUDIT = "audit"
    DISABLED = "disabled"


@dataclass
class AgentPolicy:
    """Policy definition for agent behavior control."""
    policy_id: str
    name: str
    description: str
    scope: PolicyScope
    enforcement: PolicyEnforcement
    priority: int = 100
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Policy rules
    allowed_actions: List[str] = field(default_factory=list)
    blocked_actions: List[str] = field(default_factory=list)
    allowed_resources: List[str] = field(default_factory=list)
    blocked_resources: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    blocked_tools: List[str] = field(default_factory=list)
    
    # Constraints
    max_tokens_per_request: Optional[int] = None
    max_cost_per_request: Optional[float] = None
    max_execution_time: Optional[float] = None
    max_tool_calls_per_request: Optional[int] = None
    require_human_approval: bool = False
    
    # Conditions
    conditions: Dict[str, Any] = field(default_factory=dict)


class BehaviorPolicy:
    """Policy for controlling agent behavior patterns."""
    
    def __init__(self,
                 require_explanation: bool = False,
                 max_response_length: Optional[int] = None,
                 required_output_format: Optional[str] = None,
                 allow_assumptions: bool = True,
                 require_source_citation: bool = False,
                 confidence_threshold: float = 0.0,
                 enable_self_correction: bool = True):
        self.require_explanation = require_explanation
        self.max_response_length = max_response_length
        self.required_output_format = required_output_format
        self.allow_assumptions = allow_assumptions
        self.require_source_citation = require_source_citation
        self.confidence_threshold = confidence_threshold
        self.enable_self_correction = enable_self_correction
    
    def validate_response(self, response: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate response against policy."""
        metadata = metadata or {}
        violations = []
        
        if self.max_response_length and len(response) > self.max_response_length:
            violations.append(
                f"Response exceeds max length: {len(response)} > {self.max_response_length}"
            )
        
        if self.required_output_format == 'json':
            try:
                json.loads(response)
            except json.JSONDecodeError:
                violations.append("Response is not valid JSON")
        
        if self.require_explanation:
            explanation_markers = ['because', 'since', 'therefore', 'reason', 'explain']
            has_explanation = any(marker in response.lower() for marker in explanation_markers)
            if not has_explanation:
                violations.append("Response lacks required explanation")
        
        if self.require_source_citation:
            citation_patterns = [r'\[source\]', r'\[ref\]', r'according to', r'source:']
            has_citation = any(re.search(p, response, re.IGNORECASE) for p in citation_patterns)
            if not has_citation:
                violations.append("Response lacks required source citation")
        
        confidence = metadata.get('confidence', 1.0)
        if confidence < self.confidence_threshold:
            violations.append(
                f"Response confidence below threshold: {confidence} < {self.confidence_threshold}"
            )
        
        return {'is_valid': len(violations) == 0, 'violations': violations}


class ResourcePolicy:
    """Policy for resource access control."""
    
    def __init__(self):
        self.resource_rules: Dict[str, Dict[str, Any]] = {}
        self._access_log: List[Dict[str, Any]] = []
    
    def add_rule(self,
                 resource_pattern: str,
                 allowed_actions: List[str] = None,
                 blocked_actions: List[str] = None,
                 rate_limit: Optional[int] = None,
                 require_auth: bool = False,
                 conditions: Optional[Dict] = None):
        """Add a resource access rule."""
        self.resource_rules[resource_pattern] = {
            'allowed_actions': allowed_actions or ['*'],
            'blocked_actions': blocked_actions or [],
            'rate_limit': rate_limit,
            'require_auth': require_auth,
            'conditions': conditions or {},
            'access_count': 0
        }
    
    def check_access(self, resource: str, action: str,
                    context: Optional[Dict] = None) -> Dict[str, Any]:
        """Check if access is allowed."""
        context = context or {}
        
        for pattern, rule in self.resource_rules.items():
            if re.match(pattern, resource):
                if action in rule['blocked_actions']:
                    return {'allowed': False, 'reason': f"Action '{action}' blocked for '{resource}'"}
                
                if '*' not in rule['allowed_actions'] and action not in rule['allowed_actions']:
                    return {'allowed': False, 'reason': f"Action '{action}' not allowed for '{resource}'"}
                
                if rule['require_auth'] and not context.get('authenticated'):
                    return {'allowed': False, 'reason': f"Authentication required for '{resource}'"}
                
                if rule['rate_limit'] and rule['access_count'] >= rule['rate_limit']:
                    return {'allowed': False, 'reason': f"Rate limit exceeded for '{resource}'"}
                
                rule['access_count'] += 1
                self._access_log.append({
                    'resource': resource,
                    'action': action,
                    'timestamp': datetime.now().isoformat()
                })
                return {'allowed': True, 'reason': None}
        
        return {'allowed': True, 'reason': None}


class SafetyPolicy:
    """Safety policy for critical safety constraints."""
    
    def __init__(self,
                 block_harmful_content: bool = True,
                 block_pii_output: bool = True,
                 require_safe_actions: bool = True,
                 enable_ethical_guidelines: bool = True):
        self.block_harmful_content = block_harmful_content
        self.block_pii_output = block_pii_output
        self.require_safe_actions = require_safe_actions
        self.enable_ethical_guidelines = enable_ethical_guidelines
        
        self.content_safety = ContentSafetyGuardrail()
        
        self._dangerous_patterns = [
            r'delete\s+all', r'drop\s+table', r'rm\s+-rf',
            r'format\s+\w:', r'shutdown', r'sudo\s+rm',
        ]
        self._compiled_dangerous = [
            re.compile(p, re.IGNORECASE) for p in self._dangerous_patterns
        ]
    
    def check_output_safety(self, output: str) -> Dict[str, Any]:
        """Check output for safety violations."""
        violations = []
        
        if self.block_harmful_content:
            safety_result = self.content_safety.check(output)
            if not safety_result['is_safe']:
                violations.extend(safety_result['violations'])
        
        if self.block_pii_output:
            pii_patterns = [
                (r'\b\d{3}-\d{2}-\d{4}\b', 'SSN'),
                (r'\b\d{16}\b', 'Credit Card'),
                (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'Email'),
            ]
            for pattern, pii_type in pii_patterns:
                if re.search(pattern, output):
                    violations.append({
                        'category': 'pii_exposure',
                        'type': pii_type,
                        'message': f"Output may contain {pii_type}"
                    })
        
        return {'is_safe': len(violations) == 0, 'violations': violations}
    
    def check_action_safety(self, action: str) -> Dict[str, Any]:
        """Check if action is safe to execute."""
        violations = []
        
        if self.require_safe_actions:
            for pattern in self._compiled_dangerous:
                if pattern.search(action):
                    violations.append({
                        'category': 'dangerous_action',
                        'pattern': pattern.pattern,
                        'message': "Action matches dangerous pattern"
                    })
        
        return {'is_safe': len(violations) == 0, 'violations': violations}


class AgentPolicyManager:
    """Centralized manager for agent policies."""
    
    def __init__(self):
        self.policies: Dict[str, AgentPolicy] = {}
        self.behavior_policies: Dict[str, BehaviorPolicy] = {}
        self.resource_policies: Dict[str, ResourcePolicy] = {}
        self.safety_policies: Dict[str, SafetyPolicy] = {}
        self.policy_audit_log: List[Dict[str, Any]] = []
    
    def register_policy(self, policy: AgentPolicy):
        """Register an agent policy."""
        self.policies[policy.policy_id] = policy
        logger.info("Registered policy: %s", policy.name)
    
    def register_behavior_policy(self, name: str, policy: BehaviorPolicy):
        """Register a behavior policy."""
        self.behavior_policies[name] = policy
    
    def register_resource_policy(self, name: str, policy: ResourcePolicy):
        """Register a resource policy."""
        self.resource_policies[name] = policy
    
    def register_safety_policy(self, name: str, policy: SafetyPolicy):
        """Register a safety policy."""
        self.safety_policies[name] = policy
    
    def evaluate_policies(self, agent_id: str, action: str,
                         resource: Optional[str] = None,
                         context: Optional[Dict] = None) -> Dict[str, Any]:
        """Evaluate all applicable policies for an action."""
        context = context or {}
        results = {
            'allowed': True,
            'reasons': [],
            'policies_evaluated': [],
            'enforcement_level': PolicyEnforcement.ADVISORY
        }
        
        applicable = [
            p for p in self.policies.values()
            if p.enabled and self._policy_applies(p, agent_id, action, resource, context)
        ]
        applicable.sort(key=lambda p: p.priority, reverse=True)
        
        for policy in applicable:
            results['policies_evaluated'].append(policy.name)
            
            if action in policy.blocked_actions:
                if policy.enforcement == PolicyEnforcement.STRICT:
                    results['allowed'] = False
                    results['reasons'].append(f"Action blocked by: {policy.name}")
                    results['enforcement_level'] = PolicyEnforcement.STRICT
                elif policy.enforcement == PolicyEnforcement.ADVISORY:
                    results['reasons'].append(f"Advisory: Not recommended by {policy.name}")
            
            if resource and resource in policy.blocked_resources:
                if policy.enforcement == PolicyEnforcement.STRICT:
                    results['allowed'] = False
                    results['reasons'].append(f"Resource blocked by: {policy.name}")
            
            if policy.require_human_approval:
                results['require_human_approval'] = True
        
        self.policy_audit_log.append({
            'agent_id': agent_id,
            'action': action,
            'resource': resource,
            'result': results,
            'timestamp': datetime.now().isoformat()
        })
        
        return results
    
    def _policy_applies(self, policy: AgentPolicy, _agent_id: str,
                       action: str, resource: Optional[str],
                       context: Dict) -> bool:
        """Check if policy applies to the given context."""
        if policy.scope == PolicyScope.GLOBAL:
            return True
        if policy.scope == PolicyScope.AGENT:
            return context.get('agent_id') == policy.metadata.get('target_agent')
        if policy.scope == PolicyScope.TASK:
            return context.get('task_type') in policy.metadata.get('target_tasks', [])
        if policy.scope == PolicyScope.TOOL:
            return action in policy.metadata.get('target_tools', [])
        if policy.scope == PolicyScope.RESOURCE:
            return resource and any(
                re.match(pattern, resource)
                for pattern in policy.metadata.get('resource_patterns', [])
            )
        return True
    
    def get_policy_summary(self) -> Dict[str, Any]:
        """Get summary of all policies."""
        return {
            'total_policies': len(self.policies),
            'enabled_policies': sum(1 for p in self.policies.values() if p.enabled),
            'behavior_policies': len(self.behavior_policies),
            'resource_policies': len(self.resource_policies),
            'safety_policies': len(self.safety_policies),
            'audit_log_size': len(self.policy_audit_log),
            'policies_by_scope': {
                scope.value: sum(1 for p in self.policies.values() if p.scope == scope)
                for scope in PolicyScope
            }
        }


__all__ = [
    'PolicyScope',
    'PolicyEnforcement',
    'AgentPolicy',
    'BehaviorPolicy',
    'ResourcePolicy',
    'SafetyPolicy',
    'AgentPolicyManager',
]
