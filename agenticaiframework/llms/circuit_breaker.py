"""
Circuit Breaker.

Circuit breaker pattern to prevent cascading failures.
Thread-safe implementation with proper exception re-raising.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from ..exceptions import CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Thread-safe circuit breaker to prevent cascading failures."""

    __slots__ = (
        "failure_threshold",
        "recovery_timeout",
        "failure_count",
        "last_failure_time",
        "state",
        "_lock",
    )

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "closed"  # closed, open, half-open
        self._lock = threading.Lock()

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute function with circuit breaker protection."""
        with self._lock:
            if self.state == "open":
                if (
                    self.last_failure_time
                    and time.time() - self.last_failure_time > self.recovery_timeout
                ):
                    self.state = "half-open"
                    self.failure_count = 0
                    logger.info("Circuit breaker transitioning to half-open")
                else:
                    raise CircuitBreakerOpenError(
                        recovery_timeout=self.recovery_timeout
                    )

        try:
            result = func(*args, **kwargs)

            with self._lock:
                if self.state == "half-open":
                    self.state = "closed"
                    self.failure_count = 0
                    logger.info("Circuit breaker closed after successful call")

            return result

        except Exception:
            with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    logger.warning(
                        "Circuit breaker opened after %d failures",
                        self.failure_count,
                    )

            raise  # preserve original traceback

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self.state = "closed"
            self.failure_count = 0
            self.last_failure_time = None
            logger.info("Circuit breaker manually reset")


__all__ = ['CircuitBreaker']
