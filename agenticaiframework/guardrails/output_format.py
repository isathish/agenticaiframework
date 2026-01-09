"""
Output Format Guardrail for validating output format and structure.

Validates:
- JSON schema compliance
- Required fields
- Field types
- Value constraints
"""

import json
from typing import Dict, Any, List, Optional


class OutputFormatGuardrail:
    """
    Guardrail for validating output format and structure.
    
    Validates:
    - JSON schema compliance
    - Required fields
    - Field types
    - Value constraints
    """
    
    def __init__(self,
                 schema: Optional[Dict[str, Any]] = None,
                 required_fields: Optional[List[str]] = None,
                 max_length: Optional[int] = None,
                 allowed_formats: Optional[List[str]] = None):
        """
        Initialize output format guardrail.
        
        Args:
            schema: JSON schema for validation
            required_fields: List of required fields
            max_length: Maximum output length
            allowed_formats: List of allowed output formats (json, xml, text, markdown)
        """
        self.schema = schema or {}
        self.required_fields = required_fields or []
        self.max_length = max_length
        self.allowed_formats = allowed_formats or ['json', 'text', 'markdown']
    
    def validate(self, output: Any) -> Dict[str, Any]:
        """
        Validate output format.
        
        Returns:
            Dict with is_valid, errors, and suggestions
        """
        errors = []
        suggestions = []
        
        # Check length
        if self.max_length and isinstance(output, str):
            if len(output) > self.max_length:
                errors.append(f"Output exceeds max length: {len(output)} > {self.max_length}")
                suggestions.append("Consider summarizing or truncating the output")
        
        # Check if JSON
        if isinstance(output, str):
            try:
                parsed = json.loads(output)
                
                # Check required fields
                for req_field in self.required_fields:
                    if req_field not in parsed:
                        errors.append(f"Missing required field: {req_field}")
                
                # Schema validation (basic)
                if self.schema:
                    errors.extend(self._validate_schema(parsed, self.schema))
                    
            except json.JSONDecodeError:
                if 'json' in self.allowed_formats and output.strip().startswith('{'):
                    errors.append("Output appears to be malformed JSON")
                    suggestions.append("Ensure proper JSON formatting")
        
        elif isinstance(output, dict):
            # Check required fields
            for req_field in self.required_fields:
                if req_field not in output:
                    errors.append(f"Missing required field: {req_field}")
            
            # Schema validation
            if self.schema:
                errors.extend(self._validate_schema(output, self.schema))
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'suggestions': suggestions
        }
    
    def _validate_schema(self, data: Dict, schema: Dict) -> List[str]:
        """Basic schema validation."""
        errors = []
        
        for schema_field, field_schema in schema.items():
            if schema_field not in data:
                if field_schema.get('required', False):
                    errors.append(f"Missing required field: {schema_field}")
                continue
            
            value = data[schema_field]
            expected_type = field_schema.get('type')
            
            if expected_type:
                type_map = {
                    'string': str,
                    'integer': int,
                    'number': (int, float),
                    'boolean': bool,
                    'array': list,
                    'object': dict
                }
                
                expected = type_map.get(expected_type)
                if expected and not isinstance(value, expected):
                    errors.append(
                        f"Field '{schema_field}' has wrong type: expected {expected_type}, got {type(value).__name__}"
                    )
        
        return errors


__all__ = ['OutputFormatGuardrail']
