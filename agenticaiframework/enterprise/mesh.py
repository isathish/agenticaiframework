"""
Enterprise Service Mesh Module.

Provides service mesh patterns, sidecar proxy, traffic management,
and observability for microservices architectures.

Example:
    # Create mesh
    mesh = create_service_mesh()
    
    # Register service
    mesh.register("payment-service", address="localhost:8080")
    
    # Add sidecar
    @mesh_sidecar("payment-service")
    async def payment_handler(request):
        ...
    
    # Traffic management
    mesh.add_traffic_rule(
        source="api-gateway",
        destination="payment-service",
        weight=100
    )
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
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

logger = logging.getLogger(__name__)

T = TypeVar('T')


class MeshError(Exception):
    """Service mesh error."""
    pass


class ServiceNotFoundError(MeshError):
    """Service not found."""
    pass


class CircuitOpenError(MeshError):
    """Circuit is open."""
    pass


class LoadBalanceStrategy(str, Enum):
    """Load balancing strategy."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"
    CONSISTENT_HASH = "consistent_hash"


class RetryPolicy(str, Enum):
    """Retry policy."""
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL = "exponential"
    LINEAR = "linear"


class CircuitState(str, Enum):
    """Circuit breaker state."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class TrafficPolicy(str, Enum):
    """Traffic policy."""
    ALLOW = "allow"
    DENY = "deny"
    RATE_LIMIT = "rate_limit"
    MIRROR = "mirror"


@dataclass
class ServiceEndpoint:
    """Service endpoint."""
    endpoint_id: str
    address: str
    port: int
    weight: int = 100
    healthy: bool = True
    connections: int = 0
    last_health_check: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceConfig:
    """Service configuration in mesh."""
    service_id: str
    name: str
    endpoints: List[ServiceEndpoint]
    load_balance: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN
    timeout_ms: int = 30000
    retry_policy: RetryPolicy = RetryPolicy.FIXED
    max_retries: int = 3
    circuit_breaker: bool = True
    circuit_threshold: int = 5
    circuit_timeout_seconds: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrafficRule:
    """Traffic routing rule."""
    rule_id: str
    source_service: Optional[str]
    destination_service: str
    weight: int = 100
    policy: TrafficPolicy = TrafficPolicy.ALLOW
    headers_match: Dict[str, str] = field(default_factory=dict)
    rate_limit_rps: Optional[int] = None
    timeout_ms: Optional[int] = None
    retry_on: List[int] = field(default_factory=list)  # HTTP status codes


@dataclass
class RequestContext:
    """Request context for mesh."""
    request_id: str
    source_service: Optional[str]
    destination_service: str
    method: str = "GET"
    path: str = "/"
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None


@dataclass
class RequestMetrics:
    """Metrics for a request."""
    request_id: str
    service: str
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)


class CircuitBreaker:
    """
    Circuit breaker for service protection.
    """
    
    def __init__(
        self,
        service_id: str,
        threshold: int = 5,
        timeout_seconds: int = 30,
    ):
        self._service_id = service_id
        self._threshold = threshold
        self._timeout_seconds = timeout_seconds
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED
    
    async def record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure = datetime.now()
            
            if self._failure_count >= self._threshold:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit opened for {self._service_id}")
    
    async def allow_request(self) -> bool:
        """Check if request is allowed."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # Check if timeout has passed
                if self._last_failure:
                    elapsed = (datetime.now() - self._last_failure).total_seconds()
                    
                    if elapsed >= self._timeout_seconds:
                        self._state = CircuitState.HALF_OPEN
                        return True
                
                return False
            
            # Half-open: allow one request
            return True


class LoadBalancer:
    """
    Load balancer for service endpoints.
    """
    
    def __init__(
        self,
        strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
    ):
        self._strategy = strategy
        self._index = 0
        self._lock = asyncio.Lock()
    
    async def select(
        self,
        endpoints: List[ServiceEndpoint],
        context: Optional[RequestContext] = None,
    ) -> Optional[ServiceEndpoint]:
        """Select an endpoint."""
        healthy = [e for e in endpoints if e.healthy]
        
        if not healthy:
            return None
        
        if self._strategy == LoadBalanceStrategy.ROUND_ROBIN:
            return await self._round_robin(healthy)
        
        elif self._strategy == LoadBalanceStrategy.RANDOM:
            return random.choice(healthy)
        
        elif self._strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
            return min(healthy, key=lambda e: e.connections)
        
        elif self._strategy == LoadBalanceStrategy.WEIGHTED:
            return await self._weighted_select(healthy)
        
        elif self._strategy == LoadBalanceStrategy.CONSISTENT_HASH:
            if context and context.request_id:
                idx = hash(context.request_id) % len(healthy)
                return healthy[idx]
            return random.choice(healthy)
        
        return healthy[0]
    
    async def _round_robin(
        self,
        endpoints: List[ServiceEndpoint],
    ) -> ServiceEndpoint:
        """Round-robin selection."""
        async with self._lock:
            endpoint = endpoints[self._index % len(endpoints)]
            self._index += 1
            return endpoint
    
    async def _weighted_select(
        self,
        endpoints: List[ServiceEndpoint],
    ) -> ServiceEndpoint:
        """Weighted random selection."""
        total_weight = sum(e.weight for e in endpoints)
        rand = random.randint(0, total_weight - 1)
        
        cumulative = 0
        for endpoint in endpoints:
            cumulative += endpoint.weight
            if rand < cumulative:
                return endpoint
        
        return endpoints[-1]


class Sidecar:
    """
    Sidecar proxy for a service.
    """
    
    def __init__(
        self,
        service_id: str,
        config: ServiceConfig,
    ):
        self._service_id = service_id
        self._config = config
        self._circuit = CircuitBreaker(
            service_id,
            config.circuit_threshold,
            config.circuit_timeout_seconds,
        )
        self._balancer = LoadBalancer(config.load_balance)
        self._request_count = 0
        self._error_count = 0
    
    @property
    def service_id(self) -> str:
        return self._service_id
    
    @property
    def circuit_state(self) -> CircuitState:
        return self._circuit.state
    
    async def handle_request(
        self,
        context: RequestContext,
        handler: Callable[[ServiceEndpoint], Awaitable[Any]],
    ) -> Any:
        """Handle a request through the sidecar."""
        self._request_count += 1
        
        # Check circuit breaker
        if self._config.circuit_breaker:
            if not await self._circuit.allow_request():
                raise CircuitOpenError(
                    f"Circuit open for {self._service_id}"
                )
        
        # Select endpoint
        endpoint = await self._balancer.select(
            self._config.endpoints,
            context,
        )
        
        if not endpoint:
            raise ServiceNotFoundError(
                f"No healthy endpoints for {self._service_id}"
            )
        
        # Execute with retry
        last_error = None
        retries = 0
        
        while retries <= self._config.max_retries:
            try:
                endpoint.connections += 1
                
                result = await asyncio.wait_for(
                    handler(endpoint),
                    timeout=self._config.timeout_ms / 1000,
                )
                
                endpoint.connections -= 1
                
                if self._config.circuit_breaker:
                    await self._circuit.record_success()
                
                return result
            
            except asyncio.TimeoutError as e:
                last_error = e
                endpoint.connections -= 1
                retries += 1
            
            except Exception as e:
                last_error = e
                endpoint.connections -= 1
                self._error_count += 1
                
                if self._config.circuit_breaker:
                    await self._circuit.record_failure()
                
                retries += 1
            
            # Retry delay
            if retries <= self._config.max_retries:
                if self._config.retry_policy == RetryPolicy.EXPONENTIAL:
                    await asyncio.sleep(2 ** retries * 0.1)
                elif self._config.retry_policy == RetryPolicy.LINEAR:
                    await asyncio.sleep(retries * 0.1)
                elif self._config.retry_policy == RetryPolicy.FIXED:
                    await asyncio.sleep(0.1)
        
        raise last_error or MeshError("Request failed after retries")


class MetricsCollector:
    """
    Metrics collector for mesh observability.
    """
    
    def __init__(self):
        self._metrics: List[RequestMetrics] = []
        self._lock = asyncio.Lock()
    
    async def record(self, metrics: RequestMetrics) -> None:
        """Record request metrics."""
        async with self._lock:
            self._metrics.append(metrics)
            
            # Keep last 10000 metrics
            if len(self._metrics) > 10000:
                self._metrics = self._metrics[-10000:]
    
    async def get_service_metrics(
        self,
        service: str,
        period_seconds: int = 300,
    ) -> Dict[str, Any]:
        """Get metrics for a service."""
        cutoff = datetime.now() - timedelta(seconds=period_seconds)
        
        recent = [
            m for m in self._metrics
            if m.service == service and m.timestamp > cutoff
        ]
        
        if not recent:
            return {
                "request_count": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
            }
        
        success_count = sum(1 for m in recent if m.success)
        latencies = [m.latency_ms for m in recent]
        
        return {
            "request_count": len(recent),
            "success_rate": success_count / len(recent),
            "avg_latency_ms": sum(latencies) / len(latencies),
            "p50_latency_ms": sorted(latencies)[len(latencies) // 2],
            "p99_latency_ms": sorted(latencies)[int(len(latencies) * 0.99)],
        }


class TraceCollector:
    """
    Distributed tracing collector.
    """
    
    def __init__(self):
        self._traces: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
    
    def generate_trace_id(self) -> str:
        """Generate a trace ID."""
        return uuid.uuid4().hex[:32]
    
    def generate_span_id(self) -> str:
        """Generate a span ID."""
        return uuid.uuid4().hex[:16]
    
    async def record_span(
        self,
        trace_id: str,
        span_id: str,
        parent_span_id: Optional[str],
        service: str,
        operation: str,
        start_time: datetime,
        end_time: datetime,
        status: str = "OK",
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a span."""
        async with self._lock:
            if trace_id not in self._traces:
                self._traces[trace_id] = []
            
            self._traces[trace_id].append({
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "service": service,
                "operation": operation,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_ms": (end_time - start_time).total_seconds() * 1000,
                "status": status,
                "tags": tags or {},
            })
    
    async def get_trace(
        self,
        trace_id: str,
    ) -> List[Dict[str, Any]]:
        """Get spans for a trace."""
        return self._traces.get(trace_id, [])


class ServiceMesh:
    """
    Service mesh coordinator.
    """
    
    def __init__(self):
        self._services: Dict[str, ServiceConfig] = {}
        self._sidecars: Dict[str, Sidecar] = {}
        self._traffic_rules: Dict[str, TrafficRule] = {}
        self._metrics = MetricsCollector()
        self._traces = TraceCollector()
        self._lock = asyncio.Lock()
    
    async def register(
        self,
        name: str,
        address: str,
        port: int = 80,
        weight: int = 100,
        config: Optional[ServiceConfig] = None,
    ) -> str:
        """Register a service."""
        async with self._lock:
            service_id = f"svc-{name}-{uuid.uuid4().hex[:8]}"
            
            endpoint = ServiceEndpoint(
                endpoint_id=f"ep-{uuid.uuid4().hex[:8]}",
                address=address,
                port=port,
                weight=weight,
            )
            
            if config:
                config.service_id = service_id
                config.name = name
                config.endpoints.append(endpoint)
            else:
                config = ServiceConfig(
                    service_id=service_id,
                    name=name,
                    endpoints=[endpoint],
                )
            
            self._services[service_id] = config
            self._sidecars[service_id] = Sidecar(service_id, config)
            
            logger.info(f"Registered service: {name} ({service_id})")
            
            return service_id
    
    async def unregister(self, service_id: str) -> None:
        """Unregister a service."""
        async with self._lock:
            self._services.pop(service_id, None)
            self._sidecars.pop(service_id, None)
    
    def get_service(self, name: str) -> Optional[ServiceConfig]:
        """Get service by name."""
        for config in self._services.values():
            if config.name == name:
                return config
        return None
    
    async def add_endpoint(
        self,
        service_id: str,
        address: str,
        port: int = 80,
        weight: int = 100,
    ) -> None:
        """Add endpoint to service."""
        async with self._lock:
            config = self._services.get(service_id)
            if config:
                endpoint = ServiceEndpoint(
                    endpoint_id=f"ep-{uuid.uuid4().hex[:8]}",
                    address=address,
                    port=port,
                    weight=weight,
                )
                config.endpoints.append(endpoint)
    
    async def add_traffic_rule(
        self,
        source: Optional[str],
        destination: str,
        weight: int = 100,
        policy: TrafficPolicy = TrafficPolicy.ALLOW,
        rate_limit_rps: Optional[int] = None,
    ) -> str:
        """Add a traffic routing rule."""
        rule_id = f"rule-{uuid.uuid4().hex[:8]}"
        
        rule = TrafficRule(
            rule_id=rule_id,
            source_service=source,
            destination_service=destination,
            weight=weight,
            policy=policy,
            rate_limit_rps=rate_limit_rps,
        )
        
        async with self._lock:
            self._traffic_rules[rule_id] = rule
        
        return rule_id
    
    async def remove_traffic_rule(self, rule_id: str) -> None:
        """Remove a traffic rule."""
        async with self._lock:
            self._traffic_rules.pop(rule_id, None)
    
    async def route(
        self,
        context: RequestContext,
        handler: Callable[[ServiceEndpoint], Awaitable[Any]],
    ) -> Any:
        """Route a request through the mesh."""
        # Find destination service
        dest_config = self.get_service(context.destination_service)
        
        if not dest_config:
            raise ServiceNotFoundError(
                f"Service not found: {context.destination_service}"
            )
        
        # Check traffic rules
        applicable_rules = [
            r for r in self._traffic_rules.values()
            if r.destination_service == context.destination_service
            and (r.source_service is None or r.source_service == context.source_service)
        ]
        
        for rule in applicable_rules:
            if rule.policy == TrafficPolicy.DENY:
                raise MeshError(
                    f"Traffic denied by rule: {rule.rule_id}"
                )
        
        # Get sidecar
        sidecar = self._sidecars.get(dest_config.service_id)
        
        if not sidecar:
            raise MeshError(
                f"No sidecar for service: {dest_config.service_id}"
            )
        
        # Start tracing
        trace_id = context.trace_id or self._traces.generate_trace_id()
        span_id = self._traces.generate_span_id()
        start_time = datetime.now()
        
        try:
            result = await sidecar.handle_request(context, handler)
            
            end_time = datetime.now()
            
            # Record metrics
            await self._metrics.record(RequestMetrics(
                request_id=context.request_id,
                service=context.destination_service,
                endpoint=sidecar.service_id,
                method=context.method,
                status_code=200,
                latency_ms=(end_time - start_time).total_seconds() * 1000,
                success=True,
            ))
            
            # Record trace
            await self._traces.record_span(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=context.parent_span_id,
                service=context.destination_service,
                operation=f"{context.method} {context.path}",
                start_time=start_time,
                end_time=end_time,
                status="OK",
            )
            
            return result
        
        except Exception as e:
            end_time = datetime.now()
            
            # Record metrics
            await self._metrics.record(RequestMetrics(
                request_id=context.request_id,
                service=context.destination_service,
                endpoint=sidecar.service_id,
                method=context.method,
                status_code=500,
                latency_ms=(end_time - start_time).total_seconds() * 1000,
                success=False,
            ))
            
            # Record trace
            await self._traces.record_span(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=context.parent_span_id,
                service=context.destination_service,
                operation=f"{context.method} {context.path}",
                start_time=start_time,
                end_time=end_time,
                status="ERROR",
                tags={"error": str(e)},
            )
            
            raise
    
    async def get_metrics(
        self,
        service: str,
    ) -> Dict[str, Any]:
        """Get service metrics."""
        return await self._metrics.get_service_metrics(service)
    
    async def get_trace(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get trace spans."""
        return await self._traces.get_trace(trace_id)


# Global mesh instance
_global_mesh = ServiceMesh()


# Decorators
def mesh_sidecar(
    service_name: str,
) -> Callable:
    """
    Decorator to wrap function with mesh sidecar.
    
    Example:
        @mesh_sidecar("payment-service")
        async def payment_handler(request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            context = RequestContext(
                request_id=str(uuid.uuid4()),
                source_service=None,
                destination_service=service_name,
            )
            
            async def handler(endpoint: ServiceEndpoint) -> Any:
                return await func(*args, **kwargs)
            
            return await _global_mesh.route(context, handler)
        
        return wrapper
    
    return decorator


def with_tracing(
    service_name: str,
) -> Callable:
    """
    Decorator to add tracing to function.
    
    Example:
        @with_tracing("order-service")
        async def process_order(order):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            trace_id = _global_mesh._traces.generate_trace_id()
            span_id = _global_mesh._traces.generate_span_id()
            start_time = datetime.now()
            
            try:
                result = await func(*args, **kwargs)
                
                await _global_mesh._traces.record_span(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=None,
                    service=service_name,
                    operation=func.__name__,
                    start_time=start_time,
                    end_time=datetime.now(),
                    status="OK",
                )
                
                return result
            
            except Exception as e:
                await _global_mesh._traces.record_span(
                    trace_id=trace_id,
                    span_id=span_id,
                    parent_span_id=None,
                    service=service_name,
                    operation=func.__name__,
                    start_time=start_time,
                    end_time=datetime.now(),
                    status="ERROR",
                    tags={"error": str(e)},
                )
                raise
        
        return wrapper
    
    return decorator


def mesh_service(
    name: str,
    port: int = 80,
) -> Callable:
    """
    Class decorator to register service with mesh.
    
    Example:
        @mesh_service("user-service", port=8080)
        class UserService:
            ...
    """
    def decorator(cls: type) -> type:
        original_init = cls.__init__
        
        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            asyncio.create_task(
                _global_mesh.register(name, "localhost", port)
            )
        
        cls.__init__ = new_init
        return cls
    
    return decorator


# Factory functions
def create_service_mesh() -> ServiceMesh:
    """Create a service mesh."""
    return ServiceMesh()


def create_sidecar(
    service_id: str,
    endpoints: Optional[List[Tuple[str, int]]] = None,
    load_balance: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
) -> Sidecar:
    """Create a sidecar proxy."""
    eps = [
        ServiceEndpoint(
            endpoint_id=f"ep-{i}",
            address=addr,
            port=port,
        )
        for i, (addr, port) in enumerate(endpoints or [("localhost", 80)])
    ]
    
    config = ServiceConfig(
        service_id=service_id,
        name=service_id,
        endpoints=eps,
        load_balance=load_balance,
    )
    
    return Sidecar(service_id, config)


def create_circuit_breaker(
    service_id: str,
    threshold: int = 5,
    timeout_seconds: int = 30,
) -> CircuitBreaker:
    """Create a circuit breaker."""
    return CircuitBreaker(service_id, threshold, timeout_seconds)


def create_load_balancer(
    strategy: LoadBalanceStrategy = LoadBalanceStrategy.ROUND_ROBIN,
) -> LoadBalancer:
    """Create a load balancer."""
    return LoadBalancer(strategy)


def get_global_mesh() -> ServiceMesh:
    """Get global mesh instance."""
    return _global_mesh


__all__ = [
    # Exceptions
    "MeshError",
    "ServiceNotFoundError",
    "CircuitOpenError",
    # Enums
    "LoadBalanceStrategy",
    "RetryPolicy",
    "CircuitState",
    "TrafficPolicy",
    # Data classes
    "ServiceEndpoint",
    "ServiceConfig",
    "TrafficRule",
    "RequestContext",
    "RequestMetrics",
    # Core classes
    "CircuitBreaker",
    "LoadBalancer",
    "Sidecar",
    "MetricsCollector",
    "TraceCollector",
    "ServiceMesh",
    # Decorators
    "mesh_sidecar",
    "with_tracing",
    "mesh_service",
    # Factory functions
    "create_service_mesh",
    "create_sidecar",
    "create_circuit_breaker",
    "create_load_balancer",
    "get_global_mesh",
]
