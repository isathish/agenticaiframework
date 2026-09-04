---
title: Agents
description: How to construct Agent objects with Agent.quick, Agent.from_config or the raw constructor, call invoke() and stream(), read AgentOutput, and manage fleets with AgentManager.
tags:
  - agents
  - core
---

# Agents

`agenticaiframework.core` defines `Agent`, the object that owns an LLM manager, a context window, bound tools, guardrails and a tracer, and `AgentRunner`, the ReAct loop that turns a prompt into an `AgentOutput`. `AgentManager` keeps a registry of agents for lookup, broadcast and health reporting. Use this page when you build an agent, call it, inspect what it did, or run several of them from one process.

## At a glance

| Class / function | Purpose |
|---|---|
| `Agent.quick(name, role=..., provider=..., llm=..., tools=[...])` | Build an agent from a role template with the LLM taken from environment variables |
| `Agent.from_config(dict)` | Build an agent from a JSON/YAML-style dictionary |
| `Agent(name, role, capabilities, config, max_context_tokens=4096)` | Raw constructor; `config["llm"]` must be an `LLMManager` |
| `agent.invoke(prompt, ...)` | Run the agent to completion and return `AgentOutput` |
| `agent.stream(prompt, ...)` | Yield `AgentStep` objects while the run happens |
| `AgentOutput` / `AgentStep` / `AgentThought` | Structured result, individual steps and ReAct thoughts |
| `AgentStatus` / `StepType` | Enumerations used in the output |
| `AgentRunner` | The execution loop behind `invoke()`; usable directly with `AgentInput` |
| `AgentManager` | Registry with lookup by id, name or capability, broadcast, health checks |
| `ConversationManager`, `OutputFormatter`, `HumanInTheLoop` | Conversation history, output formatting and approvals; each has a section below |

## Quick example

```python
import logging
from agenticaiframework import Agent, AgentManager

logging.disable(logging.CRITICAL)          # keep the console quiet in this example

agent = Agent.quick("Assistant", role="assistant")
print(agent.status, agent.capabilities)    # running ['chat', 'reasoning', 'tool-use']

output = agent.invoke("Explain a mutex in one sentence.", temperature=0.2)
if output.is_success:
    print(output.response)
else:
    print(output.status, output.error)     # AgentStatus.ERROR LLM generation failed (no API key)

for step in output.steps:
    print(step.step_type.value, step.name)

manager = AgentManager()
manager.register_agent(agent)
print(manager.health_check())
```

Without a provider key `invoke()` does not raise; it returns an `AgentOutput` whose `status` is `AgentStatus.ERROR` and whose `steps` contain the `input` and `input_guardrails` steps that ran before the LLM call. Set `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` or `GOOGLE_API_KEY` to get a real response.

## Creating Agents

### Agent.quick

```python
from agenticaiframework import Agent

agent = Agent.quick(
    "Coder",
    role="coder",                 # template name or free-text role description
    provider="anthropic",         # preferred provider; falls back to whatever key exists
    llm="claude-3.5-haiku",       # model name on that provider
    tools=["FileReadTool"],       # tool class names from ToolRegistry
    auto_tools=False,             # True binds a default tool set per role
    guardrails=True,              # GuardrailPipeline.minimal()
    tracing=True,                 # global AgentStepTracer
)
```

`Agent.quick` calls `LLMManager.from_environment(auto_select=True, preferred_provider=provider)`, attaches a minimal guardrail pipeline and the global tracer, binds the tools, and calls `agent.start()`. Extra keyword arguments are merged into `agent.config`. If `role` is not one of the templates it is used verbatim as the role description and `capabilities` may be passed as a keyword argument.

### Role templates

`Agent.ROLE_TEMPLATES` maps template names to role descriptions; `Agent.ROLE_CAPABILITIES` supplies the default capability list.

| Template | Description | Capabilities |
|---|---|---|
| `assistant` | A helpful AI assistant that provides accurate, concise responses. | chat, reasoning, tool-use |
| `analyst` | A data analyst that examines information and provides insights. | data-analysis, visualization, tool-use |
| `coder` | A programming assistant that writes and reviews code. | code-generation, code-review, debugging, tool-use |
| `writer` | A creative writer that produces engaging content. | writing, editing, summarization |
| `researcher` | A research assistant that finds and synthesizes information. | search, summarization, reasoning |

With `auto_tools=True`, `analyst` gets `SQLQueryTool` and `DataVisualizationTool`, `coder` gets `CodeInterpreterTool`, `GitHubTool` and `FileSystemTool`, and `researcher` gets `WebSearchTool` and `PDFReaderTool`, provided those tools are registered.

### Agent.from_config

```python
from agenticaiframework import Agent

agent = Agent.from_config({
    "name": "analyst",
    "role": "analyst",                                  # template or description
    "capabilities": ["analysis", "summarization"],      # optional; template default otherwise
    "llm": {"provider": "openai", "model": "gpt-4o-mini"},   # or just "gpt-4o-mini"
    "tools": ["FileReadTool", "CSVRAGSearchTool"],
    "guardrails": {"preset": "enterprise"},             # True | False | {"preset": minimal|safety|enterprise}
    "max_context_tokens": 8192,
    "tracing": True,
    "auto_start": True,
})
print(agent.capabilities)
```

Recognised keys: `name`, `role`, `capabilities`, `llm`, `tools`, `guardrails`, `max_context_tokens`, `tracing`, `auto_start`, plus `monitor`, `knowledge` and `policy_manager`, which are copied into `agent.config`. When `llm` is a dict with `provider`, the provider is created with `agenticaiframework.llms.providers.get_provider(provider, model=, api_key=)` and registered on a fresh `LLMManager`; when it is a string, `LLMManager.from_environment()` is used and the active provider's default model is overridden.

### Raw constructor

```python
from agenticaiframework import Agent
from agenticaiframework.llms import LLMManager
from agenticaiframework.guardrails import GuardrailPipeline

llm = LLMManager.from_environment()

agent = Agent(
    name="reviewer",
    role="Reviews pull requests for correctness and style",
    capabilities=["code-review"],
    config={
        "llm": llm,                                   # required for invoke()
        "guardrail_pipeline": GuardrailPipeline.minimal(),
    },
    max_context_tokens=8192,
)
agent.start()
print(agent.id, agent.status)                         # uuid, running
```

`config` keys read by the runner: `llm` (or `llm_manager`), `knowledge`, `guardrail_manager`, `guardrail_pipeline`, `policy_manager`, `monitor`, `tracer`. Everything else is left for your own use.

### Lifecycle

`agent.status` moves through `initialized` -> `running` (after `start()`) -> `paused` / `running` (`pause()` / `resume()`) -> `stopped` (`stop()`). `Agent.quick` and `Agent.from_config` (with `auto_start=True`) call `start()` for you. `agent.to_dict()` returns id, name, role, capabilities, status, version, performance metrics and context statistics.

## Invoking Agents

### invoke()

```python
output = agent.invoke(
    "Summarise the attached figures.",
    system_prompt="Be terse.",                 # replaces the generated system prompt
    context={"revenue": 1_250_000},            # appended to the user prompt as JSON
    tools=["FileReadTool"],                    # bind and expose these tools for this call
    tool_inputs={"FileReadTool": {"path": "q3.csv"}},
    knowledge_query="quarterly revenue",       # overrides the retrieval query
    max_iterations=5,                          # ReAct loop bound (default 10)
    temperature=0.3,
    stop_on_tool_error=False,                  # True turns a failed tool into an ERROR output
)
```

`invoke()` builds an `AgentInput`, creates an `AgentRunner` from the agent's config and calls `runner.run()`. `ainvoke()` is the `async` wrapper; `agent.last_output` keeps the most recent `AgentOutput`.

### stream()

```python
for step in agent.stream("Find the largest file in ./data", tools=["FileReadTool"]):
    print(f"{step.step_type.value:12} {step.name:24} {step.duration_ms:.1f} ms")
print(agent.last_output.status)
```

`stream()` yields `AgentStep` objects as the runner produces them and accepts `on_step` and `on_thought` callbacks. `astream()` is the async variant.

### AgentOutput

| Field | Type | Meaning |
|---|---|---|
| `status` | `AgentStatus` | `SUCCESS`, `ERROR`, `BLOCKED` (guardrail), `CANCELLED`, `PENDING`, `RUNNING` |
| `response` | `str \| None` | Final answer text |
| `steps` | `List[AgentStep]` | Every step in order (see `StepType`) |
| `thoughts` | `List[AgentThought]` | ReAct thoughts with `thought`, `action`, `action_input`, `observation` |
| `tool_results` | `List[dict]` | One dict per tool call: `tool_name`, `input`, `output`/`error`, `success` |
| `knowledge_results` | `List[dict]` | Documents returned by the knowledge retriever |
| `guardrail_report` | `dict \| None` | Report from the input (or blocking) guardrail run |
| `error` | `str \| None` | Error message when `status` is not `SUCCESS` |
| `trace_id` | `str \| None` | Id of the trace created by the tracer |
| `latency_seconds` | `float` | Wall-clock duration |
| `token_usage` | `dict` | `prompt_tokens`, `completion_tokens`, `total_tokens` |
| `metadata` | `dict` | `iterations`, `native_tools` |

`is_success`, `is_error` and `is_blocked` are convenience properties; `to_dict()` serialises the whole object.

`StepType` values: `INPUT`, `THOUGHT`, `OBSERVATION`, `TOOL_CALL`, `TOOL_RESULT`, `KNOWLEDGE`, `GUARDRAIL`, `LLM_CALL`, `OUTPUT`, `ERROR`. Each `AgentStep` has `step_type`, `name`, `content`, `timestamp`, `duration_ms` and `metadata`.

## AgentRunner

`AgentRunner` (in `agenticaiframework/core/runner.py`) is the execution loop. `invoke()` and `stream()` construct one for you; you can also drive it directly.

```python
from agenticaiframework import Agent
from agenticaiframework.core import AgentRunner, AgentInput

agent = Agent.quick("Planner", role="assistant")
runner = AgentRunner(agent, on_thought=lambda t: print("thought:", t.thought))
output = runner.run(AgentInput(prompt="Plan a three-step migration.", max_iterations=4))
print(output.status)
```

Constructor parameters (all optional, default to the matching `agent.config` entry): `llm_manager`, `knowledge`, `guardrail_manager`, `guardrail_pipeline`, `policy_manager`, `monitor`, `tracer`, `use_native_tools`, `on_thought`.

The loop, in order:

1. Record an `INPUT` step and start a trace span named `agent.run:<name>`.
2. Run input guardrails. If the report is invalid the run stops with `AgentStatus.BLOCKED`.
3. If a knowledge retriever is configured, call `retrieve(knowledge_query or prompt)` and record a `KNOWLEDGE` step; the top results are added to the agent's context window.
4. Bind any tools named in the input and collect their schemas. If no LLM manager is configured the run ends with `ERROR`.
5. Choose the loop. When tools are bound and `llm_manager.supports_native_tools()` is true, the runner uses the provider's structured tool calling (`generate_with_tools`); otherwise it uses the text ReAct protocol (`Thought:` / `Action:` / `Action Input:` / `Observation:` / `Final Answer:`). `use_native_tools` forces either path.
6. For each iteration up to `max_iterations`: call the LLM (`LLM_CALL` step), parse thoughts and actions, check the policy manager (`evaluate_policies`) if one is set, execute the tool (`TOOL_CALL` and `TOOL_RESULT` steps) and feed the observation back. Unknown tools produce an observation listing the available tools; a tool called more than twice with identical input is suppressed to break loops. Observations are truncated to 4000 characters.
7. Run output guardrails on the final answer (`BLOCKED` if they fail), record an `OUTPUT` step, add the exchange to the context window, and emit `agent.execution_seconds` / `agent.run_complete` to the monitor if one is set.

`AgentRunner.parse_action(text)` is a static helper that extracts `(tool_name, arguments)` from `Action: name[...]`, `Action:` + `Action Input:` or a fenced JSON tool call.

## Tools, knowledge and guardrails on an agent

```python
import agenticaiframework as aaf
aaf.configure()                                          # discovers the 46 built-in tools

agent.bind_tools(["FileReadTool", "JSONRAGSearchTool"])
print([s["name"] for s in agent.get_tool_schemas()])     # MCP-style schemas
result = agent.execute_tool("FileReadTool", path="README.md")   # ToolResult

agent.add_context("The user prefers metric units.", importance=0.8)
print(agent.get_context_stats()["current_tokens"])

report = agent.apply_guardrails("My SSN is 123-45-6789", direction="input", fail_fast=False)
print(report["is_valid"])
```

Tool names refer to classes in the global `tool_registry`; names that are not registered are skipped with a warning, so call `aaf.configure()` (which discovers tools by default) or `tool_registry.discover()` before binding.

Fluent helpers return the agent so they can be chained: `with_guardrails(pipeline=None, preset="minimal")`, `with_knowledge(knowledge)`, `with_policy(policy_engine)`, `with_supervisor(supervisor)`, `with_logging(level, output, file_path)`, `with_formatter(format_type)`, `with_conversation(...)`, `with_human_oversight(...)`, `with_speech(...)`. Knowledge shortcuts: `add_knowledge(key, content)`, `create_knowledge_from(sources, embedding_provider=...)`, `add_knowledge_from_api(url)`, `add_knowledge_from_web_search(query)`, `add_knowledge_from_image(path)`, `query_knowledge(query)`. See [Tools](tools.md), [Knowledge](knowledge.md) and [Guardrails](guardrails.md).

## Agent-to-agent calls

```python
from agenticaiframework import Agent

researcher = Agent.quick("Researcher", role="researcher")
writer = Agent.quick("Writer", role="writer")

draft = writer.call_agent(researcher, "List three facts about lithium recycling.")
writer.handoff_to(researcher, context={"reason": "needs sources"}, reason="verification")
```

`call_agent(agent, prompt, wait=True, **kwargs)` calls `agent.run(prompt)` on the other agent and returns its result dictionary (`response`, `status`, `tool_results`, `trace_id`, ...). `handoff_to(agent, context, reason)` records a handoff and passes the context window on. `send_to_agent`, `broadcast_to_agents`, `stream_from_agent` and `connect_remote(agent_id, url=..., protocol="http")` use the channel layer described in [Communication](communication.md). `delegate_to_team(team, task)` and `call_orchestration(agents, task, pattern=...)` hand work to the [Orchestration](orchestration.md) layer.

## AgentManager

```python
from agenticaiframework import Agent, AgentManager

manager = AgentManager()
for name, role in [("Researcher", "researcher"), ("Writer", "writer")]:
    manager.register_agent(Agent.quick(name, role=role))

writer = manager.get_agent_by_name("Writer")
print(writer.id == manager.get_agent(writer.id).id)             # True
print([a.name for a in manager.get_agents_by_capability("summarization")])
print(len(manager.get_active_agents()), len(manager.list_agents()))

manager.broadcast("Deploy freeze starts at 17:00", importance=0.9)  # adds context to every agent
print(manager.health_check())            # {agent_id: {name, status, success_rate, total_tasks, error_count, context_utilization}}
print(manager.get_aggregate_metrics())   # totals across agents plus registration/broadcast counters
manager.stop_all_agents()
manager.remove_agent(writer.id)
```

| Method | Returns |
|---|---|
| `register_agent(agent)` / `remove_agent(agent_id)` | `None` |
| `get_agent(agent_id)` / `get_agent_by_name(name)` | `Agent \| None` |
| `get_agents_by_capability(capability)` | `List[Agent]` |
| `list_agents()` / `get_active_agents()` | `List[Agent]` (active means `status == "running"`) |
| `broadcast(message, importance=0.5)` | adds the message to every agent's context |
| `health_check()` | per-agent dict of status, success rate, task and error counts, context utilisation |
| `get_aggregate_metrics()` | totals: agents, tasks, successes, failures, errors, success rate, registrations, removals, broadcasts |
| `stop_all_agents()` | calls `stop()` on every agent |

## Conversations

`agenticaiframework.conversations` tracks multi-turn history independently of the runner. `agent.with_conversation()` attaches a `ConversationManager` to `agent.config["conversation"]`; `agent.chat(message)` then appends the user turn, calls the LLM with the formatted history and stores the reply.

```python
from agenticaiframework.conversations import ConversationManager, ConversationConfig, MessageRole

conv = ConversationManager(
    agent_id="support",
    config=ConversationConfig(max_history=50, max_tokens=32_000, track_tokens=True),
)
conv.set_system_message("You are a billing assistant.")
conv.add_user_message("Why was I charged twice?")
conv.add_assistant_message("I see two authorisations; one will drop off within 3 days.")
conv.add_tool_message("lookup_invoice", '{"invoice": "A-1"}', tool_call_id="call_1")

print(conv.get_messages_for_llm(format="openai")[0])   # {'role': 'system', 'content': ...}
print(conv.search("charged", role=MessageRole.USER)[0].content)
print(conv.export_markdown()[:60])
conv.save("/tmp/support_session.json")
```

`ConversationManager` methods: `set_system_message`, `add_user_message(content, attachments=, metadata=)`, `add_assistant_message`, `add_tool_message(tool_name, content, tool_call_id=, is_result=)`, `add_thinking_message`, `get_messages()`, `get_history(limit=)`, `get_messages_for_llm(format="openai"|"anthropic", max_tokens=)`, `search(query, role=, limit=)`, `summarize(summarizer=)`, `clear(keep_system=True)`, `export_json/markdown/html()`, `save(path)`, `load(path)`, `on_message_added(cb)`, `on_turn_complete(cb)`, `set_token_counter(fn)`.

`SessionManager(agent_id, persist_dir=)` holds several sessions: `create_session(title=)`, `switch_session(id)`, `get_conversation(id)`, `list_sessions(active_only=)`, `archive_session(id)`, `delete_session(id)`.

Loggers in the same package: `AgentLogger(agent_id, session_id=, config=LogConfig(...))` with `debug/info/warning/error/critical`, `event(type, message, data)`, `llm_call(model, tokens_in, tokens_out, duration_ms)`, `tool_call(tool_name, success, duration_ms)`, `timed(operation)` context manager and `get_entries(level=, event_type=, limit=)`; `StructuredLogger` adds `start_span`/`end_span`, `record_metric` and `get_metrics_summary`; `ConversationLogger(agent_id, session_id)` adds `log_session_start`, `log_turn(user_input, assistant_output, tokens_used=, duration_ms=, tool_calls=)`, `log_feedback` and `log_session_end`. On an agent, `with_logging(level="info", output="console"|"file", file_path=)` installs an `AgentLogger` and `log_event(event_type, message, data)` writes to it.

## Output formatting

`agenticaiframework.formatting` converts agent output to Markdown, JSON, HTML, code blocks, tables or plain text.

```python
from agenticaiframework.formatting import (
    OutputFormatter, FormatType, TableFormat, MarkdownFormatter, JSONFormatter, CodeFormatter,
)

formatter = OutputFormatter()
rows = [{"model": "gpt-4o-mini", "tokens": 812}, {"model": "claude-3.5-haiku", "tokens": 640}]

print(formatter.format_table(rows, format=TableFormat.MARKDOWN).formatted)
print(formatter.format_json({"ok": True}, indent=2).formatted)
print(formatter.format_code("print('hi')", language="python", line_numbers=True).formatted)
print(formatter.format("Plain **text**", format_type=FormatType.MARKDOWN).format_type)

md = MarkdownFormatter()
print(md.heading("Report", level=2), md.checklist([("tests", True), ("docs", False)]))
print(JSONFormatter().validate('{"a": 1}'))            # (True, None)
print(CodeFormatter().detect_language("def f(): pass"))  # python
```

`OutputFormatter.format(...)` and the `format_*` helpers return a `FormattedOutput(content, formatted, format_type, metadata, timestamp)`. `register_formatter(name, formatter)` adds a custom `BaseFormatter` or callable. `HTMLFormatter` provides `heading`, `paragraph`, `link`, `image`, `list_items`, `table`, `code`, `card` and `escape`; `PlainTextFormatter` provides `strip_formatting` and `wrap_text`; `TableFormatter.format(data, format=...)` renders `TableFormat.MARKDOWN | ASCII | CSV | TSV | HTML | LATEX`.

On an agent: `with_formatter("markdown")` sets a default, and `format_response(content, format_type=)`, `format_as_markdown`, `format_as_json(data, indent=)`, `format_as_code(code, language=)` and `format_as_table(data)` return strings.

## Human-in-the-Loop

`agenticaiframework.hitl` gates selected actions behind an approval handler, escalates on conditions you define, and collects feedback on responses.

```python
from datetime import datetime
from agenticaiframework.hitl import (
    HumanInTheLoop, CallbackApprovalHandler, ApprovalDecision, ApprovalStatus, EscalationLevel,
)

def approve_small_refunds(request):
    status = ApprovalStatus.APPROVED if request.details["amount"] < 200 else ApprovalStatus.REJECTED
    return ApprovalDecision(
        request_id=request.id, status=status, decided_by="policy",
        decided_at=datetime.now().isoformat(),
    )

hitl = HumanInTheLoop(
    agent_id="payments_agent",
    approval_required_for=["refund", "delete_account"],
    approval_handler=CallbackApprovalHandler(approve_small_refunds),
    auto_approve_after=None,                      # seconds; None waits for the handler
    notification_handler=lambda kind, payload: print("notify", kind),
)

print(hitl.requires_approval("refund"))           # True
decision = hitl.request_approval(action="refund", details={"amount": 120.0, "order": "A-1"})
print(decision.status)                            # ApprovalStatus.APPROVED

hitl.add_escalation_trigger(
    "high_value", condition=lambda ctx: ctx.get("amount", 0) > 10_000,
    level=EscalationLevel.HIGH, message="Manual review for large transactions",
)
trigger = hitl.check_escalation({"amount": 25_000})
print(trigger.name if trigger else None)          # high_value

intervention = hitl.request_intervention("Customer asked for a human", level=EscalationLevel.MEDIUM)
hitl.resolve_intervention(intervention.id, "Handed to support")
print(hitl.get_history()["approvals"][-1]["status"])
```

Approval handlers:

| Handler | Behaviour |
|---|---|
| `ConsoleApprovalHandler(timeout=300)` | Prints `request.to_display()` and reads y/n from stdin |
| `CallbackApprovalHandler(callback=, async_callback=)` | Calls your function with the `ApprovalRequest` and expects an `ApprovalDecision` |
| `QueueApprovalHandler(timeout=3600)` | Parks requests; `get_pending()` lists them and `resolve(request_id, status, decided_by=, reason=)` answers one from another thread or process |

`ApprovalRequest` fields: `id`, `action`, `details`, `agent_id`, `session_id`, `reason`, `created_at`, `expires_at`, `priority`, `context`, `status`. `ApprovalDecision` fields: `request_id`, `status`, `decided_by`, `decided_at`, `reason`, `modifications`. `ApprovalStatus`: `PENDING`, `APPROVED`, `REJECTED`, `TIMEOUT`, `ESCALATED`, `AUTO_APPROVED`. `EscalationLevel`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`. `request_approval_async` awaits the handler's `request_approval_async`. Callbacks: `on_approval_requested(cb)`, `on_decision_made(cb)`, `on_intervention(cb)`. `pause_agent(reason)` opens a `CRITICAL` intervention.

Feedback:

```python
from agenticaiframework.hitl import FeedbackCollector

feedback = FeedbackCollector()
feedback.collect_thumbs("resp-1", is_positive=True, user_id="u1")
feedback.collect_rating("resp-1", rating=4)
feedback.collect_correction("resp-1", original="5 days", corrected="3 business days")
print(feedback.get_summary("resp-1"))
```

On an agent, `with_human_oversight(approval_required_for=[...], auto_approve_after=None, handler="console"|"queue")` installs a `HumanInTheLoop`; `requires_approval(action)`, `request_approval(action, details, reason=, timeout=)` (returns `bool`), `request_human_help(reason, context=)`, `pause_for_review(reason)`, `collect_feedback(response_id, feedback_type="thumbs", value=)` and `get_feedback_summary(response_id)` forward to it.

## Error handling

- `invoke()` never raises for LLM, tool or guardrail failures; check `output.is_error` / `output.is_blocked` and `output.error`. Exceptions inside the runner are logged, recorded as an `ERROR` step and returned as `AgentStatus.ERROR`.
- `execute_task(callable, *args)` runs an arbitrary callable, updates `performance_metrics`, appends failures to `agent.get_error_log()` and returns `None` on error.
- Tool failures become observations the model sees; set `stop_on_tool_error=True` to abort instead.
- Guardrail blocks return `AgentStatus.BLOCKED` with the report in `guardrail_report`.

## API summary

| Symbol | Signature / key methods | Notes |
|---|---|---|
| `Agent` | `Agent(name, role, capabilities, config, max_context_tokens=4096)`; `quick(...)`, `from_config(dict)`; `invoke`, `ainvoke`, `stream`, `astream`, `run`, `chat`; `start/pause/resume/stop`; `bind_tools`, `execute_tool`, `get_tool_schemas`; `add_context`, `get_context_stats`; `apply_guardrails`, `check_policy`; `call_agent`, `handoff_to`, `send_to_agent`, `broadcast_to_agents`, `connect_remote`; `get_performance_metrics`, `get_error_log`, `to_dict` | `ROLE_TEMPLATES`, `ROLE_CAPABILITIES` class attributes |
| `AgentInput` | `AgentInput(prompt, system_prompt=, tools=, tool_inputs=, knowledge_query=, context=, max_iterations=10, stop_sequences=, temperature=0.7, stream=False, stop_on_tool_error=False)` | Dataclass consumed by `AgentRunner` |
| `AgentOutput` | fields listed above; `is_success`, `is_error`, `is_blocked`, `to_dict()` | Returned by `invoke`, `run`, `last_output` |
| `AgentStep` | `AgentStep(step_type, name, content, timestamp=, duration_ms=0.0, metadata=)` | Yielded by `stream()` |
| `AgentThought` | `AgentThought(thought, action=, action_input=, observation=)` | ReAct trace |
| `AgentStatus`, `StepType` | enums | see tables above |
| `AgentRunner` | `AgentRunner(agent, llm_manager=, knowledge=, guardrail_manager=, guardrail_pipeline=, policy_manager=, monitor=, tracer=, use_native_tools=, on_thought=)`; `run(AgentInput)`, `iter_run(AgentInput)`, `parse_action(text)` | `runner.output` holds the final result after `iter_run` |
| `AgentManager` | `register_agent`, `remove_agent`, `get_agent`, `get_agent_by_name`, `get_agents_by_capability`, `list_agents`, `get_active_agents`, `broadcast`, `health_check`, `get_aggregate_metrics`, `stop_all_agents` | In-memory registry |
| `ConversationManager` | `ConversationManager(agent_id="agent", session_id=, config=ConversationConfig(...))` | `agenticaiframework.conversations` |
| `SessionManager` | `SessionManager(agent_id, persist_dir=)` | multiple sessions per agent |
| `AgentLogger`, `StructuredLogger`, `ConversationLogger` | `(agent_id, session_id=, config=LogConfig(...))` | `agenticaiframework.conversations` |
| `OutputFormatter` | `format`, `format_markdown`, `format_json`, `format_code`, `format_html`, `format_table`, `format_plain`, `register_formatter` | `agenticaiframework.formatting` |
| `HumanInTheLoop` | `HumanInTheLoop(agent_id="agent", session_id=, approval_required_for=, approval_handler=, auto_approve_after=, notification_handler=)` | `agenticaiframework.hitl` |
| `FeedbackCollector` | `collect_thumbs`, `collect_rating`, `collect_text`, `collect_correction`, `collect_flag`, `get_feedback`, `get_summary`, `export` | `agenticaiframework.hitl` |

## Related

- [Tasks](tasks.md) and [Processes](processes.md): wrap callables and run them sequentially or in parallel
- [Orchestration](orchestration.md): teams, supervisors and the ten coordination patterns
- [Tools](tools.md): `BaseTool`, `ToolRegistry`, MCP server and client
- [LLM Providers](llms.md): `LLMManager`, model registry, routing
- [Memory](memory.md) and [Context](context.md): what the agent remembers between and within calls
- [Guardrails](guardrails.md) and [Tracing](tracing.md)
