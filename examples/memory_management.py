"""
Memory Management Example for Agentic Framework SDK

This script demonstrates how to use memory management features in the Agentic Framework SDK
to enable agents to retain, recall, and utilize information across interactions. It showcases
the usage of MemoryManager, ShortTermMemoryStorage, LongTermMemoryStorage, and Agents components
for context retention in short-term, long-term, and external memory.
"""

import sys
import os
import time

# Adjust the path to import from the agentic_framework module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentic_framework.agents import Agent
from agentic_framework.security import SecurityLevel
from agentic_framework import initialize_framework
from agentic_framework.memory import ShortTermMemoryStorage, LongTermMemoryStorage, ExternalMemoryStorage

def main():
    """
    Main function to demonstrate memory management with the Agentic Framework SDK.
    """
    print("Initializing Agentic Framework SDK...")
    
    # Initialize the framework with a configuration
    config = {
        "secret_key": "memory_example_key_901",
        "security_level": SecurityLevel.LOW,
        "guardrail_rules": {"max_length": 100}
    }
    framework = initialize_framework(config)
    
    # Access initialized components
    security = framework["security"]
    agents = framework["agents"]
    memory = framework["memory"]
    
    # Activate the MemoryManager component
    memory.activate()
    print("MemoryManager component activated.")
    
    print("Authenticating an agent...")
    # Authenticate for security purposes
    credentials = {'username': 'agent:default', 'password': 'secure_password_123'}
    token = security.authenticate_component(credentials)
    if not token:
        print("Authentication failed. Exiting.")
        return
    print("Authentication successful.")
    
    print("Creating agent for memory-based tasks...")
    # Create an agent for memory-based tasks
    memory_agent = Agent(name="MemoryAgent", supported_modalities=["text"])
    
    # Register and start the agent
    agents.register_agent(memory_agent)
    if security.check_access(token, "agent/MemoryAgent", "execute"):
        memory_agent.start()
        print(f"Agent {memory_agent.name} started.")
    else:
        print("Access denied to start agent. Exiting.")
        security.logout(token)
        return
    
    print("Setting up memory storage types...")
    # Set up different memory storage types
    # Configuration for memory storage
    memory_config = {
        "retention_policy": "time_based",
        "expiration": 3600,  # 1 hour for short-term memory
        "storage_backend": "in_memory"
    }
    long_term_config = {
        "retention_policy": "permanent",
        "storage_backend": "disk",
        "path": "memory_data/long_term"
    }
    external_config = {
        "storage_backend": "cloud",
        "endpoint": "https://api.example.com/storage",
        "credentials": {"api_key": "placeholder_key"}
    }
    
    short_term_store = ShortTermMemoryStorage(config=memory_config)
    long_term_store = LongTermMemoryStorage(config=long_term_config)
    external_store = ExternalMemoryStorage(config=external_config)
    # Activate the memory storage components
    short_term_store.activate()
    long_term_store.activate()
    external_store.activate()
    print("Short-term, long-term, and external memory storage initialized and activated.")
    
    print("Simulating interactions with memory management...")
    # Simulate interactions where the agent uses different memory types
    interactions = [
        {"id": "conv_001", "data": "User asked about project status on 2025-08-20.", "type": "short_term", "metadata": {"category": "recent"}},
        {"id": "conv_002", "data": "User preference for detailed reports noted on 2025-08-15.", "type": "long_term", "metadata": {"category": "preferences"}},
        {"id": "conv_003", "data": "Historical project data archived on external server.", "type": "external", "metadata": {"category": "archive"}}
    ]
    
    for interaction in interactions:
        print(f"\nStoring interaction: {interaction['id']} in {interaction['type']} memory")
        # Store data in the appropriate memory type using storage objects directly
        if interaction['type'] == "short_term":
            short_term_store.store(interaction['id'], interaction['data'])
        elif interaction['type'] == "long_term":
            long_term_store.store(interaction['id'], interaction['data'], metadata=interaction['metadata'])
        elif interaction['type'] == "external":
            external_store.store(interaction['id'], interaction['data'], metadata=interaction['metadata'])
        print(f"Stored {interaction['id']} in {interaction['type']} memory.")
    
    print("\nRetrieving and using memory for agent tasks...")
    # Retrieve and use memory for agent tasks
    for interaction in interactions:
        memory_type = interaction['type']
        print(f"\nRetrieving interaction: {interaction['id']} from {memory_type} memory")
        # Retrieve data from the appropriate memory type using storage objects directly
        if memory_type == "short_term":
            retrieved_data = short_term_store.retrieve(interaction['id'])
        elif memory_type == "long_term":
            retrieved_data = long_term_store.retrieve(interaction['id'])
        else:  # external
            retrieved_data = external_store.retrieve(interaction['id'])
        if retrieved_data:
            print(f"Retrieved data: {retrieved_data[:100]}...")
            # Use the retrieved data in an agent task
            task = f"Respond based on memory: {retrieved_data[:150]}"
            if security.check_access(token, f"memory/{memory_type}", "read"):
                result = memory_agent.perform_task(task, modality="text")
                print(f"Agent response: {result}")
            else:
                print(f"Access denied to read from {memory_type} memory.")
        else:
            print(f"No data found for {interaction['id']} in {memory_type} memory.")
    
    print("\nSearching long-term memory by metadata...")
    # Demonstrate searching long-term memory by metadata
    if hasattr(long_term_store, 'search_by_metadata'):
        search_results = long_term_store.search_by_metadata({"category": "preferences"})
        print(f"Search results for category 'preferences': {search_results}")
    else:
        print("Search by metadata is not supported in the current framework version.")
    
    print("Cleaning up...")
    # Stop the agent
    memory_agent.stop()
    print("Agent stopped.")
    
    # Logout
    security.logout(token)
    print("Session logged out.")
    
    print("Memory management demonstration completed.")

if __name__ == "__main__":
    main()
