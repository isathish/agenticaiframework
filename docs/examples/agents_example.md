# Agents Example

This example demonstrates how to create, register, and control an agent using the `AgentManager` and `Agent` classes from the `agenticaiframework` package.

---

## Configuration
No special configuration is required. Ensure `agenticaiframework` is installed and accessible in your Python environment.

---

## Code

```python
from agenticaiframework.agents import AgentManager, Agent

if __name__ == "__main__":
    agent_manager = AgentManager()

    # Create and register an agent
    example_agent = Agent(name="ExampleAgent")
    agent_manager.register_agent(example_agent)

    # Control the agent
    example_agent.start()
    example_agent.pause()
    example_agent.resume()
    example_agent.stop()

    # List registered agents
    print("Registered Agents:", [agent.name for agent in agent_manager.agents])

    # Retrieve a specific agent
    retrieved_agent = agent_manager.get_agent("ExampleAgent")
    print("Retrieved Agent:", retrieved_agent.name)
```

---

## Step-by-Step Execution

1. **Import** `AgentManager` and `Agent` from `agenticaiframework.agents`.
2. **Instantiate** the agent manager.
3. **Create** an `Agent` instance with a name.
4. **Register** the agent with the manager.
5. **Control** the agent using `start`, `pause`, `resume`, and `stop`.
6. **List** all registered agents.
7. **Retrieve** a specific agent by name.

---

## Expected Input
No user input is required; the script uses hardcoded values for demonstration.

---

## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [Agent:ExampleAgent] Agent ExampleAgent started.
[YYYY-MM-DD HH:MM:SS] [Agent:ExampleAgent] Agent ExampleAgent paused.
[YYYY-MM-DD HH:MM:SS] [Agent:ExampleAgent] Agent ExampleAgent resumed.
[YYYY-MM-DD HH:MM:SS] [Agent:ExampleAgent] Agent ExampleAgent stopped.
Registered Agents: ['ExampleAgent']
Retrieved Agent: ExampleAgent
```

---

## How to Run

```bash
python examples/agents_example.py
