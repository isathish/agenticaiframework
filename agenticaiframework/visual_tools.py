"""
Agent Builder and Workflow Designer APIs.

Features:
- Agent Builder UI (backend API)
- Workflow Designer (backend API)
- Admin Console (backend API)
- Visual component definitions
"""

import uuid
import time
import logging
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import threading

logger = logging.getLogger(__name__)


# ============================================================================
# Agent Builder
# ============================================================================

class ComponentType(Enum):
    """Types of visual components."""
    INPUT = "input"
    OUTPUT = "output"
    PROCESS = "process"
    DECISION = "decision"
    LLM = "llm"
    TOOL = "tool"
    MEMORY = "memory"
    GUARDRAIL = "guardrail"


@dataclass
class ComponentDefinition:
    """Definition of a visual component."""
    component_id: str
    name: str
    component_type: ComponentType
    description: str
    icon: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    config_schema: Dict[str, Any]
    default_config: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentComponent:
    """Instance of a component in an agent."""
    instance_id: str
    component_id: str
    position: Dict[str, float]  # x, y
    config: Dict[str, Any]
    connections: List[Dict[str, str]]  # from_output -> to_input


@dataclass
class AgentBlueprint:
    """Blueprint for a visual agent."""
    blueprint_id: str
    name: str
    description: str
    version: str
    components: List[AgentComponent]
    metadata: Dict[str, Any]
    created_at: float
    updated_at: float
    created_by: str
    status: str = "draft"


class AgentBuilder:
    """
    Agent Builder backend API.
    
    Provides:
    - Component library
    - Blueprint management
    - Validation
    - Code generation
    """
    
    def __init__(self):
        self.components: Dict[str, ComponentDefinition] = {}
        self.blueprints: Dict[str, AgentBlueprint] = {}
        self._lock = threading.Lock()
        
        # Register default components
        self._register_default_components()
    
    def _register_default_components(self):
        """Register default component library."""
        default_components = [
            ComponentDefinition(
                component_id="user_input",
                name="User Input",
                component_type=ComponentType.INPUT,
                description="Receives input from user",
                icon="input",
                inputs=[],
                outputs=[{"name": "text", "type": "string"}],
                config_schema={"type": "object", "properties": {}},
                default_config={}
            ),
            ComponentDefinition(
                component_id="llm_node",
                name="LLM",
                component_type=ComponentType.LLM,
                description="Language model processing",
                icon="brain",
                inputs=[
                    {"name": "prompt", "type": "string"},
                    {"name": "context", "type": "any", "optional": True}
                ],
                outputs=[
                    {"name": "response", "type": "string"},
                    {"name": "tokens", "type": "number"}
                ],
                config_schema={
                    "type": "object",
                    "properties": {
                        "model": {"type": "string", "default": "gpt-4"},
                        "temperature": {"type": "number", "default": 0.7},
                        "max_tokens": {"type": "number", "default": 1000}
                    }
                },
                default_config={"model": "gpt-4", "temperature": 0.7}
            ),
            ComponentDefinition(
                component_id="tool_node",
                name="Tool",
                component_type=ComponentType.TOOL,
                description="Execute external tool",
                icon="wrench",
                inputs=[
                    {"name": "input", "type": "any"}
                ],
                outputs=[
                    {"name": "result", "type": "any"},
                    {"name": "status", "type": "string"}
                ],
                config_schema={
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string"},
                        "parameters": {"type": "object"}
                    }
                },
                default_config={}
            ),
            ComponentDefinition(
                component_id="decision_node",
                name="Decision",
                component_type=ComponentType.DECISION,
                description="Conditional branching",
                icon="branch",
                inputs=[
                    {"name": "condition", "type": "any"}
                ],
                outputs=[
                    {"name": "true", "type": "any"},
                    {"name": "false", "type": "any"}
                ],
                config_schema={
                    "type": "object",
                    "properties": {
                        "condition_type": {"type": "string", "enum": ["equals", "contains", "greater", "less", "custom"]},
                        "value": {"type": "any"}
                    }
                },
                default_config={"condition_type": "equals"}
            ),
            ComponentDefinition(
                component_id="memory_node",
                name="Memory",
                component_type=ComponentType.MEMORY,
                description="Store and retrieve from memory",
                icon="database",
                inputs=[
                    {"name": "query", "type": "string"},
                    {"name": "data", "type": "any", "optional": True}
                ],
                outputs=[
                    {"name": "result", "type": "any"}
                ],
                config_schema={
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "enum": ["read", "write", "search"]},
                        "memory_type": {"type": "string", "enum": ["short_term", "long_term", "semantic"]}
                    }
                },
                default_config={"operation": "search", "memory_type": "semantic"}
            ),
            ComponentDefinition(
                component_id="guardrail_node",
                name="Guardrail",
                component_type=ComponentType.GUARDRAIL,
                description="Apply safety guardrails",
                icon="shield",
                inputs=[
                    {"name": "text", "type": "string"}
                ],
                outputs=[
                    {"name": "text", "type": "string"},
                    {"name": "blocked", "type": "boolean"},
                    {"name": "violations", "type": "array"}
                ],
                config_schema={
                    "type": "object",
                    "properties": {
                        "rules": {"type": "array", "items": {"type": "string"}},
                        "action": {"type": "string", "enum": ["block", "warn", "log"]}
                    }
                },
                default_config={"action": "block"}
            ),
            ComponentDefinition(
                component_id="output_node",
                name="Output",
                component_type=ComponentType.OUTPUT,
                description="Agent output",
                icon="output",
                inputs=[
                    {"name": "response", "type": "any"}
                ],
                outputs=[],
                config_schema={"type": "object", "properties": {}},
                default_config={}
            )
        ]
        
        for comp in default_components:
            self.register_component(comp)
    
    def register_component(self, component: ComponentDefinition):
        """Register a component in the library."""
        self.components[component.component_id] = component
        logger.info("Registered component: %s", component.name)
    
    def get_component_library(self) -> List[Dict[str, Any]]:
        """Get all available components."""
        return [
            {
                'id': c.component_id,
                'name': c.name,
                'type': c.component_type.value,
                'description': c.description,
                'icon': c.icon,
                'inputs': c.inputs,
                'outputs': c.outputs,
                'config_schema': c.config_schema,
                'default_config': c.default_config
            }
            for c in self.components.values()
        ]
    
    def create_blueprint(self,
                        name: str,
                        description: str = "",
                        created_by: str = "system") -> AgentBlueprint:
        """Create a new agent blueprint."""
        blueprint_id = str(uuid.uuid4())
        
        blueprint = AgentBlueprint(
            blueprint_id=blueprint_id,
            name=name,
            description=description,
            version="1.0.0",
            components=[],
            metadata={},
            created_at=time.time(),
            updated_at=time.time(),
            created_by=created_by
        )
        
        with self._lock:
            self.blueprints[blueprint_id] = blueprint
        
        logger.info("Created blueprint: %s", name)
        
        return blueprint
    
    def add_component(self,
                     blueprint_id: str,
                     component_id: str,
                     position: Dict[str, float],
                     config: Dict[str, Any] = None) -> AgentComponent:
        """Add a component to a blueprint."""
        blueprint = self.blueprints.get(blueprint_id)
        if not blueprint:
            raise ValueError(f"Blueprint not found: {blueprint_id}")
        
        if component_id not in self.components:
            raise ValueError(f"Component not found: {component_id}")
        
        instance = AgentComponent(
            instance_id=str(uuid.uuid4()),
            component_id=component_id,
            position=position,
            config=config or self.components[component_id].default_config.copy(),
            connections=[]
        )
        
        blueprint.components.append(instance)
        blueprint.updated_at = time.time()
        
        return instance
    
    def connect_components(self,
                          blueprint_id: str,
                          from_instance: str,
                          from_output: str,
                          to_instance: str,
                          to_input: str):
        """Connect two components."""
        blueprint = self.blueprints.get(blueprint_id)
        if not blueprint:
            raise ValueError(f"Blueprint not found: {blueprint_id}")
        
        # Find source component
        source = None
        for comp in blueprint.components:
            if comp.instance_id == from_instance:
                source = comp
                break
        
        if not source:
            raise ValueError(f"Source component not found: {from_instance}")
        
        source.connections.append({
            'from_output': from_output,
            'to_instance': to_instance,
            'to_input': to_input
        })
        
        blueprint.updated_at = time.time()
    
    def validate_blueprint(self, blueprint_id: str) -> Dict[str, Any]:
        """Validate a blueprint."""
        blueprint = self.blueprints.get(blueprint_id)
        if not blueprint:
            return {'valid': False, 'errors': ['Blueprint not found']}
        
        errors = []
        warnings = []
        
        # Check for input node
        has_input = any(
            c.component_id in ['user_input'] 
            for c in blueprint.components
        )
        if not has_input:
            errors.append("Blueprint must have at least one input node")
        
        # Check for output node
        has_output = any(
            c.component_id in ['output_node'] 
            for c in blueprint.components
        )
        if not has_output:
            warnings.append("Blueprint has no output node")
        
        # Check for disconnected components
        connected_instances = set()
        for comp in blueprint.components:
            for conn in comp.connections:
                connected_instances.add(conn['to_instance'])
        
        for comp in blueprint.components:
            if (comp.instance_id not in connected_instances and 
                comp.component_id != 'user_input' and
                comp.connections):
                warnings.append(f"Component {comp.instance_id} has no incoming connections")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def generate_code(self, blueprint_id: str) -> str:
        """Generate Python code from blueprint."""
        blueprint = self.blueprints.get(blueprint_id)
        if not blueprint:
            raise ValueError(f"Blueprint not found: {blueprint_id}")
        
        lines = [
            '"""',
            f'Auto-generated agent: {blueprint.name}',
            f'Description: {blueprint.description}',
            f'Generated at: {datetime.now().isoformat()}',
            '"""',
            '',
            'from agenticaiframework import Agent, Task, LLM',
            'from agenticaiframework.memory import Memory',
            'from agenticaiframework.guardrails import GuardrailEngine',
            '',
            '',
            f'class {self._to_class_name(blueprint.name)}Agent(Agent):',
            '    """Generated agent class."""',
            '',
            '    def __init__(self):',
            '        super().__init__(',
            f'            name="{blueprint.name}",',
            f'            role="{blueprint.description}"',
            '        )',
            ''
        ]
        
        # Generate component setup
        for comp in blueprint.components:
            comp_def = self.components.get(comp.component_id)
            if comp_def and comp_def.component_type == ComponentType.LLM:
                lines.append(f'        # LLM: {comp.instance_id}')
                lines.append(f'        self.llm = LLM(')
                lines.append(f'            model="{comp.config.get("model", "gpt-4")}",')
                lines.append(f'            temperature={comp.config.get("temperature", 0.7)}')
                lines.append('        )')
                lines.append('')
        
        lines.extend([
            '    def run(self, input_text: str) -> str:',
            '        """Execute the agent."""',
            '        # TODO: Implement execution logic',
            '        return self.llm.generate(input_text)',
            '',
            '',
            'if __name__ == "__main__":',
            f'    agent = {self._to_class_name(blueprint.name)}Agent()',
            '    result = agent.run("Hello")',
            '    print(result)'
        ])
        
        return '\n'.join(lines)
    
    def _to_class_name(self, name: str) -> str:
        """Convert name to PascalCase."""
        return ''.join(word.capitalize() for word in name.replace('-', ' ').replace('_', ' ').split())
    
    def get_blueprint(self, blueprint_id: str) -> Optional[Dict[str, Any]]:
        """Get blueprint by ID."""
        blueprint = self.blueprints.get(blueprint_id)
        if not blueprint:
            return None
        
        return {
            'blueprint_id': blueprint.blueprint_id,
            'name': blueprint.name,
            'description': blueprint.description,
            'version': blueprint.version,
            'status': blueprint.status,
            'components': [
                {
                    'instance_id': c.instance_id,
                    'component_id': c.component_id,
                    'position': c.position,
                    'config': c.config,
                    'connections': c.connections
                }
                for c in blueprint.components
            ],
            'created_at': blueprint.created_at,
            'updated_at': blueprint.updated_at,
            'created_by': blueprint.created_by
        }
    
    def list_blueprints(self, status: str = None) -> List[Dict[str, Any]]:
        """List all blueprints."""
        blueprints = list(self.blueprints.values())
        
        if status:
            blueprints = [b for b in blueprints if b.status == status]
        
        return [
            {
                'blueprint_id': b.blueprint_id,
                'name': b.name,
                'description': b.description,
                'version': b.version,
                'status': b.status,
                'component_count': len(b.components),
                'created_at': b.created_at,
                'updated_at': b.updated_at
            }
            for b in blueprints
        ]


# ============================================================================
# Workflow Designer
# ============================================================================

class NodeType(Enum):
    """Types of workflow nodes."""
    START = "start"
    END = "end"
    TASK = "task"
    DECISION = "decision"
    PARALLEL = "parallel"
    JOIN = "join"
    SUBPROCESS = "subprocess"
    HUMAN_TASK = "human_task"
    TIMER = "timer"
    ERROR_HANDLER = "error_handler"


@dataclass
class WorkflowNode:
    """A node in the workflow."""
    node_id: str
    name: str
    node_type: NodeType
    position: Dict[str, float]
    config: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowEdge:
    """An edge connecting workflow nodes."""
    edge_id: str
    from_node: str
    to_node: str
    condition: Optional[str] = None
    label: Optional[str] = None


@dataclass
class WorkflowDefinition:
    """Definition of a workflow."""
    workflow_id: str
    name: str
    description: str
    version: str
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    variables: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: float
    updated_at: float
    status: str = "draft"


class WorkflowDesigner:
    """
    Workflow Designer backend API.
    
    Provides:
    - Visual workflow design
    - Workflow validation
    - Execution engine
    - Version management
    """
    
    def __init__(self):
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.executions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
    
    def create_workflow(self,
                       name: str,
                       description: str = "") -> WorkflowDefinition:
        """Create a new workflow."""
        workflow_id = str(uuid.uuid4())
        
        # Add default start node
        start_node = WorkflowNode(
            node_id="start",
            name="Start",
            node_type=NodeType.START,
            position={"x": 100, "y": 200},
            config={}
        )
        
        workflow = WorkflowDefinition(
            workflow_id=workflow_id,
            name=name,
            description=description,
            version="1.0.0",
            nodes=[start_node],
            edges=[],
            variables={},
            metadata={},
            created_at=time.time(),
            updated_at=time.time()
        )
        
        with self._lock:
            self.workflows[workflow_id] = workflow
        
        logger.info("Created workflow: %s", name)
        
        return workflow
    
    def add_node(self,
                workflow_id: str,
                name: str,
                node_type: NodeType,
                position: Dict[str, float],
                config: Dict[str, Any] = None) -> WorkflowNode:
        """Add a node to the workflow."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        node = WorkflowNode(
            node_id=str(uuid.uuid4()),
            name=name,
            node_type=node_type,
            position=position,
            config=config or {}
        )
        
        workflow.nodes.append(node)
        workflow.updated_at = time.time()
        
        return node
    
    def add_edge(self,
                workflow_id: str,
                from_node: str,
                to_node: str,
                condition: str = None,
                label: str = None) -> WorkflowEdge:
        """Add an edge connecting two nodes."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        edge = WorkflowEdge(
            edge_id=str(uuid.uuid4()),
            from_node=from_node,
            to_node=to_node,
            condition=condition,
            label=label
        )
        
        workflow.edges.append(edge)
        workflow.updated_at = time.time()
        
        return edge
    
    def validate_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Validate a workflow."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return {'valid': False, 'errors': ['Workflow not found']}
        
        errors = []
        warnings = []
        
        # Check for start node
        start_nodes = [n for n in workflow.nodes if n.node_type == NodeType.START]
        if len(start_nodes) == 0:
            errors.append("Workflow must have a start node")
        elif len(start_nodes) > 1:
            errors.append("Workflow can only have one start node")
        
        # Check for end node
        end_nodes = [n for n in workflow.nodes if n.node_type == NodeType.END]
        if len(end_nodes) == 0:
            warnings.append("Workflow has no end node")
        
        # Check for orphan nodes
        connected_nodes = set()
        for edge in workflow.edges:
            connected_nodes.add(edge.from_node)
            connected_nodes.add(edge.to_node)
        
        for node in workflow.nodes:
            if node.node_id not in connected_nodes and node.node_type != NodeType.START:
                warnings.append(f"Node '{node.name}' is not connected")
        
        # Check for cycles (simple check)
        # TODO: Implement proper cycle detection
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def execute_workflow(self,
                        workflow_id: str,
                        input_data: Dict[str, Any] = None) -> str:
        """Execute a workflow."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        execution_id = str(uuid.uuid4())
        
        execution = {
            'execution_id': execution_id,
            'workflow_id': workflow_id,
            'status': 'running',
            'current_node': 'start',
            'input_data': input_data or {},
            'variables': workflow.variables.copy(),
            'history': [],
            'started_at': time.time(),
            'completed_at': None
        }
        
        with self._lock:
            self.executions[execution_id] = execution
        
        logger.info("Started workflow execution: %s", execution_id)
        
        # TODO: Implement actual workflow execution engine
        # For now, just mark as completed
        execution['status'] = 'completed'
        execution['completed_at'] = time.time()
        
        return execution_id
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow by ID."""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return None
        
        return {
            'workflow_id': workflow.workflow_id,
            'name': workflow.name,
            'description': workflow.description,
            'version': workflow.version,
            'status': workflow.status,
            'nodes': [
                {
                    'node_id': n.node_id,
                    'name': n.name,
                    'type': n.node_type.value,
                    'position': n.position,
                    'config': n.config
                }
                for n in workflow.nodes
            ],
            'edges': [
                {
                    'edge_id': e.edge_id,
                    'from': e.from_node,
                    'to': e.to_node,
                    'condition': e.condition,
                    'label': e.label
                }
                for e in workflow.edges
            ],
            'variables': workflow.variables,
            'created_at': workflow.created_at,
            'updated_at': workflow.updated_at
        }
    
    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all workflows."""
        return [
            {
                'workflow_id': w.workflow_id,
                'name': w.name,
                'description': w.description,
                'version': w.version,
                'status': w.status,
                'node_count': len(w.nodes),
                'created_at': w.created_at,
                'updated_at': w.updated_at
            }
            for w in self.workflows.values()
        ]


# ============================================================================
# Admin Console
# ============================================================================

@dataclass
class AdminUser:
    """Admin user."""
    user_id: str
    username: str
    email: str
    role: str
    permissions: List[str]
    created_at: float
    last_login: Optional[float] = None


class AdminConsole:
    """
    Admin Console backend API.
    
    Provides:
    - User management
    - System configuration
    - Dashboard metrics
    - Audit logs access
    """
    
    def __init__(self):
        self.users: Dict[str, AdminUser] = {}
        self.settings: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
        # Default settings
        self.settings = {
            'system': {
                'name': 'AgenticAI Framework',
                'version': '2.0.0',
                'debug_mode': False,
                'log_level': 'INFO'
            },
            'limits': {
                'max_agents': 100,
                'max_concurrent_tasks': 50,
                'max_memory_mb': 8192,
                'request_timeout_seconds': 300
            },
            'features': {
                'multi_region': True,
                'audit_logging': True,
                'rate_limiting': True
            }
        }
    
    def create_user(self,
                   username: str,
                   email: str,
                   role: str = "viewer",
                   permissions: List[str] = None) -> AdminUser:
        """Create an admin user."""
        user_id = str(uuid.uuid4())
        
        # Default permissions by role
        default_permissions = {
            'admin': ['read', 'write', 'delete', 'manage_users', 'manage_settings'],
            'operator': ['read', 'write', 'manage_settings'],
            'viewer': ['read']
        }
        
        user = AdminUser(
            user_id=user_id,
            username=username,
            email=email,
            role=role,
            permissions=permissions or default_permissions.get(role, ['read']),
            created_at=time.time()
        )
        
        with self._lock:
            self.users[user_id] = user
        
        logger.info("Created admin user: %s (%s)", username, role)
        
        return user
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get dashboard metrics."""
        return {
            'timestamp': time.time(),
            'system': {
                'status': 'healthy',
                'uptime_hours': 24.5,  # Simulated
                'cpu_usage': 45.2,
                'memory_usage': 62.8
            },
            'agents': {
                'total': 15,
                'active': 8,
                'idle': 5,
                'error': 2
            },
            'tasks': {
                'total_today': 1250,
                'completed': 1180,
                'failed': 35,
                'pending': 35
            },
            'api': {
                'requests_per_minute': 85,
                'avg_latency_ms': 125,
                'error_rate': 0.02
            },
            'integrations': {
                'total': 5,
                'healthy': 4,
                'degraded': 1
            }
        }
    
    def get_setting(self, category: str, key: str = None) -> Any:
        """Get system setting."""
        if category not in self.settings:
            return None
        
        if key:
            return self.settings[category].get(key)
        
        return self.settings[category]
    
    def update_setting(self, category: str, key: str, value: Any):
        """Update system setting."""
        if category not in self.settings:
            self.settings[category] = {}
        
        self.settings[category][key] = value
        logger.info("Updated setting: %s.%s = %s", category, key, value)
    
    def get_users(self) -> List[Dict[str, Any]]:
        """Get all admin users."""
        return [
            {
                'user_id': u.user_id,
                'username': u.username,
                'email': u.email,
                'role': u.role,
                'permissions': u.permissions,
                'created_at': u.created_at,
                'last_login': u.last_login
            }
            for u in self.users.values()
        ]
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        return {
            'name': self.settings['system']['name'],
            'version': self.settings['system']['version'],
            'environment': 'production',
            'features': self.settings['features'],
            'limits': self.settings['limits']
        }
    
    def get_activity_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent activity log."""
        # Simulated activity log
        return [
            {
                'timestamp': time.time() - (i * 60),
                'type': ['agent_created', 'task_completed', 'user_login', 'config_changed'][i % 4],
                'actor': f'user_{i % 3}',
                'details': f'Activity {i}'
            }
            for i in range(min(limit, 20))
        ]


# Global instances
agent_builder = AgentBuilder()
workflow_designer = WorkflowDesigner()
admin_console = AdminConsole()
