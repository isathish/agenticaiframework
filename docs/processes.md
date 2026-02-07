---
title: Processes
description: Execute multi-step workflows with sequential, parallel, and hybrid strategies using bounded thread pools
tags:
  - processes
  - workflows
  - parallel
  - concurrency
---

# :material-cog-transfer: Processes

**Execute multi-step workflows with sequential, parallel, and hybrid strategies.**

Thread-safe task execution with bounded `ThreadPoolExecutor` and automatic resource management.

!!! tip "v2.0 Improvements"
    Processes now use **bounded thread pools** (`min(32, cpu_count + 4)` workers),
    `__slots__` for lower memory overhead, and proper structured logging.

---

## Overview

The `Process` class orchestrates callable tasks using one of three execution strategies:

| Strategy | Description | Best For |
|----------|-------------|----------|
| `sequential` | Tasks run one after another in the order added | Pipelines where each step depends on the previous |
| `parallel` | All tasks run concurrently via `ThreadPoolExecutor` | Independent I/O-bound or CPU-bound work |
| `hybrid` | First half sequentially, second half in parallel | Mixed dependency / fan-out patterns |

---

## Sequential Execution

Tasks run one at a time in insertion order. The result list preserves that order.

```python
from agenticaiframework import Process

def extract(url: str) -> dict:
    return {"url": url, "data": "..."}

def transform(record: dict) -> dict:
    record["cleaned"] = True
    return record

pipeline = Process(name="etl", strategy="sequential")
pipeline.add_task(extract, "https://example.com/data.json")
pipeline.add_task(transform, {"url": "...", "data": "raw"})

results = pipeline.execute()
# results is a list of return values in task order
```

---

## Parallel Execution

All tasks are submitted to a `ThreadPoolExecutor` and run concurrently. The
default worker count is `min(32, os.cpu_count() + 4)`, matching the Python 3.13
default, and can be overridden via `max_workers`.

```python
import time
from agenticaiframework import Process

def fetch(url: str) -> str:
    time.sleep(0.5) # simulate network I/O
    return f"fetched:{url}"

urls = ["https://api.example.com/a",
    "https://api.example.com/b",
    "https://api.example.com/c",
]

proc = Process(name="fetch_all", strategy="parallel", max_workers=8)
for url in urls:
    proc.add_task(fetch, url)

results = proc.execute() # completes in ~0.5 s instead of ~1.5 s
```

!!! warning "Thread Safety"
    Tasks submitted to the parallel executor **must be thread-safe**.
    Avoid mutating shared state without synchronisation.

---

## Hybrid Execution

The first half of the task list runs sequentially; the second half runs in
parallel. Useful when initial steps produce data that later steps consume
independently.

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

# load_config + validate_config run sequentially,
# then process_shard(1) + process_shard(2) run in parallel
results = proc.execute()
```

---

## Process Lifecycle

Every `Process` instance transitions through these states:

```text
initialized ──▶ running ──▶ completed
                      │
                      └──▶ failed (on unhandled exception)
```

Check the current state via `process.status`.

---

## API Reference

### `Process`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Human-readable process identifier |
| `strategy` | `str` | `"sequential"` | One of `"sequential"`, `"parallel"`, `"hybrid"` |
| `max_workers` | `int` or `None` | `None` | Thread pool size (defaults to `min(32, cpu_count + 4)`) |

**Attributes** (via `__slots__`): `name`, `strategy`, `tasks`, `status`, `max_workers`

#### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `add_task(callable, *args, **kwargs)` | `None` | Append a callable with its arguments |
| `add_step(callable, *args, **kwargs)` | `None` | Alias for `add_task` |
| `execute()` | `list[Any]` | Run all tasks and return results in order |

---

## Best Practices

!!! success "Do"
    - Keep tasks as **pure functions** — accept input, return output, no side effects.
    - Use `sequential` when order or data dependencies matter.
    - Use `parallel` for independent I/O-bound work (API calls, file reads).
    - Set `max_workers` explicitly for CPU-bound loads to avoid over-subscription.
    - Handle exceptions inside tasks when partial failure is acceptable.

!!! danger "Don't"
    - Mutate shared mutable state from parallel tasks without a lock.
    - Use `parallel` strategy for tasks that must run in order.
    - Ignore the return value of `execute()` — it contains all task results.

---

## Related Documentation

- [Orchestration](orchestration.md) — multi-agent orchestration engine
- [Tasks](tasks.md) — individual task definitions
- [Agents](agents.md) — agent lifecycle
- [Performance](performance.md) — tuning thread pools and concurrency
