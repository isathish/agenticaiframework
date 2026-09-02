"""
ReAct-Style Agentic Runner.

Provides the core agentic execution loop:

* Thought / Action / Observation cycle (ReAct) for any text LLM
* Native structured tool calling when the LLM provider supports it
  (OpenAI / Anthropic / Gemini function calling)
* Multi-step tool execution with policy checks and loop detection
* Incremental step streaming via :meth:`AgentRunner.iter_run`
* Guardrails on input and output, knowledge retrieval, tracing, monitoring
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, TYPE_CHECKING

from .types import (
    AgentInput,
    AgentOutput,
    AgentStep,
    AgentThought,
    AgentStatus,
    StepType,
)

if TYPE_CHECKING:
    from .agent import Agent

logger = logging.getLogger(__name__)


class _Halt(Exception):
    """Internal: stop the loop and return ``output``."""

    def __init__(self, output: AgentOutput):
        self.output = output


class AgentRunner:
    """
    ReAct-style agentic runner.

    ``run()`` returns a complete :class:`AgentOutput`; ``iter_run()`` yields
    :class:`AgentStep` objects as they happen and exposes the final output on
    ``runner.output`` when iteration finishes.
    """

    THOUGHT_PATTERN = re.compile(r"Thought:\s*(.+?)(?=\n\s*(?:Action|Observation|Final Answer)\s*:|$)", re.DOTALL | re.IGNORECASE)
    ACTION_HEAD_PATTERN = re.compile(r"Action:\s*([A-Za-z_][\w.\-]*)\s*", re.IGNORECASE)
    ACTION_INPUT_PATTERN = re.compile(r"Action\s*Input:\s*(.+?)(?=\n\s*(?:Observation|Thought|Final Answer)\s*:|$)", re.DOTALL | re.IGNORECASE)
    FINAL_ANSWER_PATTERN = re.compile(r"Final Answer:\s*(.+)", re.DOTALL | re.IGNORECASE)
    JSON_TOOL_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)

    MAX_OBSERVATION_CHARS = 4000
    MAX_REPEATED_ACTIONS = 2

    def __init__(
        self,
        agent: 'Agent',
        llm_manager: Optional[Any] = None,
        knowledge: Optional[Any] = None,
        guardrail_manager: Optional[Any] = None,
        guardrail_pipeline: Optional[Any] = None,
        policy_manager: Optional[Any] = None,
        monitor: Optional[Any] = None,
        tracer: Optional[Any] = None,
        use_native_tools: Optional[bool] = None,
        on_thought: Optional[Callable[[AgentThought], None]] = None,
    ):
        self.agent = agent
        self.llm_manager = llm_manager or agent.config.get('llm') or agent.config.get('llm_manager')
        self.knowledge = knowledge or agent.config.get('knowledge')
        self.guardrail_manager = guardrail_manager or agent.config.get('guardrail_manager')
        self.guardrail_pipeline = guardrail_pipeline or agent.config.get('guardrail_pipeline')
        self.policy_manager = policy_manager or agent.config.get('policy_manager')
        self.monitor = monitor or agent.config.get('monitor')
        self.tracer = tracer or agent.config.get('tracer')
        self.use_native_tools = use_native_tools
        self.on_thought = on_thought
        self.output: Optional[AgentOutput] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, input_data: AgentInput) -> AgentOutput:
        """Run to completion and return the structured output."""
        for _ in self.iter_run(input_data):
            pass
        assert self.output is not None
        return self.output

    def iter_run(self, input_data: AgentInput) -> Iterator[AgentStep]:
        """Execute the agent, yielding each :class:`AgentStep` as it is produced."""
        from ..tracing import tracer as global_tracer
        from ..guardrails import guardrail_manager as global_guardrail_manager
        from ..tools import agent_tool_manager
        from ..context import ContextType

        tracer = self.tracer or global_tracer
        guardrail_mgr = self.guardrail_manager or global_guardrail_manager

        start_time = time.time()
        steps: List[AgentStep] = []
        thoughts: List[AgentThought] = []
        tool_results: List[Dict[str, Any]] = []
        knowledge_results: List[Any] = []
        token_usage: Dict[str, int] = {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
        self.output = None

        trace_context = tracer.start_trace(f"agent.run:{self.agent.name}") if tracer else None
        trace_id = getattr(trace_context, 'trace_id', None)

        def record(step: AgentStep) -> AgentStep:
            steps.append(step)
            return step

        def think(thought: AgentThought) -> None:
            thoughts.append(thought)
            if self.on_thought:
                try:
                    self.on_thought(thought)
                except Exception:  # noqa: BLE001 - observer errors must not break the run
                    logger.exception("on_thought callback failed")

        def finalize(output: AgentOutput) -> AgentOutput:
            output.latency_seconds = time.time() - start_time
            output.trace_id = trace_id
            output.steps = steps
            output.thoughts = thoughts
            output.token_usage = token_usage
            if not output.tool_results:
                output.tool_results = tool_results
            if not output.knowledge_results:
                output.knowledge_results = knowledge_results
            if trace_context:
                tracer.end_span(trace_context, status="OK" if output.is_success else "ERROR")
            self.output = output
            return output

        yield record(AgentStep(
            step_type=StepType.INPUT,
            name="user_input",
            content=input_data.prompt,
            metadata={'system_prompt': input_data.system_prompt, 'context': input_data.context},
        ))

        try:
            # -- input guardrails -------------------------------------------
            step_start = time.time()
            guardrail_report = self._run_guardrails(guardrail_mgr, input_data.prompt, input_data.context)
            yield record(AgentStep(
                step_type=StepType.GUARDRAIL, name="input_guardrails", content=guardrail_report,
                duration_ms=(time.time() - step_start) * 1000,
            ))
            if not guardrail_report.get('is_valid', True):
                raise _Halt(AgentOutput(
                    status=AgentStatus.BLOCKED, guardrail_report=guardrail_report,
                    error="Input blocked by guardrails",
                ))

            # -- knowledge retrieval ----------------------------------------
            if self.knowledge is not None:
                step_start = time.time()
                query = input_data.knowledge_query or input_data.prompt
                try:
                    knowledge_results = list(self.knowledge.retrieve(query) or [])
                except Exception as e:  # noqa: BLE001 - knowledge failures are non-fatal
                    logger.warning("Knowledge retrieval failed: %s", e)
                    knowledge_results = []
                yield record(AgentStep(
                    step_type=StepType.KNOWLEDGE, name="knowledge_retrieval",
                    content=knowledge_results[:5],
                    duration_ms=(time.time() - step_start) * 1000, metadata={'query': query},
                ))
                if knowledge_results:
                    self.agent.context_manager.add_context(
                        f"Retrieved knowledge: {str(knowledge_results[:3])[:500]}",
                        importance=0.7, context_type=ContextType.KNOWLEDGE,
                    )

            # -- tools --------------------------------------------------------
            if input_data.tools:
                agent_tool_manager.bind_tools(self.agent, input_data.tools)
            tool_schemas = agent_tool_manager.get_all_schemas(self.agent) if input_data.tools else []
            tool_names = {s['name'] for s in tool_schemas} | set(input_data.tools or [])

            if self.llm_manager is None:
                raise _Halt(AgentOutput(status=AgentStatus.ERROR, error="No LLM manager configured"))

            native = self.use_native_tools
            if native is None:
                native = bool(tool_schemas) and bool(getattr(self.llm_manager, 'supports_native_tools', lambda: False)())

            system_prompt = self._build_system_prompt(input_data, tool_schemas, react_protocol=not native)
            user_prompt = self._build_user_prompt(input_data, knowledge_results)

            # -- agentic loop -------------------------------------------------
            if native:
                loop = self._native_loop(
                    input_data, system_prompt, user_prompt, tool_schemas, tool_names,
                    tool_results, token_usage, record, think, agent_tool_manager, ContextType,
                )
            else:
                loop = self._react_loop(
                    input_data, system_prompt, user_prompt, tool_names,
                    tool_results, token_usage, record, think, agent_tool_manager, ContextType,
                )
            final_response: Optional[str] = None
            iterations = 0
            try:
                while True:
                    step = next(loop)
                    yield step
            except StopIteration as stop:
                final_response, iterations = stop.value

            if final_response is None:
                final_response = "Max iterations reached without a final answer."

            # -- output guardrails ---------------------------------------------
            step_start = time.time()
            output_report = self._run_guardrails(guardrail_mgr, final_response, input_data.context)
            yield record(AgentStep(
                step_type=StepType.GUARDRAIL, name="output_guardrails", content=output_report,
                duration_ms=(time.time() - step_start) * 1000,
            ))
            if not output_report.get('is_valid', True):
                raise _Halt(AgentOutput(
                    status=AgentStatus.BLOCKED, guardrail_report=output_report,
                    error="Output blocked by guardrails",
                ))

            yield record(AgentStep(step_type=StepType.OUTPUT, name="final_output", content=final_response,
                                   metadata={'iterations': iterations}))

            self.agent.context_manager.add_context(input_data.prompt, importance=0.5, context_type=ContextType.USER)
            self.agent.context_manager.add_context(final_response, importance=0.6, context_type=ContextType.ASSISTANT)

            if self.monitor is not None:
                self.monitor.record_metric('agent.execution_seconds', time.time() - start_time)
                self.monitor.log_event('agent.run_complete', {
                    'agent_id': self.agent.id,
                    'iterations': iterations,
                    'tools_used': [t.get('tool_name') for t in tool_results],
                    'native_tools': native,
                })

            finalize(AgentOutput(
                status=AgentStatus.SUCCESS, response=final_response, tool_results=tool_results,
                knowledge_results=knowledge_results, guardrail_report=guardrail_report,
                metadata={'iterations': iterations, 'native_tools': native},
            ))

        except _Halt as halt:
            finalize(halt.output)
        except Exception as e:  # noqa: BLE001 - every failure must surface as an ERROR output
            logger.exception("AgentRunner error")
            yield record(AgentStep(step_type=StepType.ERROR, name="error", content=str(e)))
            finalize(AgentOutput(status=AgentStatus.ERROR, error=str(e)))

    # ------------------------------------------------------------------
    # Loop implementations (generators returning (final_response, iterations))
    # ------------------------------------------------------------------

    def _react_loop(self, input_data, system_prompt, user_prompt, tool_names, tool_results,
                    token_usage, record, think, tool_manager, ContextType):
        transcript = f"{system_prompt}\n\nUser: {user_prompt}"
        seen_actions: Dict[str, int] = {}
        iteration = 0
        while iteration < input_data.max_iterations:
            iteration += 1
            step_start = time.time()
            llm_kwargs: Dict[str, Any] = {'temperature': input_data.temperature}
            if input_data.stop_sequences:
                llm_kwargs['stop'] = input_data.stop_sequences
            elif tool_names:
                llm_kwargs['stop'] = ["\nObservation:"]
            llm_response = self._generate_text(transcript, llm_kwargs, token_usage)
            if llm_response is None:
                raise _Halt(AgentOutput(status=AgentStatus.ERROR, error="LLM generation failed"))
            yield record(AgentStep(
                step_type=StepType.LLM_CALL, name=f"llm_call_{iteration}", content=llm_response,
                duration_ms=(time.time() - step_start) * 1000, metadata={'iteration': iteration},
            ))

            final_match = self.FINAL_ANSWER_PATTERN.search(llm_response)
            thought_match = self.THOUGHT_PATTERN.search(llm_response)
            thought_text = thought_match.group(1).strip() if thought_match else ""
            action = self.parse_action(llm_response)

            if final_match and (action is None or final_match.start() < llm_response.find("Action")):
                final = final_match.group(1).strip()
                think(AgentThought(thought=thought_text or "Providing final answer", observation=final))
                return final, iteration

            if action is None:
                final = final_match.group(1).strip() if final_match else llm_response.strip()
                think(AgentThought(thought=thought_text or "Generating response", observation=final[:500]))
                return final, iteration

            action_name, action_input = action
            if thought_text:
                yield record(AgentStep(step_type=StepType.THOUGHT, name=f"thought_{iteration}", content=thought_text))

            if action_name not in tool_names and tool_names:
                observation = (f"Unknown tool '{action_name}'. Available tools: {', '.join(sorted(tool_names))}. "
                               f"Use one of them or give a Final Answer.")
            else:
                key = f"{action_name}:{json.dumps(action_input, sort_keys=True, default=str)}"
                seen_actions[key] = seen_actions.get(key, 0) + 1
                if seen_actions[key] > self.MAX_REPEATED_ACTIONS:
                    observation = ("You have already called this tool with the same input. "
                                   "Do not repeat it; use the earlier observation to give a Final Answer.")
                else:
                    observation, halted = yield from self._execute_action(
                        input_data, action_name, action_input, tool_results, record, tool_manager, ContextType)
                    if halted is not None:
                        raise _Halt(halted)

            think(AgentThought(thought=thought_text, action=action_name, action_input=action_input,
                               observation=observation[:500]))
            yield record(AgentStep(step_type=StepType.OBSERVATION, name=f"observation_{iteration}",
                                   content=observation[:self.MAX_OBSERVATION_CHARS]))
            transcript += f"\n{llm_response.strip()}\nObservation: {observation[:self.MAX_OBSERVATION_CHARS]}\n"
        return None, iteration

    def _native_loop(self, input_data, system_prompt, user_prompt, tool_schemas, tool_names,
                     tool_results, token_usage, record, think, tool_manager, ContextType):
        from ..llms.providers.base import LLMMessage

        messages: List[LLMMessage] = [
            LLMMessage(role='system', content=system_prompt),
            LLMMessage(role='user', content=user_prompt),
        ]
        openai_tools = [{
            'type': 'function',
            'function': {
                'name': s['name'],
                'description': s.get('description', ''),
                'parameters': s.get('parameters') or {'type': 'object', 'properties': {}},
            },
        } for s in tool_schemas]
        seen_actions: Dict[str, int] = {}
        iteration = 0
        while iteration < input_data.max_iterations:
            iteration += 1
            step_start = time.time()
            response = self.llm_manager.generate_with_tools(
                messages, openai_tools, temperature=input_data.temperature,
            )
            if response is None:
                raise _Halt(AgentOutput(status=AgentStatus.ERROR, error="LLM generation failed"))
            self._accumulate_usage(token_usage, getattr(response, 'usage', None))
            content = response.content or ""
            yield record(AgentStep(
                step_type=StepType.LLM_CALL, name=f"llm_call_{iteration}",
                content=content if not response.tool_calls else {'content': content, 'tool_calls': response.tool_calls},
                duration_ms=(time.time() - step_start) * 1000,
                metadata={'iteration': iteration, 'finish_reason': response.finish_reason, 'model': response.model},
            ))

            if not response.tool_calls:
                final = content.strip()
                fm = self.FINAL_ANSWER_PATTERN.search(final)
                if fm:
                    final = fm.group(1).strip()
                think(AgentThought(thought="Providing final answer", observation=final[:500]))
                return final, iteration

            if content.strip():
                yield record(AgentStep(step_type=StepType.THOUGHT, name=f"thought_{iteration}", content=content.strip()))

            messages.append(LLMMessage(role='assistant', content=content, tool_calls=response.tool_calls))
            for call in response.tool_calls:
                fn = call.get('function', {}) if isinstance(call, dict) else {}
                action_name = fn.get('name') or call.get('name', '')
                raw_args = fn.get('arguments', call.get('arguments', {}))
                action_input = self._parse_tool_arguments(raw_args)
                call_id = call.get('id') or f"call_{iteration}_{action_name}"

                if action_name not in tool_names:
                    observation = f"Unknown tool '{action_name}'. Available tools: {', '.join(sorted(tool_names))}."
                else:
                    key = f"{action_name}:{json.dumps(action_input, sort_keys=True, default=str)}"
                    seen_actions[key] = seen_actions.get(key, 0) + 1
                    if seen_actions[key] > self.MAX_REPEATED_ACTIONS:
                        observation = "Duplicate call suppressed: this tool was already invoked with identical arguments."
                    else:
                        observation, halted = yield from self._execute_action(
                            input_data, action_name, action_input, tool_results, record, tool_manager, ContextType)
                        if halted is not None:
                            raise _Halt(halted)
                think(AgentThought(thought=content.strip(), action=action_name, action_input=action_input,
                                   observation=observation[:500]))
                yield record(AgentStep(step_type=StepType.OBSERVATION, name=f"observation_{action_name}",
                                       content=observation[:self.MAX_OBSERVATION_CHARS], metadata={'tool_call_id': call_id}))
                messages.append(LLMMessage(role='tool', name=action_name, tool_call_id=call_id,
                                           content=observation[:self.MAX_OBSERVATION_CHARS]))
        return None, iteration

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _execute_action(self, input_data, action_name, action_input, tool_results, record, tool_manager, ContextType):
        """Policy check + tool execution. Generator: yields steps, returns (observation, halt_output|None)."""
        if self.policy_manager is not None:
            policy_result = self.policy_manager.evaluate_policies(
                self.agent.id, action=action_name, resource=action_name, context={'agent_id': self.agent.id},
            )
            if not policy_result.get('allowed', True):
                observation = f"Tool {action_name} blocked by policy: {policy_result.get('reasons')}"
                yield record(AgentStep(step_type=StepType.TOOL_CALL, name=f"tool_{action_name}",
                                       content={'action': action_name, 'input': action_input, 'blocked': True},
                                       metadata={'policy': policy_result}))
                return observation, None

        merged_input = {**(input_data.tool_inputs or {}).get(action_name, {}), **action_input}
        step_start = time.time()
        yield record(AgentStep(step_type=StepType.TOOL_CALL, name=f"tool_{action_name}",
                               content={'action': action_name, 'input': merged_input}))
        try:
            tool_result = tool_manager.execute_tool(self.agent, action_name, **merged_input)
            result_dict = tool_result.to_dict()
            success = tool_result.is_success
            observation = self._format_observation(tool_result.data) if success else f"Error: {tool_result.error}"
        except Exception as e:  # noqa: BLE001 - tool crash becomes an observation
            success = False
            observation = f"Error: {type(e).__name__}: {e}"
            result_dict = {'tool_name': action_name, 'status': 'error', 'error': str(e)}
        tool_results.append(result_dict)
        yield record(AgentStep(step_type=StepType.TOOL_RESULT, name=f"tool_result_{action_name}",
                               content=observation[:self.MAX_OBSERVATION_CHARS],
                               duration_ms=(time.time() - step_start) * 1000, metadata={'success': success}))
        self.agent.context_manager.add_context(
            f"Tool {action_name} result: {observation[:300]}", importance=0.6, context_type=ContextType.TOOL_RESULT,
        )
        if not success and input_data.stop_on_tool_error:
            return observation, AgentOutput(status=AgentStatus.ERROR, error=observation, tool_results=list(tool_results))
        return observation, None

    def _generate_text(self, prompt: str, llm_kwargs: Dict[str, Any], token_usage: Dict[str, int]) -> Optional[str]:
        provider = getattr(self.llm_manager, 'get_active_provider', lambda: None)()
        if provider is not None and hasattr(self.llm_manager, 'generate_chat'):
            from ..llms.providers.base import LLMMessage
            response = self.llm_manager.generate_chat([LLMMessage(role='user', content=prompt)], **llm_kwargs)
            if response is None:
                return None
            self._accumulate_usage(token_usage, getattr(response, 'usage', None))
            return response.content
        result = self.llm_manager.generate(prompt, **llm_kwargs)
        if result is None:
            return None
        if hasattr(result, 'content'):
            self._accumulate_usage(token_usage, getattr(result, 'usage', None))
            return result.content
        return str(result)

    @staticmethod
    def _accumulate_usage(token_usage: Dict[str, int], usage: Optional[Dict[str, Any]]) -> None:
        for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
            try:
                token_usage[key] += int((usage or {}).get(key, 0) or 0)
            except (TypeError, ValueError):
                pass

    def _run_guardrails(self, guardrail_mgr, text: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if self.guardrail_pipeline is not None:
            return self.guardrail_pipeline.execute(text, context=context) or {}
        if guardrail_mgr is not None:
            return guardrail_mgr.enforce_guardrails(text, fail_fast=True) or {}
        return {}

    def _build_system_prompt(self, input_data: AgentInput, tool_schemas: List[Dict[str, Any]], *, react_protocol: bool) -> str:
        parts = [input_data.system_prompt or f"You are {self.agent.name}, an AI assistant with role: {self.agent.role}."]
        if tool_schemas and react_protocol:
            tool_lines = []
            for schema in tool_schemas:
                props = (schema.get('parameters') or {}).get('properties') or {}
                arg_desc = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in props.items()) or "no arguments"
                tool_lines.append(f"- {schema['name']}({arg_desc}): {schema.get('description') or 'No description'}")
            parts.append("Available tools:\n" + "\n".join(tool_lines))
            parts.append(
                "Use this exact format when you need a tool:\n"
                "Thought: <your reasoning>\n"
                "Action: <tool_name>\n"
                "Action Input: <arguments as a JSON object>\n"
                "Then wait for 'Observation:' with the result. Repeat as needed.\n"
                "When you know the answer, respond with:\n"
                "Thought: <reasoning>\n"
                "Final Answer: <your answer to the user>"
            )
        elif tool_schemas:
            parts.append("Use the provided tools when they help answer the request; otherwise answer directly.")
        return "\n\n".join(parts)

    def _build_user_prompt(self, input_data: AgentInput, knowledge_results: List[Any]) -> str:
        parts = []
        summary = self.agent.context_manager.get_context_summary()
        if summary and summary != "No context available.":
            parts.append(f"Context:\n{summary}")
        if input_data.context:
            parts.append("Additional context:\n" + json.dumps(input_data.context, default=str, indent=2)[:2000])
        if knowledge_results:
            parts.append("Knowledge:\n" + "\n".join(f"- {str(k)[:300]}" for k in knowledge_results[:5]))
        parts.append(input_data.prompt)
        return "\n\n".join(parts)

    @staticmethod
    def _format_observation(data: Any) -> str:
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(data)

    @staticmethod
    def _parse_tool_arguments(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if raw in (None, ""):
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {'input': parsed}
        except (TypeError, ValueError):
            return {'input': str(raw)}

    @classmethod
    def parse_action(cls, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Extract ``(tool_name, arguments)`` from an LLM response.

        Accepts ``Action: name[{...}]``, ``Action: name\\nAction Input: {...}``,
        ``Action: name({...})`` and fenced ``{"tool": ..., "args": ...}`` JSON.
        """
        m = cls.ACTION_HEAD_PATTERN.search(text)
        if m:
            name = m.group(1)
            rest = text[m.end():]
            if rest[:1] in ("[", "("):
                closer = "]" if rest[0] == "[" else ")"
                body = cls._balanced(rest, rest[0], closer)
                if body is not None:
                    return name, cls._coerce_input(body)
            im = cls.ACTION_INPUT_PATTERN.search(rest)
            if im:
                return name, cls._coerce_input(im.group(1).strip())
            return name, {}
        jm = cls.JSON_TOOL_PATTERN.search(text)
        if jm:
            try:
                obj = json.loads(jm.group(1))
            except ValueError:
                return None
            name = obj.get('tool') or obj.get('action') or obj.get('name')
            if name:
                args = obj.get('args') or obj.get('arguments') or obj.get('action_input') or obj.get('input') or {}
                return str(name), args if isinstance(args, dict) else {'input': args}
        return None

    @staticmethod
    def _balanced(text: str, opener: str, closer: str) -> Optional[str]:
        depth = 0
        in_str = False
        escape = False
        for i, ch in enumerate(text):
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return text[1:i]
        return None

    @staticmethod
    def _coerce_input(raw: str) -> Dict[str, Any]:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {'input': parsed}
        except ValueError:
            pass
        # key=value, key: value pairs
        pairs = re.findall(r"(\w+)\s*[=:]\s*(\"[^\"]*\"|'[^']*'|[^,\n]+)", raw)
        if pairs and all(p[0] for p in pairs) and len(",".join(f"{k}{v}" for k, v in pairs)) >= len(raw) * 0.6:
            out: Dict[str, Any] = {}
            for k, v in pairs:
                v = v.strip().strip("\"'")
                try:
                    out[k] = json.loads(v)
                except ValueError:
                    out[k] = v
            return out
        return {'input': raw.strip("\"'")}


__all__ = ['AgentRunner']
