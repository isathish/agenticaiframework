"""
Circuit Breaker.

Circuit breaker pattern to prevent cascading failures.
"""

import time
from typing import Callable, Any, Optional

from ..exceptions import CircuitBreakerOpenError


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures."""
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half-open
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            # Check if recovery timeout has passed
            if (self.last_failure_time and 
                time.time() - self.last_failure_time > self.recovery_timeout):
                self.state = "half-open"
                self.failure_count = 0
            else:
                raise CircuitBreakerOpenError(
                    recovery_timeout=self.recovery_timeout
                )
        
        try:
            result = func(*args, **kwargs)
            
            # Success - reset if in half-open state
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            
            return result
            
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
            
            raise e
    
    def reset(self):
        """Manually reset the circuit breaker."""
        self.state = "closed"
        self.failure_count = 0
        self.last_failure_time = None


__all__ = ['CircuitBreaker']
