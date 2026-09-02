"""Stdlib-only schema/validation primitives.

A minimal pydantic-style ``BaseModel`` plus a JSON Schema (Draft 2020-12 subset)
validator. Used by ``enterprise/json_mode.py``, ``enterprise/api_gen.py``,
``communication/remote_agent.py`` to remove the optional ``pydantic`` dependency.

Supported field metadata:

- ``type`` (``"string" | "integer" | "number" | "boolean" | "object" | "array" | "null"``)
- ``enum``
- ``required`` / ``properties`` / ``additionalProperties``
- ``items`` (for arrays)
- ``minLength`` / ``maxLength`` / ``pattern`` (strings)
- ``minimum`` / ``maximum`` (numbers)
- ``minItems`` / ``maxItems``
"""

from __future__ import annotations

import dataclasses
import json
import re
from dataclasses import MISSING, dataclass, field, fields, is_dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Type, get_args, get_origin


class ValidationError(ValueError):
    """Raised when validation fails. ``errors`` lists individual problems."""

    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors) or "validation failed")
        self.errors = errors


# ---------------------------------------------------------------------------
# JSON Schema validator (subset of Draft 2020-12)
# ---------------------------------------------------------------------------

_TYPE_CHECKS: Dict[str, Callable[[Any], bool]] = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def _check_type(value: Any, type_spec: Any, errors: List[str], path: str) -> None:
    if isinstance(type_spec, list):
        if not any(_TYPE_CHECKS.get(t, lambda _v: True)(value) for t in type_spec):
            errors.append(f"{path}: expected one of {type_spec}, got {type(value).__name__}")
        return
    check = _TYPE_CHECKS.get(type_spec)
    if check is not None and not check(value):
        errors.append(f"{path}: expected {type_spec}, got {type(value).__name__}")


def _validate_node(value: Any, schema: Mapping[str, Any], errors: List[str], path: str) -> None:
    if not isinstance(schema, Mapping):
        return

    if "type" in schema:
        _check_type(value, schema["type"], errors, path)

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in enum {schema['enum']}")

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}, got {value!r}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: length {len(value)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: length {len(value)} > maxLength {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: does not match pattern {schema['pattern']!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: {value} <= exclusiveMinimum")
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: {value} >= exclusiveMaximum")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: items {len(value)} < minItems {schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: items {len(value)} > maxItems {schema['maxItems']}")
        items_schema = schema.get("items")
        if items_schema is not None:
            for i, item in enumerate(value):
                _validate_node(item, items_schema, errors, f"{path}[{i}]")

    if isinstance(value, dict):
        props = schema.get("properties", {})
        required = schema.get("required", [])
        for r in required:
            if r not in value:
                errors.append(f"{path}.{r}: required field missing")
        for k, v in value.items():
            if k in props:
                _validate_node(v, props[k], errors, f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}.{k}: additional property not allowed")
            elif isinstance(schema.get("additionalProperties"), Mapping):
                _validate_node(v, schema["additionalProperties"], errors, f"{path}.{k}")


def validate(value: Any, schema: Mapping[str, Any]) -> List[str]:
    """Return a list of validation errors (empty if valid)."""
    errors: List[str] = []
    _validate_node(value, schema, errors, "$")
    return errors


def validate_or_raise(value: Any, schema: Mapping[str, Any]) -> None:
    errs = validate(value, schema)
    if errs:
        raise ValidationError(errs)


# ---------------------------------------------------------------------------
# BaseModel — pydantic-style, dataclass-backed
# ---------------------------------------------------------------------------

_PY_TYPE_TO_JSON = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}


def Field(  # noqa: N802 - mimic pydantic
    default: Any = MISSING,
    *,
    default_factory: Optional[Callable[[], Any]] = None,
    description: str = "",
    ge: Optional[float] = None,
    le: Optional[float] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    pattern: Optional[str] = None,
) -> Any:
    """Declare a field with optional validation metadata."""
    metadata = {
        "description": description,
        "ge": ge,
        "le": le,
        "min_length": min_length,
        "max_length": max_length,
        "pattern": pattern,
    }
    if default_factory is not None:
        return field(default_factory=default_factory, metadata={"aaf": metadata})
    if default is MISSING:
        return field(metadata={"aaf": metadata})
    return field(default=default, metadata={"aaf": metadata})


class _BaseModelMeta(type):
    def __new__(mcs, name: str, bases: Tuple[type, ...], ns: Dict[str, Any]):
        cls = super().__new__(mcs, name, bases, ns)
        # Convert into a dataclass once (skip the abstract base itself).
        if name == "BaseModel" and ns.get("__module__") == __name__:
            return cls
        if not is_dataclass(cls) or "__annotations__" in ns:
            cls = dataclass(cls)  # type: ignore[assignment]
        return cls


class BaseModel(metaclass=_BaseModelMeta):
    """Lightweight pydantic-compatible model.

    Subclasses behave as dataclasses with extra ``.dict()`` / ``.json()`` /
    ``.parse_obj()`` / ``.model_json_schema()`` helpers.
    """

    # ---- construction -----------------------------------------------------

    @classmethod
    def parse_obj(cls, data: Mapping[str, Any]) -> "BaseModel":
        if not isinstance(data, Mapping):
            raise ValidationError([f"expected dict, got {type(data).__name__}"])
        kwargs: Dict[str, Any] = {}
        errors: List[str] = []
        names = {f.name for f in fields(cls)}
        for f in fields(cls):
            if f.name in data:
                kwargs[f.name] = _coerce_value(data[f.name], f.type, errors, f.name)
            elif f.default is MISSING and f.default_factory is MISSING:  # type: ignore[misc]
                errors.append(f"{f.name}: required field missing")
        for k in data.keys():
            if k not in names:
                # silently ignore extra keys (pydantic-compatible default)
                continue
        if errors:
            raise ValidationError(errors)
        return cls(**kwargs)  # type: ignore[call-arg]

    @classmethod
    def parse_raw(cls, raw: str) -> "BaseModel":
        return cls.parse_obj(json.loads(raw))

    @classmethod
    def model_validate(cls, data: Mapping[str, Any]) -> "BaseModel":
        return cls.parse_obj(data)

    # ---- export -----------------------------------------------------------

    def dict(self) -> Dict[str, Any]:  # noqa: A003 - keep pydantic name
        return _to_dict(self)

    def model_dump(self) -> Dict[str, Any]:
        return self.dict()

    def json(self) -> str:  # noqa: A003
        return json.dumps(self.dict(), default=str)

    def model_dump_json(self) -> str:
        return self.json()

    @classmethod
    def model_json_schema(cls) -> Dict[str, Any]:
        return _model_schema(cls)

    @classmethod
    def schema(cls) -> Dict[str, Any]:
        return cls.model_json_schema()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce_value(value: Any, type_hint: Any, errors: List[str], path: str) -> Any:
    if type_hint is None or type_hint is type(None):
        return value
    origin = get_origin(type_hint)
    args = get_args(type_hint)
    if origin in (list, List):
        if not isinstance(value, list):
            errors.append(f"{path}: expected list, got {type(value).__name__}")
            return value
        item_t = args[0] if args else None
        return [
            _coerce_value(v, item_t, errors, f"{path}[{i}]") for i, v in enumerate(value)
        ]
    if origin in (dict, Dict):
        if not isinstance(value, dict):
            errors.append(f"{path}: expected dict, got {type(value).__name__}")
            return value
        return value
    if isinstance(type_hint, type):
        if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
            if isinstance(value, type_hint):
                return value
            return type_hint.parse_obj(value)
        if type_hint is bool and not isinstance(value, bool):
            errors.append(f"{path}: expected bool, got {type(value).__name__}")
            return value
        if type_hint in (int, float) and isinstance(value, bool):
            errors.append(f"{path}: expected {type_hint.__name__}, got bool")
            return value
        if not isinstance(value, type_hint):
            try:
                return type_hint(value)
            except (TypeError, ValueError):
                errors.append(f"{path}: cannot coerce {value!r} to {type_hint.__name__}")
                return value
    return value


def _to_dict(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {f.name: _to_dict(getattr(value, f.name)) for f in fields(value)}
    if dataclasses.is_dataclass(value):
        return {f.name: _to_dict(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {k: _to_dict(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_dict(v) for v in value]
    return value


def _model_schema(cls: Type[BaseModel]) -> Dict[str, Any]:
    properties: Dict[str, Any] = {}
    required: List[str] = []
    for f in fields(cls):
        properties[f.name] = _type_to_schema(f.type)
        if f.default is MISSING and f.default_factory is MISSING:  # type: ignore[misc]
            required.append(f.name)
    return {
        "type": "object",
        "title": cls.__name__,
        "properties": properties,
        "required": required,
    }


def _type_to_schema(type_hint: Any) -> Dict[str, Any]:
    origin = get_origin(type_hint)
    args = get_args(type_hint)
    if origin in (list, List):
        return {"type": "array", "items": _type_to_schema(args[0]) if args else {}}
    if origin in (dict, Dict):
        return {"type": "object"}
    if isinstance(type_hint, type) and issubclass(type_hint, BaseModel):
        return _model_schema(type_hint)
    if isinstance(type_hint, type):
        return {"type": _PY_TYPE_TO_JSON.get(type_hint, "string")}
    if isinstance(type_hint, str):
        return {"type": "string"}
    return {}


__all__ = [
    "BaseModel",
    "Field",
    "ValidationError",
    "validate",
    "validate_or_raise",
]
