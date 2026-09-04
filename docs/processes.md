---
title: Processes
description: Run a list of callables sequentially, in a bounded thread pool, or half-and-half with agenticaiframework.processes.Process, and route work through agents with SequentialWorkflow and ParallelWorkflow.
tags:
  - processes
  - workflows
  - concurrency
---

# Processes

`agenticaiframework.processes.Process` collects callables with their arguments and runs them with one of three strategies: `sequential`, `parallel` (a `concurrent.futures.ThreadPoolExecutor` bounded by `max_workers`) or `hybrid`. `agenticaiframework.workflows` adds `SequentialWorkflow` and `ParallelWorkflow`, which run a callable through agents registered in an `AgentManager`. Use `Process` when you have plain Python steps to fan out or chain; use the workflows when the steps should be executed and tracked by agents.

## At a glance

| Class / function | Purpose |
|---|---|
| `Process(name, strategy="sequential", max_workers=None)` | Container for callables plus an execution strategy |
| `process.add_task(fn, *args, **kwargs)` / `add_step(...)` | Append a callable with its arguments (`add_step` is an alias) |
| `process.execute()` | Run all tasks, return their results in insertion order |
| `process.status` | `initialized`, `running`, `completed` or `failed` |
| `SequentialWorkflow(manager).execute_sequential(data, agent_chain, task_callable)` | Pass a value through a chain of agents |
| `ParallelWorkflow(manager).execute_parallel_sync(data, agent_names, task_callable, max_workers=None)` | Run the same callable on several agents in threads |
| `ParallelWorkflow(manager).execute_parallel(...)` | `async` variant using the running event loop |

## Quick example

```python
from agenticaiframework import Process

proc = Process(name="fetch_all", strategy="parallel", max_workers=4)
for source in ("arxiv", "scholar", "pubmed"):
    proc.add_task(lambda s: f"fetched {s}", source)

print(proc.status)          # initialized
print(proc.execute())       # ['fetched arxiv', 'fetched scholar', 'fetched pubmed']
print(proc.status)          # completed
```

## Execution strategies

| Strategy | Behaviour | Use when |
|---|---|---|
| `sequential` | Tasks run one after another in insertion order on the calling thread | Steps have side effects that must happen in order |
| `parallel` | All tasks are submitted to a `ThreadPoolExecutor(max_workers)`; results are collected in insertion order | Independent I/O-bound work such as API calls or file reads |
| `hybrid` | The first half of the task list runs sequentially, the second half in parallel | A setup phase followed by an independent fan-out |

The default `max_workers` is `min(32, os.cpu_count() + 4)`. Each task receives only the arguments given to `add_task`; the return value of one task is not passed to the next. Chain values yourself if a step depends on the previous result.

### Sequential

```python
from agenticaiframework import Process

def extract(url: str) -> dict:
    return {"url": url, "data": "raw"}

def transform(record: dict) -> dict:
    return {**record, "cleaned": True}

pipeline = Process(name="etl", strategy="sequential")
pipeline.add_task(extract, "https://example.com/data.json")
pipeline.add_task(transform, {"url": "https://example.com/data.json", "data": "raw"})

extracted, transformed = pipeline.execute()
print(transformed["cleaned"])       # True
```

### Parallel

```python
import time
from agenticaiframework import Process

def fetch(url: str) -> str:
    time.sleep(0.2)                  # stands in for network I/O
    return f"fetched:{url}"

proc = Process(name="fetch_all", strategy="parallel", max_workers=8)
for url in ("https://api.example.com/a", "https://api.example.com/b", "https://api.example.com/c"):
    proc.add_task(fetch, url)

started = time.perf_counter()
results = proc.execute()
print(results, f"{time.perf_counter() - started:.2f}s")   # about 0.2s rather than 0.6s
```

!!! warning "Thread safety"
    Callables submitted with the `parallel` or `hybrid` strategy run on worker threads at the same time. Do not mutate shared state from them without a lock.

### Hybrid

```python
from agenticaiframework import Process

def load_config() -> dict:
    return {"batch_size": 100}

def validate_config(cfg: dict) -> bool:
    return "batch_size" in cfg

def process_shard(shard_id: int) -> str:
    return f"shard-{shard_id} done"

proc = Process(name="pipeline", strategy="hybrid")
proc.add_task(load_config)
proc.add_task(validate_config, {"batch_size": 100})
proc.add_task(process_shard, 1)
proc.add_task(process_shard, 2)

# load_config and validate_config run sequentially; both process_shard calls run in parallel
print(proc.execute())
```

## Process Lifecycle

```text
initialized ──▶ running ──▶ completed
                      │
                      └──▶ failed (on unhandled exception)
```

`execute()` sets `status` to `running`, then `completed`. If any task raises, the status becomes `failed`, the exception is logged with `logger.exception` and re-raised to the caller; results from tasks that had already completed are discarded. Catch exceptions inside a task if partial failure should not stop the process.

```python
from agenticaiframework import Process

def boom():
    raise RuntimeError("disk full")

proc = Process(name="fragile")
proc.add_task(boom)
try:
    proc.execute()
except RuntimeError as exc:
    print(proc.status, exc)          # failed disk full
```

## Agent workflows

`agenticaiframework.workflows` runs a callable through agents that are registered in an `AgentManager`. Agents are resolved by id or by name; an unknown key raises `ValueError`. Each step calls `agent.execute_task(task_callable, value)`, so the agent's `performance_metrics` and context window are updated and exceptions are captured as `None` results (see [Agents](agents.md#error-handling)).

```python
import asyncio
from agenticaiframework import Agent, AgentManager
from agenticaiframework.workflows import SequentialWorkflow, ParallelWorkflow

manager = AgentManager()
for name in ("Cleaner", "Enricher", "Publisher"):
    manager.register_agent(Agent.quick(name, role="assistant"))

def step(payload: dict) -> dict:
    return {**payload, "hops": payload.get("hops", 0) + 1}

sequential = SequentialWorkflow(manager)
print(sequential.execute_sequential({"hops": 0}, ["Cleaner", "Enricher", "Publisher"], step))
# {'hops': 3}

parallel = ParallelWorkflow(manager)
print(parallel.execute_parallel_sync({"hops": 0}, ["Cleaner", "Enricher"], step, max_workers=2))
# [{'hops': 1}, {'hops': 1}]

print(asyncio.run(parallel.execute_parallel({"hops": 0}, ["Publisher"], step)))
print(manager.get_aggregate_metrics()["total_tasks"])   # 6
```

`execute_sequential` threads the return value of each agent into the next call; the parallel variants give every agent the same `data` and return one result per agent in the order of `agent_names`. For coordination patterns beyond these two (hierarchical, consensus, round-robin and so on) use the [Orchestration](orchestration.md) engine.

## API summary

| Symbol | Signature / key methods | Notes |
|---|---|---|
| `Process` | `Process(name, strategy="sequential", max_workers=None)`; `add_task(fn, *args, **kwargs)`, `add_step(...)`, `execute() -> list` | Attributes: `name`, `strategy`, `tasks`, `status`, `max_workers` (`__slots__`) |
| `SequentialWorkflow` | `SequentialWorkflow(manager)`; `execute_sequential(data, agent_chain, task_callable) -> Any` | `agent_chain` holds agent ids or names |
| `ParallelWorkflow` | `ParallelWorkflow(manager)`; `execute_parallel_sync(data, agent_names, task_callable, max_workers=None) -> list`; `async execute_parallel(data, agent_names, task_callable) -> list` | Thread pool or `loop.run_in_executor` |

## Related

- [Tasks](tasks.md): `Task` and `TaskManager` for named, tracked callables
- [Orchestration](orchestration.md): multi-agent coordination patterns
- [Agents](agents.md): `execute_task` and `AgentManager`
- [Performance](performance.md): sizing thread pools
