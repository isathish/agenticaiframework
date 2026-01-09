"""Targeted tests for guardrails.py uncovered lines"""

import pytest
from agenticaiframework import Guardrail, GuardrailManager


class TestGuardrailExceptionHandling:
    """Test guardrail exception handling (lines 73-81)"""
    
    def test_validation_exception_handling(self):
        """Test that exceptions in validation are treated as failures"""
        def failing_validator(x):
            raise RuntimeError("Validation error")
        
        guardrail = Guardrail(
            name="failing",
            validation_fn=failing_validator
        )
        
        result = guardrail.validate({"test": "data"})
        assert result is False
        assert guardrail.violation_count == 1
        assert guardrail.last_violation is not None
        assert 'error' in guardrail.last_violation
        assert 'severity' in guardrail.last_violation
    
    def test_validation_exception_increments_violation(self):
        """Test that exceptions increment violation count"""
        def error_validator(x):
            raise ValueError("Invalid data")
        
        guardrail = Guardrail(name="error", validation_fn=error_validator)
        
        initial_count = guardrail.violation_count
        guardrail.validate("test")
        assert guardrail.violation_count == initial_count + 1


class TestGuardrailStats:
    """Test guardrail statistics (lines 83-89)"""
    
    def test_get_stats_with_violations(self):
        """Test get_stats method with violations"""
        guardrail = Guardrail(
            name="stats_test",
            validation_fn=lambda x: x > 0
        )
        
        # Perform some validations
        guardrail.validate(5)  # Pass
        guardrail.validate(-1)  # Fail
        guardrail.validate(10)  # Pass
        guardrail.validate(-5)  # Fail
        
        stats = guardrail.get_stats()
        assert 'name' in stats
        assert stats['name'] == "stats_test"
        assert 'validation_count' in stats
        assert 'violation_count' in stats
        assert 'violation_rate' in stats
        assert stats['validation_count'] == 4
        assert stats['violation_count'] == 2
        assert stats['violation_rate'] == 0.5
    
    def test_get_stats_no_violations(self):
        """Test get_stats with no violations"""
        guardrail = Guardrail(
            name="no_violations",
            validation_fn=lambda x: True
        )
        
        guardrail.validate("test")
        guardrail.validate("test2")
        
        stats = guardrail.get_stats()
        assert stats['validation_count'] == 2
        assert stats['violation_count'] == 0
        assert stats['violation_rate'] == 0.0


class TestGuardrailManagerGetByName:
    """Test get_guardrail_by_name method (lines 136-139)"""
    
    def test_get_guardrail_by_name_found(self):
        """Test getting guardrail by name when it exists"""
        manager = GuardrailManager()
        
        guard1 = Guardrail(name="test1", validation_fn=lambda x: True)
        guard2 = Guardrail(name="test2", validation_fn=lambda x: True)
        
        manager.register_guardrail(guard1)
        manager.register_guardrail(guard2)
        
        found = manager.get_guardrail_by_name("test1")
        assert found is not None
        assert found.name == "test1"
    
    def test_get_guardrail_by_name_not_found(self):
        """Test getting guardrail by name when it doesn't exist"""
        manager = GuardrailManager()
        
        guard = Guardrail(name="exists", validation_fn=lambda x: True)
        manager.register_guardrail(guard)
        
        found = manager.get_guardrail_by_name("does_not_exist")
        assert found is None


class TestGuardrailManagerList:
    """Test list_guardrails sorting (lines 141-145)"""
    
    def test_list_guardrails_sorted_by_priority(self):
        """Test that list_guardrails sorts by priority"""
        manager = GuardrailManager()
        
        guard1 = Guardrail(
            name="low",
            validation_fn=lambda x: True,
            policy={"priority": 1}
        )
        guard2 = Guardrail(
            name="high",
            validation_fn=lambda x: True,
            policy={"priority": 10}
        )
        guard3 = Guardrail(
            name="medium",
            validation_fn=lambda x: True,
            policy={"priority": 5}
        )
        
        manager.register_guardrail(guard1)
        manager.register_guardrail(guard2)
        manager.register_guardrail(guard3)
        
        guards = manager.list_guardrails()
        assert len(guards) == 3
        # Should be sorted by priority
        priorities = [g.policy.get('priority', 0) for g in guards]
        assert priorities == sorted(priorities)
    
    def test_list_guardrails_default_priority(self):
        """Test list_guardrails with default priority (0)"""
        manager = GuardrailManager()
        
        guard1 = Guardrail(name="no_priority", validation_fn=lambda x: True)
        guard2 = Guardrail(
            name="with_priority",
            validation_fn=lambda x: True,
            policy={"priority": 5}
        )
        
        manager.register_guardrail(guard1)
        manager.register_guardrail(guard2)
        
        guards = manager.list_guardrails()
        assert len(guards) == 2
