"""
Cost vs Quality scoring system.

Features:
- Token cost tracking
- Quality-adjusted cost metrics
- Budget monitoring
- Cost optimization recommendations
"""

import uuid
import time
import logging
import statistics
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class CostQualityScorer:
    """
    Cost vs Quality scoring system.
    
    Features:
    - Token cost tracking
    - Quality-adjusted cost metrics
    - Budget monitoring
    - Cost optimization recommendations
    """
    
    def __init__(self):
        self.executions: List[Dict[str, Any]] = []
        self.budgets: Dict[str, float] = {}
        self.budget_alerts: List[Dict[str, Any]] = []
        
        # Default model costs (per 1K tokens)
        self.model_costs: Dict[str, Dict[str, float]] = {
            'gpt-4': {'input': 0.03, 'output': 0.06},  # Legacy model
            'gpt-4o': {'input': 0.0025, 'output': 0.01},
            'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
            'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
            'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
            'o1': {'input': 0.015, 'output': 0.06},
            'o1-mini': {'input': 0.003, 'output': 0.012},
            'o3-mini': {'input': 0.0011, 'output': 0.0044},
            'claude-4-opus': {'input': 0.015, 'output': 0.075},
            'claude-4-sonnet': {'input': 0.003, 'output': 0.015},
            'claude-3.5-haiku': {'input': 0.0008, 'output': 0.004},
            'claude-3-opus': {'input': 0.015, 'output': 0.075},
            'claude-3-sonnet': {'input': 0.003, 'output': 0.015},
            'claude-3-haiku': {'input': 0.00025, 'output': 0.00125},
            'gemini-2.0-flash': {'input': 0.0001, 'output': 0.0004},
            'gemini-1.5-pro': {'input': 0.00125, 'output': 0.005},
            'phi-4': {'input': 0.0001, 'output': 0.0004},
            'mistral-small': {'input': 0.0002, 'output': 0.0006},
            'deepseek-r1': {'input': 0.00055, 'output': 0.00219},
            'deepseek-v3': {'input': 0.00027, 'output': 0.0011},
        }
    
    def set_model_cost(self, model_name: str, 
                       input_cost_per_1k: float, 
                       output_cost_per_1k: float):
        """Set cost for a model."""
        self.model_costs[model_name] = {
            'input': input_cost_per_1k,
            'output': output_cost_per_1k
        }
    
    def set_budget(self, budget_name: str, amount: float):
        """Set a budget limit."""
        self.budgets[budget_name] = amount
    
    def record_execution(self,
                        model_name: str,
                        input_tokens: int,
                        output_tokens: int,
                        quality_score: float,
                        budget_name: str = None,
                        metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record an execution with cost and quality."""
        costs = self.model_costs.get(model_name, {'input': 0, 'output': 0})
        
        input_cost = (input_tokens / 1000) * costs['input']
        output_cost = (output_tokens / 1000) * costs['output']
        total_cost = input_cost + output_cost
        
        cost_per_quality = total_cost / quality_score if quality_score > 0 else float('inf')
        quality_per_dollar = quality_score / total_cost if total_cost > 0 else float('inf')
        
        execution = {
            'id': str(uuid.uuid4()),
            'model': model_name,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': total_cost,
            'quality_score': quality_score,
            'cost_per_quality': cost_per_quality,
            'quality_per_dollar': quality_per_dollar,
            'budget_name': budget_name,
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        
        self.executions.append(execution)
        
        if budget_name and budget_name in self.budgets:
            self._check_budget(budget_name, total_cost)
        
        return execution
    
    def _check_budget(self, budget_name: str, _cost: float):
        """Check if budget is exceeded."""
        budget = self.budgets[budget_name]
        total_spent = self.get_budget_spent(budget_name)
        
        if total_spent > budget:
            alert = {
                'id': str(uuid.uuid4()),
                'budget_name': budget_name,
                'budget': budget,
                'spent': total_spent,
                'overage': total_spent - budget,
                'timestamp': time.time()
            }
            self.budget_alerts.append(alert)
            logger.warning("Budget '%s' exceeded: $%.4f > $%.4f",
                         budget_name, total_spent, budget)
        elif total_spent > budget * 0.9:
            logger.warning("Budget '%s' at %.1f%% utilization",
                         budget_name, (total_spent / budget) * 100)
    
    def get_budget_spent(self, budget_name: str) -> float:
        """Get total spent for a budget."""
        return sum(
            e['total_cost'] for e in self.executions 
            if e.get('budget_name') == budget_name
        )
    
    def get_cost_summary(self, 
                        start_time: float = None,
                        end_time: float = None) -> Dict[str, Any]:
        """Get cost summary."""
        executions = self.executions
        
        if start_time:
            executions = [e for e in executions if e['timestamp'] >= start_time]
        if end_time:
            executions = [e for e in executions if e['timestamp'] <= end_time]
        
        if not executions:
            return {'error': 'No data'}
        
        by_model = defaultdict(lambda: {
            'count': 0, 'total_cost': 0, 'total_tokens': 0, 
            'avg_quality': 0, 'quality_scores': []
        })
        
        for e in executions:
            model = e['model']
            by_model[model]['count'] += 1
            by_model[model]['total_cost'] += e['total_cost']
            by_model[model]['total_tokens'] += e['total_tokens']
            by_model[model]['quality_scores'].append(e['quality_score'])
        
        for model, stats in by_model.items():
            stats['avg_quality'] = statistics.mean(stats['quality_scores'])
            stats['cost_per_quality'] = (
                stats['total_cost'] / stats['avg_quality'] 
                if stats['avg_quality'] > 0 else float('inf')
            )
            del stats['quality_scores']
        
        return {
            'total_executions': len(executions),
            'total_cost': sum(e['total_cost'] for e in executions),
            'total_tokens': sum(e['total_tokens'] for e in executions),
            'avg_quality': statistics.mean(e['quality_score'] for e in executions),
            'by_model': dict(by_model),
            'budget_alerts': len(self.budget_alerts)
        }
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Get cost optimization recommendations."""
        recommendations = []
        
        if len(self.executions) < 10:
            return [{'message': 'Insufficient data for recommendations'}]
        
        model_stats = defaultdict(lambda: {'costs': [], 'qualities': []})
        for e in self.executions:
            model_stats[e['model']]['costs'].append(e['total_cost'])
            model_stats[e['model']]['qualities'].append(e['quality_score'])
        
        efficiency = {}
        for model, stats in model_stats.items():
            avg_cost = statistics.mean(stats['costs'])
            avg_quality = statistics.mean(stats['qualities'])
            efficiency[model] = avg_quality / avg_cost if avg_cost > 0 else 0
        
        best_model = max(efficiency, key=efficiency.get)
        
        if efficiency:
            recommendations.append({
                'type': 'model_selection',
                'message': f"Consider using '{best_model}' for best quality/cost ratio",
                'efficiency_scores': efficiency
            })
        
        return recommendations


__all__ = ['CostQualityScorer']
