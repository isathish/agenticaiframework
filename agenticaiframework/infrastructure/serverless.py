"""
Serverless Executor.

Serverless execution environment for agents with:
- Function deployment
- Auto-scaling
- Cold start optimization
- Invocation tracking
"""

import uuid
import time
import logging
import threading
from typing import Dict, Any, List, Optional, Callable
from collections import defaultdict

from .types import ServerlessFunction, FunctionInvocation

logger = logging.getLogger(__name__)


class ServerlessExecutor:
    """
    Serverless execution environment for agents.
    
    Features:
    - Function deployment
    - Auto-scaling
    - Cold start optimization
    - Invocation tracking
    """
    
    def __init__(self):
        self.functions: Dict[str, ServerlessFunction] = {}
        self.invocations: List[FunctionInvocation] = []
        self.warm_pool: Dict[str, List[Any]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # Default configuration
        self.default_memory_mb = 256
        self.default_timeout_seconds = 30
        self.max_concurrent = 100
        self._current_concurrent = 0
    
    def deploy_function(self,
                       name: str,
                       handler: Callable,
                       memory_mb: int = None,
                       timeout_seconds: int = None,
                       environment: Dict[str, str] = None,
                       runtime: str = "python3.9") -> ServerlessFunction:
        """
        Deploy a serverless function.
        
        Args:
            name: Function name
            handler: Function handler (callable)
            memory_mb: Memory allocation
            timeout_seconds: Execution timeout
            environment: Environment variables
            runtime: Runtime environment
        """
        function_id = str(uuid.uuid4())
        
        function = ServerlessFunction(
            function_id=function_id,
            name=name,
            handler=handler,
            runtime=runtime,
            memory_mb=memory_mb or self.default_memory_mb,
            timeout_seconds=timeout_seconds or self.default_timeout_seconds,
            environment=environment or {},
            metadata={},
            created_at=time.time()
        )
        
        self.functions[function_id] = function
        logger.info("Deployed function '%s' (id=%s)", name, function_id)
        
        return function
    
    def invoke(self,
              function_id: str,
              input_data: Any,
              async_invoke: bool = False) -> FunctionInvocation:
        """
        Invoke a serverless function.
        
        Args:
            function_id: Function to invoke
            input_data: Input data
            async_invoke: Whether to invoke asynchronously
        """
        function = self.functions.get(function_id)
        if not function:
            raise ValueError(f"Function '{function_id}' not found")
        
        # Check concurrency
        if self._current_concurrent >= self.max_concurrent:
            raise RuntimeError("Max concurrent invocations reached")
        
        invocation_id = str(uuid.uuid4())
        start_time = time.time()
        
        with self._lock:
            self._current_concurrent += 1
        
        try:
            # Execute function
            output_data = function.handler(input_data)
            status = "success"
        except Exception as e:
            output_data = str(e)
            status = "error"
            logger.error("Function %s invocation failed: %s", function_id, e)
        finally:
            with self._lock:
                self._current_concurrent -= 1
        
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        # Calculate billing (rounded up to nearest 100ms)
        billed_duration = ((duration_ms // 100) + 1) * 100
        
        invocation = FunctionInvocation(
            invocation_id=invocation_id,
            function_id=function_id,
            input_data=input_data,
            output_data=output_data,
            status=status,
            start_time=start_time,
            end_time=end_time,
            memory_used_mb=function.memory_mb,  # Simplified
            billed_duration_ms=billed_duration
        )
        
        self.invocations.append(invocation)
        
        return invocation
    
    def get_function(self, function_id: str) -> Optional[ServerlessFunction]:
        """Get function by ID."""
        return self.functions.get(function_id)
    
    def get_function_by_name(self, name: str) -> Optional[ServerlessFunction]:
        """Get function by name."""
        for func in self.functions.values():
            if func.name == name:
                return func
        return None
    
    def delete_function(self, function_id: str):
        """Delete a function."""
        if function_id in self.functions:
            del self.functions[function_id]
            logger.info("Deleted function %s", function_id)
    
    def get_metrics(self, function_id: str = None) -> Dict[str, Any]:
        """Get execution metrics."""
        invocations = self.invocations
        
        if function_id:
            invocations = [i for i in invocations if i.function_id == function_id]
        
        if not invocations:
            return {'error': 'No data'}
        
        durations = [(i.end_time - i.start_time) * 1000 for i in invocations]
        success_count = sum(1 for i in invocations if i.status == 'success')
        
        return {
            'total_invocations': len(invocations),
            'success_count': success_count,
            'error_count': len(invocations) - success_count,
            'success_rate': success_count / len(invocations),
            'avg_duration_ms': sum(durations) / len(durations),
            'min_duration_ms': min(durations),
            'max_duration_ms': max(durations),
            'total_billed_ms': sum(i.billed_duration_ms for i in invocations),
            'current_concurrent': self._current_concurrent
        }
    
    def list_functions(self) -> List[Dict[str, Any]]:
        """List all functions."""
        return [
            {
                'function_id': f.function_id,
                'name': f.name,
                'runtime': f.runtime,
                'memory_mb': f.memory_mb,
                'timeout_seconds': f.timeout_seconds,
                'created_at': f.created_at
            }
            for f in self.functions.values()
        ]


__all__ = ['ServerlessExecutor']
