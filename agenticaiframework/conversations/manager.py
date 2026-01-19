"""
Conversation Manager Implementation.

Manages conversation history, sessions, and message tracking
for agent interactions.
"""

import json
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Iterator
from pathlib import Path

logger = logging.getLogger(__name__)


class MessageRole(Enum):
    """Message sender roles."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    FUNCTION = "function"


class MessageType(Enum):
    """Types of messages."""
    TEXT = "text"
    CODE = "code"
    IMAGE = "image"
    FILE = "file"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    THINKING = "thinking"


@dataclass
class Message:
    """A single message in a conversation."""
    id: str
    role: MessageRole
    content: str
    timestamp: str
    message_type: MessageType = MessageType.TEXT
    metadata: Dict[str, Any] = field(default_factory=dict)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    tokens: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "message_type": self.message_type.value,
            "metadata": self.metadata,
            "attachments": self.attachments,
            "tokens": self.tokens,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            id=data["id"],
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=data["timestamp"],
            message_type=MessageType(data.get("message_type", "text")),
            metadata=data.get("metadata", {}),
            attachments=data.get("attachments", []),
            tokens=data.get("tokens", 0),
        )
    
    def to_openai_format(self) -> Dict[str, Any]:
        """Convert to OpenAI message format."""
        msg = {
            "role": self.role.value,
            "content": self.content,
        }
        if self.role == MessageRole.TOOL:
            msg["tool_call_id"] = self.metadata.get("tool_call_id", "")
        return msg
    
    def to_anthropic_format(self) -> Dict[str, Any]:
        """Convert to Anthropic message format."""
        return {
            "role": self.role.value if self.role != MessageRole.SYSTEM else "user",
            "content": self.content,
        }


@dataclass
class Turn:
    """A conversation turn (user message + assistant response)."""
    id: str
    user_message: Message
    assistant_message: Optional[Message] = None
    tool_calls: List[Message] = field(default_factory=list)
    thinking: Optional[Message] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_message": self.user_message.to_dict(),
            "assistant_message": self.assistant_message.to_dict() if self.assistant_message else None,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "thinking": self.thinking.to_dict() if self.thinking else None,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ConversationConfig:
    """Configuration for conversation management."""
    max_history: int = 100
    max_tokens: int = 128000
    include_system: bool = True
    track_tokens: bool = True
    auto_summarize: bool = False
    summarize_threshold: int = 50
    persist: bool = False
    persist_path: Optional[str] = None


@dataclass
class Session:
    """A conversation session."""
    id: str
    agent_id: str
    created_at: str
    updated_at: str
    title: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    turns: List[Turn] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    total_tokens: int = 0
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "title": self.title,
            "messages": [m.to_dict() for m in self.messages],
            "turns": [t.to_dict() for t in self.turns],
            "metadata": self.metadata,
            "total_tokens": self.total_tokens,
            "is_active": self.is_active,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        session = cls(
            id=data["id"],
            agent_id=data["agent_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            title=data.get("title"),
            metadata=data.get("metadata", {}),
            total_tokens=data.get("total_tokens", 0),
            is_active=data.get("is_active", True),
        )
        session.messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return session


class ConversationManager:
    """
    Manages conversation history for an agent.
    
    Example:
        >>> conv = ConversationManager(agent_id="assistant")
        >>> 
        >>> # Set system message
        >>> conv.set_system_message("You are a helpful assistant.")
        >>> 
        >>> # Add conversation
        >>> conv.add_user_message("What is 2+2?")
        >>> conv.add_assistant_message("2+2 equals 4.")
        >>> 
        >>> # Get messages for LLM
        >>> messages = conv.get_messages_for_llm()
        >>> 
        >>> # Export conversation
        >>> markdown = conv.export_markdown()
        >>> json_data = conv.export_json()
    """
    
    def __init__(
        self,
        agent_id: str = "agent",
        session_id: Optional[str] = None,
        config: Optional[ConversationConfig] = None,
    ):
        self.agent_id = agent_id
        self.config = config or ConversationConfig()
        
        # Create or load session
        self.session = Session(
            id=session_id or f"session-{uuid.uuid4().hex[:8]}",
            agent_id=agent_id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        
        self._system_message: Optional[Message] = None
        self._current_turn: Optional[Turn] = None
        self._token_counter: Optional[Callable[[str], int]] = None
        
        # Callbacks
        self._on_message_added: List[Callable[[Message], None]] = []
        self._on_turn_complete: List[Callable[[Turn], None]] = []
    
    def set_token_counter(self, counter: Callable[[str], int]) -> None:
        """Set custom token counter function."""
        self._token_counter = counter
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self._token_counter:
            return self._token_counter(text)
        # Approximate: ~4 chars per token
        return len(text) // 4
    
    def set_system_message(self, content: str, metadata: Dict = None) -> Message:
        """Set the system message."""
        message = Message(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            role=MessageRole.SYSTEM,
            content=content,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {},
            tokens=self._count_tokens(content),
        )
        self._system_message = message
        return message
    
    def add_user_message(
        self,
        content: str,
        attachments: List[Dict] = None,
        metadata: Dict = None,
    ) -> Message:
        """Add a user message."""
        message = Message(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            role=MessageRole.USER,
            content=content,
            timestamp=datetime.now().isoformat(),
            attachments=attachments or [],
            metadata=metadata or {},
            tokens=self._count_tokens(content),
        )
        
        self.session.messages.append(message)
        self.session.total_tokens += message.tokens
        self.session.updated_at = datetime.now().isoformat()
        
        # Start new turn
        self._current_turn = Turn(
            id=f"turn-{uuid.uuid4().hex[:8]}",
            user_message=message,
        )
        
        self._notify_message_added(message)
        self._maybe_persist()
        
        return message
    
    def add_assistant_message(
        self,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        metadata: Dict = None,
    ) -> Message:
        """Add an assistant message."""
        message = Message(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            role=MessageRole.ASSISTANT,
            content=content,
            timestamp=datetime.now().isoformat(),
            message_type=message_type,
            metadata=metadata or {},
            tokens=self._count_tokens(content),
        )
        
        self.session.messages.append(message)
        self.session.total_tokens += message.tokens
        self.session.updated_at = datetime.now().isoformat()
        
        # Complete turn
        if self._current_turn:
            self._current_turn.assistant_message = message
            self.session.turns.append(self._current_turn)
            self._notify_turn_complete(self._current_turn)
            self._current_turn = None
        
        self._notify_message_added(message)
        self._maybe_persist()
        
        return message
    
    def add_tool_message(
        self,
        tool_name: str,
        content: str,
        tool_call_id: str = "",
        is_result: bool = True,
    ) -> Message:
        """Add a tool call or result message."""
        message = Message(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            role=MessageRole.TOOL,
            content=content,
            timestamp=datetime.now().isoformat(),
            message_type=MessageType.TOOL_RESULT if is_result else MessageType.TOOL_CALL,
            metadata={
                "tool_name": tool_name,
                "tool_call_id": tool_call_id or f"call-{uuid.uuid4().hex[:8]}",
            },
            tokens=self._count_tokens(content),
        )
        
        self.session.messages.append(message)
        self.session.total_tokens += message.tokens
        
        if self._current_turn:
            self._current_turn.tool_calls.append(message)
        
        return message
    
    def add_thinking_message(self, content: str) -> Message:
        """Add thinking/reasoning message (for chain-of-thought)."""
        message = Message(
            id=f"msg-{uuid.uuid4().hex[:8]}",
            role=MessageRole.ASSISTANT,
            content=content,
            timestamp=datetime.now().isoformat(),
            message_type=MessageType.THINKING,
            tokens=self._count_tokens(content),
        )
        
        if self._current_turn:
            self._current_turn.thinking = message
        
        return message
    
    def get_messages(self) -> List[Message]:
        """Get all messages including system."""
        messages = []
        if self._system_message and self.config.include_system:
            messages.append(self._system_message)
        messages.extend(self.session.messages)
        return messages
    
    def get_history(self, limit: Optional[int] = None) -> List[Message]:
        """Get message history (excluding system)."""
        messages = self.session.messages
        if limit:
            messages = messages[-limit:]
        return messages
    
    def get_messages_for_llm(
        self,
        format: str = "openai",
        max_tokens: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get messages formatted for LLM API.
        
        Args:
            format: 'openai', 'anthropic', or 'raw'
            max_tokens: Max tokens to include (trims from start)
        """
        messages = self.get_messages()
        
        # Trim to token limit if specified
        if max_tokens:
            messages = self._trim_to_tokens(messages, max_tokens)
        
        if format == "openai":
            return [m.to_openai_format() for m in messages]
        elif format == "anthropic":
            return [m.to_anthropic_format() for m in messages]
        else:
            return [m.to_dict() for m in messages]
    
    def _trim_to_tokens(self, messages: List[Message], max_tokens: int) -> List[Message]:
        """Trim messages to fit within token limit."""
        result = []
        total = 0
        
        # Keep system message
        if messages and messages[0].role == MessageRole.SYSTEM:
            result.append(messages[0])
            total += messages[0].tokens
            messages = messages[1:]
        
        # Add messages from end until limit
        for msg in reversed(messages):
            if total + msg.tokens <= max_tokens:
                result.insert(1 if result else 0, msg)
                total += msg.tokens
            else:
                break
        
        return result
    
    def search(
        self,
        query: str,
        role: Optional[MessageRole] = None,
        limit: int = 10,
    ) -> List[Message]:
        """Search messages by content."""
        results = []
        query_lower = query.lower()
        
        for msg in self.session.messages:
            if role and msg.role != role:
                continue
            if query_lower in msg.content.lower():
                results.append(msg)
                if len(results) >= limit:
                    break
        
        return results
    
    def clear(self, keep_system: bool = True) -> None:
        """Clear conversation history."""
        self.session.messages.clear()
        self.session.turns.clear()
        self.session.total_tokens = 0
        self._current_turn = None
        
        if not keep_system:
            self._system_message = None
    
    def summarize(self, summarizer: Optional[Callable[[str], str]] = None) -> str:
        """Summarize conversation (requires summarizer function or LLM)."""
        # Combine all messages
        text = "\n".join(
            f"{m.role.value}: {m.content}" 
            for m in self.session.messages
        )
        
        if summarizer:
            return summarizer(text)
        
        # Simple extractive summary (first and last few messages)
        if len(self.session.messages) <= 6:
            return text
        
        first = self.session.messages[:3]
        last = self.session.messages[-3:]
        
        summary_parts = [f"{m.role.value}: {m.content}" for m in first]
        summary_parts.append("... (conversation continues) ...")
        summary_parts.extend(f"{m.role.value}: {m.content}" for m in last)
        
        return "\n".join(summary_parts)
    
    # Export methods
    def export_json(self) -> str:
        """Export conversation as JSON."""
        return json.dumps(self.session.to_dict(), indent=2)
    
    def export_markdown(self) -> str:
        """Export conversation as Markdown."""
        lines = [f"# Conversation: {self.session.id}", ""]
        
        if self._system_message:
            lines.extend([
                "## System",
                "",
                self._system_message.content,
                "",
            ])
        
        for msg in self.session.messages:
            role_header = f"### {msg.role.value.capitalize()}"
            lines.extend([role_header, "", msg.content, ""])
        
        return "\n".join(lines)
    
    def export_html(self) -> str:
        """Export conversation as HTML."""
        html_parts = [
            "<html><head><style>",
            ".message { margin: 10px 0; padding: 10px; border-radius: 8px; }",
            ".user { background: #e3f2fd; }",
            ".assistant { background: #f5f5f5; }",
            ".system { background: #fff3e0; font-style: italic; }",
            "</style></head><body>",
            f"<h1>Conversation: {self.session.id}</h1>",
        ]
        
        for msg in self.get_messages():
            role_class = msg.role.value
            html_parts.append(
                f'<div class="message {role_class}">'
                f'<strong>{msg.role.value.capitalize()}</strong><br/>'
                f'{msg.content.replace(chr(10), "<br/>")}'
                f'</div>'
            )
        
        html_parts.append("</body></html>")
        return "\n".join(html_parts)
    
    def save(self, path: Optional[str] = None) -> None:
        """Save conversation to file."""
        save_path = path or self.config.persist_path
        if not save_path:
            save_path = f"conversation_{self.session.id}.json"
        
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            f.write(self.export_json())
    
    def load(self, path: str) -> None:
        """Load conversation from file."""
        with open(path) as f:
            data = json.load(f)
        
        self.session = Session.from_dict(data)
        
        # Restore system message
        if self.session.messages and self.session.messages[0].role == MessageRole.SYSTEM:
            self._system_message = self.session.messages.pop(0)
    
    # Callbacks
    def on_message_added(self, callback: Callable[[Message], None]) -> None:
        """Register callback for message added."""
        self._on_message_added.append(callback)
    
    def on_turn_complete(self, callback: Callable[[Turn], None]) -> None:
        """Register callback for turn complete."""
        self._on_turn_complete.append(callback)
    
    def _notify_message_added(self, message: Message) -> None:
        for callback in self._on_message_added:
            try:
                callback(message)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _notify_turn_complete(self, turn: Turn) -> None:
        for callback in self._on_turn_complete:
            try:
                callback(turn)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _maybe_persist(self) -> None:
        """Auto-persist if configured."""
        if self.config.persist and self.config.persist_path:
            self.save(self.config.persist_path)
    
    # Iterator
    def __iter__(self) -> Iterator[Message]:
        return iter(self.get_messages())
    
    def __len__(self) -> int:
        return len(self.session.messages)


class SessionManager:
    """
    Manages multiple conversation sessions.
    
    Example:
        >>> manager = SessionManager(agent_id="assistant")
        >>> 
        >>> # Create new session
        >>> session = manager.create_session(title="Support Chat")
        >>> 
        >>> # Get conversation for session
        >>> conv = manager.get_conversation(session.id)
        >>> conv.add_user_message("Hello!")
        >>> 
        >>> # List all sessions
        >>> sessions = manager.list_sessions()
        >>> 
        >>> # Switch to different session
        >>> conv = manager.switch_session(other_session_id)
    """
    
    def __init__(
        self,
        agent_id: str = "agent",
        persist_dir: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.persist_dir = persist_dir
        
        self._sessions: Dict[str, Session] = {}
        self._conversations: Dict[str, ConversationManager] = {}
        self._active_session_id: Optional[str] = None
    
    def create_session(
        self,
        title: Optional[str] = None,
        metadata: Dict = None,
    ) -> Session:
        """Create new conversation session."""
        session_id = f"session-{uuid.uuid4().hex[:8]}"
        
        session = Session(
            id=session_id,
            agent_id=self.agent_id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            title=title,
            metadata=metadata or {},
        )
        
        self._sessions[session_id] = session
        
        # Create conversation manager
        config = ConversationConfig(
            persist=bool(self.persist_dir),
            persist_path=f"{self.persist_dir}/{session_id}.json" if self.persist_dir else None,
        )
        self._conversations[session_id] = ConversationManager(
            agent_id=self.agent_id,
            session_id=session_id,
            config=config,
        )
        
        self._active_session_id = session_id
        
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        return self._sessions.get(session_id)
    
    def get_conversation(self, session_id: Optional[str] = None) -> Optional[ConversationManager]:
        """Get conversation manager for session."""
        sid = session_id or self._active_session_id
        if not sid:
            return None
        return self._conversations.get(sid)
    
    def get_active_conversation(self) -> Optional[ConversationManager]:
        """Get active conversation."""
        return self.get_conversation(self._active_session_id)
    
    def switch_session(self, session_id: str) -> Optional[ConversationManager]:
        """Switch to different session."""
        if session_id in self._sessions:
            self._active_session_id = session_id
            return self._conversations.get(session_id)
        return None
    
    def list_sessions(self, active_only: bool = False) -> List[Session]:
        """List all sessions."""
        sessions = list(self._sessions.values())
        if active_only:
            sessions = [s for s in sessions if s.is_active]
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            if session_id in self._conversations:
                del self._conversations[session_id]
            if self._active_session_id == session_id:
                self._active_session_id = None
            return True
        return False
    
    def archive_session(self, session_id: str) -> bool:
        """Archive (deactivate) a session."""
        session = self._sessions.get(session_id)
        if session:
            session.is_active = False
            return True
        return False


__all__ = [
    "MessageRole",
    "MessageType",
    "Message",
    "Turn",
    "Session",
    "ConversationConfig",
    "ConversationManager",
    "SessionManager",
]
