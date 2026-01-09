"""
Workflow/Orchestration Evaluation system.

Tracks multi-agent workflows, handoffs, and orchestration success.
"""

import uuid
import time
import logging
import statistics
from typing import Dict, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class WorkflowEvaluator:
    """
    Workflow/Orchestration Evaluation system.
    
    Tracks multi-agent workflows, handoffs, and orchestration success.
    """
    
    def __init__(self):
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.workflow_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {'attempts': 0, 'completions': 0, 'deadlocks': 0, 'durations': []}
        )
    
    def start_workflow(self, workflow_name: str, workflow_id: str = None) -> str:
        """Start tracking a workflow."""
        workflow_id = workflow_id or str(uuid.uuid4())
        
        self.workflows[workflow_id] = {
            'id': workflow_id,
            'name': workflow_name,
            'status': 'running',
            'steps': [],
            'agents': set(),
            'start_time': time.time(),
            'end_time': None
        }
        
        self.workflow_metrics[workflow_name]['attempts'] += 1
        return workflow_id
    
    def record_step(self,
                   workflow_id: str,
                   step_name: str,
                   agent_name: str = None,
                   success: bool = True,
                   metadata: Dict[str, Any] = None):
        """Record a workflow step."""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        
        step = {
            'step_name': step_name,
            'agent': agent_name,
            'success': success,
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        
        workflow['steps'].append(step)
        if agent_name:
            workflow['agents'].add(agent_name)
    
    def complete_workflow(self, workflow_id: str, success: bool = True, deadlock: bool = False):
        """Mark workflow as complete."""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        workflow['status'] = 'completed' if success else 'failed'
        workflow['end_time'] = time.time()
        
        duration = workflow['end_time'] - workflow['start_time']
        
        metrics = self.workflow_metrics[workflow['name']]
        if success:
            metrics['completions'] += 1
        if deadlock:
            metrics['deadlocks'] += 1
        metrics['durations'].append(duration)
    
    def get_workflow_metrics(self, workflow_name: str = None) -> Dict[str, Any]:
        """Get workflow metrics."""
        if workflow_name:
            if workflow_name not in self.workflow_metrics:
                return {'error': 'Workflow not found'}
            
            metrics = self.workflow_metrics[workflow_name]
            total = metrics['attempts']
            
            return {
                'workflow_name': workflow_name,
                'completion_rate': metrics['completions'] / total if total else 0,
                'deadlock_rate': metrics['deadlocks'] / total if total else 0,
                'avg_duration_seconds': statistics.mean(metrics['durations']) if metrics['durations'] else 0,
                'total_attempts': total
            }
        
        summary = {}
        for name, metrics in self.workflow_metrics.items():
            total = metrics['attempts']
            summary[name] = {
                'completion_rate': metrics['completions'] / total if total else 0,
                'attempts': total
            }
        return summary
    
    def record_workflow_execution(self,
                                  workflow_name: str,
                                  success: bool = True,
                                  deadlock: bool = False,
                                  metadata: Dict[str, Any] = None) -> str:
        """Record a complete workflow execution (convenience wrapper)."""
        workflow_id = self.start_workflow(workflow_name)
        if metadata:
            self.record_step(workflow_id, "execution", success=success, metadata=metadata)
        self.complete_workflow(workflow_id, success=success, deadlock=deadlock)
        return workflow_id
    
    def record_agent_handoff(self,
                            workflow_id: str,
                            from_agent: str,
                            to_agent: str,
                            metadata: Dict[str, Any] = None):
        """Record an agent handoff in a workflow."""
        handoff_metadata = metadata or {}
        handoff_metadata['from_agent'] = from_agent
        handoff_metadata['to_agent'] = to_agent
        
        self.record_step(
            workflow_id,
            step_name=f"handoff_{from_agent}_to_{to_agent}",
            agent_name=to_agent,
            success=True,
            metadata=handoff_metadata
        )


__all__ = ['WorkflowEvaluator']
