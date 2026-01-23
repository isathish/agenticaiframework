"""
Enterprise Data Masking Module.

PII masking, tokenization, anonymization,
and data protection utilities.

Example:
    # Create masker
    masker = create_data_masker()
    
    # Register patterns
    masker.register_pattern("ssn", r"\d{3}-\d{2}-\d{4}")
    masker.register_pattern("email", r"[\w.-]+@[\w.-]+\.\w+")
    
    # Mask data
    masked = masker.mask(data, fields=["ssn", "email"])
    
    # Tokenize for reversible masking
    tokenized, tokens = await masker.tokenize(data, fields=["credit_card"])
    
    # Detokenize when needed
    original = await masker.detokenize(tokenized, tokens)
"""

from __future__ import annotations

import functools
import hashlib
import random
import re
import string
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
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


class MaskingError(Exception):
    """Masking error."""
    pass


class TokenNotFoundError(MaskingError):
    """Token not found."""
    pass


class MaskingStrategy(str, Enum):
    """Masking strategies."""
    REDACT = "redact"          # Replace with [REDACTED]
    MASK = "mask"              # Replace with ****
    PARTIAL = "partial"        # Show partial (e.g., ****1234)
    HASH = "hash"              # One-way hash
    TOKENIZE = "tokenize"      # Reversible token
    ENCRYPT = "encrypt"        # Encrypted value
    RANDOMIZE = "randomize"    # Random replacement
    GENERALIZE = "generalize"  # Generalize (e.g., exact age -> age range)
    NULL = "null"              # Replace with null


class DataType(str, Enum):
    """Data types for detection."""
    SSN = "ssn"
    EMAIL = "email"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    ADDRESS = "address"
    NAME = "name"
    CUSTOM = "custom"


@dataclass
class MaskingRule:
    """Masking rule definition."""
    name: str
    pattern: Optional[str] = None
    data_type: DataType = DataType.CUSTOM
    strategy: MaskingStrategy = MaskingStrategy.MASK
    replacement: Optional[str] = None
    mask_char: str = "*"
    visible_start: int = 0
    visible_end: int = 0
    preserve_format: bool = False
    fields: List[str] = field(default_factory=list)


@dataclass
class Token:
    """Token for reversible masking."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_value: str = ""
    token_value: str = ""
    data_type: DataType = DataType.CUSTOM
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MaskingResult:
    """Result of masking operation."""
    original_fields: int = 0
    masked_fields: int = 0
    patterns_matched: Dict[str, int] = field(default_factory=dict)
    tokens_created: int = 0


@dataclass
class DetectionResult:
    """PII detection result."""
    field: str
    value: str
    data_type: DataType
    confidence: float = 1.0
    start_pos: int = 0
    end_pos: int = 0


# Token storage
class TokenStorage(ABC):
    """Abstract token storage."""
    
    @abstractmethod
    async def save(self, token: Token) -> None:
        """Save token."""
        pass
    
    @abstractmethod
    async def get(self, token_value: str) -> Optional[Token]:
        """Get token."""
        pass
    
    @abstractmethod
    async def delete(self, token_value: str) -> bool:
        """Delete token."""
        pass


class InMemoryTokenStorage(TokenStorage):
    """In-memory token storage."""
    
    def __init__(self):
        self._tokens: Dict[str, Token] = {}
    
    async def save(self, token: Token) -> None:
        self._tokens[token.token_value] = token
    
    async def get(self, token_value: str) -> Optional[Token]:
        return self._tokens.get(token_value)
    
    async def delete(self, token_value: str) -> bool:
        if token_value in self._tokens:
            del self._tokens[token_value]
            return True
        return False


# Built-in patterns
DEFAULT_PATTERNS: Dict[DataType, str] = {
    DataType.SSN: r"\b\d{3}-\d{2}-\d{4}\b",
    DataType.EMAIL: r"\b[\w.-]+@[\w.-]+\.\w+\b",
    DataType.PHONE: r"\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b",
    DataType.CREDIT_CARD: r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
    DataType.IP_ADDRESS: r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    DataType.DATE_OF_BIRTH: r"\b\d{1,2}/\d{1,2}/\d{4}\b",
}


# Masking functions
def _mask_with_char(
    value: str,
    mask_char: str = "*",
    visible_start: int = 0,
    visible_end: int = 0,
) -> str:
    """Mask with character."""
    if not value:
        return value
    
    length = len(value)
    mask_length = length - visible_start - visible_end
    
    if mask_length <= 0:
        return mask_char * length
    
    start = value[:visible_start] if visible_start > 0 else ""
    end = value[-visible_end:] if visible_end > 0 else ""
    middle = mask_char * mask_length
    
    return start + middle + end


def _hash_value(value: str, salt: str = "") -> str:
    """Hash value."""
    data = (value + salt).encode()
    return hashlib.sha256(data).hexdigest()[:16]


def _randomize_value(value: str, preserve_format: bool = False) -> str:
    """Randomize value."""
    if not preserve_format:
        return ''.join(random.choices(string.ascii_letters + string.digits, k=len(value)))
    
    result = []
    for char in value:
        if char.isdigit():
            result.append(random.choice(string.digits))
        elif char.isalpha():
            if char.isupper():
                result.append(random.choice(string.ascii_uppercase))
            else:
                result.append(random.choice(string.ascii_lowercase))
        else:
            result.append(char)
    
    return ''.join(result)


def _generalize_value(value: str, data_type: DataType) -> str:
    """Generalize value."""
    if data_type == DataType.DATE_OF_BIRTH:
        # Convert to year range
        try:
            year = int(value.split("/")[-1])
            decade = (year // 10) * 10
            return f"{decade}s"
        except:
            return "[DATE]"
    
    elif data_type == DataType.ADDRESS:
        # Just city/state
        parts = value.split(",")
        if len(parts) >= 2:
            return parts[-1].strip()
        return "[LOCATION]"
    
    return "[GENERALIZED]"


# Data masker
class DataMasker:
    """
    Data masking service.
    """
    
    def __init__(
        self,
        token_storage: Optional[TokenStorage] = None,
        default_strategy: MaskingStrategy = MaskingStrategy.MASK,
        salt: str = "",
    ):
        self._token_storage = token_storage or InMemoryTokenStorage()
        self._default_strategy = default_strategy
        self._salt = salt or str(uuid.uuid4())
        self._rules: Dict[str, MaskingRule] = {}
        self._compiled_patterns: Dict[str, Pattern] = {}
        
        # Register default patterns
        for data_type, pattern in DEFAULT_PATTERNS.items():
            self.register_pattern(
                data_type.value,
                pattern,
                data_type=data_type,
            )
    
    def register_pattern(
        self,
        name: str,
        pattern: str,
        data_type: DataType = DataType.CUSTOM,
        strategy: MaskingStrategy = MaskingStrategy.MASK,
        **kwargs,
    ) -> None:
        """
        Register masking pattern.
        
        Args:
            name: Pattern name
            pattern: Regex pattern
            data_type: Data type
            strategy: Masking strategy
            **kwargs: Additional rule options
        """
        rule = MaskingRule(
            name=name,
            pattern=pattern,
            data_type=data_type,
            strategy=strategy,
            **kwargs,
        )
        self._rules[name] = rule
        self._compiled_patterns[name] = re.compile(pattern, re.IGNORECASE)
    
    def register_rule(self, rule: MaskingRule) -> None:
        """Register masking rule."""
        self._rules[rule.name] = rule
        if rule.pattern:
            self._compiled_patterns[rule.name] = re.compile(
                rule.pattern, re.IGNORECASE
            )
    
    def mask(
        self,
        data: Any,
        fields: Optional[List[str]] = None,
        strategy: Optional[MaskingStrategy] = None,
        rules: Optional[List[str]] = None,
    ) -> Any:
        """
        Mask data.
        
        Args:
            data: Data to mask
            fields: Specific fields to mask
            strategy: Override strategy
            rules: Specific rules to apply
            
        Returns:
            Masked data
        """
        if isinstance(data, dict):
            return self._mask_dict(data, fields, strategy, rules)
        elif isinstance(data, list):
            return [self.mask(item, fields, strategy, rules) for item in data]
        elif isinstance(data, str):
            return self._mask_string(data, strategy, rules)
        else:
            return data
    
    def _mask_dict(
        self,
        data: Dict[str, Any],
        fields: Optional[List[str]],
        strategy: Optional[MaskingStrategy],
        rules: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Mask dictionary."""
        result = {}
        
        for key, value in data.items():
            should_mask = fields is None or key in fields
            
            if should_mask and isinstance(value, str):
                result[key] = self._mask_string(value, strategy, rules)
            elif isinstance(value, (dict, list)):
                result[key] = self.mask(value, fields, strategy, rules)
            else:
                result[key] = value
        
        return result
    
    def _mask_string(
        self,
        value: str,
        strategy: Optional[MaskingStrategy],
        rules: Optional[List[str]],
    ) -> str:
        """Mask string value."""
        result = value
        strategy = strategy or self._default_strategy
        
        # Apply rules
        rules_to_apply = rules or list(self._rules.keys())
        
        for rule_name in rules_to_apply:
            if rule_name not in self._rules:
                continue
            
            rule = self._rules[rule_name]
            pattern = self._compiled_patterns.get(rule_name)
            
            if not pattern:
                continue
            
            def replacer(match):
                matched = match.group()
                return self._apply_strategy(
                    matched,
                    rule.strategy if not strategy else strategy,
                    rule,
                )
            
            result = pattern.sub(replacer, result)
        
        return result
    
    def _apply_strategy(
        self,
        value: str,
        strategy: MaskingStrategy,
        rule: MaskingRule,
    ) -> str:
        """Apply masking strategy."""
        if strategy == MaskingStrategy.REDACT:
            return rule.replacement or "[REDACTED]"
        
        elif strategy == MaskingStrategy.MASK:
            return _mask_with_char(
                value,
                rule.mask_char,
                rule.visible_start,
                rule.visible_end,
            )
        
        elif strategy == MaskingStrategy.PARTIAL:
            return _mask_with_char(value, "*", 0, 4)
        
        elif strategy == MaskingStrategy.HASH:
            return _hash_value(value, self._salt)
        
        elif strategy == MaskingStrategy.RANDOMIZE:
            return _randomize_value(value, rule.preserve_format)
        
        elif strategy == MaskingStrategy.GENERALIZE:
            return _generalize_value(value, rule.data_type)
        
        elif strategy == MaskingStrategy.NULL:
            return ""
        
        return value
    
    async def tokenize(
        self,
        data: Any,
        fields: Optional[List[str]] = None,
    ) -> Tuple[Any, List[Token]]:
        """
        Tokenize data (reversible).
        
        Args:
            data: Data to tokenize
            fields: Fields to tokenize
            
        Returns:
            (tokenized_data, tokens)
        """
        tokens = []
        
        async def tokenize_value(value: str, data_type: DataType = DataType.CUSTOM) -> str:
            token_value = f"tok_{uuid.uuid4().hex[:16]}"
            
            token = Token(
                original_value=value,
                token_value=token_value,
                data_type=data_type,
            )
            
            await self._token_storage.save(token)
            tokens.append(token)
            
            return token_value
        
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                should_tokenize = fields is None or key in fields
                
                if should_tokenize and isinstance(value, str):
                    result[key] = await tokenize_value(value)
                elif isinstance(value, dict):
                    nested, nested_tokens = await self.tokenize(value, fields)
                    result[key] = nested
                    tokens.extend(nested_tokens)
                else:
                    result[key] = value
            return result, tokens
        
        elif isinstance(data, str):
            return await tokenize_value(data), tokens
        
        return data, tokens
    
    async def detokenize(
        self,
        data: Any,
        tokens: Optional[List[Token]] = None,
    ) -> Any:
        """
        Detokenize data.
        
        Args:
            data: Tokenized data
            tokens: Tokens for lookup (optional)
            
        Returns:
            Original data
        """
        # Build lookup from provided tokens
        token_lookup = {}
        if tokens:
            token_lookup = {t.token_value: t.original_value for t in tokens}
        
        async def detokenize_value(value: str) -> str:
            if value in token_lookup:
                return token_lookup[value]
            
            if value.startswith("tok_"):
                token = await self._token_storage.get(value)
                if token:
                    return token.original_value
                raise TokenNotFoundError(f"Token not found: {value}")
            
            return value
        
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if isinstance(value, str):
                    result[key] = await detokenize_value(value)
                elif isinstance(value, dict):
                    result[key] = await self.detokenize(value, tokens)
                else:
                    result[key] = value
            return result
        
        elif isinstance(data, str):
            return await detokenize_value(data)
        
        return data
    
    def detect_pii(
        self,
        data: Any,
        fields: Optional[List[str]] = None,
    ) -> List[DetectionResult]:
        """
        Detect PII in data.
        
        Args:
            data: Data to scan
            fields: Fields to scan
            
        Returns:
            List of detection results
        """
        results = []
        
        def scan_string(field_name: str, value: str):
            for rule_name, pattern in self._compiled_patterns.items():
                rule = self._rules[rule_name]
                
                for match in pattern.finditer(value):
                    results.append(DetectionResult(
                        field=field_name,
                        value=match.group(),
                        data_type=rule.data_type,
                        start_pos=match.start(),
                        end_pos=match.end(),
                    ))
        
        if isinstance(data, dict):
            for key, value in data.items():
                should_scan = fields is None or key in fields
                
                if should_scan and isinstance(value, str):
                    scan_string(key, value)
                elif isinstance(value, dict):
                    nested = self.detect_pii(value, fields)
                    for r in nested:
                        r.field = f"{key}.{r.field}"
                    results.extend(nested)
        
        elif isinstance(data, str):
            scan_string("", data)
        
        return results
    
    def anonymize(
        self,
        data: Any,
        fields: Optional[List[str]] = None,
    ) -> Any:
        """
        Anonymize data (irreversible).
        
        Args:
            data: Data to anonymize
            fields: Fields to anonymize
            
        Returns:
            Anonymized data
        """
        return self.mask(
            data,
            fields=fields,
            strategy=MaskingStrategy.HASH,
        )
    
    def pseudonymize(
        self,
        data: Any,
        mapping: Optional[Dict[str, str]] = None,
        fields: Optional[List[str]] = None,
    ) -> Tuple[Any, Dict[str, str]]:
        """
        Pseudonymize data with consistent mapping.
        
        Args:
            data: Data to pseudonymize
            mapping: Existing mapping
            fields: Fields to pseudonymize
            
        Returns:
            (pseudonymized_data, mapping)
        """
        mapping = mapping or {}
        
        def get_pseudonym(value: str) -> str:
            if value not in mapping:
                pseudonym = f"pseudo_{uuid.uuid4().hex[:8]}"
                mapping[value] = pseudonym
            return mapping[value]
        
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                should_pseudo = fields is None or key in fields
                
                if should_pseudo and isinstance(value, str):
                    result[key] = get_pseudonym(value)
                elif isinstance(value, dict):
                    nested, mapping = self.pseudonymize(value, mapping, fields)
                    result[key] = nested
                else:
                    result[key] = value
            return result, mapping
        
        elif isinstance(data, str):
            return get_pseudonym(data), mapping
        
        return data, mapping


# Decorator for masking
def masked(
    fields: Optional[List[str]] = None,
    strategy: MaskingStrategy = MaskingStrategy.MASK,
) -> Callable:
    """
    Decorator to mask function return value.
    
    Args:
        fields: Fields to mask
        strategy: Masking strategy
        
    Returns:
        Decorator
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if hasattr(result, '__await__'):
                result = await result
            
            masker = _global_masker
            if masker:
                return masker.mask(result, fields=fields, strategy=strategy)
            return result
        
        return wrapper
    
    return decorator


# Global masker
_global_masker: Optional[DataMasker] = None


def set_global_masker(masker: DataMasker) -> None:
    """Set global masker."""
    global _global_masker
    _global_masker = masker


def get_global_masker() -> Optional[DataMasker]:
    """Get global masker."""
    return _global_masker


# Factory functions
def create_data_masker(
    default_strategy: MaskingStrategy = MaskingStrategy.MASK,
    salt: Optional[str] = None,
) -> DataMasker:
    """Create data masker."""
    masker = DataMasker(
        default_strategy=default_strategy,
        salt=salt or "",
    )
    set_global_masker(masker)
    return masker


def create_masking_rule(
    name: str,
    pattern: str,
    data_type: DataType = DataType.CUSTOM,
    strategy: MaskingStrategy = MaskingStrategy.MASK,
    **kwargs,
) -> MaskingRule:
    """Create masking rule."""
    return MaskingRule(
        name=name,
        pattern=pattern,
        data_type=data_type,
        strategy=strategy,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "MaskingError",
    "TokenNotFoundError",
    # Enums
    "MaskingStrategy",
    "DataType",
    # Data classes
    "MaskingRule",
    "Token",
    "MaskingResult",
    "DetectionResult",
    # Storage
    "TokenStorage",
    "InMemoryTokenStorage",
    # Masker
    "DataMasker",
    # Decorator
    "masked",
    # Global
    "set_global_masker",
    "get_global_masker",
    # Factory functions
    "create_data_masker",
    "create_masking_rule",
]
