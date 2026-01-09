"""
Task and Tool Evaluation systems.

Provides:
- TaskEvaluator: Task completion, instruction following, multi-step reasoning
- ToolInvocationEvaluator: Tool usage correctness, parameter validity, call ordering
"""

import uuid
import time
import logging
import statistics
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class TaskEvaluator:
    """Task/Skill-Level Evaluation system."""
    
    def __init__(self):
        self.task_executions: List[Dict[str, Any]] = []
        self.task_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {'attempts': 0, 'successes': 0, 'failures': 0, 'retries': []}
        )
    
    def record_task_execution(self,
                            task_name: str,
                            success: bool,
                            completion_percentage: float = None,
                            retry_count: int = 0,
                            error_recovered: bool = False,
                            duration_ms: float = None,
                            metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record task execution."""
        execution = {
            'id': str(uuid.uuid4()),
            'task_name': task_name,
            'success': success,
            'completion_percentage': completion_percentage or (100.0 if success else 0.0),
            'retry_count': retry_count,
            'error_recovered': error_recovered,
            'duration_ms': duration_ms,
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        
        self.task_executions.append(execution)
        
        metrics = self.task_metrics[task_name]
        metrics['attempts'] += 1
        if success:
            metrics['successes'] += 1
        else:
            metrics['failures'] += 1
        metrics['retries'].append(retry_count)
        
        return execution
    
    def get_task_metrics(self, task_name: str = None) -> Dict[str, Any]:
        """Get metrics for a specific task or all tasks."""
        if task_name:
            if task_name not in self.task_metrics:
                return {'error': 'Task not found'}
            
            metrics = self.task_metrics[task_name]
            total = metrics['attempts']
            
            return {
                'task_name': task_name,
                'success_rate': metrics['successes'] / total if total else 0,
                'failure_rate': metrics['failures'] / total if total else 0,
                'avg_retry_count': statistics.mean(metrics['retries']) if metrics['retries'] else 0,
                'total_attempts': total
            }
        
        summary = {}
        for task, metrics in self.task_metrics.items():
            total = metrics['attempts']
            summary[task] = {
                'success_rate': metrics['successes'] / total if total else 0,
                'attempts': total
            }
        return summary


class ToolInvocationEvaluator:
    """Tool & API Invocation Evaluation system."""
    
    def __init__(self):
        self.tool_calls: List[Dict[str, Any]] = []
        self.tool_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'calls': 0, 'successful': 0, 'failed': 0,
                'invalid_params': 0, 'latencies': []
            }
        )
    
    def record_tool_call(self,
                        tool_name: str,
                        parameters: Dict[str, Any],
                        success: bool,
                        valid_parameters: bool = True,
                        latency_ms: float = None,
                        error: str = None,
                        metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record tool invocation."""
        call = {
            'id': str(uuid.uuid4()),
            'tool_name': tool_name,
            'parameters': parameters,
            'success': success,
            'valid_parameters': valid_parameters,
            'latency_ms': latency_ms,
            'error': error,
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        
        self.tool_calls.append(call)
        
        metrics = self.tool_metrics[tool_name]
        metrics['calls'] += 1
        if success:
            metrics['successful'] += 1
        else:
            metrics['failed'] += 1
        if not valid_parameters:
            metrics['invalid_params'] += 1
        if latency_ms:
            metrics['latencies'].append(latency_ms)
        
        return call
    
    def get_tool_metrics(self, tool_name: str = None) -> Dict[str, Any]:
        """Get tool usage metrics."""
        if tool_name:
            if tool_name not in self.tool_metrics:
                return {'error': 'Tool not found'}
            
            metrics = self.tool_metrics[tool_name]
            total = metrics['calls']
            
            return {
                'tool_name': tool_name,
                'success_rate': metrics['successful'] / total if total else 0,
                'failure_rate': metrics['failed'] / total if total else 0,
                'invalid_param_rate': metrics['invalid_params'] / total if total else 0,
                'avg_latency_ms': statistics.mean(metrics['latencies']) if metrics['latencies'] else 0,
                'total_calls': total
            }
        
        summary = {}
        for tool, metrics in self.tool_metrics.items():
            total = metrics['calls']
            summary[tool] = {
                'success_rate': metrics['successful'] / total if total else 0,
                'calls': total
            }
        return summary
    
    def detect_tool_call_patterns(self) -> Dict[str, Any]:
        """Detect common tool call patterns and issues."""
        if len(self.tool_calls) < 2:
            return {'error': 'Insufficient data'}
        
        patterns = {
            'repeated_failures': [],
            'slow_tools': [],
            'frequent_invalid_params': []
        }
        
        for tool, metrics in self.tool_metrics.items():
            total = metrics['calls']
            if total < 5:
                continue
            
            if metrics['failed'] / total > 0.3:
                patterns['repeated_failures'].append(tool)
            
            if metrics['latencies'] and statistics.mean(metrics['latencies']) > 5000:
                patterns['slow_tools'].append(tool)
            
            if metrics['invalid_params'] / total > 0.2:
                patterns['frequent_invalid_params'].append(tool)
        
        return patterns


__all__ = ['TaskEvaluator', 'ToolInvocationEvaluator']
