---
tags:
  - guardrails
  - safety
  - security
  - compliance
---

# 🛡️ Guardrails Module

<div class="annotate" markdown>

**Enforce safety, compliance, and quality constraints**

Protect your AI applications with intelligent validation and content moderation

</div>

## 🎯 Quick Navigation

<div class="grid cards" markdown>

-   :material-shield-check:{ .lg } **Safety Rules**
    
    Content moderation and filtering
    
    [:octicons-arrow-right-24: Configure](#safety-guardrails)

-   :material-scale-balance:{ .lg } **Compliance**
    
    Regulatory and policy checks
    
    [:octicons-arrow-right-24: Learn More](#compliance-guardrails)

-   :material-quality-high:{ .lg } **Quality**
    
    Output validation and scoring
    
    [:octicons-arrow-right-24: Validate](#quality-guardrails)

-   :material-book-open:{ .lg } **Examples**
    
    Implementation patterns
    
    [:octicons-arrow-right-24: View Examples](#examples)

</div>

## 📖 Overview

!!! abstract "What are Guardrails?"
    
    Guardrails enforce safety, compliance, and quality constraints on AI-generated outputs, ensuring responses adhere to predefined rules, ethical guidelines, and domain-specific requirements.

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
    policy: Dict[str, Any] = None,
    severity: str = "medium"
)
```

**Parameters:**

- **`name`** *(str)*: Unique identifier for the guardrail
- **`validation_fn`** *(Callable[[Any], bool])*: Function that returns True if validation passes
- **`policy`** *(Dict[str, Any])*: Policy configuration (e.g., priority, max_retries)
- **`severity`** *(str)*: Severity level ("low", "medium", "high", "critical")

#### Methods

```python
def validate(data: Any) -> bool
def get_stats() -> Dict[str, Any]
```

**Example:**

```python
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
print(f"Validation result: {is_valid}")

# Get statistics
stats = age_check.get_stats()
print(f"Validation count: {stats['validation_count']}")
print(f"Violation rate: {stats['violation_rate']:.2%}")
```

### GuardrailManager Class

The `GuardrailManager` orchestrates multiple guardrails with priority-based enforcement.

#### Key Methods

```python
def register_guardrail(guardrail: Guardrail) -> None
def enforce_guardrails(data: Any) -> Dict[str, Any]
def get_guardrail_by_name(name: str) -> Optional[Guardrail]
def list_guardrails() -> List[Guardrail]
```

**Example:**

```python
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
print(f"Valid: {result['is_valid']}")
print(f"Violations: {result.get('violations', [])}")
```

## Use Cases
- Preventing the disclosure of sensitive or confidential information.
- Enforcing compliance with legal and regulatory requirements.
- Maintaining brand voice and tone consistency.
- Filtering out harmful, biased, or toxic content.

## Best Practices
- Combine multiple guardrails for layered protection.
- Regularly update blocked keywords and policies.
- Test guardrails with diverse datasets to ensure robustness.
- Log blocked outputs for auditing and improvement.

## Related Documentation
- [LLMs Module](llms.md)
- [Knowledge Module](knowledge.md)
- [Monitoring Module](monitoring.md)
