"""
Latency Metrics.

Comprehensive latency metrics collection and analysis:
- Histogram-based latency tracking
- Percentile calculations (p50, p90, p95, p99)
- SLA monitoring
- Anomaly detection
- Time-window aggregations
"""

import time
import logging
import threading
import statistics
from typing import Dict, Any, List, Optional
from collections import defaultdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class LatencyMetrics:
    """
    Comprehensive latency metrics collection and analysis.
    
    Features:
    - Histogram-based latency tracking
    - Percentile calculations (p50, p90, p95, p99)
    - SLA monitoring
    - Anomaly detection
    - Time-window aggregations
    """
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.timestamps: Dict[str, List[float]] = defaultdict(list)
        self.sla_thresholds: Dict[str, float] = {}
        self.sla_violations: Dict[str, int] = defaultdict(int)
        
        self.total_counts: Dict[str, int] = defaultdict(int)
        self.total_sums: Dict[str, float] = defaultdict(float)
        
        self._lock = threading.Lock()
    
    def record(self, metric_name: str, latency_ms: float):
        """Record a latency measurement."""
        with self._lock:
            self.metrics[metric_name].append(latency_ms)
            self.timestamps[metric_name].append(time.time())
            self.total_counts[metric_name] += 1
            self.total_sums[metric_name] += latency_ms
            
            if len(self.metrics[metric_name]) > self.window_size:
                self.metrics[metric_name].pop(0)
                self.timestamps[metric_name].pop(0)
            
            if metric_name in self.sla_thresholds:
                if latency_ms > self.sla_thresholds[metric_name]:
                    self.sla_violations[metric_name] += 1
                    logger.warning(
                        "SLA violation for %s: %.2fms > %.2fms threshold",
                        metric_name, latency_ms, self.sla_thresholds[metric_name]
                    )
    
    @contextmanager
    def measure(self, metric_name: str):
        """Context manager to measure latency."""
        start = time.time()
        try:
            yield
        finally:
            latency_ms = (time.time() - start) * 1000
            self.record(metric_name, latency_ms)
    
    def set_sla_threshold(self, metric_name: str, threshold_ms: float):
        """Set SLA threshold for a metric."""
        self.sla_thresholds[metric_name] = threshold_ms
    
    def get_percentile(self, metric_name: str, percentile: float) -> Optional[float]:
        """Get percentile value for a metric."""
        values = self.metrics.get(metric_name, [])
        if not values:
            return None
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_stats(self, metric_name: str) -> Dict[str, Any]:
        """Get comprehensive stats for a metric."""
        values = self.metrics.get(metric_name, [])
        if not values:
            return {'error': 'No data'}
        
        return {
            'count': len(values),
            'total_count': self.total_counts[metric_name],
            'min': min(values),
            'max': max(values),
            'mean': statistics.mean(values),
            'median': statistics.median(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0,
            'p50': self.get_percentile(metric_name, 50),
            'p90': self.get_percentile(metric_name, 90),
            'p95': self.get_percentile(metric_name, 95),
            'p99': self.get_percentile(metric_name, 99),
            'sla_threshold': self.sla_thresholds.get(metric_name),
            'sla_violations': self.sla_violations.get(metric_name, 0),
            'sla_compliance_rate': self._calculate_sla_compliance(metric_name)
        }
    
    def _calculate_sla_compliance(self, metric_name: str) -> Optional[float]:
        """Calculate SLA compliance rate."""
        if metric_name not in self.sla_thresholds:
            return None
        
        total = self.total_counts[metric_name]
        if total == 0:
            return 100.0
        
        violations = self.sla_violations.get(metric_name, 0)
        return ((total - violations) / total) * 100
    
    def get_time_series(self, metric_name: str, 
                        bucket_seconds: int = 60) -> List[Dict[str, Any]]:
        """Get time-series data with bucketed aggregations."""
        values = self.metrics.get(metric_name, [])
        timestamps = self.timestamps.get(metric_name, [])
        
        if not values:
            return []
        
        buckets: Dict[int, List[float]] = defaultdict(list)
        for ts, val in zip(timestamps, values):
            bucket = int(ts // bucket_seconds) * bucket_seconds
            buckets[bucket].append(val)
        
        result = []
        for bucket_ts in sorted(buckets.keys()):
            bucket_values = buckets[bucket_ts]
            result.append({
                'timestamp': bucket_ts,
                'count': len(bucket_values),
                'mean': statistics.mean(bucket_values),
                'min': min(bucket_values),
                'max': max(bucket_values),
                'p95': sorted(bucket_values)[int(len(bucket_values) * 0.95)] if bucket_values else 0
            })
        
        return result
    
    def detect_anomalies(self, metric_name: str, 
                         z_threshold: float = 3.0) -> List[Dict[str, Any]]:
        """Detect latency anomalies using z-score."""
        values = self.metrics.get(metric_name, [])
        timestamps = self.timestamps.get(metric_name, [])
        
        if len(values) < 10:
            return []
        
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        
        if stdev == 0:
            return []
        
        anomalies = []
        for i, (val, ts) in enumerate(zip(values, timestamps)):
            z_score = abs(val - mean) / stdev
            if z_score > z_threshold:
                anomalies.append({
                    'index': i,
                    'timestamp': ts,
                    'value': val,
                    'z_score': z_score,
                    'mean': mean,
                    'stdev': stdev
                })
        
        return anomalies
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all metrics."""
        return {name: self.get_stats(name) for name in self.metrics.keys()}
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for metric_name, values in self.metrics.items():
            if not values:
                continue
            
            safe_name = metric_name.replace('.', '_').replace('-', '_')
            
            buckets = [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
            for bucket in buckets:
                count = sum(1 for v in values if v <= bucket)
                lines.append(f'{safe_name}_bucket{{le="{bucket}"}} {count}')
            
            lines.append(f'{safe_name}_bucket{{le="+Inf"}} {len(values)}')
            lines.append(f'{safe_name}_sum {sum(values)}')
            lines.append(f'{safe_name}_count {len(values)}')
        
        return '\n'.join(lines)


__all__ = ['LatencyMetrics']
