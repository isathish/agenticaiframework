"""
Offline evaluation system for batch testing.

Features:
- Test dataset management
- Batch evaluation
- Golden set comparison
- Regression detection
- Report generation
"""

import uuid
import time
import logging
import json
import statistics
from typing import Dict, Any, List, Callable
from datetime import datetime

from .types import EvaluationType, EvaluationResult

logger = logging.getLogger(__name__)


class OfflineEvaluator:
    """
    Offline evaluation system for batch testing.
    
    Features:
    - Test dataset management
    - Batch evaluation
    - Golden set comparison
    - Regression detection
    - Report generation
    """
    
    def __init__(self):
        self.test_datasets: Dict[str, List[Dict[str, Any]]] = {}
        self.evaluation_runs: Dict[str, List[EvaluationResult]] = {}
        self.scorers: Dict[str, Callable[[Any, Any], float]] = {}
        self.baseline_results: Dict[str, Dict[str, float]] = {}
        
        self._register_default_scorers()
    
    def _register_default_scorers(self):
        """Register default scoring functions."""
        self.scorers['exact_match'] = lambda expected, actual: 1.0 if expected == actual else 0.0
        self.scorers['contains'] = lambda expected, actual: 1.0 if str(expected) in str(actual) else 0.0
        self.scorers['length_ratio'] = lambda expected, actual: min(
            len(str(actual)) / len(str(expected)), 1.0
        ) if expected else 0.0
    
    def register_scorer(self, name: str, scorer_fn: Callable[[Any, Any], float]):
        """Register a custom scorer."""
        self.scorers[name] = scorer_fn
        logger.info("Registered scorer: %s", name)
    
    def add_test_dataset(self, name: str, dataset: List[Dict[str, Any]]):
        """Add a test dataset."""
        self.test_datasets[name] = dataset
        logger.info("Added test dataset '%s' with %d items", name, len(dataset))
    
    def load_test_dataset_from_file(self, name: str, filepath: str):
        """Load test dataset from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            dataset = json.load(f)
        self.add_test_dataset(name, dataset)
    
    def evaluate(self, 
                 dataset_name: str,
                 agent_fn: Callable[[Any], Any],
                 scorers: List[str] = None,
                 run_id: str = None) -> Dict[str, Any]:
        """Run offline evaluation on a dataset."""
        dataset = self.test_datasets.get(dataset_name)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_name}' not found")
        
        run_id = run_id or str(uuid.uuid4())
        scorers = scorers or list(self.scorers.keys())
        
        results = []
        logger.info("Starting evaluation run %s on dataset '%s'", run_id, dataset_name)
        
        for i, item in enumerate(dataset):
            input_data = item.get('input')
            expected_output = item.get('expected_output')
            metadata = item.get('metadata', {})
            
            start_time = time.time()
            try:
                actual_output = agent_fn(input_data)
                status = 'success'
            except Exception as e:  # noqa: BLE001
                actual_output = None
                status = 'error'
                metadata['error'] = str(e)
            
            latency_ms = (time.time() - start_time) * 1000
            
            scores = {}
            for scorer_name in scorers:
                if scorer_name in self.scorers:
                    try:
                        scores[scorer_name] = self.scorers[scorer_name](
                            expected_output, actual_output
                        )
                    except Exception as e:  # noqa: BLE001
                        scores[scorer_name] = 0.0
                        logger.warning("Scorer %s failed: %s", scorer_name, e)
            
            result = EvaluationResult(
                evaluation_id=f"{run_id}_{i}",
                evaluation_type=EvaluationType.OFFLINE,
                input_data=input_data,
                expected_output=expected_output,
                actual_output=actual_output,
                scores=scores,
                metadata={**metadata, 'status': status, 'index': i},
                timestamp=time.time(),
                latency_ms=latency_ms
            )
            results.append(result)
        
        self.evaluation_runs[run_id] = results
        summary = self._generate_summary(results, dataset_name, run_id)
        
        if dataset_name in self.baseline_results:
            summary['regression'] = self._check_regression(
                summary['aggregate_scores'],
                self.baseline_results[dataset_name]
            )
        
        logger.info("Completed evaluation run %s: %d/%d passed", 
                   run_id, summary['passed_count'], summary['total_count'])
        return summary
    
    def _generate_summary(self, results: List[EvaluationResult], 
                         dataset_name: str, run_id: str) -> Dict[str, Any]:
        """Generate evaluation summary."""
        if not results:
            return {'error': 'No results'}
        
        passed_count = sum(1 for r in results if r.passed)
        
        aggregate_scores = {}
        for scorer_name in results[0].scores.keys():
            scores = [r.scores.get(scorer_name, 0) for r in results]
            aggregate_scores[scorer_name] = {
                'mean': statistics.mean(scores),
                'min': min(scores),
                'max': max(scores),
                'stdev': statistics.stdev(scores) if len(scores) > 1 else 0
            }
        
        latencies = [r.latency_ms for r in results]
        
        return {
            'run_id': run_id,
            'dataset_name': dataset_name,
            'total_count': len(results),
            'passed_count': passed_count,
            'pass_rate': passed_count / len(results),
            'aggregate_scores': aggregate_scores,
            'latency': {
                'mean': statistics.mean(latencies),
                'p50': sorted(latencies)[len(latencies) // 2],
                'p95': sorted(latencies)[int(len(latencies) * 0.95)],
                'p99': sorted(latencies)[int(len(latencies) * 0.99)]
            },
            'timestamp': datetime.now().isoformat()
        }
    
    def _check_regression(self, current_scores: Dict[str, Dict[str, float]],
                         baseline_scores: Dict[str, float]) -> Dict[str, Any]:
        """Check for regression against baseline."""
        regressions = []
        
        for scorer_name, stats in current_scores.items():
            if scorer_name in baseline_scores:
                baseline = baseline_scores[scorer_name]
                current = stats['mean']
                diff = current - baseline
                
                if diff < -0.05:
                    regressions.append({
                        'scorer': scorer_name,
                        'baseline': baseline,
                        'current': current,
                        'diff': diff,
                        'percent_change': (diff / baseline) * 100 if baseline else 0
                    })
        
        return {
            'has_regression': len(regressions) > 0,
            'regressions': regressions
        }
    
    def set_baseline(self, dataset_name: str, run_id: str):
        """Set baseline from an evaluation run."""
        results = self.evaluation_runs.get(run_id)
        if not results:
            raise ValueError(f"Run '{run_id}' not found")
        
        baseline = {}
        for scorer_name in results[0].scores.keys():
            scores = [r.scores.get(scorer_name, 0) for r in results]
            baseline[scorer_name] = statistics.mean(scores)
        
        self.baseline_results[dataset_name] = baseline
        logger.info("Set baseline for dataset '%s' from run %s", dataset_name, run_id)
    
    def get_run_details(self, run_id: str) -> List[Dict[str, Any]]:
        """Get detailed results for a run."""
        results = self.evaluation_runs.get(run_id, [])
        return [r.to_dict() for r in results]
    
    def export_results(self, run_id: str, filepath: str):
        """Export results to JSON file."""
        results = self.get_run_details(run_id)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)


__all__ = ['OfflineEvaluator']
