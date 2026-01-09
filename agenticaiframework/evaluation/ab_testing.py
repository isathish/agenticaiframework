"""
A/B Testing framework.

Features:
- Experiment management
- Traffic splitting
- Statistical significance testing
- Canary analysis
- Automatic rollback triggers
"""

import uuid
import time
import logging
import hashlib
import random
import statistics
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


class ABTestingFramework:
    """
    A/B Testing framework.
    
    Features:
    - Experiment management
    - Traffic splitting
    - Statistical significance testing
    - Canary analysis
    - Automatic rollback triggers
    """
    
    def __init__(self):
        self.experiments: Dict[str, Dict[str, Any]] = {}
        self.experiment_results: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.active_canaries: Dict[str, Dict[str, Any]] = {}
    
    def create_experiment(self,
                         name: str,
                         variants: List[str],
                         traffic_split: Dict[str, float] = None,
                         metrics: List[str] = None) -> Dict[str, Any]:
        """Create an A/B test experiment."""
        if traffic_split is None:
            split = 1.0 / len(variants)
            traffic_split = {v: split for v in variants}
        
        experiment = {
            'id': str(uuid.uuid4()),
            'name': name,
            'variants': variants,
            'traffic_split': traffic_split,
            'metrics': metrics or ['conversion', 'latency', 'quality'],
            'status': 'active',
            'created_at': time.time(),
            'sample_counts': {v: 0 for v in variants}
        }
        
        self.experiments[name] = experiment
        logger.info("Created experiment '%s' with variants: %s", name, variants)
        return experiment
    
    def get_variant(self, experiment_name: str, user_id: str = None) -> str:
        """Get variant assignment for a user using consistent hashing."""
        experiment = self.experiments.get(experiment_name)
        if not experiment or experiment['status'] != 'active':
            return experiment['variants'][0] if experiment else None
        
        if user_id:
            hash_input = f"{experiment_name}:{user_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            bucket = (hash_value % 1000) / 1000
        else:
            bucket = random.random()
        
        cumulative = 0
        for variant, split in experiment['traffic_split'].items():
            cumulative += split
            if bucket < cumulative:
                experiment['sample_counts'][variant] += 1
                return variant
        
        return experiment['variants'][-1]
    
    def record_result(self,
                     experiment_name: str,
                     variant: str,
                     metrics: Dict[str, float],
                     user_id: str = None):
        """Record experiment result."""
        result = {
            'id': str(uuid.uuid4()),
            'variant': variant,
            'metrics': metrics,
            'user_id': user_id,
            'timestamp': time.time()
        }
        self.experiment_results[experiment_name].append(result)
    
    def analyze_experiment(self, experiment_name: str) -> Dict[str, Any]:
        """Analyze experiment results with statistical analysis."""
        experiment = self.experiments.get(experiment_name)
        results = self.experiment_results.get(experiment_name, [])
        
        if not experiment or not results:
            return {'error': 'No data'}
        
        by_variant = defaultdict(lambda: defaultdict(list))
        for result in results:
            variant = result['variant']
            for metric, value in result['metrics'].items():
                by_variant[variant][metric].append(value)
        
        analysis = {
            'experiment': experiment_name,
            'total_samples': len(results),
            'variants': {},
            'statistical_tests': {}
        }
        
        for variant, metrics in by_variant.items():
            analysis['variants'][variant] = {}
            for metric, values in metrics.items():
                analysis['variants'][variant][metric] = {
                    'count': len(values),
                    'mean': statistics.mean(values),
                    'stdev': statistics.stdev(values) if len(values) > 1 else 0
                }
        
        variants = list(by_variant.keys())
        if len(variants) >= 2:
            control = variants[0]
            for treatment in variants[1:]:
                for metric in experiment['metrics']:
                    if metric in by_variant[control] and metric in by_variant[treatment]:
                        control_vals = by_variant[control][metric]
                        treatment_vals = by_variant[treatment][metric]
                        
                        if len(control_vals) >= 30 and len(treatment_vals) >= 30:
                            significance = self._calculate_significance(
                                control_vals, treatment_vals
                            )
                            analysis['statistical_tests'][f"{control}_vs_{treatment}_{metric}"] = significance
        
        return analysis
    
    def _calculate_significance(self, 
                               control: List[float], 
                               treatment: List[float]) -> Dict[str, Any]:
        """Calculate statistical significance."""
        control_mean = statistics.mean(control)
        treatment_mean = statistics.mean(treatment)
        control_std = statistics.stdev(control)
        treatment_std = statistics.stdev(treatment)
        
        se = ((control_std**2 / len(control)) + (treatment_std**2 / len(treatment))) ** 0.5
        
        if se == 0:
            return {'error': 'Zero standard error'}
        
        z = (treatment_mean - control_mean) / se
        p_value = 2 * (1 - min(0.9999, abs(z) / 4))
        
        return {
            'control_mean': control_mean,
            'treatment_mean': treatment_mean,
            'lift': ((treatment_mean - control_mean) / control_mean * 100) if control_mean else 0,
            'z_score': z,
            'p_value': p_value,
            'significant': p_value < 0.05
        }
    
    def start_canary(self,
                    name: str,
                    baseline_version: str,
                    canary_version: str,
                    initial_traffic: float = 0.05,
                    success_threshold: float = 0.95) -> Dict[str, Any]:
        """Start a canary deployment."""
        canary = {
            'id': str(uuid.uuid4()),
            'name': name,
            'baseline_version': baseline_version,
            'canary_version': canary_version,
            'traffic': initial_traffic,
            'success_threshold': success_threshold,
            'status': 'active',
            'started_at': time.time(),
            'metrics': {
                'baseline': {'success': 0, 'failure': 0},
                'canary': {'success': 0, 'failure': 0}
            }
        }
        
        self.active_canaries[name] = canary
        logger.info("Started canary '%s': %s -> %s at %.1f%% traffic",
                   name, baseline_version, canary_version, initial_traffic * 100)
        return canary
    
    def record_canary_result(self,
                            canary_name: str,
                            is_canary: bool,
                            success: bool):
        """Record canary result."""
        canary = self.active_canaries.get(canary_name)
        if not canary:
            return
        
        version = 'canary' if is_canary else 'baseline'
        result = 'success' if success else 'failure'
        canary['metrics'][version][result] += 1
        self._check_canary_health(canary_name)
    
    def _check_canary_health(self, canary_name: str):
        """Check canary health and trigger rollback if needed."""
        canary = self.active_canaries.get(canary_name)
        if not canary or canary['status'] != 'active':
            return
        
        metrics = canary['metrics']['canary']
        total = metrics['success'] + metrics['failure']
        
        if total < 100:
            return
        
        success_rate = metrics['success'] / total
        if success_rate < canary['success_threshold']:
            canary['status'] = 'rolled_back'
            logger.warning("Canary '%s' rolled back: %.1f%% success < %.1f%% threshold",
                         canary_name, success_rate * 100, canary['success_threshold'] * 100)
    
    def promote_canary(self, canary_name: str):
        """Promote canary to full traffic."""
        canary = self.active_canaries.get(canary_name)
        if canary:
            canary['status'] = 'promoted'
            canary['traffic'] = 1.0
            logger.info("Canary '%s' promoted to 100%% traffic", canary_name)
    
    def get_canary_status(self, canary_name: str) -> Dict[str, Any]:
        """Get canary status and metrics."""
        canary = self.active_canaries.get(canary_name)
        if not canary:
            return {'error': 'Canary not found'}
        
        baseline_total = canary['metrics']['baseline']['success'] + canary['metrics']['baseline']['failure']
        canary_total = canary['metrics']['canary']['success'] + canary['metrics']['canary']['failure']
        
        return {
            **canary,
            'baseline_success_rate': canary['metrics']['baseline']['success'] / baseline_total if baseline_total else 0,
            'canary_success_rate': canary['metrics']['canary']['success'] / canary_total if canary_total else 0
        }


__all__ = ['ABTestingFramework']
