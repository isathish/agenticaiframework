"""
Types and enums for agent orchestration.
"""

from enum import Enum


class OrchestrationPattern(Enum):
    """Patterns for agent orchestration."""
    SEQUENTIAL = "sequential"       # One after another
    PARALLEL = "parallel"           # All at once
    HIERARCHICAL = "hierarchical"   # Manager-worker pattern
    SWARM = "swarm"                 # Emergent coordination
    CONSENSUS = "consensus"         # Vote-based decisions
    PIPELINE = "pipeline"           # Data flows through agents
    BROADCAST = "broadcast"         # One to many
    ROUND_ROBIN = "round_robin"     # Rotating assignment
    PRIORITY = "priority"           # Priority-based routing
    ADAPTIVE = "adaptive"           # Dynamic pattern selection


class SupervisionStrategy(Enum):
    """Strategies for agent supervision."""
    ONE_FOR_ONE = "one_for_one"       # Restart only failed agent
    ONE_FOR_ALL = "one_for_all"       # Restart all on any failure
    REST_FOR_ONE = "rest_for_one"     # Restart agent and all after it
    ESCALATE = "escalate"             # Escalate to parent supervisor
    IGNORE = "ignore"                 # Ignore failures


class AgentRole(Enum):
    """Roles agents can play in orchestration."""
    SUPERVISOR = "supervisor"         # Manages other agents
    WORKER = "worker"                 # Executes tasks
    COORDINATOR = "coordinator"       # Coordinates between agents
    ROUTER = "router"                 # Routes tasks to agents
    AGGREGATOR = "aggregator"         # Aggregates results
    MONITOR = "monitor"               # Monitors other agents
    SPECIALIST = "specialist"         # Domain expert
    GENERALIST = "generalist"         # General purpose


class AgentState(Enum):
    """Extended agent states for orchestration."""
    IDLE = "idle"
    BUSY = "busy"
    WAITING = "waiting"
    BLOCKED = "blocked"
    FAILED = "failed"
    RECOVERING = "recovering"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"
