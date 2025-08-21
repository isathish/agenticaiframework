"""
Knowledge Retrieval Example for Agentic Framework SDK

This script demonstrates how to use knowledge retrieval with Retrieval-Augmented Generation (RAG)
in the Agentic Framework SDK to enhance agent decision-making. It showcases the usage of Knowledge,
Agents, and RAGRetriever components to retrieve relevant information from a knowledge source and
generate informed responses.
"""

import sys
import os
import time

# Adjust the path to import from the agentic_framework module
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agentic_framework import initialize_framework
from agentic_framework.agents import Agent
from agentic_framework.security import SecurityLevel
from agentic_framework.knowledge import RAGRetriever

def main():
    """
    Main function to demonstrate knowledge retrieval with the Agentic Framework SDK.
    """
    print("Initializing Agentic Framework SDK...")
    
    # Initialize the framework with a configuration
    config = {
        "secret_key": "knowledge_example_key_012",
        "security_level": SecurityLevel.MEDIUM,
        "guardrail_rules": {"max_length": 200}
    }
    framework = initialize_framework(config)
    
    # Access initialized components
    security = framework["security"]
    agents = framework["agents"]
    knowledge = framework["knowledge"]
    
    print("Authenticating an agent...")
    # Authenticate for security purposes
    credentials = {'username': 'agent:default', 'password': 'secure_password_123'}
    token = security.authenticate_component(credentials)
    if not token:
        print("Authentication failed. Exiting.")
        return
    print("Authentication successful.")
    
    print("Setting up knowledge source and retriever...")
    # Set up a simple knowledge source with sample documents
    sample_documents = [
        "Document 1: Agentic frameworks are systems that enable autonomous agents to perform complex tasks by leveraging AI and predefined workflows.",
        "Document 2: Retrieval-Augmented Generation (RAG) combines information retrieval with generative models to produce accurate responses based on external knowledge.",
        "Document 3: Knowledge retrieval systems improve decision-making by providing agents with relevant, up-to-date information from various sources."
    ]
    # Note: add_knowledge_source is not called here as it's handled by RAGRetriever config
    
    # Set up RAG retriever with the sample documents
    rag_retriever = RAGRetriever(name="SampleRAGRetriever", config={"knowledge_sources": [{"name": "SampleDocs", "data": sample_documents}]})
    print("Knowledge source and RAG retriever set up with sample documents.")
    
    print("Creating agent for knowledge-based tasks...")
    # Create an agent for knowledge-based tasks
    knowledge_agent = Agent(name="KnowledgeAgent", supported_modalities=["text"])
    
    # Register and start the agent
    agents.register_agent(knowledge_agent)
    if security.check_access(token, "agent/KnowledgeAgent", "execute"):
        knowledge_agent.start()
        print(f"Agent {knowledge_agent.name} started.")
    else:
        print("Access denied to start agent. Exiting.")
        security.logout(token)
        return
    
    print("Processing queries with knowledge retrieval...")
    # Process queries using knowledge retrieval
    queries = [
        "What is an agentic framework?",
        "Explain Retrieval-Augmented Generation.",
        "How does knowledge retrieval improve decision-making?"
    ]
    
    for query in queries:
        print(f"\nProcessing query: '{query}'")
        # Retrieve relevant knowledge
        if security.check_access(token, "knowledge/internal_docs", "read"):
            retrieved_docs = knowledge.retrieve_knowledge(query, source="internal_docs")
            print(f"Retrieved documents: {len(retrieved_docs)} relevant items found.")
            for i, doc in enumerate(retrieved_docs, 1):
                print(f"  {i}. {doc[:100]}...")
        else:
            print("Access denied for retrieving knowledge.")
            continue
        
        # Use RAG to enhance response generation
        rag_results = rag_retriever.retrieve(query)
        print(f"RAG results: {len(rag_results)} documents matched.")
        for i, result in enumerate(rag_results, 1):
            print(f"  {i}. {result[:100]}...")
        
        # Have the agent perform a task with the retrieved knowledge
        context = " ".join(rag_results[:2])  # Combine top 2 results for context
        agent_task = f"Answer based on context: {query} Context: {context[:300]}"
        agent_result = knowledge_agent.perform_task(agent_task, modality="text")
        print(f"Agent response: {agent_result}")
    
    print("Cleaning up...")
    # Stop the agent
    knowledge_agent.stop()
    print("Agent stopped.")
    
    # Logout
    security.logout(token)
    print("Session logged out.")
    
    print("Knowledge retrieval demonstration completed.")

if __name__ == "__main__":
    main()
