"""
Online/Live evaluation system.

Features:
- Real-time quality monitoring
- User feedback integration
- Automatic alerting
- Trend analysis
"""

import uuid
import time
import logging
import threading
import statistics
from typing import Dict, Any, List, Callable
from datetime import datetime

from .types import EvaluationType, EvaluationResult

logger = logging.getLogger(__name__)


class OnlineEvaluator:
    """
    Online/Live evaluation system.
    
    Features:
    - Real-time quality monitoring
    - User feedback integration
    - Automatic alerting
    - Trend analysis
    """
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.evaluations: List[EvaluationResult] = []
        self.scorers: Dict[str, Callable[[Any, Dict[str, Any]], float]] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.alert_thresholds: Dict[str, float] = {}
        self.alert_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        
        self._lock = threading.Lock()
        self._register_default_scorers()
    
    def _register_default_scorers(self):
        """Register default online scorers."""
        self.scorers['response_length'] = lambda output, ctx: min(
            len(str(output)) / 500, 1.0
        )
        self.scorers['latency_score'] = lambda output, ctx: max(
            0, 1 - (ctx.get('latency_ms', 0) / 5000)
        )
    
    def register_scorer(self, name: str, 
                       scorer_fn: Callable[[Any, Dict[str, Any]], float]):
        """Register an online scorer."""
        self.scorers[name] = scorer_fn
    
    def set_alert_threshold(self, scorer_name: str, threshold: float):
        """Set alert threshold for a scorer."""
        self.alert_thresholds[scorer_name] = threshold
    
    def add_alert_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Add callback for alerts."""
        self.alert_callbacks.append(callback)
    
    def record(self, 
               input_data: Any,
               output: Any,
               context: Dict[str, Any] = None,
               user_feedback: float = None) -> EvaluationResult:
        """Record an online evaluation."""
        context = context or {}
        
        scores = {}
        for scorer_name, scorer_fn in self.scorers.items():
            try:
                scores[scorer_name] = scorer_fn(output, context)
            except Exception as e:  # noqa: BLE001
                scores[scorer_name] = 0.0
                logger.warning("Online scorer %s failed: %s", scorer_name, e)
        
        if user_feedback is not None:
            scores['user_feedback'] = user_feedback
        
        result = EvaluationResult(
            evaluation_id=str(uuid.uuid4()),
            evaluation_type=EvaluationType.ONLINE,
            input_data=input_data,
            expected_output=None,
            actual_output=output,
            scores=scores,
            metadata=context,
            timestamp=time.time(),
            latency_ms=context.get('latency_ms', 0)
        )
        
        with self._lock:
            self.evaluations.append(result)
            if len(self.evaluations) > self.window_size:
                self.evaluations.pop(0)
        
        self._check_alerts(scores)
        return result
    
    def _check_alerts(self, scores: Dict[str, float]):
        """Check if any scores trigger alerts."""
        for scorer_name, threshold in self.alert_thresholds.items():
            if scorer_name in scores and scores[scorer_name] < threshold:
                alert = {
                    'id': str(uuid.uuid4()),
                    'scorer': scorer_name,
                    'value': scores[scorer_name],
                    'threshold': threshold,
                    'timestamp': time.time()
                }
                
                self.alerts.append(alert)
                logger.warning("Alert triggered: %s = %.2f < %.2f",
                             scorer_name, scores[scorer_name], threshold)
                
                for callback in self.alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:  # noqa: BLE001
                        logger.error("Alert callback failed: %s", e)
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Get current online metrics."""
        with self._lock:
            if not self.evaluations:
                return {'error': 'No data'}
            
            metrics = {}
            for scorer_name in self.scorers.keys():
                scores = [e.scores.get(scorer_name, 0) for e in self.evaluations]
                metrics[scorer_name] = {
                    'current': scores[-1] if scores else 0,
                    'mean': statistics.mean(scores),
                    'min': min(scores),
                    'max': max(scores),
                    'trend': self._calculate_trend(scores)
                }
            
            return {
                'metrics': metrics,
                'sample_count': len(self.evaluations),
                'alert_count': len(self.alerts),
                'timestamp': datetime.now().isoformat()
            }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction."""
        if len(values) < 10:
            return "insufficient_data"
        
        recent = statistics.mean(values[-10:])
        older = statistics.mean(values[-20:-10]) if len(values) >= 20 else statistics.mean(values[:-10])
        
        diff = recent - older
        if diff > 0.05:
            return "improving"
        elif diff < -0.05:
            return "degrading"
        return "stable"
    
    def get_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        return self.alerts[-limit:]


__all__ = ['OnlineEvaluator']
