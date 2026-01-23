"""
Enterprise Data Lineage Tracker Module.

Data lineage tracking, impact analysis, data catalog,
and dependency visualization.

Example:
    # Create lineage tracker
    lineage = create_lineage_tracker()
    
    # Register data asset
    await lineage.register_asset(
        name="customers",
        asset_type=AssetType.TABLE,
        source="postgres.sales",
    )
    
    # Track transformation
    await lineage.add_transformation(
        name="customer_aggregation",
        inputs=["customers", "orders"],
        outputs=["customer_stats"],
    )
    
    # Get upstream dependencies
    upstream = await lineage.get_upstream("customer_stats")
    
    # Impact analysis
    impact = await lineage.analyze_impact("customers")
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

logger = logging.getLogger(__name__)


class LineageError(Exception):
    """Lineage error."""
    pass


class AssetNotFoundError(LineageError):
    """Asset not found error."""
    pass


class AssetType(str, Enum):
    """Data asset type."""
    TABLE = "table"
    VIEW = "view"
    COLUMN = "column"
    FILE = "file"
    STREAM = "stream"
    API = "api"
    DATASET = "dataset"
    MODEL = "model"
    REPORT = "report"
    DASHBOARD = "dashboard"


class TransformationType(str, Enum):
    """Transformation type."""
    ETL = "etl"
    SQL = "sql"
    PYTHON = "python"
    SPARK = "spark"
    AIRFLOW = "airflow"
    DBT = "dbt"
    CUSTOM = "custom"


class LineageDirection(str, Enum):
    """Lineage direction."""
    UPSTREAM = "upstream"
    DOWNSTREAM = "downstream"
    BOTH = "both"


class ImpactSeverity(str, Enum):
    """Impact severity."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DataAsset:
    """Data asset."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    asset_type: AssetType = AssetType.TABLE
    
    # Location
    source: str = ""  # e.g., database.schema.table
    path: str = ""
    
    # Schema
    schema: Dict[str, Any] = field(default_factory=dict)
    columns: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    description: str = ""
    owner: str = ""
    tags: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    
    # Quality
    quality_score: Optional[float] = None
    freshness: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed_at: Optional[datetime] = None


@dataclass
class Transformation:
    """Data transformation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    transformation_type: TransformationType = TransformationType.CUSTOM
    
    # Inputs/Outputs
    inputs: List[str] = field(default_factory=list)  # Asset IDs
    outputs: List[str] = field(default_factory=list)  # Asset IDs
    
    # Logic
    query: str = ""
    code: str = ""
    
    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    description: str = ""
    owner: str = ""
    schedule: str = ""  # Cron expression
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_run_at: Optional[datetime] = None


@dataclass
class LineageEdge:
    """Lineage edge."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    transformation_id: Optional[str] = None
    
    # Column-level lineage
    column_mappings: List[Dict[str, str]] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class LineagePath:
    """Lineage path."""
    nodes: List[str] = field(default_factory=list)  # Asset IDs
    edges: List[str] = field(default_factory=list)  # Edge IDs
    depth: int = 0


@dataclass
class ImpactAnalysis:
    """Impact analysis result."""
    source_asset: str = ""
    
    # Affected assets
    affected_assets: List[str] = field(default_factory=list)
    affected_by_depth: Dict[int, List[str]] = field(default_factory=dict)
    
    # Impact details
    total_affected: int = 0
    severity: ImpactSeverity = ImpactSeverity.LOW
    
    # Paths
    paths: List[LineagePath] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)


@dataclass
class LineageStats:
    """Lineage statistics."""
    total_assets: int = 0
    total_transformations: int = 0
    total_edges: int = 0
    avg_depth: float = 0.0
    max_depth: int = 0


# Lineage store
class LineageStore(ABC):
    """Lineage storage."""
    
    @abstractmethod
    async def save_asset(self, asset: DataAsset) -> None:
        pass
    
    @abstractmethod
    async def get_asset(self, asset_id: str) -> Optional[DataAsset]:
        pass
    
    @abstractmethod
    async def get_asset_by_name(self, name: str) -> Optional[DataAsset]:
        pass
    
    @abstractmethod
    async def list_assets(self) -> List[DataAsset]:
        pass
    
    @abstractmethod
    async def save_transformation(self, transformation: Transformation) -> None:
        pass
    
    @abstractmethod
    async def get_transformation(self, transformation_id: str) -> Optional[Transformation]:
        pass
    
    @abstractmethod
    async def save_edge(self, edge: LineageEdge) -> None:
        pass
    
    @abstractmethod
    async def get_edges_from(self, asset_id: str) -> List[LineageEdge]:
        pass
    
    @abstractmethod
    async def get_edges_to(self, asset_id: str) -> List[LineageEdge]:
        pass


class InMemoryLineageStore(LineageStore):
    """In-memory lineage store."""
    
    def __init__(self):
        self._assets: Dict[str, DataAsset] = {}
        self._assets_by_name: Dict[str, str] = {}
        self._transformations: Dict[str, Transformation] = {}
        self._edges: Dict[str, LineageEdge] = {}
        self._edges_from: Dict[str, List[str]] = defaultdict(list)
        self._edges_to: Dict[str, List[str]] = defaultdict(list)
    
    async def save_asset(self, asset: DataAsset) -> None:
        self._assets[asset.id] = asset
        self._assets_by_name[asset.name] = asset.id
    
    async def get_asset(self, asset_id: str) -> Optional[DataAsset]:
        return self._assets.get(asset_id)
    
    async def get_asset_by_name(self, name: str) -> Optional[DataAsset]:
        asset_id = self._assets_by_name.get(name)
        return self._assets.get(asset_id) if asset_id else None
    
    async def list_assets(self) -> List[DataAsset]:
        return list(self._assets.values())
    
    async def save_transformation(self, transformation: Transformation) -> None:
        self._transformations[transformation.id] = transformation
    
    async def get_transformation(self, transformation_id: str) -> Optional[Transformation]:
        return self._transformations.get(transformation_id)
    
    async def save_edge(self, edge: LineageEdge) -> None:
        self._edges[edge.id] = edge
        self._edges_from[edge.source_id].append(edge.id)
        self._edges_to[edge.target_id].append(edge.id)
    
    async def get_edges_from(self, asset_id: str) -> List[LineageEdge]:
        edge_ids = self._edges_from.get(asset_id, [])
        return [self._edges[eid] for eid in edge_ids if eid in self._edges]
    
    async def get_edges_to(self, asset_id: str) -> List[LineageEdge]:
        edge_ids = self._edges_to.get(asset_id, [])
        return [self._edges[eid] for eid in edge_ids if eid in self._edges]


# Lineage graph
class LineageGraph:
    """Lineage graph."""
    
    def __init__(self, store: LineageStore):
        self._store = store
    
    async def get_upstream(
        self,
        asset_id: str,
        max_depth: int = 10,
    ) -> List[LineagePath]:
        """Get upstream lineage."""
        return await self._traverse(asset_id, LineageDirection.UPSTREAM, max_depth)
    
    async def get_downstream(
        self,
        asset_id: str,
        max_depth: int = 10,
    ) -> List[LineagePath]:
        """Get downstream lineage."""
        return await self._traverse(asset_id, LineageDirection.DOWNSTREAM, max_depth)
    
    async def _traverse(
        self,
        start_id: str,
        direction: LineageDirection,
        max_depth: int,
    ) -> List[LineagePath]:
        """Traverse lineage graph."""
        paths = []
        visited = set()
        
        queue = deque([(start_id, [start_id], [], 0)])
        
        while queue:
            current_id, path_nodes, path_edges, depth = queue.popleft()
            
            if depth >= max_depth:
                continue
            
            if current_id in visited and depth > 0:
                continue
            
            visited.add(current_id)
            
            # Get edges
            if direction == LineageDirection.UPSTREAM:
                edges = await self._store.get_edges_to(current_id)
                next_ids = [e.source_id for e in edges]
            else:
                edges = await self._store.get_edges_from(current_id)
                next_ids = [e.target_id for e in edges]
            
            if not edges:
                if len(path_nodes) > 1:
                    paths.append(LineagePath(
                        nodes=path_nodes.copy(),
                        edges=path_edges.copy(),
                        depth=depth,
                    ))
                continue
            
            for edge in edges:
                next_id = edge.source_id if direction == LineageDirection.UPSTREAM else edge.target_id
                
                new_nodes = path_nodes + [next_id]
                new_edges = path_edges + [edge.id]
                
                queue.append((next_id, new_nodes, new_edges, depth + 1))
        
        return paths
    
    async def find_path(
        self,
        source_id: str,
        target_id: str,
    ) -> Optional[LineagePath]:
        """Find path between two assets."""
        visited = set()
        queue = deque([(source_id, [source_id], [])])
        
        while queue:
            current_id, path_nodes, path_edges = queue.popleft()
            
            if current_id == target_id:
                return LineagePath(
                    nodes=path_nodes,
                    edges=path_edges,
                    depth=len(path_nodes) - 1,
                )
            
            if current_id in visited:
                continue
            
            visited.add(current_id)
            
            edges = await self._store.get_edges_from(current_id)
            
            for edge in edges:
                if edge.target_id not in visited:
                    queue.append((
                        edge.target_id,
                        path_nodes + [edge.target_id],
                        path_edges + [edge.id],
                    ))
        
        return None


# Data lineage tracker
class DataLineageTracker:
    """Data lineage tracker."""
    
    def __init__(
        self,
        store: Optional[LineageStore] = None,
    ):
        self._store = store or InMemoryLineageStore()
        self._graph = LineageGraph(self._store)
        self._listeners: List[Callable] = []
    
    async def register_asset(
        self,
        name: str,
        asset_type: Union[str, AssetType] = AssetType.TABLE,
        source: str = "",
        description: str = "",
        owner: str = "",
        columns: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ) -> DataAsset:
        """Register data asset."""
        if isinstance(asset_type, str):
            asset_type = AssetType(asset_type)
        
        # Check if exists
        existing = await self._store.get_asset_by_name(name)
        if existing:
            existing.updated_at = datetime.utcnow()
            existing.source = source or existing.source
            existing.description = description or existing.description
            await self._store.save_asset(existing)
            return existing
        
        asset = DataAsset(
            name=name,
            asset_type=asset_type,
            source=source,
            description=description,
            owner=owner,
            columns=columns or [],
            **kwargs,
        )
        
        await self._store.save_asset(asset)
        
        logger.info(f"Asset registered: {name}")
        
        return asset
    
    async def get_asset(
        self,
        name_or_id: str,
    ) -> Optional[DataAsset]:
        """Get asset by name or ID."""
        asset = await self._store.get_asset(name_or_id)
        if asset:
            return asset
        return await self._store.get_asset_by_name(name_or_id)
    
    async def list_assets(
        self,
        asset_type: Optional[AssetType] = None,
        owner: Optional[str] = None,
    ) -> List[DataAsset]:
        """List assets."""
        assets = await self._store.list_assets()
        
        if asset_type:
            assets = [a for a in assets if a.asset_type == asset_type]
        
        if owner:
            assets = [a for a in assets if a.owner == owner]
        
        return sorted(assets, key=lambda a: a.name)
    
    async def add_transformation(
        self,
        name: str,
        inputs: List[str],
        outputs: List[str],
        transformation_type: Union[str, TransformationType] = TransformationType.CUSTOM,
        query: str = "",
        description: str = "",
        column_mappings: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> Transformation:
        """Add transformation with lineage edges."""
        if isinstance(transformation_type, str):
            transformation_type = TransformationType(transformation_type)
        
        # Resolve asset names to IDs
        input_ids = []
        for inp in inputs:
            asset = await self.get_asset(inp)
            if asset:
                input_ids.append(asset.id)
            else:
                # Auto-register if not exists
                asset = await self.register_asset(inp)
                input_ids.append(asset.id)
        
        output_ids = []
        for out in outputs:
            asset = await self.get_asset(out)
            if asset:
                output_ids.append(asset.id)
            else:
                asset = await self.register_asset(out)
                output_ids.append(asset.id)
        
        transformation = Transformation(
            name=name,
            transformation_type=transformation_type,
            inputs=input_ids,
            outputs=output_ids,
            query=query,
            description=description,
            **kwargs,
        )
        
        await self._store.save_transformation(transformation)
        
        # Create edges
        for input_id in input_ids:
            for output_id in output_ids:
                edge = LineageEdge(
                    source_id=input_id,
                    target_id=output_id,
                    transformation_id=transformation.id,
                    column_mappings=column_mappings or [],
                )
                await self._store.save_edge(edge)
        
        logger.info(f"Transformation added: {name}")
        
        return transformation
    
    async def add_edge(
        self,
        source: str,
        target: str,
        transformation_id: Optional[str] = None,
        column_mappings: Optional[List[Dict[str, str]]] = None,
    ) -> LineageEdge:
        """Add direct lineage edge."""
        source_asset = await self.get_asset(source)
        target_asset = await self.get_asset(target)
        
        if not source_asset:
            source_asset = await self.register_asset(source)
        
        if not target_asset:
            target_asset = await self.register_asset(target)
        
        edge = LineageEdge(
            source_id=source_asset.id,
            target_id=target_asset.id,
            transformation_id=transformation_id,
            column_mappings=column_mappings or [],
        )
        
        await self._store.save_edge(edge)
        
        return edge
    
    async def get_upstream(
        self,
        asset_name_or_id: str,
        max_depth: int = 10,
    ) -> List[DataAsset]:
        """Get upstream dependencies."""
        asset = await self.get_asset(asset_name_or_id)
        
        if not asset:
            raise AssetNotFoundError(f"Asset not found: {asset_name_or_id}")
        
        paths = await self._graph.get_upstream(asset.id, max_depth)
        
        # Collect unique assets
        asset_ids = set()
        for path in paths:
            for node_id in path.nodes:
                if node_id != asset.id:
                    asset_ids.add(node_id)
        
        assets = []
        for aid in asset_ids:
            a = await self._store.get_asset(aid)
            if a:
                assets.append(a)
        
        return assets
    
    async def get_downstream(
        self,
        asset_name_or_id: str,
        max_depth: int = 10,
    ) -> List[DataAsset]:
        """Get downstream dependents."""
        asset = await self.get_asset(asset_name_or_id)
        
        if not asset:
            raise AssetNotFoundError(f"Asset not found: {asset_name_or_id}")
        
        paths = await self._graph.get_downstream(asset.id, max_depth)
        
        asset_ids = set()
        for path in paths:
            for node_id in path.nodes:
                if node_id != asset.id:
                    asset_ids.add(node_id)
        
        assets = []
        for aid in asset_ids:
            a = await self._store.get_asset(aid)
            if a:
                assets.append(a)
        
        return assets
    
    async def analyze_impact(
        self,
        asset_name_or_id: str,
        max_depth: int = 10,
    ) -> ImpactAnalysis:
        """Analyze impact of changes to an asset."""
        asset = await self.get_asset(asset_name_or_id)
        
        if not asset:
            raise AssetNotFoundError(f"Asset not found: {asset_name_or_id}")
        
        paths = await self._graph.get_downstream(asset.id, max_depth)
        
        analysis = ImpactAnalysis(source_asset=asset.name)
        
        # Group by depth
        by_depth: Dict[int, Set[str]] = defaultdict(set)
        
        for path in paths:
            for i, node_id in enumerate(path.nodes):
                if node_id != asset.id:
                    by_depth[i].add(node_id)
        
        # Get asset names
        all_affected = set()
        for depth, asset_ids in sorted(by_depth.items()):
            depth_assets = []
            for aid in asset_ids:
                a = await self._store.get_asset(aid)
                if a:
                    depth_assets.append(a.name)
                    all_affected.add(a.name)
            
            analysis.affected_by_depth[depth] = depth_assets
        
        analysis.affected_assets = list(all_affected)
        analysis.total_affected = len(all_affected)
        analysis.paths = paths
        
        # Determine severity
        if analysis.total_affected == 0:
            analysis.severity = ImpactSeverity.LOW
        elif analysis.total_affected <= 5:
            analysis.severity = ImpactSeverity.MEDIUM
        elif analysis.total_affected <= 20:
            analysis.severity = ImpactSeverity.HIGH
        else:
            analysis.severity = ImpactSeverity.CRITICAL
        
        # Generate recommendations
        if analysis.severity == ImpactSeverity.CRITICAL:
            analysis.recommendations.append("Consider staged rollout of changes")
            analysis.recommendations.append("Notify all downstream asset owners")
        elif analysis.severity == ImpactSeverity.HIGH:
            analysis.recommendations.append("Review all affected assets before changes")
        
        return analysis
    
    async def get_column_lineage(
        self,
        asset_name: str,
        column_name: str,
    ) -> Dict[str, List[str]]:
        """Get column-level lineage."""
        asset = await self.get_asset(asset_name)
        
        if not asset:
            return {"upstream": [], "downstream": []}
        
        upstream_cols = []
        downstream_cols = []
        
        # Get edges to this asset
        edges_to = await self._store.get_edges_to(asset.id)
        for edge in edges_to:
            for mapping in edge.column_mappings:
                if mapping.get("target") == column_name:
                    source_asset = await self._store.get_asset(edge.source_id)
                    if source_asset:
                        upstream_cols.append(
                            f"{source_asset.name}.{mapping.get('source', '?')}"
                        )
        
        # Get edges from this asset
        edges_from = await self._store.get_edges_from(asset.id)
        for edge in edges_from:
            for mapping in edge.column_mappings:
                if mapping.get("source") == column_name:
                    target_asset = await self._store.get_asset(edge.target_id)
                    if target_asset:
                        downstream_cols.append(
                            f"{target_asset.name}.{mapping.get('target', '?')}"
                        )
        
        return {
            "upstream": upstream_cols,
            "downstream": downstream_cols,
        }
    
    async def export_graph(self) -> Dict[str, Any]:
        """Export lineage graph."""
        assets = await self._store.list_assets()
        
        nodes = []
        edges = []
        
        for asset in assets:
            nodes.append({
                "id": asset.id,
                "name": asset.name,
                "type": asset.asset_type.value,
                "source": asset.source,
            })
            
            asset_edges = await self._store.get_edges_from(asset.id)
            for edge in asset_edges:
                edges.append({
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "transformation": edge.transformation_id,
                })
        
        return {
            "nodes": nodes,
            "edges": edges,
        }
    
    async def get_stats(self) -> LineageStats:
        """Get statistics."""
        assets = await self._store.list_assets()
        
        total_edges = 0
        max_depth = 0
        depths = []
        
        for asset in assets:
            paths = await self._graph.get_upstream(asset.id, 10)
            if paths:
                path_depths = [p.depth for p in paths]
                depths.extend(path_depths)
                max_depth = max(max_depth, max(path_depths))
            
            edges = await self._store.get_edges_from(asset.id)
            total_edges += len(edges)
        
        return LineageStats(
            total_assets=len(assets),
            total_transformations=0,  # Would need to track
            total_edges=total_edges,
            avg_depth=sum(depths) / len(depths) if depths else 0,
            max_depth=max_depth,
        )
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)


# Factory functions
def create_lineage_tracker() -> DataLineageTracker:
    """Create data lineage tracker."""
    return DataLineageTracker()


def create_data_asset(
    name: str,
    asset_type: AssetType = AssetType.TABLE,
    **kwargs,
) -> DataAsset:
    """Create data asset."""
    return DataAsset(name=name, asset_type=asset_type, **kwargs)


def create_transformation(
    name: str,
    inputs: List[str],
    outputs: List[str],
    **kwargs,
) -> Transformation:
    """Create transformation."""
    return Transformation(name=name, inputs=inputs, outputs=outputs, **kwargs)


__all__ = [
    # Exceptions
    "LineageError",
    "AssetNotFoundError",
    # Enums
    "AssetType",
    "TransformationType",
    "LineageDirection",
    "ImpactSeverity",
    # Data classes
    "DataAsset",
    "Transformation",
    "LineageEdge",
    "LineagePath",
    "ImpactAnalysis",
    "LineageStats",
    # Store
    "LineageStore",
    "InMemoryLineageStore",
    # Graph
    "LineageGraph",
    # Tracker
    "DataLineageTracker",
    # Factory functions
    "create_lineage_tracker",
    "create_data_asset",
    "create_transformation",
]
