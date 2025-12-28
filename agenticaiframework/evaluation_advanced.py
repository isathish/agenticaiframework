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


# =============================================================================
# Model-Level Evaluations (LLM Quality)
# =============================================================================

class ModelQualityEvaluator:
    """
    Model-Level Evaluation system.
    
    Evaluates LLM quality metrics:
    - Reasoning quality
    - Language understanding
    - Hallucination detection
    - Token efficiency
    """
    
    def __init__(self):
        self.evaluations: List[Dict[str, Any]] = []
        self.model_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {'evaluations': 0, 'metrics': defaultdict(list)}
        )
    
    def evaluate_response(self,
                         model_name: str,
                         prompt: str,
                         response: str,
                         ground_truth: str = None,
                         metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Evaluate model response quality."""
        metrics = {}
        
        # Accuracy (if ground truth provided)
        if ground_truth:
            metrics['exact_match'] = 1.0 if response.strip() == ground_truth.strip() else 0.0
            metrics['token_overlap'] = self._calculate_token_overlap(response, ground_truth)
        
        # Hallucination indicators
        metrics['hallucination_score'] = self._detect_hallucination(prompt, response)
        
        # Reasoning quality
        metrics['reasoning_quality'] = self._assess_reasoning(response)
        
        # Token efficiency
        metrics['token_efficiency'] = len(prompt.split()) / max(len(response.split()), 1)
        
        # Response completeness
        metrics['completeness'] = self._assess_completeness(response)
        
        evaluation = {
            'id': str(uuid.uuid4()),
            'model': model_name,
            'prompt': prompt,
            'response': response,
            'metrics': metrics,
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        
        self.evaluations.append(evaluation)
        
        # Update model-level aggregates
        for metric_name, value in metrics.items():
            self.model_metrics[model_name]['metrics'][metric_name].append(value)
        self.model_metrics[model_name]['evaluations'] += 1
        
        return evaluation
    
    def _calculate_token_overlap(self, response: str, ground_truth: str) -> float:
        """Calculate token overlap similarity."""
        resp_tokens = set(response.lower().split())
        truth_tokens = set(ground_truth.lower().split())
        
        if not truth_tokens:
            return 0.0
        
        intersection = len(resp_tokens & truth_tokens)
        return intersection / len(truth_tokens)
    
    def _detect_hallucination(self, prompt: str, response: str) -> float:
        """Detect potential hallucinations (simplified)."""
        # Check for common hallucination patterns
        hallucination_indicators = [
            'according to my knowledge',
            'i believe',
            'i think',
            'probably',
            'might be',
            'could be'
        ]
        
        response_lower = response.lower()
        indicator_count = sum(1 for ind in hallucination_indicators if ind in response_lower)
        
        # Higher score = more likely hallucination
        return min(indicator_count * 0.2, 1.0)
    
    def _assess_reasoning(self, response: str) -> float:
        """Assess reasoning quality."""
        # Check for reasoning indicators
        reasoning_indicators = [
            'because', 'therefore', 'thus', 'since', 'as a result',
            'consequently', 'due to', 'step', 'first', 'second'
        ]
        
        response_lower = response.lower()
        indicator_count = sum(1 for ind in reasoning_indicators if ind in response_lower)
        
        return min(indicator_count * 0.15, 1.0)
    
    def _assess_completeness(self, response: str) -> float:
        """Assess response completeness."""
        # Simple heuristic based on length and structure
        word_count = len(response.split())
        has_punctuation = any(p in response for p in '.!?')
        
        completeness = 0.0
        if word_count > 10:
            completeness += 0.5
        if has_punctuation:
            completeness += 0.5
        
        return completeness
    
    def get_model_summary(self, model_name: str) -> Dict[str, Any]:
        """Get summary metrics for a model."""
        if model_name not in self.model_metrics:
            return {'error': 'Model not found'}
        
        model_data = self.model_metrics[model_name]
        summary = {
            'model': model_name,
            'total_evaluations': model_data['evaluations'],
            'metrics': {}
        }
        
        for metric_name, values in model_data['metrics'].items():
            if values:
                summary['metrics'][metric_name] = {
                    'mean': statistics.mean(values),
                    'min': min(values),
                    'max': max(values),
                    'stdev': statistics.stdev(values) if len(values) > 1 else 0
                }
        
        return summary
    
    # Convenience methods for granular evaluation
    def evaluate_hallucination(self, 
                              text: str, 
                              is_hallucination: bool, 
                              confidence: float = 1.0) -> Dict[str, Any]:
        """
        Evaluate text for hallucination.
        
        Args:
            text: The text to evaluate
            is_hallucination: Whether the text is a hallucination
            confidence: Confidence score (0-1)
            
        Returns:
            Evaluation result dictionary
        """
        result = {
            'text': text,
            'is_hallucination': is_hallucination,
            'confidence': confidence,
            'timestamp': time.time()
        }
        return result
    
    def evaluate_reasoning(self,
                          query: str,
                          reasoning: str,
                          answer: str,
                          correct: bool) -> Dict[str, Any]:
        """
        Evaluate reasoning quality.
        
        Args:
            query: The input query
            reasoning: The reasoning process
            answer: The final answer
            correct: Whether the reasoning/answer is correct
            
        Returns:
            Evaluation result dictionary
        """
        result = {
            'query': query,
            'reasoning': reasoning,
            'answer': answer,
            'correct': correct,
            'timestamp': time.time()
        }
        return result
    
    def evaluate_token_efficiency(self,
                                  response: str,
                                  token_count: int,
                                  quality_score: float) -> Dict[str, Any]:
        """
        Evaluate token efficiency.
        
        Args:
            response: The model response
            token_count: Number of tokens used
            quality_score: Quality score of the response (0-1)
            
        Returns:
            Evaluation result dictionary
        """
        result = {
            'response': response,
            'token_count': token_count,
            'quality_score': quality_score,
            'efficiency': quality_score / token_count if token_count > 0 else 0,
            'timestamp': time.time()
        }
        return result
    
    def get_quality_metrics(self) -> Dict[str, Any]:
        """
        Get overall quality metrics across all models.
        
        Returns:
            Aggregate metrics dictionary
        """
        all_metrics = {
            'total_models': len(self.model_metrics),
            'total_evaluations': sum(m['evaluations'] for m in self.model_metrics.values()),
            'models': {}
        }
        
        for model_name in self.model_metrics:
            all_metrics['models'][model_name] = self.get_model_summary(model_name)
        
        return all_metrics


# =============================================================================
# Task/Skill-Level Evaluations
# =============================================================================

class TaskEvaluator:
    """
    Task/Skill-Level Evaluation system.
    
    Tracks task completion, instruction following, and multi-step reasoning.
    """
    
    def __init__(self):
        self.task_executions: List[Dict[str, Any]] = []
        self.task_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {'attempts': 0, 'successes': 0, 'failures': 0, 'retries': []}
        )
    
    def record_task_execution(self,
                            task_name: str,
                            success: bool,
                            completion_percentage: float = None,
                            retry_count: int = 0,
                            error_recovered: bool = False,
                            duration_ms: float = None,
                            metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record task execution."""
        execution = {
            'id': str(uuid.uuid4()),
            'task_name': task_name,
            'success': success,
            'completion_percentage': completion_percentage or (100.0 if success else 0.0),
            'retry_count': retry_count,
            'error_recovered': error_recovered,
            'duration_ms': duration_ms,
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        
        self.task_executions.append(execution)
        
        # Update task metrics
        metrics = self.task_metrics[task_name]
        metrics['attempts'] += 1
        if success:
            metrics['successes'] += 1
        else:
            metrics['failures'] += 1
        metrics['retries'].append(retry_count)
        
        return execution
    
    def get_task_metrics(self, task_name: str = None) -> Dict[str, Any]:
        """Get metrics for a specific task or all tasks."""
        if task_name:
            if task_name not in self.task_metrics:
                return {'error': 'Task not found'}
            
            metrics = self.task_metrics[task_name]
            total = metrics['attempts']
            
            return {
                'task_name': task_name,
                'success_rate': metrics['successes'] / total if total else 0,
                'failure_rate': metrics['failures'] / total if total else 0,
                'avg_retry_count': statistics.mean(metrics['retries']) if metrics['retries'] else 0,
                'total_attempts': total
            }
        
        # Return all tasks
        summary = {}
        for task, metrics in self.task_metrics.items():
            total = metrics['attempts']
            summary[task] = {
                'success_rate': metrics['successes'] / total if total else 0,
                'attempts': total
            }
        
        return summary


# =============================================================================
# Tool & API Invocation Evaluations
# =============================================================================

class ToolInvocationEvaluator:
    """
    Tool & API Invocation Evaluation system.
    
    Tracks tool usage correctness, parameter validity, and call ordering.
    """
    
    def __init__(self):
        self.tool_calls: List[Dict[str, Any]] = []
        self.tool_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                'calls': 0, 'successful': 0, 'failed': 0,
                'invalid_params': 0, 'latencies': []
            }
        )
    
    def record_tool_call(self,
                        tool_name: str,
                        parameters: Dict[str, Any],
                        success: bool,
                        valid_parameters: bool = True,
                        latency_ms: float = None,
                        error: str = None,
                        metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record tool invocation."""
        call = {
            'id': str(uuid.uuid4()),
            'tool_name': tool_name,
            'parameters': parameters,
            'success': success,
            'valid_parameters': valid_parameters,
            'latency_ms': latency_ms,
            'error': error,
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        
        self.tool_calls.append(call)
        
        # Update metrics
        metrics = self.tool_metrics[tool_name]
        metrics['calls'] += 1
        if success:
            metrics['successful'] += 1
        else:
            metrics['failed'] += 1
        if not valid_parameters:
            metrics['invalid_params'] += 1
        if latency_ms:
            metrics['latencies'].append(latency_ms)
        
        return call
    
    def get_tool_metrics(self, tool_name: str = None) -> Dict[str, Any]:
        """Get tool usage metrics."""
        if tool_name:
            if tool_name not in self.tool_metrics:
                return {'error': 'Tool not found'}
            
            metrics = self.tool_metrics[tool_name]
            total = metrics['calls']
            
            return {
                'tool_name': tool_name,
                'success_rate': metrics['successful'] / total if total else 0,
                'failure_rate': metrics['failed'] / total if total else 0,
                'invalid_param_rate': metrics['invalid_params'] / total if total else 0,
                'avg_latency_ms': statistics.mean(metrics['latencies']) if metrics['latencies'] else 0,
                'total_calls': total
            }
        
        # Return all tools
        summary = {}
        for tool, metrics in self.tool_metrics.items():
            total = metrics['calls']
            summary[tool] = {
                'success_rate': metrics['successful'] / total if total else 0,
                'calls': total
            }
        
        return summary
    
    def detect_tool_call_patterns(self) -> Dict[str, Any]:
        """Detect common tool call patterns and issues."""
        if len(self.tool_calls) < 2:
            return {'error': 'Insufficient data'}
        
        patterns = {
            'repeated_failures': [],
            'slow_tools': [],
            'frequent_invalid_params': []
        }
        
        for tool, metrics in self.tool_metrics.items():
            total = metrics['calls']
            if total < 5:
                continue
            
            # Repeated failures
            if metrics['failed'] / total > 0.3:
                patterns['repeated_failures'].append(tool)
            
            # Slow tools
            if metrics['latencies'] and statistics.mean(metrics['latencies']) > 5000:
                patterns['slow_tools'].append(tool)
            
            # Frequent invalid params
            if metrics['invalid_params'] / total > 0.2:
                patterns['frequent_invalid_params'].append(tool)
        
        return patterns


# =============================================================================
# Workflow/Orchestration Evaluations
# =============================================================================

class WorkflowEvaluator:
    """
    Workflow/Orchestration Evaluation system.
    
    Tracks multi-agent workflows, handoffs, and orchestration success.
    """
    
    def __init__(self):
        self.workflows: Dict[str, Dict[str, Any]] = {}
        self.workflow_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {'attempts': 0, 'completions': 0, 'deadlocks': 0, 'durations': []}
        )
    
    def start_workflow(self, workflow_name: str, workflow_id: str = None) -> str:
        """Start tracking a workflow."""
        workflow_id = workflow_id or str(uuid.uuid4())
        
        self.workflows[workflow_id] = {
            'id': workflow_id,
            'name': workflow_name,
            'status': 'running',
            'steps': [],
            'agents': set(),
            'start_time': time.time(),
            'end_time': None
        }
        
        self.workflow_metrics[workflow_name]['attempts'] += 1
        
        return workflow_id
    
    def record_step(self,
                   workflow_id: str,
                   step_name: str,
                   agent_name: str = None,
                   success: bool = True,
                   metadata: Dict[str, Any] = None):
        """Record a workflow step."""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        
        step = {
            'step_name': step_name,
            'agent': agent_name,
            'success': success,
            'metadata': metadata or {},
            'timestamp': time.time()
        }
        
        workflow['steps'].append(step)
        if agent_name:
            workflow['agents'].add(agent_name)
    
    def complete_workflow(self, workflow_id: str, success: bool = True, deadlock: bool = False):
        """Mark workflow as complete."""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        workflow['status'] = 'completed' if success else 'failed'
        workflow['end_time'] = time.time()
        
        duration = workflow['end_time'] - workflow['start_time']
        
        # Update metrics
        metrics = self.workflow_metrics[workflow['name']]
        if success:
            metrics['completions'] += 1
        if deadlock:
            metrics['deadlocks'] += 1
        metrics['durations'].append(duration)
    
    def get_workflow_metrics(self, workflow_name: str = None) -> Dict[str, Any]:
        """Get workflow metrics."""
        if workflow_name:
            if workflow_name not in self.workflow_metrics:
                return {'error': 'Workflow not found'}
            
            metrics = self.workflow_metrics[workflow_name]
            total = metrics['attempts']
            
            return {
                'workflow_name': workflow_name,
                'completion_rate': metrics['completions'] / total if total else 0,
                'deadlock_rate': metrics['deadlocks'] / total if total else 0,
                'avg_duration_seconds': statistics.mean(metrics['durations']) if metrics['durations'] else 0,
                'total_attempts': total
            }
        
        # Return all workflows
        summary = {}
        for name, metrics in self.workflow_metrics.items():
            total = metrics['attempts']
            summary[name] = {
                'completion_rate': metrics['completions'] / total if total else 0,
                'attempts': total
            }
        
        return summary
    
    # Convenience methods for easier API usage
    def record_workflow_execution(self,
                                  workflow_name: str,
                                  success: bool = True,
                                  deadlock: bool = False,
                                  metadata: Dict[str, Any] = None) -> str:
        """
        Record a complete workflow execution (convenience wrapper).
        
        Args:
            workflow_name: Name of the workflow
            success: Whether the workflow completed successfully
            deadlock: Whether the workflow encountered a deadlock
            metadata: Additional metadata
            
        Returns:
            Workflow ID
        """
        workflow_id = self.start_workflow(workflow_name)
        if metadata:
            self.record_step(workflow_id, "execution", success=success, metadata=metadata)
        self.complete_workflow(workflow_id, success=success, deadlock=deadlock)
        return workflow_id
    
    def record_agent_handoff(self,
                            workflow_id: str,
                            from_agent: str,
                            to_agent: str,
                            metadata: Dict[str, Any] = None):
        """
        Record an agent handoff in a workflow.
        
        Args:
            workflow_id: ID of the workflow
            from_agent: Name of the agent handing off
            to_agent: Name of the agent receiving handoff
            metadata: Additional metadata
        """
        handoff_metadata = metadata or {}
        handoff_metadata['from_agent'] = from_agent
        handoff_metadata['to_agent'] = to_agent
        
        self.record_step(
            workflow_id,
            step_name=f"handoff_{from_agent}_to_{to_agent}",
            agent_name=to_agent,
            success=True,
            metadata=handoff_metadata
        )


# =============================================================================
# Memory & Context Evaluations
# =============================================================================

class MemoryEvaluator:
    """
    Memory & Context Evaluation system.
    
    Evaluates memory accuracy, context relevance, and knowledge freshness.
    """
    
    def __init__(self):
        self.memory_evaluations: List[Dict[str, Any]] = []
        self.memory_metrics: Dict[str, Any] = {
            'total_queries': 0,
            'relevant_retrievals': 0,
            'stale_data_usage': 0,
            'context_precision_scores': [],
            'memory_overwrite_errors': 0
        }
    
    def evaluate_memory_retrieval(self,
                                  query: str,
                                  retrieved_memories: List[Dict[str, Any]],
                                  relevant_memories: List[Dict[str, Any]] = None,
                                  metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Evaluate memory retrieval quality."""
        evaluation = {
            'id': str(uuid.uuid4()),
            'query': query,
            'retrieved_count': len(retrieved_memories),
            'timestamp': time.time()
        }
        
        # Context precision (if ground truth provided)
        if relevant_memories:
            precision = self._calculate_precision(retrieved_memories, relevant_memories)
            recall = self._calculate_recall(retrieved_memories, relevant_memories)
            evaluation['precision'] = precision
            evaluation['recall'] = recall
            
            self.memory_metrics['context_precision_scores'].append(precision)
        
        # Check for stale data
        stale_count = sum(1 for m in retrieved_memories if self._is_stale(m))
        evaluation['stale_count'] = stale_count
        
        if stale_count > 0:
            self.memory_metrics['stale_data_usage'] += 1
        
        self.memory_evaluations.append(evaluation)
        self.memory_metrics['total_queries'] += 1
        
        return evaluation
    
    def _calculate_precision(self, retrieved: List[Dict], relevant: List[Dict]) -> float:
        """Calculate retrieval precision."""
        if not retrieved:
            return 0.0
        
        retrieved_ids = {m.get('id', str(m)) for m in retrieved}
        relevant_ids = {m.get('id', str(m)) for m in relevant}
        
        true_positives = len(retrieved_ids & relevant_ids)
        return true_positives / len(retrieved_ids)
    
    def _calculate_recall(self, retrieved: List[Dict], relevant: List[Dict]) -> float:
        """Calculate retrieval recall."""
        if not relevant:
            return 0.0
        
        retrieved_ids = {m.get('id', str(m)) for m in retrieved}
        relevant_ids = {m.get('id', str(m)) for m in relevant}
        
        true_positives = len(retrieved_ids & relevant_ids)
        return true_positives / len(relevant_ids)
    
    def _is_stale(self, memory: Dict[str, Any]) -> bool:
        """Check if memory is stale."""
        if 'timestamp' not in memory:
            return False
        
        # Consider stale if older than 30 days
        age_seconds = time.time() - memory['timestamp']
        return age_seconds > (30 * 24 * 3600)
    
    def record_memory_error(self, error_type: str):
        """Record memory-related errors."""
        if error_type == 'overwrite':
            self.memory_metrics['memory_overwrite_errors'] += 1
    
    def get_memory_metrics(self) -> Dict[str, Any]:
        """Get memory evaluation metrics."""
        metrics = self.memory_metrics
        
        return {
            'total_queries': metrics['total_queries'],
            'stale_data_rate': metrics['stale_data_usage'] / metrics['total_queries'] if metrics['total_queries'] else 0,
            'avg_precision': statistics.mean(metrics['context_precision_scores']) if metrics['context_precision_scores'] else 0,
            'memory_errors': metrics['memory_overwrite_errors']
        }
    
    # Convenience methods for easier API usage
    def evaluate_retrieval(self,
                          query: str,
                          retrieved_memories: List[Dict[str, Any]],
                          relevant_memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate memory retrieval (alias for evaluate_memory_retrieval).
        
        Args:
            query: The query used for retrieval
            retrieved_memories: Memories retrieved by the system
            relevant_memories: Ground truth relevant memories
            
        Returns:
            Evaluation result dictionary
        """
        return self.evaluate_memory_retrieval(
            query=query,
            retrieved_items=retrieved_memories,
            relevant_items=relevant_memories
        )
    
    def record_stale_data_access(self, memory_data: Dict[str, Any]):
        """
        Record access to stale data.
        
        Args:
            memory_data: The stale memory that was accessed
        """
        self.memory_metrics['stale_data_usage'] += 1
    
    def record_overwrite_error(self):
        """Record a memory overwrite error."""
        self.record_memory_error('overwrite')


# =============================================================================
# RAG (Knowledge Retrieval) Evaluations
# =============================================================================

class RAGEvaluator:
    """
    RAG (Retrieval-Augmented Generation) Evaluation system.
    
    Evaluates retrieval accuracy, citation correctness, and answer groundedness.
    """
    
    def __init__(self):
        self.rag_evaluations: List[Dict[str, Any]] = []
        self.rag_metrics: Dict[str, Any] = {
            'total_queries': 0,
            'precision_scores': [],
            'recall_scores': [],
            'faithfulness_scores': [],
            'groundedness_scores': []
        }
    
    def evaluate_rag_response(self,
                             query: str,
                             retrieved_docs: List[Dict[str, Any]],
                             generated_answer: str,
                             relevant_docs: List[Dict[str, Any]] = None,
                             ground_truth_answer: str = None,
                             metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Evaluate RAG response quality."""
        evaluation = {
            'id': str(uuid.uuid4()),
            'query': query,
            'num_retrieved': len(retrieved_docs),
            'answer_length': len(generated_answer),
            'timestamp': time.time()
        }
        
        # Retrieval metrics
        if relevant_docs:
            precision = self._calculate_retrieval_precision(retrieved_docs, relevant_docs)
            recall = self._calculate_retrieval_recall(retrieved_docs, relevant_docs)
            
            evaluation['retrieval_precision'] = precision
            evaluation['retrieval_recall'] = recall
            
            self.rag_metrics['precision_scores'].append(precision)
            self.rag_metrics['recall_scores'].append(recall)
        
        # Faithfulness (answer grounded in retrieved docs)
        faithfulness = self._assess_faithfulness(generated_answer, retrieved_docs)
        evaluation['faithfulness'] = faithfulness
        self.rag_metrics['faithfulness_scores'].append(faithfulness)
        
        # Groundedness (no hallucinations)
        groundedness = self._assess_groundedness(generated_answer, retrieved_docs)
        evaluation['groundedness'] = groundedness
        self.rag_metrics['groundedness_scores'].append(groundedness)
        
        # Check for citations
        evaluation['has_citations'] = self._has_citations(generated_answer)
        
        self.rag_evaluations.append(evaluation)
        self.rag_metrics['total_queries'] += 1
        
        return evaluation
    
    def _calculate_retrieval_precision(self, retrieved: List[Dict], relevant: List[Dict]) -> float:
        """Calculate retrieval precision."""
        if not retrieved:
            return 0.0
        
        retrieved_ids = {str(d.get('id', d)) for d in retrieved}
        relevant_ids = {str(d.get('id', d)) for d in relevant}
        
        true_positives = len(retrieved_ids & relevant_ids)
        return true_positives / len(retrieved_ids)
    
    def _calculate_retrieval_recall(self, retrieved: List[Dict], relevant: List[Dict]) -> float:
        """Calculate retrieval recall."""
        if not relevant:
            return 0.0
        
        retrieved_ids = {str(d.get('id', d)) for d in retrieved}
        relevant_ids = {str(d.get('id', d)) for d in relevant}
        
        true_positives = len(retrieved_ids & relevant_ids)
        return true_positives / len(relevant_ids)
    
    def _assess_faithfulness(self, answer: str, docs: List[Dict]) -> float:
        """Assess if answer is faithful to retrieved documents."""
        if not docs:
            return 0.0
        
        # Simple token overlap assessment
        answer_tokens = set(answer.lower().split())
        
        doc_tokens = set()
        for doc in docs:
            content = doc.get('content', str(doc))
            doc_tokens.update(content.lower().split())
        
        if not doc_tokens:
            return 0.0
        
        overlap = len(answer_tokens & doc_tokens)
        return overlap / len(answer_tokens) if answer_tokens else 0.0
    
    def _assess_groundedness(self, answer: str, docs: List[Dict]) -> float:
        """Assess answer groundedness (inverse hallucination)."""
        # Check for statements not supported by docs
        # Simplified: use token coverage
        return self._assess_faithfulness(answer, docs)
    
    def _has_citations(self, answer: str) -> bool:
        """Check if answer has citations."""
        citation_patterns = ['[', ']', 'source:', 'reference:', 'according to']
        return any(pattern in answer.lower() for pattern in citation_patterns)
    
    def get_rag_metrics(self) -> Dict[str, Any]:
        """Get RAG evaluation metrics."""
        metrics = self.rag_metrics
        
        return {
            'total_queries': metrics['total_queries'],
            'avg_retrieval_precision': statistics.mean(metrics['precision_scores']) if metrics['precision_scores'] else 0,
            'avg_retrieval_recall': statistics.mean(metrics['recall_scores']) if metrics['recall_scores'] else 0,
            'avg_faithfulness': statistics.mean(metrics['faithfulness_scores']) if metrics['faithfulness_scores'] else 0,
            'avg_groundedness': statistics.mean(metrics['groundedness_scores']) if metrics['groundedness_scores'] else 0
        }
    
    # Convenience methods for granular evaluation
    def evaluate_retrieval(self,
                          query: str,
                          retrieved_docs: List[Dict[str, Any]],
                          relevant_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate retrieval quality.
        
        Args:
            query: The search query
            retrieved_docs: Documents retrieved by the system
            relevant_docs: Ground truth relevant documents
            
        Returns:
            Retrieval evaluation with precision and recall
        """
        precision = self._calculate_retrieval_precision(retrieved_docs, relevant_docs)
        recall = self._calculate_retrieval_recall(retrieved_docs, relevant_docs)
        
        return {
            'query': query,
            'precision': precision,
            'recall': recall,
            'f1_score': 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0,
            'num_retrieved': len(retrieved_docs),
            'num_relevant': len(relevant_docs),
            'timestamp': time.time()
        }
    
    def evaluate_faithfulness(self,
                             answer: str,
                             retrieved_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate answer faithfulness to retrieved documents.
        
        Args:
            answer: The generated answer
            retrieved_docs: The source documents
            
        Returns:
            Faithfulness evaluation result
        """
        faithfulness = self._assess_faithfulness(answer, retrieved_docs)
        
        return {
            'answer': answer,
            'faithfulness_score': faithfulness,
            'num_docs': len(retrieved_docs),
            'timestamp': time.time()
        }
    
    def evaluate_groundedness(self,
                             answer: str,
                             retrieved_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate answer groundedness (lack of hallucination).
        
        Args:
            answer: The generated answer
            retrieved_docs: The source documents
            
        Returns:
            Groundedness evaluation result
        """
        groundedness = self._assess_groundedness(answer, retrieved_docs)
        
        return {
            'answer': answer,
            'groundedness_score': groundedness,
            'num_docs': len(retrieved_docs),
            'timestamp': time.time()
        }
    
    def check_citations(self, answer: str) -> Dict[str, Any]:
        """
        Check if answer contains citations.
        
        Args:
            answer: The generated answer
            
        Returns:
            Citation check result
        """
        has_citations = self._has_citations(answer)
        
        return {
            'answer': answer,
            'has_citations': has_citations,
            'timestamp': time.time()
        }


# =============================================================================
# Autonomy & Planning Evaluations
# =============================================================================

class AutonomyEvaluator:
    """
    Autonomy & Planning Evaluation system.
    
    Evaluates agent planning quality, self-correction, and autonomy level.
    """
    
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
                     metadata: Dict[str, Any] = None) -> Dict[str, Any]:
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
        
        # Plan optimality
        if optimal_steps:
            optimality = self._calculate_plan_optimality(plan_steps, optimal_steps)
            evaluation['optimality'] = optimality
            self.autonomy_metrics['plan_optimality_scores'].append(optimality)
        
        # Autonomy score
        autonomy_score = 1.0
        if human_intervention:
            autonomy_score -= 0.5
        if replanned:
            autonomy_score -= 0.2
        if not goal_achieved:
            autonomy_score -= 0.3
        evaluation['autonomy_score'] = max(0, autonomy_score)
        
        self.planning_evaluations.append(evaluation)
        
        # Update metrics
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
        """Calculate plan optimality."""
        if not optimal_steps:
            return 1.0
        
        # Simple metric: ratio of optimal to actual steps
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
    
    # Convenience method for easier API usage
    def evaluate_plan_optimality(self,
                                 plan_steps: List[str],
                                 optimal_steps: List[str]) -> Dict[str, Any]:
        """
        Evaluate plan optimality (convenience wrapper).
        
        Args:
            plan_steps: The actual plan steps
            optimal_steps: The optimal plan steps
            
        Returns:
            Optimality evaluation result
        """
        optimality = self._calculate_plan_optimality(plan_steps, optimal_steps)
        
        return {
            'optimality': optimality,
            'actual_steps': len(plan_steps),
            'optimal_steps': len(optimal_steps),
            'timestamp': time.time()
        }


# =============================================================================
# Performance & Scalability Evaluations
# =============================================================================

class PerformanceEvaluator:
    """
    Performance & Scalability Evaluation system.
    
    Tracks latency, throughput, and stability metrics.
    """
    
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
    
    # Convenience method for easier API usage
    def record_execution(self,
                        execution_id: str,
                        duration_ms: float,
                        success: bool = True,
                        metadata: Dict[str, Any] = None):
        """
        Record execution performance (alias for record_request).
        
        Args:
            execution_id: Unique ID for the execution
            duration_ms: Duration in milliseconds
            success: Whether the execution succeeded
            metadata: Additional metadata
        """
        self.record_request(
            request_id=execution_id,
            latency_ms=duration_ms,
            success=success,
            metadata=metadata
        )


# =============================================================================
# Human-in-the-Loop (HITL) Evaluations
# =============================================================================

class HITLEvaluator:
    """
    Human-in-the-Loop (HITL) Evaluation system.
    
    Evaluates agent-human collaboration quality.
    """
    
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
        
        # Update metrics
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


# =============================================================================
# Business & Outcome Evaluations
# =============================================================================

class BusinessOutcomeEvaluator:
    """
    Business & Outcome Evaluation system.
    
    Tracks real-world business impact and value creation.
    """
    
    def __init__(self):
        self.outcome_metrics: Dict[str, List[float]] = defaultdict(list)
        self.baseline_metrics: Dict[str, float] = {}
    
    def set_baseline(self, metric_name: str, baseline_value: float):
        """Set baseline metric for comparison."""
        self.baseline_metrics[metric_name] = baseline_value
    
    def record_outcome(self,
                      metric_name: str,
                      value: float,
                      metadata: Dict[str, Any] = None):
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
            
            # Compare to baseline if available
            if metric_name in self.baseline_metrics:
                baseline = self.baseline_metrics[metric_name]
                improvement = ((current_avg - baseline) / baseline * 100) if baseline else 0
                
                metric_impact['baseline'] = baseline
                metric_impact['improvement_pct'] = improvement
            
            impact[metric_name] = metric_impact
        
        return impact
    
    def calculate_roi(self,
                     cost: float,
                     benefit: float,
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
