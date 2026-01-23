"""
Enterprise Function Calling Module.

Provides structured function calling for LLMs, tool invocation,
schema generation, and validation patterns.

Example:
    # Define tools
    @tool(name="search", description="Search the web")
    def search(query: str) -> str:
        ...
    
    # Create toolkit
    toolkit = ToolKit()
    toolkit.register(search)
    
    # Execute function call from LLM
    result = await toolkit.execute(function_call)
"""

from __future__ import annotations

import asyncio
import inspect
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    get_type_hints,
)
from datetime import datetime
from functools import wraps
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')
R = TypeVar('R')


class FunctionCallError(Exception):
    """Function call error."""
    pass


class ValidationError(FunctionCallError):
    """Argument validation error."""
    pass


class ExecutionError(FunctionCallError):
    """Function execution error."""
    pass


class ToolNotFoundError(FunctionCallError):
    """Tool not found."""
    pass


class ParameterType(str, Enum):
    """Parameter types for schema generation."""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


@dataclass
class Parameter:
    """Tool parameter definition."""
    name: str
    type: ParameterType
    description: str = ""
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    items: Optional[Dict[str, Any]] = None  # For array types
    properties: Optional[Dict[str, Any]] = None  # For object types
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert to JSON schema."""
        schema: Dict[str, Any] = {"type": self.type.value}
        
        if self.description:
            schema["description"] = self.description
        
        if self.enum:
            schema["enum"] = self.enum
        
        if self.items and self.type == ParameterType.ARRAY:
            schema["items"] = self.items
        
        if self.properties and self.type == ParameterType.OBJECT:
            schema["properties"] = self.properties
        
        return schema


@dataclass
class FunctionCall:
    """Represents a function call from LLM."""
    name: str
    arguments: Dict[str, Any]
    call_id: Optional[str] = None
    
    @classmethod
    def from_openai(cls, function_call: Dict[str, Any]) -> 'FunctionCall':
        """Parse OpenAI function call format."""
        return cls(
            name=function_call.get("name", ""),
            arguments=json.loads(function_call.get("arguments", "{}")),
            call_id=function_call.get("id"),
        )
    
    @classmethod
    def from_anthropic(cls, tool_use: Dict[str, Any]) -> 'FunctionCall':
        """Parse Anthropic tool use format."""
        return cls(
            name=tool_use.get("name", ""),
            arguments=tool_use.get("input", {}),
            call_id=tool_use.get("id"),
        )


@dataclass
class FunctionResult:
    """Result of function execution."""
    call_id: Optional[str]
    name: str
    result: Any
    success: bool
    error: Optional[str] = None
    duration_ms: float = 0.0
    
    def to_openai_message(self) -> Dict[str, Any]:
        """Convert to OpenAI tool message format."""
        content = json.dumps(self.result) if self.success else self.error
        return {
            "role": "tool",
            "tool_call_id": self.call_id,
            "content": content,
        }
    
    def to_anthropic_result(self) -> Dict[str, Any]:
        """Convert to Anthropic tool result format."""
        return {
            "type": "tool_result",
            "tool_use_id": self.call_id,
            "content": json.dumps(self.result) if self.success else self.error,
            "is_error": not self.success,
        }


@dataclass
class ToolDefinition:
    """Tool definition with schema."""
    name: str
    description: str
    parameters: List[Parameter] = field(default_factory=list)
    func: Optional[Callable] = None
    
    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function schema."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_schema()
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
    
    def to_anthropic_schema(self) -> Dict[str, Any]:
        """Convert to Anthropic tool schema."""
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_schema()
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


def _python_type_to_param_type(python_type: Any) -> ParameterType:
    """Convert Python type to parameter type."""
    type_mapping = {
        str: ParameterType.STRING,
        int: ParameterType.INTEGER,
        float: ParameterType.NUMBER,
        bool: ParameterType.BOOLEAN,
        list: ParameterType.ARRAY,
        dict: ParameterType.OBJECT,
        type(None): ParameterType.NULL,
    }
    
    # Handle Optional types
    origin = getattr(python_type, "__origin__", None)
    if origin is Union:
        args = python_type.__args__
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _python_type_to_param_type(non_none[0])
    
    if origin is list:
        return ParameterType.ARRAY
    
    if origin is dict:
        return ParameterType.OBJECT
    
    return type_mapping.get(python_type, ParameterType.STRING)


def _extract_parameters(func: Callable) -> List[Parameter]:
    """Extract parameters from function signature."""
    sig = inspect.signature(func)
    hints = get_type_hints(func) if hasattr(func, '__annotations__') else {}
    
    # Get docstring parameter descriptions
    doc = inspect.getdoc(func) or ""
    param_docs = {}
    for line in doc.split("\n"):
        line = line.strip()
        if line.startswith(":param "):
            parts = line[7:].split(":", 1)
            if len(parts) == 2:
                param_docs[parts[0].strip()] = parts[1].strip()
    
    parameters = []
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        
        python_type = hints.get(name, str)
        param_type = _python_type_to_param_type(python_type)
        
        required = param.default is inspect.Parameter.empty
        default = None if required else param.default
        
        parameters.append(Parameter(
            name=name,
            type=param_type,
            description=param_docs.get(name, ""),
            required=required,
            default=default,
        ))
    
    return parameters


class Tool(ABC):
    """Abstract tool interface."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get tool description."""
        pass
    
    @abstractmethod
    def get_definition(self) -> ToolDefinition:
        """Get tool definition."""
        pass
    
    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool."""
        pass


class FunctionTool(Tool):
    """Tool wrapping a function."""
    
    def __init__(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[List[Parameter]] = None,
    ):
        self._func = func
        self._name = name or func.__name__
        self._description = description or inspect.getdoc(func) or ""
        self._parameters = parameters or _extract_parameters(func)
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self._name,
            description=self._description,
            parameters=self._parameters,
            func=self._func,
        )
    
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the wrapped function."""
        if asyncio.iscoroutinefunction(self._func):
            return await self._func(**kwargs)
        return self._func(**kwargs)


class ToolKit:
    """Collection of tools for LLM function calling."""
    
    def __init__(self, name: str = "toolkit"):
        self._name = name
        self._tools: Dict[str, Tool] = {}
    
    @property
    def name(self) -> str:
        return self._name
    
    def register(self, tool: Union[Tool, Callable]) -> 'ToolKit':
        """Register a tool."""
        if isinstance(tool, Tool):
            self._tools[tool.name] = tool
        else:
            func_tool = FunctionTool(tool)
            self._tools[func_tool.name] = func_tool
        
        return self
    
    def unregister(self, name: str) -> 'ToolKit':
        """Unregister a tool."""
        self._tools.pop(name, None)
        return self
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all tool names."""
        return list(self._tools.keys())
    
    def get_definitions(self) -> List[ToolDefinition]:
        """Get all tool definitions."""
        return [tool.get_definition() for tool in self._tools.values()]
    
    def to_openai_tools(self) -> List[Dict[str, Any]]:
        """Get OpenAI tools format."""
        return [t.get_definition().to_openai_schema() for t in self._tools.values()]
    
    def to_anthropic_tools(self) -> List[Dict[str, Any]]:
        """Get Anthropic tools format."""
        return [t.get_definition().to_anthropic_schema() for t in self._tools.values()]
    
    async def execute(
        self,
        function_call: FunctionCall,
        validate: bool = True,
    ) -> FunctionResult:
        """Execute a function call."""
        import time
        start = time.time()
        
        tool = self._tools.get(function_call.name)
        if not tool:
            return FunctionResult(
                call_id=function_call.call_id,
                name=function_call.name,
                result=None,
                success=False,
                error=f"Tool '{function_call.name}' not found",
            )
        
        try:
            result = await tool.execute(**function_call.arguments)
            duration = (time.time() - start) * 1000
            
            return FunctionResult(
                call_id=function_call.call_id,
                name=function_call.name,
                result=result,
                success=True,
                duration_ms=duration,
            )
            
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"Tool execution error: {e}")
            
            return FunctionResult(
                call_id=function_call.call_id,
                name=function_call.name,
                result=None,
                success=False,
                error=str(e),
                duration_ms=duration,
            )
    
    async def execute_all(
        self,
        function_calls: List[FunctionCall],
        parallel: bool = True,
    ) -> List[FunctionResult]:
        """Execute multiple function calls."""
        if parallel:
            tasks = [self.execute(fc) for fc in function_calls]
            return await asyncio.gather(*tasks)
        
        results = []
        for fc in function_calls:
            result = await self.execute(fc)
            results.append(result)
        
        return results


class StructuredOutput(Generic[T]):
    """Structured output parser."""
    
    def __init__(
        self,
        output_type: Type[T],
        description: str = "",
    ):
        self._output_type = output_type
        self._description = description
    
    def get_schema(self) -> Dict[str, Any]:
        """Get JSON schema for the output type."""
        if hasattr(self._output_type, "__dataclass_fields__"):
            return self._dataclass_to_schema(self._output_type)
        
        return {"type": "object"}
    
    def _dataclass_to_schema(self, cls: Type) -> Dict[str, Any]:
        """Convert dataclass to JSON schema."""
        from dataclasses import fields as dc_fields
        
        properties = {}
        required = []
        hints = get_type_hints(cls) if hasattr(cls, '__annotations__') else {}
        
        for f in dc_fields(cls):
            python_type = hints.get(f.name, str)
            param_type = _python_type_to_param_type(python_type)
            
            properties[f.name] = {"type": param_type.value}
            
            if f.default is not None and f.default_factory is None:
                required.append(f.name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    
    def parse(self, output: str) -> T:
        """Parse LLM output to structured type."""
        import json
        
        # Try to parse as JSON
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            import re
            match = re.search(r'\{.*\}', output, re.DOTALL)
            if match:
                data = json.loads(match.group())
            else:
                raise ValidationError(f"Cannot parse output as JSON: {output[:100]}")
        
        # Create instance
        if hasattr(self._output_type, "__dataclass_fields__"):
            return self._output_type(**data)
        
        return data


class FunctionCallHandler:
    """
    Handler for LLM function calling loop.
    """
    
    def __init__(
        self,
        toolkit: ToolKit,
        max_iterations: int = 10,
    ):
        self._toolkit = toolkit
        self._max_iterations = max_iterations
    
    async def handle_response(
        self,
        response: Dict[str, Any],
        format: str = "openai",
    ) -> List[FunctionResult]:
        """
        Handle LLM response and execute function calls.
        
        Args:
            response: LLM response
            format: Response format ('openai' or 'anthropic')
        """
        function_calls = self._extract_calls(response, format)
        
        if not function_calls:
            return []
        
        return await self._toolkit.execute_all(function_calls)
    
    def _extract_calls(
        self,
        response: Dict[str, Any],
        format: str,
    ) -> List[FunctionCall]:
        """Extract function calls from response."""
        calls = []
        
        if format == "openai":
            message = response.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls", [])
            
            for tc in tool_calls:
                if tc.get("type") == "function":
                    calls.append(FunctionCall(
                        name=tc["function"]["name"],
                        arguments=json.loads(tc["function"].get("arguments", "{}")),
                        call_id=tc.get("id"),
                    ))
        
        elif format == "anthropic":
            content = response.get("content", [])
            
            for block in content:
                if block.get("type") == "tool_use":
                    calls.append(FunctionCall(
                        name=block["name"],
                        arguments=block.get("input", {}),
                        call_id=block.get("id"),
                    ))
        
        return calls


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[List[Parameter]] = None,
) -> Callable:
    """
    Decorator to create a tool from a function.
    
    Example:
        @tool(name="search", description="Search the web")
        def search(query: str) -> str:
            ...
    """
    def decorator(func: Callable) -> FunctionTool:
        return FunctionTool(
            func=func,
            name=name,
            description=description,
            parameters=parameters,
        )
    
    return decorator


def create_toolkit(*tools: Union[Tool, Callable], name: str = "toolkit") -> ToolKit:
    """
    Factory function to create a toolkit.
    
    Example:
        toolkit = create_toolkit(search, calculate, fetch_data)
    """
    toolkit = ToolKit(name=name)
    
    for t in tools:
        toolkit.register(t)
    
    return toolkit


# Global toolkit registry
_toolkits: Dict[str, ToolKit] = {}


def register_toolkit(toolkit: ToolKit) -> None:
    """Register a toolkit globally."""
    _toolkits[toolkit.name] = toolkit


def get_toolkit(name: str) -> Optional[ToolKit]:
    """Get a registered toolkit."""
    return _toolkits.get(name)


__all__ = [
    # Exceptions
    "FunctionCallError",
    "ValidationError",
    "ExecutionError",
    "ToolNotFoundError",
    # Enums
    "ParameterType",
    # Data classes
    "Parameter",
    "FunctionCall",
    "FunctionResult",
    "ToolDefinition",
    # Tools
    "Tool",
    "FunctionTool",
    # Toolkit
    "ToolKit",
    # Structured output
    "StructuredOutput",
    # Handler
    "FunctionCallHandler",
    # Decorators
    "tool",
    # Factory
    "create_toolkit",
    # Registry
    "register_toolkit",
    "get_toolkit",
]
