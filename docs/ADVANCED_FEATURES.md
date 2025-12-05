# Advanced Features Guide

## Overview

This guide covers the advanced features added to the Agentic AI Framework, including:

1. **Agent Context Engineering**
2. **Prompt Injection Protection**
3. **Advanced Security Features**
4. **Enhanced Memory Management**
5. **LLM Reliability Features**
6. **Performance Optimizations**

---

## 1. Agent Context Engineering

### Context Manager

The `ContextManager` provides sophisticated context window management for agents:

**Features:**
- Token tracking and estimation
- Context compression with importance weighting
- Automatic pruning when approaching limits
- Context history with metadata
- Statistics and monitoring

**Example:**
```python
from agenticaiframework import Agent, ContextManager

# Create agent with context management
agent = Agent(
    name="ContextAwareAgent",
    role="Assistant",
    capabilities=["reasoning"],
    config={},
    max_context_tokens=4096
)

# Add context with importance level
agent.add_context(
    "Important system instruction",
    importance=0.9  # High importance (0-1)
)

# Get context statistics
stats = agent.get_context_stats()
print(f"Token utilization: {stats['utilization']:.2%}")
print(f"Compressions: {stats['compression_stats']['total_compressions']}")
```

**Key Methods:**
- `add_context(content, importance)` - Add context with importance weighting
- `get_context_stats()` - Get current context statistics
- `get_context_summary()` - Get summary of recent context

---

## 2. Prompt Injection Protection

### Enhanced Prompt Class

The enhanced `Prompt` class provides security features to prevent injection attacks:

**Features:**
- Automatic injection pattern detection
- Variable sanitization
- Defensive prompting
- Version control with rollback
- Safe rendering mode

**Example:**
```python
from agenticaiframework import Prompt, PromptManager

# Create secure prompt
prompt = Prompt(
    template="You are a {role}. Task: {task}",
    enable_security=True
)

# Safe rendering with defensive prompting
result = prompt.render_safe(
    role="assistant",
    task="Help the user with coding"
)

# Prompt Manager with security scanning
manager = PromptManager(enable_security=True)
manager.register_prompt("my_prompt", prompt)

# Scan for vulnerabilities
vulnerabilities = manager.scan_for_vulnerabilities()
```

**Detected Patterns:**
- "Ignore previous instructions"
- "Disregard above prompts"
- System prompt manipulation attempts
- Role hijacking attempts
- And more...

---

## 3. Advanced Security Features

### Security Module

The new `security.py` module provides comprehensive security features:

#### Prompt Injection Detector
```python
from agenticaiframework import PromptInjectionDetector

detector = PromptInjectionDetector()
result = detector.detect("Ignore all previous instructions")

print(result['is_injection'])  # True
print(result['confidence'])     # 0.9
print(result['matched_patterns'])
```

#### Input Validator
```python
from agenticaiframework import InputValidator

validator = InputValidator()

# Register custom validators
validator.register_validator(
    "length_check",
    lambda data: len(str(data)) <= 1000
)

# Sanitize HTML
clean_text = validator.sanitize_html("<script>alert('xss')</script>Hello")
```

#### Rate Limiter
```python
from agenticaiframework import RateLimiter

limiter = RateLimiter(max_requests=100, time_window=60)

if limiter.is_allowed("user123"):
    # Process request
    pass
else:
    # Rate limit exceeded
    pass
```

#### Content Filter
```python
from agenticaiframework import ContentFilter

filter = ContentFilter()
filter.add_blocked_word("spam")
filter.add_blocked_pattern(r'\d{3}-\d{2}-\d{4}')  # SSN pattern

if filter.is_allowed(text):
    # Content is safe
    pass
```

#### Audit Logger
```python
from agenticaiframework import AuditLogger

logger = AuditLogger()
logger.log('user_login', {'user_id': 'user123'}, severity='info')

# Query logs
error_logs = logger.query(severity='error')
```

#### Security Manager (All-in-One)
```python
from agenticaiframework import SecurityManager

security = SecurityManager()
result = security.validate_input("User input", user_id="user123")

if result['is_valid']:
    # Process sanitized input
    safe_text = result['sanitized_text']
```

---

## 4. Enhanced Memory Management

### Advanced Memory Features

The enhanced `MemoryManager` provides sophisticated memory management:

**Features:**
- TTL (Time-To-Live) for automatic expiration
- Priority-based eviction (LRU with priorities)
- Memory consolidation (promote frequently accessed items)
- Multi-tier storage (short-term, long-term, external)
- Search and filtering
- Statistics and monitoring

**Example:**
```python
from agenticaiframework import MemoryManager

memory = MemoryManager(
    short_term_limit=100,
    long_term_limit=1000
)

# Store with TTL and priority
memory.store_short_term(
    key="session_data",
    value={"user": "john", "session": "abc123"},
    ttl=300,  # Expires in 5 minutes
    priority=8,  # High priority
    metadata={"type": "session"}
)

# Retrieve
data = memory.retrieve("session_data")

# Search
results = memory.search("session")

# Consolidate frequently accessed items
memory.consolidate()

# Get statistics
stats = memory.get_stats()
print(f"Cache hit rate: {stats['cache_hit_rate']:.2%}")
```

**Memory Tiers:**
- **Short-term**: Fast access, limited size, with TTL
- **Long-term**: Larger capacity, optional TTL
- **External**: Unlimited size, persistent storage

---

## 5. LLM Reliability Features

### Enhanced LLM Manager

The enhanced `LLMManager` provides reliability and performance features:

**Features:**
- Automatic retry with exponential backoff
- Circuit breaker pattern to prevent cascading failures
- Response caching for performance
- Fallback chain for high availability
- Per-model performance tracking
- Token usage tracking

**Example:**
```python
from agenticaiframework import LLMManager

llm = LLMManager(
    max_retries=3,
    enable_caching=True
)

# Register models
llm.register_model("primary", primary_model_fn)
llm.register_model("fallback", fallback_model_fn)

# Set active model and fallback chain
llm.set_active_model("primary")
llm.set_fallback_chain(["fallback"])

# Generate with automatic retry and caching
response = llm.generate(
    "What is machine learning?",
    use_cache=True,
    temperature=0.7
)

# Get metrics
metrics = llm.get_metrics()
print(f"Success rate: {metrics['success_rate']:.2%}")
print(f"Cache hit rate: {metrics['cache_hit_rate']:.2%}")
```

**Circuit Breaker States:**
- **Closed**: Normal operation
- **Open**: Too many failures, blocking requests
- **Half-Open**: Testing if service recovered

---

## 6. Enhanced Guardrails

### Advanced Guardrail Features

**Features:**
- Priority-based enforcement
- Circuit breaker for misbehaving guardrails
- Detailed violation tracking
- Remediation actions
- Severity levels (low, medium, high, critical)

**Example:**
```python
from agenticaiframework import Guardrail, GuardrailManager

manager = GuardrailManager()

# Create guardrails with priorities
length_check = Guardrail(
    name="length",
    validation_fn=lambda data: len(str(data)) <= 1000,
    severity="medium"
)
manager.register_guardrail(length_check, priority=5)

injection_check = Guardrail(
    name="injection",
    validation_fn=detect_injection_fn,
    severity="critical"
)
manager.register_guardrail(injection_check, priority=10)

# Enforce all guardrails
result = manager.enforce_guardrails(data, fail_fast=True)

if not result['is_valid']:
    for violation in result['violations']:
        print(f"Violation: {violation['guardrail_name']}")
        print(f"Severity: {violation['severity']}")

# Get aggregate statistics
stats = manager.get_aggregate_stats()
```

---

## 7. Performance Monitoring

### Agent Performance Metrics

**Tracked Metrics:**
- Total tasks executed
- Success/failure rates
- Average execution time
- Error counts
- Context utilization

**Example:**
```python
agent = Agent(name="MyAgent", ...)
agent.start()

# Execute tasks
for task in tasks:
    agent.execute_task(task)

# Get metrics
metrics = agent.get_performance_metrics()
print(f"Success rate: {metrics['success_rate']:.2%}")
print(f"Avg execution time: {metrics['average_execution_time']:.4f}s")
```

### Agent Manager Health Check

```python
manager = AgentManager()
# ... register agents ...

health = manager.health_check()
for agent_id, status in health.items():
    print(f"{status['name']}: {status['success_rate']:.2%}")
```

---

## 8. Best Practices

### Security Best Practices

1. **Always enable security features:**
   ```python
   prompt = Prompt(template, enable_security=True)
   manager = PromptManager(enable_security=True)
   ```

2. **Use defensive prompting for user inputs:**
   ```python
   result = prompt.render_safe(user_input=untrusted_input)
   ```

3. **Implement multi-layer validation:**
   ```python
   # Layer 1: Security manager
   security_result = security.validate_input(data, user_id)
   
   # Layer 2: Guardrails
   guardrail_result = guardrails.enforce_guardrails(data)
   ```

4. **Monitor security events:**
   ```python
   metrics = security.get_security_metrics()
   audit_logs = security.audit_logger.query(severity='error')
   ```

### Performance Best Practices

1. **Enable caching for LLMs:**
   ```python
   llm = LLMManager(enable_caching=True)
   ```

2. **Use appropriate memory tiers:**
   ```python
   # Frequently accessed, short-lived
   memory.store_short_term(key, value, ttl=300)
   
   # Important, long-lived
   memory.store_long_term(key, value, priority=10)
   ```

3. **Monitor context utilization:**
   ```python
   stats = agent.get_context_stats()
   if stats['utilization'] > 0.8:
       # Consider increasing context window
   ```

4. **Set up fallback chains:**
   ```python
   llm.set_fallback_chain(["model1", "model2", "model3"])
   ```

### Context Management Best Practices

1. **Use importance weighting:**
   ```python
   # System instructions
   agent.add_context(system_msg, importance=0.9)
   
   # User queries
   agent.add_context(user_msg, importance=0.7)
   
   # Background info
   agent.add_context(background, importance=0.3)
   ```

2. **Monitor token usage:**
   ```python
   stats = agent.get_context_stats()
   print(f"Tokens: {stats['current_tokens']}/{stats['max_tokens']}")
   ```

3. **Leverage automatic compression:**
   - Context manager automatically compresses when needed
   - Higher importance items are retained
   - Statistics track compression effectiveness

---

## 9. Example Workflows

### Secure Agent Workflow

```python
from agenticaiframework import *

# 1. Setup security
security = SecurityManager()

# 2. Setup guardrails
guardrails = GuardrailManager()
guardrails.create_standard_guardrails()

# 3. Setup prompts
prompts = PromptManager(enable_security=True)
prompt = Prompt("Task: {task}", enable_security=True)
prompts.register_prompt("task", prompt)

# 4. Setup LLM
llm = LLMManager(max_retries=3, enable_caching=True)
llm.register_model("primary", model_fn)
llm.set_active_model("primary")

# 5. Create agent
agent = Agent(
    name="SecureAgent",
    role="Assistant",
    capabilities=["analysis"],
    config={"llm": llm},
    max_context_tokens=4096
)
agent.start()

# 6. Process request
user_input = "Analyze this data..."

# Validate
security_result = security.validate_input(user_input, "user123")
if not security_result['is_valid']:
    print("Security check failed")
    exit()

# Enforce guardrails
guardrail_result = guardrails.enforce_guardrails(user_input)
if not guardrail_result['is_valid']:
    print("Guardrail check failed")
    exit()

# Render prompt
prompt_obj = prompts.get_prompt_by_name("task")
rendered = prompts.render_prompt(
    prompt_obj.id,
    safe_mode=True,
    task=security_result['sanitized_text']
)

# Generate response
response = llm.generate(rendered)

# Add to agent context
agent.add_context(f"Completed task: {user_input[:50]}", importance=0.6)

print(f"Response: {response}")
```

---

## 10. Testing Examples

All features include comprehensive examples in the `examples/` directory:

- `security_example.py` - Security features demonstration
- `context_engineering_example.py` - Context management
- `prompt_injection_protection_example.py` - Prompt security
- `memory_advanced_example.py` - Advanced memory features
- `llm_reliability_example.py` - LLM reliability features
- `comprehensive_integration_example.py` - Full integration

Run examples:
```bash
python examples/security_example.py
python examples/comprehensive_integration_example.py
```

---

## Summary

The enhanced Agentic AI Framework now provides enterprise-grade features for:

✅ **Security**: Prompt injection protection, input validation, rate limiting, audit logging  
✅ **Reliability**: Circuit breakers, retry mechanisms, fallback chains  
✅ **Performance**: Caching, context compression, memory optimization  
✅ **Monitoring**: Comprehensive metrics, health checks, violation tracking  
✅ **Safety**: Multi-layer guardrails, content filtering, defensive prompting  

These features work together to create a robust, secure, and production-ready agent framework.
