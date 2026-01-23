"""
Enterprise Compliance Engine Module.

Compliance checking, policy enforcement,
regulatory controls, and audit compliance.

Example:
    # Create compliance engine
    compliance = create_compliance_engine()
    
    # Register policy
    policy = compliance.add_policy(
        name="data_retention",
        rules=[
            {"field": "age", "operator": ">=", "value": 18},
            {"field": "consent", "operator": "==", "value": True},
        ],
    )
    
    # Check compliance
    result = await compliance.check(
        policy_name="data_retention",
        data={"age": 25, "consent": True},
    )
    
    # Generate compliance report
    report = await compliance.generate_report()
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class ComplianceError(Exception):
    """Compliance error."""
    pass


class PolicyViolation(ComplianceError):
    """Policy violation."""
    pass


class ComplianceStatus(str, Enum):
    """Compliance status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    PENDING = "pending"


class RuleOperator(str, Enum):
    """Rule operator."""
    EQUALS = "=="
    NOT_EQUALS = "!="
    GREATER_THAN = ">"
    GREATER_THAN_EQUALS = ">="
    LESS_THAN = "<"
    LESS_THAN_EQUALS = "<="
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MATCHES = "matches"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"


class Severity(str, Enum):
    """Violation severity."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyType(str, Enum):
    """Policy type."""
    DATA_PRIVACY = "data_privacy"
    SECURITY = "security"
    ACCESS_CONTROL = "access_control"
    DATA_RETENTION = "data_retention"
    REGULATORY = "regulatory"
    CUSTOM = "custom"


@dataclass
class Rule:
    """Compliance rule."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    field: str = ""
    operator: RuleOperator = RuleOperator.EQUALS
    value: Any = None
    severity: Severity = Severity.MEDIUM
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Policy:
    """Compliance policy."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    policy_type: PolicyType = PolicyType.CUSTOM
    rules: List[Rule] = field(default_factory=list)
    require_all: bool = True  # All rules must pass
    enabled: bool = True
    version: str = "1.0"
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleResult:
    """Rule evaluation result."""
    rule_id: str = ""
    rule_name: str = ""
    passed: bool = True
    actual_value: Any = None
    expected_value: Any = None
    message: str = ""
    severity: Severity = Severity.MEDIUM


@dataclass
class ComplianceResult:
    """Compliance check result."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str = ""
    policy_name: str = ""
    status: ComplianceStatus = ComplianceStatus.UNKNOWN
    rule_results: List[RuleResult] = field(default_factory=list)
    checked_at: datetime = field(default_factory=datetime.utcnow)
    duration: float = 0.0
    data_hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_compliant(self) -> bool:
        return self.status == ComplianceStatus.COMPLIANT
    
    @property
    def violations(self) -> List[RuleResult]:
        return [r for r in self.rule_results if not r.passed]


@dataclass
class ComplianceReport:
    """Compliance report."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    generated_at: datetime = field(default_factory=datetime.utcnow)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    results: List[ComplianceResult] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def compliance_rate(self) -> float:
        if not self.results:
            return 0.0
        compliant = sum(1 for r in self.results if r.is_compliant)
        return compliant / len(self.results) * 100


@dataclass
class ComplianceStats:
    """Compliance statistics."""
    total_checks: int = 0
    compliant_checks: int = 0
    non_compliant_checks: int = 0
    policies_count: int = 0
    rules_count: int = 0


# Policy store
class PolicyStore(ABC):
    """Policy storage."""
    
    @abstractmethod
    async def save(self, policy: Policy) -> None:
        pass
    
    @abstractmethod
    async def get(self, policy_id: str) -> Optional[Policy]:
        pass
    
    @abstractmethod
    async def get_by_name(self, name: str) -> Optional[Policy]:
        pass
    
    @abstractmethod
    async def delete(self, policy_id: str) -> bool:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Policy]:
        pass


class InMemoryPolicyStore(PolicyStore):
    """In-memory policy store."""
    
    def __init__(self):
        self._policies: Dict[str, Policy] = {}
        self._by_name: Dict[str, str] = {}
    
    async def save(self, policy: Policy) -> None:
        self._policies[policy.id] = policy
        self._by_name[policy.name] = policy.id
    
    async def get(self, policy_id: str) -> Optional[Policy]:
        return self._policies.get(policy_id)
    
    async def get_by_name(self, name: str) -> Optional[Policy]:
        policy_id = self._by_name.get(name)
        if policy_id:
            return self._policies.get(policy_id)
        return None
    
    async def delete(self, policy_id: str) -> bool:
        policy = self._policies.get(policy_id)
        if policy:
            del self._policies[policy_id]
            self._by_name.pop(policy.name, None)
            return True
        return False
    
    async def list_all(self) -> List[Policy]:
        return list(self._policies.values())


# Result store
class ResultStore(ABC):
    """Compliance result storage."""
    
    @abstractmethod
    async def save(self, result: ComplianceResult) -> None:
        pass
    
    @abstractmethod
    async def get(self, result_id: str) -> Optional[ComplianceResult]:
        pass
    
    @abstractmethod
    async def list_by_policy(self, policy_id: str, limit: int = 100) -> List[ComplianceResult]:
        pass
    
    @abstractmethod
    async def list_violations(self, limit: int = 100) -> List[ComplianceResult]:
        pass


class InMemoryResultStore(ResultStore):
    """In-memory result store."""
    
    def __init__(self, max_results: int = 10000):
        self._results: Dict[str, ComplianceResult] = {}
        self._by_policy: Dict[str, List[str]] = {}
        self._max_results = max_results
    
    async def save(self, result: ComplianceResult) -> None:
        self._results[result.id] = result
        
        if result.policy_id not in self._by_policy:
            self._by_policy[result.policy_id] = []
        
        self._by_policy[result.policy_id].append(result.id)
        
        # Trim
        if len(self._results) > self._max_results:
            oldest = list(self._results.keys())[0]
            del self._results[oldest]
    
    async def get(self, result_id: str) -> Optional[ComplianceResult]:
        return self._results.get(result_id)
    
    async def list_by_policy(self, policy_id: str, limit: int = 100) -> List[ComplianceResult]:
        ids = self._by_policy.get(policy_id, [])[-limit:]
        return [self._results[rid] for rid in ids if rid in self._results]
    
    async def list_violations(self, limit: int = 100) -> List[ComplianceResult]:
        violations = [
            r for r in self._results.values()
            if r.status == ComplianceStatus.NON_COMPLIANT
        ]
        return sorted(violations, key=lambda r: r.checked_at, reverse=True)[:limit]


# Rule evaluator
class RuleEvaluator:
    """Rule evaluator."""
    
    def _get_value(self, data: Dict[str, Any], field: str) -> Any:
        """Get value from nested field."""
        parts = field.split(".")
        value = data
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        
        return value
    
    def evaluate(self, rule: Rule, data: Dict[str, Any]) -> RuleResult:
        """Evaluate rule against data."""
        actual = self._get_value(data, rule.field)
        expected = rule.value
        passed = False
        message = ""
        
        try:
            if rule.operator == RuleOperator.EQUALS:
                passed = actual == expected
                message = f"{rule.field} equals {expected}"
            
            elif rule.operator == RuleOperator.NOT_EQUALS:
                passed = actual != expected
                message = f"{rule.field} not equals {expected}"
            
            elif rule.operator == RuleOperator.GREATER_THAN:
                passed = actual is not None and actual > expected
                message = f"{rule.field} > {expected}"
            
            elif rule.operator == RuleOperator.GREATER_THAN_EQUALS:
                passed = actual is not None and actual >= expected
                message = f"{rule.field} >= {expected}"
            
            elif rule.operator == RuleOperator.LESS_THAN:
                passed = actual is not None and actual < expected
                message = f"{rule.field} < {expected}"
            
            elif rule.operator == RuleOperator.LESS_THAN_EQUALS:
                passed = actual is not None and actual <= expected
                message = f"{rule.field} <= {expected}"
            
            elif rule.operator == RuleOperator.CONTAINS:
                passed = actual is not None and expected in actual
                message = f"{rule.field} contains {expected}"
            
            elif rule.operator == RuleOperator.NOT_CONTAINS:
                passed = actual is None or expected not in actual
                message = f"{rule.field} not contains {expected}"
            
            elif rule.operator == RuleOperator.MATCHES:
                if actual is not None and isinstance(expected, str):
                    passed = bool(re.match(expected, str(actual)))
                message = f"{rule.field} matches {expected}"
            
            elif rule.operator == RuleOperator.IN:
                if isinstance(expected, (list, tuple, set)):
                    passed = actual in expected
                message = f"{rule.field} in {expected}"
            
            elif rule.operator == RuleOperator.NOT_IN:
                if isinstance(expected, (list, tuple, set)):
                    passed = actual not in expected
                message = f"{rule.field} not in {expected}"
            
            elif rule.operator == RuleOperator.EXISTS:
                passed = actual is not None
                message = f"{rule.field} exists"
            
            elif rule.operator == RuleOperator.NOT_EXISTS:
                passed = actual is None
                message = f"{rule.field} not exists"
            
            else:
                message = f"Unknown operator: {rule.operator}"
        except Exception as e:
            message = f"Evaluation error: {e}"
            passed = False
        
        if not passed:
            message = f"VIOLATION: {message} (actual: {actual})"
        
        return RuleResult(
            rule_id=rule.id,
            rule_name=rule.name,
            passed=passed,
            actual_value=actual,
            expected_value=expected,
            message=message,
            severity=rule.severity,
        )


# Compliance engine
class ComplianceEngine:
    """Compliance engine."""
    
    def __init__(
        self,
        policy_store: Optional[PolicyStore] = None,
        result_store: Optional[ResultStore] = None,
    ):
        self._policy_store = policy_store or InMemoryPolicyStore()
        self._result_store = result_store or InMemoryResultStore()
        self._evaluator = RuleEvaluator()
        self._stats = ComplianceStats()
        self._listeners: List[Callable] = []
    
    async def add_policy(
        self,
        name: str,
        rules: List[Dict[str, Any]],
        policy_type: PolicyType = PolicyType.CUSTOM,
        description: str = "",
        require_all: bool = True,
        **kwargs,
    ) -> Policy:
        """Add compliance policy."""
        rule_objects = []
        
        for rule_data in rules:
            operator = rule_data.get("operator", "==")
            if isinstance(operator, str) and not isinstance(operator, RuleOperator):
                operator = RuleOperator(operator)
            
            rule = Rule(
                name=rule_data.get("name", rule_data.get("field", "")),
                field=rule_data.get("field", ""),
                operator=operator,
                value=rule_data.get("value"),
                severity=Severity(rule_data.get("severity", "medium")),
            )
            rule_objects.append(rule)
        
        policy = Policy(
            name=name,
            description=description,
            policy_type=policy_type,
            rules=rule_objects,
            require_all=require_all,
            **kwargs,
        )
        
        await self._policy_store.save(policy)
        
        self._stats.policies_count += 1
        self._stats.rules_count += len(rule_objects)
        
        logger.info(f"Policy added: {name} ({len(rule_objects)} rules)")
        
        return policy
    
    async def get_policy(self, name: str) -> Optional[Policy]:
        """Get policy by name."""
        return await self._policy_store.get_by_name(name)
    
    async def remove_policy(self, name: str) -> bool:
        """Remove policy."""
        policy = await self._policy_store.get_by_name(name)
        
        if policy:
            result = await self._policy_store.delete(policy.id)
            if result:
                self._stats.policies_count = max(0, self._stats.policies_count - 1)
                self._stats.rules_count = max(0, self._stats.rules_count - len(policy.rules))
            return result
        
        return False
    
    async def list_policies(self) -> List[Policy]:
        """List all policies."""
        return await self._policy_store.list_all()
    
    async def check(
        self,
        policy_name: str,
        data: Dict[str, Any],
        raise_on_violation: bool = False,
    ) -> ComplianceResult:
        """Check compliance against policy."""
        start = time.time()
        
        policy = await self._policy_store.get_by_name(policy_name)
        
        if not policy:
            raise ComplianceError(f"Policy not found: {policy_name}")
        
        if not policy.enabled:
            return ComplianceResult(
                policy_id=policy.id,
                policy_name=policy.name,
                status=ComplianceStatus.COMPLIANT,
                duration=time.time() - start,
            )
        
        # Check effective dates
        now = datetime.utcnow()
        
        if policy.effective_from and now < policy.effective_from:
            return ComplianceResult(
                policy_id=policy.id,
                policy_name=policy.name,
                status=ComplianceStatus.PENDING,
                duration=time.time() - start,
            )
        
        if policy.effective_until and now > policy.effective_until:
            return ComplianceResult(
                policy_id=policy.id,
                policy_name=policy.name,
                status=ComplianceStatus.COMPLIANT,
                duration=time.time() - start,
            )
        
        # Evaluate rules
        rule_results = []
        
        for rule in policy.rules:
            if not rule.enabled:
                continue
            
            result = self._evaluator.evaluate(rule, data)
            rule_results.append(result)
        
        # Determine status
        passed_count = sum(1 for r in rule_results if r.passed)
        total_count = len(rule_results)
        
        if total_count == 0:
            status = ComplianceStatus.COMPLIANT
        elif policy.require_all:
            status = ComplianceStatus.COMPLIANT if passed_count == total_count else ComplianceStatus.NON_COMPLIANT
        else:
            if passed_count == total_count:
                status = ComplianceStatus.COMPLIANT
            elif passed_count > 0:
                status = ComplianceStatus.PARTIAL
            else:
                status = ComplianceStatus.NON_COMPLIANT
        
        # Create data hash
        data_hash = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]
        
        result = ComplianceResult(
            policy_id=policy.id,
            policy_name=policy.name,
            status=status,
            rule_results=rule_results,
            duration=time.time() - start,
            data_hash=data_hash,
        )
        
        await self._result_store.save(result)
        
        # Update stats
        self._stats.total_checks += 1
        if status == ComplianceStatus.COMPLIANT:
            self._stats.compliant_checks += 1
        else:
            self._stats.non_compliant_checks += 1
        
        # Notify listeners
        await self._notify_listeners(result)
        
        if raise_on_violation and not result.is_compliant:
            violations = result.violations
            raise PolicyViolation(
                f"Policy {policy_name} violated: {len(violations)} rule(s) failed"
            )
        
        return result
    
    async def check_all(
        self,
        data: Dict[str, Any],
    ) -> List[ComplianceResult]:
        """Check compliance against all policies."""
        policies = await self._policy_store.list_all()
        results = []
        
        for policy in policies:
            if policy.enabled:
                result = await self.check(policy.name, data)
                results.append(result)
        
        return results
    
    async def generate_report(
        self,
        title: str = "Compliance Report",
        period_days: int = 30,
    ) -> ComplianceReport:
        """Generate compliance report."""
        period_start = datetime.utcnow() - timedelta(days=period_days)
        period_end = datetime.utcnow()
        
        # Get all violations
        violations = await self._result_store.list_violations(limit=1000)
        
        # Filter by period
        results = [
            v for v in violations
            if v.checked_at >= period_start
        ]
        
        # Calculate summary
        total = len(results)
        by_severity = {}
        by_policy = {}
        
        for result in results:
            for violation in result.violations:
                severity = violation.severity.value
                by_severity[severity] = by_severity.get(severity, 0) + 1
            
            by_policy[result.policy_name] = by_policy.get(result.policy_name, 0) + 1
        
        summary = {
            "total_violations": total,
            "by_severity": by_severity,
            "by_policy": by_policy,
            "period_days": period_days,
        }
        
        report = ComplianceReport(
            title=title,
            period_start=period_start,
            period_end=period_end,
            results=results,
            summary=summary,
        )
        
        return report
    
    async def get_violations(self, limit: int = 100) -> List[ComplianceResult]:
        """Get recent violations."""
        return await self._result_store.list_violations(limit)
    
    def add_listener(self, listener: Callable) -> None:
        """Add compliance check listener."""
        self._listeners.append(listener)
    
    async def _notify_listeners(self, result: ComplianceResult) -> None:
        """Notify listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(result)
                else:
                    listener(result)
            except Exception as e:
                logger.error(f"Listener error: {e}")
    
    def get_stats(self) -> ComplianceStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_compliance_engine() -> ComplianceEngine:
    """Create compliance engine."""
    return ComplianceEngine()


def create_policy(
    name: str,
    rules: List[Rule],
    **kwargs,
) -> Policy:
    """Create policy."""
    return Policy(name=name, rules=rules, **kwargs)


def create_rule(
    field: str,
    operator: Union[str, RuleOperator],
    value: Any,
    **kwargs,
) -> Rule:
    """Create rule."""
    if isinstance(operator, str):
        operator = RuleOperator(operator)
    
    return Rule(field=field, operator=operator, value=value, **kwargs)


__all__ = [
    # Exceptions
    "ComplianceError",
    "PolicyViolation",
    # Enums
    "ComplianceStatus",
    "RuleOperator",
    "Severity",
    "PolicyType",
    # Data classes
    "Rule",
    "Policy",
    "RuleResult",
    "ComplianceResult",
    "ComplianceReport",
    "ComplianceStats",
    # Stores
    "PolicyStore",
    "InMemoryPolicyStore",
    "ResultStore",
    "InMemoryResultStore",
    # Evaluator
    "RuleEvaluator",
    # Engine
    "ComplianceEngine",
    # Factory functions
    "create_compliance_engine",
    "create_policy",
    "create_rule",
]
