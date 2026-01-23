"""
Enterprise API Generator - Auto-generate OpenAPI specs for agents.

Provides automatic OpenAPI specification generation
for agent endpoints and workflows.

Features:
- Auto-generate OpenAPI specs
- FastAPI integration
- Endpoint discovery
- Schema generation
- Documentation
"""

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import (
    Any, Callable, Dict, Generic, List, Optional, 
    Type, TypeVar, Union, get_args, get_origin, get_type_hints,
)
import uuid

logger = logging.getLogger(__name__)


# =============================================================================
# OpenAPI Schema Types
# =============================================================================

@dataclass
class SchemaObject:
    """OpenAPI Schema Object."""
    type: str = "object"
    properties: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    description: str = ""
    example: Any = None
    items: Optional["SchemaObject"] = None
    enum: List[Any] = field(default_factory=list)
    format: Optional[str] = None
    
    def to_dict(self) -> Dict:
        result = {"type": self.type}
        
        if self.properties:
            result["properties"] = {
                k: v.to_dict() if isinstance(v, SchemaObject) else v
                for k, v in self.properties.items()
            }
        
        if self.required:
            result["required"] = self.required
        
        if self.description:
            result["description"] = self.description
        
        if self.example is not None:
            result["example"] = self.example
        
        if self.items:
            result["items"] = self.items.to_dict() if isinstance(self.items, SchemaObject) else self.items
        
        if self.enum:
            result["enum"] = self.enum
        
        if self.format:
            result["format"] = self.format
        
        return result


@dataclass
class ParameterObject:
    """OpenAPI Parameter Object."""
    name: str
    location: str = "query"  # query, path, header, cookie
    description: str = ""
    required: bool = False
    schema: SchemaObject = None
    
    def to_dict(self) -> Dict:
        result = {
            "name": self.name,
            "in": self.location,
            "required": self.required,
        }
        
        if self.description:
            result["description"] = self.description
        
        if self.schema:
            result["schema"] = self.schema.to_dict()
        
        return result


@dataclass
class RequestBodyObject:
    """OpenAPI Request Body Object."""
    description: str = ""
    required: bool = True
    content: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "description": self.description,
            "required": self.required,
            "content": self.content,
        }


@dataclass
class ResponseObject:
    """OpenAPI Response Object."""
    description: str
    content: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        result = {"description": self.description}
        
        if self.content:
            result["content"] = self.content
        
        if self.headers:
            result["headers"] = self.headers
        
        return result


@dataclass
class OperationObject:
    """OpenAPI Operation Object."""
    operation_id: str
    summary: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    parameters: List[ParameterObject] = field(default_factory=list)
    request_body: Optional[RequestBodyObject] = None
    responses: Dict[str, ResponseObject] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        result = {
            "operationId": self.operation_id,
            "responses": {k: v.to_dict() for k, v in self.responses.items()},
        }
        
        if self.summary:
            result["summary"] = self.summary
        
        if self.description:
            result["description"] = self.description
        
        if self.tags:
            result["tags"] = self.tags
        
        if self.parameters:
            result["parameters"] = [p.to_dict() for p in self.parameters]
        
        if self.request_body:
            result["requestBody"] = self.request_body.to_dict()
        
        return result


@dataclass
class PathItemObject:
    """OpenAPI Path Item Object."""
    get: Optional[OperationObject] = None
    post: Optional[OperationObject] = None
    put: Optional[OperationObject] = None
    delete: Optional[OperationObject] = None
    patch: Optional[OperationObject] = None
    
    def to_dict(self) -> Dict:
        result = {}
        
        for method in ["get", "post", "put", "delete", "patch"]:
            op = getattr(self, method)
            if op:
                result[method] = op.to_dict()
        
        return result


@dataclass
class OpenAPISpec:
    """Complete OpenAPI Specification."""
    openapi: str = "3.0.3"
    info: Dict[str, Any] = field(default_factory=dict)
    servers: List[Dict[str, Any]] = field(default_factory=list)
    paths: Dict[str, PathItemObject] = field(default_factory=dict)
    components: Dict[str, Any] = field(default_factory=dict)
    tags: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "openapi": self.openapi,
            "info": self.info,
            "servers": self.servers,
            "paths": {k: v.to_dict() for k, v in self.paths.items()},
            "components": self.components,
            "tags": self.tags,
        }
    
    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
    
    def to_yaml(self) -> str:
        try:
            import yaml
            return yaml.dump(self.to_dict(), default_flow_style=False)
        except ImportError:
            raise RuntimeError("PyYAML not installed")


# =============================================================================
# Type to Schema Converter
# =============================================================================

class SchemaConverter:
    """Convert Python types to OpenAPI schemas."""
    
    def __init__(self):
        self._schemas: Dict[str, SchemaObject] = {}
    
    def convert(self, python_type: Type) -> SchemaObject:
        """Convert a Python type to OpenAPI schema."""
        origin = get_origin(python_type)
        args = get_args(python_type)
        
        # Handle None
        if python_type is type(None):
            return SchemaObject(type="null")
        
        # Handle basic types
        if python_type is str:
            return SchemaObject(type="string")
        elif python_type is int:
            return SchemaObject(type="integer")
        elif python_type is float:
            return SchemaObject(type="number")
        elif python_type is bool:
            return SchemaObject(type="boolean")
        
        # Handle Optional
        if origin is Union:
            non_none = [t for t in args if t is not type(None)]
            if len(non_none) == 1:
                return self.convert(non_none[0])
            # anyOf for multiple types
            return SchemaObject(type="object")
        
        # Handle List
        if origin is list:
            items = self.convert(args[0]) if args else SchemaObject(type="object")
            return SchemaObject(type="array", items=items)
        
        # Handle Dict
        if origin is dict:
            return SchemaObject(type="object")
        
        # Handle Enum
        if isinstance(python_type, type) and issubclass(python_type, Enum):
            return SchemaObject(
                type="string",
                enum=[e.value for e in python_type],
            )
        
        # Handle Pydantic models
        try:
            from pydantic import BaseModel
            if isinstance(python_type, type) and issubclass(python_type, BaseModel):
                return self._from_pydantic(python_type)
        except ImportError:
            pass
        
        # Handle dataclasses
        import dataclasses
        if dataclasses.is_dataclass(python_type):
            return self._from_dataclass(python_type)
        
        # Default
        return SchemaObject(type="object")
    
    def _from_pydantic(self, model: Type) -> SchemaObject:
        """Convert Pydantic model to schema."""
        try:
            json_schema = model.model_json_schema()
            return self._json_schema_to_openapi(json_schema)
        except Exception:
            return SchemaObject(type="object")
    
    def _from_dataclass(self, dc: Type) -> SchemaObject:
        """Convert dataclass to schema."""
        import dataclasses
        
        properties = {}
        required = []
        
        for f in dataclasses.fields(dc):
            properties[f.name] = self.convert(f.type)
            
            if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
                required.append(f.name)
        
        return SchemaObject(
            type="object",
            properties=properties,
            required=required,
        )
    
    def _json_schema_to_openapi(self, json_schema: Dict) -> SchemaObject:
        """Convert JSON Schema to OpenAPI Schema."""
        schema_type = json_schema.get("type", "object")
        
        return SchemaObject(
            type=schema_type,
            properties={
                k: self._json_schema_to_openapi(v) if isinstance(v, dict) else SchemaObject(type="string")
                for k, v in json_schema.get("properties", {}).items()
            },
            required=json_schema.get("required", []),
            description=json_schema.get("description", ""),
        )


# =============================================================================
# API Generator
# =============================================================================

class APIGenerator:
    """
    Generate OpenAPI specifications from agents and functions.
    
    Usage:
        >>> generator = APIGenerator(title="My Agent API")
        >>> 
        >>> # Add an agent
        >>> generator.add_agent(my_agent, base_path="/agents/my-agent")
        >>> 
        >>> # Add a function as endpoint
        >>> @generator.endpoint("/search", method="post")
        >>> async def search(query: str) -> List[Result]:
        ...     pass
        >>> 
        >>> # Generate spec
        >>> spec = generator.generate()
    """
    
    def __init__(
        self,
        title: str = "Agent API",
        version: str = "1.0.0",
        description: str = "",
        servers: List[Dict[str, str]] = None,
    ):
        self.title = title
        self.version = version
        self.description = description
        self.servers = servers or [{"url": "http://localhost:8000"}]
        
        self._converter = SchemaConverter()
        self._paths: Dict[str, PathItemObject] = {}
        self._tags: List[Dict[str, str]] = []
        self._schemas: Dict[str, SchemaObject] = {}
    
    def add_agent(
        self,
        agent: Any,
        base_path: str = "/agents",
        tag: str = None,
    ) -> "APIGenerator":
        """Add an agent's endpoints to the spec."""
        agent_name = getattr(agent, "name", agent.__class__.__name__)
        path = f"{base_path}/{agent_name.lower()}"
        
        # Add tag
        tag_name = tag or agent_name
        self._tags.append({"name": tag_name, "description": f"Operations for {agent_name}"})
        
        # Add run endpoint
        run_op = self._create_agent_run_operation(agent, tag_name)
        self._paths[f"{path}/run"] = PathItemObject(post=run_op)
        
        # Add status endpoint
        status_op = self._create_agent_status_operation(agent, tag_name)
        self._paths[f"{path}/status"] = PathItemObject(get=status_op)
        
        # Add any custom methods
        for method_name in dir(agent):
            if method_name.startswith("_"):
                continue
            
            method = getattr(agent, method_name)
            if callable(method) and hasattr(method, "_api_endpoint"):
                endpoint_info = method._api_endpoint
                op = self._create_operation_from_method(method, tag_name)
                
                method_type = endpoint_info.get("method", "post").lower()
                endpoint_path = f"{path}/{endpoint_info.get('path', method_name)}"
                
                path_item = self._paths.get(endpoint_path, PathItemObject())
                setattr(path_item, method_type, op)
                self._paths[endpoint_path] = path_item
        
        return self
    
    def endpoint(
        self,
        path: str,
        method: str = "post",
        tags: List[str] = None,
        summary: str = None,
    ) -> Callable:
        """Decorator to add a function as an endpoint."""
        def decorator(func: Callable) -> Callable:
            op = self._create_operation_from_function(func, tags or [], summary)
            
            path_item = self._paths.get(path, PathItemObject())
            setattr(path_item, method.lower(), op)
            self._paths[path] = path_item
            
            return func
        
        return decorator
    
    def _create_agent_run_operation(self, agent: Any, tag: str) -> OperationObject:
        """Create run operation for an agent."""
        agent_name = getattr(agent, "name", agent.__class__.__name__)
        
        # Create request body schema
        request_schema = SchemaObject(
            type="object",
            properties={
                "input": SchemaObject(type="string", description="Input to the agent"),
                "context": SchemaObject(type="object", description="Additional context"),
            },
            required=["input"],
        )
        
        # Create response schema
        response_schema = SchemaObject(
            type="object",
            properties={
                "output": SchemaObject(type="string", description="Agent output"),
                "metadata": SchemaObject(type="object", description="Execution metadata"),
            },
        )
        
        return OperationObject(
            operation_id=f"run_{agent_name.lower()}",
            summary=f"Run {agent_name}",
            description=f"Execute the {agent_name} agent with the given input.",
            tags=[tag],
            request_body=RequestBodyObject(
                description="Input for the agent",
                required=True,
                content={
                    "application/json": {
                        "schema": request_schema.to_dict(),
                    }
                },
            ),
            responses={
                "200": ResponseObject(
                    description="Successful response",
                    content={
                        "application/json": {
                            "schema": response_schema.to_dict(),
                        }
                    },
                ),
                "400": ResponseObject(description="Bad request"),
                "500": ResponseObject(description="Internal server error"),
            },
        )
    
    def _create_agent_status_operation(self, agent: Any, tag: str) -> OperationObject:
        """Create status operation for an agent."""
        agent_name = getattr(agent, "name", agent.__class__.__name__)
        
        return OperationObject(
            operation_id=f"status_{agent_name.lower()}",
            summary=f"Get {agent_name} Status",
            description=f"Get the current status of the {agent_name} agent.",
            tags=[tag],
            responses={
                "200": ResponseObject(
                    description="Agent status",
                    content={
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "status": {"type": "string", "enum": ["active", "inactive", "error"]},
                                    "uptime": {"type": "number"},
                                    "last_run": {"type": "string", "format": "date-time"},
                                },
                            }
                        }
                    },
                ),
            },
        )
    
    def _create_operation_from_function(
        self,
        func: Callable,
        tags: List[str],
        summary: str = None,
    ) -> OperationObject:
        """Create operation from a function."""
        # Get type hints
        hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}
        return_type = hints.pop("return", None)
        
        # Build parameters/request body from function args
        sig = inspect.signature(func)
        parameters = []
        properties = {}
        required = []
        
        for name, param in sig.parameters.items():
            if name in ["self", "cls"]:
                continue
            
            param_type = hints.get(name, str)
            schema = self._converter.convert(param_type)
            
            properties[name] = schema
            if param.default is inspect.Parameter.empty:
                required.append(name)
        
        request_body = None
        if properties:
            request_body = RequestBodyObject(
                content={
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {k: v.to_dict() for k, v in properties.items()},
                            "required": required,
                        }
                    }
                },
            )
        
        # Build response
        response_schema = self._converter.convert(return_type) if return_type else SchemaObject(type="object")
        
        return OperationObject(
            operation_id=func.__name__,
            summary=summary or func.__name__.replace("_", " ").title(),
            description=func.__doc__ or "",
            tags=tags,
            request_body=request_body,
            responses={
                "200": ResponseObject(
                    description="Successful response",
                    content={
                        "application/json": {
                            "schema": response_schema.to_dict(),
                        }
                    },
                ),
            },
        )
    
    def _create_operation_from_method(
        self,
        method: Callable,
        tag: str,
    ) -> OperationObject:
        """Create operation from an agent method."""
        return self._create_operation_from_function(method, [tag])
    
    def generate(self) -> OpenAPISpec:
        """Generate the complete OpenAPI specification."""
        return OpenAPISpec(
            info={
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            servers=self.servers,
            paths=self._paths,
            components={
                "schemas": {k: v.to_dict() for k, v in self._schemas.items()},
            },
            tags=self._tags,
        )


# =============================================================================
# Decorators
# =============================================================================

def api_endpoint(path: str = None, method: str = "post", summary: str = None):
    """
    Decorator to mark a method as an API endpoint.
    
    Usage:
        >>> class MyAgent:
        ...     @api_endpoint("/analyze", method="post", summary="Analyze data")
        ...     async def analyze(self, data: str) -> Dict:
        ...         pass
    """
    def decorator(func: Callable) -> Callable:
        func._api_endpoint = {
            "path": path or func.__name__,
            "method": method,
            "summary": summary or func.__name__,
        }
        return func
    
    return decorator


# =============================================================================
# FastAPI Integration
# =============================================================================

def create_fastapi_app(spec: OpenAPISpec) -> Any:
    """
    Create a FastAPI app from an OpenAPI spec.
    
    Usage:
        >>> spec = generator.generate()
        >>> app = create_fastapi_app(spec)
    """
    try:
        from fastapi import FastAPI
        
        app = FastAPI(
            title=spec.info.get("title", "API"),
            version=spec.info.get("version", "1.0.0"),
            description=spec.info.get("description", ""),
            openapi_tags=spec.tags,
        )
        
        return app
        
    except ImportError:
        raise RuntimeError("FastAPI not installed. Install with: pip install fastapi")


def register_agent_routes(app: Any, agent: Any, base_path: str = "/agents"):
    """
    Register agent routes with a FastAPI app.
    
    Usage:
        >>> app = FastAPI()
        >>> register_agent_routes(app, my_agent)
    """
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
        
        class RunRequest(BaseModel):
            input: str
            context: dict = {}
        
        agent_name = getattr(agent, "name", agent.__class__.__name__)
        path = f"{base_path}/{agent_name.lower()}"
        
        @app.post(f"{path}/run")
        async def run_agent(request: RunRequest):
            try:
                if hasattr(agent, "run"):
                    result = await agent.run(request.input)
                elif hasattr(agent, "process"):
                    result = await agent.process(request.input)
                else:
                    result = str(agent)
                
                return {"output": result, "metadata": {}}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get(f"{path}/status")
        async def get_status():
            return {
                "status": "active",
                "agent": agent_name,
            }
        
    except ImportError:
        raise RuntimeError("FastAPI not installed")


# =============================================================================
# Helper Functions
# =============================================================================

def generate_openapi(
    agents: List[Any] = None,
    functions: List[Callable] = None,
    title: str = "Agent API",
    version: str = "1.0.0",
) -> OpenAPISpec:
    """Generate OpenAPI spec from agents and functions."""
    generator = APIGenerator(title=title, version=version)
    
    if agents:
        for agent in agents:
            generator.add_agent(agent)
    
    return generator.generate()


def save_openapi_spec(spec: OpenAPISpec, path: str, format: str = "json"):
    """Save OpenAPI spec to file."""
    with open(path, "w") as f:
        if format == "json":
            f.write(spec.to_json())
        elif format == "yaml":
            f.write(spec.to_yaml())
