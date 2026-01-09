from agenticaiframework.agents import Agent, AgentManager

# Example: Creating and managing agents
# --------------------------------------
# This example demonstrates how to:
# 1. Create an Agent with a specific role and capabilities
# 2. Start, pause, resume, and stop the agent
# 3. Register the agent with AgentManager
# 4. List and retrieve agents
#
# Expected Output:
# - Logs showing agent lifecycle events (start, pause, resume, stop)
# - Confirmation of agent registration and listing

if __name__ == "__main__":
    # Create an agent
    agent = Agent(
        name="ExampleAgent",
        role="Demo Role",
        capabilities=["demo_task", "logging"],
        config={"version": "1.0"}
    )

    # Start the agent
    agent.start()

    # Pause the agent
    agent.pause()

    # Resume the agent
    agent.resume()

    # Stop the agent
    agent.stop()

    # Create an AgentManager and register the agent
    manager = AgentManager()
    manager.register_agent(agent)

    # List all agents
    agents_list = manager.list_agents()
    print("Registered Agents:", [a.name for a in agents_list])

    # Retrieve the agent by ID
    retrieved_agent = manager.get_agent(agent.id)
    print("Retrieved Agent:", retrieved_agent.name if retrieved_agent else "Not found")
