"""
Tests for new convenience methods added to evaluators.

This file tests the granular evaluation methods that were added to match
the documented API, ensuring they work correctly as convenience wrappers.
"""

import pytest


class TestModelQualityConvenienceMethods:
    """Test convenience methods for ModelQualityEvaluator."""
    
    def test_evaluate_hallucination_method(self):
        """Test the evaluate_hallucination convenience method."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        
        result = evaluator.evaluate_hallucination(
            text="The Eiffel Tower is in London",
            is_hallucination=True,
            confidence=0.95
        )
        
        assert result is not None
        assert result['text'] == "The Eiffel Tower is in London"
        assert result['is_hallucination'] is True
        assert result['confidence'] == 0.95
        assert 'timestamp' in result
    
    def test_evaluate_reasoning_method(self):
        """Test the evaluate_reasoning convenience method."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        
        result = evaluator.evaluate_reasoning(
            query="What is 2+2?",
            reasoning="Adding two plus two equals four",
            answer="4",
            correct=True
        )
        
        assert result is not None
        assert result['query'] == "What is 2+2?"
        assert result['reasoning'] == "Adding two plus two equals four"
        assert result['answer'] == "4"
        assert result['correct'] is True
        assert 'timestamp' in result
    
    def test_evaluate_token_efficiency_method(self):
        """Test the evaluate_token_efficiency convenience method."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        
        result = evaluator.evaluate_token_efficiency(
            response="This is a concise answer",
            token_count=5,
            quality_score=0.9
        )
        
        assert result is not None
        assert result['response'] == "This is a concise answer"
        assert result['token_count'] == 5
        assert result['quality_score'] == 0.9
        assert result['efficiency'] == 0.9 / 5
        assert 'timestamp' in result
    
    def test_get_quality_metrics_method(self):
        """Test the get_quality_metrics convenience method."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        
        # Add some evaluations
        evaluator.evaluate_response(
            model_name="gpt-4",
            prompt="Test",
            response="Test response",
            ground_truth="Test response"
        )
        
        result = evaluator.get_quality_metrics()
        
        assert result is not None
        assert 'total_models' in result
        assert 'total_evaluations' in result
        assert 'models' in result
        assert result['total_models'] == 1
        assert 'gpt-4' in result['models']


class TestRAGConvenienceMethods:
    """Test convenience methods for RAGEvaluator."""
    
    def test_evaluate_retrieval_method(self):
        """Test the evaluate_retrieval convenience method."""
        from agenticaiframework import RAGEvaluator
        
        evaluator = RAGEvaluator()
        
        retrieved_docs = [
            {'id': 'doc1', 'content': 'Content 1'},
            {'id': 'doc2', 'content': 'Content 2'}
        ]
        relevant_docs = [
            {'id': 'doc1', 'content': 'Content 1'},
            {'id': 'doc3', 'content': 'Content 3'}
        ]
        
        result = evaluator.evaluate_retrieval(
            query="test query",
            retrieved_docs=retrieved_docs,
            relevant_docs=relevant_docs
        )
        
        assert result is not None
        assert result['query'] == "test query"
        assert 'precision' in result
        assert 'recall' in result
        assert 'f1_score' in result
        assert result['num_retrieved'] == 2
        assert result['num_relevant'] == 2
        assert 'timestamp' in result
    
    def test_evaluate_faithfulness_method(self):
        """Test the evaluate_faithfulness convenience method."""
        from agenticaiframework import RAGEvaluator
        
        evaluator = RAGEvaluator()
        
        docs = [
            {'content': 'The sky is blue and grass is green'}
        ]
        
        result = evaluator.evaluate_faithfulness(
            answer="The sky is blue",
            retrieved_docs=docs
        )
        
        assert result is not None
        assert result['answer'] == "The sky is blue"
        assert 'faithfulness_score' in result
        assert result['num_docs'] == 1
        assert 'timestamp' in result
    
    def test_evaluate_groundedness_method(self):
        """Test the evaluate_groundedness convenience method."""
        from agenticaiframework import RAGEvaluator
        
        evaluator = RAGEvaluator()
        
        docs = [
            {'content': 'Paris is the capital of France'}
        ]
        
        result = evaluator.evaluate_groundedness(
            answer="Paris is the capital of France",
            retrieved_docs=docs
        )
        
        assert result is not None
        assert result['answer'] == "Paris is the capital of France"
        assert 'groundedness_score' in result
        assert result['num_docs'] == 1
        assert 'timestamp' in result
    
    def test_check_citations_method(self):
        """Test the check_citations convenience method."""
        from agenticaiframework import RAGEvaluator
        
        evaluator = RAGEvaluator()
        
        result = evaluator.check_citations(
            answer="According to [1], the answer is 42"
        )
        
        assert result is not None
        assert result['answer'] == "According to [1], the answer is 42"
        assert result['has_citations'] is True
        assert 'timestamp' in result


class TestWorkflowConvenienceMethods:
    """Test convenience methods for WorkflowEvaluator."""
    
    def test_record_workflow_execution_method(self):
        """Test the record_workflow_execution convenience method."""
        from agenticaiframework import WorkflowEvaluator
        
        evaluator = WorkflowEvaluator()
        
        workflow_id = evaluator.record_workflow_execution(
            workflow_name="test_workflow",
            success=True,
            metadata={'duration': 100}
        )
        
        assert workflow_id is not None
        assert isinstance(workflow_id, str)
        
        metrics = evaluator.get_workflow_metrics("test_workflow")
        assert metrics['workflow_name'] == "test_workflow"
        assert metrics['total_attempts'] == 1
    
    def test_record_agent_handoff_method(self):
        """Test the record_agent_handoff convenience method."""
        from agenticaiframework import WorkflowEvaluator
        
        evaluator = WorkflowEvaluator()
        
        workflow_id = evaluator.start_workflow("test_workflow")
        
        evaluator.record_agent_handoff(
            workflow_id=workflow_id,
            from_agent="agent1",
            to_agent="agent2"
        )
        
        workflow = evaluator.workflows[workflow_id]
        assert len(workflow['steps']) == 1
        assert 'agent2' in workflow['agents']


class TestMemoryConvenienceMethods:
    """Test convenience methods for MemoryEvaluator."""
    
    def test_evaluate_retrieval_alias(self):
        """Test the evaluate_retrieval alias method."""
        from agenticaiframework import MemoryEvaluator
        
        evaluator = MemoryEvaluator()
        
        retrieved = [{'id': '1', 'content': 'memory1'}]
        relevant = [{'id': '1', 'content': 'memory1'}]
        
        result = evaluator.evaluate_retrieval(
            query="test",
            retrieved_memories=retrieved,
            relevant_memories=relevant
        )
        
        assert result is not None
        assert 'precision' in result or 'num_retrieved' in result
    
    def test_record_stale_data_access_method(self):
        """Test the record_stale_data_access convenience method."""
        from agenticaiframework import MemoryEvaluator
        
        evaluator = MemoryEvaluator()
        
        initial_count = evaluator.memory_metrics['stale_data_usage']
        
        evaluator.record_stale_data_access(
            memory_data={'id': '1', 'timestamp': 0}
        )
        
        assert evaluator.memory_metrics['stale_data_usage'] == initial_count + 1
    
    def test_record_overwrite_error_method(self):
        """Test the record_overwrite_error convenience method."""
        from agenticaiframework import MemoryEvaluator
        
        evaluator = MemoryEvaluator()
        
        initial_count = evaluator.memory_metrics['memory_overwrite_errors']
        
        evaluator.record_overwrite_error()
        
        assert evaluator.memory_metrics['memory_overwrite_errors'] == initial_count + 1


class TestAutonomyConvenienceMethods:
    """Test convenience methods for AutonomyEvaluator."""
    
    def test_evaluate_plan_optimality_method(self):
        """Test the evaluate_plan_optimality convenience method."""
        from agenticaiframework import AutonomyEvaluator
        
        evaluator = AutonomyEvaluator()
        
        result = evaluator.evaluate_plan_optimality(
            plan_steps=['step1', 'step2', 'step3'],
            optimal_steps=['step1', 'step2']
        )
        
        assert result is not None
        assert 'optimality' in result
        assert result['actual_steps'] == 3
        assert result['optimal_steps'] == 2
        assert 'timestamp' in result


class TestPerformanceConvenienceMethods:
    """Test convenience methods for PerformanceEvaluator."""
    
    def test_record_execution_alias(self):
        """Test the record_execution alias method."""
        from agenticaiframework import PerformanceEvaluator
        
        evaluator = PerformanceEvaluator()
        
        evaluator.record_execution(
            execution_id="exec1",
            duration_ms=100.5,
            success=True
        )
        
        metrics = evaluator.get_performance_metrics()
        assert metrics['total_requests'] == 1
        assert 100.5 in evaluator.latencies


class TestHITLConvenienceMethods:
    """Test convenience methods for HITLEvaluator."""
    
    def test_record_review_method(self):
        """Test the record_review convenience method."""
        from agenticaiframework import HITLEvaluator
        
        evaluator = HITLEvaluator()
        
        result = evaluator.record_review(
            decision="Approve transaction",
            approved=True,
            review_time_seconds=5.2
        )
        
        assert result is not None
        assert result['recommendation'] == "Approve transaction"
        assert result['accepted'] is True
        assert 'timestamp' in result
    
    def test_record_override_method(self):
        """Test the record_override convenience method."""
        from agenticaiframework import HITLEvaluator
        
        evaluator = HITLEvaluator()
        
        result = evaluator.record_override(
            agent_decision="Reject",
            human_decision="Approve",
            reason="Special case"
        )
        
        assert result is not None
        assert result['recommendation'] == "Reject"
        assert result['accepted'] is False
        assert result['metadata']['human_decision'] == "Approve"
        assert result['metadata']['reason'] == "Special case"
    
    def test_record_trust_signal_method(self):
        """Test the record_trust_signal convenience method."""
        from agenticaiframework import HITLEvaluator
        
        evaluator = HITLEvaluator()
        
        result = evaluator.record_trust_signal(
            interaction_id="int123",
            trust_score=0.85
        )
        
        assert result is not None
        assert result['interaction_id'] == "int123"
        assert result['trust_score'] == 0.85
        assert 0.85 in evaluator.hitl_metrics['trust_scores']
        assert 'timestamp' in result


class TestConvenienceMethodsIntegration:
    """Integration tests using the new convenience methods."""
    
    def test_model_quality_full_workflow(self):
        """Test full workflow with ModelQualityEvaluator convenience methods."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        
        # Use granular methods
        evaluator.evaluate_hallucination("Test text", False, 0.9)
        evaluator.evaluate_reasoning("query", "reasoning", "answer", True)
        evaluator.evaluate_token_efficiency("response", 10, 0.85)
        
        # Use comprehensive method
        evaluator.evaluate_response("gpt-4", "prompt", "response", "response")
        
        # Get metrics
        metrics = evaluator.get_quality_metrics()
        
        assert metrics['total_models'] == 1
        assert metrics['total_evaluations'] == 1
    
    def test_rag_full_workflow(self):
        """Test full workflow with RAGEvaluator convenience methods."""
        from agenticaiframework import RAGEvaluator
        
        evaluator = RAGEvaluator()
        
        docs = [{'id': 'doc1', 'content': 'test content'}]
        
        # Use granular methods
        evaluator.evaluate_retrieval("query", docs, docs)
        evaluator.evaluate_faithfulness("answer", docs)
        evaluator.evaluate_groundedness("answer", docs)
        evaluator.check_citations("answer [1]")
        
        # Use comprehensive method
        evaluator.evaluate_rag_response(
            query="test",
            retrieved_docs=docs,
            generated_answer="test answer",
            relevant_docs=docs
        )
        
        metrics = evaluator.get_rag_metrics()
        assert metrics['total_queries'] == 1
    
    def test_hitl_full_workflow(self):
        """Test full workflow with HITLEvaluator convenience methods."""
        from agenticaiframework import HITLEvaluator
        
        evaluator = HITLEvaluator()
        
        # Use granular methods
        evaluator.record_review("decision1", True, 3.5)
        evaluator.record_override("agent_decision", "human_decision", "reason")
        evaluator.record_trust_signal("int1", 0.9)
        
        # Use generic method
        evaluator.record_escalation("recommendation", True, 2.0, 0.95)
        
        metrics = evaluator.get_hitl_metrics()
        assert metrics['total_escalations'] == 3
