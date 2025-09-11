from agenticaiframework.agents import Agent, AgentManager

# Example: Using the Agent and AgentManager
# ------------------------------------------
# This example demonstrates how to:
# 1. Create agents
# 2. Manage their lifecycle (start, pause, resume, stop)
# 3. Register and retrieve agents using AgentManager
#
# Expected Output:
# - Logs showing agent lifecycle events
# - List of registered agents and retrieval results

if __name__ == "__main__":
    # Create an agent manager
    agent_manager = AgentManager()

    # Create an agent
    agent = Agent(
        name="TestAgent",
        role="Demo Role",
        capabilities=["task_execution", "logging"],
        config={"version": "1.0"}
    )

    # Manage agent lifecycle
    agent.start()
    agent.pause()
    agent.resume()
    agent.stop()

    # Register the agent
    agent_manager.register_agent(agent)

    # List all agents
    agents_list = agent_manager.list_agents()
    print("Registered Agents:", [a.name for a in agents_list])

    # Retrieve the agent by ID
    retrieved_agent = agent_manager.get_agent(agent.id)
    print("Retrieved Agent:", retrieved_agent.name if retrieved_agent else "Not found")

    # Broadcast a message to all agents
    agent_manager.broadcast("System maintenance scheduled.")
