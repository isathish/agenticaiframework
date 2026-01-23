"""
Enterprise Serialization Module.

Provides custom serializers with support for JSON, Pickle, MessagePack,
and Protocol Buffers for efficient data transfer.

Example:
    # JSON serialization
    serializer = JSONSerializer()
    data = serializer.serialize({"key": "value"})
    obj = serializer.deserialize(data)
    
    # Registry for type-based serialization
    registry = SerializerRegistry()
    registry.register(MyClass, custom_serializer)
"""

from __future__ import annotations

import json
import pickle
import base64
import gzip
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict, is_dataclass
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class SerializationError(Exception):
    """Serialization error."""
    pass


class DeserializationError(Exception):
    """Deserialization error."""
    pass


class SerializationFormat(str, Enum):
    """Supported serialization formats."""
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"
    BINARY = "binary"


@dataclass
class SerializationOptions:
    """Options for serialization."""
    compress: bool = False
    encode_base64: bool = False
    pretty: bool = False
    date_format: str = "%Y-%m-%dT%H:%M:%S.%fZ"
    decimal_as_string: bool = True
    include_type_info: bool = False


class Serializer(ABC, Generic[T]):
    """Abstract serializer interface."""
    
    @property
    @abstractmethod
    def format(self) -> SerializationFormat:
        """Get serialization format."""
        pass
    
    @property
    @abstractmethod
    def content_type(self) -> str:
        """Get MIME content type."""
        pass
    
    @abstractmethod
    def serialize(self, obj: T, options: Optional[SerializationOptions] = None) -> bytes:
        """Serialize object to bytes."""
        pass
    
    @abstractmethod
    def deserialize(self, data: bytes, target_type: Optional[Type[T]] = None) -> T:
        """Deserialize bytes to object."""
        pass
    
    def serialize_string(self, obj: T, options: Optional[SerializationOptions] = None) -> str:
        """Serialize object to string."""
        data = self.serialize(obj, options)
        return base64.b64encode(data).decode("utf-8")
    
    def deserialize_string(self, data: str, target_type: Optional[Type[T]] = None) -> T:
        """Deserialize string to object."""
        raw = base64.b64decode(data.encode("utf-8"))
        return self.deserialize(raw, target_type)


class JSONSerializer(Serializer[Any]):
    """JSON serializer with extended type support."""
    
    def __init__(
        self,
        default_options: Optional[SerializationOptions] = None,
        custom_encoders: Optional[Dict[Type, Callable[[Any], Any]]] = None,
        custom_decoders: Optional[Dict[str, Callable[[Any], Any]]] = None,
    ):
        """
        Initialize JSON serializer.
        
        Args:
            default_options: Default serialization options
            custom_encoders: Custom type encoders
            custom_decoders: Custom type decoders
        """
        self.default_options = default_options or SerializationOptions()
        self.custom_encoders = custom_encoders or {}
        self.custom_decoders = custom_decoders or {}
    
    @property
    def format(self) -> SerializationFormat:
        return SerializationFormat.JSON
    
    @property
    def content_type(self) -> str:
        return "application/json"
    
    def _encode_value(self, obj: Any, options: SerializationOptions) -> Any:
        """Encode a value for JSON serialization."""
        # Check custom encoders first
        for type_cls, encoder in self.custom_encoders.items():
            if isinstance(obj, type_cls):
                encoded = encoder(obj)
                if options.include_type_info:
                    return {"__type__": type_cls.__name__, "__value__": encoded}
                return encoded
        
        # Handle standard types
        if isinstance(obj, datetime):
            value = obj.strftime(options.date_format)
            if options.include_type_info:
                return {"__type__": "datetime", "__value__": value}
            return value
        
        if isinstance(obj, date):
            value = obj.isoformat()
            if options.include_type_info:
                return {"__type__": "date", "__value__": value}
            return value
        
        if isinstance(obj, Decimal):
            value = str(obj) if options.decimal_as_string else float(obj)
            if options.include_type_info:
                return {"__type__": "Decimal", "__value__": value}
            return value
        
        if isinstance(obj, UUID):
            value = str(obj)
            if options.include_type_info:
                return {"__type__": "UUID", "__value__": value}
            return value
        
        if isinstance(obj, bytes):
            value = base64.b64encode(obj).decode("utf-8")
            if options.include_type_info:
                return {"__type__": "bytes", "__value__": value}
            return value
        
        if isinstance(obj, Enum):
            if options.include_type_info:
                return {"__type__": type(obj).__name__, "__value__": obj.value}
            return obj.value
        
        if is_dataclass(obj) and not isinstance(obj, type):
            value = asdict(obj)
            if options.include_type_info:
                return {"__type__": type(obj).__name__, "__value__": value}
            return value
        
        if isinstance(obj, dict):
            return {k: self._encode_value(v, options) for k, v in obj.items()}
        
        if isinstance(obj, (list, tuple)):
            return [self._encode_value(item, options) for item in obj]
        
        if isinstance(obj, set):
            return list(obj)
        
        return obj
    
    def _decode_value(self, obj: Any) -> Any:
        """Decode a value from JSON."""
        if isinstance(obj, dict):
            # Check for type info
            if "__type__" in obj and "__value__" in obj:
                type_name = obj["__type__"]
                value = obj["__value__"]
                
                # Check custom decoders
                if type_name in self.custom_decoders:
                    return self.custom_decoders[type_name](value)
                
                # Handle standard types
                if type_name == "datetime":
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                if type_name == "date":
                    return date.fromisoformat(value)
                if type_name == "Decimal":
                    return Decimal(value)
                if type_name == "UUID":
                    return UUID(value)
                if type_name == "bytes":
                    return base64.b64decode(value)
                
                return value
            
            return {k: self._decode_value(v) for k, v in obj.items()}
        
        if isinstance(obj, list):
            return [self._decode_value(item) for item in obj]
        
        return obj
    
    def serialize(self, obj: Any, options: Optional[SerializationOptions] = None) -> bytes:
        """Serialize object to JSON bytes."""
        opts = options or self.default_options
        
        try:
            encoded = self._encode_value(obj, opts)
            
            if opts.pretty:
                json_str = json.dumps(encoded, indent=2, ensure_ascii=False)
            else:
                json_str = json.dumps(encoded, ensure_ascii=False)
            
            data = json_str.encode("utf-8")
            
            if opts.compress:
                data = gzip.compress(data)
            
            if opts.encode_base64:
                data = base64.b64encode(data)
            
            return data
            
        except Exception as e:
            raise SerializationError(f"JSON serialization failed: {e}") from e
    
    def deserialize(self, data: bytes, target_type: Optional[Type] = None) -> Any:
        """Deserialize JSON bytes to object."""
        try:
            # Try to decompress
            try:
                data = gzip.decompress(data)
            except gzip.BadGzipFile:
                pass
            
            # Try base64 decode
            try:
                decoded = base64.b64decode(data)
                data = decoded
            except Exception:
                pass
            
            json_str = data.decode("utf-8")
            obj = json.loads(json_str)
            
            return self._decode_value(obj)
            
        except Exception as e:
            raise DeserializationError(f"JSON deserialization failed: {e}") from e


class PickleSerializer(Serializer[Any]):
    """Pickle serializer for Python objects."""
    
    def __init__(
        self,
        protocol: int = pickle.HIGHEST_PROTOCOL,
        default_options: Optional[SerializationOptions] = None,
    ):
        self.protocol = protocol
        self.default_options = default_options or SerializationOptions()
    
    @property
    def format(self) -> SerializationFormat:
        return SerializationFormat.PICKLE
    
    @property
    def content_type(self) -> str:
        return "application/python-pickle"
    
    def serialize(self, obj: Any, options: Optional[SerializationOptions] = None) -> bytes:
        """Serialize object using pickle."""
        opts = options or self.default_options
        
        try:
            data = pickle.dumps(obj, protocol=self.protocol)
            
            if opts.compress:
                data = gzip.compress(data)
            
            if opts.encode_base64:
                data = base64.b64encode(data)
            
            return data
            
        except Exception as e:
            raise SerializationError(f"Pickle serialization failed: {e}") from e
    
    def deserialize(self, data: bytes, target_type: Optional[Type] = None) -> Any:
        """Deserialize pickle bytes."""
        try:
            # Try to decompress
            try:
                data = gzip.decompress(data)
            except gzip.BadGzipFile:
                pass
            
            # Try base64 decode
            try:
                decoded = base64.b64decode(data)
                data = decoded
            except Exception:
                pass
            
            return pickle.loads(data)
            
        except Exception as e:
            raise DeserializationError(f"Pickle deserialization failed: {e}") from e


class MessagePackSerializer(Serializer[Any]):
    """MessagePack serializer (requires msgpack package)."""
    
    def __init__(self, default_options: Optional[SerializationOptions] = None):
        self.default_options = default_options or SerializationOptions()
        self._msgpack = None
    
    def _get_msgpack(self):
        """Lazy import msgpack."""
        if self._msgpack is None:
            try:
                import msgpack
                self._msgpack = msgpack
            except ImportError:
                raise ImportError("msgpack package required for MessagePackSerializer")
        return self._msgpack
    
    @property
    def format(self) -> SerializationFormat:
        return SerializationFormat.MSGPACK
    
    @property
    def content_type(self) -> str:
        return "application/msgpack"
    
    def serialize(self, obj: Any, options: Optional[SerializationOptions] = None) -> bytes:
        """Serialize object using MessagePack."""
        opts = options or self.default_options
        msgpack = self._get_msgpack()
        
        try:
            data = msgpack.packb(obj, use_bin_type=True)
            
            if opts.compress:
                data = gzip.compress(data)
            
            return data
            
        except Exception as e:
            raise SerializationError(f"MessagePack serialization failed: {e}") from e
    
    def deserialize(self, data: bytes, target_type: Optional[Type] = None) -> Any:
        """Deserialize MessagePack bytes."""
        msgpack = self._get_msgpack()
        
        try:
            try:
                data = gzip.decompress(data)
            except gzip.BadGzipFile:
                pass
            
            return msgpack.unpackb(data, raw=False)
            
        except Exception as e:
            raise DeserializationError(f"MessagePack deserialization failed: {e}") from e


class BinarySerializer(Serializer[bytes]):
    """Simple binary serializer for raw bytes."""
    
    def __init__(self, default_options: Optional[SerializationOptions] = None):
        self.default_options = default_options or SerializationOptions()
    
    @property
    def format(self) -> SerializationFormat:
        return SerializationFormat.BINARY
    
    @property
    def content_type(self) -> str:
        return "application/octet-stream"
    
    def serialize(self, obj: bytes, options: Optional[SerializationOptions] = None) -> bytes:
        """Serialize bytes (with optional compression)."""
        opts = options or self.default_options
        
        if not isinstance(obj, bytes):
            raise SerializationError("BinarySerializer only accepts bytes")
        
        data = obj
        
        if opts.compress:
            data = gzip.compress(data)
        
        if opts.encode_base64:
            data = base64.b64encode(data)
        
        return data
    
    def deserialize(self, data: bytes, target_type: Optional[Type] = None) -> bytes:
        """Deserialize to bytes."""
        try:
            try:
                data = gzip.decompress(data)
            except gzip.BadGzipFile:
                pass
            
            try:
                data = base64.b64decode(data)
            except Exception:
                pass
            
            return data
            
        except Exception as e:
            raise DeserializationError(f"Binary deserialization failed: {e}") from e


class SerializerRegistry:
    """
    Registry for type-specific serializers.
    """
    
    def __init__(self, default_serializer: Optional[Serializer] = None):
        """
        Initialize serializer registry.
        
        Args:
            default_serializer: Default serializer for unregistered types
        """
        self._serializers: Dict[Type, Serializer] = {}
        self._default = default_serializer or JSONSerializer()
    
    def register(self, type_cls: Type, serializer: Serializer) -> None:
        """Register a serializer for a type."""
        self._serializers[type_cls] = serializer
    
    def get(self, type_cls: Type) -> Serializer:
        """Get serializer for a type."""
        # Check exact type match
        if type_cls in self._serializers:
            return self._serializers[type_cls]
        
        # Check parent types
        for registered_type, serializer in self._serializers.items():
            if issubclass(type_cls, registered_type):
                return serializer
        
        return self._default
    
    def serialize(self, obj: Any, options: Optional[SerializationOptions] = None) -> bytes:
        """Serialize using appropriate serializer."""
        serializer = self.get(type(obj))
        return serializer.serialize(obj, options)
    
    def deserialize(self, data: bytes, target_type: Type[T]) -> T:
        """Deserialize using appropriate serializer."""
        serializer = self.get(target_type)
        return serializer.deserialize(data, target_type)


class TypedSerializer(Generic[T]):
    """
    Type-safe serializer wrapper.
    """
    
    def __init__(
        self,
        target_type: Type[T],
        serializer: Optional[Serializer] = None,
    ):
        self.target_type = target_type
        self.serializer = serializer or JSONSerializer()
    
    def serialize(self, obj: T, options: Optional[SerializationOptions] = None) -> bytes:
        """Serialize typed object."""
        return self.serializer.serialize(obj, options)
    
    def deserialize(self, data: bytes) -> T:
        """Deserialize to typed object."""
        return self.serializer.deserialize(data, self.target_type)


def serialize_json(obj: Any, pretty: bool = False, compress: bool = False) -> bytes:
    """Convenience function for JSON serialization."""
    options = SerializationOptions(pretty=pretty, compress=compress)
    return JSONSerializer().serialize(obj, options)


def deserialize_json(data: bytes) -> Any:
    """Convenience function for JSON deserialization."""
    return JSONSerializer().deserialize(data)


def serialize_pickle(obj: Any, compress: bool = False) -> bytes:
    """Convenience function for pickle serialization."""
    options = SerializationOptions(compress=compress)
    return PickleSerializer().serialize(obj, options)


def deserialize_pickle(data: bytes) -> Any:
    """Convenience function for pickle deserialization."""
    return PickleSerializer().deserialize(data)


__all__ = [
    # Exceptions
    "SerializationError",
    "DeserializationError",
    # Enums
    "SerializationFormat",
    # Data classes
    "SerializationOptions",
    # Serializers
    "Serializer",
    "JSONSerializer",
    "PickleSerializer",
    "MessagePackSerializer",
    "BinarySerializer",
    # Registry
    "SerializerRegistry",
    "TypedSerializer",
    # Convenience functions
    "serialize_json",
    "deserialize_json",
    "serialize_pickle",
    "deserialize_pickle",
]
