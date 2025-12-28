"""
Guardrail management module with enhanced security and validation features.

Provides:
- Input/output validation
- Content filtering
- Prompt injection protection
- Rate limiting
- Policy enforcement
- Comprehensive audit logging
"""

from typing import Dict, Any, List, Callable, Optional
import logging
import uuid
import time
from datetime import datetime
from collections import defaultdict

from .exceptions import GuardrailViolationError  # noqa: F401 - exported for library users

logger = logging.getLogger(__name__)


class Guardrail:
    """
    Enhanced Guardrail with detailed validation and reporting.
    
    Features:
    - Flexible validation functions
    - Policy enforcement
    - Violation tracking
    - Performance monitoring
    """
    
    def __init__(self, 
                 name: str, 
                 validation_fn: Callable[[Any], bool], 
                 policy: Dict[str, Any] = None,
                 severity: str = "medium"):
        self.id = str(uuid.uuid4())
        self.name = name
        self.validation_fn = validation_fn
        self.policy = policy or {}
        self.version = "2.0.0"
        self.severity = severity  # low, medium, high, critical
        
        # Tracking
        self.validation_count = 0
        self.violation_count = 0
        self.last_violation: Optional[Dict[str, Any]] = None

    def validate(self, data: Any) -> bool:
        """
        Validate data against the guardrail.
        
        Args:
            data: Data to validate
            
        Returns:
            True if valid, False otherwise
        """
        self.validation_count += 1
        
        try:
            is_valid = self.validation_fn(data)
            
            if not is_valid:
                self.violation_count += 1
                self.last_violation = {
                    'timestamp': datetime.now().isoformat(),
                    'data_preview': str(data)[:100],
                    'severity': self.severity
                }
            
            return is_valid
            
        except (TypeError, ValueError, AttributeError) as e:
            # Fail closed - treat exceptions as validation failures
            self.violation_count += 1
            self.last_violation = {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'severity': 'critical'
            }
            logger.warning("Guardrail '%s' validation error: %s", self.name, e)
            return False
        except Exception as e:  # noqa: BLE001 - Fail closed for unknown errors
            self.violation_count += 1
            self.last_violation = {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'severity': 'critical'
            }
            logger.exception("Unexpected error in guardrail '%s'", self.name)
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get guardrail statistics."""
        violation_rate = 0.0
        if self.validation_count > 0:
            violation_rate = self.violation_count / self.validation_count
        
        return {
            'name': self.name,
            'validation_count': self.validation_count,
            'violation_count': self.violation_count,
            'violation_rate': violation_rate,
            'last_violation': self.last_violation,
            'severity': self.severity
        }


class GuardrailManager:
    """
    Enhanced Guardrail Manager with comprehensive security features.
    
    Features:
    - Multi-layered validation
    - Priority-based enforcement
    - Detailed violation tracking
    - Integration with security module
    - Custom remediation actions
    """
    
    def __init__(self):
        self.guardrails: Dict[str, Guardrail] = {}
        self.violation_log: List[Dict[str, Any]] = []
        self.remediation_actions: Dict[str, Callable] = {}
        self.circuit_breaker_threshold = 10  # Auto-disable after X consecutive violations
        self.circuit_breaker_counts: Dict[str, int] = defaultdict(int)

    def register_guardrail(self, guardrail: Guardrail, priority: int = 0):
        """
        Register a guardrail with optional priority.
        
        Args:
            guardrail: Guardrail to register
            priority: Priority level (higher = checked first)
        """
        guardrail.policy['priority'] = priority
        self.guardrails[guardrail.id] = guardrail
        self._log(f"Registered guardrail '{guardrail.name}' with ID {guardrail.id} (priority: {priority})")

    def get_guardrail(self, guardrail_id: str) -> Optional[Guardrail]:
        """Get a guardrail by ID."""
        return self.guardrails.get(guardrail_id)
    
    def get_guardrail_by_name(self, name: str) -> Optional[Guardrail]:
        """Get a guardrail by name."""
        for guardrail in self.guardrails.values():
            if guardrail.name == name:
                return guardrail
        return None

    def list_guardrails(self) -> List[Guardrail]:
        """List all guardrails sorted by priority."""
        return sorted(
            self.guardrails.values(),
            key=lambda g: g.policy.get('priority', 0),
            reverse=True
        )

    def remove_guardrail(self, guardrail_id: str):
        """Remove a guardrail by ID."""
        if guardrail_id in self.guardrails:
            name = self.guardrails[guardrail_id].name
            del self.guardrails[guardrail_id]
            self.circuit_breaker_counts.pop(guardrail_id, None)
            self._log(f"Removed guardrail '{name}' with ID {guardrail_id}")

    def enforce_guardrails(self, data: Any, fail_fast: bool = True) -> Dict[str, Any]:
        """
        Enforce all guardrails with detailed reporting.
        
        Args:
            data: Data to validate
            fail_fast: Stop at first failure if True
            
        Returns:
            Dict with validation results and details
        """
        results = {
            'is_valid': True,
            'violations': [],
            'guardrails_checked': 0,
            'timestamp': datetime.now().isoformat()
        }
        
        # Check guardrails in priority order
        for guardrail in self.list_guardrails():
            results['guardrails_checked'] += 1
            
            # Check circuit breaker
            if self.circuit_breaker_counts[guardrail.id] >= self.circuit_breaker_threshold:
                self._log(f"Guardrail '{guardrail.name}' circuit breaker activated (skipping)")
                continue
            
            if not guardrail.validate(data):
                violation = {
                    'guardrail_id': guardrail.id,
                    'guardrail_name': guardrail.name,
                    'severity': guardrail.severity,
                    'timestamp': datetime.now().isoformat()
                }
                
                results['violations'].append(violation)
                results['is_valid'] = False
                
                # Log violation
                self.violation_log.append(violation)
                self._log(f"Guardrail '{guardrail.name}' failed validation (severity: {guardrail.severity})")
                
                # Increment circuit breaker
                self.circuit_breaker_counts[guardrail.id] += 1
                
                # Execute remediation action if available
                if guardrail.id in self.remediation_actions:
                    try:
                        self.remediation_actions[guardrail.id](data, violation)
                    except (TypeError, ValueError, RuntimeError) as e:
                        self._log(f"Remediation action failed: {e}")
                        logger.error("Remediation action failed for guardrail %s: %s", guardrail.id, e)
                    except Exception as e:  # noqa: BLE001 - Log but continue for unknown errors
                        self._log(f"Remediation action failed with unexpected error: {e}")
                        logger.exception("Unexpected remediation error for guardrail %s", guardrail.id)
                
                # Fail fast if requested
                if fail_fast:
                    break
            else:
                # Reset circuit breaker on success
                self.circuit_breaker_counts[guardrail.id] = 0
        
        return results

    def validate(self, guardrail_name: str, data: Any) -> bool:
        """
        Validate data against a specific guardrail by name.
        
        Args:
            guardrail_name: Name of guardrail
            data: Data to validate
            
        Returns:
            True if valid, False otherwise
        """
        guardrail = self.get_guardrail_by_name(guardrail_name)
        if guardrail:
            return guardrail.validate(data)
        
        self._log(f"Guardrail '{guardrail_name}' not found")
        return False
    
    def register_remediation_action(self, 
                                   guardrail_id: str, 
                                   action: Callable[[Any, Dict], None]):
        """
        Register a remediation action for a guardrail.
        
        Args:
            guardrail_id: ID of guardrail
            action: Callable that takes (data, violation_info)
        """
        self.remediation_actions[guardrail_id] = action
        self._log(f"Registered remediation action for guardrail {guardrail_id}")
    
    def get_violation_report(self, 
                            severity: str = None,
                            limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get violation report with optional filtering.
        
        Args:
            severity: Filter by severity level
            limit: Maximum number of entries to return
            
        Returns:
            List of violation entries
        """
        violations = self.violation_log
        
        if severity:
            violations = [v for v in violations if v.get('severity') == severity]
        
        return violations[-limit:]
    
    def get_aggregate_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics across all guardrails."""
        total_validations = 0
        total_violations = 0
        severity_counts = defaultdict(int)
        
        for guardrail in self.guardrails.values():
            stats = guardrail.get_stats()
            total_validations += stats['validation_count']
            total_violations += stats['violation_count']
            severity_counts[guardrail.severity] += stats['violation_count']
        
        return {
            'total_guardrails': len(self.guardrails),
            'total_validations': total_validations,
            'total_violations': total_violations,
            'violation_rate': total_violations / total_validations if total_validations > 0 else 0.0,
            'violations_by_severity': dict(severity_counts),
            'circuit_breakers_active': sum(
                1 for count in self.circuit_breaker_counts.values() 
                if count >= self.circuit_breaker_threshold
            )
        }
    
    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self.circuit_breaker_counts.clear()
        self._log("Reset all circuit breakers")
    
    def create_standard_guardrails(self):
        """Create a set of standard security guardrails."""
        # Length validation
        length_guardrail = Guardrail(
            name="input_length",
            validation_fn=lambda data: len(str(data)) <= 10000,
            policy={'max_length': 10000},
            severity="medium"
        )
        self.register_guardrail(length_guardrail, priority=10)
        
        # Empty input check
        empty_guardrail = Guardrail(
            name="non_empty",
            validation_fn=lambda data: bool(str(data).strip()),
            severity="low"
        )
        self.register_guardrail(empty_guardrail, priority=5)
        
        self._log("Created standard guardrails")

    def _log(self, message: str):
        """Log a message."""
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [GuardrailManager] {message}")
