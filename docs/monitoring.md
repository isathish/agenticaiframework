---
title: Monitoring
description: Real-time metrics, event logging, and garbage collection management for production workloads
tags:
  - monitoring
  - metrics
  - logging
  - observability
---

# :material-chart-line: Monitoring

**Real-time metrics collection, structured event logging, and garbage collection management.**

Thread-safe monitoring with bounded collections, `__slots__`, and structured logging throughout.

!!! tip "v2.0 Improvements"
    MonitoringSystem now uses `deque(maxlen)` for bounded metric storage,
    `threading.Lock` for thread safety, `__slots__` for memory efficiency,
    and built-in GC statistics / forced collection helpers.

---

## Overview

The `MonitoringSystem` class provides a centralised monitoring hub for your
agents, processes, and workflows:

| Feature | Description |
|---------|-------------|
| **Metrics** | Record and retrieve named numeric metrics with bounded history |
| **Events** | Log structured events with type classification |
| **Messages** | Append free-form log messages |
| **GC Management** | Inspect garbage collector stats and force collection |
| **Thread Safety** | All public methods are protected by `threading.Lock` |

---

## Quick Start

```python
from agenticaiframework import MonitoringSystem

monitor = MonitoringSystem()

# Record metrics
monitor.record_metric("latency_ms", 42.5)
monitor.record_metric("latency_ms", 38.1)
monitor.record_metric("tokens_used", 1500)

# Log events
monitor.log_event("agent_started", {"agent": "researcher", "model": "gpt-4o"})
monitor.log_event("task_completed", {"task": "summarise", "duration": 1.2})

# Log messages
monitor.log_message("Pipeline initialised successfully")

# Retrieve data
all_metrics = monitor.get_metrics() # dict of all metrics
latency = monitor.get_metric("latency_ms") # list of latency values
events = monitor.get_events() # list of all events
logs = monitor.get_logs() # list of all messages
```

---

## Metrics

Metrics are stored per-name in bounded `deque` collections so memory usage stays
constant regardless of how long the system runs.

```python
monitor.record_metric("request_count", 1)
monitor.record_metric("request_count", 2)

values = monitor.get_metric("request_count") # [1, 2]
```

---

## Event Logging

Events capture structured information with a type label and arbitrary details:

```python
monitor.log_event("error", {
    "component": "llm_client",
    "message": "Rate limit exceeded",
    "retry_after": 30,
})

errors = [e for e in monitor.get_events() if e["type"] == "error"]
```

---

## Garbage Collection Management

The monitoring system exposes helpers for Python's garbage collector:

```python
# Get GC statistics (generation counts, thresholds)
gc_stats = monitor.get_gc_stats()

# Force a garbage collection cycle
collected = monitor.force_gc()
```

!!! info "When to use `force_gc()`"
    Use sparingly — only when you have evidence of memory pressure (e.g. after
    disposing a large batch of agents). Python's automatic GC handles most cases.

---

## Clearing Data

Reset all collected monitoring data:

```python
monitor.clear()
```

---

## API Reference

### `MonitoringSystem`

Uses `__slots__` for memory efficiency. All methods are thread-safe.

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `record_metric(name, value)` | `None` | Record a numeric metric value |
| `get_metric(name)` | `list` | Retrieve all recorded values for a metric |
| `get_metrics()` | `dict` | Retrieve all metrics as `{name: [values]}` |
| `log_event(event_type, details)` | `None` | Log a structured event |
| `get_events()` | `list[dict]` | Retrieve all logged events |
| `log_message(message)` | `None` | Append a free-form log message |
| `get_logs()` | `list[str]` | Retrieve all log messages |
| `get_gc_stats()` | `dict` | Get garbage collector statistics |
| `force_gc()` | `int` | Force GC and return number of collected objects |
| `clear()` | `None` | Reset all metrics, events, and logs |

---

## Integration with Tracing

MonitoringSystem works alongside the [Tracing](tracing.md) module. Use
monitoring for **aggregate metrics** and tracing for **per-request spans**.

```python
from agenticaiframework import MonitoringSystem
from agenticaiframework.tracing import TracingManager

monitor = MonitoringSystem()
tracer = TracingManager()

# Record high-level metrics
monitor.record_metric("requests_total", 1)

# Trace individual request flow
with tracer.span("handle_request"):
    pass # your logic here
```

---

## Best Practices

!!! success "Do"
    - Use `record_metric()` for numeric KPIs (latency, token count, error rate).
    - Use `log_event()` for discrete occurrences with structured context.
    - Review `get_gc_stats()` periodically in long-running services.
    - Call `clear()` between test runs to avoid data bleed.

!!! danger "Don't"
    - Store unbounded data in metric names — the collection is bounded, but creating
      millions of unique metric keys will still consume memory.
    - Call `force_gc()` in hot paths — it pauses the interpreter.

---

## Related Documentation

- [Tracing](tracing.md) — distributed tracing and spans
- [Performance](performance.md) — tuning and benchmarking
- [Infrastructure](infrastructure.md) — deployment and scaling
