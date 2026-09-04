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
import re
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


_CLAUSE_RE = re.compile(r"\b(MATCH|WHERE|RETURN|ORDER\s+BY|SKIP|LIMIT)\b", re.IGNORECASE)
_NODE_RE = re.compile(r"\(\s*(\w+)?\s*((?::\s*\w+\s*)*)\s*(\{[^{}]*\})?\s*\)")
_EDGE_RE = re.compile(
    r"(<-|-)\s*(?:\[\s*(\w+)?\s*(?::\s*(\w+(?:\s*\|\s*\w+)*))?\s*(\{[^{}]*\})?\s*\])?\s*(->|-)"
)
_PROP_RE = re.compile(r"\s*(\w+)\s*:\s*")
_COND_RE = re.compile(
    r"^(\w+)(?:\.(\w+))?\s*"
    r"(IS\s+NOT\s+NULL|IS\s+NULL|STARTS\s+WITH|ENDS\s+WITH|CONTAINS|IN|<>|!=|<=|>=|=|<|>)"
    r"\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_LABEL_COND_RE = re.compile(r"^(\w+)\s*:\s*(\w+)$")
_RETURN_ITEM_RE = re.compile(
    r"^(?:(count)\s*\(\s*(\*|\w+)\s*\)|(\w+)(?:\.(\w+))?)(?:\s+AS\s+(\w+))?$",
    re.IGNORECASE,
)
_STRING_RE = re.compile(r"""^(?:'((?:\\.|[^'\\])*)'|"((?:\\.|[^"\\])*)")$""")


class _CypherSubset:
    """
    Evaluator for the Cypher subset understood by :class:`InMemoryGraphBackend`.

    Supported grammar (case-insensitive keywords)::

        MATCH pattern [, pattern ...]
        [WHERE cond [AND cond ...]]
        [RETURN [DISTINCT] item [, item ...]
         [ORDER BY expr [ASC|DESC] [, ...]] [SKIP n] [LIMIT n]]

    pattern  := (var[:Label ...][{k: v, ...}]) [ -[var[:TYPE|TYPE2][{...}]]-> | <-[...]- | -[...]- (…) ]...
    cond     := var.prop OP value | var.prop IS [NOT] NULL | var:Label
    OP       := = | <> | != | < | <= | > | >= | CONTAINS | STARTS WITH | ENDS WITH | IN
    item     := var | var.prop | count(*) | count(var) [AS alias]
    value    := 'string' | number | true | false | null | $param | [value, ...]

    Anything outside this grammar raises :class:`QueryError`.
    """

    def __init__(
        self,
        nodes: Dict[str, Node],
        edges: Dict[str, Edge],
        outgoing: Dict[str, List[str]],
        incoming: Dict[str, List[str]],
    ):
        self._nodes = nodes
        self._edges = edges
        self._outgoing = outgoing
        self._incoming = incoming

    # -- entry point ---------------------------------------------------------

    def run(self, query: str, params: Dict[str, Any]) -> QueryResult:
        clauses = self._split_clauses(query)
        if "MATCH" not in clauses:
            raise QueryError("Query must start with MATCH")

        bindings = self._match(clauses["MATCH"], params)
        if "WHERE" in clauses:
            conds = self._parse_where(clauses["WHERE"], params)
            bindings = [b for b in bindings if all(c(b) for c in conds)]

        if "RETURN" not in clauses:
            records = [dict(b) for b in bindings]
            columns = sorted({k for b in bindings for k in b})
            return QueryResult(records=records, columns=columns, count=len(records))

        records, columns, row_bindings = self._project(clauses["RETURN"], bindings, params)

        if "ORDER BY" in clauses:
            records = self._order(records, clauses["ORDER BY"], row_bindings)
        if "SKIP" in clauses:
            records = records[self._int_clause("SKIP", clauses["SKIP"], params):]
        if "LIMIT" in clauses:
            records = records[: self._int_clause("LIMIT", clauses["LIMIT"], params)]

        return QueryResult(records=records, columns=columns, count=len(records))

    # -- clause splitting ----------------------------------------------------

    @staticmethod
    def _split_clauses(query: str) -> Dict[str, str]:
        text = query.strip().rstrip(";")
        if not text:
            raise QueryError("Empty query")
        hits = list(_CLAUSE_RE.finditer(text))
        if not hits or hits[0].start() != 0:
            raise QueryError(f"Unsupported query start: {text[:40]!r}")
        order = ["MATCH", "WHERE", "RETURN", "ORDER BY", "SKIP", "LIMIT"]
        clauses: Dict[str, str] = {}
        last_idx = -1
        for i, hit in enumerate(hits):
            name = re.sub(r"\s+", " ", hit.group(1).upper())
            idx = order.index(name)
            if idx <= last_idx:
                raise QueryError(f"Unexpected or repeated clause: {name}")
            last_idx = idx
            end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
            clauses[name] = text[hit.end():end].strip()
        if "WHERE" in clauses and "RETURN" not in clauses and any(
            k in clauses for k in ("ORDER BY", "SKIP", "LIMIT")
        ):
            raise QueryError("ORDER BY/SKIP/LIMIT require a RETURN clause")
        return clauses

    # -- value parsing -------------------------------------------------------

    def _value(self, token: str, params: Dict[str, Any]) -> Any:
        tok = token.strip()
        if not tok:
            raise QueryError("Missing value")
        if tok.startswith("$"):
            name = tok[1:]
            if name not in params:
                raise QueryError(f"Missing query parameter: ${name}")
            return params[name]
        m = _STRING_RE.match(tok)
        if m:
            raw = m.group(1) if m.group(1) is not None else m.group(2)
            return re.sub(r"\\(.)", r"\1", raw)
        low = tok.lower()
        if low == "true":
            return True
        if low == "false":
            return False
        if low == "null":
            return None
        if tok.startswith("[") and tok.endswith("]"):
            inner = tok[1:-1].strip()
            return [self._value(p, params) for p in self._split_top(inner)] if inner else []
        try:
            return int(tok)
        except ValueError:
            pass
        try:
            return float(tok)
        except ValueError:
            raise QueryError(f"Unsupported literal: {tok!r}") from None

    @staticmethod
    def _split_top(text: str) -> List[str]:
        """Split on commas that are not nested in (), [], {} or quotes."""
        parts: List[str] = []
        depth = 0
        quote: Optional[str] = None
        buf: List[str] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if quote:
                buf.append(ch)
                if ch == "\\" and i + 1 < len(text):
                    buf.append(text[i + 1])
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "'\"":
                quote = ch
                buf.append(ch)
            elif ch in "([{":
                depth += 1
                buf.append(ch)
            elif ch in ")]}":
                depth -= 1
                buf.append(ch)
            elif ch == "," and depth == 0:
                parts.append("".join(buf).strip())
                buf = []
            else:
                buf.append(ch)
            i += 1
        tail = "".join(buf).strip()
        if tail or parts:
            parts.append(tail)
        return [p for p in parts if p]

    def _props(self, text: Optional[str], params: Dict[str, Any]) -> Dict[str, Any]:
        if not text:
            return {}
        inner = text.strip()[1:-1].strip()
        result: Dict[str, Any] = {}
        for item in self._split_top(inner):
            m = _PROP_RE.match(item)
            if not m:
                raise QueryError(f"Invalid property map entry: {item!r}")
            result[m.group(1)] = self._value(item[m.end():], params)
        return result

    # -- MATCH ---------------------------------------------------------------

    def _parse_pattern(self, text: str, params: Dict[str, Any]) -> List[Any]:
        pos = 0
        text = text.strip()
        m = _NODE_RE.match(text, pos)
        if not m:
            raise QueryError(f"Invalid node pattern: {text[pos:pos + 40]!r}")
        steps: List[Any] = [self._node_spec(m, params)]
        pos = m.end()
        while pos < len(text):
            if text[pos].isspace():
                pos += 1
                continue
            em = _EDGE_RE.match(text, pos)
            if not em:
                raise QueryError(f"Invalid relationship pattern: {text[pos:pos + 40]!r}")
            left, var, types, props, right = em.groups()
            if left == "<-" and right == "->":
                raise QueryError("Relationship cannot point both ways")
            direction = (
                TraversalDirection.OUTGOING if right == "->"
                else TraversalDirection.INCOMING if left == "<-"
                else TraversalDirection.BOTH
            )
            type_set = {t.strip() for t in types.split("|")} if types else None
            pos = em.end()
            nm = _NODE_RE.match(text, pos)
            if not nm:
                raise QueryError(f"Relationship must end in a node: {text[pos:pos + 40]!r}")
            steps.append((var, type_set, self._props(props, params), direction))
            steps.append(self._node_spec(nm, params))
            pos = nm.end()
        return steps

    def _node_spec(self, m: "re.Match[str]", params: Dict[str, Any]) -> Tuple[Optional[str], Set[str], Dict[str, Any]]:
        var, labels, props = m.groups()
        label_set = {l.strip() for l in labels.split(":") if l.strip()} if labels else set()
        return var, label_set, self._props(props, params)

    @staticmethod
    def _element_matches(element: Any, labels_or_types: Optional[Set[str]], props: Dict[str, Any]) -> bool:
        if isinstance(element, Node):
            if labels_or_types and not labels_or_types.issubset(element.labels):
                return False
        elif labels_or_types and element.type not in labels_or_types:
            return False
        return all(element.properties.get(k) == v for k, v in props.items())

    @staticmethod
    def _bind(binding: Dict[str, Any], var: Optional[str], element: Any) -> Optional[Dict[str, Any]]:
        if var is None:
            return binding
        existing = binding.get(var)
        if existing is not None and existing is not element:
            return None
        if existing is None:
            binding = dict(binding)
            binding[var] = element
        return binding

    def _match(self, text: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not text:
            raise QueryError("MATCH requires a pattern")
        bindings: List[Dict[str, Any]] = [{}]
        for pattern in self._split_top(text):
            steps = self._parse_pattern(pattern, params)
            bindings = self._match_pattern(steps, bindings)
            if not bindings:
                break
        return bindings

    def _match_pattern(self, steps: List[Any], bindings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        var0, labels0, props0 = steps[0]
        results: List[Tuple[Dict[str, Any], Node, Set[str]]] = []
        for binding in bindings:
            candidates = [binding[var0]] if var0 in binding else self._nodes.values()
            for node in candidates:
                if not isinstance(node, Node) or not self._element_matches(node, labels0, props0):
                    continue
                b = self._bind(binding, var0, node)
                if b is not None:
                    results.append((b, node, set()))

        for i in range(1, len(steps), 2):
            evar, etypes, eprops, direction = steps[i]
            nvar, nlabels, nprops = steps[i + 1]
            next_results: List[Tuple[Dict[str, Any], Node, Set[str]]] = []
            for binding, current, used in results:
                for edge, neighbor in self._expand(current.id, direction):
                    if edge.id in used or not self._element_matches(edge, etypes, eprops):
                        continue
                    if not self._element_matches(neighbor, nlabels, nprops):
                        continue
                    b = self._bind(binding, evar, edge)
                    if b is None:
                        continue
                    b = self._bind(b, nvar, neighbor)
                    if b is None:
                        continue
                    next_results.append((b, neighbor, used | {edge.id}))
            results = next_results
            if not results:
                break
        return [b for b, _, _ in results]

    def _expand(self, node_id: str, direction: TraversalDirection) -> Iterator[Tuple[Edge, Node]]:
        if direction in (TraversalDirection.OUTGOING, TraversalDirection.BOTH):
            for edge_id in self._outgoing.get(node_id, []):
                edge = self._edges[edge_id]
                target = self._nodes.get(edge.target_id)
                if target is not None:
                    yield edge, target
        if direction in (TraversalDirection.INCOMING, TraversalDirection.BOTH):
            for edge_id in self._incoming.get(node_id, []):
                edge = self._edges[edge_id]
                source = self._nodes.get(edge.source_id)
                if source is not None:
                    yield edge, source

    # -- WHERE ---------------------------------------------------------------

    @staticmethod
    def _resolve(binding: Dict[str, Any], var: str, prop: Optional[str]) -> Any:
        if var not in binding:
            raise QueryError(f"Variable not defined: {var}")
        element = binding[var]
        if prop is None:
            return element
        if prop in element.properties:
            return element.properties[prop]
        if prop == "id":
            return element.id
        return None

    def _parse_where(self, text: str, params: Dict[str, Any]) -> List[Callable[[Dict[str, Any]], bool]]:
        if not text:
            raise QueryError("WHERE requires a condition")
        if re.search(r"\b(OR|NOT|XOR)\b", text, re.IGNORECASE):
            raise QueryError("Only AND-joined conditions are supported in WHERE")
        conds: List[Callable[[Dict[str, Any]], bool]] = []
        for raw in re.split(r"\s+AND\s+", text.strip(), flags=re.IGNORECASE):
            raw = raw.strip()
            lm = _LABEL_COND_RE.match(raw)
            if lm:
                var, label = lm.groups()
                conds.append(lambda b, v=var, l=label: isinstance(b.get(v), Node) and l in b[v].labels)
                continue
            cm = _COND_RE.match(raw)
            if not cm:
                raise QueryError(f"Unsupported WHERE condition: {raw!r}")
            var, prop, op, rhs = cm.groups()
            op = re.sub(r"\s+", " ", op.upper())
            if op in ("IS NULL", "IS NOT NULL"):
                if rhs.strip():
                    raise QueryError(f"Unexpected text after {op}: {rhs!r}")
                want_null = op == "IS NULL"
                conds.append(lambda b, v=var, p=prop, w=want_null: (self._resolve(b, v, p) is None) == w)
                continue
            value = self._value(rhs, params)
            conds.append(self._comparison(var, prop, op, value))
        return conds

    def _comparison(self, var: str, prop: Optional[str], op: str, value: Any) -> Callable[[Dict[str, Any]], bool]:
        def check(binding: Dict[str, Any]) -> bool:
            left = self._resolve(binding, var, prop)
            try:
                if op == "=":
                    return left == value
                if op in ("<>", "!="):
                    return left != value
                if left is None:
                    return False
                if op == "<":
                    return left < value
                if op == "<=":
                    return left <= value
                if op == ">":
                    return left > value
                if op == ">=":
                    return left >= value
                if op == "CONTAINS":
                    return str(value) in str(left)
                if op == "STARTS WITH":
                    return str(left).startswith(str(value))
                if op == "ENDS WITH":
                    return str(left).endswith(str(value))
                if op == "IN":
                    return left in value
            except TypeError:
                return False
            raise QueryError(f"Unsupported operator: {op}")
        return check

    # -- RETURN / ORDER BY ---------------------------------------------------

    def _project(
        self,
        text: str,
        bindings: List[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
        text = text.strip()
        if not text:
            raise QueryError("RETURN requires at least one item")
        distinct = False
        if re.match(r"DISTINCT\b", text, re.IGNORECASE):
            distinct = True
            text = text[len("DISTINCT"):].strip()

        if text == "*":
            columns = sorted({k for b in bindings for k in b})
            items = [(c, None, c, False) for c in columns]
        else:
            items = []
            for raw in self._split_top(text):
                m = _RETURN_ITEM_RE.match(raw.strip())
                if not m:
                    raise QueryError(f"Unsupported RETURN item: {raw!r}")
                count_kw, count_arg, var, prop, alias = m.groups()
                if count_kw:
                    items.append((count_arg, None, alias or raw.strip(), True))
                else:
                    items.append((var, prop, alias or raw.strip(), False))
            columns = [name for _, _, name, _ in items]

        aggregates = [it for it in items if it[3]]
        if aggregates:
            if len(aggregates) != len(items):
                raise QueryError("Mixing aggregated and non-aggregated RETURN items is not supported")
            record: Dict[str, Any] = {}
            for arg, _, name, _ in items:
                if arg == "*":
                    record[name] = len(bindings)
                else:
                    record[name] = sum(1 for b in bindings if b.get(arg) is not None)
            return [record], columns, [{}]

        records: List[Dict[str, Any]] = []
        row_bindings: List[Dict[str, Any]] = []
        seen: Set[Tuple[Any, ...]] = set()
        for binding in bindings:
            record = {name: self._resolve(binding, var, prop) for var, prop, name, _ in items}
            if distinct:
                key = tuple(self._hashable(record[c]) for c in columns)
                if key in seen:
                    continue
                seen.add(key)
            records.append(record)
            row_bindings.append(binding)
        return records, columns, row_bindings

    @staticmethod
    def _hashable(value: Any) -> Any:
        if isinstance(value, (Node, Edge)):
            return ("__el__", value.id)
        try:
            hash(value)
            return value
        except TypeError:
            return repr(value)

    def _order(
        self,
        records: List[Dict[str, Any]],
        text: str,
        bindings: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        keys: List[Tuple[Callable[[int], Any], bool]] = []
        for raw in self._split_top(text):
            m = re.match(r"^(\w+)(?:\.(\w+))?(?:\s+(ASC|DESC))?$", raw.strip(), re.IGNORECASE)
            if not m:
                raise QueryError(f"Unsupported ORDER BY item: {raw!r}")
            var, prop, direction = m.groups()
            if prop is None and records and var in records[0]:
                getter = lambda i, v=var: records[i][v]
            else:
                getter = lambda i, v=var, p=prop: self._resolve(bindings[i], v, p)
            keys.append((getter, (direction or "ASC").upper() == "DESC"))

        indices = list(range(len(records)))
        try:
            for getter, desc in reversed(keys):
                if desc:
                    indices.sort(key=lambda i, g=getter: (g(i) is not None, g(i)), reverse=True)
                else:
                    indices.sort(key=lambda i, g=getter: (g(i) is None, g(i)))
        except TypeError as exc:
            raise QueryError(f"ORDER BY values are not comparable: {exc}") from exc
        return [records[i] for i in indices]

    def _int_clause(self, name: str, text: str, params: Dict[str, Any]) -> int:
        value = self._value(text, params)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise QueryError(f"{name} requires a non-negative integer")
        return value


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
        # Cypher subset: MATCH [WHERE] [RETURN [ORDER BY] [SKIP] [LIMIT]]; see _CypherSubset.
        return _CypherSubset(self._nodes, self._edges, self._outgoing, self._incoming).run(
            query, params or {}
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
