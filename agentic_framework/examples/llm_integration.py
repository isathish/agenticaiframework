"""
LLM Integration Example for Agentic Framework SDK

This script demonstrates how to integrate Large Language Models (LLMs) with the Agentic Framework SDK
to perform natural language processing tasks. It showcases the usage of LLMs, Agents, and Prompts components
to generate responses based on user input, with security checks in place.
"""

import sys
import os
import time

# Adjust the path to import from the agentic_framework module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentic_framework import initialize_framework
from agentic_framework.agents import Agent
from agentic_framework.security import SecurityLevel
from agentic_framework.llms import SimpleLLM
from agentic_framework.prompts import PromptTemplate

def main():
    """
    Main function to demonstrate LLM integration with the Agentic Framework SDK.
    """
    print("Initializing Agentic Framework SDK...")
    
    # Initialize the framework with a configuration
    config = {
        "secret_key": "llm_example_key_789",
        "security_level": SecurityLevel.MEDIUM,
        "guardrail_rules": {"max_length": 150}
    }
    framework = initialize_framework(config)
    
    # Access initialized components
    security = framework["security"]
    agents = framework["agents"]
    prompts = framework["prompts"]
    llms = framework["llms"]
    
    print("Authenticating an agent...")
    # Authenticate for security purposes
    credentials = {'username': 'agent:default', 'password': 'secure_password_123'}
    token = security.authenticate_component(credentials)
    if not token:
        print("Authentication failed. Exiting.")
        return
    print("Authentication successful.")
    
    print("Activating framework components...")
    # Ensure all framework components are activated
    for component in framework.values():
        try:
            if hasattr(component, 'activate'):
                component.activate()
                print(f"Component {component.__class__.__name__} activated.")
        except Exception as e:
            print(f"Error activating component: {str(e)}")
    
    print("Setting up LLM...")
    # Set up an LLM for natural language processing with Azure OpenAI
    azure_config = {
        "endpoint": "https://sathi-ma2quq4p-eastus2.cognitiveservices.azure.com/openai/deployments/gpt-4.1/chat/completions?api-version=2025-01-01-preview",
        "api_key": "2zONVGezgdzB0ju91mGzUdu45LRsSjrMjWGhtyeS90ce3X1VfSZ8JQQJ99BDACHYHv6XJ3w3AAAAACOGZyqh",
        "api_version": "2024-12-01-preview",
        "model": "gpt-4.1"
    }
    general_llm = SimpleLLM(name="AzureOpenAI_GPT4", config=azure_config)
    llms.register_llm(general_llm)
    print(f"LLM {general_llm.name} registered with Azure OpenAI configuration.")
    
    print("Creating agent for language processing...")
    # Create an agent for language processing tasks
    language_agent = Agent(name="LanguageProcessor", supported_modalities=["text"])
    
    # Register and start the agent
    agents.register_agent(language_agent)
    if security.check_access(token, "agent/LanguageProcessor", "execute"):
        language_agent.start()
        print(f"Agent {language_agent.name} started.")
    else:
        print("Access denied to start agent. Exiting.")
        security.logout(token)
        return
    
    print("Setting up prompt template...")
    # Set up a prompt template for LLM queries
    template = PromptTemplate(name="QueryTemplate", 
                              structure="You are an expert in {domain}. Answer the following question: {question}")
    prompts.add_prompt(template)
    print(f"Prompt template {template.name} added.")
    
    print("Processing language queries with LLM integration...")
    # Process language queries with LLM integration
    queries = [
        {"domain": "artificial intelligence", "question": "What is an agentic framework?"},
        {"domain": "history", "question": "Who was the first president of the United States?"},
        {"domain": "science", "question": "Explain the theory of relativity in simple terms."}
    ]
    
    for query in queries:
        print(f"\nProcessing query: '{query['question'][:50]}...' in domain '{query['domain']}'")
        # Retrieve the template and generate the prompt
        template = prompts.get_prompt("QueryTemplate")
        if not template:
            print("Template 'QueryTemplate' not found.")
            continue
        prompt_text = template.generate(query)
        print(f"Generated prompt: {prompt_text}")
        
        # Check access permission for using LLM
        if not security.check_access(token, "llm/GeneralModel", "execute"):
            print("Access denied for using this LLM.")
            continue
        
        # Generate response using the LLM
        response = llms.generate_response(prompt_text, context={"domain": query["domain"]})
        print(f"LLM response: {response['content'][:100]}...")
        
        # Optionally, have the agent perform a related task
        agent_task = f"Summarize: {response['content'][:200]}"
        agent_result = language_agent.perform_task(agent_task, modality="text")
        print(f"Agent summary: {agent_result}")
    
    print("Cleaning up...")
    # Stop the agent
    language_agent.stop()
    print("Agent stopped.")
    
    # Logout
    security.logout(token)
    print("Session logged out.")
    
    print("LLM integration demonstration completed.")

if __name__ == "__main__":
    main()
