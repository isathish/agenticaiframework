"""
Enterprise Workflow DSL - Declarative workflow definition.

Provides a domain-specific language for defining
complex agent workflows declaratively.

Features:
- YAML/JSON workflow definitions
- Visual workflow builder
- Conditional branching
- Loop support
- Human-in-the-loop
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
import uuid
import json

logger = logging.getLogger(__name__)


# =============================================================================
# DSL Types
# =============================================================================

class NodeType(Enum):
    """Type of workflow node."""
    START = "start"
    END = "end"
    AGENT = "agent"
    TOOL = "tool"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    HUMAN = "human"
    WAIT = "wait"
    TRANSFORM = "transform"
    SUBWORKFLOW = "subworkflow"


class ConditionOperator(Enum):
    """Operators for conditions."""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER = "gt"
    LESS = "lt"
    CONTAINS = "contains"
    MATCHES = "matches"  # Regex
    EXISTS = "exists"
    TRUE = "true"
    FALSE = "false"


@dataclass
class Condition:
    """A condition for branching."""
    left: str  # Variable reference like "$.output.status"
    operator: ConditionOperator
    right: Any = None
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate the condition against context."""
        left_value = self._resolve(self.left, context)
        right_value = self.right
        
        if self.operator == ConditionOperator.EQUALS:
            return left_value == right_value
        elif self.operator == ConditionOperator.NOT_EQUALS:
            return left_value != right_value
        elif self.operator == ConditionOperator.GREATER:
            return left_value > right_value
        elif self.operator == ConditionOperator.LESS:
            return left_value < right_value
        elif self.operator == ConditionOperator.CONTAINS:
            return right_value in left_value
        elif self.operator == ConditionOperator.MATCHES:
            return bool(re.match(right_value, str(left_value)))
        elif self.operator == ConditionOperator.EXISTS:
            return left_value is not None
        elif self.operator == ConditionOperator.TRUE:
            return bool(left_value)
        elif self.operator == ConditionOperator.FALSE:
            return not bool(left_value)
        
        return False
    
    def _resolve(self, path: str, context: Dict) -> Any:
        """Resolve a path like $.output.status to a value."""
        if not path.startswith("$"):
            return path
        
        parts = path[2:].split(".")  # Remove "$." prefix
        value = context
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return None
        
        return value


# =============================================================================
# Workflow Nodes
# =============================================================================

@dataclass
class WorkflowNode:
    """Base workflow node."""
    id: str
    name: str
    type: NodeType
    
    # Connections
    next: List[str] = field(default_factory=list)
    
    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    description: str = ""
    timeout_seconds: Optional[float] = None
    retry_count: int = 0


@dataclass
class AgentNode(WorkflowNode):
    """Node that executes an agent."""
    agent_name: str = ""
    prompt_template: str = ""
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_mapping: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        self.type = NodeType.AGENT


@dataclass
class ToolNode(WorkflowNode):
    """Node that calls a tool."""
    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.type = NodeType.TOOL


@dataclass
class ConditionNode(WorkflowNode):
    """Node for conditional branching."""
    condition: Condition = None
    true_next: str = ""
    false_next: str = ""
    
    def __post_init__(self):
        self.type = NodeType.CONDITION


@dataclass
class LoopNode(WorkflowNode):
    """Node for loops."""
    items_path: str = ""  # Path to items to iterate
    item_variable: str = "item"  # Variable name for current item
    body_nodes: List[str] = field(default_factory=list)
    max_iterations: int = 100
    
    def __post_init__(self):
        self.type = NodeType.LOOP


@dataclass
class ParallelNode(WorkflowNode):
    """Node for parallel execution."""
    branches: List[List[str]] = field(default_factory=list)
    wait_all: bool = True
    
    def __post_init__(self):
        self.type = NodeType.PARALLEL


@dataclass
class HumanNode(WorkflowNode):
    """Node requiring human input."""
    prompt: str = ""
    options: List[str] = field(default_factory=list)
    timeout_action: str = "skip"  # skip, fail, default
    default_value: Any = None
    
    def __post_init__(self):
        self.type = NodeType.HUMAN


@dataclass
class TransformNode(WorkflowNode):
    """Node for data transformation."""
    transform_type: str = "jq"  # jq, python, jinja
    expression: str = ""
    
    def __post_init__(self):
        self.type = NodeType.TRANSFORM


# =============================================================================
# Workflow Definition
# =============================================================================

@dataclass
class WorkflowDefinition:
    """Complete workflow definition."""
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    
    # Nodes
    nodes: Dict[str, WorkflowNode] = field(default_factory=dict)
    
    # Entry/exit
    start_node: str = ""
    end_nodes: List[str] = field(default_factory=list)
    
    # Variables
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, str] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_node(self, node: WorkflowNode) -> "WorkflowDefinition":
        """Add a node to the workflow."""
        self.nodes[node.id] = node
        return self
    
    def connect(self, from_id: str, to_id: str) -> "WorkflowDefinition":
        """Connect two nodes."""
        if from_id in self.nodes:
            self.nodes[from_id].next.append(to_id)
        return self
    
    def validate(self) -> List[str]:
        """Validate the workflow. Returns list of errors."""
        errors = []
        
        # Check start node
        if not self.start_node:
            errors.append("No start node defined")
        elif self.start_node not in self.nodes:
            errors.append(f"Start node '{self.start_node}' not found")
        
        # Check all connections
        for node_id, node in self.nodes.items():
            for next_id in node.next:
                if next_id not in self.nodes:
                    errors.append(f"Node '{node_id}' connects to unknown node '{next_id}'")
        
        # Check for orphan nodes (except start)
        reachable = self._find_reachable()
        for node_id in self.nodes:
            if node_id != self.start_node and node_id not in reachable:
                errors.append(f"Node '{node_id}' is not reachable")
        
        return errors
    
    def _find_reachable(self) -> set:
        """Find all reachable nodes from start."""
        reachable = set()
        to_visit = [self.start_node] if self.start_node else []
        
        while to_visit:
            node_id = to_visit.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            
            node = self.nodes.get(node_id)
            if node:
                to_visit.extend(node.next)
        
        return reachable


# =============================================================================
# Workflow Builder
# =============================================================================

class WorkflowBuilder:
    """
    Fluent builder for workflows.
    
    Usage:
        >>> workflow = (
        ...     WorkflowBuilder("my-workflow")
        ...     .start()
        ...     .agent("analyzer", prompt="Analyze: {{input}}")
        ...     .condition("$.output.needs_review")
        ...         .on_true("review")
        ...         .on_false("complete")
        ...     .agent("review", id="review", prompt="Review: {{analysis}}")
        ...     .end(id="complete")
        ...     .build()
        ... )
    """
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self._name = name
        self._version = version
        self._nodes: Dict[str, WorkflowNode] = {}
        self._current_id: Optional[str] = None
        self._start_id: Optional[str] = None
        self._end_ids: List[str] = []
        self._pending_connections: List[tuple] = []
    
    def _generate_id(self, prefix: str = "node") -> str:
        return f"{prefix}_{len(self._nodes) + 1}"
    
    def start(self, id: str = None) -> "WorkflowBuilder":
        """Add start node."""
        node_id = id or self._generate_id("start")
        self._nodes[node_id] = WorkflowNode(
            id=node_id,
            name="Start",
            type=NodeType.START,
        )
        self._start_id = node_id
        self._current_id = node_id
        return self
    
    def end(self, id: str = None) -> "WorkflowBuilder":
        """Add end node."""
        node_id = id or self._generate_id("end")
        self._nodes[node_id] = WorkflowNode(
            id=node_id,
            name="End",
            type=NodeType.END,
        )
        self._end_ids.append(node_id)
        
        if self._current_id:
            self._connect(self._current_id, node_id)
        
        self._current_id = node_id
        return self
    
    def agent(
        self,
        name: str,
        id: str = None,
        prompt: str = "",
        input_mapping: Dict[str, str] = None,
        output_mapping: Dict[str, str] = None,
        **config,
    ) -> "WorkflowBuilder":
        """Add an agent node."""
        node_id = id or self._generate_id("agent")
        node = AgentNode(
            id=node_id,
            name=name,
            type=NodeType.AGENT,
            agent_name=name,
            prompt_template=prompt,
            input_mapping=input_mapping or {},
            output_mapping=output_mapping or {},
            config=config,
        )
        self._nodes[node_id] = node
        
        if self._current_id:
            self._connect(self._current_id, node_id)
        
        self._current_id = node_id
        return self
    
    def tool(
        self,
        name: str,
        id: str = None,
        arguments: Dict[str, Any] = None,
        **config,
    ) -> "WorkflowBuilder":
        """Add a tool node."""
        node_id = id or self._generate_id("tool")
        node = ToolNode(
            id=node_id,
            name=name,
            type=NodeType.TOOL,
            tool_name=name,
            arguments=arguments or {},
            config=config,
        )
        self._nodes[node_id] = node
        
        if self._current_id:
            self._connect(self._current_id, node_id)
        
        self._current_id = node_id
        return self
    
    def condition(
        self,
        path: str,
        operator: str = "true",
        value: Any = None,
        id: str = None,
    ) -> "ConditionBuilder":
        """Add a condition node."""
        node_id = id or self._generate_id("condition")
        
        op = ConditionOperator[operator.upper()] if isinstance(operator, str) else operator
        condition = Condition(left=path, operator=op, right=value)
        
        node = ConditionNode(
            id=node_id,
            name=f"Condition: {path}",
            type=NodeType.CONDITION,
            condition=condition,
        )
        self._nodes[node_id] = node
        
        if self._current_id:
            self._connect(self._current_id, node_id)
        
        return ConditionBuilder(self, node_id)
    
    def parallel(self, id: str = None) -> "ParallelBuilder":
        """Add a parallel node."""
        node_id = id or self._generate_id("parallel")
        node = ParallelNode(
            id=node_id,
            name="Parallel",
            type=NodeType.PARALLEL,
        )
        self._nodes[node_id] = node
        
        if self._current_id:
            self._connect(self._current_id, node_id)
        
        return ParallelBuilder(self, node_id)
    
    def loop(
        self,
        items_path: str,
        item_var: str = "item",
        id: str = None,
        max_iterations: int = 100,
    ) -> "LoopBuilder":
        """Add a loop node."""
        node_id = id or self._generate_id("loop")
        node = LoopNode(
            id=node_id,
            name=f"Loop: {items_path}",
            type=NodeType.LOOP,
            items_path=items_path,
            item_variable=item_var,
            max_iterations=max_iterations,
        )
        self._nodes[node_id] = node
        
        if self._current_id:
            self._connect(self._current_id, node_id)
        
        return LoopBuilder(self, node_id)
    
    def human(
        self,
        prompt: str,
        id: str = None,
        options: List[str] = None,
        timeout_action: str = "skip",
        default_value: Any = None,
    ) -> "WorkflowBuilder":
        """Add a human input node."""
        node_id = id or self._generate_id("human")
        node = HumanNode(
            id=node_id,
            name="Human Input",
            type=NodeType.HUMAN,
            prompt=prompt,
            options=options or [],
            timeout_action=timeout_action,
            default_value=default_value,
        )
        self._nodes[node_id] = node
        
        if self._current_id:
            self._connect(self._current_id, node_id)
        
        self._current_id = node_id
        return self
    
    def transform(
        self,
        expression: str,
        transform_type: str = "jq",
        id: str = None,
    ) -> "WorkflowBuilder":
        """Add a transform node."""
        node_id = id or self._generate_id("transform")
        node = TransformNode(
            id=node_id,
            name="Transform",
            type=NodeType.TRANSFORM,
            transform_type=transform_type,
            expression=expression,
        )
        self._nodes[node_id] = node
        
        if self._current_id:
            self._connect(self._current_id, node_id)
        
        self._current_id = node_id
        return self
    
    def goto(self, node_id: str) -> "WorkflowBuilder":
        """Connect to an existing node."""
        if self._current_id:
            self._connect(self._current_id, node_id)
        return self
    
    def _connect(self, from_id: str, to_id: str):
        """Connect two nodes."""
        if from_id in self._nodes:
            self._nodes[from_id].next.append(to_id)
    
    def build(self) -> WorkflowDefinition:
        """Build the workflow definition."""
        workflow = WorkflowDefinition(
            id=str(uuid.uuid4()),
            name=self._name,
            version=self._version,
            nodes=self._nodes,
            start_node=self._start_id or "",
            end_nodes=self._end_ids,
        )
        
        errors = workflow.validate()
        if errors:
            logger.warning(f"Workflow validation warnings: {errors}")
        
        return workflow


class ConditionBuilder:
    """Builder for condition branches."""
    
    def __init__(self, parent: WorkflowBuilder, node_id: str):
        self._parent = parent
        self._node_id = node_id
        self._true_id: Optional[str] = None
        self._false_id: Optional[str] = None
    
    def on_true(self, node_id: str) -> "ConditionBuilder":
        """Set the true branch target."""
        self._true_id = node_id
        node = self._parent._nodes[self._node_id]
        if isinstance(node, ConditionNode):
            node.true_next = node_id
            node.next.append(node_id)
        return self
    
    def on_false(self, node_id: str) -> "ConditionBuilder":
        """Set the false branch target."""
        self._false_id = node_id
        node = self._parent._nodes[self._node_id]
        if isinstance(node, ConditionNode):
            node.false_next = node_id
            node.next.append(node_id)
        return self
    
    def done(self) -> WorkflowBuilder:
        """Return to parent builder."""
        self._parent._current_id = self._node_id
        return self._parent


class ParallelBuilder:
    """Builder for parallel branches."""
    
    def __init__(self, parent: WorkflowBuilder, node_id: str):
        self._parent = parent
        self._node_id = node_id
        self._branches: List[List[str]] = []
        self._current_branch: List[str] = []
    
    def branch(self) -> "ParallelBuilder":
        """Start a new branch."""
        if self._current_branch:
            self._branches.append(self._current_branch)
        self._current_branch = []
        return self
    
    def add(self, node_id: str) -> "ParallelBuilder":
        """Add a node to current branch."""
        self._current_branch.append(node_id)
        return self
    
    def done(self) -> WorkflowBuilder:
        """Return to parent builder."""
        if self._current_branch:
            self._branches.append(self._current_branch)
        
        node = self._parent._nodes[self._node_id]
        if isinstance(node, ParallelNode):
            node.branches = self._branches
        
        self._parent._current_id = self._node_id
        return self._parent


class LoopBuilder:
    """Builder for loop body."""
    
    def __init__(self, parent: WorkflowBuilder, node_id: str):
        self._parent = parent
        self._node_id = node_id
        self._body: List[str] = []
    
    def add(self, node_id: str) -> "LoopBuilder":
        """Add a node to loop body."""
        self._body.append(node_id)
        return self
    
    def done(self) -> WorkflowBuilder:
        """Return to parent builder."""
        node = self._parent._nodes[self._node_id]
        if isinstance(node, LoopNode):
            node.body_nodes = self._body
        
        self._parent._current_id = self._node_id
        return self._parent


# =============================================================================
# YAML/JSON Parser
# =============================================================================

class WorkflowParser:
    """
    Parse workflow definitions from YAML/JSON.
    
    Usage:
        >>> parser = WorkflowParser()
        >>> workflow = parser.parse_yaml(yaml_string)
    """
    
    def parse_yaml(self, yaml_str: str) -> WorkflowDefinition:
        """Parse YAML workflow definition."""
        try:
            import yaml
            data = yaml.safe_load(yaml_str)
            return self._parse_dict(data)
        except ImportError:
            raise RuntimeError("PyYAML not installed. Install with: pip install pyyaml")
    
    def parse_json(self, json_str: str) -> WorkflowDefinition:
        """Parse JSON workflow definition."""
        data = json.loads(json_str)
        return self._parse_dict(data)
    
    def _parse_dict(self, data: Dict) -> WorkflowDefinition:
        """Parse dictionary to workflow."""
        nodes = {}
        
        for node_data in data.get("nodes", []):
            node = self._parse_node(node_data)
            nodes[node.id] = node
        
        return WorkflowDefinition(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Untitled"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            nodes=nodes,
            start_node=data.get("start", ""),
            end_nodes=data.get("ends", []),
            inputs=data.get("inputs", {}),
            outputs=data.get("outputs", {}),
        )
    
    def _parse_node(self, data: Dict) -> WorkflowNode:
        """Parse a single node."""
        node_type = NodeType(data.get("type", "agent"))
        
        base_kwargs = {
            "id": data.get("id", str(uuid.uuid4())),
            "name": data.get("name", ""),
            "type": node_type,
            "next": data.get("next", []),
            "config": data.get("config", {}),
            "description": data.get("description", ""),
            "timeout_seconds": data.get("timeout"),
            "retry_count": data.get("retries", 0),
        }
        
        if node_type == NodeType.AGENT:
            return AgentNode(
                **base_kwargs,
                agent_name=data.get("agent", data.get("name", "")),
                prompt_template=data.get("prompt", ""),
                input_mapping=data.get("inputs", {}),
                output_mapping=data.get("outputs", {}),
            )
        elif node_type == NodeType.TOOL:
            return ToolNode(
                **base_kwargs,
                tool_name=data.get("tool", ""),
                arguments=data.get("args", {}),
            )
        elif node_type == NodeType.CONDITION:
            cond_data = data.get("condition", {})
            return ConditionNode(
                **base_kwargs,
                condition=Condition(
                    left=cond_data.get("left", ""),
                    operator=ConditionOperator(cond_data.get("op", "true")),
                    right=cond_data.get("right"),
                ),
                true_next=data.get("true_next", ""),
                false_next=data.get("false_next", ""),
            )
        elif node_type == NodeType.HUMAN:
            return HumanNode(
                **base_kwargs,
                prompt=data.get("prompt", ""),
                options=data.get("options", []),
                timeout_action=data.get("timeout_action", "skip"),
                default_value=data.get("default"),
            )
        else:
            return WorkflowNode(**base_kwargs)


# =============================================================================
# Helper Functions
# =============================================================================

def workflow(name: str, version: str = "1.0.0") -> WorkflowBuilder:
    """Create a new workflow builder."""
    return WorkflowBuilder(name, version)


def parse_workflow(definition: Union[str, Dict]) -> WorkflowDefinition:
    """Parse a workflow from YAML, JSON, or dict."""
    parser = WorkflowParser()
    
    if isinstance(definition, dict):
        return parser._parse_dict(definition)
    elif definition.strip().startswith("{"):
        return parser.parse_json(definition)
    else:
        return parser.parse_yaml(definition)
