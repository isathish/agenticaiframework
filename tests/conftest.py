"""Shared pytest fixtures for agenticaiframework tests."""

from __future__ import annotations

import logging
import pytest

from agenticaiframework import (
    Agent,
    AgentManager,
    CommunicationManager,
    Hub,
    KnowledgeRetriever,
    Process,
    Prompt,
    PromptManager,
    Task,
    TaskManager,
)


@pytest.fixture()
def agent() -> Agent:
    """Create a basic test agent."""
    return Agent(
        name="TestAgent",
        role="tester",
        capabilities=["compute"],
        config={},
    )


@pytest.fixture()
def agent_manager() -> AgentManager:
    """Create an AgentManager instance."""
    return AgentManager()


@pytest.fixture()
def task_manager() -> TaskManager:
    """Create a TaskManager instance."""
    return TaskManager()


@pytest.fixture()
def prompt_manager() -> PromptManager:
    """Create a PromptManager instance."""
    return PromptManager()


@pytest.fixture()
def hub() -> Hub:
    """Create a Hub registry instance."""
    return Hub()


@pytest.fixture()
def knowledge_retriever() -> KnowledgeRetriever:
    """Create a KnowledgeRetriever instance."""
    return KnowledgeRetriever()


@pytest.fixture()
def communication_manager() -> CommunicationManager:
    """Create a CommunicationManager instance."""
    return CommunicationManager()


@pytest.fixture(autouse=True)
def _capture_logs(caplog: pytest.LogCaptureFixture) -> None:
    """Auto-capture INFO-level logs so tests can inspect them."""
    caplog.set_level(logging.INFO)
