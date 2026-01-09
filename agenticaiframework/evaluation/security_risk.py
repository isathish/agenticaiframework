"""
Security risk scoring system.

Features:
- Input risk assessment
- Output risk assessment
- PII detection
- Injection attempt detection
- Risk trend monitoring
"""

import uuid
import time
import logging
import re
import statistics
from typing import Dict, Any, List, Callable, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


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
        
        code_patterns = [r'exec\(', r'eval\(', r'__import__', r'subprocess', r'os\.system']
        
        def code_risk(text: str) -> float:
            matches = sum(1 for p in code_patterns if re.search(p, text))
            return min(matches * 0.4, 1.0)
        
        self.risk_rules['code_execution'] = code_risk
        
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
                   _context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Assess security risk for input/output."""
        assessment = {
            'id': str(uuid.uuid4()),
            'timestamp': time.time(),
            'input_risks': {},
            'output_risks': {},
            'pii_detected': [],
            'overall_risk': 0.0,
            'risk_level': 'low'
        }
        
        if input_text:
            for rule_name, rule_fn in self.risk_rules.items():
                try:
                    score = rule_fn(input_text)
                    assessment['input_risks'][rule_name] = score
                except Exception as e:  # noqa: BLE001
                    logger.warning("Risk rule %s failed: %s", rule_name, e)
        
        if output_text:
            for rule_name, rule_fn in self.risk_rules.items():
                try:
                    score = rule_fn(output_text)
                    assessment['output_risks'][rule_name] = score
                except Exception as e:  # noqa: BLE001
                    logger.warning("Risk rule %s failed: %s", rule_name, e)
            
            for pattern, pii_type in self.pii_patterns:
                if re.search(pattern, output_text):
                    assessment['pii_detected'].append(pii_type)
        
        all_scores = list(assessment['input_risks'].values()) + \
                     list(assessment['output_risks'].values())
        
        if assessment['pii_detected']:
            all_scores.append(0.8)
        
        if all_scores:
            assessment['overall_risk'] = max(all_scores)
        
        if assessment['overall_risk'] >= 0.8:
            assessment['risk_level'] = 'critical'
        elif assessment['overall_risk'] >= 0.6:
            assessment['risk_level'] = 'high'
        elif assessment['overall_risk'] >= 0.3:
            assessment['risk_level'] = 'medium'
        else:
            assessment['risk_level'] = 'low'
        
        self.risk_scores.append(assessment)
        
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


__all__ = ['SecurityRiskScorer']
