"""
Human-in-the-Loop and Business Outcome Evaluation systems.

Provides:
- HITLEvaluator: Agent-human collaboration quality
- BusinessOutcomeEvaluator: Real-world business impact and value creation
"""

import uuid
import time
import logging
import statistics
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class HITLEvaluator:
    """Human-in-the-Loop (HITL) Evaluation system."""
    
    def __init__(self):
        self.hitl_interactions: List[Dict[str, Any]] = []
        self.hitl_metrics: Dict[str, Any] = {
            'total_escalations': 0,
            'accepted_recommendations': 0,
            'overridden_decisions': 0,
            'review_times': [],
            'trust_scores': []
        }
    
    def record_escalation(self,
                         agent_recommendation: str,
                         human_accepted: bool,
                         review_time_seconds: float = None,
                         trust_score: float = None,
                         metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record human-in-the-loop interaction."""
        interaction = {
            'id': str(uuid.uuid4()),
            'recommendation': agent_recommendation,
            'accepted': human_accepted,
            'review_time_seconds': review_time_seconds,
            'trust_score': trust_score,
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        
        self.hitl_interactions.append(interaction)
        
        self.hitl_metrics['total_escalations'] += 1
        if human_accepted:
            self.hitl_metrics['accepted_recommendations'] += 1
        else:
            self.hitl_metrics['overridden_decisions'] += 1
        
        if review_time_seconds:
            self.hitl_metrics['review_times'].append(review_time_seconds)
        
        if trust_score:
            self.hitl_metrics['trust_scores'].append(trust_score)
        
        return interaction
    
    def get_hitl_metrics(self) -> Dict[str, Any]:
        """Get HITL evaluation metrics."""
        metrics = self.hitl_metrics
        total = metrics['total_escalations']
        
        return {
            'total_escalations': total,
            'acceptance_rate': metrics['accepted_recommendations'] / total if total else 0,
            'override_rate': metrics['overridden_decisions'] / total if total else 0,
            'avg_review_time_seconds': statistics.mean(metrics['review_times']) if metrics['review_times'] else 0,
            'avg_trust_score': statistics.mean(metrics['trust_scores']) if metrics['trust_scores'] else 0
        }
    
    def record_review(self, decision: str, approved: bool,
                     review_time_seconds: float = None) -> Dict[str, Any]:
        """Record a human review decision."""
        return self.record_escalation(
            agent_recommendation=decision,
            human_accepted=approved,
            review_time_seconds=review_time_seconds,
            metadata={'type': 'review'}
        )
    
    def record_override(self, agent_decision: str, human_decision: str,
                       reason: str = None) -> Dict[str, Any]:
        """Record a human override of agent decision."""
        metadata = {'type': 'override', 'human_decision': human_decision}
        if reason:
            metadata['reason'] = reason
        return self.record_escalation(
            agent_recommendation=agent_decision,
            human_accepted=False,
            metadata=metadata
        )
    
    def record_trust_signal(self, interaction_id: str, trust_score: float) -> Dict[str, Any]:
        """Record a trust signal from human feedback."""
        self.hitl_metrics['trust_scores'].append(trust_score)
        return {
            'interaction_id': interaction_id,
            'trust_score': trust_score,
            'timestamp': time.time()
        }


class BusinessOutcomeEvaluator:
    """Business & Outcome Evaluation system."""
    
    def __init__(self):
        self.outcome_metrics: Dict[str, List[float]] = defaultdict(list)
        self.baseline_metrics: Dict[str, float] = {}
    
    def set_baseline(self, metric_name: str, baseline_value: float):
        """Set baseline metric for comparison."""
        self.baseline_metrics[metric_name] = baseline_value
    
    def record_outcome(self, metric_name: str, value: float,
                      _metadata: Dict[str, Any] = None):
        """Record business outcome metric."""
        self.outcome_metrics[metric_name].append(value)
    
    def get_business_impact(self) -> Dict[str, Any]:
        """Get business impact analysis."""
        impact = {}
        
        for metric_name, values in self.outcome_metrics.items():
            if not values:
                continue
            
            current_avg = statistics.mean(values)
            
            metric_impact = {
                'current': current_avg,
                'samples': len(values)
            }
            
            if metric_name in self.baseline_metrics:
                baseline = self.baseline_metrics[metric_name]
                improvement = ((current_avg - baseline) / baseline * 100) if baseline else 0
                metric_impact['baseline'] = baseline
                metric_impact['improvement_pct'] = improvement
            
            impact[metric_name] = metric_impact
        
        return impact
    
    def calculate_roi(self, cost: float, benefit: float,
                     time_period_days: int = 30) -> Dict[str, Any]:
        """Calculate return on investment."""
        roi = ((benefit - cost) / cost * 100) if cost > 0 else 0
        
        return {
            'cost': cost,
            'benefit': benefit,
            'roi_percent': roi,
            'time_period_days': time_period_days,
            'daily_benefit': benefit / time_period_days if time_period_days else 0
        }


__all__ = ['HITLEvaluator', 'BusinessOutcomeEvaluator']
