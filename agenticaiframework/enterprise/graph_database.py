"""
Enterprise Graph Database Module.

Graph database connectivity with traversal, queries,
and pattern matching for Neo4j, Amazon Neptune, etc.

Example:
    # Create graph database
    graph = create_graph_database()
    
    # Create nodes and relationships
    user = await graph.create_node("User", {"name": "Alice"})
    post = await graph.create_node("Post", {"title": "Hello"})
    await graph.create_edge(user.id, post.id, "AUTHORED")
    
    # Query
    results = await graph.query(
        "MATCH (u:User)-[:AUTHORED]->(p:Post) RETURN u, p"
    )
    
    # Traversal
    friends = await graph.traverse(
        user.id,
        edge_type="FRIEND",
        depth=2,
    )
"""

from __future__ import annotations

import asyncio
import functools
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
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')


logger = logging.getLogger(__name__)


class GraphError(Exception):
    """Graph error."""
    pass


class NodeNotFoundError(GraphError):
    """Node not found."""
    pass


class EdgeNotFoundError(GraphError):
    """Edge not found."""
    pass


class QueryError(GraphError):
    """Query error."""
    pass


class TraversalDirection(str, Enum):
    """Traversal direction."""
    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BOTH = "both"


class TraversalStrategy(str, Enum):
    """Traversal strategy."""
    BFS = "bfs"
    DFS = "dfs"


@dataclass
class Node:
    """Graph node."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    labels: List[str] = field(default_factory=list)
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def add_label(self, label: str) -> None:
        """Add label to node."""
        if label not in self.labels:
            self.labels.append(label)
    
    def remove_label(self, label: str) -> None:
        """Remove label from node."""
        if label in self.labels:
            self.labels.remove(label)
    
    def has_label(self, label: str) -> bool:
        """Check if node has label."""
        return label in self.labels
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get property value."""
        return self.properties.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set property value."""
        self.properties[key] = value
        self.updated_at = datetime.utcnow()


@dataclass
class Edge:
    """Graph edge."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""
    target_id: str = ""
    type: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get property value."""
        return self.properties.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set property value."""
        self.properties[key] = value


@dataclass
class Path:
    """Graph path."""
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    
    @property
    def length(self) -> int:
        """Get path length (number of edges)."""
        return len(self.edges)
    
    @property
    def start_node(self) -> Optional[Node]:
        """Get start node."""
        return self.nodes[0] if self.nodes else None
    
    @property
    def end_node(self) -> Optional[Node]:
        """Get end node."""
        return self.nodes[-1] if self.nodes else None


@dataclass
class TraversalResult:
    """Traversal result."""
    paths: List[Path] = field(default_factory=list)
    visited_nodes: List[Node] = field(default_factory=list)
    visited_edges: List[Edge] = field(default_factory=list)
    depth: int = 0


@dataclass
class QueryResult:
    """Query result."""
    records: List[Dict[str, Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    count: int = 0
    execution_time_ms: float = 0.0
    
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return iter(self.records)
    
    def __len__(self) -> int:
        return self.count


@dataclass
class GraphStats:
    """Graph statistics."""
    node_count: int = 0
    edge_count: int = 0
    label_counts: Dict[str, int] = field(default_factory=dict)
    edge_type_counts: Dict[str, int] = field(default_factory=dict)


# Graph backend interface
class GraphBackend(ABC):
    """Abstract graph backend."""
    
    @abstractmethod
    async def create_node(
        self,
        labels: List[str],
        properties: Dict[str, Any],
    ) -> Node:
        """Create node."""
        pass
    
    @abstractmethod
    async def get_node(self, node_id: str) -> Optional[Node]:
        """Get node by ID."""
        pass
    
    @abstractmethod
    async def update_node(
        self,
        node_id: str,
        properties: Dict[str, Any],
    ) -> Optional[Node]:
        """Update node properties."""
        pass
    
    @abstractmethod
    async def delete_node(self, node_id: str) -> bool:
        """Delete node."""
        pass
    
    @abstractmethod
    async def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: Dict[str, Any],
    ) -> Edge:
        """Create edge."""
        pass
    
    @abstractmethod
    async def get_edge(self, edge_id: str) -> Optional[Edge]:
        """Get edge by ID."""
        pass
    
    @abstractmethod
    async def delete_edge(self, edge_id: str) -> bool:
        """Delete edge."""
        pass
    
    @abstractmethod
    async def query(self, query: str, params: Dict[str, Any]) -> QueryResult:
        """Execute query."""
        pass
    
    @abstractmethod
    async def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[str],
        direction: TraversalDirection,
    ) -> List[Tuple[Edge, Node]]:
        """Get neighboring nodes."""
        pass
    
    @abstractmethod
    async def get_stats(self) -> GraphStats:
        """Get graph statistics."""
        pass


class InMemoryGraphBackend(GraphBackend):
    """In-memory graph backend."""
    
    def __init__(self):
        self._nodes: Dict[str, Node] = {}
        self._edges: Dict[str, Edge] = {}
        self._outgoing: Dict[str, List[str]] = defaultdict(list)
        self._incoming: Dict[str, List[str]] = defaultdict(list)
        self._label_index: Dict[str, Set[str]] = defaultdict(set)
    
    async def create_node(
        self,
        labels: List[str],
        properties: Dict[str, Any],
    ) -> Node:
        node = Node(labels=labels, properties=properties)
        self._nodes[node.id] = node
        
        for label in labels:
            self._label_index[label].add(node.id)
        
        return node
    
    async def get_node(self, node_id: str) -> Optional[Node]:
        return self._nodes.get(node_id)
    
    async def update_node(
        self,
        node_id: str,
        properties: Dict[str, Any],
    ) -> Optional[Node]:
        node = self._nodes.get(node_id)
        
        if node:
            node.properties.update(properties)
            node.updated_at = datetime.utcnow()
        
        return node
    
    async def delete_node(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        
        node = self._nodes[node_id]
        
        # Remove from label index
        for label in node.labels:
            self._label_index[label].discard(node_id)
        
        # Remove connected edges
        for edge_id in list(self._outgoing.get(node_id, [])):
            await self.delete_edge(edge_id)
        
        for edge_id in list(self._incoming.get(node_id, [])):
            await self.delete_edge(edge_id)
        
        del self._nodes[node_id]
        return True
    
    async def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: Dict[str, Any],
    ) -> Edge:
        if source_id not in self._nodes:
            raise NodeNotFoundError(f"Source node {source_id} not found")
        
        if target_id not in self._nodes:
            raise NodeNotFoundError(f"Target node {target_id} not found")
        
        edge = Edge(
            source_id=source_id,
            target_id=target_id,
            type=edge_type,
            properties=properties,
        )
        
        self._edges[edge.id] = edge
        self._outgoing[source_id].append(edge.id)
        self._incoming[target_id].append(edge.id)
        
        return edge
    
    async def get_edge(self, edge_id: str) -> Optional[Edge]:
        return self._edges.get(edge_id)
    
    async def delete_edge(self, edge_id: str) -> bool:
        if edge_id not in self._edges:
            return False
        
        edge = self._edges[edge_id]
        
        if edge.source_id in self._outgoing:
            self._outgoing[edge.source_id].remove(edge_id)
        
        if edge.target_id in self._incoming:
            self._incoming[edge.target_id].remove(edge_id)
        
        del self._edges[edge_id]
        return True
    
    async def query(self, query: str, params: Dict[str, Any]) -> QueryResult:
        # Simple query parser for demo purposes
        records = []
        
        # Handle simple MATCH queries
        if "MATCH" in query.upper():
            # Return all nodes for simple queries
            for node in self._nodes.values():
                records.append({"n": node})
        
        return QueryResult(
            records=records,
            count=len(records),
        )
    
    async def get_neighbors(
        self,
        node_id: str,
        edge_type: Optional[str],
        direction: TraversalDirection,
    ) -> List[Tuple[Edge, Node]]:
        neighbors = []
        
        if direction in (TraversalDirection.OUTGOING, TraversalDirection.BOTH):
            for edge_id in self._outgoing.get(node_id, []):
                edge = self._edges[edge_id]
                
                if edge_type is None or edge.type == edge_type:
                    node = self._nodes.get(edge.target_id)
                    if node:
                        neighbors.append((edge, node))
        
        if direction in (TraversalDirection.INCOMING, TraversalDirection.BOTH):
            for edge_id in self._incoming.get(node_id, []):
                edge = self._edges[edge_id]
                
                if edge_type is None or edge.type == edge_type:
                    node = self._nodes.get(edge.source_id)
                    if node:
                        neighbors.append((edge, node))
        
        return neighbors
    
    async def get_stats(self) -> GraphStats:
        label_counts = {}
        for label, node_ids in self._label_index.items():
            label_counts[label] = len(node_ids)
        
        edge_type_counts: Dict[str, int] = defaultdict(int)
        for edge in self._edges.values():
            edge_type_counts[edge.type] += 1
        
        return GraphStats(
            node_count=len(self._nodes),
            edge_count=len(self._edges),
            label_counts=label_counts,
            edge_type_counts=dict(edge_type_counts),
        )
    
    async def find_by_label(self, label: str) -> List[Node]:
        """Find nodes by label."""
        return [
            self._nodes[node_id]
            for node_id in self._label_index.get(label, [])
        ]
    
    async def find_by_property(
        self,
        label: Optional[str],
        key: str,
        value: Any,
    ) -> List[Node]:
        """Find nodes by property."""
        results = []
        
        if label:
            node_ids = self._label_index.get(label, set())
            nodes = [self._nodes[nid] for nid in node_ids]
        else:
            nodes = list(self._nodes.values())
        
        for node in nodes:
            if node.properties.get(key) == value:
                results.append(node)
        
        return results


# Graph database
class GraphDatabase:
    """
    Graph database service.
    """
    
    def __init__(
        self,
        backend: Optional[GraphBackend] = None,
    ):
        self._backend = backend or InMemoryGraphBackend()
    
    async def create_node(
        self,
        *labels: str,
        **properties,
    ) -> Node:
        """
        Create a node.
        
        Args:
            *labels: Node labels
            **properties: Node properties
            
        Returns:
            Created node
        """
        return await self._backend.create_node(
            labels=list(labels),
            properties=properties,
        )
    
    async def get_node(self, node_id: str) -> Optional[Node]:
        """Get node by ID."""
        return await self._backend.get_node(node_id)
    
    async def update_node(
        self,
        node_id: str,
        **properties,
    ) -> Optional[Node]:
        """Update node properties."""
        return await self._backend.update_node(node_id, properties)
    
    async def delete_node(self, node_id: str) -> bool:
        """Delete node."""
        return await self._backend.delete_node(node_id)
    
    async def create_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        **properties,
    ) -> Edge:
        """
        Create an edge between nodes.
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            edge_type: Edge type/relationship
            **properties: Edge properties
            
        Returns:
            Created edge
        """
        return await self._backend.create_edge(
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            properties=properties,
        )
    
    async def get_edge(self, edge_id: str) -> Optional[Edge]:
        """Get edge by ID."""
        return await self._backend.get_edge(edge_id)
    
    async def delete_edge(self, edge_id: str) -> bool:
        """Delete edge."""
        return await self._backend.delete_edge(edge_id)
    
    async def query(
        self,
        query: str,
        **params,
    ) -> QueryResult:
        """
        Execute a query.
        
        Args:
            query: Query string (Cypher-like)
            **params: Query parameters
            
        Returns:
            Query result
        """
        import time
        start = time.perf_counter()
        
        result = await self._backend.query(query, params)
        
        result.execution_time_ms = (time.perf_counter() - start) * 1000
        
        return result
    
    async def traverse(
        self,
        start_node_id: str,
        edge_type: Optional[str] = None,
        direction: TraversalDirection = TraversalDirection.OUTGOING,
        depth: int = 1,
        strategy: TraversalStrategy = TraversalStrategy.BFS,
        filter_func: Optional[Callable[[Node], bool]] = None,
    ) -> TraversalResult:
        """
        Traverse graph from starting node.
        
        Args:
            start_node_id: Starting node ID
            edge_type: Filter by edge type
            direction: Traversal direction
            depth: Maximum depth
            strategy: BFS or DFS
            filter_func: Node filter function
            
        Returns:
            Traversal result
        """
        start_node = await self._backend.get_node(start_node_id)
        
        if not start_node:
            raise NodeNotFoundError(f"Node {start_node_id} not found")
        
        visited_node_ids: Set[str] = {start_node_id}
        visited_nodes: List[Node] = [start_node]
        visited_edges: List[Edge] = []
        paths: List[Path] = []
        
        # Queue/stack of (node_id, current_depth, current_path)
        frontier: deque = deque([(start_node_id, 0, Path(nodes=[start_node]))])
        
        while frontier:
            if strategy == TraversalStrategy.BFS:
                node_id, current_depth, current_path = frontier.popleft()
            else:
                node_id, current_depth, current_path = frontier.pop()
            
            if current_depth >= depth:
                paths.append(current_path)
                continue
            
            neighbors = await self._backend.get_neighbors(
                node_id, edge_type, direction
            )
            
            for edge, neighbor in neighbors:
                if neighbor.id in visited_node_ids:
                    continue
                
                if filter_func and not filter_func(neighbor):
                    continue
                
                visited_node_ids.add(neighbor.id)
                visited_nodes.append(neighbor)
                visited_edges.append(edge)
                
                new_path = Path(
                    nodes=current_path.nodes + [neighbor],
                    edges=current_path.edges + [edge],
                )
                
                frontier.append((neighbor.id, current_depth + 1, new_path))
        
        return TraversalResult(
            paths=paths,
            visited_nodes=visited_nodes,
            visited_edges=visited_edges,
            depth=depth,
        )
    
    async def find_shortest_path(
        self,
        start_node_id: str,
        end_node_id: str,
        edge_type: Optional[str] = None,
        max_depth: int = 10,
    ) -> Optional[Path]:
        """
        Find shortest path between nodes.
        
        Args:
            start_node_id: Start node ID
            end_node_id: End node ID
            edge_type: Filter by edge type
            max_depth: Maximum search depth
            
        Returns:
            Shortest path or None
        """
        start_node = await self._backend.get_node(start_node_id)
        end_node = await self._backend.get_node(end_node_id)
        
        if not start_node or not end_node:
            return None
        
        visited: Set[str] = {start_node_id}
        queue: deque = deque([Path(nodes=[start_node])])
        
        while queue:
            current_path = queue.popleft()
            current_node = current_path.end_node
            
            if not current_node:
                continue
            
            if current_path.length >= max_depth:
                continue
            
            if current_node.id == end_node_id:
                return current_path
            
            neighbors = await self._backend.get_neighbors(
                current_node.id,
                edge_type,
                TraversalDirection.BOTH,
            )
            
            for edge, neighbor in neighbors:
                if neighbor.id not in visited:
                    visited.add(neighbor.id)
                    
                    new_path = Path(
                        nodes=current_path.nodes + [neighbor],
                        edges=current_path.edges + [edge],
                    )
                    
                    queue.append(new_path)
        
        return None
    
    async def get_stats(self) -> GraphStats:
        """Get graph statistics."""
        return await self._backend.get_stats()
    
    async def find_by_label(self, label: str) -> List[Node]:
        """Find nodes by label."""
        if isinstance(self._backend, InMemoryGraphBackend):
            return await self._backend.find_by_label(label)
        
        result = await self.query(f"MATCH (n:{label}) RETURN n")
        return [r.get("n") for r in result.records if r.get("n")]
    
    async def find_by_property(
        self,
        label: Optional[str] = None,
        **properties,
    ) -> List[Node]:
        """Find nodes by properties."""
        if isinstance(self._backend, InMemoryGraphBackend):
            results = []
            for key, value in properties.items():
                nodes = await self._backend.find_by_property(label, key, value)
                results.extend(nodes)
            return results
        
        # Use query for other backends
        if label:
            query = f"MATCH (n:{label}) WHERE"
        else:
            query = "MATCH (n) WHERE"
        
        conditions = [f"n.{k} = ${k}" for k in properties.keys()]
        query += " AND ".join(conditions) + " RETURN n"
        
        result = await self.query(query, **properties)
        return [r.get("n") for r in result.records if r.get("n")]


# Decorators
def graph_entity(label: str, **defaults):
    """
    Decorator to mark class as graph entity.
    
    Args:
        label: Node label
        **defaults: Default properties
    """
    def decorator(cls):
        cls._graph_label = label
        cls._graph_defaults = defaults
        
        @functools.wraps(cls)
        def wrapper(*args, **kwargs):
            instance = cls(*args, **kwargs)
            return instance
        
        wrapper._graph_label = label
        wrapper._graph_defaults = defaults
        
        return wrapper
    
    return decorator


def relationship(
    edge_type: str,
    target_label: Optional[str] = None,
):
    """
    Decorator for relationship property.
    
    Args:
        edge_type: Edge type
        target_label: Target node label
    """
    def decorator(func):
        func._relationship = {
            "type": edge_type,
            "target_label": target_label,
        }
        return func
    
    return decorator


# Factory functions
def create_graph_database(
    backend: Optional[GraphBackend] = None,
) -> GraphDatabase:
    """Create graph database."""
    return GraphDatabase(backend=backend)


def create_in_memory_backend() -> InMemoryGraphBackend:
    """Create in-memory backend."""
    return InMemoryGraphBackend()


__all__ = [
    # Exceptions
    "GraphError",
    "NodeNotFoundError",
    "EdgeNotFoundError",
    "QueryError",
    # Enums
    "TraversalDirection",
    "TraversalStrategy",
    # Data classes
    "Node",
    "Edge",
    "Path",
    "TraversalResult",
    "QueryResult",
    "GraphStats",
    # Backend
    "GraphBackend",
    "InMemoryGraphBackend",
    # Main class
    "GraphDatabase",
    # Decorators
    "graph_entity",
    "relationship",
    # Factory functions
    "create_graph_database",
    "create_in_memory_backend",
]
