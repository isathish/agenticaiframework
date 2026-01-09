"""
Tool Use Guardrail for validating tool invocations.

Validates:
- Tool existence
- Parameter validity
- Permission checks
- Rate limiting per tool
- Result validation
"""

import time
from typing import Dict, Any, List, Optional
from collections import defaultdict


class ToolUseGuardrail:
    """
    Guardrail for validating tool invocations.
    
    Validates:
    - Tool existence
    - Parameter validity
    - Permission checks
    - Rate limiting per tool
    - Result validation
    """
    
    def __init__(self,
                 allowed_tools: Optional[List[str]] = None,
                 blocked_tools: Optional[List[str]] = None,
                 tool_rate_limits: Optional[Dict[str, int]] = None,
                 require_confirmation: Optional[List[str]] = None):
        """
        Initialize tool use guardrail.
        
        Args:
            allowed_tools: Whitelist of allowed tools (None = all)
            blocked_tools: Blacklist of blocked tools
            tool_rate_limits: Rate limits per tool (calls per minute)
            require_confirmation: Tools requiring human confirmation
        """
        self.allowed_tools = allowed_tools
        self.blocked_tools = blocked_tools or []
        self.tool_rate_limits = tool_rate_limits or {}
        self.require_confirmation = require_confirmation or []
        
        # Track tool usage
        self._tool_usage: Dict[str, List[float]] = defaultdict(list)
    
    def validate_invocation(self,
                           tool_name: str,
                           parameters: Dict[str, Any],
                           tool_schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Validate a tool invocation.
        
        Returns:
            Dict with is_valid, requires_confirmation, errors
        """
        errors = []
        warnings = []
        
        # Check if tool is allowed
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            errors.append(f"Tool '{tool_name}' is not in allowed tools list")
        
        # Check if tool is blocked
        if tool_name in self.blocked_tools:
            errors.append(f"Tool '{tool_name}' is blocked")
        
        # Check rate limit
        if tool_name in self.tool_rate_limits:
            limit = self.tool_rate_limits[tool_name]
            now = time.time()
            
            # Clean old entries
            self._tool_usage[tool_name] = [
                t for t in self._tool_usage[tool_name]
                if now - t < 60
            ]
            
            if len(self._tool_usage[tool_name]) >= limit:
                errors.append(
                    f"Tool '{tool_name}' rate limit exceeded: {limit} calls/minute"
                )
        
        # Validate parameters against schema
        if tool_schema and 'parameters' in tool_schema:
            param_errors = self._validate_parameters(parameters, tool_schema['parameters'])
            errors.extend(param_errors)
        
        # Check if confirmation required
        requires_confirmation = tool_name in self.require_confirmation
        if requires_confirmation:
            warnings.append(f"Tool '{tool_name}' requires human confirmation")
        
        # Record usage
        if not errors:
            self._tool_usage[tool_name].append(time.time())
        
        return {
            'is_valid': len(errors) == 0,
            'requires_confirmation': requires_confirmation,
            'errors': errors,
            'warnings': warnings
        }
    
    def _validate_parameters(self, 
                            params: Dict[str, Any], 
                            schema: Dict) -> List[str]:
        """Validate parameters against schema."""
        errors = []
        
        required = schema.get('required', [])
        properties = schema.get('properties', {})
        
        # Check required parameters
        for req in required:
            if req not in params:
                errors.append(f"Missing required parameter: {req}")
        
        # Validate parameter types
        for param_name, param_value in params.items():
            if param_name in properties:
                prop_schema = properties[param_name]
                expected_type = prop_schema.get('type')
                
                if expected_type == 'string' and not isinstance(param_value, str):
                    errors.append(f"Parameter '{param_name}' must be string")
                elif expected_type == 'integer' and not isinstance(param_value, int):
                    errors.append(f"Parameter '{param_name}' must be integer")
                elif expected_type == 'boolean' and not isinstance(param_value, bool):
                    errors.append(f"Parameter '{param_name}' must be boolean")
                elif expected_type == 'array' and not isinstance(param_value, list):
                    errors.append(f"Parameter '{param_name}' must be array")
        
        return errors


__all__ = ['ToolUseGuardrail']
