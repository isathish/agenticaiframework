---
title: Agent Example
description: Step-by-step walkthrough for creating, registering, and controlling agents with AgentManager
tags:
  - example
  - agents
  - basic
  - tutorial
---

# 🤖 Agent Management Example

This guide provides a **professional, step-by-step walkthrough** for creating, registering, and controlling an agent using the `AgentManager` and `Agent` classes from the `agenticaiframework` package.  
It is intended for developers building intelligent systems that require autonomous or semi-autonomous agents.

!!! info "Part of 400+ Module Framework"
    This example uses core agent modules. For enterprise agent patterns including multi-tenant agents and advanced orchestration, see [Enterprise Documentation](../enterprise.md).


## Prerequisites & Configuration

- **Installation**: Ensure `agenticaiframework` is installed and accessible in your Python environment.
- **No additional configuration** is required for this example.
- **Python Version**: Compatible with Python 3.10+.


## Code

```python
import logging

logger = logging.getLogger(__name__)

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
    logger.info("Registered Agents:", [agent.name for agent in agent_manager.agents])

    # Retrieve a specific agent
    retrieved_agent = agent_manager.get_agent("ExampleAgent")
    logger.info("Retrieved Agent:", retrieved_agent.name)
```


## Step-by-Step Execution

1. **Import Required Classes**  
   Import `AgentManager` and `Agent` from `agenticaiframework.agents`.

2. **Instantiate the Agent Manager**  
   Create an instance of `AgentManager` to handle agent registration and lifecycle management.

3. **Create an Agent**  
   Instantiate an `Agent` with a unique name.

4. **Register the Agent**  
   Use `register_agent` to add the agent to the manager's registry.

5. **Control the Agent**  
   Use `start`, `pause`, `resume`, and `stop` to manage the agent's lifecycle.

6. **List Registered Agents**  
   Access the `agents` list to see all registered agents.

7. **Retrieve a Specific Agent**  
   Use `get_agent` to fetch an agent by name.

> **Best Practice:** Assign meaningful names to agents to make debugging and monitoring easier.


## Expected Input

No user input is required; the script uses hardcoded values for demonstration purposes. In production, agent names and behaviors could be dynamically configured based on application needs.


## Expected Output

```
[YYYY-MM-DD HH:MM:SS] [Agent:ExampleAgent] Agent ExampleAgent started.
[YYYY-MM-DD HH:MM:SS] [Agent:ExampleAgent] Agent ExampleAgent paused.
[YYYY-MM-DD HH:MM:SS] [Agent:ExampleAgent] Agent ExampleAgent resumed.
[YYYY-MM-DD HH:MM:SS] [Agent:ExampleAgent] Agent ExampleAgent stopped.
Registered Agents: ['ExampleAgent']
Retrieved Agent: ExampleAgent
```


## How to Run

Run the example from the project root:

```bash
python examples/agents_example.py
```

If installed as a package, you can also run it from anywhere:

```bash
python -m examples.agents_example
```

> **Tip:** Integrate `AgentManager` with monitoring and task management systems for full lifecycle control of agents in production environments.
