"""
Model Tier Evaluator for SLM/MLM/LLM/RLM support.

Provides tier-specific evaluation:
- SLM: Speed and cost efficiency
- MLM: Balance of quality and cost
- LLM: Quality and capability
- RLM: Reasoning depth and accuracy
"""

import time
import logging
import statistics
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class ModelTierEvaluator:
    """Evaluator for different model tiers (SLM, MLM, LLM, RLM)."""
    
    def __init__(self):
        self.evaluations: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.tier_benchmarks = {
            'slm': {
                'expected_latency_ms': 300,
                'expected_cost_per_1k': 0.0005,
                'min_quality_threshold': 0.6
            },
            'mlm': {
                'expected_latency_ms': 800,
                'expected_cost_per_1k': 0.002,
                'min_quality_threshold': 0.75
            },
            'llm': {
                'expected_latency_ms': 1500,
                'expected_cost_per_1k': 0.01,
                'min_quality_threshold': 0.85
            },
            'rlm': {
                'expected_latency_ms': 5000,
                'expected_cost_per_1k': 0.02,
                'min_quality_threshold': 0.90,
                'min_reasoning_depth': 3
            }
        }
    
    def evaluate_model(self,
                      model_name: str,
                      tier: str,
                      response: str,
                      latency_ms: float,
                      input_tokens: int,
                      output_tokens: int,
                      cost: float,
                      ground_truth: str = None,
                      reasoning_steps: List[str] = None) -> Dict[str, Any]:
        """Evaluate a model response based on its tier."""
        tier = tier.lower()
        benchmarks = self.tier_benchmarks.get(tier, self.tier_benchmarks['llm'])
        
        evaluation = {
            'model_name': model_name,
            'tier': tier,
            'timestamp': time.time(),
            'metrics': {},
            'benchmarks': benchmarks,
            'scores': {}
        }
        
        evaluation['metrics']['latency_ms'] = latency_ms
        evaluation['metrics']['input_tokens'] = input_tokens
        evaluation['metrics']['output_tokens'] = output_tokens
        evaluation['metrics']['total_tokens'] = input_tokens + output_tokens
        evaluation['metrics']['cost'] = cost
        evaluation['metrics']['tokens_per_second'] = output_tokens / (latency_ms / 1000) if latency_ms > 0 else 0
        
        expected_latency = benchmarks['expected_latency_ms']
        evaluation['scores']['latency'] = min(1.0, expected_latency / latency_ms) if latency_ms > 0 else 1.0
        
        cost_per_1k = (cost / (input_tokens + output_tokens)) * 1000 if (input_tokens + output_tokens) > 0 else 0
        expected_cost = benchmarks['expected_cost_per_1k']
        evaluation['scores']['cost_efficiency'] = min(1.0, expected_cost / cost_per_1k) if cost_per_1k > 0 else 1.0
        
        if ground_truth:
            evaluation['scores']['accuracy'] = self._calculate_accuracy(response, ground_truth)
        
        if tier == 'rlm' and reasoning_steps:
            evaluation['metrics']['reasoning_depth'] = len(reasoning_steps)
            evaluation['scores']['reasoning_quality'] = self._evaluate_reasoning(reasoning_steps)
            
            min_depth = benchmarks.get('min_reasoning_depth', 3)
            evaluation['scores']['reasoning_depth_score'] = min(1.0, len(reasoning_steps) / min_depth)
        
        scores = evaluation['scores']
        if scores:
            evaluation['overall_score'] = statistics.mean(scores.values())
            evaluation['meets_tier_requirements'] = evaluation['overall_score'] >= benchmarks['min_quality_threshold']
        
        self.evaluations[model_name].append(evaluation)
        
        return evaluation
    
    def _calculate_accuracy(self, response: str, ground_truth: str) -> float:
        """Calculate accuracy score."""
        response_lower = response.lower().strip()
        truth_lower = ground_truth.lower().strip()
        
        if response_lower == truth_lower:
            return 1.0
        
        resp_tokens = set(response_lower.split())
        truth_tokens = set(truth_lower.split())
        
        if not truth_tokens:
            return 0.0
        
        return len(resp_tokens & truth_tokens) / len(truth_tokens)
    
    def _evaluate_reasoning(self, steps: List[str]) -> float:
        """Evaluate reasoning quality."""
        if not steps:
            return 0.0
        
        score = 0.0
        connectors = ['therefore', 'because', 'thus', 'hence', 'since', 'given', 'if', 'then']
        
        for step in steps:
            step_lower = step.lower()
            if any(c in step_lower for c in connectors):
                score += 0.2
        
        if len(steps) >= 2:
            score += 0.3
        
        last_step = steps[-1].lower()
        if any(c in last_step for c in ['therefore', 'conclusion', 'answer', 'result']):
            score += 0.2
        
        return min(1.0, score)
    
    def get_model_summary(self, model_name: str) -> Dict[str, Any]:
        """Get summary of model evaluations."""
        evals = self.evaluations.get(model_name, [])
        if not evals:
            return {'error': 'No evaluations found'}
        
        metrics = defaultdict(list)
        scores = defaultdict(list)
        
        for e in evals:
            for k, v in e.get('metrics', {}).items():
                if isinstance(v, (int, float)):
                    metrics[k].append(v)
            for k, v in e.get('scores', {}).items():
                if isinstance(v, (int, float)):
                    scores[k].append(v)
        
        return {
            'model_name': model_name,
            'tier': evals[0].get('tier', 'unknown'),
            'total_evaluations': len(evals),
            'avg_metrics': {k: statistics.mean(v) for k, v in metrics.items()},
            'avg_scores': {k: statistics.mean(v) for k, v in scores.items()},
            'meets_requirements_rate': sum(1 for e in evals if e.get('meets_tier_requirements', False)) / len(evals)
        }
    
    def compare_tiers(self) -> Dict[str, Any]:
        """Compare performance across tiers."""
        tier_stats = defaultdict(lambda: {'count': 0, 'avg_latency': [], 'avg_cost': [], 'avg_score': []})
        
        for _model_name, evals in self.evaluations.items():
            for e in evals:
                tier = e.get('tier', 'unknown')
                tier_stats[tier]['count'] += 1
                tier_stats[tier]['avg_latency'].append(e['metrics'].get('latency_ms', 0))
                tier_stats[tier]['avg_cost'].append(e['metrics'].get('cost', 0))
                if 'overall_score' in e:
                    tier_stats[tier]['avg_score'].append(e['overall_score'])
        
        comparison = {}
        for tier, stats in tier_stats.items():
            comparison[tier] = {
                'evaluation_count': stats['count'],
                'avg_latency_ms': statistics.mean(stats['avg_latency']) if stats['avg_latency'] else 0,
                'avg_cost': statistics.mean(stats['avg_cost']) if stats['avg_cost'] else 0,
                'avg_score': statistics.mean(stats['avg_score']) if stats['avg_score'] else 0
            }
        
        return comparison


# Global instance
model_tier_evaluator = ModelTierEvaluator()

__all__ = ['ModelTierEvaluator', 'model_tier_evaluator']
