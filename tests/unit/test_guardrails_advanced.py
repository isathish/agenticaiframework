"""
Comprehensive tests for guardrails module - advanced components.

Tests for:
- ChainOfThoughtGuardrail
- OutputFormatGuardrail
- GuardrailPipeline
- SemanticGuardrail
- ToolUseGuardrail
"""

import pytest
import time
from typing import Dict, Any


class TestChainOfThoughtGuardrail:
    """Tests for ChainOfThoughtGuardrail."""
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        
        guardrail = ChainOfThoughtGuardrail()
        assert guardrail.min_steps == 2
        assert guardrail.max_steps == 10
        assert guardrail.require_conclusion is True
        assert len(guardrail.step_markers) > 0
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        
        custom_markers = [r'Stage \d+']
        guardrail = ChainOfThoughtGuardrail(
            min_steps=3,
            max_steps=5,
            require_conclusion=False,
            step_markers=custom_markers
        )
        
        assert guardrail.min_steps == 3
        assert guardrail.max_steps == 5
        assert guardrail.require_conclusion is False
        assert guardrail.step_markers == custom_markers
    
    def test_validate_valid_reasoning(self):
        """Test validation of valid reasoning chain."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        
        guardrail = ChainOfThoughtGuardrail()
        reasoning = """
        Step 1: Analyze the problem requirements.
        Step 2: Identify key components because they are essential.
        Step 3: Design the solution.
        Therefore, the answer is to implement a modular architecture.
        """
        
        result = guardrail.validate(reasoning)
        assert result['is_valid'] is True
        assert result['step_count'] >= 3
        assert result['has_conclusion'] is True
        assert len(result['issues']) == 0
    
    def test_validate_insufficient_steps(self):
        """Test validation fails with insufficient steps."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        
        guardrail = ChainOfThoughtGuardrail(min_steps=3)
        reasoning = "Step 1: Do something. Therefore, done."
        
        result = guardrail.validate(reasoning)
        assert result['is_valid'] is False
        assert any('Insufficient' in issue for issue in result['issues'])
    
    def test_validate_too_many_steps(self):
        """Test validation fails with too many steps."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        
        guardrail = ChainOfThoughtGuardrail(max_steps=3)
        reasoning = """
        Step 1: First.
        Step 2: Second.
        Step 3: Third.
        Step 4: Fourth.
        Step 5: Fifth.
        Therefore done.
        """
        
        result = guardrail.validate(reasoning)
        assert result['is_valid'] is False
        assert any('Too many' in issue for issue in result['issues'])
    
    def test_validate_missing_conclusion(self):
        """Test validation fails without conclusion."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        
        guardrail = ChainOfThoughtGuardrail(require_conclusion=True)
        reasoning = """
        Step 1: First thing.
        Step 2: Second thing.
        Step 3: Third thing.
        """
        
        result = guardrail.validate(reasoning)
        assert result['has_conclusion'] is False
        assert any('conclusion' in issue.lower() for issue in result['issues'])
    
    def test_validate_no_conclusion_required(self):
        """Test validation passes without conclusion when not required."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        
        guardrail = ChainOfThoughtGuardrail(require_conclusion=False)
        reasoning = """
        Step 1: First because it matters.
        Step 2: Second since it's needed.
        Step 3: Third thing.
        """
        
        result = guardrail.validate(reasoning)
        assert result['is_valid'] is True
    
    def test_validate_detects_logical_connectors(self):
        """Test detection of logical connectors."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        
        guardrail = ChainOfThoughtGuardrail()
        reasoning = """
        Step 1: Because this matters.
        Step 2: Since we need it.
        Step 3: If we do this, then that happens.
        Therefore, conclusion.
        """
        
        result = guardrail.validate(reasoning)
        assert result['connector_count'] > 0
    
    def test_validate_bullet_points(self):
        """Test detection of bullet point steps."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        
        guardrail = ChainOfThoughtGuardrail()
        reasoning = """
        - First point because important
        - Second point since needed
        - Third point
        Therefore, done.
        """
        
        result = guardrail.validate(reasoning)
        assert result['step_count'] >= 3
    
    def test_validate_numbered_list(self):
        """Test detection of numbered list steps."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        
        guardrail = ChainOfThoughtGuardrail()
        reasoning = """
        1. First thing because x
        2. Second thing since y
        3. Third thing
        The answer is Z.
        """
        
        result = guardrail.validate(reasoning)
        assert result['step_count'] >= 3
        assert result['has_conclusion'] is True


class TestOutputFormatGuardrail:
    """Tests for OutputFormatGuardrail."""
    
    def test_init_default_values(self):
        """Test initialization with defaults."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        guardrail = OutputFormatGuardrail()
        assert guardrail.schema == {}
        assert guardrail.required_fields == []
        assert guardrail.max_length is None
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        schema = {'name': {'type': 'string'}}
        guardrail = OutputFormatGuardrail(
            schema=schema,
            required_fields=['name'],
            max_length=1000,
            allowed_formats=['json']
        )
        
        assert guardrail.schema == schema
        assert guardrail.required_fields == ['name']
        assert guardrail.max_length == 1000
    
    def test_validate_string_within_length(self):
        """Test validation of string within length limit."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        guardrail = OutputFormatGuardrail(max_length=100)
        result = guardrail.validate("Short string")
        
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_string_exceeds_length(self):
        """Test validation fails when string exceeds length."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        guardrail = OutputFormatGuardrail(max_length=10)
        result = guardrail.validate("This string is way too long")
        
        assert result['is_valid'] is False
        assert any('exceeds' in err for err in result['errors'])
    
    def test_validate_json_string_valid(self):
        """Test validation of valid JSON string."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        guardrail = OutputFormatGuardrail(required_fields=['name', 'value'])
        json_str = '{"name": "test", "value": 123}'
        result = guardrail.validate(json_str)
        
        assert result['is_valid'] is True
    
    def test_validate_json_string_missing_field(self):
        """Test validation fails with missing required field."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        guardrail = OutputFormatGuardrail(required_fields=['name', 'value'])
        json_str = '{"name": "test"}'
        result = guardrail.validate(json_str)
        
        assert result['is_valid'] is False
        assert any('value' in err for err in result['errors'])
    
    def test_validate_malformed_json(self):
        """Test validation detects malformed JSON."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        guardrail = OutputFormatGuardrail(allowed_formats=['json'])
        result = guardrail.validate('{"name": "test"')  # Missing closing brace
        
        assert result['is_valid'] is False
        assert any('malformed' in err.lower() for err in result['errors'])
    
    def test_validate_dict_with_required_fields(self):
        """Test validation of dict with required fields."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        guardrail = OutputFormatGuardrail(required_fields=['name'])
        result = guardrail.validate({'name': 'test', 'extra': 'data'})
        
        assert result['is_valid'] is True
    
    def test_validate_dict_missing_required_fields(self):
        """Test validation fails when dict missing required fields."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        guardrail = OutputFormatGuardrail(required_fields=['name', 'id'])
        result = guardrail.validate({'name': 'test'})
        
        assert result['is_valid'] is False
        assert any('id' in err for err in result['errors'])
    
    def test_validate_schema_type_validation(self):
        """Test schema type validation."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        schema = {
            'name': {'type': 'string'},
            'count': {'type': 'integer'},
            'active': {'type': 'boolean'}
        }
        guardrail = OutputFormatGuardrail(schema=schema)
        
        # Valid types
        result = guardrail.validate({'name': 'test', 'count': 5, 'active': True})
        assert result['is_valid'] is True
        
        # Invalid type
        result = guardrail.validate({'name': 123, 'count': 5, 'active': True})
        assert result['is_valid'] is False
    
    def test_validate_schema_required_field(self):
        """Test schema required field validation."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        schema = {
            'name': {'type': 'string', 'required': True}
        }
        guardrail = OutputFormatGuardrail(schema=schema)
        
        result = guardrail.validate({})
        assert result['is_valid'] is False
        assert any('required' in err.lower() for err in result['errors'])
    
    def test_validate_array_type(self):
        """Test array type validation."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        schema = {'items': {'type': 'array'}}
        guardrail = OutputFormatGuardrail(schema=schema)
        
        result = guardrail.validate({'items': [1, 2, 3]})
        assert result['is_valid'] is True
        
        result = guardrail.validate({'items': 'not an array'})
        assert result['is_valid'] is False
    
    def test_validate_object_type(self):
        """Test object type validation."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        
        schema = {'config': {'type': 'object'}}
        guardrail = OutputFormatGuardrail(schema=schema)
        
        result = guardrail.validate({'config': {'key': 'value'}})
        assert result['is_valid'] is True


class TestGuardrailPipeline:
    """Tests for GuardrailPipeline."""
    
    def test_init(self):
        """Test pipeline initialization."""
        from agenticaiframework.guardrails.pipeline import GuardrailPipeline
        
        pipeline = GuardrailPipeline("test_pipeline")
        assert pipeline.name == "test_pipeline"
        assert len(pipeline.stages) == 0
    
    def test_add_stage(self):
        """Test adding stages to pipeline."""
        from agenticaiframework.guardrails.pipeline import GuardrailPipeline
        from agenticaiframework.guardrails.types import GuardrailAction
        
        pipeline = GuardrailPipeline("test")
        
        # Mock guardrail
        class MockGuardrail:
            name = "mock"
            def validate(self, data):
                return True
        
        pipeline.add_stage(
            guardrails=[MockGuardrail()],
            mode="all",
            on_failure=GuardrailAction.BLOCK
        )
        
        assert len(pipeline.stages) == 1
        assert pipeline.stages[0]['mode'] == "all"
    
    def test_execute_all_pass(self):
        """Test execution when all guardrails pass."""
        from agenticaiframework.guardrails.pipeline import GuardrailPipeline
        
        pipeline = GuardrailPipeline("test")
        
        class PassGuardrail:
            name = "pass"
            def validate(self, data):
                return True
        
        pipeline.add_stage(guardrails=[PassGuardrail(), PassGuardrail()])
        
        result = pipeline.execute("test data")
        assert result['is_valid'] is True
        assert result['stages_passed'] == 1
        assert result['stages_failed'] == 0
    
    def test_execute_with_failure(self):
        """Test execution when guardrail fails."""
        from agenticaiframework.guardrails.pipeline import GuardrailPipeline
        from agenticaiframework.guardrails.types import GuardrailAction
        
        pipeline = GuardrailPipeline("test")
        
        class FailGuardrail:
            name = "fail"
            def validate(self, data):
                return False
        
        pipeline.add_stage(
            guardrails=[FailGuardrail()],
            on_failure=GuardrailAction.BLOCK
        )
        
        result = pipeline.execute("test data")
        assert result['is_valid'] is False
        assert result['stages_failed'] == 1
    
    def test_execute_any_mode(self):
        """Test execution with 'any' mode."""
        from agenticaiframework.guardrails.pipeline import GuardrailPipeline
        
        pipeline = GuardrailPipeline("test")
        
        class PassGuardrail:
            name = "pass"
            def validate(self, data):
                return True
        
        class FailGuardrail:
            name = "fail"
            def validate(self, data):
                return False
        
        pipeline.add_stage(
            guardrails=[PassGuardrail(), FailGuardrail()],
            mode="any"
        )
        
        result = pipeline.execute("test data")
        assert result['is_valid'] is True
    
    def test_execute_majority_mode(self):
        """Test execution with 'majority' mode."""
        from agenticaiframework.guardrails.pipeline import GuardrailPipeline
        
        pipeline = GuardrailPipeline("test")
        
        class PassGuardrail:
            name = "pass"
            def validate(self, data):
                return True
        
        class FailGuardrail:
            name = "fail"
            def validate(self, data):
                return False
        
        # 2 pass, 1 fail = majority pass
        pipeline.add_stage(
            guardrails=[PassGuardrail(), PassGuardrail(), FailGuardrail()],
            mode="majority"
        )
        
        result = pipeline.execute("test data")
        assert result['is_valid'] is True
    
    def test_execute_with_condition(self):
        """Test execution with conditional stage."""
        from agenticaiframework.guardrails.pipeline import GuardrailPipeline
        
        pipeline = GuardrailPipeline("test")
        
        class FailGuardrail:
            name = "fail"
            def validate(self, data):
                return False
        
        # Stage with condition that returns False
        pipeline.add_stage(
            guardrails=[FailGuardrail()],
            condition=lambda ctx: ctx.get('run_stage', False)
        )
        
        result = pipeline.execute("test data", context={'run_stage': False})
        # Stage should be skipped, so still valid
        assert result['is_valid'] is True
        assert result['stages_executed'] == 0
    
    def test_execute_with_safety_guardrail(self):
        """Test execution with safety guardrail (check method)."""
        from agenticaiframework.guardrails.pipeline import GuardrailPipeline
        
        pipeline = GuardrailPipeline("test")
        
        class SafetyGuardrail:
            name = "safety"
            def check(self, data):
                return {'is_safe': True}
        
        pipeline.add_stage(guardrails=[SafetyGuardrail()])
        
        result = pipeline.execute("test data")
        assert result['is_valid'] is True


class TestSemanticGuardrail:
    """Tests for SemanticGuardrail."""
    
    def test_init(self):
        """Test initialization."""
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        guardrail = SemanticGuardrail(
            name="test",
            allowed_topics=["python"],
            blocked_topics=["violence"],
            required_topics=["code"]
        )
        
        assert guardrail.name == "test"
        assert "python" in guardrail.allowed_topics
        assert "violence" in guardrail.blocked_topics
    
    def test_validate_blocked_topic(self):
        """Test validation catches blocked topics."""
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        guardrail = SemanticGuardrail(
            name="test",
            blocked_topics=["violence", "weapons"]
        )
        
        is_valid, violations = guardrail.validate("This content mentions violence explicitly.")
        assert is_valid is False
        assert any("violence" in v for v in violations)
    
    def test_validate_required_topic_present(self):
        """Test validation passes with required topic present."""
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        guardrail = SemanticGuardrail(
            name="test",
            required_topics=["python"]
        )
        
        is_valid, violations = guardrail.validate("This is about python programming.")
        assert is_valid is True
        assert len(violations) == 0
    
    def test_validate_required_topic_missing(self):
        """Test validation fails with required topic missing."""
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        guardrail = SemanticGuardrail(
            name="test",
            required_topics=["python", "code"]
        )
        
        is_valid, violations = guardrail.validate("This mentions nothing relevant.")
        assert is_valid is False
        assert len(violations) == 2
    
    def test_validate_clean_content(self):
        """Test validation passes for clean content."""
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        guardrail = SemanticGuardrail(
            name="test",
            blocked_topics=["harmful"],
            required_topics=[]
        )
        
        is_valid, violations = guardrail.validate("This is safe content about programming.")
        assert is_valid is True
    
    def test_compute_topic_score_direct_match(self):
        """Test topic score with direct match."""
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        guardrail = SemanticGuardrail(name="test")
        score = guardrail.compute_topic_score("Python programming language", "python")
        assert score == 1.0
    
    def test_compute_topic_score_word_overlap(self):
        """Test topic score with word overlap."""
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        guardrail = SemanticGuardrail(name="test")
        score = guardrail.compute_topic_score(
            "machine learning algorithms",
            "machine learning"
        )
        assert score == 1.0  # Both words present
    
    def test_compute_topic_score_partial_match(self):
        """Test topic score with partial match."""
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        guardrail = SemanticGuardrail(name="test")
        score = guardrail.compute_topic_score(
            "machine intelligence",
            "machine learning"
        )
        assert 0 < score < 1.0  # Partial match
    
    def test_compute_topic_score_no_match(self):
        """Test topic score with no match."""
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        guardrail = SemanticGuardrail(name="test")
        score = guardrail.compute_topic_score("cats and dogs", "python")
        assert score == 0.0
    
    def test_compute_topic_score_empty_topic(self):
        """Test topic score with empty topic."""
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        guardrail = SemanticGuardrail(name="test")
        score = guardrail.compute_topic_score("some content", "")
        # Empty topic may return 1.0 (always matches) or 0.0 depending on implementation
        assert 0.0 <= score <= 1.0


class TestToolUseGuardrail:
    """Tests for ToolUseGuardrail."""
    
    def test_init_default(self):
        """Test initialization with defaults."""
        from agenticaiframework.guardrails.tool_use import ToolUseGuardrail
        
        guardrail = ToolUseGuardrail()
        assert guardrail.allowed_tools is None
        assert guardrail.blocked_tools == []
    
    def test_init_custom(self):
        """Test initialization with custom values."""
        from agenticaiframework.guardrails.tool_use import ToolUseGuardrail
        
        guardrail = ToolUseGuardrail(
            allowed_tools=["search", "calculate"],
            blocked_tools=["delete"],
            tool_rate_limits={"search": 10},
            require_confirmation=["delete"]
        )
        
        assert "search" in guardrail.allowed_tools
        assert "delete" in guardrail.blocked_tools
    
    def test_validate_allowed_tool(self):
        """Test validation of allowed tool."""
        from agenticaiframework.guardrails.tool_use import ToolUseGuardrail
        
        guardrail = ToolUseGuardrail(allowed_tools=["search", "calculate"])
        
        result = guardrail.validate_invocation("search", {"query": "test"})
        assert result['is_valid'] is True
    
    def test_validate_disallowed_tool(self):
        """Test validation fails for disallowed tool."""
        from agenticaiframework.guardrails.tool_use import ToolUseGuardrail
        
        guardrail = ToolUseGuardrail(allowed_tools=["search"])
        
        result = guardrail.validate_invocation("delete", {})
        assert result['is_valid'] is False
        assert any("not in allowed" in err for err in result['errors'])
    
    def test_validate_blocked_tool(self):
        """Test validation fails for blocked tool."""
        from agenticaiframework.guardrails.tool_use import ToolUseGuardrail
        
        guardrail = ToolUseGuardrail(blocked_tools=["delete", "destroy"])
        
        result = guardrail.validate_invocation("delete", {})
        assert result['is_valid'] is False
        assert any("blocked" in err for err in result['errors'])
    
    def test_validate_rate_limit(self):
        """Test rate limiting enforcement."""
        from agenticaiframework.guardrails.tool_use import ToolUseGuardrail
        
        guardrail = ToolUseGuardrail(tool_rate_limits={"search": 2})
        
        # First two calls should succeed
        result1 = guardrail.validate_invocation("search", {})
        result2 = guardrail.validate_invocation("search", {})
        assert result1['is_valid'] is True
        assert result2['is_valid'] is True
        
        # Third call should fail
        result3 = guardrail.validate_invocation("search", {})
        assert result3['is_valid'] is False
        assert any("rate limit" in err for err in result3['errors'])
    
    def test_validate_requires_confirmation(self):
        """Test confirmation requirement detection."""
        from agenticaiframework.guardrails.tool_use import ToolUseGuardrail
        
        guardrail = ToolUseGuardrail(require_confirmation=["dangerous_op"])
        
        result = guardrail.validate_invocation("dangerous_op", {})
        assert result['requires_confirmation'] is True
        assert len(result['warnings']) > 0
    
    def test_validate_schema_missing_required(self):
        """Test schema validation with missing required params."""
        from agenticaiframework.guardrails.tool_use import ToolUseGuardrail
        
        guardrail = ToolUseGuardrail()
        schema = {
            'parameters': {
                'required': ['query', 'limit'],
                'properties': {}
            }
        }
        
        result = guardrail.validate_invocation("search", {'query': 'test'}, schema)
        assert result['is_valid'] is False
        assert any("limit" in err for err in result['errors'])
    
    def test_validate_schema_type_mismatch(self):
        """Test schema validation with type mismatch."""
        from agenticaiframework.guardrails.tool_use import ToolUseGuardrail
        
        guardrail = ToolUseGuardrail()
        schema = {
            'parameters': {
                'required': [],
                'properties': {
                    'limit': {'type': 'integer'},
                    'query': {'type': 'string'},
                    'active': {'type': 'boolean'},
                    'items': {'type': 'array'}
                }
            }
        }
        
        # Valid types
        result = guardrail.validate_invocation(
            "search", 
            {'limit': 10, 'query': 'test', 'active': True, 'items': []}, 
            schema
        )
        assert result['is_valid'] is True
        
        # Invalid string type
        result = guardrail.validate_invocation("search", {'query': 123}, schema)
        assert result['is_valid'] is False
        
        # Invalid integer type
        result = guardrail.validate_invocation("search", {'limit': "ten"}, schema)
        assert result['is_valid'] is False
    
    def test_validate_no_allowed_list(self):
        """Test validation when no allowed list specified."""
        from agenticaiframework.guardrails.tool_use import ToolUseGuardrail
        
        guardrail = ToolUseGuardrail()  # No restrictions
        
        result = guardrail.validate_invocation("any_tool", {})
        assert result['is_valid'] is True


class TestGuardrailIntegration:
    """Integration tests for guardrail components."""
    
    def test_chain_of_thought_with_pipeline(self):
        """Test ChainOfThoughtGuardrail in pipeline."""
        from agenticaiframework.guardrails.chain_of_thought import ChainOfThoughtGuardrail
        from agenticaiframework.guardrails.pipeline import GuardrailPipeline
        
        cot_guardrail = ChainOfThoughtGuardrail()
        pipeline = GuardrailPipeline("reasoning_check")
        
        # Wrap as check-based guardrail
        class COTWrapper:
            name = "cot"
            def __init__(self, guardrail):
                self.guardrail = guardrail
            def check(self, data):
                result = self.guardrail.validate(data)
                return {'is_safe': result['is_valid']}
        
        pipeline.add_stage(guardrails=[COTWrapper(cot_guardrail)])
        
        good_reasoning = """
        Step 1: First because important.
        Step 2: Then since needed.
        Step 3: Next we do.
        Therefore, the conclusion is clear.
        """
        
        result = pipeline.execute(good_reasoning)
        assert result['is_valid'] is True
    
    def test_output_format_with_semantic(self):
        """Test combining OutputFormat and Semantic guardrails."""
        from agenticaiframework.guardrails.output_format import OutputFormatGuardrail
        from agenticaiframework.guardrails.semantic import SemanticGuardrail
        
        format_guardrail = OutputFormatGuardrail(required_fields=['response'])
        semantic_guardrail = SemanticGuardrail(
            name="safe",
            blocked_topics=["harmful"]
        )
        
        # Test valid output
        output = {'response': 'This is a helpful answer'}
        format_result = format_guardrail.validate(output)
        semantic_result = semantic_guardrail.validate(output['response'])
        
        assert format_result['is_valid'] is True
        assert semantic_result[0] is True
