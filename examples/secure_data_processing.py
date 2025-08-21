"""
Secure Data Processing Example for Agentic Framework SDK

This script demonstrates how to set up an agent for secure data processing using the Agentic Framework SDK.
It showcases the usage of Security, Guardrails, and Agents components to ensure data is processed within
safety and compliance boundaries. The example includes authentication, access control, input validation,
rate limiting, and data encryption.
"""

import sys
import os
import time

# Adjust the path to import from the agentic_framework module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentic_framework import initialize_framework, Agent, SecurityLevel, ValidationGuardrail, RateLimiter

def main():
    """
    Main function to demonstrate secure data processing with the Agentic Framework SDK.
    """
    print("Initializing Agentic Framework SDK...")
    
    # Initialize the framework with a configuration
    config = {
        "secret_key": "secure_example_key_456",
        "security_level": SecurityLevel.HIGH,
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
    
    print("Setting up guardrails...")
    # Set up guardrails for input validation and rate limiting
    validator = ValidationGuardrail(validation_rules={"max_length": 100, "allowed_chars": r'^[a-zA-Z0-9\s]+$"})
    limiter = RateLimiter(rate_limit=5, time_window=60)
    
    print("Creating agent for secure data processing...")
    # Create an agent for secure data processing
    secure_processor = Agent(name="SecureProcessor", supported_modalities=["text"])
    
    # Register and start the agent
    agents.register_agent(secure_processor)
    if security.check_access(token, "agent/SecureProcessor", "execute"):
        secure_processor.start()
        print(f"Agent {secure_processor.name} started.")
    else:
        print("Access denied to start agent. Exiting.")
        security.logout(token)
        return
    
    print("Processing data with security and guardrails...")
    # Process data with guardrails and security checks
    user_id = "example_user"
    data_samples = [
        "This is a safe data sample.",
        "Another safe input for processing.",
        "This input is way too long to be considered safe because it exceeds the maximum length allowed by the guardrail rules set for this agent in the configuration settings."
    ]
    
    for data in data_samples:
        print(f"\nAttempting to process data: '{data[:50]}...'")
        # Check rate limit
        if not limiter.check_rate_limit(user_id):
            print("Rate limit exceeded. Please wait before processing more data.")
            continue
        
        # Validate input
        validation_result = validator.validate_input(data)
        if not validation_result["valid"]:
            print(f"Input validation failed: {validation_result['reason']}")
            continue
        
        # Check access permission for processing
        if not security.check_access(token, "data/secure", "write"):
            print("Access denied for processing this data.")
            continue
        
        # Process the data with the agent
        result = secure_processor.perform_task(data, modality="text")
        print(f"Processing result: {result}")
        
        # Encrypt the result for secure storage or transmission
        encrypted_result = security.secure_data(result.encode())
        print(f"Encrypted result: {encrypted_result[:50]}...")
        
        # Decrypt to verify
        decrypted_result = security.access_secure_data(encrypted_result)
        print(f"Decrypted result for verification: {decrypted_result.decode()}")
    
    print("Cleaning up...")
    # Stop the agent
    secure_processor.stop()
    print("Agent stopped.")
    
    # Logout
    security.logout(token)
    print("Session logged out.")
    
    print("Secure data processing demonstration completed.")

if __name__ == "__main__":
    main()
