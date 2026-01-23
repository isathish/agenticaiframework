"""
Enterprise Graph Module.

Provides knowledge graph structures, entity relationships,
graph traversal, and graph-based reasoning for agents.

Example:
    # Create graph
    graph = KnowledgeGraph()
    
    # Add nodes and edges
    graph.add_node("Alice", type="person", age=30)
    graph.add_node("Bob", type="person", age=25)
    graph.add_edge("Alice", "Bob", relation="knows")
    
    # Query
    friends = graph.neighbors("Alice", relation="knows")
    path = graph.shortest_path("Alice", "Charlie")
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
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
from collections import defaultdict, deque
from datetime import datetime
from functools import wraps
from enum import Enum
import logging
import json
import hashlib

logger = logging.getLogger(__name__)

T = TypeVar('T')
NodeId = str
EdgeId = str


class GraphError(Exception):
    """Graph operation error."""
    pass


class NodeNotFoundError(GraphError):
    """Node not found."""
    pass


class EdgeNotFoundError(GraphError):
    """Edge not found."""
    pass


class CycleDetectedError(GraphError):
    """Cycle detected in graph."""
    pass


class NodeType(str, Enum):
    """Common node types."""
    ENTITY = "entity"
    CONCEPT = "concept"
    DOCUMENT = "document"
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    EVENT = "event"


class EdgeType(str, Enum):
    """Common edge/relation types."""
    RELATES_TO = "relates_to"
    IS_A = "is_a"
    HAS_A = "has_a"
    PART_OF = "part_of"
    MENTIONS = "mentions"
    SIMILAR_TO = "similar_to"
    DERIVED_FROM = "derived_from"


@dataclass
class Node:
    """A graph node."""
    id: NodeId
    type: str = "entity"
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    embedding: Optional[List[float]] = None
    
    def __hash__(self) -> int:
        return hash(self.id)
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Node):
            return self.id == other.id
        return self.id == other
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "properties": self.properties,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Node':
        return cls(
            id=data["id"],
            type=data.get("type", "entity"),
            properties=data.get("properties", {}),
        )


@dataclass
class Edge:
    """A graph edge."""
    id: EdgeId
    source: NodeId
    target: NodeId
    relation: str = "relates_to"
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)
    directed: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    
    def __hash__(self) -> int:
        return hash(self.id)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "weight": self.weight,
            "properties": self.properties,
            "directed": self.directed,
        }


@dataclass
class Path:
    """A path through the graph."""
    nodes: List[Node]
    edges: List[Edge]
    
    @property
    def length(self) -> int:
        return len(self.edges)
    
    @property
    def weight(self) -> float:
        return sum(e.weight for e in self.edges)
    
    @property
    def node_ids(self) -> List[NodeId]:
        return [n.id for n in self.nodes]


@dataclass
class Subgraph:
    """A subgraph view."""
    nodes: Set[Node]
    edges: Set[Edge]
    
    @property
    def node_count(self) -> int:
        return len(self.nodes)
    
    @property
    def edge_count(self) -> int:
        return len(self.edges)


class Graph(ABC):
    """Abstract graph interface."""
    
    @abstractmethod
    def add_node(
        self,
        id: NodeId,
        type: str = "entity",
        **properties: Any,
    ) -> Node:
        """Add a node."""
        pass
    
    @abstractmethod
    def add_edge(
        self,
        source: NodeId,
        target: NodeId,
        relation: str = "relates_to",
        weight: float = 1.0,
        **properties: Any,
    ) -> Edge:
        """Add an edge."""
        pass
    
    @abstractmethod
    def get_node(self, id: NodeId) -> Optional[Node]:
        """Get a node by ID."""
        pass
    
    @abstractmethod
    def get_edge(self, source: NodeId, target: NodeId) -> Optional[Edge]:
        """Get an edge."""
        pass
    
    @abstractmethod
    def neighbors(
        self,
        id: NodeId,
        direction: str = "out",
        relation: Optional[str] = None,
    ) -> List[Node]:
        """Get neighboring nodes."""
        pass
    
    @abstractmethod
    def remove_node(self, id: NodeId) -> bool:
        """Remove a node."""
        pass
    
    @abstractmethod
    def remove_edge(self, source: NodeId, target: NodeId) -> bool:
        """Remove an edge."""
        pass


class KnowledgeGraph(Graph):
    """
    In-memory knowledge graph.
    """
    
    def __init__(self):
        self._nodes: Dict[NodeId, Node] = {}
        self._edges: Dict[EdgeId, Edge] = {}
        self._adjacency: Dict[NodeId, Dict[NodeId, EdgeId]] = defaultdict(dict)  # out edges
        self._reverse_adjacency: Dict[NodeId, Dict[NodeId, EdgeId]] = defaultdict(dict)  # in edges
    
    @property
    def node_count(self) -> int:
        return len(self._nodes)
    
    @property
    def edge_count(self) -> int:
        return len(self._edges)
    
    def add_node(
        self,
        id: NodeId,
        type: str = "entity",
        **properties: Any,
    ) -> Node:
        """Add or update a node."""
        if id in self._nodes:
            node = self._nodes[id]
            node.type = type
            node.properties.update(properties)
        else:
            node = Node(id=id, type=type, properties=properties)
            self._nodes[id] = node
        
        return node
    
    def add_edge(
        self,
        source: NodeId,
        target: NodeId,
        relation: str = "relates_to",
        weight: float = 1.0,
        directed: bool = True,
        **properties: Any,
    ) -> Edge:
        """Add an edge."""
        # Ensure nodes exist
        if source not in self._nodes:
            self.add_node(source)
        if target not in self._nodes:
            self.add_node(target)
        
        edge_id = f"{source}-{relation}-{target}"
        
        edge = Edge(
            id=edge_id,
            source=source,
            target=target,
            relation=relation,
            weight=weight,
            directed=directed,
            properties=properties,
        )
        
        self._edges[edge_id] = edge
        self._adjacency[source][target] = edge_id
        self._reverse_adjacency[target][source] = edge_id
        
        # For undirected edges, add reverse
        if not directed:
            rev_id = f"{target}-{relation}-{source}"
            rev_edge = Edge(
                id=rev_id,
                source=target,
                target=source,
                relation=relation,
                weight=weight,
                directed=directed,
                properties=properties,
            )
            self._edges[rev_id] = rev_edge
            self._adjacency[target][source] = rev_id
            self._reverse_adjacency[source][target] = rev_id
        
        return edge
    
    def get_node(self, id: NodeId) -> Optional[Node]:
        """Get a node."""
        return self._nodes.get(id)
    
    def get_edge(self, source: NodeId, target: NodeId) -> Optional[Edge]:
        """Get an edge."""
        edge_id = self._adjacency.get(source, {}).get(target)
        if edge_id:
            return self._edges.get(edge_id)
        return None
    
    def get_edges_between(
        self,
        source: NodeId,
        target: NodeId,
    ) -> List[Edge]:
        """Get all edges between two nodes."""
        edges = []
        
        # Check forward
        if source in self._adjacency and target in self._adjacency[source]:
            edges.append(self._edges[self._adjacency[source][target]])
        
        # Check reverse
        if target in self._adjacency and source in self._adjacency[target]:
            edges.append(self._edges[self._adjacency[target][source]])
        
        return edges
    
    def neighbors(
        self,
        id: NodeId,
        direction: str = "out",
        relation: Optional[str] = None,
    ) -> List[Node]:
        """Get neighboring nodes."""
        if id not in self._nodes:
            return []
        
        neighbors = []
        
        if direction in ("out", "both"):
            for target_id, edge_id in self._adjacency.get(id, {}).items():
                edge = self._edges[edge_id]
                if relation is None or edge.relation == relation:
                    neighbors.append(self._nodes[target_id])
        
        if direction in ("in", "both"):
            for source_id, edge_id in self._reverse_adjacency.get(id, {}).items():
                edge = self._edges[edge_id]
                if relation is None or edge.relation == relation:
                    if self._nodes[source_id] not in neighbors:
                        neighbors.append(self._nodes[source_id])
        
        return neighbors
    
    def edges_of(
        self,
        id: NodeId,
        direction: str = "out",
        relation: Optional[str] = None,
    ) -> List[Edge]:
        """Get edges connected to a node."""
        if id not in self._nodes:
            return []
        
        edges = []
        
        if direction in ("out", "both"):
            for edge_id in self._adjacency.get(id, {}).values():
                edge = self._edges[edge_id]
                if relation is None or edge.relation == relation:
                    edges.append(edge)
        
        if direction in ("in", "both"):
            for edge_id in self._reverse_adjacency.get(id, {}).values():
                edge = self._edges[edge_id]
                if relation is None or edge.relation == relation:
                    if edge not in edges:
                        edges.append(edge)
        
        return edges
    
    def remove_node(self, id: NodeId) -> bool:
        """Remove a node and its edges."""
        if id not in self._nodes:
            return False
        
        # Remove edges
        for target_id in list(self._adjacency.get(id, {}).keys()):
            self.remove_edge(id, target_id)
        
        for source_id in list(self._reverse_adjacency.get(id, {}).keys()):
            self.remove_edge(source_id, id)
        
        del self._nodes[id]
        return True
    
    def remove_edge(self, source: NodeId, target: NodeId) -> bool:
        """Remove an edge."""
        edge_id = self._adjacency.get(source, {}).get(target)
        
        if not edge_id:
            return False
        
        del self._edges[edge_id]
        del self._adjacency[source][target]
        del self._reverse_adjacency[target][source]
        
        return True
    
    def shortest_path(
        self,
        source: NodeId,
        target: NodeId,
        relation: Optional[str] = None,
    ) -> Optional[Path]:
        """Find shortest path using BFS."""
        if source not in self._nodes or target not in self._nodes:
            return None
        
        if source == target:
            return Path(nodes=[self._nodes[source]], edges=[])
        
        # BFS
        visited = {source}
        queue = deque([(source, [source], [])])
        
        while queue:
            current, node_path, edge_path = queue.popleft()
            
            for neighbor in self.neighbors(current, direction="out", relation=relation):
                if neighbor.id in visited:
                    continue
                
                edge = self.get_edge(current, neighbor.id)
                new_node_path = node_path + [neighbor.id]
                new_edge_path = edge_path + [edge]
                
                if neighbor.id == target:
                    return Path(
                        nodes=[self._nodes[n] for n in new_node_path],
                        edges=new_edge_path,
                    )
                
                visited.add(neighbor.id)
                queue.append((neighbor.id, new_node_path, new_edge_path))
        
        return None
    
    def all_paths(
        self,
        source: NodeId,
        target: NodeId,
        max_depth: int = 5,
    ) -> List[Path]:
        """Find all paths between nodes."""
        if source not in self._nodes or target not in self._nodes:
            return []
        
        paths = []
        
        def dfs(current: NodeId, path: List[NodeId], edges: List[Edge], depth: int):
            if depth > max_depth:
                return
            
            if current == target:
                paths.append(Path(
                    nodes=[self._nodes[n] for n in path],
                    edges=edges,
                ))
                return
            
            for neighbor in self.neighbors(current, direction="out"):
                if neighbor.id not in path:
                    edge = self.get_edge(current, neighbor.id)
                    dfs(
                        neighbor.id,
                        path + [neighbor.id],
                        edges + [edge],
                        depth + 1,
                    )
        
        dfs(source, [source], [], 0)
        return paths
    
    def subgraph(
        self,
        node_ids: Set[NodeId],
        include_edges: bool = True,
    ) -> Subgraph:
        """Extract a subgraph."""
        nodes = {self._nodes[id] for id in node_ids if id in self._nodes}
        edges = set()
        
        if include_edges:
            for edge in self._edges.values():
                if edge.source in node_ids and edge.target in node_ids:
                    edges.add(edge)
        
        return Subgraph(nodes=nodes, edges=edges)
    
    def neighborhood(
        self,
        id: NodeId,
        hops: int = 1,
        relation: Optional[str] = None,
    ) -> Subgraph:
        """Get k-hop neighborhood."""
        if id not in self._nodes:
            return Subgraph(nodes=set(), edges=set())
        
        node_ids = {id}
        frontier = {id}
        
        for _ in range(hops):
            new_frontier = set()
            for node_id in frontier:
                for neighbor in self.neighbors(node_id, direction="both", relation=relation):
                    if neighbor.id not in node_ids:
                        new_frontier.add(neighbor.id)
                        node_ids.add(neighbor.id)
            frontier = new_frontier
        
        return self.subgraph(node_ids)
    
    def find_nodes(
        self,
        type: Optional[str] = None,
        **properties: Any,
    ) -> List[Node]:
        """Find nodes by type and properties."""
        results = []
        
        for node in self._nodes.values():
            if type and node.type != type:
                continue
            
            match = True
            for key, value in properties.items():
                if node.properties.get(key) != value:
                    match = False
                    break
            
            if match:
                results.append(node)
        
        return results
    
    def find_edges(
        self,
        relation: Optional[str] = None,
        **properties: Any,
    ) -> List[Edge]:
        """Find edges by relation and properties."""
        results = []
        
        for edge in self._edges.values():
            if relation and edge.relation != relation:
                continue
            
            match = True
            for key, value in properties.items():
                if edge.properties.get(key) != value:
                    match = False
                    break
            
            if match:
                results.append(edge)
        
        return results
    
    def degree(self, id: NodeId, direction: str = "both") -> int:
        """Get node degree."""
        count = 0
        
        if direction in ("out", "both"):
            count += len(self._adjacency.get(id, {}))
        
        if direction in ("in", "both"):
            count += len(self._reverse_adjacency.get(id, {}))
        
        return count
    
    def pagerank(
        self,
        damping: float = 0.85,
        iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> Dict[NodeId, float]:
        """Calculate PageRank scores."""
        n = len(self._nodes)
        if n == 0:
            return {}
        
        # Initialize
        scores = {id: 1.0 / n for id in self._nodes}
        
        for _ in range(iterations):
            new_scores = {}
            diff = 0
            
            for node_id in self._nodes:
                rank = (1 - damping) / n
                
                # Sum contributions from incoming edges
                for source_id in self._reverse_adjacency.get(node_id, {}):
                    out_degree = len(self._adjacency.get(source_id, {}))
                    if out_degree > 0:
                        rank += damping * scores[source_id] / out_degree
                
                new_scores[node_id] = rank
                diff += abs(rank - scores[node_id])
            
            scores = new_scores
            
            if diff < tolerance:
                break
        
        return scores
    
    def to_dict(self) -> Dict[str, Any]:
        """Export graph to dictionary."""
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeGraph':
        """Import graph from dictionary."""
        graph = cls()
        
        for node_data in data.get("nodes", []):
            graph.add_node(
                node_data["id"],
                type=node_data.get("type", "entity"),
                **node_data.get("properties", {}),
            )
        
        for edge_data in data.get("edges", []):
            graph.add_edge(
                edge_data["source"],
                edge_data["target"],
                relation=edge_data.get("relation", "relates_to"),
                weight=edge_data.get("weight", 1.0),
                **edge_data.get("properties", {}),
            )
        
        return graph
    
    def clear(self) -> None:
        """Clear the graph."""
        self._nodes.clear()
        self._edges.clear()
        self._adjacency.clear()
        self._reverse_adjacency.clear()


class EntityExtractor:
    """Extract entities and relations from text."""
    
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        model: Optional[str] = None,
    ):
        self._client = llm_client
        self._model = model
    
    async def extract(
        self,
        text: str,
        entity_types: Optional[List[str]] = None,
        relation_types: Optional[List[str]] = None,
    ) -> Tuple[List[Node], List[Edge]]:
        """Extract entities and relations from text."""
        if not self._client:
            return [], []
        
        # Build prompt
        prompt = f"""Extract entities and relationships from the following text.

Text: {text}

Return JSON with:
- entities: list of {{id, type, properties}}
- relations: list of {{source, target, relation, properties}}

Entity types: {entity_types or ["person", "organization", "location", "concept"]}
Relation types: {relation_types or ["relates_to", "works_for", "located_in", "is_a"]}

JSON:"""
        
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        
        try:
            content = response.choices[0].message.content
            # Parse JSON
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                
                nodes = [
                    Node(
                        id=e["id"],
                        type=e.get("type", "entity"),
                        properties=e.get("properties", {}),
                    )
                    for e in data.get("entities", [])
                ]
                
                edges = [
                    Edge(
                        id=f"{r['source']}-{r['relation']}-{r['target']}",
                        source=r["source"],
                        target=r["target"],
                        relation=r.get("relation", "relates_to"),
                        properties=r.get("properties", {}),
                    )
                    for r in data.get("relations", [])
                ]
                
                return nodes, edges
        except Exception as e:
            logger.error(f"Failed to parse extraction: {e}")
        
        return [], []


def create_graph() -> KnowledgeGraph:
    """Factory function to create a knowledge graph."""
    return KnowledgeGraph()


__all__ = [
    # Exceptions
    "GraphError",
    "NodeNotFoundError",
    "EdgeNotFoundError",
    "CycleDetectedError",
    # Enums
    "NodeType",
    "EdgeType",
    # Data classes
    "Node",
    "Edge",
    "Path",
    "Subgraph",
    # Graph
    "Graph",
    "KnowledgeGraph",
    # Extraction
    "EntityExtractor",
    # Factory
    "create_graph",
    # Type aliases
    "NodeId",
    "EdgeId",
]
