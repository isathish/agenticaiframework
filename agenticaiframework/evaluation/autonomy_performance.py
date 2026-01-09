"""
Autonomy and Performance Evaluation systems.

Provides:
- AutonomyEvaluator: Agent planning quality, self-correction, autonomy level
- PerformanceEvaluator: Latency, throughput, stability metrics
"""

import uuid
import time
import logging
import statistics
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class AutonomyEvaluator:
    """Autonomy & Planning Evaluation system."""
    
    def __init__(self):
        self.planning_evaluations: List[Dict[str, Any]] = []
        self.autonomy_metrics: Dict[str, Any] = {
            'total_plans': 0,
            'replanning_count': 0,
            'human_interventions': 0,
            'autonomous_completions': 0,
            'goal_drift_incidents': 0,
            'plan_optimality_scores': []
        }
    
    def evaluate_plan(self,
                     goal: str,
                     plan_steps: List[str],
                     optimal_steps: List[str] = None,
                     replanned: bool = False,
                     human_intervention: bool = False,
                     goal_achieved: bool = True,
                     _metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Evaluate planning quality."""
        evaluation = {
            'id': str(uuid.uuid4()),
            'goal': goal,
            'num_steps': len(plan_steps),
            'replanned': replanned,
            'human_intervention': human_intervention,
            'goal_achieved': goal_achieved,
            'timestamp': time.time()
        }
        
        if optimal_steps:
            optimality = self._calculate_plan_optimality(plan_steps, optimal_steps)
            evaluation['optimality'] = optimality
            self.autonomy_metrics['plan_optimality_scores'].append(optimality)
        
        autonomy_score = 1.0
        if human_intervention:
            autonomy_score -= 0.5
        if replanned:
            autonomy_score -= 0.2
        if not goal_achieved:
            autonomy_score -= 0.3
        evaluation['autonomy_score'] = max(0, autonomy_score)
        
        self.planning_evaluations.append(evaluation)
        
        self.autonomy_metrics['total_plans'] += 1
        if replanned:
            self.autonomy_metrics['replanning_count'] += 1
        if human_intervention:
            self.autonomy_metrics['human_interventions'] += 1
        else:
            self.autonomy_metrics['autonomous_completions'] += 1
        if not goal_achieved:
            self.autonomy_metrics['goal_drift_incidents'] += 1
        
        return evaluation
    
    def _calculate_plan_optimality(self, actual_steps: List[str], optimal_steps: List[str]) -> float:
        if not optimal_steps:
            return 1.0
        return len(optimal_steps) / max(len(actual_steps), 1)
    
    def get_autonomy_metrics(self) -> Dict[str, Any]:
        """Get autonomy evaluation metrics."""
        metrics = self.autonomy_metrics
        total = metrics['total_plans']
        
        return {
            'total_plans': total,
            'replanning_rate': metrics['replanning_count'] / total if total else 0,
            'human_intervention_rate': metrics['human_interventions'] / total if total else 0,
            'autonomous_completion_rate': metrics['autonomous_completions'] / total if total else 0,
            'goal_drift_rate': metrics['goal_drift_incidents'] / total if total else 0,
            'avg_plan_optimality': statistics.mean(metrics['plan_optimality_scores']) if metrics['plan_optimality_scores'] else 0
        }
    
    def evaluate_plan_optimality(self, plan_steps: List[str], 
                                 optimal_steps: List[str]) -> Dict[str, Any]:
        """Evaluate plan optimality (convenience wrapper)."""
        optimality = self._calculate_plan_optimality(plan_steps, optimal_steps)
        return {
            'optimality': optimality,
            'actual_steps': len(plan_steps),
            'optimal_steps': len(optimal_steps),
            'timestamp': time.time()
        }


class PerformanceEvaluator:
    """Performance & Scalability Evaluation system."""
    
    def __init__(self):
        self.performance_data: List[Dict[str, Any]] = []
        self.latencies: List[float] = []
        self.failure_count: int = 0
        self.total_requests: int = 0
    
    def record_request(self,
                      request_id: str,
                      latency_ms: float,
                      success: bool,
                      concurrent_requests: int = 1,
                      metadata: Dict[str, Any] = None):
        """Record request performance."""
        record = {
            'request_id': request_id,
            'latency_ms': latency_ms,
            'success': success,
            'concurrent_requests': concurrent_requests,
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        
        self.performance_data.append(record)
        self.latencies.append(latency_ms)
        self.total_requests += 1
        
        if not success:
            self.failure_count += 1
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        if not self.latencies:
            return {'error': 'No data'}
        
        sorted_latencies = sorted(self.latencies)
        
        return {
            'total_requests': self.total_requests,
            'failure_rate': self.failure_count / self.total_requests if self.total_requests else 0,
            'latency_mean_ms': statistics.mean(self.latencies),
            'latency_p50_ms': sorted_latencies[len(sorted_latencies) // 2],
            'latency_p95_ms': sorted_latencies[int(len(sorted_latencies) * 0.95)],
            'latency_p99_ms': sorted_latencies[int(len(sorted_latencies) * 0.99)],
            'latency_max_ms': max(self.latencies)
        }
    
    def record_execution(self, execution_id: str, duration_ms: float,
                        success: bool = True, metadata: Dict[str, Any] = None):
        """Record execution performance (alias)."""
        self.record_request(execution_id, duration_ms, success, metadata=metadata)


__all__ = ['AutonomyEvaluator', 'PerformanceEvaluator']
