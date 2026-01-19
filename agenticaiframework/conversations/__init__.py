"""
Conversation and Logging Module for Agents.

Provides conversation history management, session handling,
structured logging, and message tracking for agent interactions.

Features:
- Conversation history with turn management
- Session-based conversation tracking
- Structured logging for agent activities
- Message export (JSON, Markdown, HTML)
- Conversation search and filtering
- Token counting and context management

Example:
    >>> from agenticaiframework.conversations import (
    ...     ConversationManager, AgentLogger, Session
    ... )
    >>> 
    >>> # Create conversation manager
    >>> conv = ConversationManager(agent_id="assistant")
    >>> 
    >>> # Add messages
    >>> conv.add_user_message("Hello!")
    >>> conv.add_assistant_message("Hi there! How can I help?")
    >>> 
    >>> # Get conversation history
    >>> history = conv.get_history()
    >>> 
    >>> # Export as markdown
    >>> markdown = conv.export_markdown()
"""

from .manager import (
    # Types
    MessageRole,
    MessageType,
    Message,
    Turn,
    Session,
    ConversationConfig,
    # Managers
    ConversationManager,
    SessionManager,
)

from .logger import (
    # Types
    LogLevel,
    LogEntry,
    LogConfig,
    # Loggers
    AgentLogger,
    StructuredLogger,
    ConversationLogger,
)

__all__ = [
    # Message Types
    "MessageRole",
    "MessageType",
    "Message",
    "Turn",
    "Session",
    "ConversationConfig",
    # Managers
    "ConversationManager",
    "SessionManager",
    # Log Types
    "LogLevel",
    "LogEntry",
    "LogConfig",
    # Loggers
    "AgentLogger",
    "StructuredLogger",
    "ConversationLogger",
]
