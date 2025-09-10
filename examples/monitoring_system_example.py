from agenticaiframework.monitoring import MonitoringSystem

# Example: Using the MonitoringSystem
# ------------------------------------
# This example demonstrates how to:
# 1. Create a MonitoringSystem
# 2. Add metrics
# 3. Retrieve metrics
#
# Expected Output:
# - Display of recorded metrics

if __name__ == "__main__":
    # Create a monitoring system
    monitor = MonitoringSystem()

    # Record some metrics
    monitor.record_metric("CPU_Usage", 75)
    monitor.record_metric("Memory_Usage", 60)

    # Retrieve and display metrics
    metrics = monitor.get_metrics()
    print("Recorded Metrics:", metrics)
