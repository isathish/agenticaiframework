"""
Core Agent components.

This module provides the fundamental agent building blocks:
- Agent: Individual AI agent with context management
- AgentManager: Manager for multiple agents
"""

from .agent import Agent
from .manager import AgentManager

__all__ = [
    "Agent",
    "AgentManager",
]
