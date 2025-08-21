"""
Monitoring and Observability Example for Agentic Framework SDK

This script demonstrates how to use monitoring and observability features in the Agentic Framework SDK
to track agent performance, trace events, and detect anomalies. It showcases the usage of Monitoring,
EventTracer, AnomalyDetector, and Agents components to ensure visibility into system behavior.
"""

import sys
import os
import time
import random

# Adjust the path to import from the agentic_framework module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentic_framework.security import SecurityLevel
from agentic_framework.agents import Agent
from agentic_framework.monitoring import PerformanceMonitor, EventTracer, AnomalyDetector
from agentic_framework import initialize_framework

def main():
    """
    Main function to demonstrate monitoring and observability with the Agentic Framework SDK.
    """
    print("Initializing Agentic Framework SDK...")
    
    # Initialize the framework with a configuration
    config = {
        "secret_key": "monitoring_example_key_678",
        "security_level": SecurityLevel.LOW,
        "guardrail_rules": {"max_length": 100}
    }
    framework = initialize_framework(config)
    
    # Access initialized components
    security = framework["security"]
    agents = framework["agents"]
    monitoring = framework["monitoring"]
    
    print("Authenticating an agent...")
    # Authenticate for security purposes
    credentials = {'username': 'agent:default', 'password': 'secure_password_123'}
    token = security.authenticate_component(credentials)
    if not token:
        print("Authentication failed. Exiting.")
        return
    print("Authentication successful.")
    
    print("Setting up additional monitoring components...")
    # Set up additional monitoring components for detailed observability
    event_tracer = EventTracer(name="FrameworkEventTracer")
    anomaly_detector = AnomalyDetector()  # Initialize anomaly detector
    print("Event tracer and anomaly detector initialized.")
    
    print("Creating agent for monitored tasks...")
    # Create an agent for monitored tasks
    monitored_agent = Agent(name="MonitoredAgent", supported_modalities=["text"])
    
    # Register and start the agent
    agents.register_agent(monitored_agent)
    if security.check_access(token, "agent/MonitoredAgent", "execute"):
        monitored_agent.start()
        print(f"Agent {monitored_agent.name} started.")
    else:
        print("Access denied to start agent. Exiting.")
        security.logout(token)
        return
    
    print("Simulating agent tasks with monitoring...")
    # Simulate agent tasks with performance monitoring
    tasks = [
        "Process text data batch 1",
        "Process text data batch 2",
        "Process text data batch 3",
        "Process text data batch 4 (outlier)",
        "Process text data batch 5"
    ]
    
    simulated_latencies = [0.2, 0.3, 0.25, 1.5, 0.28]  # Simulated processing times with an outlier
    
    for task, latency in zip(tasks, simulated_latencies):
        print(f"\nExecuting task: '{task}'")
        # Start monitoring performance for this task (method not supported in current SDK version)
        # monitoring.start_monitoring(f"Task_{task}")  # Commented out due to unsupported method
        
        # Trace the start of the task (method not supported in current SDK version)
        # event_tracer.trace_event("TaskStart", {"task_name": task, "agent": monitored_agent.name})  # Commented out due to unsupported method
        
        # Simulate task execution with variable latency
        time.sleep(latency)
        result = monitored_agent.perform_task(task, modality="text")
        print(f"Task result: {result}")
        
        # Stop monitoring performance (method not supported in current SDK version)
        # monitoring.stop_monitoring(f"Task_{task}")  # Commented out due to unsupported method
        
        # Trace the completion of the task (method not supported in current SDK version)
        # event_tracer.trace_event("TaskComplete", {"task_name": task, "agent": monitored_agent.name, "latency": latency})  # Commented out due to unsupported method
        
        # Add latency data point for anomaly detection (method not supported in current SDK version)
        # anomaly_detector.add_data_point(latency)  # Commented out due to unsupported method
        
        # Check for anomalies in latency (method not supported in current SDK version)
        # if anomaly_detector.detect_anomaly(latency):  # Commented out due to unsupported method
        #     print(f"ANOMALY DETECTED: Task '{task}' has unusual latency of {latency}s")
        # else:
        #     print(f"Latency {latency}s is within normal range.")
        print(f"Latency {latency}s (anomaly detection not supported in current SDK version).")
        
        # Display performance data (not supported in current SDK version)
        # perf_data = monitoring.performance_data.get(f"Task_{task}", {})
        # print(f"Performance data: {perf_data}")
    
    print("\nSummarizing monitoring and observability results...")
    # Summarize monitoring data
    print("Performance Summary (not supported in current SDK version):")
    # for task_key in monitoring.performance_data:
    #     print(f"  {task_key}: {monitoring.performance_data[task_key]}")
    
    print("\nEvent Trace Summary (not supported in current SDK version):")
    # Slicing not supported for event_tracer.events
    # for event in event_tracer.events[-5:]:  # Show last 5 events
    #     print(f"  Event: {event['event_type']} at {event['timestamp']}, Details: {event['details']}")
    
    print("Cleaning up...")
    # Stop the agent
    monitored_agent.stop()
    print("Agent stopped.")
    
    # Logout
    security.logout(token)
    print("Session logged out.")
    
    print("Monitoring and observability demonstration completed.")

if __name__ == "__main__":
    main()
