"""
Prompt Drift Detection system.

Monitors prompt effectiveness over time:
- Quality degradation detection
- Latency and cost tracking
- Behavior and distribution shifts
- Statistical significance testing
"""

import uuid
import time
import logging
import threading
import statistics
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

logger = logging.getLogger(__name__)


class DriftType(Enum):
    """Types of prompt drift."""
    QUALITY_DEGRADATION = "quality_degradation"
    LATENCY_INCREASE = "latency_increase"
    COST_INCREASE = "cost_increase"
    BEHAVIOR_SHIFT = "behavior_shift"
    DISTRIBUTION_SHIFT = "distribution_shift"
    SEMANTIC_DRIFT = "semantic_drift"


class DriftSeverity(Enum):
    """Severity levels for detected drift."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftAlert:
    """Alert for detected drift."""
    alert_id: str
    drift_type: DriftType
    severity: DriftSeverity
    prompt_id: str
    metric_name: str
    baseline_value: float
    current_value: float
    deviation_percent: float
    detected_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptDriftDetector:
    """
    Prompt Drift Detection system.
    
    Features:
    - Rolling window analysis
    - Statistical significance testing
    - Configurable thresholds
    - Alert callbacks
    """
    
    def __init__(self,
                 window_size: int = 100,
                 significance_threshold: float = 0.05,
                 drift_thresholds: Dict[str, float] = None):
        self.window_size = window_size
        self.significance_threshold = significance_threshold
        
        self.drift_thresholds = drift_thresholds or {
            'quality_score': 10.0,
            'latency_ms': 25.0,
            'token_count': 20.0,
            'error_rate': 50.0,
            'hallucination_score': 30.0
        }
        
        self.prompt_baselines: Dict[str, Dict[str, Any]] = {}
        self.prompt_metrics: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.alerts: List[DriftAlert] = []
        self.alert_callbacks: List[Callable[[DriftAlert], None]] = []
        
        self.stats = {
            'total_samples': 0,
            'drift_detections': 0,
            'prompts_monitored': 0
        }
        
        self._lock = threading.Lock()
    
    def establish_baseline(self,
                          prompt_id: str,
                          samples: List[Dict[str, Any]],
                          metadata: Dict[str, Any] = None):
        """Establish baseline metrics for a prompt."""
        if len(samples) < 10:
            logger.warning("Insufficient samples for baseline (minimum 10 required)")
            return
        
        metrics = defaultdict(list)
        for sample in samples:
            for key, value in sample.items():
                if isinstance(value, (int, float)):
                    metrics[key].append(value)
        
        baseline = {
            'prompt_id': prompt_id,
            'established_at': time.time(),
            'sample_count': len(samples),
            'metadata': metadata or {},
            'metrics': {}
        }
        
        for metric_name, values in metrics.items():
            baseline['metrics'][metric_name] = {
                'mean': statistics.mean(values),
                'std': statistics.stdev(values) if len(values) > 1 else 0,
                'min': min(values),
                'max': max(values),
                'median': statistics.median(values)
            }
        
        with self._lock:
            self.prompt_baselines[prompt_id] = baseline
            self.stats['prompts_monitored'] = len(self.prompt_baselines)
        
        logger.info("Established baseline for prompt '%s' with %d samples", 
                   prompt_id, len(samples))
    
    def record_sample(self,
                     prompt_id: str,
                     metrics: Dict[str, float],
                     metadata: Dict[str, Any] = None) -> Optional[List[DriftAlert]]:
        """Record a new sample and check for drift."""
        sample = {
            'timestamp': time.time(),
            'metrics': metrics,
            'metadata': metadata or {}
        }
        
        with self._lock:
            self.prompt_metrics[prompt_id].append(sample)
            self.stats['total_samples'] += 1
            
            if len(self.prompt_metrics[prompt_id]) > self.window_size * 2:
                self.prompt_metrics[prompt_id] = self.prompt_metrics[prompt_id][-self.window_size:]
        
        return self._detect_drift(prompt_id, metrics)
    
    def _detect_drift(self, prompt_id: str, current_metrics: Dict[str, float]) -> List[DriftAlert]:
        """Detect drift by comparing current metrics to baseline."""
        alerts = []
        baseline = self.prompt_baselines.get(prompt_id)
        if not baseline:
            return alerts
        
        for metric_name, current_value in current_metrics.items():
            if metric_name not in baseline['metrics']:
                continue
            
            baseline_stats = baseline['metrics'][metric_name]
            baseline_mean = baseline_stats['mean']
            baseline_std = baseline_stats['std']
            
            if baseline_mean == 0:
                continue
            
            deviation = current_value - baseline_mean
            deviation_percent = abs(deviation / baseline_mean) * 100
            
            drift_type = self._classify_drift(metric_name, deviation)
            threshold = self.drift_thresholds.get(metric_name, 20.0)
            
            if deviation_percent > threshold:
                if baseline_std > 0:
                    z_score = abs(deviation) / baseline_std
                    if z_score < 2:
                        continue
                
                severity = self._calculate_severity(deviation_percent, threshold)
                
                alert = DriftAlert(
                    alert_id=str(uuid.uuid4()),
                    drift_type=drift_type,
                    severity=severity,
                    prompt_id=prompt_id,
                    metric_name=metric_name,
                    baseline_value=baseline_mean,
                    current_value=current_value,
                    deviation_percent=deviation_percent,
                    detected_at=time.time(),
                    metadata={
                        'z_score': abs(deviation) / baseline_std if baseline_std > 0 else 0,
                        'threshold': threshold
                    }
                )
                
                alerts.append(alert)
                
                with self._lock:
                    self.alerts.append(alert)
                    self.stats['drift_detections'] += 1
                
                for callback in self.alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:  # noqa: BLE001
                        logger.error("Drift alert callback failed: %s", e)
                
                logger.warning(
                    "Drift detected for prompt '%s': %s %s deviated %.1f%%",
                    prompt_id, drift_type.value, metric_name, deviation_percent
                )
        
        return alerts
    
    def _classify_drift(self, metric_name: str, deviation: float) -> DriftType:
        """Classify the type of drift."""
        metric_lower = metric_name.lower()
        
        if 'quality' in metric_lower or 'score' in metric_lower:
            return DriftType.QUALITY_DEGRADATION if deviation < 0 else DriftType.BEHAVIOR_SHIFT
        elif 'latency' in metric_lower or 'time' in metric_lower:
            return DriftType.LATENCY_INCREASE
        elif 'token' in metric_lower or 'cost' in metric_lower:
            return DriftType.COST_INCREASE
        elif 'hallucination' in metric_lower or 'error' in metric_lower:
            return DriftType.QUALITY_DEGRADATION
        else:
            return DriftType.BEHAVIOR_SHIFT
    
    def _calculate_severity(self, deviation_percent: float, threshold: float) -> DriftSeverity:
        """Calculate severity based on deviation magnitude."""
        ratio = deviation_percent / threshold
        
        if ratio < 1.5:
            return DriftSeverity.LOW
        elif ratio < 2.5:
            return DriftSeverity.MEDIUM
        elif ratio < 4.0:
            return DriftSeverity.HIGH
        else:
            return DriftSeverity.CRITICAL
    
    def get_drift_report(self, prompt_id: str = None) -> Dict[str, Any]:
        """Generate drift report for one or all prompts."""
        prompts = [prompt_id] if prompt_id else list(self.prompt_baselines.keys())
        
        report = {
            'generated_at': time.time(),
            'total_prompts': len(prompts),
            'prompts': {}
        }
        
        for pid in prompts:
            baseline = self.prompt_baselines.get(pid)
            samples = self.prompt_metrics.get(pid, [])
            prompt_alerts = [a for a in self.alerts if a.prompt_id == pid]
            
            if not baseline:
                continue
            
            recent_samples = samples[-self.window_size:] if samples else []
            current_metrics = defaultdict(list)
            
            for sample in recent_samples:
                for key, value in sample.get('metrics', {}).items():
                    if isinstance(value, (int, float)):
                        current_metrics[key].append(value)
            
            metric_comparison = {}
            for metric_name, values in current_metrics.items():
                if metric_name in baseline['metrics']:
                    baseline_mean = baseline['metrics'][metric_name]['mean']
                    current_mean = statistics.mean(values) if values else 0
                    
                    metric_comparison[metric_name] = {
                        'baseline': baseline_mean,
                        'current': current_mean,
                        'change_percent': ((current_mean - baseline_mean) / baseline_mean * 100) if baseline_mean else 0,
                        'sample_count': len(values)
                    }
            
            report['prompts'][pid] = {
                'baseline_established': baseline['established_at'],
                'total_samples': len(samples),
                'recent_samples': len(recent_samples),
                'total_alerts': len(prompt_alerts),
                'recent_alerts': len([a for a in prompt_alerts if time.time() - a.detected_at < 86400]),
                'metrics': metric_comparison,
                'health_status': self._calculate_health(metric_comparison)
            }
        
        return report
    
    def _calculate_health(self, metric_comparison: Dict[str, Any]) -> str:
        """Calculate overall health status."""
        if not metric_comparison:
            return 'unknown'
        
        max_deviation = 0
        for metric in metric_comparison.values():
            max_deviation = max(max_deviation, abs(metric.get('change_percent', 0)))
        
        if max_deviation < 5:
            return 'healthy'
        elif max_deviation < 15:
            return 'warning'
        elif max_deviation < 30:
            return 'degraded'
        else:
            return 'critical'
    
    def add_alert_callback(self, callback: Callable[[DriftAlert], None]):
        """Add callback for drift alerts."""
        self.alert_callbacks.append(callback)
    
    def get_alerts(self, prompt_id: str = None, severity: DriftSeverity = None,
                   since: float = None) -> List[DriftAlert]:
        """Get drift alerts with optional filtering."""
        alerts = self.alerts.copy()
        
        if prompt_id:
            alerts = [a for a in alerts if a.prompt_id == prompt_id]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if since:
            alerts = [a for a in alerts if a.detected_at >= since]
        
        return alerts
    
    def reset_baseline(self, prompt_id: str):
        """Reset baseline for a prompt using recent samples."""
        samples = self.prompt_metrics.get(prompt_id, [])
        if len(samples) >= 10:
            baseline_samples = [s['metrics'] for s in samples[-self.window_size:]]
            metadata = self.prompt_baselines.get(prompt_id, {}).get('metadata', {})
            self.establish_baseline(prompt_id, baseline_samples, metadata)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get drift detection statistics."""
        return {
            **self.stats,
            'total_alerts': len(self.alerts),
            'alerts_by_severity': {
                s.value: len([a for a in self.alerts if a.severity == s])
                for s in DriftSeverity
            },
            'alerts_by_type': {
                t.value: len([a for a in self.alerts if a.drift_type == t])
                for t in DriftType
            }
        }


# Global instance
prompt_drift_detector = PromptDriftDetector()

__all__ = [
    'DriftType',
    'DriftSeverity', 
    'DriftAlert',
    'PromptDriftDetector',
    'prompt_drift_detector'
]
