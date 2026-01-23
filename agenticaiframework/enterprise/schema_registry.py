"""
Enterprise Schema Registry Module.

Schema versioning, validation, and evolution for
data contracts, APIs, and event schemas.

Example:
    # Create schema registry
    registry = create_schema_registry()
    
    # Register schema
    schema_id = await registry.register(
        subject="user-events",
        schema={
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "event": {"type": "string"},
            },
            "required": ["user_id", "event"],
        },
    )
    
    # Validate data
    valid = await registry.validate(
        subject="user-events",
        data={"user_id": "123", "event": "login"},
    )
    
    # Check compatibility
    compatible = await registry.check_compatibility(
        subject="user-events",
        schema=new_schema,
    )
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class SchemaError(Exception):
    """Schema error."""
    pass


class SchemaNotFoundError(SchemaError):
    """Schema not found."""
    pass


class ValidationError(SchemaError):
    """Validation error."""
    pass


class CompatibilityError(SchemaError):
    """Compatibility error."""
    pass


class SchemaFormat(str, Enum):
    """Schema formats."""
    JSON_SCHEMA = "json_schema"
    AVRO = "avro"
    PROTOBUF = "protobuf"
    OPENAPI = "openapi"


class CompatibilityMode(str, Enum):
    """Compatibility modes."""
    NONE = "none"
    BACKWARD = "backward"
    FORWARD = "forward"
    FULL = "full"
    BACKWARD_TRANSITIVE = "backward_transitive"
    FORWARD_TRANSITIVE = "forward_transitive"
    FULL_TRANSITIVE = "full_transitive"


class SchemaStatus(str, Enum):
    """Schema status."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DELETED = "deleted"


@dataclass
class SchemaVersion:
    """Schema version."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    schema: Dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""
    format: SchemaFormat = SchemaFormat.JSON_SCHEMA
    status: SchemaStatus = SchemaStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Subject:
    """Schema subject."""
    name: str
    compatibility: CompatibilityMode = CompatibilityMode.BACKWARD
    versions: List[SchemaVersion] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def latest(self) -> Optional[SchemaVersion]:
        """Get latest version."""
        active = [v for v in self.versions if v.status == SchemaStatus.ACTIVE]
        return active[-1] if active else None
    
    @property
    def version_count(self) -> int:
        """Get version count."""
        return len(self.versions)


@dataclass
class ValidationResult:
    """Validation result."""
    valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, message: str) -> None:
        """Add error."""
        self.valid = False
        self.errors.append(message)
    
    def add_warning(self, message: str) -> None:
        """Add warning."""
        self.warnings.append(message)


@dataclass
class CompatibilityResult:
    """Compatibility result."""
    compatible: bool = True
    breaking_changes: List[str] = field(default_factory=list)
    non_breaking_changes: List[str] = field(default_factory=list)


@dataclass
class RegistryStats:
    """Registry statistics."""
    total_subjects: int = 0
    total_versions: int = 0
    subjects_by_compatibility: Dict[str, int] = field(default_factory=dict)


# Schema validator
class SchemaValidator(ABC):
    """Abstract schema validator."""
    
    @abstractmethod
    def validate(
        self,
        schema: Dict[str, Any],
        data: Any,
    ) -> ValidationResult:
        """Validate data against schema."""
        pass
    
    @abstractmethod
    def validate_schema(
        self,
        schema: Dict[str, Any],
    ) -> ValidationResult:
        """Validate schema itself."""
        pass


class JSONSchemaValidator(SchemaValidator):
    """JSON Schema validator."""
    
    def validate(
        self,
        schema: Dict[str, Any],
        data: Any,
    ) -> ValidationResult:
        result = ValidationResult()
        
        try:
            self._validate_type(schema, data, result, "")
        except Exception as e:
            result.add_error(str(e))
        
        return result
    
    def _validate_type(
        self,
        schema: Dict[str, Any],
        data: Any,
        result: ValidationResult,
        path: str,
    ) -> None:
        """Validate type."""
        if "type" not in schema:
            return
        
        schema_type = schema["type"]
        
        if schema_type == "object":
            self._validate_object(schema, data, result, path)
        elif schema_type == "array":
            self._validate_array(schema, data, result, path)
        elif schema_type == "string":
            if not isinstance(data, str):
                result.add_error(f"{path}: expected string, got {type(data).__name__}")
        elif schema_type == "number":
            if not isinstance(data, (int, float)):
                result.add_error(f"{path}: expected number, got {type(data).__name__}")
        elif schema_type == "integer":
            if not isinstance(data, int):
                result.add_error(f"{path}: expected integer, got {type(data).__name__}")
        elif schema_type == "boolean":
            if not isinstance(data, bool):
                result.add_error(f"{path}: expected boolean, got {type(data).__name__}")
        elif schema_type == "null":
            if data is not None:
                result.add_error(f"{path}: expected null")
    
    def _validate_object(
        self,
        schema: Dict[str, Any],
        data: Any,
        result: ValidationResult,
        path: str,
    ) -> None:
        """Validate object."""
        if not isinstance(data, dict):
            result.add_error(f"{path}: expected object, got {type(data).__name__}")
            return
        
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # Check required properties
        for prop in required:
            if prop not in data:
                result.add_error(f"{path}.{prop}: required property missing")
        
        # Validate each property
        for prop, prop_schema in properties.items():
            if prop in data:
                prop_path = f"{path}.{prop}" if path else prop
                self._validate_type(prop_schema, data[prop], result, prop_path)
        
        # Check for additional properties
        if schema.get("additionalProperties") is False:
            extra = set(data.keys()) - set(properties.keys())
            for prop in extra:
                result.add_error(f"{path}.{prop}: additional property not allowed")
    
    def _validate_array(
        self,
        schema: Dict[str, Any],
        data: Any,
        result: ValidationResult,
        path: str,
    ) -> None:
        """Validate array."""
        if not isinstance(data, list):
            result.add_error(f"{path}: expected array, got {type(data).__name__}")
            return
        
        items_schema = schema.get("items", {})
        
        for i, item in enumerate(data):
            item_path = f"{path}[{i}]"
            self._validate_type(items_schema, item, result, item_path)
        
        # Check min/max items
        if "minItems" in schema and len(data) < schema["minItems"]:
            result.add_error(f"{path}: array has fewer than {schema['minItems']} items")
        
        if "maxItems" in schema and len(data) > schema["maxItems"]:
            result.add_error(f"{path}: array has more than {schema['maxItems']} items")
    
    def validate_schema(
        self,
        schema: Dict[str, Any],
    ) -> ValidationResult:
        result = ValidationResult()
        
        if not isinstance(schema, dict):
            result.add_error("Schema must be an object")
            return result
        
        # Check for type
        if "type" not in schema and "anyOf" not in schema and "oneOf" not in schema:
            result.add_warning("Schema should have a 'type' field")
        
        return result


# Compatibility checker
class CompatibilityChecker:
    """Schema compatibility checker."""
    
    def check(
        self,
        old_schema: Dict[str, Any],
        new_schema: Dict[str, Any],
        mode: CompatibilityMode,
    ) -> CompatibilityResult:
        """Check schema compatibility."""
        result = CompatibilityResult()
        
        if mode == CompatibilityMode.NONE:
            return result
        
        if mode in (CompatibilityMode.BACKWARD, CompatibilityMode.BACKWARD_TRANSITIVE):
            self._check_backward(old_schema, new_schema, result)
        
        if mode in (CompatibilityMode.FORWARD, CompatibilityMode.FORWARD_TRANSITIVE):
            self._check_forward(old_schema, new_schema, result)
        
        if mode in (CompatibilityMode.FULL, CompatibilityMode.FULL_TRANSITIVE):
            self._check_backward(old_schema, new_schema, result)
            self._check_forward(old_schema, new_schema, result)
        
        return result
    
    def _check_backward(
        self,
        old_schema: Dict[str, Any],
        new_schema: Dict[str, Any],
        result: CompatibilityResult,
    ) -> None:
        """Check backward compatibility (new can read old)."""
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})
        new_required = set(new_schema.get("required", []))
        old_required = set(old_schema.get("required", []))
        
        # New required fields that weren't in old schema
        new_required_added = new_required - old_required - set(old_props.keys())
        for prop in new_required_added:
            if prop not in old_props:
                result.compatible = False
                result.breaking_changes.append(
                    f"New required field '{prop}' added"
                )
        
        # Field type changes
        for prop in old_props:
            if prop in new_props:
                old_type = old_props[prop].get("type")
                new_type = new_props[prop].get("type")
                
                if old_type != new_type:
                    result.compatible = False
                    result.breaking_changes.append(
                        f"Field '{prop}' type changed from '{old_type}' to '{new_type}'"
                    )
        
        # Removed fields
        removed = set(old_props.keys()) - set(new_props.keys())
        for prop in removed:
            result.non_breaking_changes.append(
                f"Field '{prop}' removed (backward compatible)"
            )
    
    def _check_forward(
        self,
        old_schema: Dict[str, Any],
        new_schema: Dict[str, Any],
        result: CompatibilityResult,
    ) -> None:
        """Check forward compatibility (old can read new)."""
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})
        old_required = set(old_schema.get("required", []))
        
        # Fields removed from new that were required in old
        for prop in old_required:
            if prop not in new_props:
                result.compatible = False
                result.breaking_changes.append(
                    f"Required field '{prop}' removed"
                )
        
        # New fields added
        added = set(new_props.keys()) - set(old_props.keys())
        for prop in added:
            result.non_breaking_changes.append(
                f"New field '{prop}' added"
            )


# Schema registry
class SchemaRegistry:
    """
    Schema registry service.
    """
    
    def __init__(
        self,
        default_compatibility: CompatibilityMode = CompatibilityMode.BACKWARD,
    ):
        self._subjects: Dict[str, Subject] = {}
        self._schemas: Dict[str, SchemaVersion] = {}  # By fingerprint
        self._default_compatibility = default_compatibility
        self._validator = JSONSchemaValidator()
        self._compat_checker = CompatibilityChecker()
    
    def _compute_fingerprint(self, schema: Dict[str, Any]) -> str:
        """Compute schema fingerprint."""
        canonical = json.dumps(schema, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
    
    async def register(
        self,
        subject: str,
        schema: Dict[str, Any],
        format: SchemaFormat = SchemaFormat.JSON_SCHEMA,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SchemaVersion:
        """
        Register a schema.
        
        Args:
            subject: Subject name
            schema: Schema definition
            format: Schema format
            metadata: Optional metadata
            
        Returns:
            Schema version
        """
        # Validate schema
        validation = self._validator.validate_schema(schema)
        
        if not validation.valid:
            raise ValidationError(
                f"Invalid schema: {', '.join(validation.errors)}"
            )
        
        fingerprint = self._compute_fingerprint(schema)
        
        # Check if subject exists
        if subject not in self._subjects:
            self._subjects[subject] = Subject(
                name=subject,
                compatibility=self._default_compatibility,
            )
        
        subj = self._subjects[subject]
        
        # Check if schema already exists
        for version in subj.versions:
            if version.fingerprint == fingerprint:
                return version
        
        # Check compatibility
        if subj.latest:
            compat = await self.check_compatibility(subject, schema)
            
            if not compat.compatible:
                raise CompatibilityError(
                    f"Schema incompatible: {', '.join(compat.breaking_changes)}"
                )
        
        # Create new version
        version = SchemaVersion(
            version=len(subj.versions) + 1,
            schema=schema,
            fingerprint=fingerprint,
            format=format,
            metadata=metadata or {},
        )
        
        subj.versions.append(version)
        subj.updated_at = datetime.utcnow()
        
        self._schemas[fingerprint] = version
        
        return version
    
    async def get(
        self,
        subject: str,
        version: Optional[int] = None,
    ) -> Optional[SchemaVersion]:
        """
        Get schema version.
        
        Args:
            subject: Subject name
            version: Version number (None for latest)
            
        Returns:
            Schema version or None
        """
        subj = self._subjects.get(subject)
        
        if not subj:
            return None
        
        if version is None:
            return subj.latest
        
        for v in subj.versions:
            if v.version == version:
                return v
        
        return None
    
    async def get_by_id(self, schema_id: str) -> Optional[SchemaVersion]:
        """Get schema by ID."""
        for subj in self._subjects.values():
            for version in subj.versions:
                if version.id == schema_id:
                    return version
        return None
    
    async def get_by_fingerprint(
        self,
        fingerprint: str,
    ) -> Optional[SchemaVersion]:
        """Get schema by fingerprint."""
        return self._schemas.get(fingerprint)
    
    async def get_subject(self, name: str) -> Optional[Subject]:
        """Get subject."""
        return self._subjects.get(name)
    
    async def list_subjects(self) -> List[str]:
        """List all subjects."""
        return list(self._subjects.keys())
    
    async def list_versions(self, subject: str) -> List[int]:
        """List versions for subject."""
        subj = self._subjects.get(subject)
        return [v.version for v in subj.versions] if subj else []
    
    async def delete_subject(self, subject: str) -> bool:
        """Delete subject and all versions."""
        if subject in self._subjects:
            subj = self._subjects[subject]
            
            for version in subj.versions:
                if version.fingerprint in self._schemas:
                    del self._schemas[version.fingerprint]
            
            del self._subjects[subject]
            return True
        
        return False
    
    async def delete_version(
        self,
        subject: str,
        version: int,
    ) -> bool:
        """Delete specific version."""
        subj = self._subjects.get(subject)
        
        if not subj:
            return False
        
        for v in subj.versions:
            if v.version == version:
                v.status = SchemaStatus.DELETED
                return True
        
        return False
    
    async def validate(
        self,
        subject: str,
        data: Any,
        version: Optional[int] = None,
    ) -> ValidationResult:
        """
        Validate data against schema.
        
        Args:
            subject: Subject name
            data: Data to validate
            version: Schema version
            
        Returns:
            Validation result
        """
        schema_version = await self.get(subject, version)
        
        if not schema_version:
            result = ValidationResult()
            result.add_error(f"Schema not found: {subject}")
            return result
        
        return self._validator.validate(schema_version.schema, data)
    
    async def check_compatibility(
        self,
        subject: str,
        schema: Dict[str, Any],
    ) -> CompatibilityResult:
        """
        Check schema compatibility.
        
        Args:
            subject: Subject name
            schema: New schema to check
            
        Returns:
            Compatibility result
        """
        subj = self._subjects.get(subject)
        
        if not subj or not subj.latest:
            return CompatibilityResult()
        
        return self._compat_checker.check(
            subj.latest.schema,
            schema,
            subj.compatibility,
        )
    
    async def set_compatibility(
        self,
        subject: str,
        mode: CompatibilityMode,
    ) -> None:
        """Set compatibility mode for subject."""
        if subject in self._subjects:
            self._subjects[subject].compatibility = mode
    
    async def get_compatibility(
        self,
        subject: str,
    ) -> Optional[CompatibilityMode]:
        """Get compatibility mode for subject."""
        subj = self._subjects.get(subject)
        return subj.compatibility if subj else None
    
    async def deprecate(
        self,
        subject: str,
        version: int,
    ) -> bool:
        """Deprecate schema version."""
        schema_version = await self.get(subject, version)
        
        if schema_version:
            schema_version.status = SchemaStatus.DEPRECATED
            return True
        
        return False
    
    async def get_stats(self) -> RegistryStats:
        """Get registry statistics."""
        stats = RegistryStats(
            total_subjects=len(self._subjects),
        )
        
        for subj in self._subjects.values():
            stats.total_versions += len(subj.versions)
            
            mode = subj.compatibility.value
            stats.subjects_by_compatibility[mode] = (
                stats.subjects_by_compatibility.get(mode, 0) + 1
            )
        
        return stats


# Decorators
def schema(
    registry: SchemaRegistry,
    subject: str,
    version: Optional[int] = None,
):
    """
    Decorator to validate function input/output.
    
    Args:
        registry: Schema registry
        subject: Subject name
        version: Schema version
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            if isinstance(result, dict):
                validation = await registry.validate(subject, result, version)
                
                if not validation.valid:
                    raise ValidationError(
                        f"Output validation failed: {', '.join(validation.errors)}"
                    )
            
            return result
        
        return wrapper
    
    return decorator


# Factory functions
def create_schema_registry(
    default_compatibility: CompatibilityMode = CompatibilityMode.BACKWARD,
) -> SchemaRegistry:
    """Create schema registry."""
    return SchemaRegistry(default_compatibility=default_compatibility)


def create_json_schema(
    properties: Dict[str, Dict[str, Any]],
    required: Optional[List[str]] = None,
    additional_properties: bool = False,
) -> Dict[str, Any]:
    """Create JSON Schema."""
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": additional_properties,
    }


__all__ = [
    # Exceptions
    "SchemaError",
    "SchemaNotFoundError",
    "ValidationError",
    "CompatibilityError",
    # Enums
    "SchemaFormat",
    "CompatibilityMode",
    "SchemaStatus",
    # Data classes
    "SchemaVersion",
    "Subject",
    "ValidationResult",
    "CompatibilityResult",
    "RegistryStats",
    # Validators
    "SchemaValidator",
    "JSONSchemaValidator",
    # Compatibility
    "CompatibilityChecker",
    # Registry
    "SchemaRegistry",
    # Decorators
    "schema",
    # Factory functions
    "create_schema_registry",
    "create_json_schema",
]
