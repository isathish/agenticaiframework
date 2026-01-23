"""
Enterprise API Documentation Module.

OpenAPI/Swagger generation, automatic API documentation,
endpoint discovery, and schema generation.

Example:
    # Create API documentation generator
    docs = create_api_docs(
        title="My API",
        version="1.0.0",
    )
    
    # Register endpoints
    docs.add_endpoint(
        path="/users",
        method="GET",
        summary="List users",
        responses={200: {"schema": {"type": "array"}}},
    )
    
    # Generate OpenAPI spec
    spec = await docs.generate_openapi()
    
    # Export as JSON/YAML
    json_spec = docs.to_json()
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import re
import time
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
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class APIDocsError(Exception):
    """API documentation error."""
    pass


class HTTPMethod(str, Enum):
    """HTTP methods."""
    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"
    PATCH = "patch"
    HEAD = "head"
    OPTIONS = "options"


class ParameterLocation(str, Enum):
    """Parameter location."""
    PATH = "path"
    QUERY = "query"
    HEADER = "header"
    COOKIE = "cookie"
    BODY = "body"


class DataType(str, Enum):
    """Data types."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


@dataclass
class Contact:
    """API contact info."""
    name: str = ""
    email: str = ""
    url: str = ""


@dataclass
class License:
    """API license info."""
    name: str = "MIT"
    url: str = ""


@dataclass
class ServerInfo:
    """Server info."""
    url: str = ""
    description: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Schema:
    """JSON Schema."""
    type: DataType = DataType.OBJECT
    title: str = ""
    description: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    items: Optional[Dict[str, Any]] = None
    enum: Optional[List[Any]] = None
    format: str = ""
    example: Any = None
    default: Any = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: str = ""
    nullable: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result: Dict[str, Any] = {"type": self.type.value}
        
        if self.title:
            result["title"] = self.title
        if self.description:
            result["description"] = self.description
        if self.properties:
            result["properties"] = self.properties
        if self.required:
            result["required"] = self.required
        if self.items:
            result["items"] = self.items
        if self.enum:
            result["enum"] = self.enum
        if self.format:
            result["format"] = self.format
        if self.example is not None:
            result["example"] = self.example
        if self.default is not None:
            result["default"] = self.default
        if self.minimum is not None:
            result["minimum"] = self.minimum
        if self.maximum is not None:
            result["maximum"] = self.maximum
        if self.min_length is not None:
            result["minLength"] = self.min_length
        if self.max_length is not None:
            result["maxLength"] = self.max_length
        if self.pattern:
            result["pattern"] = self.pattern
        if self.nullable:
            result["nullable"] = self.nullable
        
        return result


@dataclass
class Parameter:
    """API parameter."""
    name: str = ""
    location: ParameterLocation = ParameterLocation.QUERY
    description: str = ""
    required: bool = False
    schema: Optional[Schema] = None
    example: Any = None
    deprecated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result = {
            "name": self.name,
            "in": self.location.value,
            "required": self.required,
        }
        
        if self.description:
            result["description"] = self.description
        
        if self.schema:
            result["schema"] = self.schema.to_dict()
        
        if self.example is not None:
            result["example"] = self.example
        
        if self.deprecated:
            result["deprecated"] = self.deprecated
        
        return result


@dataclass
class RequestBody:
    """Request body."""
    description: str = ""
    required: bool = True
    content: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result = {"required": self.required}
        
        if self.description:
            result["description"] = self.description
        
        if self.content:
            result["content"] = self.content
        
        return result


@dataclass
class Response:
    """API response."""
    status_code: int = 200
    description: str = ""
    schema: Optional[Schema] = None
    content_type: str = "application/json"
    headers: Dict[str, Any] = field(default_factory=dict)
    examples: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result: Dict[str, Any] = {}
        
        if self.description:
            result["description"] = self.description
        
        if self.schema:
            result["content"] = {
                self.content_type: {
                    "schema": self.schema.to_dict(),
                }
            }
            
            if self.examples:
                result["content"][self.content_type]["examples"] = self.examples
        
        if self.headers:
            result["headers"] = self.headers
        
        return result


@dataclass
class Endpoint:
    """API endpoint."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    path: str = ""
    method: HTTPMethod = HTTPMethod.GET
    summary: str = ""
    description: str = ""
    operation_id: str = ""
    tags: List[str] = field(default_factory=list)
    parameters: List[Parameter] = field(default_factory=list)
    request_body: Optional[RequestBody] = None
    responses: Dict[int, Response] = field(default_factory=dict)
    deprecated: bool = False
    security: List[Dict[str, List[str]]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result: Dict[str, Any] = {}
        
        if self.summary:
            result["summary"] = self.summary
        if self.description:
            result["description"] = self.description
        if self.operation_id:
            result["operationId"] = self.operation_id
        if self.tags:
            result["tags"] = self.tags
        if self.deprecated:
            result["deprecated"] = self.deprecated
        
        if self.parameters:
            result["parameters"] = [p.to_dict() for p in self.parameters]
        
        if self.request_body:
            result["requestBody"] = self.request_body.to_dict()
        
        if self.responses:
            result["responses"] = {
                str(code): resp.to_dict()
                for code, resp in self.responses.items()
            }
        else:
            result["responses"] = {"200": {"description": "Successful response"}}
        
        if self.security:
            result["security"] = self.security
        
        return result


@dataclass
class Tag:
    """API tag."""
    name: str = ""
    description: str = ""
    external_docs: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result = {"name": self.name}
        
        if self.description:
            result["description"] = self.description
        
        if self.external_docs:
            result["externalDocs"] = self.external_docs
        
        return result


@dataclass
class SecurityScheme:
    """Security scheme."""
    name: str = ""
    type: str = "apiKey"  # apiKey, http, oauth2, openIdConnect
    description: str = ""
    location: str = "header"  # query, header, cookie
    scheme: str = ""  # bearer, basic
    bearer_format: str = ""
    flows: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result = {"type": self.type}
        
        if self.description:
            result["description"] = self.description
        
        if self.type == "apiKey":
            result["name"] = self.name
            result["in"] = self.location
        
        elif self.type == "http":
            result["scheme"] = self.scheme
            if self.bearer_format:
                result["bearerFormat"] = self.bearer_format
        
        elif self.type == "oauth2" and self.flows:
            result["flows"] = self.flows
        
        return result


@dataclass
class APIInfo:
    """API info."""
    title: str = "API"
    description: str = ""
    version: str = "1.0.0"
    terms_of_service: str = ""
    contact: Optional[Contact] = None
    license: Optional[License] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result = {
            "title": self.title,
            "version": self.version,
        }
        
        if self.description:
            result["description"] = self.description
        if self.terms_of_service:
            result["termsOfService"] = self.terms_of_service
        if self.contact:
            result["contact"] = {
                k: v for k, v in {
                    "name": self.contact.name,
                    "email": self.contact.email,
                    "url": self.contact.url,
                }.items() if v
            }
        if self.license:
            result["license"] = {
                "name": self.license.name,
                "url": self.license.url,
            } if self.license.url else {"name": self.license.name}
        
        return result


@dataclass
class OpenAPISpec:
    """OpenAPI specification."""
    openapi: str = "3.0.3"
    info: APIInfo = field(default_factory=APIInfo)
    servers: List[ServerInfo] = field(default_factory=list)
    paths: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    tags: List[Tag] = field(default_factory=list)
    components: Dict[str, Any] = field(default_factory=dict)
    security: List[Dict[str, List[str]]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        result = {
            "openapi": self.openapi,
            "info": self.info.to_dict(),
        }
        
        if self.servers:
            result["servers"] = [
                {"url": s.url, "description": s.description}
                for s in self.servers
            ]
        
        if self.paths:
            result["paths"] = self.paths
        
        if self.tags:
            result["tags"] = [t.to_dict() for t in self.tags]
        
        if self.components:
            result["components"] = self.components
        
        if self.security:
            result["security"] = self.security
        
        return result


# Schema registry
class SchemaRegistry:
    """Schema registry."""
    
    def __init__(self):
        self._schemas: Dict[str, Schema] = {}
    
    def register(self, name: str, schema: Schema) -> None:
        """Register schema."""
        self._schemas[name] = schema
    
    def get(self, name: str) -> Optional[Schema]:
        """Get schema."""
        return self._schemas.get(name)
    
    def get_ref(self, name: str) -> Dict[str, str]:
        """Get schema reference."""
        return {"$ref": f"#/components/schemas/{name}"}
    
    def all(self) -> Dict[str, Schema]:
        """Get all schemas."""
        return self._schemas.copy()
    
    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Convert all to dict."""
        return {name: schema.to_dict() for name, schema in self._schemas.items()}


# Type to schema converter
class TypeConverter:
    """Python type to JSON schema converter."""
    
    _type_map = {
        str: DataType.STRING,
        int: DataType.INTEGER,
        float: DataType.NUMBER,
        bool: DataType.BOOLEAN,
        list: DataType.ARRAY,
        dict: DataType.OBJECT,
    }
    
    @classmethod
    def convert(cls, python_type: Type) -> Schema:
        """Convert Python type to schema."""
        origin = getattr(python_type, "__origin__", None)
        
        if origin is list:
            args = getattr(python_type, "__args__", (Any,))
            item_schema = cls.convert(args[0]) if args else Schema(type=DataType.STRING)
            return Schema(type=DataType.ARRAY, items=item_schema.to_dict())
        
        if origin is dict:
            return Schema(type=DataType.OBJECT)
        
        if python_type in cls._type_map:
            return Schema(type=cls._type_map[python_type])
        
        return Schema(type=DataType.STRING)


# API documentation generator
class APIDocumentation:
    """API documentation generator."""
    
    def __init__(
        self,
        title: str = "API",
        version: str = "1.0.0",
        description: str = "",
    ):
        self._info = APIInfo(
            title=title,
            version=version,
            description=description,
        )
        self._servers: List[ServerInfo] = []
        self._endpoints: List[Endpoint] = []
        self._tags: List[Tag] = []
        self._security_schemes: Dict[str, SecurityScheme] = {}
        self._schema_registry = SchemaRegistry()
        self._global_security: List[Dict[str, List[str]]] = []
    
    def set_info(
        self,
        title: Optional[str] = None,
        version: Optional[str] = None,
        description: Optional[str] = None,
        contact: Optional[Contact] = None,
        license: Optional[License] = None,
    ) -> None:
        """Set API info."""
        if title:
            self._info.title = title
        if version:
            self._info.version = version
        if description:
            self._info.description = description
        if contact:
            self._info.contact = contact
        if license:
            self._info.license = license
    
    def add_server(
        self,
        url: str,
        description: str = "",
    ) -> None:
        """Add server."""
        self._servers.append(ServerInfo(url=url, description=description))
    
    def add_tag(
        self,
        name: str,
        description: str = "",
    ) -> None:
        """Add tag."""
        self._tags.append(Tag(name=name, description=description))
    
    def add_schema(
        self,
        name: str,
        schema: Schema,
    ) -> None:
        """Add reusable schema."""
        self._schema_registry.register(name, schema)
    
    def add_security_scheme(
        self,
        name: str,
        scheme: SecurityScheme,
    ) -> None:
        """Add security scheme."""
        self._security_schemes[name] = scheme
    
    def add_endpoint(
        self,
        path: str,
        method: Union[str, HTTPMethod],
        summary: str = "",
        description: str = "",
        tags: Optional[List[str]] = None,
        parameters: Optional[List[Dict[str, Any]]] = None,
        request_body: Optional[Dict[str, Any]] = None,
        responses: Optional[Dict[int, Dict[str, Any]]] = None,
        deprecated: bool = False,
        operation_id: str = "",
        security: Optional[List[Dict[str, List[str]]]] = None,
    ) -> Endpoint:
        """Add endpoint."""
        if isinstance(method, str):
            method = HTTPMethod(method.lower())
        
        # Convert parameters
        param_objs = []
        if parameters:
            for p in parameters:
                schema = None
                if "schema" in p:
                    schema = Schema(**p["schema"]) if isinstance(p["schema"], dict) else p["schema"]
                
                param_objs.append(Parameter(
                    name=p.get("name", ""),
                    location=ParameterLocation(p.get("in", "query")),
                    description=p.get("description", ""),
                    required=p.get("required", False),
                    schema=schema,
                    example=p.get("example"),
                ))
        
        # Convert request body
        req_body = None
        if request_body:
            req_body = RequestBody(
                description=request_body.get("description", ""),
                required=request_body.get("required", True),
                content=request_body.get("content", {}),
            )
        
        # Convert responses
        resp_objs = {}
        if responses:
            for code, resp in responses.items():
                schema = None
                if "schema" in resp:
                    schema_data = resp["schema"]
                    if isinstance(schema_data, dict):
                        schema = Schema(**{k: v for k, v in schema_data.items() if k != "type"})
                        schema.type = DataType(schema_data.get("type", "object"))
                
                resp_objs[code] = Response(
                    status_code=code,
                    description=resp.get("description", ""),
                    schema=schema,
                )
        
        endpoint = Endpoint(
            path=path,
            method=method,
            summary=summary,
            description=description,
            operation_id=operation_id or f"{method.value}_{path.replace('/', '_').strip('_')}",
            tags=tags or [],
            parameters=param_objs,
            request_body=req_body,
            responses=resp_objs,
            deprecated=deprecated,
            security=security or [],
        )
        
        self._endpoints.append(endpoint)
        
        logger.info(f"Endpoint added: {method.value.upper()} {path}")
        
        return endpoint
    
    def document_function(
        self,
        func: Callable,
        path: str,
        method: Union[str, HTTPMethod] = HTTPMethod.GET,
        tags: Optional[List[str]] = None,
    ) -> Endpoint:
        """Document function as endpoint."""
        summary = func.__name__.replace("_", " ").title()
        description = func.__doc__ or ""
        
        # Extract parameters from function signature
        sig = inspect.signature(func)
        parameters = []
        
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls", "request"):
                continue
            
            schema_type = DataType.STRING
            if param.annotation != inspect.Parameter.empty:
                try:
                    schema = TypeConverter.convert(param.annotation)
                    schema_type = schema.type
                except Exception:
                    pass
            
            parameters.append({
                "name": param_name,
                "in": "query",
                "required": param.default == inspect.Parameter.empty,
                "schema": {"type": schema_type.value},
            })
        
        return self.add_endpoint(
            path=path,
            method=method,
            summary=summary,
            description=description.strip(),
            tags=tags,
            parameters=parameters,
        )
    
    async def generate_openapi(self) -> OpenAPISpec:
        """Generate OpenAPI specification."""
        # Build paths
        paths: Dict[str, Dict[str, Any]] = {}
        
        for endpoint in self._endpoints:
            if endpoint.path not in paths:
                paths[endpoint.path] = {}
            
            paths[endpoint.path][endpoint.method.value] = endpoint.to_dict()
        
        # Build components
        components: Dict[str, Any] = {}
        
        schemas = self._schema_registry.to_dict()
        if schemas:
            components["schemas"] = schemas
        
        if self._security_schemes:
            components["securitySchemes"] = {
                name: scheme.to_dict()
                for name, scheme in self._security_schemes.items()
            }
        
        spec = OpenAPISpec(
            info=self._info,
            servers=self._servers,
            paths=paths,
            tags=self._tags,
            components=components,
            security=self._global_security,
        )
        
        return spec
    
    def to_dict(self) -> Dict[str, Any]:
        """Synchronously generate spec dict."""
        loop = asyncio.new_event_loop()
        try:
            spec = loop.run_until_complete(self.generate_openapi())
            return spec.to_dict()
        finally:
            loop.close()
    
    def to_json(self, indent: int = 2) -> str:
        """Export as JSON."""
        return json.dumps(self.to_dict(), indent=indent)
    
    def to_yaml(self) -> str:
        """Export as YAML."""
        try:
            import yaml
            return yaml.dump(self.to_dict(), default_flow_style=False)
        except ImportError:
            raise APIDocsError("PyYAML required for YAML export")
    
    def get_endpoints(self) -> List[Endpoint]:
        """Get all endpoints."""
        return self._endpoints.copy()


# Decorator for documenting endpoints
def document(
    path: str,
    method: Union[str, HTTPMethod] = HTTPMethod.GET,
    summary: str = "",
    tags: Optional[List[str]] = None,
    docs: Optional[APIDocumentation] = None,
):
    """Decorator to document endpoint."""
    def decorator(func: Callable) -> Callable:
        if docs:
            docs.document_function(func, path, method, tags)
        
        func._api_path = path
        func._api_method = method
        func._api_summary = summary
        func._api_tags = tags
        
        return func
    
    return decorator


# Factory functions
def create_api_docs(
    title: str = "API",
    version: str = "1.0.0",
    description: str = "",
) -> APIDocumentation:
    """Create API documentation."""
    return APIDocumentation(title=title, version=version, description=description)


def create_schema(
    type: Union[str, DataType] = DataType.OBJECT,
    **kwargs,
) -> Schema:
    """Create schema."""
    if isinstance(type, str):
        type = DataType(type)
    return Schema(type=type, **kwargs)


def create_parameter(
    name: str,
    location: Union[str, ParameterLocation] = ParameterLocation.QUERY,
    **kwargs,
) -> Parameter:
    """Create parameter."""
    if isinstance(location, str):
        location = ParameterLocation(location)
    return Parameter(name=name, location=location, **kwargs)


def create_response(
    status_code: int = 200,
    description: str = "",
    schema: Optional[Schema] = None,
) -> Response:
    """Create response."""
    return Response(status_code=status_code, description=description, schema=schema)


__all__ = [
    # Exceptions
    "APIDocsError",
    # Enums
    "HTTPMethod",
    "ParameterLocation",
    "DataType",
    # Data classes
    "Contact",
    "License",
    "ServerInfo",
    "Schema",
    "Parameter",
    "RequestBody",
    "Response",
    "Endpoint",
    "Tag",
    "SecurityScheme",
    "APIInfo",
    "OpenAPISpec",
    # Classes
    "SchemaRegistry",
    "TypeConverter",
    "APIDocumentation",
    # Decorators
    "document",
    # Factory functions
    "create_api_docs",
    "create_schema",
    "create_parameter",
    "create_response",
]
