"""
ReAct-Style Agentic Runner.

Provides an agentic execution loop with:
- Thought/Action/Observation cycle (ReAct pattern)
- Multi-step tool calling
- Structured input/output
- Step-by-step tracing
"""

import time
import re
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

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


class AgentRunner:
    """
    ReAct-style agentic runner.
    
    Provides:
    - Structured input/output
    - Multi-step tool execution loop
    - Thought/Action/Observation tracing
    - Guardrail enforcement
    - Knowledge retrieval integration
    """
    
    THOUGHT_PATTERN = re.compile(r"Thought:\s*(.+?)(?=Action:|Observation:|$)", re.DOTALL | re.IGNORECASE)
    ACTION_PATTERN = re.compile(r"Action:\s*(\w+)\s*\[(.+?)\]", re.DOTALL | re.IGNORECASE)
    FINAL_ANSWER_PATTERN = re.compile(r"Final Answer:\s*(.+)", re.DOTALL | re.IGNORECASE)
    
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
    ):
        self.agent = agent
        self.llm_manager = llm_manager or agent.config.get('llm') or agent.config.get('llm_manager')
        self.knowledge = knowledge or agent.config.get('knowledge')
        self.guardrail_manager = guardrail_manager or agent.config.get('guardrail_manager')
        self.guardrail_pipeline = guardrail_pipeline or agent.config.get('guardrail_pipeline')
        self.policy_manager = policy_manager or agent.config.get('policy_manager')
        self.monitor = monitor or agent.config.get('monitor')
        self.tracer = tracer or agent.config.get('tracer')
    
    def run(self, input_data: AgentInput) -> AgentOutput:
        """
        Run the agent with structured input.
        
        Args:
            input_data: Structured AgentInput
            
        Returns:
            AgentOutput with steps, thoughts, and response
        """
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
        knowledge_results: List[Dict[str, Any]] = []
        
        # Start trace
        trace_context = tracer.start_trace(f"agent.run:{self.agent.name}")
        trace_id = trace_context.trace_id if trace_context else None
        
        # Record input step
        steps.append(AgentStep(
            step_type=StepType.INPUT,
            name="user_input",
            content=input_data.prompt,
            metadata={'system_prompt': input_data.system_prompt},
        ))
        
        def finalize(output: AgentOutput) -> AgentOutput:
            output.latency_seconds = time.time() - start_time
            output.trace_id = trace_id
            output.steps = steps
            output.thoughts = thoughts
            if trace_context:
                status = "OK" if output.is_success else "ERROR"
                tracer.end_span(trace_context, status=status)
            return output
        
        try:
            # Input guardrails
            step_start = time.time()
            guardrail_report = {}
            if self.guardrail_pipeline:
                guardrail_report = self.guardrail_pipeline.execute(input_data.prompt, context=input_data.context)
            elif guardrail_mgr:
                guardrail_report = guardrail_mgr.enforce_guardrails(input_data.prompt, fail_fast=True)
            
            steps.append(AgentStep(
                step_type=StepType.GUARDRAIL,
                name="input_guardrails",
                content=guardrail_report,
                duration_ms=(time.time() - step_start) * 1000,
            ))
            
            if not guardrail_report.get('is_valid', True):
                return finalize(AgentOutput(
                    status=AgentStatus.BLOCKED,
                    guardrail_report=guardrail_report,
                    error="Input blocked by guardrails",
                ))
            
            # Knowledge retrieval
            if self.knowledge:
                step_start = time.time()
                query = input_data.knowledge_query or input_data.prompt
                knowledge_results = self.knowledge.retrieve(query)
                steps.append(AgentStep(
                    step_type=StepType.KNOWLEDGE,
                    name="knowledge_retrieval",
                    content=knowledge_results[:5] if knowledge_results else [],
                    duration_ms=(time.time() - step_start) * 1000,
                    metadata={'query': query},
                ))
                
                if knowledge_results:
                    self.agent.context_manager.add_context(
                        f"Retrieved knowledge: {str(knowledge_results[:3])[:500]}",
                        importance=0.7,
                        context_type=ContextType.KNOWLEDGE,
                    )
            
            # Bind tools
            if input_data.tools:
                agent_tool_manager.bind_tools(self.agent, input_data.tools)
            
            # Build system prompt
            system_parts = []
            if input_data.system_prompt:
                system_parts.append(input_data.system_prompt)
            else:
                system_parts.append(f"You are {self.agent.name}, an AI assistant with role: {self.agent.role}.")
            
            if input_data.tools:
                tool_schemas = agent_tool_manager.get_all_schemas(self.agent)
                tool_desc = "\n".join(
                    f"- {t['name']}: {t.get('description', 'No description')}"
                    for t in tool_schemas
                )
                system_parts.append(f"\nAvailable tools:\n{tool_desc}")
                system_parts.append("""
When you need to use a tool, format your response as:
Thought: [your reasoning]
Action: tool_name[input parameters as JSON]

After receiving the observation, continue reasoning or provide:
Final Answer: [your final response to the user]
""")
            
            system_prompt = "\n".join(system_parts)
            
            # Build initial prompt
            context_summary = self.agent.context_manager.get_context_summary()
            prompt_parts = [system_prompt]
            if context_summary and context_summary != "No context available.":
                prompt_parts.append(f"\nContext:\n{context_summary}")
            if knowledge_results:
                knowledge_text = "\n".join(f"- {str(k)[:200]}" for k in knowledge_results[:3])
                prompt_parts.append(f"\nKnowledge:\n{knowledge_text}")
            prompt_parts.append(f"\nUser: {input_data.prompt}")
            
            current_prompt = "\n".join(prompt_parts)
            
            # Agentic loop
            iteration = 0
            final_response = None
            
            while iteration < input_data.max_iterations:
                iteration += 1
                
                # LLM call
                step_start = time.time()
                llm_response = self.llm_manager.generate(
                    current_prompt,
                    temperature=input_data.temperature,
                )
                
                if llm_response is None:
                    return finalize(AgentOutput(
                        status=AgentStatus.ERROR,
                        error="LLM generation failed",
                    ))
                
                steps.append(AgentStep(
                    step_type=StepType.LLM_CALL,
                    name=f"llm_call_{iteration}",
                    content=llm_response,
                    duration_ms=(time.time() - step_start) * 1000,
                    metadata={'iteration': iteration},
                ))
                
                # Parse response
                final_match = self.FINAL_ANSWER_PATTERN.search(llm_response)
                if final_match:
                    final_response = final_match.group(1).strip()
                    thoughts.append(AgentThought(
                        thought="Providing final answer",
                        observation=final_response,
                    ))
                    break
                
                # Parse thought
                thought_match = self.THOUGHT_PATTERN.search(llm_response)
                thought_text = thought_match.group(1).strip() if thought_match else ""
                
                # Parse action
                action_match = self.ACTION_PATTERN.search(llm_response)
                if action_match:
                    action_name = action_match.group(1).strip()
                    action_input_str = action_match.group(2).strip()
                    
                    # Parse action input
                    import json
                    try:
                        action_input = json.loads(action_input_str)
                    except json.JSONDecodeError:
                        action_input = {'input': action_input_str}
                    
                    # Check policy
                    if self.policy_manager:
                        policy_result = self.policy_manager.evaluate_policies(
                            self.agent.id,
                            action=action_name,
                            resource=action_name,
                            context={'agent_id': self.agent.id},
                        )
                        if not policy_result.get('allowed', True):
                            observation = f"Tool {action_name} blocked by policy: {policy_result.get('reasons')}"
                            thoughts.append(AgentThought(
                                thought=thought_text,
                                action=action_name,
                                action_input=action_input,
                                observation=observation,
                            ))
                            current_prompt += f"\n{llm_response}\nObservation: {observation}"
                            continue
                    
                    # Execute tool
                    step_start = time.time()
                    
                    # Merge with predefined tool inputs
                    merged_input = {**(input_data.tool_inputs or {}).get(action_name, {}), **action_input}
                    
                    tool_result = agent_tool_manager.execute_tool(self.agent, action_name, **merged_input)
                    tool_results.append(tool_result.to_dict())
                    
                    observation = str(tool_result.data) if tool_result.is_success else f"Error: {tool_result.error}"
                    
                    steps.append(AgentStep(
                        step_type=StepType.TOOL_CALL,
                        name=f"tool_{action_name}",
                        content={'action': action_name, 'input': merged_input},
                        duration_ms=(time.time() - step_start) * 1000,
                    ))
                    steps.append(AgentStep(
                        step_type=StepType.TOOL_RESULT,
                        name=f"tool_result_{action_name}",
                        content=observation[:1000],
                        duration_ms=0,
                    ))
                    
                    thoughts.append(AgentThought(
                        thought=thought_text,
                        action=action_name,
                        action_input=merged_input,
                        observation=observation[:500],
                    ))
                    
                    # Add to context
                    self.agent.context_manager.add_context(
                        f"Tool {action_name} result: {observation[:300]}",
                        importance=0.6,
                        context_type=ContextType.TOOL_RESULT,
                    )
                    
                    # Continue loop
                    current_prompt += f"\n{llm_response}\nObservation: {observation}"
                
                else:
                    # No action found, treat as final response
                    final_response = llm_response
                    thoughts.append(AgentThought(
                        thought=thought_text or "Generating response",
                        observation=llm_response[:500],
                    ))
                    break
            
            if final_response is None:
                final_response = "Max iterations reached without final answer."
            
            # Output guardrails
            step_start = time.time()
            output_report = {}
            if self.guardrail_pipeline:
                output_report = self.guardrail_pipeline.execute(final_response, context=input_data.context)
            elif guardrail_mgr:
                output_report = guardrail_mgr.enforce_guardrails(final_response, fail_fast=True)
            
            steps.append(AgentStep(
                step_type=StepType.GUARDRAIL,
                name="output_guardrails",
                content=output_report,
                duration_ms=(time.time() - step_start) * 1000,
            ))
            
            if not output_report.get('is_valid', True):
                return finalize(AgentOutput(
                    status=AgentStatus.BLOCKED,
                    guardrail_report=output_report,
                    error="Output blocked by guardrails",
                ))
            
            # Record output step
            steps.append(AgentStep(
                step_type=StepType.OUTPUT,
                name="final_output",
                content=final_response,
            ))
            
            # Add to memory
            from ..context import ContextType
            self.agent.context_manager.add_context(
                input_data.prompt,
                importance=0.5,
                context_type=ContextType.USER,
            )
            self.agent.context_manager.add_context(
                final_response,
                importance=0.6,
                context_type=ContextType.ASSISTANT,
            )
            
            # Monitor
            if self.monitor:
                self.monitor.record_metric('agent.execution_seconds', time.time() - start_time)
                self.monitor.log_event('agent.run_complete', {
                    'agent_id': self.agent.id,
                    'iterations': iteration,
                    'tools_used': [t.get('tool_name') for t in tool_results],
                })
            
            return finalize(AgentOutput(
                status=AgentStatus.SUCCESS,
                response=final_response,
                tool_results=tool_results,
                knowledge_results=knowledge_results,
                guardrail_report=guardrail_report,
            ))
        
        except Exception as e:
            logger.exception("AgentRunner error")
            steps.append(AgentStep(
                step_type=StepType.ERROR,
                name="error",
                content=str(e),
            ))
            return finalize(AgentOutput(
                status=AgentStatus.ERROR,
                error=str(e),
            ))


__all__ = ['AgentRunner']
