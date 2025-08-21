"""
Multi-Agent Workflow Example for Agentic Framework SDK

This script demonstrates how to set up a multi-agent workflow using the Agentic Framework SDK.
It creates two agents—a Data Collector and a Data Analyzer—that collaborate to collect and analyze data
through a sequential process. This example showcases the usage of Agents, Tasks, and Process components.
"""

import sys
import os
import time

# Adjust the path to import from the agentic_framework module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentic_framework import initialize_framework, SecurityLevel, Agent, Task, Process

def main():
    """
    Main function to demonstrate a multi-agent workflow with the Agentic Framework SDK.
    """
    print("Initializing Agentic Framework SDK...")
    
    # Initialize the framework with a configuration
    config = {
        "secret_key": "example_secret_key_123",
        "security_level": SecurityLevel.LOW,
        "guardrail_rules": {"max_length": 200}
    }
    framework = initialize_framework(config)
    
    # Access initialized components
    security = framework["security"]
    agents = framework["agents"]
    tasks = framework["tasks"]
    processes = framework["processes"]
    
    print("Authenticating an agent...")
    # Authenticate for security purposes
    credentials = {'username': 'agent:default', 'password': 'secure_password_123'}
    token = security.authenticate_component(credentials)
    if not token:
        print("Authentication failed. Exiting.")
        return
    print("Authentication successful.")
    
    print("Creating agents...")
    # Create agents for data collection and analysis
    data_collector = Agent(name="DataCollector", supported_modalities=["text", "sensor_data"])
    data_analyzer = Agent(name="DataAnalyzer", supported_modalities=["text", "structured_data"])
    
    # Register agents
    agents.register_agent(data_collector)
    agents.register_agent(data_analyzer)
    
    # Start agents
    if security.check_access(token, "agent/DataCollector", "execute"):
        data_collector.start()
        print(f"Agent {data_collector.name} started.")
    if security.check_access(token, "agent/DataAnalyzer", "execute"):
        data_analyzer.start()
        print(f"Agent {data_analyzer.name} started.")
    
    print("Creating tasks...")
    # Create tasks for the workflow
    collect_task = Task(name="CollectData", objective="Collect data from various sources")
    analyze_task = Task(name="AnalyzeData", objective="Analyze the collected data for insights")
    
    # Register tasks
    tasks.register_task(collect_task)
    tasks.register_task(analyze_task)
    
    # Assign tasks to agents
    tasks.assign_task("CollectData", "DataCollector")
    tasks.assign_task("AnalyzeData", "DataAnalyzer")
    print(f"Task 'CollectData' assigned to {collect_task.assigned_agent}")
    print(f"Task 'AnalyzeData' assigned to {analyze_task.assigned_agent}")
    
    print("Setting up a sequential process...")
    # Create a sequential process for the workflow
    workflow_process = Process(process_type="sequential", tasks=["CollectData", "AnalyzeData"])
    processes.register_process(workflow_process)
    print(f"Process {workflow_process.process_id} registered with tasks: {workflow_process.tasks}")
    
    print("Executing the process...")
    # Execute the process
    result = processes.execute_process(workflow_process.process_id)
    print(f"Process execution result: {result}")
    
    print("Cleaning up...")
    # Stop agents
    data_collector.stop()
    data_analyzer.stop()
    print("Agents stopped.")
    
    # Logout
    security.logout(token)
    print("Session logged out.")
    
    print("Multi-agent workflow demonstration completed.")

if __name__ == "__main__":
    main()
