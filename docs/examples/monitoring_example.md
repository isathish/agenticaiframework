# Monitoring Example

This example demonstrates how to use the `MonitoringSystem` in the `agenticaiframework` package to log events and record metrics.

---

## Configuration
No special configuration is required. Ensure `agenticaiframework` is installed and accessible in your Python environment.

---

## Code

```python
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
    print("Logged Events:", monitor.events)
    print("Logged Metrics:", monitor.metrics)
```

---

## Step-by-Step Execution

1. **Import** `MonitoringSystem` from `agenticaiframework.monitoring`.
2. **Instantiate** the monitoring system.
3. **Log** events with a type and details using `log_event`.
4. **Record** metrics with a name and value using `record_metric`.
5. **Print** the stored events and metrics.

---

## Expected Input
No user input is required; the script uses hardcoded values for demonstration.

---

## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [MonitoringSystem] Event logged: AgentStarted - {'agent_name': 'ExampleAgent'}
[YYYY-MM-DD HH:MM:SS] [MonitoringSystem] Event logged: TaskCompleted - {'task_name': 'AdditionTask', 'status': 'success'}
[YYYY-MM-DD HH:MM:SS] [MonitoringSystem] Metric recorded: ResponseTime = 1.23
[YYYY-MM-DD HH:MM:SS] [MonitoringSystem] Metric recorded: Accuracy = 0.98
Logged Events: [{'type': 'AgentStarted', 'details': {'agent_name': 'ExampleAgent'}, 'timestamp': <timestamp>}, {'type': 'TaskCompleted', 'details': {'task_name': 'AdditionTask', 'status': 'success'}, 'timestamp': <timestamp>}]
Logged Metrics: {'ResponseTime': 1.23, 'Accuracy': 0.98}
```

---

## How to Run

```bash
python examples/monitoring_example.py
