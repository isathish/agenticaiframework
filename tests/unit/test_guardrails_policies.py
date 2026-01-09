"""
Tests for guardrails/policies.py - Agent Policy Framework.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from agenticaiframework.guardrails.policies import (
    PolicyScope,
    PolicyEnforcement,
    AgentPolicy,
    BehaviorPolicy,
    ResourcePolicy,
    SafetyPolicy,
    AgentPolicyManager,
)


class TestPolicyScope:
    """Tests for PolicyScope enum."""
    
    def test_scope_values(self):
        """Test all scope values exist."""
        assert PolicyScope.GLOBAL.value == "global"
        assert PolicyScope.AGENT_TYPE.value == "agent_type"
        assert PolicyScope.AGENT.value == "agent"
        assert PolicyScope.TASK.value == "task"
        assert PolicyScope.TOOL.value == "tool"
        assert PolicyScope.RESOURCE.value == "resource"


class TestPolicyEnforcement:
    """Tests for PolicyEnforcement enum."""
    
    def test_enforcement_values(self):
        """Test all enforcement levels exist."""
        assert PolicyEnforcement.STRICT.value == "strict"
        assert PolicyEnforcement.ADVISORY.value == "advisory"
        assert PolicyEnforcement.AUDIT.value == "audit"
        assert PolicyEnforcement.DISABLED.value == "disabled"


class TestAgentPolicy:
    """Tests for AgentPolicy dataclass."""
    
    def test_create_policy(self):
        """Test creating an agent policy."""
        policy = AgentPolicy(
            policy_id="policy-1",
            name="Test Policy",
            description="A test policy",
            scope=PolicyScope.GLOBAL,
            enforcement=PolicyEnforcement.STRICT,
        )
        
        assert policy.policy_id == "policy-1"
        assert policy.name == "Test Policy"
        assert policy.scope == PolicyScope.GLOBAL
        assert policy.enforcement == PolicyEnforcement.STRICT
        assert policy.enabled is True
    
    def test_policy_default_values(self):
        """Test policy default values."""
        policy = AgentPolicy(
            policy_id="policy-1",
            name="Test",
            description="Test",
            scope=PolicyScope.AGENT,
            enforcement=PolicyEnforcement.ADVISORY,
        )
        
        assert policy.priority == 100
        assert policy.enabled is True
        assert policy.allowed_actions == []
        assert policy.blocked_actions == []
        assert policy.max_tokens_per_request is None
        assert policy.require_human_approval is False
    
    def test_policy_with_rules(self):
        """Test policy with custom rules."""
        policy = AgentPolicy(
            policy_id="policy-1",
            name="Restricted",
            description="Restricted policy",
            scope=PolicyScope.TOOL,
            enforcement=PolicyEnforcement.STRICT,
            allowed_actions=["read", "write"],
            blocked_actions=["delete"],
            allowed_tools=["search", "calculate"],
            blocked_tools=["execute_code"],
        )
        
        assert "read" in policy.allowed_actions
        assert "delete" in policy.blocked_actions
        assert "search" in policy.allowed_tools
        assert "execute_code" in policy.blocked_tools
    
    def test_policy_with_constraints(self):
        """Test policy with constraints."""
        policy = AgentPolicy(
            policy_id="policy-1",
            name="Limited",
            description="Limited policy",
            scope=PolicyScope.TASK,
            enforcement=PolicyEnforcement.STRICT,
            max_tokens_per_request=1000,
            max_cost_per_request=0.10,
            max_execution_time=30.0,
            max_tool_calls_per_request=5,
            require_human_approval=True,
        )
        
        assert policy.max_tokens_per_request == 1000
        assert policy.max_cost_per_request == 0.10
        assert policy.max_execution_time == 30.0
        assert policy.max_tool_calls_per_request == 5
        assert policy.require_human_approval is True


class TestBehaviorPolicy:
    """Tests for BehaviorPolicy class."""
    
    def test_init_default(self):
        """Test default initialization."""
        policy = BehaviorPolicy()
        
        assert policy.require_explanation is False
        assert policy.max_response_length is None
        assert policy.required_output_format is None
        assert policy.allow_assumptions is True
        assert policy.require_source_citation is False
        assert policy.confidence_threshold == 0.0
        assert policy.enable_self_correction is True
    
    def test_init_custom(self):
        """Test custom initialization."""
        policy = BehaviorPolicy(
            require_explanation=True,
            max_response_length=500,
            required_output_format="json",
            allow_assumptions=False,
            require_source_citation=True,
            confidence_threshold=0.8,
        )
        
        assert policy.require_explanation is True
        assert policy.max_response_length == 500
        assert policy.required_output_format == "json"
        assert policy.allow_assumptions is False
        assert policy.require_source_citation is True
        assert policy.confidence_threshold == 0.8
    
    def test_validate_response_valid(self):
        """Test validating a valid response."""
        policy = BehaviorPolicy()
        
        result = policy.validate_response("This is a valid response")
        
        assert result['is_valid'] is True
        assert result['violations'] == []
    
    def test_validate_response_length_violation(self):
        """Test response length violation."""
        policy = BehaviorPolicy(max_response_length=10)
        
        result = policy.validate_response("This is a very long response")
        
        assert result['is_valid'] is False
        assert len(result['violations']) > 0
        assert "exceeds max length" in result['violations'][0]
    
    def test_validate_response_json_format(self):
        """Test JSON format validation."""
        policy = BehaviorPolicy(required_output_format="json")
        
        # Valid JSON
        result = policy.validate_response('{"key": "value"}')
        assert result['is_valid'] is True
        
        # Invalid JSON
        result = policy.validate_response("not json")
        assert result['is_valid'] is False
        assert any("not valid JSON" in v for v in result['violations'])
    
    def test_validate_response_explanation_required(self):
        """Test explanation requirement."""
        policy = BehaviorPolicy(require_explanation=True)
        
        # Response with explanation
        result = policy.validate_response("The answer is yes because it meets the criteria")
        assert result['is_valid'] is True
        
        # Response without explanation
        result = policy.validate_response("The answer is yes")
        assert result['is_valid'] is False
    
    def test_validate_response_source_citation(self):
        """Test source citation requirement."""
        policy = BehaviorPolicy(require_source_citation=True)
        
        # Response with citation
        result = policy.validate_response("According to the docs, this is correct")
        assert result['is_valid'] is True
        
        # Response without citation
        result = policy.validate_response("This is correct")
        assert result['is_valid'] is False
    
    def test_validate_response_confidence_threshold(self):
        """Test confidence threshold validation."""
        policy = BehaviorPolicy(confidence_threshold=0.8)
        
        # High confidence
        result = policy.validate_response("Answer", {'confidence': 0.9})
        assert result['is_valid'] is True
        
        # Low confidence
        result = policy.validate_response("Answer", {'confidence': 0.5})
        assert result['is_valid'] is False


class TestResourcePolicy:
    """Tests for ResourcePolicy class."""
    
    def test_init(self):
        """Test initialization."""
        policy = ResourcePolicy()
        
        assert policy.resource_rules == {}
        assert policy._access_log == []
    
    def test_add_rule(self):
        """Test adding a resource rule."""
        policy = ResourcePolicy()
        
        policy.add_rule(
            resource_pattern=r"files/.*",
            allowed_actions=["read"],
            blocked_actions=["delete"],
            rate_limit=100,
            require_auth=True,
        )
        
        assert r"files/.*" in policy.resource_rules
        rule = policy.resource_rules[r"files/.*"]
        assert rule['allowed_actions'] == ["read"]
        assert rule['blocked_actions'] == ["delete"]
        assert rule['rate_limit'] == 100
        assert rule['require_auth'] is True
    
    def test_check_access_allowed(self):
        """Test allowed access check."""
        policy = ResourcePolicy()
        policy.add_rule(r".*", allowed_actions=["read", "write"])
        
        result = policy.check_access("resource", "read")
        
        assert result['allowed'] is True
    
    def test_check_access_blocked(self):
        """Test blocked access check."""
        policy = ResourcePolicy()
        policy.add_rule(r".*", blocked_actions=["delete"])
        
        result = policy.check_access("resource", "delete")
        
        assert result['allowed'] is False
        assert "blocked" in result['reason']
    
    def test_check_access_not_in_allowed(self):
        """Test action not in allowed list."""
        policy = ResourcePolicy()
        policy.add_rule(r".*", allowed_actions=["read"])
        
        result = policy.check_access("resource", "write")
        
        assert result['allowed'] is False
        assert "not allowed" in result['reason']
    
    def test_check_access_auth_required(self):
        """Test authentication required."""
        policy = ResourcePolicy()
        policy.add_rule(r"secure/.*", require_auth=True)
        
        # Without auth
        result = policy.check_access("secure/data", "read")
        assert result['allowed'] is False
        assert "Authentication required" in result['reason']
        
        # With auth
        result = policy.check_access("secure/data", "read", {'authenticated': True})
        assert result['allowed'] is True
    
    def test_check_access_rate_limit(self):
        """Test rate limit enforcement."""
        policy = ResourcePolicy()
        policy.add_rule(r"api/.*", rate_limit=2)
        
        # First two should pass
        result = policy.check_access("api/endpoint", "call")
        assert result['allowed'] is True
        
        result = policy.check_access("api/endpoint", "call")
        assert result['allowed'] is True
        
        # Third should fail
        result = policy.check_access("api/endpoint", "call")
        assert result['allowed'] is False
        assert "Rate limit" in result['reason']
    
    def test_check_access_logs(self):
        """Test access logging."""
        policy = ResourcePolicy()
        policy.add_rule(r".*")
        
        policy.check_access("resource", "read")
        
        assert len(policy._access_log) == 1
        assert policy._access_log[0]['resource'] == "resource"
        assert policy._access_log[0]['action'] == "read"
    
    def test_check_access_no_matching_rule(self):
        """Test access when no rule matches."""
        policy = ResourcePolicy()
        policy.add_rule(r"specific/.*")
        
        result = policy.check_access("other/resource", "read")
        
        # Default is allowed when no rule matches
        assert result['allowed'] is True


class TestSafetyPolicy:
    """Tests for SafetyPolicy class."""
    
    def test_init_default(self):
        """Test default initialization."""
        policy = SafetyPolicy()
        
        assert policy.block_harmful_content is True
        assert policy.block_pii_output is True
        assert policy.require_safe_actions is True
        assert policy.enable_ethical_guidelines is True
    
    def test_init_custom(self):
        """Test custom initialization."""
        policy = SafetyPolicy(
            block_harmful_content=False,
            block_pii_output=False,
        )
        
        assert policy.block_harmful_content is False
        assert policy.block_pii_output is False
    
    def test_check_output_safety_clean(self):
        """Test checking clean output."""
        policy = SafetyPolicy()
        
        result = policy.check_output_safety("This is a safe output")
        
        assert result['is_safe'] is True
    
    def test_check_output_pii_email(self):
        """Test detecting email in output."""
        policy = SafetyPolicy()
        
        result = policy.check_output_safety("Contact: user@example.com")
        
        assert result['is_safe'] is False
        assert any(v.get('type') == 'Email' for v in result['violations'])
    
    def test_check_output_pii_ssn(self):
        """Test detecting SSN in output."""
        policy = SafetyPolicy()
        
        result = policy.check_output_safety("SSN: 123-45-6789")
        
        assert result['is_safe'] is False
    
    def test_check_output_pii_disabled(self):
        """Test PII check disabled."""
        policy = SafetyPolicy(block_pii_output=False)
        
        result = policy.check_output_safety("Email: test@test.com")
        
        # May still flag via content safety, but PII check is disabled
        # So at minimum we verify no PII violations
        pii_violations = [v for v in result['violations'] if isinstance(v, dict) and v.get('category') == 'pii_exposure']
        assert len(pii_violations) == 0
    
    def test_check_action_safety_safe(self):
        """Test safe action check."""
        policy = SafetyPolicy()
        
        result = policy.check_action_safety("read file.txt")
        
        assert result['is_safe'] is True
    
    def test_check_action_safety_dangerous(self):
        """Test dangerous action detection."""
        policy = SafetyPolicy()
        
        # rm -rf
        result = policy.check_action_safety("rm -rf /")
        assert result['is_safe'] is False
        
        # drop table
        result = policy.check_action_safety("DROP TABLE users")
        assert result['is_safe'] is False
        
        # delete all
        result = policy.check_action_safety("DELETE ALL records")
        assert result['is_safe'] is False
    
    def test_check_action_safety_disabled(self):
        """Test safe actions check disabled."""
        policy = SafetyPolicy(require_safe_actions=False)
        
        result = policy.check_action_safety("rm -rf /")
        
        assert result['is_safe'] is True


class TestAgentPolicyManager:
    """Tests for AgentPolicyManager class."""
    
    def test_init(self):
        """Test initialization."""
        manager = AgentPolicyManager()
        
        assert manager.policies == {}
        assert manager.behavior_policies == {}
        assert manager.resource_policies == {}
        assert manager.safety_policies == {}
    
    def test_register_policy(self):
        """Test registering an agent policy."""
        manager = AgentPolicyManager()
        policy = AgentPolicy(
            policy_id="test-policy",
            name="Test",
            description="Test policy",
            scope=PolicyScope.GLOBAL,
            enforcement=PolicyEnforcement.STRICT,
        )
        
        manager.register_policy(policy)
        
        assert "test-policy" in manager.policies
        assert manager.policies["test-policy"] == policy
    
    def test_register_behavior_policy(self):
        """Test registering a behavior policy."""
        manager = AgentPolicyManager()
        policy = BehaviorPolicy(require_explanation=True)
        
        manager.register_behavior_policy("explain", policy)
        
        assert "explain" in manager.behavior_policies
    
    def test_register_resource_policy(self):
        """Test registering a resource policy."""
        manager = AgentPolicyManager()
        policy = ResourcePolicy()
        
        manager.register_resource_policy("files", policy)
        
        assert "files" in manager.resource_policies
    
    def test_register_safety_policy(self):
        """Test registering a safety policy."""
        manager = AgentPolicyManager()
        policy = SafetyPolicy()
        
        manager.register_safety_policy("default", policy)
        
        assert "default" in manager.safety_policies
    
    def test_evaluate_policies_no_policies(self):
        """Test evaluation with no policies."""
        manager = AgentPolicyManager()
        
        result = manager.evaluate_policies("agent-1", "read")
        
        assert result['allowed'] is True
        assert result['policies_evaluated'] == []
    
    def test_evaluate_policies_disabled_policy(self):
        """Test that disabled policies are skipped."""
        manager = AgentPolicyManager()
        policy = AgentPolicy(
            policy_id="disabled",
            name="Disabled Policy",
            description="Test",
            scope=PolicyScope.GLOBAL,
            enforcement=PolicyEnforcement.STRICT,
            enabled=False,
            blocked_actions=["read"],
        )
        manager.register_policy(policy)
        
        result = manager.evaluate_policies("agent-1", "read")
        
        # Disabled policy should not block
        assert "Disabled Policy" not in result['policies_evaluated']
