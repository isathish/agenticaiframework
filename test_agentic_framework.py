"""
Test Script for Agentic Framework SDK

This script demonstrates the basic usage of the Agentic Framework SDK after installation.
It initializes the framework, creates a simple agent, and performs a basic task to verify
that the SDK is installed and functioning correctly.
"""

import sys
import os
import time

# Import the Agentic Framework SDK
try:
    from agentic_framework import initialize_framework, Agent, SecurityLevel
    print("Agentic Framework SDK imported successfully.")
except ImportError as e:
    print(f"Failed to import Agentic Framework SDK: {e}")
    sys.exit(1)

def main():
    """
    Main function to test the Agentic Framework SDK installation and usage.
    """
    print("Initializing Agentic Framework SDK...")
    
    # Initialize the framework with a basic configuration
    config = {
        "secret_key": "test_key_123",
        "security_level": SecurityLevel.LOW,
        "guardrail_rules": {"max_length": 100}
    }
    framework = initialize_framework(config)
    
    # Access initialized components
    security = framework["security"]
    agents = framework["agents"]
    
    print("Authenticating an agent...")
    # Authenticate for security purposes
    credentials = {'username': 'agent:default', 'password': 'secure_password_123'}
    token = security.authenticate_component(credentials)
    if not token:
        print("Authentication failed. Exiting.")
        return
    print("Authentication successful.")
    
    print("Creating a simple agent...")
    # Create a simple agent for testing
    test_agent = Agent(name="TestAgent", supported_modalities=["text"])
    
    # Register and start the agent
    agents.add_agent(test_agent)
    if security.check_access(token, "agent/TestAgent", "execute"):
        test_agent.start()
        print(f"Agent {test_agent.name} started.")
    else:
        print("Access denied to start agent. Exiting.")
        security.logout(token)
        return
    
    print("Performing a basic task...")
    # Perform a basic task with the agent
    task = "Perform a simple test task."
    result = test_agent.perform_task(task, modality="text")
    print(f"Task result: {result}")
    
    print("Cleaning up...")
    # Stop the agent
    test_agent.stop()
    print("Agent stopped.")
    
    # Logout
    security.logout(token)
    print("Session logged out.")
    
    print("Agentic Framework SDK test completed successfully.")

if __name__ == "__main__":
    main()
