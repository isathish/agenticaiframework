"""
Enterprise Feature Store Module.

ML feature storage, serving, versioning,
and real-time feature computation.

Example:
    # Create feature store
    store = create_feature_store()
    
    # Register feature group
    await store.register_feature_group(
        name="user_features",
        entity="user_id",
        features=["age", "total_purchases", "last_login_days"],
    )
    
    # Ingest features
    await store.ingest("user_features", {"user_id": "123", "age": 25})
    
    # Get features for serving
    features = await store.get_features("user_features", entity_ids=["123"])
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

logger = logging.getLogger(__name__)


class FeatureStoreError(Exception):
    """Feature store error."""
    pass


class FeatureGroupNotFoundError(FeatureStoreError):
    """Feature group not found error."""
    pass


class FeatureNotFoundError(FeatureStoreError):
    """Feature not found error."""
    pass


class EntityNotFoundError(FeatureStoreError):
    """Entity not found error."""
    pass


class FeatureType(str, Enum):
    """Feature types."""
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    ARRAY = "array"
    EMBEDDING = "embedding"


class StorageType(str, Enum):
    """Storage types."""
    ONLINE = "online"
    OFFLINE = "offline"
    BOTH = "both"


class ComputationType(str, Enum):
    """Feature computation types."""
    BATCH = "batch"
    STREAM = "stream"
    ON_DEMAND = "on_demand"


class AggregationType(str, Enum):
    """Aggregation types."""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    LAST = "last"
    FIRST = "first"


@dataclass
class FeatureDefinition:
    """Feature definition."""
    name: str = ""
    feature_type: FeatureType = FeatureType.FLOAT
    
    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Defaults
    default_value: Any = None
    nullable: bool = True
    
    # Transformation
    transformation: Optional[str] = None
    
    # Statistics
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None


@dataclass
class FeatureGroup:
    """Feature group."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    name: str = ""
    description: str = ""
    
    # Entity
    entity: str = ""  # Primary key field name
    entity_type: str = ""
    
    # Features
    features: Dict[str, FeatureDefinition] = field(default_factory=dict)
    
    # Storage
    storage_type: StorageType = StorageType.BOTH
    
    # TTL
    online_ttl_seconds: int = 86400  # 1 day
    offline_retention_days: int = 365
    
    # Versioning
    version: int = 1
    
    # Metadata
    owner: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FeatureValue:
    """Feature value."""
    feature_name: str = ""
    value: Any = None
    
    # Timing
    event_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Version
    version: int = 1


@dataclass
class FeatureVector:
    """Feature vector for an entity."""
    entity_id: str = ""
    feature_group: str = ""
    
    features: Dict[str, FeatureValue] = field(default_factory=dict)
    
    # Timing
    event_time: Optional[datetime] = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MaterializationJob:
    """Feature materialization job."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    feature_group: str = ""
    
    # Status
    status: str = "pending"  # pending, running, completed, failed
    
    # Range
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # Statistics
    rows_processed: int = 0
    rows_written: int = 0
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Error
    error_message: str = ""


@dataclass
class OnDemandFeature:
    """On-demand computed feature."""
    name: str = ""
    
    # Dependencies
    input_features: List[str] = field(default_factory=list)
    
    # Computation
    compute_fn: Optional[Callable] = None
    
    # Caching
    cache_ttl_seconds: int = 0


@dataclass
class FeatureStoreStats:
    """Feature store statistics."""
    total_feature_groups: int = 0
    total_features: int = 0
    total_entities: int = 0
    
    online_requests: int = 0
    offline_requests: int = 0
    
    avg_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0


# Online store
class OnlineStore(ABC):
    """Online feature store."""
    
    @abstractmethod
    async def write(
        self,
        feature_group: str,
        entity_id: str,
        features: Dict[str, Any],
        event_time: Optional[datetime] = None,
    ) -> None:
        pass
    
    @abstractmethod
    async def read(
        self,
        feature_group: str,
        entity_ids: List[str],
        feature_names: Optional[List[str]] = None,
    ) -> List[FeatureVector]:
        pass
    
    @abstractmethod
    async def delete(self, feature_group: str, entity_id: str) -> bool:
        pass


class InMemoryOnlineStore(OnlineStore):
    """In-memory online store."""
    
    def __init__(self, max_entities: int = 100000):
        self._data: Dict[str, Dict[str, FeatureVector]] = defaultdict(dict)
        self._max_entities = max_entities
    
    async def write(
        self,
        feature_group: str,
        entity_id: str,
        features: Dict[str, Any],
        event_time: Optional[datetime] = None,
    ) -> None:
        vector = FeatureVector(
            entity_id=entity_id,
            feature_group=feature_group,
            event_time=event_time or datetime.utcnow(),
        )
        
        for name, value in features.items():
            vector.features[name] = FeatureValue(
                feature_name=name,
                value=value,
                event_time=event_time,
            )
        
        self._data[feature_group][entity_id] = vector
    
    async def read(
        self,
        feature_group: str,
        entity_ids: List[str],
        feature_names: Optional[List[str]] = None,
    ) -> List[FeatureVector]:
        results = []
        group_data = self._data.get(feature_group, {})
        
        for entity_id in entity_ids:
            vector = group_data.get(entity_id)
            
            if vector:
                if feature_names:
                    filtered = FeatureVector(
                        entity_id=entity_id,
                        feature_group=feature_group,
                        event_time=vector.event_time,
                    )
                    for name in feature_names:
                        if name in vector.features:
                            filtered.features[name] = vector.features[name]
                    results.append(filtered)
                else:
                    results.append(vector)
            else:
                results.append(FeatureVector(
                    entity_id=entity_id,
                    feature_group=feature_group,
                ))
        
        return results
    
    async def delete(self, feature_group: str, entity_id: str) -> bool:
        group_data = self._data.get(feature_group, {})
        
        if entity_id in group_data:
            del group_data[entity_id]
            return True
        
        return False


# Offline store
class OfflineStore(ABC):
    """Offline feature store."""
    
    @abstractmethod
    async def write_batch(
        self,
        feature_group: str,
        data: List[Dict[str, Any]],
    ) -> int:
        pass
    
    @abstractmethod
    async def read_historical(
        self,
        feature_group: str,
        entity_ids: List[str],
        start_time: datetime,
        end_time: datetime,
        feature_names: Optional[List[str]] = None,
    ) -> List[FeatureVector]:
        pass
    
    @abstractmethod
    async def get_training_data(
        self,
        feature_groups: List[str],
        entity_ids: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        pass


class InMemoryOfflineStore(OfflineStore):
    """In-memory offline store."""
    
    def __init__(self, max_rows: int = 1000000):
        self._data: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._max_rows = max_rows
    
    async def write_batch(
        self,
        feature_group: str,
        data: List[Dict[str, Any]],
    ) -> int:
        for row in data:
            row["_ingested_at"] = datetime.utcnow()
            self._data[feature_group].append(row)
        
        # Truncate if too many rows
        if len(self._data[feature_group]) > self._max_rows:
            self._data[feature_group] = self._data[feature_group][-self._max_rows:]
        
        return len(data)
    
    async def read_historical(
        self,
        feature_group: str,
        entity_ids: List[str],
        start_time: datetime,
        end_time: datetime,
        feature_names: Optional[List[str]] = None,
    ) -> List[FeatureVector]:
        results = []
        group_data = self._data.get(feature_group, [])
        
        for entity_id in entity_ids:
            entity_data = [
                row for row in group_data
                if row.get("entity_id") == entity_id
            ]
            
            if entity_data:
                # Get latest within time range
                latest = entity_data[-1]
                
                vector = FeatureVector(
                    entity_id=entity_id,
                    feature_group=feature_group,
                )
                
                for key, value in latest.items():
                    if key.startswith("_"):
                        continue
                    if feature_names and key not in feature_names:
                        continue
                    
                    vector.features[key] = FeatureValue(
                        feature_name=key,
                        value=value,
                    )
                
                results.append(vector)
        
        return results
    
    async def get_training_data(
        self,
        feature_groups: List[str],
        entity_ids: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        combined = []
        
        for group in feature_groups:
            group_data = self._data.get(group, [])
            
            for row in group_data:
                if entity_ids and row.get("entity_id") not in entity_ids:
                    continue
                
                combined.append({
                    "feature_group": group,
                    **{k: v for k, v in row.items() if not k.startswith("_")},
                })
        
        return combined


# Feature registry
class FeatureRegistry:
    """Feature group registry."""
    
    def __init__(self):
        self._groups: Dict[str, FeatureGroup] = {}
        self._on_demand: Dict[str, OnDemandFeature] = {}
    
    async def register(self, group: FeatureGroup) -> None:
        self._groups[group.name] = group
    
    async def get(self, name: str) -> Optional[FeatureGroup]:
        return self._groups.get(name)
    
    async def list(self) -> List[FeatureGroup]:
        return list(self._groups.values())
    
    async def delete(self, name: str) -> bool:
        if name in self._groups:
            del self._groups[name]
            return True
        return False
    
    async def register_on_demand(self, feature: OnDemandFeature) -> None:
        self._on_demand[feature.name] = feature
    
    async def get_on_demand(self, name: str) -> Optional[OnDemandFeature]:
        return self._on_demand.get(name)


# Feature store
class FeatureStore:
    """Feature store."""
    
    def __init__(
        self,
        online_store: Optional[OnlineStore] = None,
        offline_store: Optional[OfflineStore] = None,
    ):
        self._online = online_store or InMemoryOnlineStore()
        self._offline = offline_store or InMemoryOfflineStore()
        self._registry = FeatureRegistry()
        
        # Cache for on-demand features
        self._cache: Dict[str, Tuple[Any, datetime]] = {}
        
        self._listeners: List[Callable] = []
        
        # Statistics
        self._online_requests = 0
        self._offline_requests = 0
        self._latencies: List[float] = []
        self._cache_hits = 0
        self._cache_misses = 0
    
    async def register_feature_group(
        self,
        name: str,
        entity: str,
        features: List[str],
        description: str = "",
        storage_type: StorageType = StorageType.BOTH,
        **kwargs,
    ) -> FeatureGroup:
        """Register a feature group."""
        feature_defs = {
            f: FeatureDefinition(name=f)
            for f in features
        }
        
        group = FeatureGroup(
            name=name,
            entity=entity,
            features=feature_defs,
            description=description,
            storage_type=storage_type,
            **kwargs,
        )
        
        await self._registry.register(group)
        
        await self._emit_event("feature_group_registered", {"name": name})
        
        logger.info(f"Feature group registered: {name} with {len(features)} features")
        
        return group
    
    async def get_feature_group(self, name: str) -> Optional[FeatureGroup]:
        """Get feature group."""
        return await self._registry.get(name)
    
    async def list_feature_groups(self) -> List[FeatureGroup]:
        """List all feature groups."""
        return await self._registry.list()
    
    async def ingest(
        self,
        feature_group: str,
        features: Dict[str, Any],
        event_time: Optional[datetime] = None,
    ) -> None:
        """Ingest features for an entity."""
        group = await self._registry.get(feature_group)
        
        if not group:
            raise FeatureGroupNotFoundError(f"Feature group not found: {feature_group}")
        
        entity_id = features.get(group.entity)
        
        if not entity_id:
            raise FeatureStoreError(f"Missing entity key: {group.entity}")
        
        # Write to online store
        if group.storage_type in (StorageType.ONLINE, StorageType.BOTH):
            await self._online.write(
                feature_group,
                str(entity_id),
                features,
                event_time,
            )
        
        # Write to offline store
        if group.storage_type in (StorageType.OFFLINE, StorageType.BOTH):
            await self._offline.write_batch(
                feature_group,
                [{"entity_id": str(entity_id), **features}],
            )
        
        await self._emit_event("features_ingested", {
            "feature_group": feature_group,
            "entity_id": entity_id,
        })
    
    async def ingest_batch(
        self,
        feature_group: str,
        data: List[Dict[str, Any]],
    ) -> int:
        """Ingest batch of features."""
        group = await self._registry.get(feature_group)
        
        if not group:
            raise FeatureGroupNotFoundError(f"Feature group not found: {feature_group}")
        
        # Write to online store
        if group.storage_type in (StorageType.ONLINE, StorageType.BOTH):
            for row in data:
                entity_id = row.get(group.entity)
                if entity_id:
                    await self._online.write(
                        feature_group,
                        str(entity_id),
                        row,
                    )
        
        # Write to offline store
        if group.storage_type in (StorageType.OFFLINE, StorageType.BOTH):
            rows = [
                {"entity_id": str(row.get(group.entity)), **row}
                for row in data
            ]
            await self._offline.write_batch(feature_group, rows)
        
        logger.info(f"Ingested {len(data)} rows to {feature_group}")
        
        return len(data)
    
    async def get_features(
        self,
        feature_group: str,
        entity_ids: List[str],
        feature_names: Optional[List[str]] = None,
    ) -> List[FeatureVector]:
        """Get features from online store."""
        start_time = time.monotonic()
        self._online_requests += 1
        
        vectors = await self._online.read(
            feature_group,
            entity_ids,
            feature_names,
        )
        
        latency = (time.monotonic() - start_time) * 1000
        self._latencies.append(latency)
        
        if len(self._latencies) > 1000:
            self._latencies = self._latencies[-1000:]
        
        return vectors
    
    async def get_feature(
        self,
        feature_group: str,
        entity_id: str,
        feature_name: str,
    ) -> Any:
        """Get a single feature value."""
        vectors = await self.get_features(
            feature_group,
            [entity_id],
            [feature_name],
        )
        
        if vectors and vectors[0].features:
            fv = vectors[0].features.get(feature_name)
            return fv.value if fv else None
        
        return None
    
    async def get_historical_features(
        self,
        feature_group: str,
        entity_ids: List[str],
        start_time: datetime,
        end_time: datetime,
        feature_names: Optional[List[str]] = None,
    ) -> List[FeatureVector]:
        """Get historical features from offline store."""
        self._offline_requests += 1
        
        return await self._offline.read_historical(
            feature_group,
            entity_ids,
            start_time,
            end_time,
            feature_names,
        )
    
    async def get_training_data(
        self,
        feature_groups: List[str],
        entity_ids: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get training data from offline store."""
        self._offline_requests += 1
        
        return await self._offline.get_training_data(
            feature_groups,
            entity_ids,
            start_time,
            end_time,
        )
    
    async def register_on_demand_feature(
        self,
        name: str,
        input_features: List[str],
        compute_fn: Callable,
        cache_ttl_seconds: int = 0,
    ) -> OnDemandFeature:
        """Register an on-demand computed feature."""
        feature = OnDemandFeature(
            name=name,
            input_features=input_features,
            compute_fn=compute_fn,
            cache_ttl_seconds=cache_ttl_seconds,
        )
        
        await self._registry.register_on_demand(feature)
        
        logger.info(f"On-demand feature registered: {name}")
        
        return feature
    
    async def compute_on_demand(
        self,
        feature_name: str,
        inputs: Dict[str, Any],
    ) -> Any:
        """Compute an on-demand feature."""
        feature = await self._registry.get_on_demand(feature_name)
        
        if not feature:
            raise FeatureNotFoundError(f"On-demand feature not found: {feature_name}")
        
        # Check cache
        cache_key = f"{feature_name}:{json.dumps(inputs, sort_keys=True)}"
        
        if feature.cache_ttl_seconds > 0:
            cached = self._cache.get(cache_key)
            
            if cached:
                value, cached_at = cached
                age = (datetime.utcnow() - cached_at).total_seconds()
                
                if age < feature.cache_ttl_seconds:
                    self._cache_hits += 1
                    return value
        
        self._cache_misses += 1
        
        # Compute
        if feature.compute_fn:
            if asyncio.iscoroutinefunction(feature.compute_fn):
                result = await feature.compute_fn(inputs)
            else:
                result = feature.compute_fn(inputs)
            
            # Cache result
            if feature.cache_ttl_seconds > 0:
                self._cache[cache_key] = (result, datetime.utcnow())
            
            return result
        
        return None
    
    async def delete_entity(
        self,
        feature_group: str,
        entity_id: str,
    ) -> bool:
        """Delete entity from online store."""
        return await self._online.delete(feature_group, entity_id)
    
    async def get_stats(self) -> FeatureStoreStats:
        """Get feature store statistics."""
        groups = await self._registry.list()
        
        total_features = sum(len(g.features) for g in groups)
        
        avg_latency = (
            sum(self._latencies) / len(self._latencies)
            if self._latencies else 0.0
        )
        
        total_cache = self._cache_hits + self._cache_misses
        cache_hit_rate = self._cache_hits / total_cache if total_cache > 0 else 0.0
        
        return FeatureStoreStats(
            total_feature_groups=len(groups),
            total_features=total_features,
            online_requests=self._online_requests,
            offline_requests=self._offline_requests,
            avg_latency_ms=avg_latency,
            cache_hit_rate=cache_hit_rate,
        )
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    async def _emit_event(self, event: str, data: Dict[str, Any]) -> None:
        """Emit event to listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, data)
                else:
                    listener(event, data)
            except Exception as e:
                logger.error(f"Listener error: {e}")


# Feature serving
class FeatureServer:
    """Feature server for low-latency serving."""
    
    def __init__(self, store: FeatureStore):
        self._store = store
        self._preloaded: Dict[str, Dict[str, FeatureVector]] = {}
    
    async def preload(
        self,
        feature_group: str,
        entity_ids: List[str],
    ) -> int:
        """Preload features into memory."""
        vectors = await self._store.get_features(feature_group, entity_ids)
        
        if feature_group not in self._preloaded:
            self._preloaded[feature_group] = {}
        
        for vector in vectors:
            self._preloaded[feature_group][vector.entity_id] = vector
        
        return len(vectors)
    
    async def serve(
        self,
        feature_group: str,
        entity_id: str,
        feature_names: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Serve features with low latency."""
        # Check preloaded
        if feature_group in self._preloaded:
            vector = self._preloaded[feature_group].get(entity_id)
            
            if vector:
                result = {}
                
                for name, fv in vector.features.items():
                    if feature_names is None or name in feature_names:
                        result[name] = fv.value
                
                return result
        
        # Fall back to store
        vectors = await self._store.get_features(
            feature_group,
            [entity_id],
            feature_names,
        )
        
        if vectors and vectors[0].features:
            return {
                name: fv.value
                for name, fv in vectors[0].features.items()
            }
        
        return {}


# Factory functions
def create_feature_store() -> FeatureStore:
    """Create feature store."""
    return FeatureStore()


def create_feature_server(store: FeatureStore) -> FeatureServer:
    """Create feature server."""
    return FeatureServer(store)


def create_feature_definition(
    name: str,
    feature_type: FeatureType = FeatureType.FLOAT,
    **kwargs,
) -> FeatureDefinition:
    """Create feature definition."""
    return FeatureDefinition(
        name=name,
        feature_type=feature_type,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "FeatureStoreError",
    "FeatureGroupNotFoundError",
    "FeatureNotFoundError",
    "EntityNotFoundError",
    # Enums
    "FeatureType",
    "StorageType",
    "ComputationType",
    "AggregationType",
    # Data classes
    "FeatureDefinition",
    "FeatureGroup",
    "FeatureValue",
    "FeatureVector",
    "MaterializationJob",
    "OnDemandFeature",
    "FeatureStoreStats",
    # Online store
    "OnlineStore",
    "InMemoryOnlineStore",
    # Offline store
    "OfflineStore",
    "InMemoryOfflineStore",
    # Registry
    "FeatureRegistry",
    # Store
    "FeatureStore",
    # Server
    "FeatureServer",
    # Factory functions
    "create_feature_store",
    "create_feature_server",
    "create_feature_definition",
]
