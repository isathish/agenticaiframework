---
title: Monitoring Example
description: Log events and record metrics with MonitoringSystem for observability
tags:
  - example
  - monitoring
  - observability
  - tutorial
---

# Monitoring System Example

This guide provides a **professional, step-by-step walkthrough** for using the `MonitoringSystem` in the `agenticaiframework` package to log events and record metrics. 
It is intended for developers who want to track agent activities, performance, and operational metrics in real-time.

!!! info "Enterprise Observability"
    Part of **237 enterprise modules** with 16 observability modules including distributed tracing, APM integration, and real-time dashboards.

## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **No additional configuration** is required for this example.
- **Python Version**: Compatible with Python 3.10+.

## Code

```python
import logging

logger = logging.getLogger(__name__)

from agenticaiframework.monitoring import MonitoringSystem

if __name__ == "__main__":
    monitor = MonitoringSystem()

    # Log events
    monitor.log_event("AgentStarted", {"agent_name": "ExampleAgent"})
    monitor.log_event("TaskCompleted", {"task_name": "AdditionTask", "status": "success"})

    # Record metrics
    monitor.record_metric("ResponseTime", 1.23)
    monitor.record_metric("Accuracy", 0.98)

    # Display logged data
    logger.info("Logged Events:", monitor.events)
    logger.info("Logged Metrics:", monitor.metrics)
```

## Step-by-Step Execution

1. **Import the Class** 
   Import `MonitoringSystem` from `agenticaiframework.monitoring`.

2. **Instantiate the Monitoring System** 
   Create an instance of `MonitoringSystem` to manage event logging and metric recording.

3. **Log Events** 
   Use `log_event` to record significant occurrences, passing:
   - `event_type`: A string describing the event.
   - `details`: A dictionary with event-specific data.

4. **Record Metrics** 
   Use `record_metric` to store performance or operational metrics, passing:
   - `metric_name`: The name of the metric.
   - `value`: The metric's value.

5. **Inspect Logged Data** 
   Access `events` and `metrics` attributes to review stored information.

> **Best Practice:** Use consistent naming conventions for events and metrics to simplify analysis and reporting.

## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes. In production, events and metrics could be generated dynamically from agent activities, API calls, or system monitoring hooks.

## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [MonitoringSystem] Event logged: AgentStarted - {'agent_name': 'ExampleAgent'}
[YYYY-MM-DD HH:MM:SS] [MonitoringSystem] Event logged: TaskCompleted - {'task_name': 'AdditionTask', 'status': 'success'}
[YYYY-MM-DD HH:MM:SS] [MonitoringSystem] Metric recorded: ResponseTime = 1.23
[YYYY-MM-DD HH:MM:SS] [MonitoringSystem] Metric recorded: Accuracy = 0.98
Logged Events: [{'type': 'AgentStarted', 'details': {'agent_name': 'ExampleAgent'}, 'timestamp': <timestamp>}, {'type': 'TaskCompleted', 'details': {'task_name': 'AdditionTask', 'status': 'success'}, 'timestamp': <timestamp>}]
Logged Metrics: {'ResponseTime': 1.23, 'Accuracy': 0.98}
```

## How to Run

Run the example from the project root:

```bash
python examples/monitoring_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.monitoring_example
```

> **Tip:** Integrate `MonitoringSystem` into your agents to automatically log key lifecycle events and performance metrics.
