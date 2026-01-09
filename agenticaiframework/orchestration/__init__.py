"""
Agent Orchestration Framework.

This module provides comprehensive agent orchestration including:
- Orchestration patterns (sequential, parallel, hierarchical, etc.)
- Agent supervision with Erlang/OTP-style supervision trees
- Agent teams for collaborative work
- Workflow coordination and handoffs
"""

from .types import (
    OrchestrationPattern,
    SupervisionStrategy,
    AgentRole,
    AgentState,
)
from .models import (
    TaskAssignment,
    AgentHandoff,
    SupervisionConfig,
    TeamRole,
)
from .supervisor import AgentSupervisor
from .teams import AgentTeam
from .engine import OrchestrationEngine, orchestration_engine

__all__ = [
    # Types and enums
    "OrchestrationPattern",
    "SupervisionStrategy",
    "AgentRole",
    "AgentState",
    # Data models
    "TaskAssignment",
    "AgentHandoff",
    "SupervisionConfig",
    "TeamRole",
    # Core classes
    "AgentSupervisor",
    "AgentTeam",
    "OrchestrationEngine",
    # Global instances
    "orchestration_engine",
]
