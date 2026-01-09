"""Ultra-targeted tests to cross the 80% threshold"""

import pytest
from agenticaiframework import Guardrail, GuardrailManager
from agenticaiframework import Prompt, PromptManager


class TestGuardrailsFinalPush:
    """Final guardrails coverage push"""
    
    def test_guardrail_str_validation(self):
        """Test string validation guardrail"""
        manager = GuardrailManager()
        guard = Guardrail(
            name="string_check",
            validation_fn=lambda x: isinstance(x, str) and len(x) > 0
        )
        manager.register_guardrail(guard)
        
        result1 = manager.enforce_guardrails("valid")
        assert result1['is_valid'] is True
        
        result2 = manager.enforce_guardrails("")
        assert result2['is_valid'] is False
    
    def test_guardrail_numeric_range(self):
        """Test numeric range guardrail"""
        manager = GuardrailManager()
        guard = Guardrail(
            name="range_check",
            validation_fn=lambda x: 0 <= x <= 100
        )
        manager.register_guardrail(guard)
        
        assert manager.enforce_guardrails(50)['is_valid'] is True
        assert manager.enforce_guardrails(150)['is_valid'] is False
        assert manager.enforce_guardrails(-10)['is_valid'] is False
    
    def test_guardrail_dict_validation(self):
        """Test dict validation guardrail"""
        manager = GuardrailManager()
        guard = Guardrail(
            name="dict_check",
            validation_fn=lambda x: isinstance(x, dict) and 'key' in x
        )
        manager.register_guardrail(guard)
        
        assert manager.enforce_guardrails({'key': 'value'})['is_valid'] is True
        assert manager.enforce_guardrails({})['is_valid'] is False
    
    def test_guardrail_list_validation(self):
        """Test list validation guardrail"""
        manager = GuardrailManager()
        guard = Guardrail(
            name="list_check",
            validation_fn=lambda x: isinstance(x, list) and len(x) > 0
        )
        manager.register_guardrail(guard)
        
        assert manager.enforce_guardrails([1, 2, 3])['is_valid'] is True
        assert manager.enforce_guardrails([])['is_valid'] is False


class TestPromptsFinalPush:
    """Final prompts coverage push"""
    
    def test_prompt_special_chars(self):
        """Test prompt with special characters"""
        manager = PromptManager()
        prompt = Prompt(
            template="Special: {x} & {y} | {z}",
            metadata={"type": "special"}
        )
        manager.register_prompt(prompt)
        
        result = manager.render_prompt(prompt.id, x="a", y="b", z="c")
        assert "a" in result and "b" in result and "c" in result
    
    def test_prompt_numbers(self):
        """Test prompt with numeric values"""
        manager = PromptManager()
        prompt = Prompt(template="Count: {num}", metadata={})
        manager.register_prompt(prompt)
        
        result = manager.render_prompt(prompt.id, num=42)
        assert "42" in result
    
    def test_prompt_boolean(self):
        """Test prompt with boolean values"""
        manager = PromptManager()
        prompt = Prompt(template="Status: {active}", metadata={})
        manager.register_prompt(prompt)
        
        result = manager.render_prompt(prompt.id, active=True)
        assert "True" in result
    
    def test_multiple_prompt_renders(self):
        """Test rendering same prompt multiple times"""
        manager = PromptManager()
        prompt = Prompt(template="Value: {v}", metadata={})
        manager.register_prompt(prompt)
        
        r1 = manager.render_prompt(prompt.id, v="first")
        r2 = manager.render_prompt(prompt.id, v="second")
        r3 = manager.render_prompt(prompt.id, v="third")
        
        assert "first" in r1
        assert "second" in r2
        assert "third" in r3
