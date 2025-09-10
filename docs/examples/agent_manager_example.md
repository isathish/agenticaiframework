# Agent Manager Example

This guide provides a **comprehensive walkthrough** for creating, managing, and controlling agents using the `Agent` and `AgentManager` classes from the `agenticaiframework` package.

---

## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **Python Version**: Compatible with Python 3.8+.

---

## Code

```python
from agenticaiframework.agents import Agent, AgentManager

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
```

---

## Step-by-Step Execution

1. **Import Required Classes**  
   Import `Agent` and `AgentManager` from `agenticaiframework.agents`.

2. **Instantiate the Agent Manager**  
   Create an instance to handle agent registration and lifecycle management.

3. **Create an Agent**  
   Instantiate an `Agent` with a name, role, capabilities, and configuration.

4. **Manage Agent Lifecycle**  
   Use `start`, `pause`, `resume`, and `stop` to control the agent.

5. **Register the Agent**  
   Use `register_agent` to add the agent to the manager's registry.

6. **List All Agents**  
   Use `list_agents` to retrieve all registered agents.

7. **Retrieve an Agent by ID**  
   Use `get_agent` to fetch a specific agent.

8. **Broadcast a Message**  
   Use `broadcast` to send a message to all registered agents.

---

## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes.

---

## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [Agent:TestAgent] Agent TestAgent started.
[YYYY-MM-DD HH:MM:SS] [Agent:TestAgent] Agent TestAgent paused.
[YYYY-MM-DD HH:MM:SS] [Agent:TestAgent] Agent TestAgent resumed.
[YYYY-MM-DD HH:MM:SS] [Agent:TestAgent] Agent TestAgent stopped.
Registered Agents: ['TestAgent']
Retrieved Agent: TestAgent
[Broadcast] System maintenance scheduled.
```

---

## How to Run

Run the example from the project root:

```bash
python examples/agent_manager_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.agent_manager_example
```

> **Tip:** Use `AgentManager` to coordinate multiple agents in distributed or multi-tasking environments.
