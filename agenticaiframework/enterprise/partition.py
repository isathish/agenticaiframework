"""
Enterprise Partition Module.

Provides data partitioning, sharding, and consistent hashing
for distributed data management.

Example:
    # Create partitioner
    partitioner = create_partitioner(
        strategy="consistent_hash",
        partitions=["p1", "p2", "p3"]
    )
    
    # Get partition for key
    partition = partitioner.get_partition("user_12345")
    
    # Shard registry
    registry = create_shard_registry()
    registry.register_shard("shard_1", "host1:5432")
    
    shard = registry.get_shard_for_key("order_789")
"""

from __future__ import annotations

import asyncio
import bisect
import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')
K = TypeVar('K')


class PartitionError(Exception):
    """Partition error."""
    pass


class ShardNotFoundError(PartitionError):
    """Shard not found."""
    pass


class PartitionStrategy(str, Enum):
    """Partition strategy."""
    HASH = "hash"
    RANGE = "range"
    LIST = "list"
    CONSISTENT_HASH = "consistent_hash"
    ROUND_ROBIN = "round_robin"


class ShardState(str, Enum):
    """Shard state."""
    ACTIVE = "active"
    DRAINING = "draining"
    READONLY = "readonly"
    OFFLINE = "offline"


class RebalanceState(str, Enum):
    """Rebalance state."""
    IDLE = "idle"
    PLANNING = "planning"
    MIGRATING = "migrating"
    COMPLETING = "completing"


@dataclass
class Partition:
    """A data partition."""
    partition_id: str
    shard_id: str
    start_key: Optional[str] = None
    end_key: Optional[str] = None
    key_count: int = 0
    size_bytes: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Shard:
    """A data shard."""
    shard_id: str
    address: str
    state: ShardState = ShardState.ACTIVE
    weight: int = 100
    partitions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PartitionConfig:
    """Partition configuration."""
    strategy: PartitionStrategy = PartitionStrategy.CONSISTENT_HASH
    num_partitions: int = 256
    replication_factor: int = 1
    virtual_nodes: int = 150


@dataclass
class MigrationPlan:
    """Data migration plan."""
    migration_id: str
    source_shard: str
    target_shard: str
    partitions: List[str]
    status: str = "pending"
    progress: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


class HashFunction(ABC):
    """Abstract hash function."""
    
    @abstractmethod
    def hash(self, key: str) -> int:
        """Hash a key to an integer."""
        pass


class MD5Hash(HashFunction):
    """MD5 hash function."""
    
    def hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)


class SHA256Hash(HashFunction):
    """SHA256 hash function."""
    
    def hash(self, key: str) -> int:
        return int(hashlib.sha256(key.encode()).hexdigest(), 16)


class MurmurHash(HashFunction):
    """Murmur-like hash function."""
    
    def hash(self, key: str) -> int:
        h = 0
        for c in key:
            h = (h * 31 + ord(c)) & 0xFFFFFFFF
        return h


class Partitioner(ABC):
    """Abstract partitioner."""
    
    @abstractmethod
    def get_partition(self, key: str) -> str:
        """Get partition ID for a key."""
        pass
    
    @abstractmethod
    def get_all_partitions(self) -> List[str]:
        """Get all partition IDs."""
        pass


class HashPartitioner(Partitioner):
    """Simple hash-based partitioner."""
    
    def __init__(
        self,
        partitions: List[str],
        hash_fn: Optional[HashFunction] = None,
    ):
        self._partitions = partitions
        self._hash_fn = hash_fn or MD5Hash()
    
    def get_partition(self, key: str) -> str:
        idx = self._hash_fn.hash(key) % len(self._partitions)
        return self._partitions[idx]
    
    def get_all_partitions(self) -> List[str]:
        return self._partitions.copy()


class RangePartitioner(Partitioner):
    """Range-based partitioner."""
    
    def __init__(
        self,
        ranges: List[Tuple[str, str, str]],  # (start, end, partition_id)
    ):
        self._ranges = sorted(ranges, key=lambda x: x[0])
    
    def get_partition(self, key: str) -> str:
        for start, end, partition_id in self._ranges:
            if start <= key <= end:
                return partition_id
        
        # Default to last partition
        return self._ranges[-1][2] if self._ranges else ""
    
    def get_all_partitions(self) -> List[str]:
        return [r[2] for r in self._ranges]


class ListPartitioner(Partitioner):
    """List-based partitioner."""
    
    def __init__(
        self,
        mapping: Dict[str, List[str]],  # partition_id -> list of keys
    ):
        self._mapping = mapping
        self._reverse: Dict[str, str] = {}
        
        for partition_id, keys in mapping.items():
            for key in keys:
                self._reverse[key] = partition_id
    
    def get_partition(self, key: str) -> str:
        return self._reverse.get(key, "")
    
    def get_all_partitions(self) -> List[str]:
        return list(self._mapping.keys())


class ConsistentHashRing:
    """
    Consistent hash ring for data distribution.
    """
    
    def __init__(
        self,
        virtual_nodes: int = 150,
        hash_fn: Optional[HashFunction] = None,
    ):
        self._virtual_nodes = virtual_nodes
        self._hash_fn = hash_fn or MD5Hash()
        self._ring: Dict[int, str] = {}
        self._sorted_keys: List[int] = []
        self._nodes: Set[str] = set()
    
    def add_node(self, node: str, weight: int = 1) -> None:
        """Add a node to the ring."""
        self._nodes.add(node)
        
        for i in range(self._virtual_nodes * weight):
            key = self._hash_fn.hash(f"{node}:{i}")
            self._ring[key] = node
        
        self._sorted_keys = sorted(self._ring.keys())
    
    def remove_node(self, node: str) -> None:
        """Remove a node from the ring."""
        self._nodes.discard(node)
        
        self._ring = {k: v for k, v in self._ring.items() if v != node}
        self._sorted_keys = sorted(self._ring.keys())
    
    def get_node(self, key: str) -> Optional[str]:
        """Get node for a key."""
        if not self._ring:
            return None
        
        h = self._hash_fn.hash(key)
        idx = bisect.bisect_right(self._sorted_keys, h) % len(self._sorted_keys)
        
        return self._ring[self._sorted_keys[idx]]
    
    def get_nodes(self, key: str, count: int = 1) -> List[str]:
        """Get multiple nodes for a key (for replication)."""
        if not self._ring:
            return []
        
        h = self._hash_fn.hash(key)
        idx = bisect.bisect_right(self._sorted_keys, h)
        
        nodes = []
        seen = set()
        
        for i in range(len(self._sorted_keys)):
            node = self._ring[self._sorted_keys[(idx + i) % len(self._sorted_keys)]]
            
            if node not in seen:
                nodes.append(node)
                seen.add(node)
            
            if len(nodes) >= count:
                break
        
        return nodes
    
    @property
    def nodes(self) -> Set[str]:
        return self._nodes.copy()
    
    def get_partition_map(self) -> Dict[str, List[int]]:
        """Get mapping of nodes to their virtual positions."""
        result: Dict[str, List[int]] = {}
        
        for pos, node in self._ring.items():
            if node not in result:
                result[node] = []
            result[node].append(pos)
        
        return result


class ConsistentHashPartitioner(Partitioner):
    """Consistent hash ring partitioner."""
    
    def __init__(
        self,
        partitions: List[str],
        virtual_nodes: int = 150,
    ):
        self._ring = ConsistentHashRing(virtual_nodes)
        self._partitions = partitions
        
        for partition in partitions:
            self._ring.add_node(partition)
    
    def get_partition(self, key: str) -> str:
        return self._ring.get_node(key) or self._partitions[0]
    
    def get_all_partitions(self) -> List[str]:
        return self._partitions.copy()
    
    def add_partition(self, partition_id: str, weight: int = 1) -> None:
        """Add a partition to the ring."""
        self._partitions.append(partition_id)
        self._ring.add_node(partition_id, weight)
    
    def remove_partition(self, partition_id: str) -> None:
        """Remove a partition from the ring."""
        self._partitions.remove(partition_id)
        self._ring.remove_node(partition_id)


class ShardRegistry:
    """
    Registry for data shards.
    """
    
    def __init__(
        self,
        partitioner: Optional[Partitioner] = None,
    ):
        self._shards: Dict[str, Shard] = {}
        self._partitioner = partitioner
        self._partition_to_shard: Dict[str, str] = {}
        self._lock = asyncio.Lock()
    
    async def register_shard(
        self,
        shard_id: str,
        address: str,
        weight: int = 100,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Shard:
        """Register a new shard."""
        async with self._lock:
            shard = Shard(
                shard_id=shard_id,
                address=address,
                weight=weight,
                metadata=metadata or {},
            )
            
            self._shards[shard_id] = shard
            
            # Update partitioner if consistent hash
            if isinstance(self._partitioner, ConsistentHashPartitioner):
                self._partitioner.add_partition(shard_id, weight // 100)
            
            logger.info(f"Registered shard: {shard_id} at {address}")
            
            return shard
    
    async def unregister_shard(self, shard_id: str) -> None:
        """Unregister a shard."""
        async with self._lock:
            if shard_id in self._shards:
                del self._shards[shard_id]
                
                # Update partitioner
                if isinstance(self._partitioner, ConsistentHashPartitioner):
                    self._partitioner.remove_partition(shard_id)
                
                logger.info(f"Unregistered shard: {shard_id}")
    
    def get_shard(self, shard_id: str) -> Optional[Shard]:
        """Get shard by ID."""
        return self._shards.get(shard_id)
    
    def get_shard_for_key(self, key: str) -> Optional[Shard]:
        """Get shard for a key."""
        if not self._partitioner:
            # Return first active shard
            for shard in self._shards.values():
                if shard.state == ShardState.ACTIVE:
                    return shard
            return None
        
        partition = self._partitioner.get_partition(key)
        
        # If partition is a shard ID
        if partition in self._shards:
            return self._shards[partition]
        
        # Look up partition to shard mapping
        shard_id = self._partition_to_shard.get(partition)
        return self._shards.get(shard_id) if shard_id else None
    
    def get_all_shards(
        self,
        state: Optional[ShardState] = None,
    ) -> List[Shard]:
        """Get all shards, optionally filtered by state."""
        shards = list(self._shards.values())
        
        if state:
            shards = [s for s in shards if s.state == state]
        
        return shards
    
    async def set_shard_state(
        self,
        shard_id: str,
        state: ShardState,
    ) -> None:
        """Set shard state."""
        async with self._lock:
            shard = self._shards.get(shard_id)
            if shard:
                shard.state = state
                logger.info(f"Shard {shard_id} state changed to {state}")


class PartitionManager:
    """
    Manager for partition operations.
    """
    
    def __init__(
        self,
        registry: ShardRegistry,
        config: Optional[PartitionConfig] = None,
    ):
        self._registry = registry
        self._config = config or PartitionConfig()
        self._partitions: Dict[str, Partition] = {}
        self._migrations: Dict[str, MigrationPlan] = {}
        self._rebalance_state = RebalanceState.IDLE
    
    def create_partition(
        self,
        partition_id: str,
        shard_id: str,
        start_key: Optional[str] = None,
        end_key: Optional[str] = None,
    ) -> Partition:
        """Create a new partition."""
        partition = Partition(
            partition_id=partition_id,
            shard_id=shard_id,
            start_key=start_key,
            end_key=end_key,
        )
        
        self._partitions[partition_id] = partition
        
        # Update shard
        shard = self._registry.get_shard(shard_id)
        if shard:
            shard.partitions.append(partition_id)
        
        return partition
    
    def get_partition(self, partition_id: str) -> Optional[Partition]:
        """Get partition by ID."""
        return self._partitions.get(partition_id)
    
    def get_partitions_for_shard(self, shard_id: str) -> List[Partition]:
        """Get all partitions for a shard."""
        return [
            p for p in self._partitions.values()
            if p.shard_id == shard_id
        ]
    
    async def plan_rebalance(self) -> List[MigrationPlan]:
        """Plan rebalance of partitions across shards."""
        self._rebalance_state = RebalanceState.PLANNING
        
        shards = self._registry.get_all_shards(ShardState.ACTIVE)
        
        if not shards:
            return []
        
        # Calculate ideal distribution
        total_partitions = len(self._partitions)
        total_weight = sum(s.weight for s in shards)
        
        ideal: Dict[str, int] = {}
        for shard in shards:
            ideal[shard.shard_id] = int(
                total_partitions * shard.weight / total_weight
            )
        
        # Find overloaded and underloaded shards
        current: Dict[str, int] = {}
        for shard in shards:
            current[shard.shard_id] = len(
                self.get_partitions_for_shard(shard.shard_id)
            )
        
        migrations = []
        
        for source_id, count in current.items():
            excess = count - ideal.get(source_id, 0)
            
            if excess > 0:
                # Find target shards that need more partitions
                for target_id, target_ideal in ideal.items():
                    if target_id == source_id:
                        continue
                    
                    deficit = target_ideal - current.get(target_id, 0)
                    
                    if deficit > 0:
                        move = min(excess, deficit)
                        
                        # Get partitions to move
                        source_partitions = self.get_partitions_for_shard(source_id)
                        to_move = [p.partition_id for p in source_partitions[:move]]
                        
                        if to_move:
                            plan = MigrationPlan(
                                migration_id=f"rebal-{source_id}-{target_id}",
                                source_shard=source_id,
                                target_shard=target_id,
                                partitions=to_move,
                            )
                            migrations.append(plan)
                            self._migrations[plan.migration_id] = plan
                        
                        excess -= move
                        current[target_id] = current.get(target_id, 0) + move
                        
                        if excess <= 0:
                            break
        
        self._rebalance_state = RebalanceState.IDLE
        
        return migrations
    
    async def execute_migration(
        self,
        plan: MigrationPlan,
        migrate_fn: Optional[Callable[[str, str, str], bool]] = None,
    ) -> bool:
        """Execute a migration plan."""
        self._rebalance_state = RebalanceState.MIGRATING
        plan.status = "in_progress"
        
        total = len(plan.partitions)
        
        for i, partition_id in enumerate(plan.partitions):
            try:
                # Call migration function if provided
                if migrate_fn:
                    success = await migrate_fn(
                        partition_id,
                        plan.source_shard,
                        plan.target_shard,
                    )
                    
                    if not success:
                        plan.status = "failed"
                        return False
                
                # Update partition
                partition = self._partitions.get(partition_id)
                if partition:
                    partition.shard_id = plan.target_shard
                
                # Update shards
                source = self._registry.get_shard(plan.source_shard)
                target = self._registry.get_shard(plan.target_shard)
                
                if source and partition_id in source.partitions:
                    source.partitions.remove(partition_id)
                
                if target:
                    target.partitions.append(partition_id)
                
                plan.progress = (i + 1) / total
            
            except Exception as e:
                logger.error(f"Migration error: {e}")
                plan.status = "failed"
                return False
        
        plan.status = "completed"
        plan.progress = 1.0
        self._rebalance_state = RebalanceState.IDLE
        
        return True


class ShardRouter:
    """
    Routes operations to appropriate shards.
    """
    
    def __init__(
        self,
        registry: ShardRegistry,
        replication_factor: int = 1,
    ):
        self._registry = registry
        self._replication_factor = replication_factor
    
    def route(self, key: str) -> Optional[Shard]:
        """Route a key to its shard."""
        return self._registry.get_shard_for_key(key)
    
    def route_with_replicas(self, key: str) -> List[Shard]:
        """Route a key to primary and replica shards."""
        primary = self.route(key)
        
        if not primary:
            return []
        
        if self._replication_factor <= 1:
            return [primary]
        
        # Get additional shards for replicas
        all_shards = self._registry.get_all_shards(ShardState.ACTIVE)
        replicas = [primary]
        
        for shard in all_shards:
            if shard.shard_id != primary.shard_id:
                replicas.append(shard)
            
            if len(replicas) >= self._replication_factor:
                break
        
        return replicas
    
    async def execute_on_shard(
        self,
        key: str,
        operation: Callable[[Shard, str], Any],
    ) -> Any:
        """Execute operation on the appropriate shard."""
        shard = self.route(key)
        
        if not shard:
            raise ShardNotFoundError(f"No shard for key: {key}")
        
        return await operation(shard, key)
    
    async def broadcast(
        self,
        operation: Callable[[Shard], Any],
        state: Optional[ShardState] = ShardState.ACTIVE,
    ) -> Dict[str, Any]:
        """Broadcast operation to all shards."""
        shards = self._registry.get_all_shards(state)
        results = {}
        
        for shard in shards:
            try:
                results[shard.shard_id] = await operation(shard)
            except Exception as e:
                results[shard.shard_id] = {"error": str(e)}
        
        return results


# Decorators
def partitioned(
    partitioner: Partitioner,
    key_extractor: Callable[..., str],
) -> Callable:
    """
    Decorator for partitioned operations.
    
    Example:
        @partitioned(partitioner, lambda user_id: user_id)
        async def get_user(user_id: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = key_extractor(*args, **kwargs)
            partition = partitioner.get_partition(key)
            
            # Add partition to kwargs
            kwargs["_partition"] = partition
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


def sharded(
    router: ShardRouter,
    key_extractor: Callable[..., str],
) -> Callable:
    """
    Decorator for sharded operations.
    
    Example:
        @sharded(router, lambda order_id: order_id)
        async def get_order(order_id: str, shard: Shard):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = key_extractor(*args, **kwargs)
            shard = router.route(key)
            
            if not shard:
                raise ShardNotFoundError(f"No shard for key: {key}")
            
            # Add shard to kwargs
            kwargs["shard"] = shard
            
            return await func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Factory functions
def create_partitioner(
    strategy: Union[PartitionStrategy, str] = PartitionStrategy.CONSISTENT_HASH,
    partitions: Optional[List[str]] = None,
    **kwargs: Any,
) -> Partitioner:
    """Create a partitioner."""
    if isinstance(strategy, str):
        strategy = PartitionStrategy(strategy)
    
    parts = partitions or ["p0", "p1", "p2", "p3"]
    
    if strategy == PartitionStrategy.HASH:
        return HashPartitioner(parts)
    
    elif strategy == PartitionStrategy.CONSISTENT_HASH:
        virtual_nodes = kwargs.get("virtual_nodes", 150)
        return ConsistentHashPartitioner(parts, virtual_nodes)
    
    elif strategy == PartitionStrategy.RANGE:
        ranges = kwargs.get("ranges", [])
        return RangePartitioner(ranges)
    
    elif strategy == PartitionStrategy.LIST:
        mapping = kwargs.get("mapping", {})
        return ListPartitioner(mapping)
    
    else:
        return HashPartitioner(parts)


def create_shard_registry(
    partitioner: Optional[Partitioner] = None,
) -> ShardRegistry:
    """Create a shard registry."""
    return ShardRegistry(partitioner)


def create_consistent_hash_ring(
    nodes: Optional[List[str]] = None,
    virtual_nodes: int = 150,
) -> ConsistentHashRing:
    """Create a consistent hash ring."""
    ring = ConsistentHashRing(virtual_nodes)
    
    if nodes:
        for node in nodes:
            ring.add_node(node)
    
    return ring


def create_partition_manager(
    registry: ShardRegistry,
    config: Optional[PartitionConfig] = None,
) -> PartitionManager:
    """Create a partition manager."""
    return PartitionManager(registry, config)


def create_shard_router(
    registry: ShardRegistry,
    replication_factor: int = 1,
) -> ShardRouter:
    """Create a shard router."""
    return ShardRouter(registry, replication_factor)


__all__ = [
    # Exceptions
    "PartitionError",
    "ShardNotFoundError",
    # Enums
    "PartitionStrategy",
    "ShardState",
    "RebalanceState",
    # Data classes
    "Partition",
    "Shard",
    "PartitionConfig",
    "MigrationPlan",
    # Hash functions
    "HashFunction",
    "MD5Hash",
    "SHA256Hash",
    "MurmurHash",
    # Partitioners
    "Partitioner",
    "HashPartitioner",
    "RangePartitioner",
    "ListPartitioner",
    "ConsistentHashPartitioner",
    "ConsistentHashRing",
    # Core classes
    "ShardRegistry",
    "PartitionManager",
    "ShardRouter",
    # Decorators
    "partitioned",
    "sharded",
    # Factory functions
    "create_partitioner",
    "create_shard_registry",
    "create_consistent_hash_ring",
    "create_partition_manager",
    "create_shard_router",
]
