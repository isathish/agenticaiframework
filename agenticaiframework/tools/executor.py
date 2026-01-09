"""
Tool Executor for running tools within agent contexts.

Provides orchestrated tool execution with:
- Permission checking
- Resource management
- Execution tracking
- Error handling
"""

import logging
import time
import asyncio
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import BaseTool, AsyncBaseTool, ToolResult, ToolStatus, ToolConfig
from .registry import ToolRegistry, tool_registry, ToolCategory

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Context for tool execution."""
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    permissions: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0
    max_retries: int = 3


@dataclass  
class ExecutionPlan:
    """Plan for executing multiple tools."""
    tool_calls: List[Dict[str, Any]]
    parallel: bool = False
    stop_on_error: bool = True
    timeout: float = 60.0


class ToolExecutor:
    """
    Executes tools within an agent context.
    
    Features:
    - Single and batch tool execution
    - Parallel execution support
    - Permission enforcement
    - Execution history tracking
    - Resource limits
    """
    
    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        max_workers: int = 4,
        default_timeout: float = 30.0,
    ):
        self.registry = registry or tool_registry
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        
        self._execution_history: List[Dict[str, Any]] = []
        self._active_executions: Dict[str, Dict[str, Any]] = {}
        self._hooks: Dict[str, List[Callable]] = {
            'before_execute': [],
            'after_execute': [],
            'on_error': [],
        }
    
    def execute(
        self,
        tool_name: str,
        context: Optional[ExecutionContext] = None,
        **kwargs
    ) -> ToolResult:
        """
        Execute a single tool.
        
        Args:
            tool_name: Name of the tool to execute
            context: Execution context
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with execution results
        """
        context = context or ExecutionContext()
        start_time = time.time()
        
        # Get tool instance
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            return ToolResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error=f"Tool not found: {tool_name}",
            )
        
        # Check permissions
        metadata = self.registry.get_metadata(tool_name)
        if metadata and metadata.required_permissions:
            missing = set(metadata.required_permissions) - context.permissions
            if missing:
                return ToolResult(
                    tool_name=tool_name,
                    status=ToolStatus.ERROR,
                    error=f"Missing permissions: {missing}",
                )
        
        # Run before hooks
        self._run_hooks('before_execute', {
            'tool_name': tool_name,
            'context': context,
            'kwargs': kwargs,
        })
        
        # Execute with tracking
        execution_id = f"{tool_name}_{time.time()}"
        self._active_executions[execution_id] = {
            'tool_name': tool_name,
            'start_time': start_time,
            'context': context,
        }
        
        try:
            result = tool.execute(**kwargs)
            
            # Add context metadata
            result.metadata['agent_id'] = context.agent_id
            result.metadata['agent_name'] = context.agent_name
            result.metadata['session_id'] = context.session_id
            
            # Run after hooks
            self._run_hooks('after_execute', {
                'tool_name': tool_name,
                'result': result,
                'context': context,
            })
            
            # Record history
            self._record_execution(tool_name, context, result)
            
            return result
            
        except Exception as e:
            error_result = ToolResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error=str(e),
                execution_time=time.time() - start_time,
            )
            
            self._run_hooks('on_error', {
                'tool_name': tool_name,
                'error': e,
                'context': context,
            })
            
            self._record_execution(tool_name, context, error_result)
            return error_result
            
        finally:
            self._active_executions.pop(execution_id, None)
    
    async def execute_async(
        self,
        tool_name: str,
        context: Optional[ExecutionContext] = None,
        **kwargs
    ) -> ToolResult:
        """
        Execute a tool asynchronously.
        
        Args:
            tool_name: Name of the tool to execute
            context: Execution context
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with execution results
        """
        context = context or ExecutionContext()
        
        tool = self.registry.get_tool(tool_name)
        if tool is None:
            return ToolResult(
                tool_name=tool_name,
                status=ToolStatus.ERROR,
                error=f"Tool not found: {tool_name}",
            )
        
        # Use async execution if available
        if isinstance(tool, AsyncBaseTool):
            return await tool.execute_async(**kwargs)
        
        # Fall back to sync in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.execute(tool_name, context, **kwargs)
        )
    
    def execute_batch(
        self,
        plan: ExecutionPlan,
        context: Optional[ExecutionContext] = None,
    ) -> List[ToolResult]:
        """
        Execute multiple tools according to a plan.
        
        Args:
            plan: Execution plan
            context: Execution context
            
        Returns:
            List of ToolResults
        """
        context = context or ExecutionContext()
        results: List[ToolResult] = []
        
        if plan.parallel:
            results = self._execute_parallel(plan, context)
        else:
            results = self._execute_sequential(plan, context)
        
        return results
    
    def _execute_sequential(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
    ) -> List[ToolResult]:
        """Execute tools sequentially."""
        results = []
        
        for call in plan.tool_calls:
            tool_name = call.get('tool')
            kwargs = call.get('params', {})
            
            result = self.execute(tool_name, context, **kwargs)
            results.append(result)
            
            if plan.stop_on_error and not result.is_success:
                break
        
        return results
    
    def _execute_parallel(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
    ) -> List[ToolResult]:
        """Execute tools in parallel."""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            
            for i, call in enumerate(plan.tool_calls):
                tool_name = call.get('tool')
                kwargs = call.get('params', {})
                
                future = executor.submit(
                    self.execute, tool_name, context, **kwargs
                )
                futures[future] = i
            
            # Collect results in order
            result_map = {}
            for future in as_completed(futures, timeout=plan.timeout):
                idx = futures[future]
                try:
                    result_map[idx] = future.result()
                except Exception as e:
                    result_map[idx] = ToolResult(
                        tool_name=plan.tool_calls[idx].get('tool', 'unknown'),
                        status=ToolStatus.ERROR,
                        error=str(e),
                    )
            
            # Return in original order
            results = [result_map[i] for i in range(len(plan.tool_calls))]
        
        return results
    
    async def execute_batch_async(
        self,
        plan: ExecutionPlan,
        context: Optional[ExecutionContext] = None,
    ) -> List[ToolResult]:
        """Execute multiple tools asynchronously."""
        context = context or ExecutionContext()
        
        if plan.parallel:
            tasks = [
                self.execute_async(
                    call.get('tool'),
                    context,
                    **call.get('params', {})
                )
                for call in plan.tool_calls
            ]
            return await asyncio.gather(*tasks, return_exceptions=False)
        else:
            results = []
            for call in plan.tool_calls:
                result = await self.execute_async(
                    call.get('tool'),
                    context,
                    **call.get('params', {})
                )
                results.append(result)
                
                if plan.stop_on_error and not result.is_success:
                    break
            
            return results
    
    def _record_execution(
        self,
        tool_name: str,
        context: ExecutionContext,
        result: ToolResult,
    ) -> None:
        """Record execution in history."""
        self._execution_history.append({
            'tool_name': tool_name,
            'agent_id': context.agent_id,
            'session_id': context.session_id,
            'status': result.status.value,
            'execution_time': result.execution_time,
            'timestamp': result.timestamp,
            'error': result.error,
        })
        
        # Limit history size
        if len(self._execution_history) > 1000:
            self._execution_history = self._execution_history[-500:]
    
    def get_history(
        self,
        agent_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get execution history.
        
        Args:
            agent_id: Filter by agent
            tool_name: Filter by tool
            limit: Maximum records to return
        """
        history = self._execution_history
        
        if agent_id:
            history = [h for h in history if h.get('agent_id') == agent_id]
        
        if tool_name:
            history = [h for h in history if h.get('tool_name') == tool_name]
        
        return history[-limit:]
    
    def add_hook(self, event: str, callback: Callable) -> None:
        """Add a hook callback."""
        if event in self._hooks:
            self._hooks[event].append(callback)
    
    def _run_hooks(self, event: str, data: Any) -> None:
        """Run hooks for an event."""
        for hook in self._hooks.get(event, []):
            try:
                hook(data)
            except Exception as e:
                logger.error("Hook error: %s", e)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        history = self._execution_history
        
        successful = sum(1 for h in history if h.get('status') == 'success')
        total = len(history)
        
        return {
            'total_executions': total,
            'successful_executions': successful,
            'failed_executions': total - successful,
            'success_rate': successful / total if total > 0 else 0,
            'active_executions': len(self._active_executions),
            'avg_execution_time': (
                sum(h.get('execution_time', 0) for h in history) / total
                if total > 0 else 0
            ),
        }


# Global executor instance
tool_executor = ToolExecutor()


__all__ = [
    'ExecutionContext',
    'ExecutionPlan',
    'ToolExecutor',
    'tool_executor',
]
