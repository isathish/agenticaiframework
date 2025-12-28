"""
Comprehensive Evaluation module for AI agents.

Provides:
- Offline Evaluation (batch testing)
- Online/Live Evaluation (real-time monitoring)
- Cost vs Quality Scoring
- Security Risk Scoring
- A/B Testing framework
"""

import uuid
import time
import logging
import threading
import hashlib
import statistics
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
import json
import random

logger = logging.getLogger(__name__)


class EvaluationType(Enum):
    """Types of evaluation."""
    OFFLINE = "offline"
    ONLINE = "online"
    SHADOW = "shadow"
    CANARY = "canary"


@dataclass
class EvaluationResult:
    """Result of an evaluation."""
    evaluation_id: str
    evaluation_type: EvaluationType
    input_data: Any
    expected_output: Any
    actual_output: Any
    scores: Dict[str, float]
    metadata: Dict[str, Any]
    timestamp: float
    latency_ms: float
    
    @property
    def passed(self) -> bool:
        """Check if evaluation passed all criteria."""
        return all(score >= 0.5 for score in self.scores.values())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'evaluation_id': self.evaluation_id,
            'evaluation_type': self.evaluation_type.value,
            'scores': self.scores,
            'passed': self.passed,
            'metadata': self.metadata,
            'timestamp': self.timestamp,
            'latency_ms': self.latency_ms
        }


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
        
        # Register default scorers
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
        """
        Add a test dataset.
        
        Each item should have:
        - input: Input data
        - expected_output: Expected output
        - metadata: Optional metadata
        """
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
        """
        Run offline evaluation on a dataset.
        
        Args:
            dataset_name: Name of test dataset
            agent_fn: Agent function to evaluate
            scorers: List of scorers to use
            run_id: Optional run identifier
            
        Returns:
            Evaluation summary
        """
        dataset = self.test_datasets.get(dataset_name)
        if not dataset:
            raise ValueError(f"Dataset '{dataset_name}' not found")
        
        run_id = run_id or str(uuid.uuid4())
        scorers = scorers or list(self.scorers.keys())
        
        results = []
        total_latency = 0
        
        logger.info("Starting evaluation run %s on dataset '%s'", run_id, dataset_name)
        
        for i, item in enumerate(dataset):
            input_data = item.get('input')
            expected_output = item.get('expected_output')
            metadata = item.get('metadata', {})
            
            # Run agent
            start_time = time.time()
            try:
                actual_output = agent_fn(input_data)
                status = 'success'
            except Exception as e:
                actual_output = None
                status = 'error'
                metadata['error'] = str(e)
            
            latency_ms = (time.time() - start_time) * 1000
            total_latency += latency_ms
            
            # Calculate scores
            scores = {}
            for scorer_name in scorers:
                if scorer_name in self.scorers:
                    try:
                        scores[scorer_name] = self.scorers[scorer_name](
                            expected_output, actual_output
                        )
                    except Exception as e:
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
        
        # Generate summary
        summary = self._generate_summary(results, dataset_name, run_id)
        
        # Check for regression
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
        
        # Aggregate scores
        aggregate_scores = {}
        for scorer_name in results[0].scores.keys():
            scores = [r.scores.get(scorer_name, 0) for r in results]
            aggregate_scores[scorer_name] = {
                'mean': statistics.mean(scores),
                'min': min(scores),
                'max': max(scores),
                'stdev': statistics.stdev(scores) if len(scores) > 1 else 0
            }
        
        # Latency stats
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
                
                if diff < -0.05:  # 5% regression threshold
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
        
        # Register default scorers
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
        """
        Record an online evaluation.
        
        Args:
            input_data: Input to agent
            output: Agent output
            context: Execution context (latency, tokens, etc.)
            user_feedback: Optional user feedback score (0-1)
        """
        context = context or {}
        
        # Calculate scores
        scores = {}
        for scorer_name, scorer_fn in self.scorers.items():
            try:
                scores[scorer_name] = scorer_fn(output, context)
            except Exception as e:
                scores[scorer_name] = 0.0
                logger.warning("Online scorer %s failed: %s", scorer_name, e)
        
        # Add user feedback if provided
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
            
            # Maintain window size
            if len(self.evaluations) > self.window_size:
                self.evaluations.pop(0)
        
        # Check alerts
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
                    except Exception as e:
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
        self.model_costs: Dict[str, Dict[str, float]] = {}
        self.executions: List[Dict[str, Any]] = []
        self.budgets: Dict[str, float] = {}
        self.budget_alerts: List[Dict[str, Any]] = []
        
        # Default model costs (per 1K tokens)
        self.model_costs = {
            'gpt-4': {'input': 0.03, 'output': 0.06},
            'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
            'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
            'claude-3-opus': {'input': 0.015, 'output': 0.075},
            'claude-3-sonnet': {'input': 0.003, 'output': 0.015},
            'claude-3-haiku': {'input': 0.00025, 'output': 0.00125}
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
        """
        Record an execution with cost and quality.
        
        Returns:
            Execution record with cost analysis
        """
        costs = self.model_costs.get(model_name, {'input': 0, 'output': 0})
        
        input_cost = (input_tokens / 1000) * costs['input']
        output_cost = (output_tokens / 1000) * costs['output']
        total_cost = input_cost + output_cost
        
        # Quality-adjusted metrics
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
        
        # Check budget
        if budget_name and budget_name in self.budgets:
            self._check_budget(budget_name, total_cost)
        
        return execution
    
    def _check_budget(self, budget_name: str, cost: float):
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
        
        # Calculate averages
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
        
        # Analyze by model
        model_stats = defaultdict(lambda: {'costs': [], 'qualities': []})
        for e in self.executions:
            model_stats[e['model']]['costs'].append(e['total_cost'])
            model_stats[e['model']]['qualities'].append(e['quality_score'])
        
        # Find cost-efficient models
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


class SecurityRiskScorer:
    """
    Security risk scoring system.
    
    Features:
    - Input risk assessment
    - Output risk assessment
    - PII detection
    - Injection attempt detection
    - Risk trend monitoring
    """
    
    def __init__(self):
        self.risk_scores: List[Dict[str, Any]] = []
        self.risk_rules: Dict[str, Callable[[str], float]] = {}
        self.pii_patterns: List[Tuple[str, str]] = []
        self.high_risk_threshold: float = 0.7
        self.alerts: List[Dict[str, Any]] = []
        
        self._setup_default_rules()
        self._setup_pii_patterns()
    
    def _setup_default_rules(self):
        """Setup default risk detection rules."""
        import re
        
        # Injection patterns
        injection_patterns = [
            r'ignore\s+(previous|all|above)\s+(instructions|prompts)',
            r'disregard\s+(previous|all|above)',
            r'system\s*:',
            r'<\|im_start\|',
            r'jailbreak',
            r'bypass\s+(security|filter|safety)'
        ]
        
        def injection_risk(text: str) -> float:
            text_lower = text.lower()
            matches = sum(1 for p in injection_patterns if re.search(p, text_lower))
            return min(matches * 0.3, 1.0)
        
        self.risk_rules['injection'] = injection_risk
        
        # Code execution risk
        code_patterns = [r'exec\(', r'eval\(', r'__import__', r'subprocess', r'os\.system']
        
        def code_risk(text: str) -> float:
            matches = sum(1 for p in code_patterns if re.search(p, text))
            return min(matches * 0.4, 1.0)
        
        self.risk_rules['code_execution'] = code_risk
        
        # Data exfiltration risk
        exfil_patterns = [r'send\s+to', r'upload', r'post\s+to', r'webhook']
        
        def exfil_risk(text: str) -> float:
            text_lower = text.lower()
            matches = sum(1 for p in exfil_patterns if re.search(p, text_lower))
            return min(matches * 0.25, 1.0)
        
        self.risk_rules['data_exfiltration'] = exfil_risk
    
    def _setup_pii_patterns(self):
        """Setup PII detection patterns."""
        self.pii_patterns = [
            (r'\b\d{3}-\d{2}-\d{4}\b', 'ssn'),
            (r'\b\d{16}\b', 'credit_card'),
            (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'email'),
            (r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b', 'phone'),
            (r'\b\d{5}(?:-\d{4})?\b', 'zipcode'),
        ]
    
    def add_risk_rule(self, name: str, rule_fn: Callable[[str], float]):
        """Add a custom risk rule."""
        self.risk_rules[name] = rule_fn
    
    def assess_risk(self, 
                   input_text: str = None,
                   output_text: str = None,
                   context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Assess security risk for input/output.
        
        Returns:
            Risk assessment with scores and details
        """
        import re
        
        assessment = {
            'id': str(uuid.uuid4()),
            'timestamp': time.time(),
            'input_risks': {},
            'output_risks': {},
            'pii_detected': [],
            'overall_risk': 0.0,
            'risk_level': 'low'
        }
        
        # Assess input
        if input_text:
            for rule_name, rule_fn in self.risk_rules.items():
                try:
                    score = rule_fn(input_text)
                    assessment['input_risks'][rule_name] = score
                except Exception as e:
                    logger.warning("Risk rule %s failed: %s", rule_name, e)
        
        # Assess output
        if output_text:
            for rule_name, rule_fn in self.risk_rules.items():
                try:
                    score = rule_fn(output_text)
                    assessment['output_risks'][rule_name] = score
                except Exception as e:
                    logger.warning("Risk rule %s failed: %s", rule_name, e)
            
            # PII detection in output
            for pattern, pii_type in self.pii_patterns:
                if re.search(pattern, output_text):
                    assessment['pii_detected'].append(pii_type)
        
        # Calculate overall risk
        all_scores = list(assessment['input_risks'].values()) + \
                     list(assessment['output_risks'].values())
        
        if assessment['pii_detected']:
            all_scores.append(0.8)  # PII presence is high risk
        
        if all_scores:
            assessment['overall_risk'] = max(all_scores)
        
        # Determine risk level
        if assessment['overall_risk'] >= 0.8:
            assessment['risk_level'] = 'critical'
        elif assessment['overall_risk'] >= 0.6:
            assessment['risk_level'] = 'high'
        elif assessment['overall_risk'] >= 0.3:
            assessment['risk_level'] = 'medium'
        else:
            assessment['risk_level'] = 'low'
        
        self.risk_scores.append(assessment)
        
        # Alert on high risk
        if assessment['overall_risk'] >= self.high_risk_threshold:
            self._raise_alert(assessment)
        
        return assessment
    
    def _raise_alert(self, assessment: Dict[str, Any]):
        """Raise a security alert."""
        alert = {
            'id': str(uuid.uuid4()),
            'assessment_id': assessment['id'],
            'risk_level': assessment['risk_level'],
            'overall_risk': assessment['overall_risk'],
            'pii_detected': assessment['pii_detected'],
            'timestamp': time.time()
        }
        
        self.alerts.append(alert)
        logger.warning("Security alert: %s risk (%.2f)", 
                      assessment['risk_level'], assessment['overall_risk'])
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get risk summary."""
        if not self.risk_scores:
            return {'error': 'No data'}
        
        risk_levels = defaultdict(int)
        pii_counts = defaultdict(int)
        
        for score in self.risk_scores:
            risk_levels[score['risk_level']] += 1
            for pii_type in score.get('pii_detected', []):
                pii_counts[pii_type] += 1
        
        return {
            'total_assessments': len(self.risk_scores),
            'risk_distribution': dict(risk_levels),
            'pii_detections': dict(pii_counts),
            'alert_count': len(self.alerts),
            'avg_risk': statistics.mean(s['overall_risk'] for s in self.risk_scores)
        }
    
    def get_alerts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent security alerts."""
        return self.alerts[-limit:]


class ABTestingFramework:
    """
    A/B Testing and Canary deployment framework.
    
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
        """
        Create an A/B test experiment.
        
        Args:
            name: Experiment name
            variants: List of variant names (e.g., ['control', 'treatment'])
            traffic_split: Traffic allocation per variant
            metrics: Metrics to track
        """
        if traffic_split is None:
            # Equal split
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
        """
        Get variant assignment for a user.
        
        Uses consistent hashing for deterministic assignment.
        """
        experiment = self.experiments.get(experiment_name)
        if not experiment or experiment['status'] != 'active':
            return experiment['variants'][0] if experiment else None
        
        # Consistent hashing
        if user_id:
            hash_input = f"{experiment_name}:{user_id}"
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            bucket = (hash_value % 1000) / 1000
        else:
            bucket = random.random()
        
        # Assign based on traffic split
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
        """
        Analyze experiment results.
        
        Returns statistical analysis including significance.
        """
        experiment = self.experiments.get(experiment_name)
        results = self.experiment_results.get(experiment_name, [])
        
        if not experiment or not results:
            return {'error': 'No data'}
        
        # Group by variant
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
        
        # Statistical significance (simplified t-test approximation)
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
        
        # Pooled standard error
        se = ((control_std**2 / len(control)) + (treatment_std**2 / len(treatment))) ** 0.5
        
        if se == 0:
            return {'error': 'Zero standard error'}
        
        # Z-score
        z = (treatment_mean - control_mean) / se
        
        # Simplified p-value approximation
        p_value = 2 * (1 - min(0.9999, abs(z) / 4))  # Rough approximation
        
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
        """
        Start a canary deployment.
        
        Args:
            name: Canary name
            baseline_version: Current production version
            canary_version: New version to test
            initial_traffic: Initial traffic percentage for canary
            success_threshold: Required success rate to proceed
        """
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
        
        # Check for automatic rollback
        self._check_canary_health(canary_name)
    
    def _check_canary_health(self, canary_name: str):
        """Check canary health and trigger rollback if needed."""
        canary = self.active_canaries.get(canary_name)
        if not canary or canary['status'] != 'active':
            return
        
        metrics = canary['metrics']['canary']
        total = metrics['success'] + metrics['failure']
        
        if total < 100:
            return  # Not enough data
        
        success_rate = metrics['success'] / total
        
        if success_rate < canary['success_threshold']:
            canary['status'] = 'rolled_back'
            logger.warning("Canary '%s' rolled back: %.1f%% success rate < %.1f%% threshold",
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
