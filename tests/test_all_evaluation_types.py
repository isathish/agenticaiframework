"""
Complete Tests for All 12 Evaluation Types

Comprehensive test coverage for the entire evaluation framework as described
in the Agentic AI evaluation stack.
"""

import pytest
import time


# =============================================================================
# 1. Model-Level Evaluations
# =============================================================================
class TestModelQualityEvaluator:
    """Tests for Model-Level evaluations (LLM Quality)."""
    
    def test_model_evaluator_creation(self):
        """Test creating model quality evaluator."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        assert evaluator is not None
    
    def test_evaluate_response_with_ground_truth(self):
        """Test evaluating response with ground truth."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        
        evaluation = evaluator.evaluate_response(
            model_name="gpt-4",
            prompt="What is 2+2?",
            response="The answer is 4.",
            ground_truth="The answer is 4."
        )
        
        assert evaluation is not None
        assert "metrics" in evaluation
        assert "exact_match" in evaluation["metrics"]
        assert evaluation["metrics"]["exact_match"] == 1.0
    
    def test_hallucination_detection(self):
        """Test hallucination detection."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        
        # Response with hallucination indicators
        evaluation = evaluator.evaluate_response(
            model_name="gpt-3.5",
            prompt="What is the population of Mars?",
            response="I believe the population might be around 1 million, probably."
        )
        
        assert "hallucination_score" in evaluation["metrics"]
        assert evaluation["metrics"]["hallucination_score"] > 0
    
    def test_reasoning_quality_assessment(self):
        """Test reasoning quality assessment."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        
        evaluation = evaluator.evaluate_response(
            model_name="claude-3",
            prompt="Explain why the sky is blue",
            response="The sky is blue because light scatters. First, sunlight enters the atmosphere. "
                    "Second, blue light scatters more due to shorter wavelength. Therefore, we see blue."
        )
        
        assert "reasoning_quality" in evaluation["metrics"]
        assert evaluation["metrics"]["reasoning_quality"] > 0
    
    def test_token_efficiency(self):
        """Test token efficiency calculation."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        
        evaluation = evaluator.evaluate_response(
            model_name="gpt-4",
            prompt="Say hi",
            response="Hello there! How can I help you today?"
        )
        
        assert "token_efficiency" in evaluation["metrics"]
    
    def test_get_model_summary(self):
        """Test getting model summary."""
        from agenticaiframework import ModelQualityEvaluator
        
        evaluator = ModelQualityEvaluator()
        
        # Record multiple evaluations
        for i in range(5):
            evaluator.evaluate_response(
                model_name="gpt-4",
                prompt=f"Question {i}",
                response=f"Answer {i}",
                ground_truth=f"Answer {i}"
            )
        
        summary = evaluator.get_model_summary("gpt-4")
        
        assert summary["total_evaluations"] == 5
        assert "metrics" in summary


# =============================================================================
# 2. Task/Skill-Level Evaluations
# =============================================================================
class TestTaskEvaluator:
    """Tests for Task/Skill-Level evaluations."""
    
    def test_task_evaluator_creation(self):
        """Test creating task evaluator."""
        from agenticaiframework import TaskEvaluator
        
        evaluator = TaskEvaluator()
        assert evaluator is not None
    
    def test_record_successful_task(self):
        """Test recording successful task execution."""
        from agenticaiframework import TaskEvaluator
        
        evaluator = TaskEvaluator()
        
        execution = evaluator.record_task_execution(
            task_name="create_jira_ticket",
            success=True,
            completion_percentage=100.0,
            duration_ms=1500
        )
        
        assert execution is not None
        assert execution["success"] is True
    
    def test_record_failed_task_with_retries(self):
        """Test recording failed task with retries."""
        from agenticaiframework import TaskEvaluator
        
        evaluator = TaskEvaluator()
        
        execution = evaluator.record_task_execution(
            task_name="deploy_service",
            success=False,
            completion_percentage=75.0,
            retry_count=3,
            error_recovered=False
        )
        
        assert execution["success"] is False
        assert execution["retry_count"] == 3
    
    def test_get_task_metrics(self):
        """Test getting task metrics."""
        from agenticaiframework import TaskEvaluator
        
        evaluator = TaskEvaluator()
        
        # Record multiple attempts
        for i in range(10):
            evaluator.record_task_execution(
                task_name="summarize_pr",
                success=(i % 2 == 0),  # 50% success rate
                retry_count=i % 3
            )
        
        metrics = evaluator.get_task_metrics("summarize_pr")
        
        assert metrics["total_attempts"] == 10
        assert 0.4 <= metrics["success_rate"] <= 0.6  # Around 50%
    
    def test_get_all_tasks_metrics(self):
        """Test getting metrics for all tasks."""
        from agenticaiframework import TaskEvaluator
        
        evaluator = TaskEvaluator()
        
        evaluator.record_task_execution("task_a", success=True)
        evaluator.record_task_execution("task_b", success=True)
        evaluator.record_task_execution("task_a", success=False)
        
        all_metrics = evaluator.get_task_metrics()
        
        assert "task_a" in all_metrics
        assert "task_b" in all_metrics


# =============================================================================
# 3. Tool & API Invocation Evaluations
# =============================================================================
class TestToolInvocationEvaluator:
    """Tests for Tool & API invocation evaluations."""
    
    def test_tool_evaluator_creation(self):
        """Test creating tool invocation evaluator."""
        from agenticaiframework import ToolInvocationEvaluator
        
        evaluator = ToolInvocationEvaluator()
        assert evaluator is not None
    
    def test_record_successful_tool_call(self):
        """Test recording successful tool call."""
        from agenticaiframework import ToolInvocationEvaluator
        
        evaluator = ToolInvocationEvaluator()
        
        call = evaluator.record_tool_call(
            tool_name="github_create_issue",
            parameters={"title": "Bug fix", "body": "Description"},
            success=True,
            valid_parameters=True,
            latency_ms=250
        )
        
        assert call is not None
        assert call["success"] is True
    
    def test_record_invalid_parameters(self):
        """Test recording tool call with invalid parameters."""
        from agenticaiframework import ToolInvocationEvaluator
        
        evaluator = ToolInvocationEvaluator()
        
        call = evaluator.record_tool_call(
            tool_name="jira_create_ticket",
            parameters={"invalid_field": "value"},
            success=False,
            valid_parameters=False,
            error="Missing required field: project"
        )
        
        assert call["valid_parameters"] is False
        assert call["error"] is not None
    
    def test_get_tool_metrics(self):
        """Test getting tool usage metrics."""
        from agenticaiframework import ToolInvocationEvaluator
        
        evaluator = ToolInvocationEvaluator()
        
        # Record multiple calls
        for i in range(20):
            evaluator.record_tool_call(
                tool_name="slack_send_message",
                parameters={"channel": "general", "text": f"Message {i}"},
                success=(i % 4 != 0),  # 75% success rate
                latency_ms=100 + i * 10
            )
        
        metrics = evaluator.get_tool_metrics("slack_send_message")
        
        assert metrics["total_calls"] == 20
        assert 0.7 <= metrics["success_rate"] <= 0.8
    
    def test_detect_tool_call_patterns(self):
        """Test detecting problematic tool call patterns."""
        from agenticaiframework import ToolInvocationEvaluator
        
        evaluator = ToolInvocationEvaluator()
        
        # Create pattern: high failure rate tool
        for i in range(10):
            evaluator.record_tool_call(
                tool_name="unreliable_api",
                parameters={},
                success=(i < 2),  # 20% success rate (high failure)
                latency_ms=100
            )
        
        patterns = evaluator.detect_tool_call_patterns()
        
        assert "repeated_failures" in patterns


# =============================================================================
# 4. Workflow/Orchestration Evaluations
# =============================================================================
class TestWorkflowEvaluator:
    """Tests for Workflow/Orchestration evaluations."""
    
    def test_workflow_evaluator_creation(self):
        """Test creating workflow evaluator."""
        from agenticaiframework import WorkflowEvaluator
        
        evaluator = WorkflowEvaluator()
        assert evaluator is not None
    
    def test_complete_workflow(self):
        """Test complete workflow execution."""
        from agenticaiframework import WorkflowEvaluator
        
        evaluator = WorkflowEvaluator()
        
        # Start workflow
        wf_id = evaluator.start_workflow("incident_resolution")
        
        # Record steps
        evaluator.record_step(wf_id, "detect_incident", "monitor_agent", True)
        evaluator.record_step(wf_id, "analyze_root_cause", "analysis_agent", True)
        evaluator.record_step(wf_id, "apply_fix", "remediation_agent", True)
        
        # Complete
        evaluator.complete_workflow(wf_id, success=True)
        
        metrics = evaluator.get_workflow_metrics("incident_resolution")
        assert metrics["completion_rate"] == 1.0
    
    def test_workflow_with_handoffs(self):
        """Test workflow with multiple agent handoffs."""
        from agenticaiframework import WorkflowEvaluator
        
        evaluator = WorkflowEvaluator()
        
        wf_id = evaluator.start_workflow("customer_support")
        
        evaluator.record_step(wf_id, "receive_query", "intake_agent")
        evaluator.record_step(wf_id, "retrieve_knowledge", "rag_agent")
        evaluator.record_step(wf_id, "generate_response", "generation_agent")
        evaluator.record_step(wf_id, "send_notification", "notification_agent")
        
        evaluator.complete_workflow(wf_id, success=True)
        
        workflow = evaluator.workflows[wf_id]
        assert len(workflow["steps"]) == 4
        assert len(workflow["agents"]) == 4
    
    def test_workflow_deadlock_detection(self):
        """Test workflow deadlock detection."""
        from agenticaiframework import WorkflowEvaluator
        
        evaluator = WorkflowEvaluator()
        
        wf_id = evaluator.start_workflow("complex_workflow")
        
        evaluator.record_step(wf_id, "step1", "agent1")
        evaluator.record_step(wf_id, "step2", "agent2")
        
        evaluator.complete_workflow(wf_id, success=False, deadlock=True)
        
        metrics = evaluator.get_workflow_metrics("complex_workflow")
        assert metrics["deadlock_rate"] > 0


# =============================================================================
# 5. Memory & Context Evaluations
# =============================================================================
class TestMemoryEvaluator:
    """Tests for Memory & Context evaluations."""
    
    def test_memory_evaluator_creation(self):
        """Test creating memory evaluator."""
        from agenticaiframework import MemoryEvaluator
        
        evaluator = MemoryEvaluator()
        assert evaluator is not None
    
    def test_evaluate_memory_retrieval(self):
        """Test evaluating memory retrieval."""
        from agenticaiframework import MemoryEvaluator
        
        evaluator = MemoryEvaluator()
        
        retrieved = [
            {"id": "mem1", "content": "User prefers Python"},
            {"id": "mem2", "content": "User works on AI projects"}
        ]
        
        relevant = [
            {"id": "mem1", "content": "User prefers Python"},
            {"id": "mem3", "content": "User likes TDD"}
        ]
        
        evaluation = evaluator.evaluate_memory_retrieval(
            query="What programming language does user prefer?",
            retrieved_memories=retrieved,
            relevant_memories=relevant
        )
        
        assert "precision" in evaluation
        assert "recall" in evaluation
    
    def test_stale_memory_detection(self):
        """Test detection of stale memories."""
        from agenticaiframework import MemoryEvaluator
        
        evaluator = MemoryEvaluator()
        
        # Old timestamp (> 30 days ago)
        old_timestamp = time.time() - (40 * 24 * 3600)
        
        retrieved = [
            {"id": "old_mem", "content": "Outdated info", "timestamp": old_timestamp}
        ]
        
        evaluation = evaluator.evaluate_memory_retrieval(
            query="Recent info",
            retrieved_memories=retrieved
        )
        
        assert evaluation["stale_count"] > 0
    
    def test_memory_error_tracking(self):
        """Test memory error tracking."""
        from agenticaiframework import MemoryEvaluator
        
        evaluator = MemoryEvaluator()
        
        evaluator.record_memory_error("overwrite")
        evaluator.record_memory_error("overwrite")
        
        metrics = evaluator.get_memory_metrics()
        assert metrics["memory_errors"] == 2


# =============================================================================
# 6. RAG (Knowledge Retrieval) Evaluations
# =============================================================================
class TestRAGEvaluator:
    """Tests for RAG evaluations."""
    
    def test_rag_evaluator_creation(self):
        """Test creating RAG evaluator."""
        from agenticaiframework import RAGEvaluator
        
        evaluator = RAGEvaluator()
        assert evaluator is not None
    
    def test_evaluate_rag_response(self):
        """Test evaluating RAG response."""
        from agenticaiframework import RAGEvaluator
        
        evaluator = RAGEvaluator()
        
        retrieved_docs = [
            {"id": "doc1", "content": "Python is a programming language"},
            {"id": "doc2", "content": "Python is used for AI and data science"}
        ]
        
        relevant_docs = [
            {"id": "doc1", "content": "Python is a programming language"},
            {"id": "doc3", "content": "Python has simple syntax"}
        ]
        
        evaluation = evaluator.evaluate_rag_response(
            query="What is Python?",
            retrieved_docs=retrieved_docs,
            generated_answer="Python is a programming language used for AI.",
            relevant_docs=relevant_docs
        )
        
        assert "retrieval_precision" in evaluation
        assert "retrieval_recall" in evaluation
        assert "faithfulness" in evaluation
    
    def test_faithfulness_assessment(self):
        """Test faithfulness assessment."""
        from agenticaiframework import RAGEvaluator
        
        evaluator = RAGEvaluator()
        
        docs = [
            {"content": "The capital of France is Paris"}
        ]
        
        # Faithful answer
        faithful_eval = evaluator.evaluate_rag_response(
            query="What is the capital of France?",
            retrieved_docs=docs,
            generated_answer="The capital of France is Paris"
        )
        
        # Unfaithful answer
        unfaithful_eval = evaluator.evaluate_rag_response(
            query="What is the capital of France?",
            retrieved_docs=docs,
            generated_answer="The capital of Germany is Berlin"
        )
        
        assert faithful_eval["faithfulness"] > unfaithful_eval["faithfulness"]
    
    def test_citation_detection(self):
        """Test citation detection in answers."""
        from agenticaiframework import RAGEvaluator
        
        evaluator = RAGEvaluator()
        
        docs = [{"content": "Some information"}]
        
        # Answer with citations
        eval_with_citation = evaluator.evaluate_rag_response(
            query="Question",
            retrieved_docs=docs,
            generated_answer="According to the source, the answer is X [1]."
        )
        
        # Answer without citations
        eval_without_citation = evaluator.evaluate_rag_response(
            query="Question",
            retrieved_docs=docs,
            generated_answer="The answer is X."
        )
        
        assert eval_with_citation["has_citations"] is True
        assert eval_without_citation["has_citations"] is False


# =============================================================================
# 7. Autonomy & Planning Evaluations
# =============================================================================
class TestAutonomyEvaluator:
    """Tests for Autonomy & Planning evaluations."""
    
    def test_autonomy_evaluator_creation(self):
        """Test creating autonomy evaluator."""
        from agenticaiframework import AutonomyEvaluator
        
        evaluator = AutonomyEvaluator()
        assert evaluator is not None
    
    def test_evaluate_optimal_plan(self):
        """Test evaluating optimal plan."""
        from agenticaiframework import AutonomyEvaluator
        
        evaluator = AutonomyEvaluator()
        
        plan = ["step1", "step2", "step3"]
        optimal = ["step1", "step2", "step3"]
        
        evaluation = evaluator.evaluate_plan(
            goal="Complete task",
            plan_steps=plan,
            optimal_steps=optimal,
            replanned=False,
            human_intervention=False,
            goal_achieved=True
        )
        
        assert evaluation["optimality"] == 1.0
        assert evaluation["autonomy_score"] == 1.0
    
    def test_evaluate_plan_with_replanning(self):
        """Test evaluating plan with replanning."""
        from agenticaiframework import AutonomyEvaluator
        
        evaluator = AutonomyEvaluator()
        
        evaluation = evaluator.evaluate_plan(
            goal="Deploy service",
            plan_steps=["step1", "step2", "step3", "step4"],
            replanned=True,
            goal_achieved=True
        )
        
        assert evaluation["autonomy_score"] < 1.0
    
    def test_evaluate_plan_with_human_intervention(self):
        """Test evaluating plan with human intervention."""
        from agenticaiframework import AutonomyEvaluator
        
        evaluator = AutonomyEvaluator()
        
        evaluation = evaluator.evaluate_plan(
            goal="Complex task",
            plan_steps=["step1", "step2"],
            human_intervention=True,
            goal_achieved=True
        )
        
        assert evaluation["autonomy_score"] <= 0.5
    
    def test_get_autonomy_metrics(self):
        """Test getting autonomy metrics."""
        from agenticaiframework import AutonomyEvaluator
        
        evaluator = AutonomyEvaluator()
        
        # Record multiple plans
        for i in range(10):
            evaluator.evaluate_plan(
                goal=f"Task {i}",
                plan_steps=["step1", "step2"],
                human_intervention=(i % 3 == 0),
                replanned=(i % 4 == 0),
                goal_achieved=True
            )
        
        metrics = evaluator.get_autonomy_metrics()
        
        assert metrics["total_plans"] == 10
        assert "replanning_rate" in metrics
        assert "human_intervention_rate" in metrics


# =============================================================================
# 8. Performance & Scalability Evaluations
# =============================================================================
class TestPerformanceEvaluator:
    """Tests for Performance & Scalability evaluations."""
    
    def test_performance_evaluator_creation(self):
        """Test creating performance evaluator."""
        from agenticaiframework import PerformanceEvaluator
        
        evaluator = PerformanceEvaluator()
        assert evaluator is not None
    
    def test_record_requests(self):
        """Test recording performance data."""
        from agenticaiframework import PerformanceEvaluator
        
        evaluator = PerformanceEvaluator()
        
        for i in range(100):
            evaluator.record_request(
                request_id=f"req_{i}",
                latency_ms=100 + i,
                success=(i % 10 != 0),  # 90% success rate
                concurrent_requests=1
            )
        
        metrics = evaluator.get_performance_metrics()
        
        assert metrics["total_requests"] == 100
        assert 0.08 <= metrics["failure_rate"] <= 0.12
    
    def test_latency_percentiles(self):
        """Test latency percentile calculations."""
        from agenticaiframework import PerformanceEvaluator
        
        evaluator = PerformanceEvaluator()
        
        # Record requests with varying latencies
        for i in range(100):
            evaluator.record_request(
                request_id=f"req_{i}",
                latency_ms=i * 10,  # 0ms to 990ms
                success=True
            )
        
        metrics = evaluator.get_performance_metrics()
        
        assert "latency_p50_ms" in metrics
        assert "latency_p95_ms" in metrics
        assert "latency_p99_ms" in metrics
        assert metrics["latency_p95_ms"] > metrics["latency_p50_ms"]


# =============================================================================
# 9. Human-in-the-Loop (HITL) Evaluations
# =============================================================================
class TestHITLEvaluator:
    """Tests for Human-in-the-Loop evaluations."""
    
    def test_hitl_evaluator_creation(self):
        """Test creating HITL evaluator."""
        from agenticaiframework import HITLEvaluator
        
        evaluator = HITLEvaluator()
        assert evaluator is not None
    
    def test_record_accepted_recommendation(self):
        """Test recording accepted recommendation."""
        from agenticaiframework import HITLEvaluator
        
        evaluator = HITLEvaluator()
        
        interaction = evaluator.record_escalation(
            agent_recommendation="Deploy to production",
            human_accepted=True,
            review_time_seconds=120,
            trust_score=0.9
        )
        
        assert interaction is not None
        assert interaction["accepted"] is True
    
    def test_record_overridden_decision(self):
        """Test recording overridden decision."""
        from agenticaiframework import HITLEvaluator
        
        evaluator = HITLEvaluator()
        
        interaction = evaluator.record_escalation(
            agent_recommendation="Delete database",
            human_accepted=False,
            review_time_seconds=30,
            trust_score=0.2
        )
        
        assert interaction["accepted"] is False
    
    def test_get_hitl_metrics(self):
        """Test getting HITL metrics."""
        from agenticaiframework import HITLEvaluator
        
        evaluator = HITLEvaluator()
        
        # Record multiple interactions
        for i in range(10):
            evaluator.record_escalation(
                agent_recommendation=f"Action {i}",
                human_accepted=(i % 3 != 0),  # ~67% acceptance rate
                review_time_seconds=60 + i * 10,
                trust_score=0.7 + (i * 0.01)
            )
        
        metrics = evaluator.get_hitl_metrics()
        
        assert metrics["total_escalations"] == 10
        assert 0.6 <= metrics["acceptance_rate"] <= 0.7
        assert "avg_review_time_seconds" in metrics
        assert "avg_trust_score" in metrics


# =============================================================================
# 10. Business & Outcome Evaluations
# =============================================================================
class TestBusinessOutcomeEvaluator:
    """Tests for Business & Outcome evaluations."""
    
    def test_business_evaluator_creation(self):
        """Test creating business outcome evaluator."""
        from agenticaiframework import BusinessOutcomeEvaluator
        
        evaluator = BusinessOutcomeEvaluator()
        assert evaluator is not None
    
    def test_set_baseline_and_measure_improvement(self):
        """Test setting baseline and measuring improvement."""
        from agenticaiframework import BusinessOutcomeEvaluator
        
        evaluator = BusinessOutcomeEvaluator()
        
        # Set baseline
        evaluator.set_baseline("incident_resolution_time_hours", 24.0)
        
        # Record improved values
        for i in range(10):
            evaluator.record_outcome("incident_resolution_time_hours", 12.0 + i * 0.5)
        
        impact = evaluator.get_business_impact()
        
        assert "incident_resolution_time_hours" in impact
        metric = impact["incident_resolution_time_hours"]
        assert "improvement_pct" in metric
        assert metric["improvement_pct"] < 0  # Negative = improvement (lower time)
    
    def test_record_productivity_metrics(self):
        """Test recording productivity metrics."""
        from agenticaiframework import BusinessOutcomeEvaluator
        
        evaluator = BusinessOutcomeEvaluator()
        
        # Record productivity gains
        for i in range(5):
            evaluator.record_outcome("tickets_resolved_per_day", 50 + i * 5)
        
        impact = evaluator.get_business_impact()
        
        assert "tickets_resolved_per_day" in impact
        assert impact["tickets_resolved_per_day"]["samples"] == 5
    
    def test_calculate_roi(self):
        """Test ROI calculation."""
        from agenticaiframework import BusinessOutcomeEvaluator
        
        evaluator = BusinessOutcomeEvaluator()
        
        roi_analysis = evaluator.calculate_roi(
            cost=10000,
            benefit=15000,
            time_period_days=30
        )
        
        assert roi_analysis["roi_percent"] == 50.0  # (15k-10k)/10k * 100
        assert roi_analysis["daily_benefit"] == 500.0  # 15k/30
    
    def test_negative_roi(self):
        """Test negative ROI calculation."""
        from agenticaiframework import BusinessOutcomeEvaluator
        
        evaluator = BusinessOutcomeEvaluator()
        
        roi_analysis = evaluator.calculate_roi(
            cost=20000,
            benefit=15000,
            time_period_days=30
        )
        
        assert roi_analysis["roi_percent"] == -25.0  # Negative ROI


# =============================================================================
# 11. Integration Tests - Multiple Evaluation Types
# =============================================================================
class TestEvaluationIntegrationComplete:
    """Integration tests combining multiple evaluation types."""
    
    def test_complete_agent_evaluation_pipeline(self):
        """Test complete evaluation pipeline for an agent."""
        from agenticaiframework import (
            ModelQualityEvaluator,
            TaskEvaluator,
            ToolInvocationEvaluator,
            PerformanceEvaluator,
            CostQualityScorer
        )
        
        # Initialize evaluators
        model_eval = ModelQualityEvaluator()
        task_eval = TaskEvaluator()
        tool_eval = ToolInvocationEvaluator()
        perf_eval = PerformanceEvaluator()
        cost_eval = CostQualityScorer()
        
        # Simulate agent execution
        # 1. Model generates response
        model_eval.evaluate_response(
            model_name="gpt-4",
            prompt="Create a Jira ticket for bug #123",
            response="I will create a Jira ticket with the following details..."
        )
        
        # 2. Task execution
        task_exec = task_eval.record_task_execution(
            task_name="create_jira_ticket",
            success=True,
            duration_ms=1200
        )
        
        # 3. Tool invocation
        tool_eval.record_tool_call(
            tool_name="jira_api",
            parameters={"type": "bug", "priority": "high"},
            success=True,
            latency_ms=800
        )
        
        # 4. Performance
        perf_eval.record_request(
            request_id="req_001",
            latency_ms=1200,
            success=True
        )
        
        # 5. Cost tracking
        cost_eval.record_execution(
            model_name="gpt-4",
            input_tokens=50,
            output_tokens=150,
            quality_score=0.95
        )
        
        # Verify all evaluations recorded
        assert len(model_eval.evaluations) == 1
        assert len(task_eval.task_executions) == 1
        assert len(tool_eval.tool_calls) == 1
        assert perf_eval.total_requests == 1
        assert len(cost_eval.executions) == 1
    
    def test_workflow_with_rag_and_memory(self):
        """Test workflow evaluation with RAG and memory."""
        from agenticaiframework import (
            WorkflowEvaluator,
            RAGEvaluator,
            MemoryEvaluator
        )
        
        workflow_eval = WorkflowEvaluator()
        rag_eval = RAGEvaluator()
        memory_eval = MemoryEvaluator()
        
        # Start workflow
        wf_id = workflow_eval.start_workflow("customer_support_with_rag")
        
        # Step 1: Retrieve from RAG
        rag_eval.evaluate_rag_response(
            query="How do I reset my password?",
            retrieved_docs=[{"id": "doc1", "content": "Password reset instructions"}],
            generated_answer="To reset your password, click on 'Forgot Password'."
        )
        workflow_eval.record_step(wf_id, "rag_retrieval", "rag_agent", True)
        
        # Step 2: Check memory
        memory_eval.evaluate_memory_retrieval(
            query="User preferences",
            retrieved_memories=[{"id": "pref1", "content": "User prefers email notifications"}]
        )
        workflow_eval.record_step(wf_id, "memory_check", "memory_agent", True)
        
        # Step 3: Generate response
        workflow_eval.record_step(wf_id, "generate_response", "llm_agent", True)
        
        # Complete workflow
        workflow_eval.complete_workflow(wf_id, success=True)
        
        # Verify
        workflow = workflow_eval.workflows[wf_id]
        assert len(workflow["steps"]) == 3
        assert workflow["status"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
