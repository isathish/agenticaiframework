---
title: Orchestration
description: Coordinate several agents with AgentTeam roles, AgentSupervisor restart strategies and the ten OrchestrationEngine patterns (sequential, parallel, hierarchical, swarm, consensus, pipeline, broadcast, round-robin, priority, adaptive).
tags:
  - orchestration
  - multi-agent
---

# Orchestration

`agenticaiframework.orchestration` coordinates groups of agents. `AgentTeam` groups agents under named roles with a shared goal and shared context. `AgentSupervisor` owns agents, delegates tasks to the best available one and applies a restart strategy when an agent fails. `OrchestrationEngine.orchestrate()` runs one callable across a list of agents using one of ten patterns and records metrics and history. Use this package when a single `Agent` is not enough and you need to decide who does what, in which order, and what happens on failure.

## At a glance

| Class / function | Purpose |
|---|---|
| `OrchestrationEngine(default_pattern=SEQUENTIAL)` | Runs a callable across agents with a pattern; `orchestration_engine` is a module-level instance |
| `OrchestrationPattern` | `SEQUENTIAL`, `PARALLEL`, `HIERARCHICAL`, `SWARM`, `CONSENSUS`, `PIPELINE`, `BROADCAST`, `ROUND_ROBIN`, `PRIORITY`, `ADAPTIVE` |
| `AgentTeam(name, goal, roles=[TeamRole(...)])` | Role-based group with shared context, broadcast and step plans |
| `TeamRole(name, description, required_capabilities=[], max_agents=1, min_agents=1)` | Role definition; `max_agents` is enforced by `add_member` |
| `AgentSupervisor(name, config=SupervisionConfig(...), parent_supervisor=None)` | Delegation, health status, restart strategies, hierarchical escalation, handoffs |
| `SupervisionConfig` / `SupervisionStrategy` | Restart limits and backoff; `ONE_FOR_ONE`, `ONE_FOR_ALL`, `REST_FOR_ONE`, `ESCALATE`, `IGNORE` |
| `TaskAssignment` | Record of a delegated task: agent, status, result, error, timing, retries |
| `AgentHandoff` | Record of context passed from one agent to another |
| `AgentRole` / `AgentState` | Role given to an agent by a supervisor; the supervisor's view of the agent's state |

## Quick example

```python
import logging
from agenticaiframework import Agent
from agenticaiframework.orchestration import (
    AgentTeam, TeamRole, OrchestrationEngine, OrchestrationPattern,
)

logging.disable(logging.CRITICAL)

researcher = Agent.quick("Researcher", role="researcher")
writer = Agent.quick("Writer", role="writer")

team = AgentTeam(
    name="content_team",
    goal="Produce a sourced briefing on a topic",
    roles=[
        TeamRole(name="research", description="Collects and verifies facts"),
        TeamRole(name="writing", description="Turns facts into prose"),
    ],
)
team.add_member(researcher, role_name="research")
team.add_member(writer, role_name="writing")
print([m["name"] for m in team.get_team_status()["members"]])   # ['Researcher', 'Writer']

engine = OrchestrationEngine()
engine.register_team(team)

def handle(topic: str) -> str:
    return f"handled {topic}"

results = engine.orchestrate(
    agents=[researcher, writer],
    task_callable=handle,
    pattern=OrchestrationPattern.SEQUENTIAL,
    topic="battery recycling",
)
print(results)                    # ['handled battery recycling', 'handled battery recycling']
print(engine.get_metrics())
```

The task callable receives the keyword arguments you pass to `orchestrate()`; it does not receive the agent. Each call goes through `agent.execute_task`, which updates the agent's performance metrics and context window.

## OrchestrationEngine

### orchestrate()

```python
result = engine.orchestrate(
    agents,                       # List[Agent]
    task_callable,                # called as task_callable(**kwargs) on each agent
    pattern=OrchestrationPattern.PARALLEL,   # defaults to engine.default_pattern
    aggregator=sum,               # optional; applied when the pattern returns a list
    **kwargs,                     # forwarded to task_callable
)
```

Every call appends an entry to `engine.execution_history` (a deque capped at 5000) with `id`, `pattern`, `agent_count`, `started_at`, `completed_at`, `status` and a truncated `result` or `error`, and updates `engine.metrics` (`orchestrations_completed`, `orchestrations_failed`, `total_agent_invocations`). Exceptions raised by the pattern itself are re-raised after being recorded.

### Patterns

| Pattern | What the engine does | Returns |
|---|---|---|
| `SEQUENTIAL` | Calls the task on each agent in list order | `list` of results |
| `PARALLEL` | Submits one call per agent to a `ThreadPoolExecutor` (at most `min(32, cpu_count + 4)` workers) | `list` in completion order |
| `BROADCAST` | Same implementation as `PARALLEL`; use it when the intent is "tell everyone" | `list` |
| `HIERARCHICAL` | `agents[0]` is the manager; the rest run the task, then the manager receives `Worker results: [...]` as context | `{"manager": name, "worker_results": [...]}` |
| `PIPELINE` | Threads a value through the agents: the task is called as `task(previous, **kwargs)`; the first value is `kwargs["input"]` (or `None`) | the last agent's result |
| `CONSENSUS` | Runs `PARALLEL`, then picks the most common result by string equality | a single result |
| `ROUND_ROBIN` | Picks the agent with the lowest `total_tasks` and runs the task once | that agent's result |
| `SWARM` | Sequential run where each agent first receives `Swarm context: {swarm_size, iteration}` | `list` |
| `PRIORITY` | Falls back to `SEQUENTIAL`; reserved for priority ordering | `list` |
| `ADAPTIVE` | Falls back to `SEQUENTIAL`; reserved for runtime pattern selection | `list` |

```python
import logging
from agenticaiframework import Agent
from agenticaiframework.orchestration import OrchestrationEngine, OrchestrationPattern

logging.disable(logging.CRITICAL)
agents = [Agent.quick(n, role="assistant") for n in ("A", "B", "C")]
engine = OrchestrationEngine(default_pattern=OrchestrationPattern.PARALLEL)

print(engine.orchestrate(agents, lambda topic: len(topic), topic="battery", aggregator=sum))   # 21
print(engine.orchestrate(agents, lambda: "approve", pattern=OrchestrationPattern.CONSENSUS))   # approve
print(engine.orchestrate(agents, lambda topic: topic.upper(), pattern=OrchestrationPattern.HIERARCHICAL, topic="x"))
# {'manager': 'A', 'worker_results': ['X', 'X']}

def add_one(previous, **kwargs):
    return (previous or 0) + 1

print(engine.orchestrate(agents, add_one, pattern=OrchestrationPattern.PIPELINE, input=10))    # 13
print(engine.orchestrate(agents, lambda: "once", pattern=OrchestrationPattern.ROUND_ROBIN))    # once
print(engine.execution_history[-1]["pattern"], engine.get_metrics()["total_agent_invocations"])
```

!!! note "Failures inside the task"
    `Agent.execute_task` catches exceptions from the callable, logs them, increments the agent's `failed_tasks` counter and returns `None`. A failing step therefore shows up as `None` in the results rather than as an exception from `orchestrate()`.

`register_team(team)` and `register_supervisor(supervisor)` store objects in `engine.teams` / `engine.supervisors` so `get_metrics()` can report `registered_teams`, `registered_supervisors` and `execution_history_size`. The module-level `orchestration_engine` instance is what `Agent.call_orchestration(agents, task, pattern="sequential")` uses.

## AgentTeam

```python
import logging
from agenticaiframework import Agent
from agenticaiframework.orchestration import AgentTeam, TeamRole

logging.disable(logging.CRITICAL)

team = AgentTeam(
    name="support",
    goal="Resolve tier-1 tickets",
    roles=[
        TeamRole(name="triage", description="Classifies tickets", max_agents=2),
        TeamRole(name="resolver", description="Answers tickets", required_capabilities=["chat"]),
    ],
)
team.add_role(TeamRole(name="qa", description="Reviews answers"))

triage = Agent.quick("Triage", role="analyst")
resolver = Agent.quick("Resolver", role="assistant")
team.add_member(triage, role_name="triage")
team.add_member(resolver, role_name="resolver")
try:
    team.add_member(Agent.quick("Second", role="assistant"), role_name="resolver")
except ValueError as exc:
    print(exc)                                    # Role 'resolver' has max agents

print([a.name for a in team.get_members_by_role("triage")])

team.share_context("ticket_id", "T-1042", sender=triage)     # visible to every other member
team.broadcast_message(triage, "Ticket is about billing", importance=0.7)

results = team.execute_collaborative("resolve_T-1042", [
    {"role": "triage", "action": lambda text: "billing", "args": {"text": "Charged twice"}},
    {"role": "resolver", "action": lambda category: f"Refund policy for {category}", "args": {"category": "billing"}},
    {"role": "qa", "action": lambda: "ok"},                  # no agent in this role -> error entry
])
print(results["step_1"])                        # {'success': True, 'result': 'Refund policy for billing'}
print(results["step_2"])                        # {'error': "No agent for role 'qa'"}

status = team.get_team_status()
print(status["member_count"], status["roles"], status["metrics"])
team.remove_member(resolver.id)
```

- `add_member` raises `ValueError` when the role already holds `max_agents` members. Unknown role names are accepted without a limit. Joining a team adds a high-importance context entry to the agent.
- `execute_collaborative(task_name, task_plan)` runs each step on the first agent in the given role via `agent.execute_task(action, **args)`; a non-callable `action` is stored as the result. Results are stored in `team.task_results[task_name]` and each step result is shared with the team as `step_<i>_result`.
- `share_context(key, value, sender=None)` writes to `team.shared_context` and pushes a context entry to every member other than the sender. `broadcast_message` appends to `team.message_history` and increments `metrics["messages_exchanged"]`.
- `get_team_status()` returns `id`, `name`, `goal`, `status`, `member_count`, `roles`, `current_task`, `metrics` and a `members` list with each agent's id, name, role and status.

`Agent.delegate_to_team(team, task, coordinator_role=None)` is the agent-side entry point.

## AgentSupervisor

```python
import logging
from agenticaiframework import Agent
from agenticaiframework.orchestration import (
    AgentSupervisor, SupervisionConfig, SupervisionStrategy, AgentRole, AgentState,
)

logging.disable(logging.CRITICAL)

config = SupervisionConfig(
    strategy=SupervisionStrategy.ONE_FOR_ONE,   # restart only the failed agent
    max_restarts=3,                             # within restart_window seconds
    restart_window=60.0,
    initial_backoff=1.0, backoff_multiplier=2.0, max_backoff=60.0,
    health_check_interval=30.0, timeout=300.0,
)
print(config.get_backoff(3))                    # 4.0

supervisor = AgentSupervisor("ops", config=config)
coder = Agent.quick("Coder", role="coder")
writer = Agent.quick("Writer", role="writer")
supervisor.add_agent(coder)                                   # AgentRole.WORKER
supervisor.add_agent(writer, role=AgentRole.SPECIALIST)

task_id = supervisor.delegate_task(
    lambda text, n: text[:n], kwargs={"text": "release notes", "n": 7},
    priority=1, required_capability="writing",
)
task = supervisor.completed_tasks[-1]
print(task.task_id == task_id, task.agent_id == writer.id, task.status, task.result)   # True True completed release

print(supervisor.agent_states[coder.id])                     # AgentState.IDLE
print([a.name for a in supervisor.get_available_agents(capability="code-review")])   # ['Coder']

handoff_id = supervisor.handoff(coder, writer, context={"draft": "v1"}, reason="needs prose")
print(supervisor.handoffs[-1].to_dict()["reason"])

print(supervisor.get_health_status()["agents"][writer.id]["total_tasks"])   # 1
print(supervisor.get_metrics())
```

### Delegation

`delegate_task(task_callable, args=(), kwargs=None, priority=0, required_capability=None, preferred_agent_id=None, deadline=None)` creates a `TaskAssignment`, selects an agent and runs the task synchronously on it. Selection order: the preferred agent if it is `IDLE`; otherwise the idle agents with the required capability (checking child supervisors when none are local), scored by `success_rate - 0.01 * total_tasks`. If no agent is available the assignment is queued (sorted by descending priority) and drained the next time an agent finishes. The return value is the task id; look up the outcome in `supervisor.completed_tasks`, `active_tasks` or `task_queue`.

`TaskAssignment` fields: `task_id`, `agent_id`, `task_callable`, `args`, `kwargs`, `priority`, `deadline`, `dependencies`, `status` (`pending`, `assigned`, `completed`, `failed`), `result`, `error`, `assigned_at`, `started_at`, `completed_at`, `retries`, `max_retries=3`, `metadata`; properties `duration`, `is_complete`, `can_retry`.

### Supervision strategies

| Strategy | On failure |
|---|---|
| `ONE_FOR_ONE` | Restart the failed agent (`stop()` then `start()`) after the backoff |
| `ONE_FOR_ALL` | Restart every supervised agent |
| `REST_FOR_ONE` | Restart the failed agent and every agent added after it |
| `ESCALATE` | Call `parent_supervisor.handle_escalation(...)`; the parent reassigns the task to one of its own idle agents or escalates further |
| `IGNORE` | Record the failure and do nothing |

Restarts are counted per agent inside `restart_window`; when `max_restarts` is exceeded the failure is escalated to the parent instead. `SupervisionConfig.get_backoff(restart_count)` returns `min(initial_backoff * backoff_multiplier ** (restart_count - 1), max_backoff)` and the supervisor sleeps for that long before restarting. A task whose `can_retry` is true is re-queued at the front.

Because `Agent.execute_task` catches exceptions raised by the callable, an ordinary failing task completes with `result=None` and the restart path is not triggered; the strategies apply when the agent itself raises (for example a stopped agent or a failing `execute_task` override).

### Hierarchies and handoffs

`add_child_supervisor(supervisor)` sets the child's `parent_supervisor` and lets the parent's `get_all_agents(recursive=True)` and `delegate_task` reach the child's agents. `handoff(from_agent, to_agent, context, reason="")` appends an `AgentHandoff(handoff_id, from_agent_id, to_agent_id, context, timestamp, reason, success, metadata)` to `supervisor.handoffs`, adds the context to the receiving agent and returns the handoff id. `Agent.with_supervisor(supervisor)` records the relationship from the agent side.

`add_agent` sets `agent.supervisor_id` and replaces `agent.role` with the `AgentRole` value (`SUPERVISOR`, `WORKER`, `COORDINATOR`, `ROUTER`, `AGGREGATOR`, `MONITOR`, `SPECIALIST`, `GENERALIST`). `AgentState` values tracked per agent: `IDLE`, `BUSY`, `WAITING`, `BLOCKED`, `FAILED`, `RECOVERING`, `SUSPENDED`, `TERMINATED`.

`get_health_status()` returns the supervisor's id, name, status and uptime, one entry per agent (`name`, `state`, `success_rate`, `total_tasks`, `restarts`), the child supervisors' health and the metrics dict. `get_metrics()` returns `tasks_delegated`, `tasks_completed`, `tasks_failed`, `restarts`, `escalations`, `handoffs`, `total_agents`, `child_supervisors`, `queued_tasks`, `active_tasks`, `completed_tasks`, `total_handoffs`.

## Choosing a layer

| Need | Use |
|---|---|
| Run one callable on N agents and collect results | `OrchestrationEngine.orchestrate` with `SEQUENTIAL`, `PARALLEL` or `BROADCAST` |
| Chain results through agents | `PIPELINE`, or `SequentialWorkflow` in [Processes](processes.md#agent-workflows) |
| Majority vote | `CONSENSUS` |
| Load-based single assignment | `ROUND_ROBIN`, or `AgentSupervisor.delegate_task` when you also want retries, capability matching and queuing |
| Named roles with shared context and step plans | `AgentTeam.execute_collaborative` |
| Restart and escalation policy | `AgentSupervisor` with a `SupervisionConfig` |

## API summary

| Symbol | Signature / key methods | Notes |
|---|---|---|
| `OrchestrationEngine` | `OrchestrationEngine(default_pattern=OrchestrationPattern.SEQUENTIAL)`; `orchestrate(agents, task_callable, pattern=None, aggregator=None, **kwargs)`, `register_team(team)`, `register_supervisor(supervisor)`, `get_metrics()` | Attributes `teams`, `supervisors`, `workflows`, `execution_history`, `metrics`; module instance `orchestration_engine` |
| `OrchestrationPattern` | enum with 10 members | `PRIORITY` and `ADAPTIVE` currently behave like `SEQUENTIAL` |
| `AgentTeam` | `AgentTeam(name, goal, roles=None)`; `add_role`, `add_member(agent, role_name)`, `remove_member(agent_id)`, `get_members_by_role(role_name)`, `share_context(key, value, sender=None)`, `broadcast_message(sender, message, importance=0.5)`, `execute_collaborative(task_name, task_plan)`, `get_team_status()` | Attributes `id`, `members`, `role_assignments`, `shared_context`, `message_history`, `task_results`, `metrics` |
| `TeamRole` | `TeamRole(name, description, required_capabilities=[], max_agents=1, min_agents=1)`; `is_valid_count(count)` | dataclass |
| `AgentSupervisor` | `AgentSupervisor(name, config=None, parent_supervisor=None)`; `add_agent(agent, role=AgentRole.WORKER)`, `remove_agent(agent_id)`, `add_child_supervisor`, `get_all_agents(recursive=True)`, `get_available_agents(capability=None)`, `delegate_task(...) -> task_id`, `handoff(from_agent, to_agent, context, reason="") -> handoff_id`, `handle_escalation(child, agent, task, error)`, `get_health_status()`, `get_metrics()` | Attributes `agents`, `agent_states`, `task_queue`, `active_tasks`, `completed_tasks`, `handoffs`, `metrics` |
| `SupervisionConfig` | `SupervisionConfig(strategy=ONE_FOR_ONE, max_restarts=3, restart_window=60.0, backoff_multiplier=2.0, initial_backoff=1.0, max_backoff=60.0, health_check_interval=30.0, timeout=300.0)`; `get_backoff(restart_count)` | dataclass |
| `SupervisionStrategy` | `ONE_FOR_ONE`, `ONE_FOR_ALL`, `REST_FOR_ONE`, `ESCALATE`, `IGNORE` | enum |
| `TaskAssignment` | dataclass; `duration`, `is_complete`, `can_retry` properties | created by `delegate_task` |
| `AgentHandoff` | `AgentHandoff(handoff_id, from_agent_id, to_agent_id, context, timestamp=, reason="", success=True, metadata=)`; `to_dict()` | created by `handoff` |
| `AgentRole`, `AgentState` | enums | set by `add_agent`; tracked in `agent_states` |

## Related

- [Agents](agents.md): `execute_task`, `call_agent`, `handoff_to`, `delegate_to_team`
- [Processes](processes.md): `Process` and the `SequentialWorkflow` / `ParallelWorkflow` helpers
- [Memory](memory.md): `OrchestrationMemoryManager` for persisting orchestration runs
- [State](state.md): `OrchestrationStateManager` and `AgentCoordinationState`
