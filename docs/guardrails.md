---
title: Guardrails
description: Enforce safety, compliance, and quality constraints on AI-generated outputs
tags:
  - guardrails
  - safety
  - security
  - compliance
  - policies
  - content-safety
  - validation
---

# 🛡️ Guardrails

<div class="annotate" markdown>

**Enforce safety, compliance, and quality constraints**

Protect your AI applications with intelligent validation and content moderation across **400+ modules**

</div>

!!! success "Enterprise Compliance"
    Part of **237 enterprise modules** with **18 compliance & audit features**. See [Enterprise Documentation](enterprise.md).

---

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :material-shield-check:{ .lg } **Core Guardrails**
    
    Basic validation and enforcement
    
    [:octicons-arrow-right-24: Configure](#core-components)

-   :material-brain:{ .lg } **Specialized**
    
    Semantic, safety, format validation
    
    [:octicons-arrow-right-24: Explore](#specialized-guardrails)

-   :material-pipe:{ .lg } **Pipeline**
    
    Chain multiple guardrails
    
    [:octicons-arrow-right-24: Build](#guardrail-pipeline)

-   :material-gavel:{ .lg } **Policies**
    
    Behavior and resource policies
    
    [:octicons-arrow-right-24: Define](#agent-policy-framework)

</div>

## 📖 Overview

!!! abstract "What are Guardrails?"
    
    Guardrails enforce safety, compliance, and quality constraints on AI-generated outputs, ensuring responses adhere to predefined rules, ethical guidelines, and domain-specific requirements.

!!! success "Enterprise Security"
    
    The framework includes **18 security & compliance modules** for enterprise-grade protection with encryption, authentication, PII detection, and audit logging.

<div class="grid" markdown>

:material-shield-alert:{ .lg } **Input Validation**
:   Check user inputs before processing

:material-filter:{ .lg } **Content Filtering**
:   Remove harmful or inappropriate content

:material-gavel:{ .lg } **Policy Enforcement**
:   Ensure compliance with regulations

:material-check-circle:{ .lg } **Output Verification**
:   Validate AI responses before delivery

</div>

## Core Components

### Guardrail Class

The `Guardrail` class defines individual validation rules with priority and severity levels.

#### Constructor

```python
Guardrail(
    name: str,
    validation_fn: Callable[[Any], bool],
    policy: dict[str, Any] = None,
    severity: str = "medium"
)
```

**Parameters:**

- **`name`** *(str)*: Unique identifier for the guardrail
- **`validation_fn`** *(Callable[[Any], bool])*: Function that returns True if validation passes
- **`policy`** *(dict[str, Any])*: Policy configuration (e.g., priority, max_retries)
- **`severity`** *(str)*: Severity level ("low", "medium", "high", "critical")

#### Methods

```python
def validate(data: Any) -> bool
def get_stats() -> dict[str, Any]
```

**Example:**

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.guardrails import Guardrail

# Create a guardrail
age_check = Guardrail(
    name="age_verification",
    validation_fn=lambda x: x.get('age', 0) >= 18,
    policy={"priority": 10},
    severity="high"
)

# Validate data
user_data = {"age": 25, "name": "Alice"}
is_valid = age_check.validate(user_data)
logger.info(f"Validation result: {is_valid}")

# Get statistics
stats = age_check.get_stats()
logger.info(f"Validation count: {stats['validation_count']}")
logger.info(f"Violation rate: {stats['violation_rate']:.2%}")
```

### GuardrailManager Class

The `GuardrailManager` orchestrates multiple guardrails with priority-based enforcement.

#### Key Methods

```python
def register_guardrail(guardrail: Guardrail) -> None
def enforce_guardrails(data: Any) -> dict[str, Any]
def get_guardrail_by_name(name: str) -> Guardrail | None
def list_guardrails() -> list[Guardrail]
```

**Example:**

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.guardrails import Guardrail, GuardrailManager

# Create manager
manager = GuardrailManager()

# Register multiple guardrails
manager.register_guardrail(Guardrail(
    name="range_check",
    validation_fn=lambda x: 0 <= x <= 100,
    severity="medium"
))

manager.register_guardrail(Guardrail(
    name="type_check",
    validation_fn=lambda x: isinstance(x, (int, float)),
    severity="critical"
))

# Enforce all guardrails
result = manager.enforce_guardrails(50)
logger.info(f"Valid: {result['is_valid']}")
logger.info(f"Violations: {result.get('violations', [])}")
```

## Use Cases
- Preventing the disclosure of sensitive or confidential information.
- Enforcing compliance with legal and regulatory requirements.
- Maintaining brand voice and tone consistency.
- Filtering out harmful, biased, or toxic content.

---

## 🎯 Specialized Guardrails

The framework provides pre-built guardrails for common validation scenarios.

### SemanticGuardrail

Validates content based on semantic meaning and intent:

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.guardrails import SemanticGuardrail

# Create semantic guardrail
semantic = SemanticGuardrail(
    name="topic_guardrail",
    allowed_topics=["technology", "science", "education"],
    blocked_topics=["violence", "illegal activities"],
    similarity_threshold=0.75
)

# Validate content
result = semantic.validate("Explain quantum computing basics")
logger.info(f"Valid: {result.is_valid}")
logger.info(f"Detected topics: {result.detected_topics}")
```

### ContentSafetyGuardrail

Comprehensive content safety checking:

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.guardrails import ContentSafetyGuardrail

# Create content safety guardrail
content_safety = ContentSafetyGuardrail(
    name="content_filter",
    check_toxicity=True,
    check_profanity=True,
    check_pii=True,
    toxicity_threshold=0.7
)

# Validate content
result = content_safety.validate("Check this message for safety issues")
logger.info(f"Safe: {result.is_valid}")
logger.info(f"Flags: {result.flags}")
```

### OutputFormatGuardrail

Validates output format and structure:

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.guardrails import OutputFormatGuardrail

# Create format guardrail for JSON output
format_guard = OutputFormatGuardrail(
    name="json_format",
    expected_format="json",
    required_fields=["result", "confidence", "sources"],
    max_length=5000
)

# Validate output
output = '{"result": "answer", "confidence": 0.95, "sources": ["doc1"]}'
result = format_guard.validate(output)
logger.info(f"Format valid: {result.is_valid}")
```

### ChainOfThoughtGuardrail

Validates reasoning chains for quality:

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.guardrails import ChainOfThoughtGuardrail

# Create CoT guardrail
cot_guard = ChainOfThoughtGuardrail(
    name="reasoning_check",
    min_steps=3,
    require_conclusion=True,
    check_logical_flow=True
)

# Validate reasoning
reasoning = """
Step 1: Identify the problem
Step 2: Analyze the data
Step 3: Draw conclusions
Conclusion: Based on the analysis, the answer is X.
"""
result = cot_guard.validate(reasoning)
logger.info(f"Valid reasoning: {result.is_valid}")
```

### ToolUseGuardrail

Validates tool invocations:

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.guardrails import ToolUseGuardrail

# Create tool use guardrail
tool_guard = ToolUseGuardrail(
    name="tool_validator",
    allowed_tools=["file_read", "web_search", "calculator"],
    blocked_tools=["system_exec", "delete_file"],
    max_tool_calls=10
)

# Validate tool invocation
result = tool_guard.validate({
    "tool": "file_read",
    "params": {"path": "/data/config.json"}
})
logger.info(f"Tool allowed: {result.is_valid}")
```

---

## 🔗 Guardrail Pipeline

Chain multiple guardrails for comprehensive validation:

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.guardrails import (
    GuardrailPipeline,
    ContentSafetyGuardrail,
    OutputFormatGuardrail,
    SemanticGuardrail
)

# Create pipeline
pipeline = GuardrailPipeline(name="output_pipeline")

# Add guardrails in order
pipeline.add_guardrail(ContentSafetyGuardrail(
    name="safety",
    check_toxicity=True,
    check_pii=True
))

pipeline.add_guardrail(SemanticGuardrail(
    name="topic",
    allowed_topics=["technical", "support"]
))

pipeline.add_guardrail(OutputFormatGuardrail(
    name="format",
    expected_format="json"
))

# Execute pipeline
result = pipeline.execute(content)
logger.info(f"All passed: {result.all_passed}")
logger.info(f"Failed guardrails: {result.failures}")
```

---

## 📜 Agent Policy Framework

Define and enforce policies on agent behavior.

### Policy Types

| Type | Description |
|------|-------------|
| `BehaviorPolicy` | Controls agent behavior constraints |
| `ResourcePolicy` | Manages resource access and limits |
| `SafetyPolicy` | Enforces safety requirements |

### PolicyScope

```python
from agenticaiframework.guardrails import PolicyScope

PolicyScope.GLOBAL    # Applies to all agents
PolicyScope.TEAM      # Applies to agent team
PolicyScope.AGENT     # Applies to specific agent
PolicyScope.TASK      # Applies to specific task
```

### PolicyEnforcement

```python
from agenticaiframework.guardrails import PolicyEnforcement

PolicyEnforcement.STRICT   # Block on violation
PolicyEnforcement.WARN     # Warn but allow
PolicyEnforcement.LOG      # Log only
```

### Creating Policies

```python
from agenticaiframework.guardrails import (
    BehaviorPolicy,
    ResourcePolicy,
    SafetyPolicy,
    AgentPolicyManager,
    PolicyScope,
    PolicyEnforcement,
    agent_policy_manager
)

# Create a behavior policy
behavior_policy = BehaviorPolicy(
    name="production_behavior",
    scope=PolicyScope.GLOBAL,
    enforcement=PolicyEnforcement.STRICT,
    max_tokens_per_response=2000,
    max_tool_calls_per_task=5,
    require_reasoning=True,
    timeout_seconds=30
)

# Create a resource policy
resource_policy = ResourcePolicy(
    name="resource_limits",
    scope=PolicyScope.TEAM,
    max_memory_mb=512,
    max_concurrent_tasks=10,
    allowed_external_apis=["openai", "anthropic"],
    blocked_file_paths=["/etc", "/var/log"]
)

# Create a safety policy
safety_policy = SafetyPolicy(
    name="enterprise_safety",
    scope=PolicyScope.GLOBAL,
    enforcement=PolicyEnforcement.STRICT,
    block_pii=True,
    block_secrets=True,
    content_moderation=True,
    max_risk_score=0.3
)

# Register policies
agent_policy_manager.register_behavior_policy("prod", behavior_policy)
agent_policy_manager.register_resource_policy("limits", resource_policy)
agent_policy_manager.register_safety_policy("enterprise", safety_policy)
```

### Enforcing Policies

```python
import logging

logger = logging.getLogger(__name__)

# Apply policies to an agent
agent_policy_manager.apply_policies(
    agent_id="agent-001",
    policy_names=["production_behavior", "resource_limits", "enterprise_safety"]
)

# Check policy compliance
compliance = agent_policy_manager.check_compliance(
    agent_id="agent-001",
    action="tool_call",
    context={"tool": "file_read", "path": "/data/config.json"}
)

if not compliance.is_allowed:
    logger.info(f"Policy violation: {compliance.violated_policy}")
    logger.info(f"Reason: {compliance.reason}")
```

---

## 📊 Guardrail Types Summary

| Guardrail | Purpose |
|-----------|---------|
| `SemanticGuardrail` | Topic and intent validation |
| `ContentSafetyGuardrail` | Toxicity, profanity, PII detection |
| `OutputFormatGuardrail` | Format and schema validation |
| `ChainOfThoughtGuardrail` | Reasoning quality validation |
| `ToolUseGuardrail` | Tool invocation validation |
| `PromptInjectionGuardrail` | Injection attack detection |
| `InputLengthGuardrail` | Input length validation |
| `PIIDetectionGuardrail` | PII detection and masking |

---

## Best Practices
- Combine multiple guardrails for layered protection.
- Regularly update blocked keywords and policies.
- Test guardrails with diverse datasets to ensure robustness.
- Log blocked outputs for auditing and improvement.
- **Use GuardrailPipeline for chaining multiple validations.**
- **Define policies at appropriate scopes (global, team, agent, task).**
- **Start with WARN enforcement and move to STRICT after testing.**

## Related Documentation
- [LLMs Module](llms.md)
- [Knowledge Module](knowledge.md)
- [Monitoring Module](monitoring.md)
- [Compliance Module](compliance.md)
- [Security Module](security.md)
