---
title: Tasks
description: Wrap a callable in a named Task with an objective and inputs, run it with lifecycle tracking, and register many tasks in a thread-safe TaskManager.
tags:
  - tasks
  - core
---

# Tasks

`agenticaiframework.tasks` provides `Task`, a named callable with an objective, keyword inputs, a status and a stored result, and `TaskManager`, a thread-safe registry that can run tasks by id or name or all at once. Tasks are the smallest unit of work in the framework: agents call them through `Agent.execute_task`, processes fan them out, and the orchestration engine uses callables with the same shape. Use this module when you want a unit of work with a name and a recorded outcome rather than a bare function call.

## At a glance

| Class / function | Purpose |
|---|---|
| `Task(name, objective, executor, inputs=None)` | A callable plus metadata; `inputs` are passed as keyword arguments |
| `task.run()` | Execute once, set `status` to `completed` or `failed`, store and return `result` |
| `task.status`, `task.result`, `task.id` | Lifecycle state, last result, generated UUID |
| `TaskManager()` | Registry keyed by task id, guarded by a lock |
| `manager.register_task(task)` / `remove_task(task_id)` | Add or drop a task |
| `manager.get_task(task_id)` / `list_tasks()` | Look up one or all tasks |
| `manager.execute_task(name_or_id)` | Run one task by id or by name |
| `manager.run_all()` | Run every registered task; returns `{task_id: result}` |
| `TaskExecutionError` | Exception type exported for your own executors |

## Quick example

```python
from agenticaiframework import Task, TaskManager

task = Task(name="double", objective="Double a number", executor=lambda x: x * 2, inputs={"x": 21})
print(task.status)          # pending
print(task.run())           # 42
print(task.status, task.result)   # completed 42

manager = TaskManager()
manager.register_task(task)
manager.register_task(Task("greet", "Say hello", lambda name: f"hello {name}", {"name": "Ada"}))

print(manager.execute_task("greet"))            # hello Ada   (lookup by name)
print(manager.run_all())                        # {<task-id>: 42, <task-id>: 'hello Ada'}
print([t.name for t in manager.list_tasks()])   # ['double', 'greet']
```

## Defining a task

```python
from agenticaiframework import Task

def summarise(text: str, max_words: int = 20) -> str:
    words = text.split()
    return " ".join(words[:max_words]) + ("..." if len(words) > max_words else "")

task = Task(
    name="summarise_intro",
    objective="Shorten the introduction to twenty words",
    executor=summarise,
    inputs={"text": "AgenticAI Framework is a zero-dependency SDK ...", "max_words": 6},
)
print(task.id)              # uuid4 string
print(task.version)         # 1.0.0
print(task.run())           # AgenticAI Framework is a zero-dependency SDK...
```

- `executor` is any callable. `run()` calls it as `executor(**inputs)`; positional arguments are not supported, so wrap them in a lambda or `functools.partial`.
- `inputs` defaults to `{}`. It is a plain dict you can mutate between runs.
- `Task` uses `__slots__`; the available attributes are `id`, `name`, `objective`, `executor`, `inputs`, `status`, `result`, `version`.

## Lifecycle and error handling

```text
pending ──▶ running ──▶ completed
                  │
                  └──▶ failed
```

`run()` never raises. Exceptions from the executor are logged (`TypeError`, `ValueError`, `KeyError`, `AttributeError` at `ERROR` level, anything else with a traceback via `logger.exception`), `status` becomes `failed` and `run()` returns the previous `result`, which is `None` on the first attempt. A task can be run again; each call resets `status` to `running` first.

```python
from agenticaiframework import Task

def divide(a: int, b: int) -> float:
    return a / b

task = Task("ratio", "Divide two numbers", divide, {"a": 1, "b": 0})
print(task.run())            # None
print(task.status)           # failed

task.inputs["b"] = 4
print(task.run(), task.status)   # 0.25 completed
```

If your executor needs to signal a domain failure with structured information, raise `TaskExecutionError(message, task_name=, original_error=)` from `agenticaiframework.tasks` (re-exported from `agenticaiframework.exceptions`). It is caught by `run()` like any other exception, so read `task.status` to detect it, or call the executor directly when you want the exception to propagate.

## TaskManager

```python
from agenticaiframework import Task, TaskManager

manager = TaskManager()
ids = []
for n in range(3):
    task = Task(f"square_{n}", "Square a number", lambda x: x * x, {"x": n})
    manager.register_task(task)
    ids.append(task.id)

print(manager.get_task(ids[1]).name)             # square_1
print(manager.execute_task(ids[2]))              # 4
print(manager.execute_task("square_0"))          # 0
print(manager.execute_task("missing"))           # None, with a warning in the log

results = manager.run_all()                      # {task_id: result}
print([results[i] for i in ids])                 # [0, 1, 4]

manager.remove_task(ids[0])
print(len(manager.list_tasks()))                 # 2
```

- Registration, lookup and removal hold a `threading.Lock`, so a manager can be shared between threads.
- `run_all()` snapshots the registry under the lock and then runs tasks sequentially in registration order, outside the lock. To run tasks concurrently, add their `run` methods to a `Process(strategy="parallel")` (see below).
- `execute_task` tries the argument as an id first, then as a name. Names are not required to be unique; the first match wins.

## Combining tasks with processes and agents

```python
from agenticaiframework import Task, Process

tasks = [Task(f"fetch_{s}", f"Fetch {s}", lambda src=s: f"fetched {src}") for s in ("arxiv", "pubmed")]

proc = Process(name="fetch_all", strategy="parallel", max_workers=2)
for task in tasks:
    proc.add_task(task.run)

print(proc.execute())                            # ['fetched arxiv', 'fetched pubmed']
print([t.status for t in tasks])                 # ['completed', 'completed']
```

Agents can execute a task's callable with metrics tracking: `agent.execute_task(task.executor, **task.inputs)` increments the agent's `total_tasks` and `successful_tasks` counters and records the call in the agent's context window (see [Agents](agents.md#error-handling)). To run one callable through several agents, use `SequentialWorkflow` or `ParallelWorkflow` from `agenticaiframework.workflows`, documented in [Processes](processes.md#agent-workflows).

## API summary

| Symbol | Signature / key methods | Notes |
|---|---|---|
| `Task` | `Task(name, objective, executor, inputs=None)`; `run() -> Any` | Attributes: `id`, `name`, `objective`, `executor`, `inputs`, `status` (`pending`/`running`/`completed`/`failed`), `result`, `version` |
| `TaskManager` | `register_task(task)`, `get_task(task_id) -> Task \| None`, `list_tasks() -> list[Task]`, `remove_task(task_id)`, `execute_task(name_or_id) -> Any`, `run_all() -> dict[str, Any]` | Thread-safe; `tasks` attribute is the underlying `{id: Task}` dict |
| `TaskExecutionError` | `TaskExecutionError(message=None, task_name=None, original_error=None)` | Subclass of `TaskError` in `agenticaiframework.exceptions` |

## Related

- [Processes](processes.md): sequential, parallel and hybrid execution of callables; agent workflows
- [Orchestration](orchestration.md): running a task callable across a team of agents with ten coordination patterns
- [Agents](agents.md): `Agent.execute_task` and performance metrics
