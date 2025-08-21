"""
Process Orchestration Example for Agentic Framework SDK

This script demonstrates how to set up different process orchestration strategies using the Agentic Framework SDK.
It showcases the usage of Process, Tasks, and Agents components to execute workflows in sequential, parallel,
and hybrid modes for efficient task management.
"""

import sys
import os
import time

# Adjust the path to import from the agentic_framework module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentic_framework import initialize_framework, Agent, Task, Process, SecurityLevel

def main():
    """
    Main function to demonstrate process orchestration with the Agentic Framework SDK.
    """
    print("Initializing Agentic Framework SDK...")
    
    # Initialize the framework with a configuration
    config = {
        "secret_key": "process_example_key_345",
        "security_level": SecurityLevel.LOW,
        "guardrail_rules": {"max_length": 100}
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
    
    print("Creating agents for workflow...")
    # Create agents for different tasks in the workflow
    data_collector = Agent(name="DataCollector", supported_modalities=["text"])
    data_analyzer = Agent(name="DataAnalyzer", supported_modalities=["text"])
    report_generator = Agent(name="ReportGenerator", supported_modalities=["text"])
    data_validator = Agent(name="DataValidator", supported_modalities=["text"])
    
    # Register agents
    agents.register_agent(data_collector)
    agents.register_agent(data_analyzer)
    agents.register_agent(report_generator)
    agents.register_agent(data_validator)
    
    # Start agents if access is granted
    for agent in [data_collector, data_analyzer, report_generator, data_validator]:
        if security.check_access(token, f"agent/{agent.name}", "execute"):
            agent.start()
            print(f"Agent {agent.name} started.")
        else:
            print(f"Access denied to start agent {agent.name}. Exiting.")
            security.logout(token)
            return
    
    print("Creating tasks for orchestration...")
    # Create tasks for the workflow
    collect_task = Task(task_id="CollectData", description="Collect data from sources", required_capabilities=["text"])
    validate_task = Task(task_id="ValidateData", description="Validate collected data", required_capabilities=["text"])
    analyze_task = Task(task_id="AnalyzeData", description="Analyze validated data", required_capabilities=["text"])
    report_task = Task(task_id="GenerateReport", description="Generate report from analysis", required_capabilities=["text"])
    
    # Register tasks
    tasks.register_task(collect_task)
    tasks.register_task(validate_task)
    tasks.register_task(analyze_task)
    tasks.register_task(report_task)
    
    # Assign tasks to agents
    tasks.assign_task("CollectData", "DataCollector")
    tasks.assign_task("ValidateData", "DataValidator")
    tasks.assign_task("AnalyzeData", "DataAnalyzer")
    tasks.assign_task("GenerateReport", "ReportGenerator")
    print("Tasks assigned to respective agents.")
    
    print("Setting up different process orchestration strategies...")
    # Set up different process orchestration strategies
    # 1. Sequential Process: Collect -> Validate -> Analyze -> Report
    sequential_process = Process(process_type="sequential", tasks=["CollectData", "ValidateData", "AnalyzeData", "GenerateReport"])
    processes.register_process(sequential_process)
    print(f"Sequential Process {sequential_process.process_id} registered with tasks: {sequential_process.tasks}")
    
    # 2. Parallel Process: Run Validate and Analyze in parallel after Collect, then Report
    # Note: For simplicity, the SDK simulates parallel execution in this example
    parallel_process = Process(process_type="parallel", tasks=["CollectData", "ValidateData", "AnalyzeData", "GenerateReport"])
    processes.register_process(parallel_process)
    print(f"Parallel Process {parallel_process.process_id} registered with tasks: {parallel_process.tasks}")
    
    # 3. Hybrid Process: Collect (sequential) -> Validate & Analyze (parallel) -> Report (sequential)
    hybrid_process = Process(process_type="hybrid", tasks=["CollectData", "ValidateData", "AnalyzeData", "GenerateReport"])
    processes.register_process(hybrid_process)
    print(f"Hybrid Process {hybrid_process.process_id} registered with tasks: {hybrid_process.tasks}")
    
    print("Executing processes with different orchestration strategies...")
    # Execute processes with different orchestration strategies
    for process in [sequential_process, parallel_process, hybrid_process]:
        print(f"\nExecuting {process.process_type} process {process.process_id}...")
        result = processes.execute_process(process.process_id)
        print(f"Process execution result: {result}")
    
    print("Cleaning up...")
    # Stop agents
    for agent in [data_collector, data_analyzer, report_generator, data_validator]:
        agent.stop()
        print(f"Agent {agent.name} stopped.")
    
    # Logout
    security.logout(token)
    print("Session logged out.")
    
    print("Process orchestration demonstration completed.")

if __name__ == "__main__":
    main()
