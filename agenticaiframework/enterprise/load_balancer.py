"""
Enterprise Load Balancer Module.

Provides load balancing strategies, health checking,
circuit breakers, and service discovery integration.

Example:
    # Create load balancer
    lb = create_load_balancer(
        strategy=LoadBalancingStrategy.ROUND_ROBIN,
        endpoints=["http://server1:8080", "http://server2:8080"],
    )
    
    # Get next endpoint
    endpoint = await lb.get_endpoint()
    
    # Use decorator
    @load_balanced("my-service")
    async def call_service(endpoint: str, data: dict):
        ...
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import random
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class LoadBalancingStrategy(str, Enum):
    """Load balancing strategy."""
    ROUND_ROBIN = "round_robin"
    WEIGHTED_ROUND_ROBIN = "weighted_round_robin"
    LEAST_CONNECTIONS = "least_connections"
    RANDOM = "random"
    IP_HASH = "ip_hash"
    WEIGHTED_RANDOM = "weighted_random"


class EndpointState(str, Enum):
    """Endpoint health state."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    DRAINING = "draining"


class CircuitState(str, Enum):
    """Circuit breaker state."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class EndpointConfig:
    """Endpoint configuration."""
    url: str
    weight: int = 1
    priority: int = 0
    zone: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EndpointStats:
    """Endpoint statistics."""
    requests: int = 0
    successes: int = 0
    failures: int = 0
    active_connections: int = 0
    total_latency_ms: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        if self.requests == 0:
            return 1.0
        return self.successes / self.requests
    
    @property
    def avg_latency_ms(self) -> float:
        if self.requests == 0:
            return 0.0
        return self.total_latency_ms / self.requests


@dataclass
class Endpoint:
    """Load balancer endpoint."""
    config: EndpointConfig
    state: EndpointState = EndpointState.UNKNOWN
    stats: EndpointStats = field(default_factory=EndpointStats)
    circuit: CircuitState = CircuitState.CLOSED
    circuit_opened_at: Optional[datetime] = None
    
    @property
    def url(self) -> str:
        return self.config.url
    
    @property
    def weight(self) -> int:
        return self.config.weight
    
    @property
    def is_available(self) -> bool:
        return (
            self.state in (EndpointState.HEALTHY, EndpointState.UNKNOWN) and
            self.circuit in (CircuitState.CLOSED, CircuitState.HALF_OPEN)
        )


@dataclass
class HealthCheckConfig:
    """Health check configuration."""
    enabled: bool = True
    interval: timedelta = field(default_factory=lambda: timedelta(seconds=10))
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=5))
    path: str = "/health"
    healthy_threshold: int = 2
    unhealthy_threshold: int = 3


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    enabled: bool = True
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    half_open_max_calls: int = 3


class LoadBalancerStrategy(ABC):
    """Abstract load balancing strategy."""
    
    @abstractmethod
    def select(
        self,
        endpoints: List[Endpoint],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Endpoint]:
        """Select an endpoint."""
        pass


class RoundRobinStrategy(LoadBalancerStrategy):
    """Round-robin load balancing."""
    
    def __init__(self):
        self._index = 0
    
    def select(
        self,
        endpoints: List[Endpoint],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Endpoint]:
        available = [e for e in endpoints if e.is_available]
        if not available:
            return None
        
        idx = self._index % len(available)
        self._index += 1
        return available[idx]


class WeightedRoundRobinStrategy(LoadBalancerStrategy):
    """Weighted round-robin load balancing."""
    
    def __init__(self):
        self._weights: Dict[str, int] = {}
        self._current_weights: Dict[str, int] = {}
    
    def select(
        self,
        endpoints: List[Endpoint],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Endpoint]:
        available = [e for e in endpoints if e.is_available]
        if not available:
            return None
        
        # Initialize weights
        total_weight = 0
        for ep in available:
            if ep.url not in self._current_weights:
                self._current_weights[ep.url] = 0
            self._current_weights[ep.url] += ep.weight
            total_weight += ep.weight
        
        # Select highest weight
        selected = max(available, key=lambda e: self._current_weights[e.url])
        
        # Adjust weights
        self._current_weights[selected.url] -= total_weight
        
        return selected


class LeastConnectionsStrategy(LoadBalancerStrategy):
    """Least connections load balancing."""
    
    def select(
        self,
        endpoints: List[Endpoint],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Endpoint]:
        available = [e for e in endpoints if e.is_available]
        if not available:
            return None
        
        return min(available, key=lambda e: e.stats.active_connections)


class RandomStrategy(LoadBalancerStrategy):
    """Random load balancing."""
    
    def select(
        self,
        endpoints: List[Endpoint],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Endpoint]:
        available = [e for e in endpoints if e.is_available]
        if not available:
            return None
        
        return random.choice(available)


class WeightedRandomStrategy(LoadBalancerStrategy):
    """Weighted random load balancing."""
    
    def select(
        self,
        endpoints: List[Endpoint],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Endpoint]:
        available = [e for e in endpoints if e.is_available]
        if not available:
            return None
        
        total_weight = sum(e.weight for e in available)
        rand_val = random.uniform(0, total_weight)
        
        cumulative = 0
        for ep in available:
            cumulative += ep.weight
            if rand_val <= cumulative:
                return ep
        
        return available[-1]


class IpHashStrategy(LoadBalancerStrategy):
    """IP hash load balancing."""
    
    def select(
        self,
        endpoints: List[Endpoint],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Endpoint]:
        available = [e for e in endpoints if e.is_available]
        if not available:
            return None
        
        client_ip = (context or {}).get("client_ip", "default")
        hash_val = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
        
        return available[hash_val % len(available)]


class HealthChecker:
    """
    Health checker for endpoints.
    """
    
    def __init__(self, config: HealthCheckConfig):
        self._config = config
        self._healthy_counts: Dict[str, int] = defaultdict(int)
        self._unhealthy_counts: Dict[str, int] = defaultdict(int)
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def check(self, endpoint: Endpoint) -> bool:
        """Check endpoint health."""
        try:
            import aiohttp
            
            url = f"{endpoint.url.rstrip('/')}{self._config.path}"
            timeout = aiohttp.ClientTimeout(
                total=self._config.timeout.total_seconds()
            )
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    return response.status < 400
                    
        except ImportError:
            # aiohttp not installed, assume healthy
            return True
        except Exception:
            return False
    
    async def run(self, endpoints: List[Endpoint]) -> None:
        """Run health checks continuously."""
        self._running = True
        
        while self._running:
            for endpoint in endpoints:
                healthy = await self.check(endpoint)
                
                if healthy:
                    self._healthy_counts[endpoint.url] += 1
                    self._unhealthy_counts[endpoint.url] = 0
                    
                    if self._healthy_counts[endpoint.url] >= self._config.healthy_threshold:
                        endpoint.state = EndpointState.HEALTHY
                else:
                    self._unhealthy_counts[endpoint.url] += 1
                    self._healthy_counts[endpoint.url] = 0
                    
                    if self._unhealthy_counts[endpoint.url] >= self._config.unhealthy_threshold:
                        endpoint.state = EndpointState.UNHEALTHY
            
            await asyncio.sleep(self._config.interval.total_seconds())
    
    def start(self, endpoints: List[Endpoint]) -> asyncio.Task:
        """Start health checking."""
        self._task = asyncio.create_task(self.run(endpoints))
        return self._task
    
    def stop(self) -> None:
        """Stop health checking."""
        self._running = False
        if self._task:
            self._task.cancel()


class CircuitBreaker:
    """
    Circuit breaker for endpoints.
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self._config = config
        self._failure_counts: Dict[str, int] = defaultdict(int)
        self._success_counts: Dict[str, int] = defaultdict(int)
        self._half_open_calls: Dict[str, int] = defaultdict(int)
    
    def record_success(self, endpoint: Endpoint) -> None:
        """Record successful call."""
        if endpoint.circuit == CircuitState.HALF_OPEN:
            self._success_counts[endpoint.url] += 1
            
            if self._success_counts[endpoint.url] >= self._config.success_threshold:
                endpoint.circuit = CircuitState.CLOSED
                self._reset(endpoint.url)
        else:
            self._failure_counts[endpoint.url] = 0
    
    def record_failure(self, endpoint: Endpoint) -> None:
        """Record failed call."""
        if endpoint.circuit == CircuitState.HALF_OPEN:
            endpoint.circuit = CircuitState.OPEN
            endpoint.circuit_opened_at = datetime.utcnow()
            self._reset(endpoint.url)
        else:
            self._failure_counts[endpoint.url] += 1
            
            if self._failure_counts[endpoint.url] >= self._config.failure_threshold:
                endpoint.circuit = CircuitState.OPEN
                endpoint.circuit_opened_at = datetime.utcnow()
    
    def check_circuit(self, endpoint: Endpoint) -> bool:
        """Check if circuit allows calls."""
        if not self._config.enabled:
            return True
        
        if endpoint.circuit == CircuitState.CLOSED:
            return True
        
        if endpoint.circuit == CircuitState.OPEN:
            # Check if timeout has passed
            if endpoint.circuit_opened_at:
                elapsed = datetime.utcnow() - endpoint.circuit_opened_at
                if elapsed >= self._config.timeout:
                    endpoint.circuit = CircuitState.HALF_OPEN
                    self._half_open_calls[endpoint.url] = 0
                    return True
            return False
        
        if endpoint.circuit == CircuitState.HALF_OPEN:
            # Allow limited calls
            if self._half_open_calls[endpoint.url] < self._config.half_open_max_calls:
                self._half_open_calls[endpoint.url] += 1
                return True
            return False
        
        return True
    
    def _reset(self, url: str) -> None:
        """Reset counters for endpoint."""
        self._failure_counts[url] = 0
        self._success_counts[url] = 0
        self._half_open_calls[url] = 0


class LoadBalancer:
    """
    Load balancer with health checking and circuit breaker.
    """
    
    def __init__(
        self,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
        health_config: Optional[HealthCheckConfig] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
    ):
        self._endpoints: List[Endpoint] = []
        self._strategy = self._create_strategy(strategy)
        self._health_config = health_config or HealthCheckConfig()
        self._circuit_config = circuit_config or CircuitBreakerConfig()
        self._health_checker = HealthChecker(self._health_config)
        self._circuit_breaker = CircuitBreaker(self._circuit_config)
        self._started = False
    
    @property
    def endpoints(self) -> List[Endpoint]:
        return self._endpoints
    
    def add_endpoint(
        self,
        url: str,
        weight: int = 1,
        priority: int = 0,
        **metadata,
    ) -> Endpoint:
        """Add an endpoint."""
        config = EndpointConfig(
            url=url,
            weight=weight,
            priority=priority,
            metadata=metadata,
        )
        endpoint = Endpoint(config=config)
        self._endpoints.append(endpoint)
        return endpoint
    
    def remove_endpoint(self, url: str) -> None:
        """Remove an endpoint."""
        self._endpoints = [e for e in self._endpoints if e.url != url]
    
    async def get_endpoint(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Get next endpoint URL."""
        # Filter by circuit breaker
        available = [
            e for e in self._endpoints
            if self._circuit_breaker.check_circuit(e)
        ]
        
        endpoint = self._strategy.select(available, context)
        
        if endpoint:
            endpoint.stats.active_connections += 1
            return endpoint.url
        
        return None
    
    def record_success(
        self,
        url: str,
        latency_ms: float = 0,
    ) -> None:
        """Record successful request."""
        endpoint = self._get_endpoint(url)
        if endpoint:
            endpoint.stats.requests += 1
            endpoint.stats.successes += 1
            endpoint.stats.active_connections = max(0, endpoint.stats.active_connections - 1)
            endpoint.stats.total_latency_ms += latency_ms
            endpoint.stats.last_success = datetime.utcnow()
            self._circuit_breaker.record_success(endpoint)
    
    def record_failure(self, url: str) -> None:
        """Record failed request."""
        endpoint = self._get_endpoint(url)
        if endpoint:
            endpoint.stats.requests += 1
            endpoint.stats.failures += 1
            endpoint.stats.active_connections = max(0, endpoint.stats.active_connections - 1)
            endpoint.stats.last_failure = datetime.utcnow()
            self._circuit_breaker.record_failure(endpoint)
    
    async def start(self) -> None:
        """Start health checking."""
        if self._started:
            return
        
        self._started = True
        if self._health_config.enabled:
            self._health_checker.start(self._endpoints)
    
    def stop(self) -> None:
        """Stop health checking."""
        self._started = False
        self._health_checker.stop()
    
    def get_stats(self) -> Dict[str, EndpointStats]:
        """Get all endpoint statistics."""
        return {e.url: e.stats for e in self._endpoints}
    
    def drain(self, url: str) -> None:
        """Drain an endpoint (stop sending new requests)."""
        endpoint = self._get_endpoint(url)
        if endpoint:
            endpoint.state = EndpointState.DRAINING
    
    def undrain(self, url: str) -> None:
        """Undrain an endpoint."""
        endpoint = self._get_endpoint(url)
        if endpoint:
            endpoint.state = EndpointState.HEALTHY
    
    def _get_endpoint(self, url: str) -> Optional[Endpoint]:
        """Get endpoint by URL."""
        for endpoint in self._endpoints:
            if endpoint.url == url:
                return endpoint
        return None
    
    def _create_strategy(
        self,
        strategy: LoadBalancingStrategy,
    ) -> LoadBalancerStrategy:
        """Create strategy instance."""
        strategies = {
            LoadBalancingStrategy.ROUND_ROBIN: RoundRobinStrategy,
            LoadBalancingStrategy.WEIGHTED_ROUND_ROBIN: WeightedRoundRobinStrategy,
            LoadBalancingStrategy.LEAST_CONNECTIONS: LeastConnectionsStrategy,
            LoadBalancingStrategy.RANDOM: RandomStrategy,
            LoadBalancingStrategy.WEIGHTED_RANDOM: WeightedRandomStrategy,
            LoadBalancingStrategy.IP_HASH: IpHashStrategy,
        }
        return strategies[strategy]()


class LoadBalancerPool:
    """
    Pool of load balancers for different services.
    """
    
    def __init__(self):
        self._balancers: Dict[str, LoadBalancer] = {}
    
    def register(
        self,
        service: str,
        balancer: LoadBalancer,
    ) -> None:
        """Register a load balancer for a service."""
        self._balancers[service] = balancer
    
    def get(self, service: str) -> Optional[LoadBalancer]:
        """Get load balancer for a service."""
        return self._balancers.get(service)
    
    async def get_endpoint(
        self,
        service: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Get endpoint for a service."""
        balancer = self._balancers.get(service)
        if balancer:
            return await balancer.get_endpoint(context)
        return None
    
    async def start_all(self) -> None:
        """Start all load balancers."""
        for balancer in self._balancers.values():
            await balancer.start()
    
    def stop_all(self) -> None:
        """Stop all load balancers."""
        for balancer in self._balancers.values():
            balancer.stop()


# Global pool
_global_pool: Optional[LoadBalancerPool] = None


# Decorators
def load_balanced(
    service: str,
    retries: int = 3,
    timeout: float = 30.0,
) -> Callable:
    """
    Decorator to load balance function calls.
    
    Example:
        @load_balanced("my-service")
        async def call_service(endpoint: str, data: dict):
            async with aiohttp.ClientSession() as session:
                return await session.post(endpoint, json=data)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            pool = get_global_pool()
            balancer = pool.get(service)
            
            if not balancer:
                raise ValueError(f"No load balancer registered for service: {service}")
            
            last_error = None
            
            for attempt in range(retries):
                endpoint = await balancer.get_endpoint()
                
                if not endpoint:
                    raise RuntimeError(f"No available endpoints for service: {service}")
                
                start = time.perf_counter()
                
                try:
                    result = await asyncio.wait_for(
                        func(endpoint, *args, **kwargs),
                        timeout=timeout,
                    )
                    
                    latency = (time.perf_counter() - start) * 1000
                    balancer.record_success(endpoint, latency)
                    
                    return result
                    
                except Exception as e:
                    balancer.record_failure(endpoint)
                    last_error = e
                    
                    if attempt < retries - 1:
                        await asyncio.sleep(0.1 * (attempt + 1))
            
            raise last_error or RuntimeError("All retries exhausted")
        
        return wrapper
    
    return decorator


def with_retry(
    retries: int = 3,
    delay: float = 0.1,
    backoff: float = 2.0,
) -> Callable:
    """
    Decorator to retry failed calls.
    
    Example:
        @with_retry(retries=3, delay=0.1)
        async def call_api(url: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay
            
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    if attempt < retries - 1:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_error
        
        return wrapper
    
    return decorator


# Factory functions
def create_load_balancer(
    strategy: LoadBalancingStrategy = LoadBalancingStrategy.ROUND_ROBIN,
    endpoints: Optional[List[str]] = None,
    health_check: bool = True,
    circuit_breaker: bool = True,
) -> LoadBalancer:
    """Create a load balancer."""
    health_config = HealthCheckConfig(enabled=health_check)
    circuit_config = CircuitBreakerConfig(enabled=circuit_breaker)
    
    lb = LoadBalancer(
        strategy=strategy,
        health_config=health_config,
        circuit_config=circuit_config,
    )
    
    if endpoints:
        for url in endpoints:
            lb.add_endpoint(url)
    
    return lb


def create_endpoint_config(
    url: str,
    weight: int = 1,
    priority: int = 0,
) -> EndpointConfig:
    """Create endpoint configuration."""
    return EndpointConfig(url=url, weight=weight, priority=priority)


def create_health_check_config(
    interval_seconds: int = 10,
    timeout_seconds: int = 5,
    path: str = "/health",
) -> HealthCheckConfig:
    """Create health check configuration."""
    return HealthCheckConfig(
        interval=timedelta(seconds=interval_seconds),
        timeout=timedelta(seconds=timeout_seconds),
        path=path,
    )


def create_circuit_breaker_config(
    failure_threshold: int = 5,
    timeout_seconds: int = 30,
) -> CircuitBreakerConfig:
    """Create circuit breaker configuration."""
    return CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        timeout=timedelta(seconds=timeout_seconds),
    )


def create_load_balancer_pool() -> LoadBalancerPool:
    """Create a load balancer pool."""
    return LoadBalancerPool()


def get_global_pool() -> LoadBalancerPool:
    """Get global load balancer pool."""
    global _global_pool
    if _global_pool is None:
        _global_pool = create_load_balancer_pool()
    return _global_pool


__all__ = [
    # Enums
    "LoadBalancingStrategy",
    "EndpointState",
    "CircuitState",
    # Data classes
    "EndpointConfig",
    "EndpointStats",
    "Endpoint",
    "HealthCheckConfig",
    "CircuitBreakerConfig",
    # Strategies
    "LoadBalancerStrategy",
    "RoundRobinStrategy",
    "WeightedRoundRobinStrategy",
    "LeastConnectionsStrategy",
    "RandomStrategy",
    "WeightedRandomStrategy",
    "IpHashStrategy",
    # Health checker
    "HealthChecker",
    # Circuit breaker
    "CircuitBreaker",
    # Load balancer
    "LoadBalancer",
    "LoadBalancerPool",
    # Decorators
    "load_balanced",
    "with_retry",
    # Factory functions
    "create_load_balancer",
    "create_endpoint_config",
    "create_health_check_config",
    "create_circuit_breaker_config",
    "create_load_balancer_pool",
    "get_global_pool",
]
