"""
Data Masking Engine.

PII protection with:
- Pattern-based detection
- Multiple masking strategies
- Tokenization
- Audit integration
"""

import uuid
import logging
import re
import hashlib
import threading
from typing import Dict, Any, List, Optional, Tuple, Pattern

from .types import MaskingRule, MaskingType, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


class DataMaskingEngine:
    """
    Data masking and PII protection engine.
    
    Features:
    - Pattern-based detection
    - Multiple masking strategies
    - Tokenization
    - Audit integration
    """
    
    def __init__(self, audit_manager=None):
        self.rules: Dict[str, MaskingRule] = {}
        self.audit_manager = audit_manager
        self._compiled_rules: Dict[str, Pattern] = {}
        self._token_map: Dict[str, str] = {}
        self._reverse_token_map: Dict[str, str] = {}
        self._lock = threading.Lock()
        
        # Add default rules
        self._add_default_rules()
    
    def _add_default_rules(self):
        """Add default PII detection rules."""
        default_rules = [
            MaskingRule(
                rule_id="email",
                name="Email Address",
                pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                data_type="email",
                masking_type=MaskingType.PARTIAL,
                visible_chars=3
            ),
            MaskingRule(
                rule_id="ssn",
                name="Social Security Number",
                pattern=r'\b\d{3}-\d{2}-\d{4}\b',
                data_type="ssn",
                masking_type=MaskingType.PARTIAL,
                visible_chars=4
            ),
            MaskingRule(
                rule_id="credit_card",
                name="Credit Card Number",
                pattern=r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
                data_type="credit_card",
                masking_type=MaskingType.PARTIAL,
                visible_chars=4
            ),
            MaskingRule(
                rule_id="phone",
                name="Phone Number",
                pattern=r'\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
                data_type="phone",
                masking_type=MaskingType.PARTIAL,
                visible_chars=4
            ),
            MaskingRule(
                rule_id="api_key",
                name="API Key",
                pattern=r'\b(?:sk|pk|api)[-_][A-Za-z0-9]{20,}\b',
                data_type="api_key",
                masking_type=MaskingType.FULL,
                replacement="[REDACTED_API_KEY]"
            )
        ]
        
        for rule in default_rules:
            self.add_rule(rule)
    
    def add_rule(self, rule: MaskingRule):
        """Add a masking rule."""
        with self._lock:
            self.rules[rule.rule_id] = rule
            self._compiled_rules[rule.rule_id] = re.compile(rule.pattern, re.IGNORECASE)
        
        logger.info("Added masking rule: %s", rule.name)
    
    def remove_rule(self, rule_id: str):
        """Remove a masking rule."""
        with self._lock:
            if rule_id in self.rules:
                del self.rules[rule_id]
                del self._compiled_rules[rule_id]
    
    def mask(self, 
            text: str,
            rules: List[str] = None,
            actor: str = None) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Mask sensitive data in text.
        
        Args:
            text: Text to mask
            rules: Specific rules to apply (None = all)
            actor: Who requested masking (for audit)
            
        Returns:
            Tuple of (masked_text, list of detections)
        """
        detections = []
        masked_text = text
        
        rules_to_apply = self.rules.values() if rules is None else [
            self.rules[r] for r in rules if r in self.rules
        ]
        
        for rule in rules_to_apply:
            if not rule.enabled:
                continue
            
            pattern = self._compiled_rules[rule.rule_id]
            matches = pattern.finditer(masked_text)
            
            for match in matches:
                original = match.group()
                masked = self._apply_masking(original, rule)
                
                detections.append({
                    'rule_id': rule.rule_id,
                    'data_type': rule.data_type,
                    'position': match.start(),
                    'original_length': len(original),
                    'masked': masked != original
                })
                
                masked_text = masked_text.replace(original, masked, 1)
        
        # Audit if requested
        if self.audit_manager and detections:
            self.audit_manager.log(
                event_type=AuditEventType.DATA_ACCESS,
                actor=actor or 'system',
                resource='data_masking',
                action='mask',
                details={
                    'detections': len(detections),
                    'data_types': list(set(d['data_type'] for d in detections))
                },
                severity=AuditSeverity.INFO
            )
        
        return masked_text, detections
    
    def _apply_masking(self, value: str, rule: MaskingRule) -> str:
        """Apply masking to a value."""
        if rule.masking_type == MaskingType.FULL:
            return rule.replacement or "[REDACTED]"
        
        elif rule.masking_type == MaskingType.PARTIAL:
            visible = rule.visible_chars
            if len(value) <= visible:
                return '*' * len(value)
            return '*' * (len(value) - visible) + value[-visible:]
        
        elif rule.masking_type == MaskingType.HASH:
            return hashlib.sha256(value.encode()).hexdigest()[:16]
        
        elif rule.masking_type == MaskingType.TOKENIZE:
            return self._tokenize(value)
        
        elif rule.masking_type == MaskingType.REDACT:
            return ""
        
        return value
    
    def _tokenize(self, value: str) -> str:
        """Replace value with reversible token."""
        if value in self._token_map:
            return self._token_map[value]
        
        token = f"TOKEN_{uuid.uuid4().hex[:12]}"
        
        with self._lock:
            self._token_map[value] = token
            self._reverse_token_map[token] = value
        
        return token
    
    def detokenize(self, token: str, actor: str = None) -> Optional[str]:
        """Reverse tokenization (requires authorization)."""
        original = self._reverse_token_map.get(token)
        
        if self.audit_manager and original:
            self.audit_manager.log(
                event_type=AuditEventType.DATA_ACCESS,
                actor=actor or 'system',
                resource='data_masking',
                action='detokenize',
                details={'token': token},
                severity=AuditSeverity.WARNING
            )
        
        return original
    
    def detect_pii(self, text: str) -> List[Dict[str, Any]]:
        """Detect PII without masking."""
        detections = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            pattern = self._compiled_rules[rule.rule_id]
            matches = pattern.finditer(text)
            
            for match in matches:
                detections.append({
                    'rule_id': rule.rule_id,
                    'data_type': rule.data_type,
                    'start': match.start(),
                    'end': match.end(),
                    'value': '*' * len(match.group())  # Don't expose actual value
                })
        
        return detections
    
    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all masking rules."""
        return [
            {
                'rule_id': r.rule_id,
                'name': r.name,
                'data_type': r.data_type,
                'masking_type': r.masking_type.value,
                'enabled': r.enabled
            }
            for r in self.rules.values()
        ]


__all__ = ['DataMaskingEngine']
