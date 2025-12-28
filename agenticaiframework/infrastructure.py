"""
Infrastructure Module for AgenticAI Framework.

Features:
- Multi-Region Support
- Tenant Isolation
- Serverless Execution
- Distributed coordination
"""

import uuid
import time
import logging
import threading
import json
import hashlib
from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import random

logger = logging.getLogger(__name__)


class Region(Enum):
    """Supported regions."""
    US_EAST = "us-east"
    US_WEST = "us-west"
    EU_WEST = "eu-west"
    EU_CENTRAL = "eu-central"
    ASIA_PACIFIC = "asia-pacific"
    ASIA_SOUTH = "asia-south"
    AUSTRALIA = "australia"


@dataclass
class RegionConfig:
    """Configuration for a region."""
    region: Region
    endpoint: str
    is_primary: bool = False
    weight: float = 1.0
    latency_ms: float = 0
    health_status: str = "healthy"
    metadata: Dict[str, Any] = field(default_factory=dict)


class MultiRegionManager:
    """
    Manages multi-region deployment and routing.
    
    Features:
    - Geographic load balancing
    - Failover handling
    - Latency-based routing
    - Region health monitoring
    """
    
    def __init__(self):
        self.regions: Dict[Region, RegionConfig] = {}
        self.primary_region: Optional[Region] = None
        self.routing_mode: str = "latency"  # latency, round-robin, weighted
        self._health_check_interval: int = 30
        self._lock = threading.Lock()
        self._request_counts: Dict[Region, int] = defaultdict(int)
    
    def register_region(self, config: RegionConfig):
        """Register a region."""
        with self._lock:
            self.regions[config.region] = config
            
            if config.is_primary:
                self.primary_region = config.region
        
        logger.info("Registered region: %s (primary: %s)", 
                   config.region.value, config.is_primary)
    
    def set_routing_mode(self, mode: str):
        """Set routing mode."""
        if mode not in ["latency", "round-robin", "weighted", "primary-only"]:
            raise ValueError(f"Invalid routing mode: {mode}")
        self.routing_mode = mode
        logger.info("Set routing mode to: %s", mode)
    
    def get_region(self, user_region: Region = None) -> Region:
        """
        Get the best region for a request.
        
        Args:
            user_region: User's geographic region (for latency routing)
        """
        healthy_regions = [
            r for r, c in self.regions.items() 
            if c.health_status == "healthy"
        ]
        
        if not healthy_regions:
            raise RuntimeError("No healthy regions available")
        
        if self.routing_mode == "primary-only":
            if self.primary_region and self.primary_region in healthy_regions:
                return self.primary_region
            return healthy_regions[0]
        
        if self.routing_mode == "round-robin":
            region = min(healthy_regions, key=lambda r: self._request_counts[r])
            self._request_counts[region] += 1
            return region
        
        if self.routing_mode == "weighted":
            weights = [self.regions[r].weight for r in healthy_regions]
            return random.choices(healthy_regions, weights=weights)[0]
        
        # Latency-based (default)
        if user_region and user_region in healthy_regions:
            return user_region
        
        # Return region with lowest latency
        return min(healthy_regions, key=lambda r: self.regions[r].latency_ms)
    
    def update_health(self, region: Region, status: str, latency_ms: float = None):
        """Update region health status."""
        if region not in self.regions:
            return
        
        with self._lock:
            self.regions[region].health_status = status
            if latency_ms is not None:
                self.regions[region].latency_ms = latency_ms
        
        logger.info("Updated region %s health: %s (latency: %s ms)",
                   region.value, status, latency_ms)
    
    def failover(self, failed_region: Region) -> Region:
        """Handle region failover."""
        self.update_health(failed_region, "unhealthy")
        
        # Get next best region
        new_region = self.get_region()
        
        logger.warning("Failover from %s to %s", 
                      failed_region.value, new_region.value)
        
        return new_region
    
    def get_status(self) -> Dict[str, Any]:
        """Get multi-region status."""
        return {
            'routing_mode': self.routing_mode,
            'primary_region': self.primary_region.value if self.primary_region else None,
            'regions': {
                r.value: {
                    'endpoint': c.endpoint,
                    'is_primary': c.is_primary,
                    'health_status': c.health_status,
                    'latency_ms': c.latency_ms,
                    'weight': c.weight,
                    'request_count': self._request_counts[r]
                }
                for r, c in self.regions.items()
            }
        }


@dataclass
class Tenant:
    """Represents a tenant in multi-tenant system."""
    tenant_id: str
    name: str
    tier: str  # free, standard, premium, enterprise
    quota: Dict[str, int]
    metadata: Dict[str, Any]
    created_at: float
    status: str = "active"
    region: Optional[Region] = None
    isolation_level: str = "shared"  # shared, dedicated, isolated


class TenantManager:
    """
    Manages tenant isolation and multi-tenancy.
    
    Features:
    - Tenant provisioning
    - Resource isolation
    - Quota management
    - Usage tracking
    """
    
    def __init__(self):
        self.tenants: Dict[str, Tenant] = {}
        self.usage: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._context = threading.local()
        self._lock = threading.Lock()
        
        # Default quotas by tier
        self.tier_quotas = {
            'free': {'requests_per_day': 100, 'agents': 1, 'storage_mb': 100},
            'standard': {'requests_per_day': 10000, 'agents': 10, 'storage_mb': 1000},
            'premium': {'requests_per_day': 100000, 'agents': 100, 'storage_mb': 10000},
            'enterprise': {'requests_per_day': -1, 'agents': -1, 'storage_mb': -1}  # unlimited
        }
    
    def create_tenant(self,
                     name: str,
                     tier: str = "free",
                     custom_quota: Dict[str, int] = None,
                     metadata: Dict[str, Any] = None,
                     region: Region = None,
                     isolation_level: str = "shared") -> Tenant:
        """
        Create a new tenant.
        
        Args:
            name: Tenant name
            tier: Pricing tier
            custom_quota: Override default quotas
            metadata: Additional metadata
            region: Preferred region
            isolation_level: Isolation type
        """
        tenant_id = str(uuid.uuid4())
        
        # Get quota based on tier
        quota = self.tier_quotas.get(tier, self.tier_quotas['free']).copy()
        if custom_quota:
            quota.update(custom_quota)
        
        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            tier=tier,
            quota=quota,
            metadata=metadata or {},
            created_at=time.time(),
            region=region,
            isolation_level=isolation_level
        )
        
        with self._lock:
            self.tenants[tenant_id] = tenant
        
        logger.info("Created tenant '%s' (id=%s, tier=%s)", name, tenant_id, tier)
        
        return tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return self.tenants.get(tenant_id)
    
    def set_current_tenant(self, tenant_id: str):
        """Set current tenant context."""
        if tenant_id not in self.tenants:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        self._context.tenant_id = tenant_id
    
    def get_current_tenant(self) -> Optional[str]:
        """Get current tenant context."""
        return getattr(self._context, 'tenant_id', None)
    
    def clear_tenant_context(self):
        """Clear tenant context."""
        if hasattr(self._context, 'tenant_id'):
            del self._context.tenant_id
    
    def check_quota(self, tenant_id: str, resource: str, amount: int = 1) -> bool:
        """Check if tenant has quota for resource."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False
        
        quota_limit = tenant.quota.get(resource, 0)
        if quota_limit == -1:  # Unlimited
            return True
        
        current_usage = self.usage[tenant_id][resource]
        return (current_usage + amount) <= quota_limit
    
    def consume_quota(self, tenant_id: str, resource: str, amount: int = 1) -> bool:
        """Consume tenant quota."""
        if not self.check_quota(tenant_id, resource, amount):
            return False
        
        with self._lock:
            self.usage[tenant_id][resource] += amount
        
        return True
    
    def get_usage(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant usage."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return {}
        
        return {
            'tenant_id': tenant_id,
            'tier': tenant.tier,
            'quota': tenant.quota,
            'usage': dict(self.usage[tenant_id]),
            'utilization': {
                resource: (self.usage[tenant_id][resource] / limit * 100) 
                if limit > 0 else 0
                for resource, limit in tenant.quota.items()
            }
        }
    
    def update_tier(self, tenant_id: str, new_tier: str):
        """Update tenant tier."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        
        tenant.tier = new_tier
        tenant.quota = self.tier_quotas.get(new_tier, self.tier_quotas['free']).copy()
        
        logger.info("Updated tenant %s to tier %s", tenant_id, new_tier)
    
    def suspend_tenant(self, tenant_id: str, reason: str = None):
        """Suspend a tenant."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant '{tenant_id}' not found")
        
        tenant.status = "suspended"
        tenant.metadata['suspension_reason'] = reason
        tenant.metadata['suspended_at'] = time.time()
        
        logger.warning("Suspended tenant %s: %s", tenant_id, reason)
    
    def list_tenants(self, 
                    status: str = None,
                    tier: str = None) -> List[Dict[str, Any]]:
        """List tenants with optional filtering."""
        results = []
        
        for tenant in self.tenants.values():
            if status and tenant.status != status:
                continue
            if tier and tenant.tier != tier:
                continue
            
            results.append({
                'tenant_id': tenant.tenant_id,
                'name': tenant.name,
                'tier': tenant.tier,
                'status': tenant.status,
                'isolation_level': tenant.isolation_level,
                'region': tenant.region.value if tenant.region else None,
                'created_at': tenant.created_at
            })
        
        return results


@dataclass
class ServerlessFunction:
    """Represents a serverless function."""
    function_id: str
    name: str
    handler: Callable
    runtime: str
    memory_mb: int
    timeout_seconds: int
    environment: Dict[str, str]
    metadata: Dict[str, Any]
    created_at: float


@dataclass
class FunctionInvocation:
    """Records a function invocation."""
    invocation_id: str
    function_id: str
    input_data: Any
    output_data: Any
    status: str
    start_time: float
    end_time: float
    memory_used_mb: float
    billed_duration_ms: float


class ServerlessExecutor:
    """
    Serverless execution environment for agents.
    
    Features:
    - Function deployment
    - Auto-scaling
    - Cold start optimization
    - Invocation tracking
    """
    
    def __init__(self):
        self.functions: Dict[str, ServerlessFunction] = {}
        self.invocations: List[FunctionInvocation] = []
        self.warm_pool: Dict[str, List[Any]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # Default configuration
        self.default_memory_mb = 256
        self.default_timeout_seconds = 30
        self.max_concurrent = 100
        self._current_concurrent = 0
    
    def deploy_function(self,
                       name: str,
                       handler: Callable,
                       memory_mb: int = None,
                       timeout_seconds: int = None,
                       environment: Dict[str, str] = None,
                       runtime: str = "python3.9") -> ServerlessFunction:
        """
        Deploy a serverless function.
        
        Args:
            name: Function name
            handler: Function handler (callable)
            memory_mb: Memory allocation
            timeout_seconds: Execution timeout
            environment: Environment variables
            runtime: Runtime environment
        """
        function_id = str(uuid.uuid4())
        
        function = ServerlessFunction(
            function_id=function_id,
            name=name,
            handler=handler,
            runtime=runtime,
            memory_mb=memory_mb or self.default_memory_mb,
            timeout_seconds=timeout_seconds or self.default_timeout_seconds,
            environment=environment or {},
            metadata={},
            created_at=time.time()
        )
        
        self.functions[function_id] = function
        logger.info("Deployed function '%s' (id=%s)", name, function_id)
        
        return function
    
    def invoke(self,
              function_id: str,
              input_data: Any,
              async_invoke: bool = False) -> FunctionInvocation:
        """
        Invoke a serverless function.
        
        Args:
            function_id: Function to invoke
            input_data: Input data
            async_invoke: Whether to invoke asynchronously
        """
        function = self.functions.get(function_id)
        if not function:
            raise ValueError(f"Function '{function_id}' not found")
        
        # Check concurrency
        if self._current_concurrent >= self.max_concurrent:
            raise RuntimeError("Max concurrent invocations reached")
        
        invocation_id = str(uuid.uuid4())
        start_time = time.time()
        
        with self._lock:
            self._current_concurrent += 1
        
        try:
            # Execute function
            output_data = function.handler(input_data)
            status = "success"
        except Exception as e:
            output_data = str(e)
            status = "error"
            logger.error("Function %s invocation failed: %s", function_id, e)
        finally:
            with self._lock:
                self._current_concurrent -= 1
        
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        # Calculate billing (rounded up to nearest 100ms)
        billed_duration = ((duration_ms // 100) + 1) * 100
        
        invocation = FunctionInvocation(
            invocation_id=invocation_id,
            function_id=function_id,
            input_data=input_data,
            output_data=output_data,
            status=status,
            start_time=start_time,
            end_time=end_time,
            memory_used_mb=function.memory_mb,  # Simplified
            billed_duration_ms=billed_duration
        )
        
        self.invocations.append(invocation)
        
        return invocation
    
    def get_function(self, function_id: str) -> Optional[ServerlessFunction]:
        """Get function by ID."""
        return self.functions.get(function_id)
    
    def get_function_by_name(self, name: str) -> Optional[ServerlessFunction]:
        """Get function by name."""
        for func in self.functions.values():
            if func.name == name:
                return func
        return None
    
    def delete_function(self, function_id: str):
        """Delete a function."""
        if function_id in self.functions:
            del self.functions[function_id]
            logger.info("Deleted function %s", function_id)
    
    def get_metrics(self, function_id: str = None) -> Dict[str, Any]:
        """Get execution metrics."""
        invocations = self.invocations
        
        if function_id:
            invocations = [i for i in invocations if i.function_id == function_id]
        
        if not invocations:
            return {'error': 'No data'}
        
        durations = [(i.end_time - i.start_time) * 1000 for i in invocations]
        success_count = sum(1 for i in invocations if i.status == 'success')
        
        return {
            'total_invocations': len(invocations),
            'success_count': success_count,
            'error_count': len(invocations) - success_count,
            'success_rate': success_count / len(invocations),
            'avg_duration_ms': sum(durations) / len(durations),
            'min_duration_ms': min(durations),
            'max_duration_ms': max(durations),
            'total_billed_ms': sum(i.billed_duration_ms for i in invocations),
            'current_concurrent': self._current_concurrent
        }
    
    def list_functions(self) -> List[Dict[str, Any]]:
        """List all functions."""
        return [
            {
                'function_id': f.function_id,
                'name': f.name,
                'runtime': f.runtime,
                'memory_mb': f.memory_mb,
                'timeout_seconds': f.timeout_seconds,
                'created_at': f.created_at
            }
            for f in self.functions.values()
        ]


class DistributedCoordinator:
    """
    Coordinates distributed agent execution.
    
    Features:
    - Distributed locking
    - Leader election
    - Task distribution
    - Consensus
    """
    
    def __init__(self, node_id: str = None):
        self.node_id = node_id or str(uuid.uuid4())
        self.locks: Dict[str, Dict[str, Any]] = {}
        self.leader: Optional[str] = None
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        
        # Register self
        self._register_node()
    
    def _register_node(self):
        """Register this node."""
        self.nodes[self.node_id] = {
            'node_id': self.node_id,
            'registered_at': time.time(),
            'last_heartbeat': time.time(),
            'status': 'active'
        }
    
    def acquire_lock(self, 
                    lock_name: str,
                    timeout_seconds: float = 30) -> bool:
        """
        Acquire a distributed lock.
        
        Args:
            lock_name: Name of lock
            timeout_seconds: Lock timeout
        """
        with self._lock:
            if lock_name in self.locks:
                existing = self.locks[lock_name]
                
                # Check if lock expired
                if time.time() - existing['acquired_at'] > existing['timeout']:
                    pass  # Lock expired, can acquire
                elif existing['owner'] == self.node_id:
                    # Reentrant
                    existing['count'] += 1
                    return True
                else:
                    return False
            
            self.locks[lock_name] = {
                'owner': self.node_id,
                'acquired_at': time.time(),
                'timeout': timeout_seconds,
                'count': 1
            }
        
        logger.debug("Node %s acquired lock '%s'", self.node_id, lock_name)
        return True
    
    def release_lock(self, lock_name: str) -> bool:
        """Release a distributed lock."""
        with self._lock:
            if lock_name not in self.locks:
                return False
            
            lock = self.locks[lock_name]
            if lock['owner'] != self.node_id:
                return False
            
            lock['count'] -= 1
            if lock['count'] <= 0:
                del self.locks[lock_name]
        
        logger.debug("Node %s released lock '%s'", self.node_id, lock_name)
        return True
    
    def elect_leader(self) -> str:
        """Perform leader election."""
        active_nodes = [
            nid for nid, info in self.nodes.items()
            if info['status'] == 'active' and 
            time.time() - info['last_heartbeat'] < 60
        ]
        
        if not active_nodes:
            self.leader = self.node_id
        else:
            # Simple: lowest node ID wins
            self.leader = min(active_nodes)
        
        logger.info("Leader elected: %s", self.leader)
        return self.leader
    
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self.leader == self.node_id
    
    def submit_task(self, 
                   task_id: str,
                   task_data: Any,
                   target_node: str = None) -> Dict[str, Any]:
        """Submit a task for distributed execution."""
        if target_node is None:
            # Round-robin distribution
            active_nodes = [
                nid for nid, info in self.nodes.items()
                if info['status'] == 'active'
            ]
            if not active_nodes:
                target_node = self.node_id
            else:
                target_node = active_nodes[len(self.tasks) % len(active_nodes)]
        
        task = {
            'task_id': task_id,
            'data': task_data,
            'target_node': target_node,
            'submitted_by': self.node_id,
            'submitted_at': time.time(),
            'status': 'pending'
        }
        
        self.tasks[task_id] = task
        logger.info("Submitted task %s to node %s", task_id, target_node)
        
        return task
    
    def heartbeat(self):
        """Send heartbeat."""
        if self.node_id in self.nodes:
            self.nodes[self.node_id]['last_heartbeat'] = time.time()
    
    def get_cluster_status(self) -> Dict[str, Any]:
        """Get cluster status."""
        active_count = sum(
            1 for info in self.nodes.values()
            if info['status'] == 'active' and 
            time.time() - info['last_heartbeat'] < 60
        )
        
        return {
            'node_id': self.node_id,
            'is_leader': self.is_leader(),
            'leader': self.leader,
            'total_nodes': len(self.nodes),
            'active_nodes': active_count,
            'active_locks': len(self.locks),
            'pending_tasks': sum(
                1 for t in self.tasks.values() if t['status'] == 'pending'
            )
        }


# Global instances
multi_region_manager = MultiRegionManager()
tenant_manager = TenantManager()
serverless_executor = ServerlessExecutor()
distributed_coordinator = DistributedCoordinator()
