# AgenticAI Framework — Processes Module Documentation

## Overview
The `processes` module defines and manages workflows for agents. It supports both synchronous and asynchronous execution, enabling flexible orchestration of tasks.


## Key Functions

### `run_process(name, params)`
Run a registered process by name with the given parameters.

### `run_process_async(func)`
Run a process asynchronously, useful for I/O-bound or long-running tasks.


## Example Usage

### Running a Synchronous Process
```python
from agenticaiframework.processes import run_process

def greet():
    return "Hello, World!"

result = run_process(greet)
print(result)  # Output: Hello, World!
```

### Running an Asynchronous Process
```python
import asyncio
from agenticaiframework.processes import run_process_async

async def async_task():
    return "Completed async task"

result = asyncio.run(run_process_async(async_task))
print(result)
```


## Use Cases

- **Data Processing Pipelines** — Chain multiple processes for ETL workflows.
- **Parallel Execution** — Run multiple processes concurrently.
- **Background Tasks** — Offload long-running tasks to asynchronous processes.


## Best Practices

- Keep processes modular and reusable.
- Avoid blocking operations in asynchronous processes.
- Use descriptive names for registered processes.


## Related Documentation
- [Hub Module](hub.md)
- [Agents Module](agents.md)
- [Memory Module](memory.md)
