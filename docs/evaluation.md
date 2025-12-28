# Evaluation Framework

Complete guide to the AgenticAI Framework evaluation system, providing comprehensive assessment capabilities from model-level intelligence to business outcomes.


## Overview

The AgenticAI Framework includes a **comprehensive 12-tier evaluation system** covering every aspect of agentic AI applications:

<div class="grid cards" markdown>

-   :material-brain:{ .lg .middle } __Model-Level Evaluation__
    
    LLM quality, hallucination detection, reasoning assessment, and token efficiency monitoring.

-   :material-checkbox-marked-circle:{ .lg .middle } __Task & Skill Evaluation__
    
    Task success tracking, retry monitoring, completion percentages, and performance metrics.

-   :material-api:{ .lg .middle } __Tool & API Evaluation__
    
    Tool invocation tracking, parameter validation, latency monitoring, and error patterns.

-   :material-workflow:{ .lg .middle } __Workflow Evaluation__
    
    Multi-agent orchestration, handoff tracking, deadlock detection, and completion rates.

-   :material-memory:{ .lg .middle } __Memory & Context Evaluation__
    
    Context precision/recall, stale data detection, overwrite errors, and quality scoring.

-   :material-database-search:{ .lg .middle } __RAG Evaluation__
    
    Retrieval quality, faithfulness, groundedness, citation accuracy, and relevance.

-   :material-shield-check:{ .lg .middle } __Safety & Guardrails__
    
    Security risk scoring, PII detection, policy compliance, and content filtering.

-   :material-robot:{ .lg .middle } __Autonomy & Planning__
    
    Plan optimality, replanning tracking, human intervention, and goal drift monitoring.

-   :material-speedometer:{ .lg .middle } __Performance & Scalability__
    
    Latency percentiles (P50/P95/P99), failure rates, concurrency, and throughput analysis.

-   :material-currency-usd:{ .lg .middle } __Cost & FinOps__
    
    Token usage tracking, cost per request, budget alerts, and optimization recommendations.

-   :material-human:{ .lg .middle } __Human-in-the-Loop__
    
    Acceptance rates, override tracking, review time monitoring, and trust scoring.

-   :material-chart-line:{ .lg .middle } __Business Outcomes__
    
    ROI calculation, baseline comparison, impact metrics, and value assessment.

</div>


## Installation

The evaluation framework is included in the core AgenticAI Framework:

```bash
pip install agenticaiframework
```


## Evaluation Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│              Business Outcomes (Level 12)                │
│          ROI, Impact, Value, Productivity                │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│        Human-in-the-Loop (Level 11)                      │
│     Acceptance, Trust, Review Time                       │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│         Cost & FinOps (Level 10)                         │
│      Token Usage, Budget, Cost per Request               │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│      Performance & Scalability (Level 9)                 │
│     Latency, Throughput, Stability                       │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│       Autonomy & Planning (Level 8)                      │
│    Optimality, Replanning, Intervention                  │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│       Safety & Guardrails (Level 7)                      │
│     PII, Injection, Compliance, Security                 │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│            RAG Evaluation (Level 6)                      │
│   Retrieval, Faithfulness, Groundedness                  │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│       Memory & Context (Level 5)                         │
│    Precision, Recall, Stale Data                         │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│        Workflow Orchestration (Level 4)                  │
│     Handoffs, Deadlocks, Completion                      │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│         Tool & API Invocation (Level 3)                  │
│      Calls, Parameters, Latency, Errors                  │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│          Task & Skill Level (Level 2)                    │
│       Success, Retries, Completion                       │
└──────────────────┬──────────────────────────────────────┘
                   │
┌──────────────────┴──────────────────────────────────────┐
│            Model Quality (Level 1)                       │
│    Hallucination, Reasoning, Efficiency                  │
└─────────────────────────────────────────────────────────┘
```


## Level 1: Model Quality Evaluation

Evaluate LLM output quality, hallucination detection, and reasoning capabilities.

### ModelQualityEvaluator

```python
from agenticaiframework import ModelQualityEvaluator

# Initialize evaluator
evaluator = ModelQualityEvaluator(threshold=0.3)

# Evaluate hallucination
evaluator.evaluate_hallucination(
    text="The capital of France is Paris",
    is_hallucination=False,
    confidence=0.95
)

# Evaluate reasoning quality
evaluator.evaluate_reasoning(
    query="What is 2+2?",
    reasoning="Adding 2 and 2 together gives us 4",
    answer="4",
    correct=True
)

# Evaluate token efficiency
evaluator.evaluate_token_efficiency(
    response="Concise answer",
    token_count=50,
    quality_score=0.9
)

# Get metrics
metrics = evaluator.get_quality_metrics()
print(f"Hallucination rate: {metrics['hallucination_rate']:.2%}")
print(f"Avg reasoning quality: {metrics['avg_reasoning_quality']:.2f}")
print(f"Token efficiency: {metrics['avg_token_efficiency']:.2f}")
```

**Key Metrics:**
- Hallucination rate and false positive rate
- Average reasoning quality scores
- Token efficiency and cost optimization
- Response coherence assessment


## Level 2: Task & Skill Evaluation

Track task execution success, retries, and completion metrics.

### TaskEvaluator

```python
from agenticaiframework import TaskEvaluator

# Initialize evaluator
evaluator = TaskEvaluator()

# Record task execution
evaluator.record_task_execution(
    task_id="task_001",
    success=True,
    retries=1,
    duration=2.5
)

# Record task failure
evaluator.record_task_execution(
    task_id="task_002",
    success=False,
    retries=3,
    error="Timeout error"
)

# Get metrics
metrics = evaluator.get_task_metrics()
print(f"Success rate: {metrics['success_rate']:.2%}")
print(f"Avg retries: {metrics['avg_retries']:.2f}")
print(f"Total tasks: {metrics['total_tasks']}")
```

**Key Metrics:**
- Task success/failure rates
- Average retry counts
- Task duration statistics
- Error pattern analysis


## Level 3: Tool & API Invocation

Monitor tool calls, parameter validation, and API latency.

### ToolInvocationEvaluator

```python
from agenticaiframework import ToolInvocationEvaluator

# Initialize evaluator
evaluator = ToolInvocationEvaluator()

# Record tool call
evaluator.record_tool_call(
    tool_name="search_api",
    params={"query": "AI agents", "limit": 10},
    success=True,
    latency=0.35
)

# Record failed call
evaluator.record_tool_call(
    tool_name="database_query",
    params={"table": "users"},
    success=False,
    error="Connection timeout"
)

# Get metrics
metrics = evaluator.get_tool_metrics()
print(f"Tool success rate: {metrics['success_rate']:.2%}")
print(f"Avg latency: {metrics['avg_latency']:.3f}s")
print(f"Most used: {metrics['most_used_tool']}")
```

**Key Metrics:**
- Tool invocation success rates
- Parameter validation errors
- Average latency per tool
- Error pattern detection


## Level 4: Workflow Orchestration

Evaluate multi-agent coordination and workflow execution.

### WorkflowEvaluator

```python
from agenticaiframework import WorkflowEvaluator

# Initialize evaluator
evaluator = WorkflowEvaluator()

# Record workflow execution
evaluator.record_workflow_execution(
    workflow_id="data_pipeline",
    steps=5,
    handoffs=2,
    completed=True,
    duration=10.5
)

# Record agent handoff
evaluator.record_agent_handoff(
    from_agent="collector",
    to_agent="processor",
    success=True
)

# Detect deadlock
evaluator.detect_deadlock(
    workflow_id="stuck_workflow",
    max_wait_time=30.0
)

# Get metrics
metrics = evaluator.get_workflow_metrics()
print(f"Completion rate: {metrics['completion_rate']:.2%}")
print(f"Avg handoffs: {metrics['avg_handoffs']:.2f}")
print(f"Deadlocks detected: {metrics['deadlock_count']}")
```

**Key Metrics:**
- Workflow completion rates
- Agent handoff success
- Deadlock detection
- Average execution time


## Level 5: Memory & Context

Assess memory retrieval quality and context management.

### MemoryEvaluator

```python
from agenticaiframework import MemoryEvaluator

# Initialize evaluator
evaluator = MemoryEvaluator()

# Evaluate retrieval
evaluator.evaluate_retrieval(
    retrieved=8,      # Documents retrieved
    relevant=7,       # Relevant documents
    total_relevant=10 # Total relevant in corpus
)

# Track stale data
evaluator.record_stale_data_access(
    key="user_prefs",
    age_days=45
)

# Track overwrite error
evaluator.record_overwrite_error(
    key="config",
    error_type="concurrent_modification"
)

# Get metrics
metrics = evaluator.get_memory_metrics()
print(f"Precision: {metrics['precision']:.2%}")
print(f"Recall: {metrics['recall']:.2%}")
print(f"Stale accesses: {metrics['stale_data_accesses']}")
```

**Key Metrics:**
- Retrieval precision and recall
- Stale data access patterns
- Memory overwrite errors
- Context quality scores


## Level 6: RAG (Retrieval-Augmented Generation)

Evaluate retrieval quality, faithfulness, and groundedness.

### RAGEvaluator

```python
from agenticaiframework import RAGEvaluator

# Initialize evaluator
evaluator = RAGEvaluator()

# Evaluate retrieval
evaluator.evaluate_retrieval(
    retrieved=5,
    relevant=4,
    total_relevant=6
)

# Evaluate faithfulness
evaluator.evaluate_faithfulness(
    answer="Paris is the capital of France",
    context="France's capital city is Paris, located in the north.",
    score=0.95
)

# Evaluate groundedness
evaluator.evaluate_groundedness(
    answer="The population is 2.1 million",
    citations=["source1", "source2"],
    grounded=True
)

# Check citation accuracy
evaluator.check_citation_accuracy(
    answer="According to [1], Paris has 2.1M residents",
    citations=["source1"],
    accurate=True
)

# Get metrics
metrics = evaluator.get_rag_metrics()
print(f"Retrieval precision: {metrics['retrieval_precision']:.2%}")
print(f"Avg faithfulness: {metrics['avg_faithfulness']:.2f}")
print(f"Citation accuracy: {metrics['citation_accuracy']:.2%}")
```

**Key Metrics:**
- Retrieval precision/recall
- Faithfulness to source
- Groundedness verification
- Citation accuracy


## Level 7: Safety & Guardrails

Security risk assessment, PII detection, and policy compliance.

### SecurityRiskScorer

```python
from agenticaiframework import SecurityRiskScorer

# Initialize scorer
scorer = SecurityRiskScorer(
    max_risk_score=0.7,
    pii_detection_enabled=True
)

# Evaluate input/output
result = scorer.evaluate({
    "query": "What is your email?",
    "response": "Contact us at support@example.com"
})

print(f"Risk score: {result.score:.2f}")
print(f"PII detected: {result.data.get('pii_detected')}")
print(f"Passed: {result.passed}")

# Get scoring history
history = scorer.get_scoring_history(limit=10)
```

**Key Metrics:**
- Security risk scores
- PII detection accuracy
- Policy compliance rates
- Injection attempt detection


## Level 8: Autonomy & Planning

Evaluate agent planning quality and self-correction.

### AutonomyEvaluator

```python
from agenticaiframework import AutonomyEvaluator

# Initialize evaluator
evaluator = AutonomyEvaluator()

# Evaluate plan optimality
evaluator.evaluate_plan_optimality(
    plan_id="plan_001",
    steps=5,
    optimal_steps=4,
    quality_score=0.85
)

# Record replanning event
evaluator.record_replanning_event(
    task_id="task_001",
    reason="environment_change",
    success=True
)

# Track human intervention
evaluator.record_human_intervention(
    task_id="task_002",
    reason="approval_required",
    accepted=True
)

# Detect goal drift
evaluator.detect_goal_drift(
    original_goal="analyze_sales",
    current_state="processing_inventory",
    drift_detected=True
)

# Get metrics
metrics = evaluator.get_autonomy_metrics()
print(f"Avg optimality: {metrics['avg_plan_optimality']:.2f}")
print(f"Replanning rate: {metrics['replanning_rate']:.2%}")
print(f"Intervention rate: {metrics['intervention_rate']:.2%}")
```

**Key Metrics:**
- Plan optimality scores
- Replanning frequency
- Human intervention rates
- Goal drift detection


## Level 9: Performance & Scalability

Monitor latency, throughput, and system stability.

### PerformanceEvaluator

```python
from agenticaiframework import PerformanceEvaluator

# Initialize evaluator
evaluator = PerformanceEvaluator()

# Record executions
for _ in range(100):
    evaluator.record_execution(
        operation="llm_call",
        latency=0.5 + random.random(),
        success=random.random() > 0.05
    )

# Get metrics
metrics = evaluator.get_performance_metrics()
print(f"P50 latency: {metrics['p50_latency']:.3f}s")
print(f"P95 latency: {metrics['p95_latency']:.3f}s")
print(f"P99 latency: {metrics['p99_latency']:.3f}s")
print(f"Failure rate: {metrics['failure_rate']:.2%}")
```

**Key Metrics:**
- P50/P95/P99 latency percentiles
- Failure rate tracking
- Concurrency monitoring
- Throughput analysis


## Level 10: Cost & FinOps

Track token usage, costs, and budget optimization.

### CostQualityScorer

```python
from agenticaiframework import CostQualityScorer

# Initialize scorer
scorer = CostQualityScorer(
    max_cost_per_request=0.50,
    quality_threshold=0.70
)

# Evaluate cost vs quality
result = scorer.evaluate({
    "query": "Summarize this document",
    "cost": 0.25,
    "quality": 0.90,
    "token_count": 500
})

print(f"Cost: ${result.data['cost']:.4f}")
print(f"Quality: {result.data['quality']:.2f}")
print(f"Passed: {result.passed}")

# Get cost analysis
history = scorer.get_scoring_history(limit=100)
total_cost = sum(h.data.get('cost', 0) for h in history)
print(f"Total cost: ${total_cost:.2f}")
```

**Key Metrics:**
- Token usage tracking
- Cost per request
- Budget alerts
- Quality-adjusted cost


## Level 11: Human-in-the-Loop

Track human feedback, acceptance rates, and trust.

### HITLEvaluator

```python
from agenticaiframework import HITLEvaluator

# Initialize evaluator
evaluator = HITLEvaluator()

# Record human review
evaluator.record_review(
    decision_id="dec_001",
    accepted=True,
    review_time=25.0,
    overridden=False
)

# Record override
evaluator.record_override(
    decision_id="dec_002",
    original_decision="approve",
    human_decision="reject",
    reason="policy_violation"
)

# Record trust signal
evaluator.record_trust_signal(
    decision_id="dec_003",
    feedback="helpful",
    confidence=0.9
)

# Get metrics
metrics = evaluator.get_hitl_metrics()
print(f"Acceptance rate: {metrics['acceptance_rate']:.2%}")
print(f"Override rate: {metrics['override_rate']:.2%}")
print(f"Avg review time: {metrics['avg_review_time']:.1f}s")
print(f"Trust score: {metrics['trust_score']:.2f}")
```

**Key Metrics:**
- Human acceptance rates
- Override tracking
- Review time monitoring
- Trust score calculation


## Level 12: Business Outcomes

Measure ROI, impact, and business value.

### BusinessOutcomeEvaluator

```python
from agenticaiframework import BusinessOutcomeEvaluator

# Initialize evaluator
evaluator = BusinessOutcomeEvaluator()

# Set baseline
evaluator.set_baseline(
    metric="response_time",
    value=2.0
)

evaluator.set_baseline(
    metric="customer_satisfaction",
    value=0.75
)

# Record outcomes
evaluator.record_outcome(
    metric="response_time",
    value=1.5,
    cost=100.0,
    revenue=500.0
)

evaluator.record_outcome(
    metric="customer_satisfaction",
    value=0.85,
    cost=50.0,
    revenue=300.0
)

# Get metrics
metrics = evaluator.get_business_metrics()
print(f"ROI: {metrics['roi']:.2%}")
print(f"Total improvement: {metrics['total_improvement']:.2%}")
print(f"Revenue: ${metrics['total_revenue']:.2f}")
```

**Key Metrics:**
- ROI calculation
- Baseline comparisons
- Impact metrics
- Value assessment


## Complete Evaluation Pipeline

Combine all evaluation types for comprehensive assessment:

```python
from agenticaiframework import (
    ModelQualityEvaluator,
    TaskEvaluator,
    ToolInvocationEvaluator,
    WorkflowEvaluator,
    MemoryEvaluator,
    RAGEvaluator,
    SecurityRiskScorer,
    AutonomyEvaluator,
    PerformanceEvaluator,
    CostQualityScorer,
    HITLEvaluator,
    BusinessOutcomeEvaluator
)

class ComprehensiveEvaluator:
    """Complete evaluation pipeline for agentic applications."""
    
    def __init__(self):
        # Initialize all evaluators
        self.model_eval = ModelQualityEvaluator(threshold=0.3)
        self.task_eval = TaskEvaluator()
        self.tool_eval = ToolInvocationEvaluator()
        self.workflow_eval = WorkflowEvaluator()
        self.memory_eval = MemoryEvaluator()
        self.rag_eval = RAGEvaluator()
        self.security_scorer = SecurityRiskScorer()
        self.autonomy_eval = AutonomyEvaluator()
        self.perf_eval = PerformanceEvaluator()
        self.cost_scorer = CostQualityScorer(max_cost_per_request=0.5)
        self.hitl_eval = HITLEvaluator()
        self.business_eval = BusinessOutcomeEvaluator()
    
    def evaluate_agent_execution(self, execution_data):
        """Evaluate a complete agent execution across all levels."""
        
        # Level 1: Model Quality
        self.model_eval.evaluate_hallucination(
            text=execution_data['output'],
            is_hallucination=False,
            confidence=0.95
        )
        
        # Level 2: Task Success
        self.task_eval.record_task_execution(
            task_id=execution_data['task_id'],
            success=execution_data['success'],
            retries=execution_data.get('retries', 0)
        )
        
        # Level 3: Tool Calls
        for tool_call in execution_data.get('tool_calls', []):
            self.tool_eval.record_tool_call(
                tool_name=tool_call['name'],
                params=tool_call['params'],
                success=tool_call['success'],
                latency=tool_call['latency']
            )
        
        # Level 4: Workflow
        if execution_data.get('workflow_id'):
            self.workflow_eval.record_workflow_execution(
                workflow_id=execution_data['workflow_id'],
                steps=execution_data['steps'],
                handoffs=execution_data.get('handoffs', 0),
                completed=execution_data['success']
            )
        
        # Level 5: Memory
        if execution_data.get('memory_retrieval'):
            self.memory_eval.evaluate_retrieval(
                retrieved=execution_data['memory_retrieval']['retrieved'],
                relevant=execution_data['memory_retrieval']['relevant'],
                total_relevant=execution_data['memory_retrieval']['total']
            )
        
        # Level 6: RAG
        if execution_data.get('rag_enabled'):
            self.rag_eval.evaluate_faithfulness(
                answer=execution_data['output'],
                context=execution_data['context'],
                score=execution_data['faithfulness_score']
            )
        
        # Level 7: Security
        security_result = self.security_scorer.evaluate({
            'query': execution_data['input'],
            'response': execution_data['output']
        })
        
        # Level 8: Autonomy
        if execution_data.get('plan_id'):
            self.autonomy_eval.evaluate_plan_optimality(
                plan_id=execution_data['plan_id'],
                steps=execution_data['steps'],
                optimal_steps=execution_data.get('optimal_steps', execution_data['steps'])
            )
        
        # Level 9: Performance
        self.perf_eval.record_execution(
            operation='agent_execution',
            latency=execution_data['duration'],
            success=execution_data['success']
        )
        
        # Level 10: Cost
        cost_result = self.cost_scorer.evaluate({
            'query': execution_data['input'],
            'cost': execution_data['cost'],
            'quality': execution_data.get('quality_score', 0.8)
        })
        
        # Level 11: HITL
        if execution_data.get('human_review'):
            self.hitl_eval.record_review(
                decision_id=execution_data['task_id'],
                accepted=execution_data['human_review']['accepted'],
                review_time=execution_data['human_review']['time'],
                overridden=execution_data['human_review'].get('overridden', False)
            )
        
        # Level 12: Business
        if execution_data.get('business_metric'):
            self.business_eval.record_outcome(
                metric=execution_data['business_metric'],
                value=execution_data['business_value'],
                cost=execution_data['cost'],
                revenue=execution_data.get('revenue', 0)
            )
        
        return self.get_all_metrics()
    
    def get_all_metrics(self):
        """Get comprehensive metrics from all evaluators."""
        return {
            'model_quality': self.model_eval.get_quality_metrics(),
            'task_success': self.task_eval.get_task_metrics(),
            'tool_performance': self.tool_eval.get_tool_metrics(),
            'workflow': self.workflow_eval.get_workflow_metrics(),
            'memory': self.memory_eval.get_memory_metrics(),
            'rag': self.rag_eval.get_rag_metrics(),
            'autonomy': self.autonomy_eval.get_autonomy_metrics(),
            'performance': self.perf_eval.get_performance_metrics(),
            'hitl': self.hitl_eval.get_hitl_metrics(),
            'business': self.business_eval.get_business_metrics()
        }

# Usage
evaluator = ComprehensiveEvaluator()

# Evaluate agent execution
metrics = evaluator.evaluate_agent_execution({
    'task_id': 'task_001',
    'input': 'Analyze sales data',
    'output': 'Sales increased by 15%',
    'success': True,
    'duration': 2.5,
    'cost': 0.15,
    'quality_score': 0.9,
    'tool_calls': [
        {'name': 'database_query', 'params': {}, 'success': True, 'latency': 0.5}
    ],
    'workflow_id': 'analytics_workflow',
    'steps': 3,
    'plan_id': 'plan_001'
})

print("Comprehensive Evaluation Metrics:")
for level, metrics_data in metrics.items():
    print(f"\n{level.upper()}:")
    for key, value in metrics_data.items():
        print(f"  {key}: {value}")
```


## Best Practices

### 1. **Layer Your Evaluations**
Start with basic model quality and gradually add more evaluation layers as your application matures.

### 2. **Set Appropriate Thresholds**
Configure thresholds based on your specific use case and risk tolerance.

### 3. **Monitor Continuously**
Use online evaluation for real-time production monitoring.

### 4. **Use Offline Testing**
Test with comprehensive datasets before deploying to production.

### 5. **Track Trends**
Monitor metrics over time to identify degradation or improvements.

### 6. **Correlate Metrics**
Look for correlations between different evaluation levels (e.g., cost vs. quality).

### 7. **Automate Alerts**
Set up automated alerts for critical metrics exceeding thresholds.

### 8. **Regular Audits**
Perform regular comprehensive audits across all evaluation levels.


## Next Steps

- :octicons-book-24: [API Reference](API_REFERENCE.md) - Detailed API documentation
- :octicons-code-24: [Examples](EXAMPLES.md) - Complete code examples
- :octicons-rocket-24: [Quick Start](quick-start.md) - Get started guide
- :octicons-shield-check-24: [Best Practices](best-practices.md) - Production patterns


## Additional Resources

- [EVALUATION_FRAMEWORK.md](../EVALUATION_FRAMEWORK.md) - Detailed implementation guide
- [EVALUATION_IMPLEMENTATION_SUMMARY.md](../EVALUATION_IMPLEMENTATION_SUMMARY.md) - Complete implementation summary
- [Test Suite](../tests/test_all_evaluation_types.py) - Comprehensive test examples
