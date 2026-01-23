---
title: API Reference
description: Complete API documentation for all 380+ modules including classes, methods, and functions
tags:
  - API
  - reference
  - documentation
  - modules
---

# 📖 API Reference

<div class="annotate" markdown>

**Complete API documentation for all 380+ modules**

Detailed reference for classes, methods, and functions across **237 enterprise features**

</div>

!!! success "Enterprise API"
    Full API coverage for all enterprise modules. See [Enterprise Documentation](enterprise.md) for advanced APIs.

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :material-robot:{ .lg } **Agents**
    
    Agent classes and methods
    
    [:octicons-arrow-right-24: View](#agenticaiframeworkagents)

-   :material-checkbox-marked:{ .lg } **Tasks**
    
    Task management API
    
    [:octicons-arrow-right-24: View](#agenticaiframeworktasks)

-   :material-memory:{ .lg } **Memory**
    
    Memory system API
    
    [:octicons-arrow-right-24: View](#agenticaiframeworkmemory)

-   :material-brain:{ .lg } **LLMs**
    
    LLM integration API
    
    [:octicons-arrow-right-24: View](#agenticaiframeworkllms)

-   :material-shield-check:{ .lg } **Guardrails**
    
    Safety and validation API
    
    [:octicons-arrow-right-24: View](#agenticaiframeworkguardrails)

-   :material-database:{ .lg } **Knowledge**
    
    Knowledge base API
    
    [:octicons-arrow-right-24: View](#agenticaiframeworkknowledge)

</div>


## Module Overview

### agenticaiframework.agents

**Classes:**
- `Agent(name, role, capabilities, config)` – Base agent class
- `AgentManager()` – Multi-agent orchestration
- `ContextManager(max_tokens)` – Context window management

**Agent Methods:**
- `start()` – Start the agent
- `pause()` – Pause agent execution
- `resume()` – Resume agent execution
- `stop()` – Stop the agent
- `execute_task(task_callable, *args, **kwargs)` – Execute a task

**AgentManager Methods:**
- `register_agent(agent)` – Register an agent
- `get_agent(agent_id)` – Get agent by ID
- `list_agents()` – List all agents
- `remove_agent(agent_id)` – Remove an agent
- `broadcast(message)` – Broadcast to all agents

**ContextManager Methods:**
- `add_context(content, importance)` – Add context with importance weighting
- `get_context_summary()` – Get context summary
- `get_stats()` – Get context statistics
- `clear()` – Clear context

### agenticaiframework.communication

**Classes:**
- `CommunicationManager()` – Protocol-based communication

**Methods:**
- `register_protocol(name, handler_fn)` – Register communication protocol
- `register_handler(handler_fn, name)` – Register handler (alias)
- `send(protocol, data)` – Send data via protocol
- `send_message(message, protocol)` – Send message
- `list_protocols()` – List registered protocols

### agenticaiframework.configurations

**Classes:**
- `ConfigurationManager()` – Configuration management

**Methods:**
- `set(key, value)` – Set configuration value
- `get(key, default)` – Get configuration value
- `update(config_dict)` – Update multiple values
- `remove(key)` – Remove configuration
- `list_configs()` – List all configurations

### agenticaiframework.evaluation

**Basic Evaluation:**
- `EvaluationSystem()` – Core evaluation and scoring
- `define_criterion(name, evaluator_fn)` – Define evaluation metric
- `evaluate(data)` – Evaluate data against criteria
- `get_results()` – Get evaluation results

**Comprehensive 12-Tier Evaluation Framework:**

**Level 1 - Model Quality:**
- `ModelQualityEvaluator(threshold)` – LLM quality assessment
  - `evaluate_hallucination(text, is_hallucination, confidence)` – Detect hallucinations
  - `evaluate_reasoning(query, reasoning, answer, correct)` – Assess reasoning quality
  - `evaluate_token_efficiency(response, token_count, quality_score)` – Token efficiency
  - `get_quality_metrics()` – Get model quality metrics

**Level 2 - Task & Skill:**
- `TaskEvaluator()` – Task execution assessment
  - `record_task_execution(task_id, success, retries, duration)` – Track task execution
  - `get_task_metrics()` – Get task success metrics

**Level 3 - Tool & API:**
- `ToolInvocationEvaluator()` – Tool call monitoring
  - `record_tool_call(tool_name, params, success, latency, error)` – Track tool invocations
  - `get_tool_metrics()` – Get tool performance metrics

**Level 4 - Workflow:**
- `WorkflowEvaluator()` – Multi-agent orchestration
  - `record_workflow_execution(workflow_id, steps, handoffs, completed)` – Track workflows
  - `record_agent_handoff(from_agent, to_agent, success)` – Monitor handoffs
  - `detect_deadlock(workflow_id, max_wait_time)` – Detect deadlocks
  - `get_workflow_metrics()` – Get workflow metrics

**Level 5 - Memory & Context:**
- `MemoryEvaluator()` – Memory quality assessment
  - `evaluate_retrieval(retrieved, relevant, total_relevant)` – Assess retrieval quality
  - `record_stale_data_access(key, age_days)` – Track stale data
  - `record_overwrite_error(key, error_type)` – Monitor overwrites
  - `get_memory_metrics()` – Get memory metrics

**Level 6 - RAG:**
- `RAGEvaluator()` – Retrieval-augmented generation assessment
  - `evaluate_retrieval(retrieved, relevant, total_relevant)` – Retrieval quality
  - `evaluate_faithfulness(answer, context, score)` – Faithfulness to source
  - `evaluate_groundedness(answer, citations, grounded)` – Groundedness check
  - `check_citation_accuracy(answer, citations, accurate)` – Citation accuracy
  - `get_rag_metrics()` – Get RAG metrics

**Level 7 - Safety:**
- `SecurityRiskScorer(max_risk_score, pii_detection_enabled)` – Security assessment
  - `evaluate(data)` – Assess security risks
  - `get_scoring_history(limit)` – Get scoring history

**Level 8 - Autonomy:**
- `AutonomyEvaluator()` – Autonomy and planning assessment
  - `evaluate_plan_optimality(plan_id, steps, optimal_steps, quality_score)` – Plan quality
  - `record_replanning_event(task_id, reason, success)` – Track replanning
  - `record_human_intervention(task_id, reason, accepted)` – Monitor interventions
  - `detect_goal_drift(original_goal, current_state, drift_detected)` – Goal drift
  - `get_autonomy_metrics()` – Get autonomy metrics

**Level 9 - Performance:**
- `PerformanceEvaluator()` – Performance and scalability
  - `record_execution(operation, latency, success)` – Track performance
  - `get_performance_metrics()` – Get performance metrics (P50/P95/P99)

**Level 10 - Cost:**
- `CostQualityScorer(max_cost_per_request, quality_threshold)` – Cost analysis
  - `evaluate(data)` – Evaluate cost vs quality
  - `get_scoring_history(limit)` – Get cost history

**Level 11 - HITL:**
- `HITLEvaluator()` – Human-in-the-loop assessment
  - `record_review(decision_id, accepted, review_time, overridden)` – Track reviews
  - `record_override(decision_id, original_decision, human_decision, reason)` – Monitor overrides
  - `record_trust_signal(decision_id, feedback, confidence)` – Trust signals
  - `get_hitl_metrics()` – Get HITL metrics

**Level 12 - Business:**
- `BusinessOutcomeEvaluator()` – Business outcome assessment
  - `set_baseline(metric, value)` – Establish baselines
  - `record_outcome(metric, value, cost, revenue)` – Track business outcomes
  - `get_business_metrics()` – Get business metrics

**Advanced Evaluation:**
- `OfflineEvaluator(test_dataset, evaluators)` – Batch offline evaluation
- `OnlineEvaluator(evaluators, alert_config)` – Real-time online evaluation
- `ABTestingFramework()` – A/B testing and experimentation
- `CanaryDeploymentManager()` – Canary deployment evaluation

### agenticaiframework.guardrails

**Classes:**
- `Guardrail(name, validation_fn, policy, severity)` – Single guardrail
- `GuardrailManager()` – Guardrail orchestration

**Guardrail Methods:**
- `validate(data)` – Validate data
- `get_stats()` – Get guardrail statistics

**GuardrailManager Methods:**
- `register_guardrail(guardrail)` – Register guardrail
- `enforce_guardrails(data)` – Enforce all guardrails
- `get_guardrail_by_name(name)` – Get guardrail by name
- `list_guardrails()` – List all guardrails

### agenticaiframework.hub

**Classes:**
- `Hub()` – Agent and tool registry

**Methods:**
- `register_agent(name, agent_class)` – Register agent class
- `get_agent(name)` – Get registered agent
- `list_agents()` – List agents
- `remove_agent(name)` – Remove agent
- `register_tool(name, tool_fn)` – Register tool
- `get_tool(name)` – Get tool

### agenticaiframework.knowledge

**Classes:**
- `KnowledgeRetriever()` – Knowledge base operations

**Methods:**
- `register_source(name, source_fn)` – Register knowledge source
- `retrieve(query, source)` – Retrieve knowledge
- `clear_cache()` – Clear retrieval cache

### agenticaiframework.llms

**Classes:**
- `LLMManager()` – LLM lifecycle management
- `CircuitBreaker(failure_threshold)` – Circuit breaker for reliability

**LLMManager Methods:**
- `register_model(name, model_instance)` – Register LLM
- `set_active_model(name)` – Set active model
- `generate(prompt, **kwargs)` – Generate response
- `list_models()` – List registered models

**CircuitBreaker Methods:**
- `call(fn, *args, **kwargs)` – Execute with circuit breaker
- `reset()` – Reset circuit breaker state

### agenticaiframework.mcp_tools

**Classes:**
- `MCPToolManager()` – MCP tool management

**Methods:**
- `register_tool(name, tool_fn)` – Register MCP tool
- `invoke_tool(name, *args, **kwargs)` – Invoke tool
- `list_tools()` – List registered tools

### agenticaiframework.memory

**Classes:**
- `MemoryEntry(key, value, ttl, priority, metadata)` – Memory entry
- `MemoryManager(short_term_limit, long_term_limit)` – Multi-tier memory

**MemoryManager Methods:**
- `store(key, value, memory_type, ttl, priority, metadata)` – Store memory
- `retrieve(key)` – Retrieve memory
- `search(query)` – Search memories
- `consolidate()` – Consolidate memories
- `get_stats()` – Get memory statistics
- `clear_short_term()` – Clear short-term memory
- `clear_long_term()` – Clear long-term memory
- `clear_external()` – Clear external memory
- `clear_all()` – Clear all memory

### agenticaiframework.monitoring

**Classes:**
- `MonitoringSystem()` – System monitoring

**Methods:**
- `log(message, level)` – Log message
- `track_metric(name, value)` – Track metric
- `create_alert(name, condition_fn)` – Create alert
- `get_metrics()` – Get metrics

### agenticaiframework.processes

**Classes:**
- `Process(name, steps)` – Process definition

**Methods:**
- `run(*args, **kwargs)` – Run process
- `run_async(*args, **kwargs)` – Run process asynchronously

### agenticaiframework.prompts

**Classes:**
- `Prompt(template, metadata, enable_security)` – Prompt template
- `PromptManager(enable_security)` – Prompt management

**Prompt Methods:**
- `render(**kwargs)` – Render prompt
- `render_safe(**kwargs)` – Render with sanitization
- `update_template(new_template)` – Update template

**PromptManager Methods:**
- `register_prompt(prompt)` – Register prompt
- `get_prompt(prompt_id)` – Get prompt by ID
- `render_prompt(prompt_id, **kwargs)` – Render prompt
- `list_prompts()` – List prompts
- `delete_prompt(prompt_id)` – Delete prompt

### agenticaiframework.security

**Classes:**
- `PromptInjectionDetector(enable_logging, custom_patterns)` – Injection detection
- `InputValidator(max_length, allow_html, allow_scripts)` – Input validation
- `RateLimiter(max_requests, window_seconds, strategy)` – Rate limiting
- `ContentFilter(blocked_words, categories, severity_threshold)` – Content filtering
- `AuditLogger(log_file, retention_days, log_level)` – Audit logging
- `SecurityManager(enable_*)` – Unified security management

**PromptInjectionDetector Methods:**
- `detect(text)` – Detect injection attempts
- `add_pattern(pattern, severity)` – Add detection pattern
- `get_stats()` – Get detection statistics

**InputValidator Methods:**
- `validate(text)` – Validate input
- `sanitize(text)` – Sanitize input
- `sanitize_html(text)` – Remove HTML
- `sanitize_sql(text)` – Remove SQL injection patterns

**RateLimiter Methods:**
- `check_rate_limit(identifier)` – Check rate limit
- `get_remaining(identifier)` – Get remaining requests
- `reset(identifier)` – Reset rate limit

**ContentFilter Methods:**
- `filter_text(text)` – Filter content
- `add_blocked_word(word, category)` – Add blocked word
- `get_stats()` – Get filter statistics

**AuditLogger Methods:**
- `log_event(event_type, details)` – Log security event
- `query_logs(filters)` – Query logs
- `clear_old_logs()` – Clear old logs

**SecurityManager Methods:**
- `validate_input(text, user_id)` – Comprehensive validation
- `get_security_report()` – Get security report

### agenticaiframework.tasks

**Classes:**
- `Task(name, description, callable_fn)` – Task definition
- `TaskManager()` – Task orchestration

**Task Methods:**
- `run(*args, **kwargs)` – Run task
- `get_result()` – Get task result

**TaskManager Methods:**
- `register_task(task)` – Register task
- `run_task(task_id, *args, **kwargs)` – Run task
- `run_all()` – Run all tasks
- `list_tasks()` – List tasks

---

## 📝 Usage Examples

### Using Multiple Modules Together

```python
from agenticaiframework import Agent, AgentManager
from agenticaiframework.memory import MemoryManager

# Create and register agent
agent = Agent(name="MyAgent", role="assistant", capabilities=["text"])
manager = AgentManager()
manager.register_agent(agent)

# Use memory
memory = MemoryManager()
memory.store("greeting", "Hello, World!")

# Agent action with memory
result = agent.act(memory.retrieve("greeting"))
print(result)
```

### Custom Process with Guardrails

```python
from agenticaiframework.guardrails import GuardrailManager

# Create guardrail manager
guardrails = GuardrailManager()

# Add validation guardrail
def no_numbers(input_data):
    if any(char.isdigit() for char in input_data):
        raise ValueError("Numbers are not allowed!")
    return input_data

guardrails.add_guardrail("no_numbers", no_numbers)

# Validate input
result = guardrails.enforce_guardrails("Hello World")
print(result)
```

---

## ⚠️ API Stability Notes

!!! info "Versioning Policy"
    - Public APIs follow semantic versioning
    - Experimental APIs are marked in documentation and may change
    - Deprecated APIs will be marked with warnings before removal

---

## 📚 Related Documentation

- [Usage Guide](USAGE.md)
- [Examples](EXAMPLES.md)
- [Extending the Framework](EXTENDING.md)
