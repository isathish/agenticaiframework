"""
Enterprise JSON Mode - Structured JSON output with validation.

Provides guaranteed JSON output from LLMs with
Pydantic model validation and schema generation.

Features:
- Pydantic model integration
- JSON schema generation
- Output validation
- Auto-repair for malformed JSON
- Type-safe responses
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import (
    Any, Callable, Dict, Generic, List, Optional, 
    Type, TypeVar, Union, get_args, get_origin,
)

logger = logging.getLogger(__name__)


# Type variable for generic model
T = TypeVar("T")


# =============================================================================
# JSON Schema Generation
# =============================================================================

def python_type_to_json_schema(python_type: Type) -> Dict[str, Any]:
    """Convert Python type to JSON schema."""
    origin = get_origin(python_type)
    args = get_args(python_type)
    
    # Handle None
    if python_type is type(None):
        return {"type": "null"}
    
    # Handle basic types
    if python_type is str:
        return {"type": "string"}
    elif python_type is int:
        return {"type": "integer"}
    elif python_type is float:
        return {"type": "number"}
    elif python_type is bool:
        return {"type": "boolean"}
    
    # Handle Optional
    if origin is Union:
        non_none_types = [t for t in args if t is not type(None)]
        if len(non_none_types) == 1:
            # Optional[X] -> nullable X
            schema = python_type_to_json_schema(non_none_types[0])
            return {"anyOf": [schema, {"type": "null"}]}
        else:
            # Union of multiple types
            return {"anyOf": [python_type_to_json_schema(t) for t in non_none_types]}
    
    # Handle List
    if origin is list:
        if args:
            return {
                "type": "array",
                "items": python_type_to_json_schema(args[0]),
            }
        return {"type": "array"}
    
    # Handle Dict
    if origin is dict:
        return {"type": "object"}
    
    # Handle Pydantic models
    try:
        from pydantic import BaseModel
        if isinstance(python_type, type) and issubclass(python_type, BaseModel):
            return python_type.model_json_schema()
    except ImportError:
        pass
    
    # Handle dataclasses
    import dataclasses
    if dataclasses.is_dataclass(python_type):
        properties = {}
        required = []
        
        for f in dataclasses.fields(python_type):
            properties[f.name] = python_type_to_json_schema(f.type)
            if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
                required.append(f.name)
        
        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    
    # Fallback
    return {"type": "object"}


def generate_json_schema(model: Type[T]) -> Dict[str, Any]:
    """Generate JSON schema from a model."""
    try:
        from pydantic import BaseModel
        if isinstance(model, type) and issubclass(model, BaseModel):
            return model.model_json_schema()
    except ImportError:
        pass
    
    return python_type_to_json_schema(model)


# =============================================================================
# JSON Extractor
# =============================================================================

class JSONExtractor:
    """
    Extracts JSON from LLM responses.
    
    Handles common issues like:
    - Markdown code blocks
    - Leading/trailing text
    - Malformed JSON
    """
    
    # Patterns for extracting JSON
    CODE_BLOCK_PATTERN = re.compile(r'```(?:json)?\s*([\s\S]*?)```')
    JSON_OBJECT_PATTERN = re.compile(r'\{[\s\S]*\}')
    JSON_ARRAY_PATTERN = re.compile(r'\[[\s\S]*\]')
    
    def extract(self, text: str) -> str:
        """Extract JSON from text."""
        # Try code block first
        match = self.CODE_BLOCK_PATTERN.search(text)
        if match:
            return match.group(1).strip()
        
        # Try to find JSON object
        match = self.JSON_OBJECT_PATTERN.search(text)
        if match:
            return match.group(0)
        
        # Try to find JSON array
        match = self.JSON_ARRAY_PATTERN.search(text)
        if match:
            return match.group(0)
        
        # Return original text
        return text.strip()
    
    def extract_and_parse(self, text: str) -> Any:
        """Extract and parse JSON from text."""
        json_str = self.extract(text)
        return json.loads(json_str)


class JSONRepairer:
    """
    Attempts to repair malformed JSON.
    
    Handles common issues:
    - Missing quotes
    - Trailing commas
    - Single quotes instead of double
    - Missing closing brackets
    """
    
    def repair(self, text: str) -> str:
        """Attempt to repair malformed JSON."""
        # Replace single quotes with double quotes
        text = re.sub(r"(?<!\\)'", '"', text)
        
        # Remove trailing commas
        text = re.sub(r',\s*([}\]])', r'\1', text)
        
        # Add missing closing brackets
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        
        if open_braces > 0:
            text += '}' * open_braces
        
        if open_brackets > 0:
            text += ']' * open_brackets
        
        # Fix unquoted keys
        text = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
        
        return text
    
    def try_repair(self, text: str) -> Optional[Any]:
        """Try to repair and parse JSON."""
        repaired = self.repair(text)
        
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None


# =============================================================================
# Typed Response
# =============================================================================

@dataclass
class JSONResponse(Generic[T]):
    """Response with parsed JSON."""
    raw_response: str
    json_str: str
    parsed: T
    
    # Validation
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    # Repair info
    was_repaired: bool = False


# =============================================================================
# JSON Mode Handler
# =============================================================================

class JSONMode(Generic[T]):
    """
    Handles JSON mode for LLM responses.
    
    Usage:
        >>> from pydantic import BaseModel
        >>> 
        >>> class User(BaseModel):
        ...     name: str
        ...     age: int
        >>> 
        >>> json_mode = JSONMode(User)
        >>> 
        >>> # Get system prompt for JSON mode
        >>> system_prompt = json_mode.get_system_prompt()
        >>> 
        >>> # Parse response
        >>> response = json_mode.parse(llm_response)
        >>> print(response.parsed.name)
    """
    
    def __init__(
        self,
        model: Type[T],
        strict: bool = True,
        auto_repair: bool = True,
    ):
        self.model = model
        self.strict = strict
        self.auto_repair = auto_repair
        
        self._extractor = JSONExtractor()
        self._repairer = JSONRepairer()
        self._schema = generate_json_schema(model)
    
    @property
    def schema(self) -> Dict[str, Any]:
        """Get the JSON schema."""
        return self._schema
    
    def get_system_prompt(self, base_prompt: str = "") -> str:
        """Get system prompt with JSON schema."""
        schema_str = json.dumps(self._schema, indent=2)
        
        json_instruction = f"""
{base_prompt}

You must respond with valid JSON that matches this schema:
```json
{schema_str}
```

Important:
- Respond ONLY with the JSON object, no additional text
- Ensure all required fields are present
- Use the correct data types as specified
"""
        return json_instruction.strip()
    
    def get_function_schema(self) -> Dict[str, Any]:
        """Get schema for function calling."""
        return {
            "name": "output",
            "description": "The structured output",
            "parameters": self._schema,
        }
    
    def parse(self, response: str) -> JSONResponse[T]:
        """Parse LLM response to typed model."""
        try:
            # Extract JSON
            json_str = self._extractor.extract(response)
            
            # Try to parse
            try:
                data = json.loads(json_str)
                was_repaired = False
            except json.JSONDecodeError:
                if self.auto_repair:
                    data = self._repairer.try_repair(json_str)
                    if data is None:
                        raise
                    was_repaired = True
                else:
                    raise
            
            # Validate and create model
            parsed, errors = self._validate_and_create(data)
            
            return JSONResponse(
                raw_response=response,
                json_str=json_str,
                parsed=parsed,
                is_valid=len(errors) == 0,
                validation_errors=errors,
                was_repaired=was_repaired,
            )
            
        except Exception as e:
            logger.error(f"Failed to parse JSON response: {e}")
            
            return JSONResponse(
                raw_response=response,
                json_str="",
                parsed=None,
                is_valid=False,
                validation_errors=[str(e)],
            )
    
    def _validate_and_create(self, data: Any) -> tuple[Optional[T], List[str]]:
        """Validate data and create model instance."""
        errors = []
        
        try:
            # Try Pydantic
            from pydantic import BaseModel, ValidationError
            
            if isinstance(self.model, type) and issubclass(self.model, BaseModel):
                try:
                    return self.model.model_validate(data), []
                except ValidationError as e:
                    errors = [str(err) for err in e.errors()]
                    if self.strict:
                        return None, errors
                    # Try to create anyway
                    return self.model.model_construct(**data), errors
        except ImportError:
            pass
        
        # Try dataclass
        import dataclasses
        if dataclasses.is_dataclass(self.model):
            try:
                return self.model(**data), []
            except TypeError as e:
                return None, [str(e)]
        
        # Just return the data
        return data, []
    
    async def parse_async(self, response: str) -> JSONResponse[T]:
        """Async parse (same as sync for now)."""
        return self.parse(response)


# =============================================================================
# Decorator for JSON Mode
# =============================================================================

def json_output(model: Type[T], strict: bool = True):
    """
    Decorator to enable JSON mode for a function.
    
    Usage:
        >>> @json_output(User)
        ... async def get_user(prompt: str) -> User:
        ...     response = await llm.chat(prompt)
        ...     return response  # Will be parsed as JSON
    """
    def decorator(func: Callable) -> Callable:
        json_mode = JSONMode(model, strict=strict)
        
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            if isinstance(result, str):
                response = json_mode.parse(result)
                if response.is_valid:
                    return response.parsed
                raise ValueError(f"Invalid JSON: {response.validation_errors}")
            return result
        
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if isinstance(result, str):
                response = json_mode.parse(result)
                if response.is_valid:
                    return response.parsed
                raise ValueError(f"Invalid JSON: {response.validation_errors}")
            return result
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            async_wrapper.__name__ = func.__name__
            async_wrapper.__doc__ = func.__doc__
            async_wrapper.json_mode = json_mode
            return async_wrapper
        else:
            sync_wrapper.__name__ = func.__name__
            sync_wrapper.__doc__ = func.__doc__
            sync_wrapper.json_mode = json_mode
            return sync_wrapper
    
    return decorator


# =============================================================================
# Common Models
# =============================================================================

@dataclass
class TextWithConfidence:
    """Text with confidence score."""
    text: str
    confidence: float


@dataclass
class EntityExtraction:
    """Extracted entities."""
    entities: List[Dict[str, Any]]


@dataclass
class Classification:
    """Classification result."""
    label: str
    confidence: float
    reasoning: Optional[str] = None


@dataclass
class Sentiment:
    """Sentiment analysis result."""
    sentiment: str  # positive, negative, neutral
    score: float  # -1 to 1
    aspects: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Summary:
    """Summary result."""
    summary: str
    key_points: List[str] = field(default_factory=list)
    word_count: int = 0


@dataclass
class Translation:
    """Translation result."""
    translated_text: str
    source_language: str
    target_language: str


@dataclass
class CodeGeneration:
    """Code generation result."""
    code: str
    language: str
    explanation: Optional[str] = None
    imports: List[str] = field(default_factory=list)


@dataclass
class StructuredAnswer:
    """Structured Q&A answer."""
    answer: str
    confidence: float
    sources: List[str] = field(default_factory=list)
    follow_up_questions: List[str] = field(default_factory=list)


# =============================================================================
# Helper Functions
# =============================================================================

def create_json_mode(model: Type[T], **kwargs) -> JSONMode[T]:
    """Create a JSON mode handler."""
    return JSONMode(model, **kwargs)


def extract_json(text: str) -> Any:
    """Extract and parse JSON from text."""
    return JSONExtractor().extract_and_parse(text)


def repair_json(text: str) -> str:
    """Attempt to repair malformed JSON."""
    return JSONRepairer().repair(text)


def schema_from_model(model: Type) -> Dict[str, Any]:
    """Generate JSON schema from a model."""
    return generate_json_schema(model)
