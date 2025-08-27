from agenticaiframework.monitoring import MonitoringSystem

# Example: Using MonitoringSystem to log events and metrics
# ------------------------------------------------
# This example demonstrates how to:
# 1. Create a Monitor instance
# 2. Log events
# 3. Log metrics
# 4. Retrieve logs and metrics
#
# Expected Output:
# - Confirmation of logged events and metrics
# - Printed list of events and metrics

if __name__ == "__main__":
    # Create a Monitor instance
    monitor = MonitoringSystem()

    # Log some events
    monitor.log_event("AgentStarted", {"agent_name": "ExampleAgent"})
    monitor.log_event("TaskCompleted", {"task_name": "AdditionTask", "status": "success"})

    # Log some metrics
    monitor.record_metric("ResponseTime", 1.23)
    monitor.record_metric("Accuracy", 0.98)

    # Retrieve and print events
    events = monitor.get_events()
    print("Logged Events:", events)

    # Retrieve and print metrics
    metrics = monitor.metrics
    print("Logged Metrics:", metrics)
