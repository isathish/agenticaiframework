"""
Compliance Decorators.

Convenience decorators for:
- Auditing function calls
- Enforcing policies
- Masking output
"""

from typing import List, Callable

from .types import AuditEventType, AuditSeverity


def audit_action(event_type: AuditEventType = AuditEventType.EXECUTE,
                resource: str = None):
    """Decorator to audit function calls."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # Import here to avoid circular imports
            from . import audit_trail
            
            func_resource = resource or f"{func.__module__}.{func.__name__}"
            
            audit_trail.log(
                event_type=event_type,
                actor=kwargs.get('actor', 'system'),
                resource=func_resource,
                action=func.__name__,
                details={'args_count': len(args), 'kwargs_keys': list(kwargs.keys())},
                outcome='started'
            )
            
            try:
                result = func(*args, **kwargs)
                
                audit_trail.log(
                    event_type=event_type,
                    actor=kwargs.get('actor', 'system'),
                    resource=func_resource,
                    action=func.__name__,
                    details={},
                    outcome='success'
                )
                
                return result
            except Exception as e:
                audit_trail.log(
                    event_type=event_type,
                    actor=kwargs.get('actor', 'system'),
                    resource=func_resource,
                    action=func.__name__,
                    details={'error': str(e)},
                    outcome='failure',
                    severity=AuditSeverity.ERROR
                )
                raise
        
        return wrapper
    return decorator


def enforce_policy(resource: str, action: str):
    """Decorator to enforce policies."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # Import here to avoid circular imports
            from . import policy_engine
            
            context = kwargs.get('policy_context', {})
            actor = kwargs.get('actor', 'system')
            
            result = policy_engine.evaluate(resource, action, context, actor)
            
            if not result['allowed']:
                raise PermissionError(f"Policy denied: {result['reason']}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def mask_output(rules: List[str] = None):
    """Decorator to mask sensitive data in function output."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            # Import here to avoid circular imports
            from . import data_masking
            
            result = func(*args, **kwargs)
            
            if isinstance(result, str):
                masked, _ = data_masking.mask(result, rules)
                return masked
            
            return result
        
        return wrapper
    return decorator


__all__ = ['audit_action', 'enforce_policy', 'mask_output']
