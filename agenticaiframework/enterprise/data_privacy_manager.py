"""
Enterprise Data Privacy Manager Module.

Data anonymization, PII detection, consent management,
data retention policies, and privacy compliance.

Example:
    # Create data privacy manager
    privacy = create_data_privacy_manager()
    
    # Register PII field
    await privacy.register_pii_field(
        name="email",
        pii_type=PIIType.EMAIL,
        sensitivity=SensitivityLevel.HIGH,
    )
    
    # Anonymize data
    result = await privacy.anonymize({
        "user_id": "123",
        "email": "john@example.com",
        "ssn": "123-45-6789",
    })
    
    # Record consent
    await privacy.record_consent(
        subject_id="user123",
        purpose="marketing",
        granted=True,
    )
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
import string
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
)

logger = logging.getLogger(__name__)


class PrivacyError(Exception):
    """Privacy error."""
    pass


class ConsentError(PrivacyError):
    """Consent error."""
    pass


class RetentionError(PrivacyError):
    """Retention policy error."""
    pass


class PIIType(str, Enum):
    """PII types."""
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    IP_ADDRESS = "ip_address"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    MEDICAL = "medical"
    BIOMETRIC = "biometric"
    FINANCIAL = "financial"
    CUSTOM = "custom"


class SensitivityLevel(str, Enum):
    """Sensitivity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnonymizationMethod(str, Enum):
    """Anonymization methods."""
    MASK = "mask"
    HASH = "hash"
    ENCRYPT = "encrypt"
    REDACT = "redact"
    TOKENIZE = "tokenize"
    GENERALIZE = "generalize"
    PSEUDONYMIZE = "pseudonymize"


class ConsentStatus(str, Enum):
    """Consent status."""
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    PENDING = "pending"
    EXPIRED = "expired"


class RetentionAction(str, Enum):
    """Retention actions."""
    DELETE = "delete"
    ARCHIVE = "archive"
    ANONYMIZE = "anonymize"
    RETAIN = "retain"


@dataclass
class PIIField:
    """PII field definition."""
    name: str = ""
    pii_type: PIIType = PIIType.CUSTOM
    sensitivity: SensitivityLevel = SensitivityLevel.MEDIUM
    
    # Detection
    patterns: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    # Anonymization
    anonymization_method: AnonymizationMethod = AnonymizationMethod.MASK
    mask_char: str = "*"
    mask_length: int = -1  # -1 = same as original
    
    # Metadata
    description: str = ""


@dataclass
class DetectedPII:
    """Detected PII occurrence."""
    field_path: str = ""
    pii_type: PIIType = PIIType.CUSTOM
    sensitivity: SensitivityLevel = SensitivityLevel.MEDIUM
    
    value: str = ""
    start_index: int = 0
    end_index: int = 0
    
    confidence: float = 1.0


@dataclass
class Consent:
    """Consent record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    subject_id: str = ""
    purpose: str = ""
    
    # Status
    status: ConsentStatus = ConsentStatus.PENDING
    
    # Dates
    granted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    
    # Details
    scope: List[str] = field(default_factory=list)
    data_categories: List[str] = field(default_factory=list)
    
    # Source
    consent_source: str = ""  # web form, email, etc.
    ip_address: str = ""
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetentionPolicy:
    """Data retention policy."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    name: str = ""
    data_category: str = ""
    
    # Retention
    retention_days: int = 365
    action: RetentionAction = RetentionAction.DELETE
    
    # Conditions
    applies_to_deleted_users: bool = True
    applies_to_inactive_users: bool = True
    inactive_days: int = 365
    
    # Schedule
    check_frequency_hours: int = 24
    last_check_at: Optional[datetime] = None
    
    # Metadata
    legal_basis: str = ""
    description: str = ""


@dataclass
class DataSubjectRequest:
    """Data subject request (GDPR/CCPA)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    subject_id: str = ""
    request_type: str = ""  # access, deletion, rectification, portability
    
    # Status
    status: str = "pending"  # pending, processing, completed, rejected
    
    # Dates
    requested_at: datetime = field(default_factory=datetime.utcnow)
    deadline: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Details
    description: str = ""
    result: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PrivacyStats:
    """Privacy statistics."""
    pii_fields_registered: int = 0
    total_detections: int = 0
    total_anonymizations: int = 0
    
    active_consents: int = 0
    withdrawn_consents: int = 0
    
    pending_requests: int = 0
    completed_requests: int = 0


# PII detector
class PIIDetector(ABC):
    """PII detector."""
    
    @abstractmethod
    async def detect(self, data: Dict[str, Any]) -> List[DetectedPII]:
        pass


class PatternPIIDetector(PIIDetector):
    """Pattern-based PII detector."""
    
    # Default patterns
    DEFAULT_PATTERNS: Dict[PIIType, List[str]] = {
        PIIType.EMAIL: [r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"],
        PIIType.PHONE: [r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", r"\+\d{1,3}[-.]?\d{3,14}\b"],
        PIIType.SSN: [r"\b\d{3}-\d{2}-\d{4}\b"],
        PIIType.CREDIT_CARD: [r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"],
        PIIType.IP_ADDRESS: [r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"],
    }
    
    def __init__(self, custom_fields: Optional[List[PIIField]] = None):
        self._fields = custom_fields or []
        self._patterns: Dict[PIIType, List[Pattern]] = {}
        
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile patterns."""
        # Default patterns
        for pii_type, patterns in self.DEFAULT_PATTERNS.items():
            self._patterns[pii_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
        
        # Custom patterns
        for pii_field in self._fields:
            if pii_field.patterns:
                self._patterns[pii_field.pii_type] = [
                    re.compile(p, re.IGNORECASE) for p in pii_field.patterns
                ]
    
    async def detect(self, data: Dict[str, Any]) -> List[DetectedPII]:
        """Detect PII in data."""
        detected = []
        
        def scan_value(value: Any, path: str) -> None:
            if isinstance(value, str):
                for pii_type, patterns in self._patterns.items():
                    for pattern in patterns:
                        for match in pattern.finditer(value):
                            detected.append(DetectedPII(
                                field_path=path,
                                pii_type=pii_type,
                                sensitivity=self._get_sensitivity(pii_type),
                                value=match.group(),
                                start_index=match.start(),
                                end_index=match.end(),
                            ))
            
            elif isinstance(value, dict):
                for k, v in value.items():
                    scan_value(v, f"{path}.{k}" if path else k)
            
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    scan_value(v, f"{path}[{i}]")
        
        scan_value(data, "")
        
        return detected
    
    def _get_sensitivity(self, pii_type: PIIType) -> SensitivityLevel:
        """Get sensitivity level for PII type."""
        HIGH_SENSITIVITY = {PIIType.SSN, PIIType.CREDIT_CARD, PIIType.MEDICAL, PIIType.BIOMETRIC}
        CRITICAL_SENSITIVITY = {PIIType.PASSPORT, PIIType.FINANCIAL}
        
        if pii_type in CRITICAL_SENSITIVITY:
            return SensitivityLevel.CRITICAL
        elif pii_type in HIGH_SENSITIVITY:
            return SensitivityLevel.HIGH
        else:
            return SensitivityLevel.MEDIUM


# Anonymizer
class Anonymizer(ABC):
    """Data anonymizer."""
    
    @abstractmethod
    async def anonymize(
        self,
        value: str,
        method: AnonymizationMethod,
        **options,
    ) -> str:
        pass


class DefaultAnonymizer(Anonymizer):
    """Default anonymizer."""
    
    def __init__(self, salt: str = ""):
        self._salt = salt or str(uuid.uuid4())
        self._token_map: Dict[str, str] = {}
    
    async def anonymize(
        self,
        value: str,
        method: AnonymizationMethod,
        **options,
    ) -> str:
        """Anonymize value."""
        if method == AnonymizationMethod.MASK:
            return self._mask(value, options.get("mask_char", "*"))
        
        elif method == AnonymizationMethod.HASH:
            return self._hash(value)
        
        elif method == AnonymizationMethod.REDACT:
            return options.get("redact_text", "[REDACTED]")
        
        elif method == AnonymizationMethod.TOKENIZE:
            return self._tokenize(value)
        
        elif method == AnonymizationMethod.GENERALIZE:
            return self._generalize(value, options.get("level", 1))
        
        elif method == AnonymizationMethod.PSEUDONYMIZE:
            return self._pseudonymize(value)
        
        return value
    
    def _mask(self, value: str, mask_char: str = "*") -> str:
        """Mask value."""
        if len(value) <= 4:
            return mask_char * len(value)
        
        # Keep first and last 2 characters
        return value[:2] + mask_char * (len(value) - 4) + value[-2:]
    
    def _hash(self, value: str) -> str:
        """Hash value."""
        salted = f"{self._salt}:{value}"
        return hashlib.sha256(salted.encode()).hexdigest()[:16]
    
    def _tokenize(self, value: str) -> str:
        """Tokenize value."""
        if value in self._token_map:
            return self._token_map[value]
        
        token = "TOK_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self._token_map[value] = token
        
        return token
    
    def _generalize(self, value: str, level: int = 1) -> str:
        """Generalize value."""
        # Email: keep domain only
        if "@" in value:
            parts = value.split("@")
            if level == 1:
                return f"***@{parts[-1]}"
            else:
                domain = parts[-1].split(".")[-1]
                return f"***@***.{domain}"
        
        # Number: round to nearest 10^level
        if value.isdigit():
            num = int(value)
            divisor = 10 ** level
            return str((num // divisor) * divisor)
        
        return value
    
    def _pseudonymize(self, value: str) -> str:
        """Pseudonymize with consistent mapping."""
        return self._tokenize(value)


# Privacy store
class PrivacyStore(ABC):
    """Privacy data store."""
    
    @abstractmethod
    async def save_consent(self, consent: Consent) -> None:
        pass
    
    @abstractmethod
    async def get_consent(self, subject_id: str, purpose: str) -> Optional[Consent]:
        pass
    
    @abstractmethod
    async def get_consents_for_subject(self, subject_id: str) -> List[Consent]:
        pass
    
    @abstractmethod
    async def save_request(self, request: DataSubjectRequest) -> None:
        pass
    
    @abstractmethod
    async def get_pending_requests(self) -> List[DataSubjectRequest]:
        pass


class InMemoryPrivacyStore(PrivacyStore):
    """In-memory privacy store."""
    
    def __init__(self):
        self._consents: Dict[str, Consent] = {}
        self._requests: Dict[str, DataSubjectRequest] = {}
    
    async def save_consent(self, consent: Consent) -> None:
        key = f"{consent.subject_id}:{consent.purpose}"
        self._consents[key] = consent
    
    async def get_consent(self, subject_id: str, purpose: str) -> Optional[Consent]:
        key = f"{subject_id}:{purpose}"
        return self._consents.get(key)
    
    async def get_consents_for_subject(self, subject_id: str) -> List[Consent]:
        return [
            c for c in self._consents.values()
            if c.subject_id == subject_id
        ]
    
    async def save_request(self, request: DataSubjectRequest) -> None:
        self._requests[request.id] = request
    
    async def get_pending_requests(self) -> List[DataSubjectRequest]:
        return [
            r for r in self._requests.values()
            if r.status == "pending"
        ]


# Data privacy manager
class DataPrivacyManager:
    """Data privacy manager."""
    
    def __init__(
        self,
        store: Optional[PrivacyStore] = None,
        detector: Optional[PIIDetector] = None,
        anonymizer: Optional[Anonymizer] = None,
    ):
        self._store = store or InMemoryPrivacyStore()
        self._anonymizer = anonymizer or DefaultAnonymizer()
        
        self._pii_fields: Dict[str, PIIField] = {}
        self._retention_policies: Dict[str, RetentionPolicy] = {}
        self._listeners: List[Callable] = []
        
        # Initialize detector after registering fields
        self._detector = detector
        
        # Statistics
        self._detection_count = 0
        self._anonymization_count = 0
    
    async def register_pii_field(
        self,
        name: str,
        pii_type: PIIType,
        sensitivity: SensitivityLevel = SensitivityLevel.MEDIUM,
        anonymization_method: AnonymizationMethod = AnonymizationMethod.MASK,
        **kwargs,
    ) -> PIIField:
        """Register a PII field."""
        pii_field = PIIField(
            name=name,
            pii_type=pii_type,
            sensitivity=sensitivity,
            anonymization_method=anonymization_method,
            **kwargs,
        )
        
        self._pii_fields[name] = pii_field
        
        logger.info(f"PII field registered: {name} ({pii_type.value})")
        
        return pii_field
    
    async def detect_pii(self, data: Dict[str, Any]) -> List[DetectedPII]:
        """Detect PII in data."""
        if not self._detector:
            self._detector = PatternPIIDetector(list(self._pii_fields.values()))
        
        detected = await self._detector.detect(data)
        self._detection_count += len(detected)
        
        return detected
    
    async def anonymize(
        self,
        data: Dict[str, Any],
        fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Anonymize data."""
        result = dict(data)
        
        # Detect PII
        detected = await self.detect_pii(data)
        
        for pii in detected:
            if fields and pii.field_path not in fields:
                continue
            
            # Get field config
            pii_field = self._pii_fields.get(pii.field_path)
            method = pii_field.anonymization_method if pii_field else AnonymizationMethod.MASK
            
            # Anonymize
            anonymized = await self._anonymizer.anonymize(pii.value, method)
            
            # Update result
            self._set_nested_value(result, pii.field_path, anonymized)
            self._anonymization_count += 1
        
        return result
    
    async def anonymize_field(
        self,
        value: str,
        method: AnonymizationMethod = AnonymizationMethod.MASK,
        **options,
    ) -> str:
        """Anonymize a single field value."""
        return await self._anonymizer.anonymize(value, method, **options)
    
    async def record_consent(
        self,
        subject_id: str,
        purpose: str,
        granted: bool = True,
        expires_in_days: Optional[int] = None,
        scope: Optional[List[str]] = None,
        **kwargs,
    ) -> Consent:
        """Record consent."""
        consent = Consent(
            subject_id=subject_id,
            purpose=purpose,
            status=ConsentStatus.GRANTED if granted else ConsentStatus.DENIED,
            granted_at=datetime.utcnow() if granted else None,
            scope=scope or [],
            **kwargs,
        )
        
        if expires_in_days:
            consent.expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        
        await self._store.save_consent(consent)
        await self._emit_event("consent_recorded", {
            "subject_id": subject_id,
            "purpose": purpose,
            "granted": granted,
        })
        
        logger.info(f"Consent recorded: {subject_id} - {purpose} ({consent.status.value})")
        
        return consent
    
    async def withdraw_consent(
        self,
        subject_id: str,
        purpose: str,
    ) -> Optional[Consent]:
        """Withdraw consent."""
        consent = await self._store.get_consent(subject_id, purpose)
        
        if consent:
            consent.status = ConsentStatus.WITHDRAWN
            consent.withdrawn_at = datetime.utcnow()
            await self._store.save_consent(consent)
            
            await self._emit_event("consent_withdrawn", {
                "subject_id": subject_id,
                "purpose": purpose,
            })
            
            logger.info(f"Consent withdrawn: {subject_id} - {purpose}")
        
        return consent
    
    async def check_consent(
        self,
        subject_id: str,
        purpose: str,
    ) -> Tuple[bool, Optional[Consent]]:
        """Check if consent is granted."""
        consent = await self._store.get_consent(subject_id, purpose)
        
        if not consent:
            return False, None
        
        # Check status
        if consent.status != ConsentStatus.GRANTED:
            return False, consent
        
        # Check expiration
        if consent.expires_at and consent.expires_at < datetime.utcnow():
            consent.status = ConsentStatus.EXPIRED
            await self._store.save_consent(consent)
            return False, consent
        
        return True, consent
    
    async def get_consents(self, subject_id: str) -> List[Consent]:
        """Get all consents for a subject."""
        return await self._store.get_consents_for_subject(subject_id)
    
    async def add_retention_policy(
        self,
        name: str,
        data_category: str,
        retention_days: int,
        action: RetentionAction = RetentionAction.DELETE,
        **kwargs,
    ) -> RetentionPolicy:
        """Add retention policy."""
        policy = RetentionPolicy(
            name=name,
            data_category=data_category,
            retention_days=retention_days,
            action=action,
            **kwargs,
        )
        
        self._retention_policies[name] = policy
        
        logger.info(f"Retention policy added: {name} ({retention_days} days)")
        
        return policy
    
    async def check_retention(
        self,
        data_category: str,
        created_at: datetime,
    ) -> Tuple[bool, Optional[RetentionAction]]:
        """Check if data should be acted upon based on retention policy."""
        for policy in self._retention_policies.values():
            if policy.data_category == data_category:
                age_days = (datetime.utcnow() - created_at).days
                
                if age_days > policy.retention_days:
                    return True, policy.action
        
        return False, None
    
    async def create_data_subject_request(
        self,
        subject_id: str,
        request_type: str,
        description: str = "",
        deadline_days: int = 30,
    ) -> DataSubjectRequest:
        """Create data subject request (GDPR/CCPA)."""
        request = DataSubjectRequest(
            subject_id=subject_id,
            request_type=request_type,
            description=description,
            deadline=datetime.utcnow() + timedelta(days=deadline_days),
        )
        
        await self._store.save_request(request)
        await self._emit_event("data_subject_request_created", {
            "request_id": request.id,
            "subject_id": subject_id,
            "type": request_type,
        })
        
        logger.info(f"Data subject request created: {request.id} ({request_type})")
        
        return request
    
    async def complete_data_subject_request(
        self,
        request_id: str,
        result: Dict[str, Any],
    ) -> None:
        """Complete a data subject request."""
        # In real implementation, fetch and update request
        await self._emit_event("data_subject_request_completed", {
            "request_id": request_id,
            "result": result,
        })
        
        logger.info(f"Data subject request completed: {request_id}")
    
    async def get_pending_requests(self) -> List[DataSubjectRequest]:
        """Get pending data subject requests."""
        return await self._store.get_pending_requests()
    
    async def get_stats(self) -> PrivacyStats:
        """Get privacy statistics."""
        return PrivacyStats(
            pii_fields_registered=len(self._pii_fields),
            total_detections=self._detection_count,
            total_anonymizations=self._anonymization_count,
        )
    
    def _set_nested_value(
        self,
        data: Dict[str, Any],
        path: str,
        value: Any,
    ) -> None:
        """Set nested value in dict."""
        if not path:
            return
        
        parts = path.replace("[", ".").replace("]", "").split(".")
        parts = [p for p in parts if p]
        
        current = data
        
        for i, part in enumerate(parts[:-1]):
            if part.isdigit():
                part = int(part)
            
            if isinstance(current, list) and isinstance(part, int):
                current = current[part]
            elif isinstance(current, dict):
                current = current.get(part, {})
        
        final_key = parts[-1]
        
        if final_key.isdigit():
            final_key = int(final_key)
        
        if isinstance(current, list) and isinstance(final_key, int):
            current[final_key] = value
        elif isinstance(current, dict):
            current[final_key] = value
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    async def _emit_event(self, event: str, data: Dict[str, Any]) -> None:
        """Emit event to listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, data)
                else:
                    listener(event, data)
            except Exception as e:
                logger.error(f"Listener error: {e}")


# Privacy decorators
def require_consent(purpose: str):
    """Decorator to require consent before processing."""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # Extract subject_id from kwargs or first arg
            subject_id = kwargs.get("subject_id")
            
            if not subject_id and args:
                subject_id = getattr(args[0], "subject_id", None)
            
            if not subject_id:
                raise ConsentError("Subject ID required for consent check")
            
            # Get manager from context or kwargs
            manager = kwargs.get("privacy_manager")
            
            if manager:
                granted, _ = await manager.check_consent(subject_id, purpose)
                
                if not granted:
                    raise ConsentError(f"Consent not granted for: {purpose}")
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def anonymize_result(*fields: str):
    """Decorator to anonymize result fields."""
    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            manager = kwargs.get("privacy_manager")
            
            if manager and isinstance(result, dict):
                result = await manager.anonymize(result, list(fields) if fields else None)
            
            return result
        
        return wrapper
    
    return decorator


# Factory functions
def create_data_privacy_manager() -> DataPrivacyManager:
    """Create data privacy manager."""
    return DataPrivacyManager()


def create_pii_detector(
    custom_fields: Optional[List[PIIField]] = None,
) -> PatternPIIDetector:
    """Create PII detector."""
    return PatternPIIDetector(custom_fields)


def create_anonymizer(salt: str = "") -> DefaultAnonymizer:
    """Create anonymizer."""
    return DefaultAnonymizer(salt)


def create_retention_policy(
    name: str,
    data_category: str,
    retention_days: int,
    action: RetentionAction = RetentionAction.DELETE,
) -> RetentionPolicy:
    """Create retention policy."""
    return RetentionPolicy(
        name=name,
        data_category=data_category,
        retention_days=retention_days,
        action=action,
    )


__all__ = [
    # Exceptions
    "PrivacyError",
    "ConsentError",
    "RetentionError",
    # Enums
    "PIIType",
    "SensitivityLevel",
    "AnonymizationMethod",
    "ConsentStatus",
    "RetentionAction",
    # Data classes
    "PIIField",
    "DetectedPII",
    "Consent",
    "RetentionPolicy",
    "DataSubjectRequest",
    "PrivacyStats",
    # Detector
    "PIIDetector",
    "PatternPIIDetector",
    # Anonymizer
    "Anonymizer",
    "DefaultAnonymizer",
    # Store
    "PrivacyStore",
    "InMemoryPrivacyStore",
    # Manager
    "DataPrivacyManager",
    # Decorators
    "require_consent",
    "anonymize_result",
    # Factory functions
    "create_data_privacy_manager",
    "create_pii_detector",
    "create_anonymizer",
    "create_retention_policy",
]
