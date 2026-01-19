"""
Agent Memory Management.

Provides specialized memory for agents including:
- Conversation history (short-term)
- Working memory (current task context)
- Episodic memory (past experiences)
- Semantic memory (learned facts)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
import hashlib

from .manager import MemoryManager
from .types import MemoryEntry

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of agent memory."""
    CONVERSATION = "conversation"  # Chat history
    WORKING = "working"  # Current task context
    EPISODIC = "episodic"  # Past experiences
    SEMANTIC = "semantic"  # Learned facts
    PROCEDURAL = "procedural"  # How to do things


@dataclass
class ConversationTurn:
    """Single conversation turn."""
    turn_id: str
    role: str  # user, assistant, system, tool
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "tokens": self.tokens,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationTurn":
        return cls(
            turn_id=data["turn_id"],
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
            tokens=data.get("tokens", 0),
        )


@dataclass
class Episode:
    """Episodic memory - a past experience."""
    episode_id: str
    task: str
    outcome: str  # success, failure, partial
    summary: str
    actions: List[str]
    learnings: List[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    importance: float = 0.5  # 0-1 scale
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "task": self.task,
            "outcome": self.outcome,
            "summary": self.summary,
            "actions": self.actions,
            "learnings": self.learnings,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Episode":
        return cls(
            episode_id=data["episode_id"],
            task=data["task"],
            outcome=data["outcome"],
            summary=data["summary"],
            actions=data.get("actions", []),
            learnings=data.get("learnings", []),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            importance=data.get("importance", 0.5),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Fact:
    """Semantic memory - a learned fact."""
    fact_id: str
    category: str
    content: str
    source: Optional[str] = None
    confidence: float = 1.0
    learned_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: Optional[str] = None
    use_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "category": self.category,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "learned_at": self.learned_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fact":
        return cls(
            fact_id=data["fact_id"],
            category=data["category"],
            content=data["content"],
            source=data.get("source"),
            confidence=data.get("confidence", 1.0),
            learned_at=data.get("learned_at", datetime.now().isoformat()),
            last_used=data.get("last_used"),
            use_count=data.get("use_count", 0),
        )


@dataclass
class WorkingMemoryItem:
    """Working memory - current task context."""
    key: str
    value: Any
    relevance: float = 1.0  # 0-1, decays over time
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "relevance": self.relevance,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkingMemoryItem":
        return cls(
            key=data["key"],
            value=data["value"],
            relevance=data.get("relevance", 1.0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            expires_at=data.get("expires_at"),
        )


class AgentMemoryManager:
    """
    Manages all memory types for an agent.
    
    Example:
        >>> memory = AgentMemoryManager(agent_id="agent-1")
        >>> 
        >>> # Add conversation turn
        >>> memory.add_turn("user", "Hello!")
        >>> memory.add_turn("assistant", "Hi there!")
        >>> 
        >>> # Store working memory
        >>> memory.set_working("current_task", "Answer question")
        >>> 
        >>> # Record episode
        >>> memory.record_episode(task="Answer question", outcome="success")
        >>> 
        >>> # Learn a fact
        >>> memory.learn_fact("user_preferences", "User prefers concise answers")
    """
    
    def __init__(
        self,
        agent_id: str,
        memory_manager: MemoryManager = None,
        max_conversation_turns: int = 100,
        max_working_items: int = 50,
        max_episodes: int = 500,
        max_facts: int = 1000,
    ):
        self.agent_id = agent_id
        self.memory = memory_manager or MemoryManager()
        
        self.max_conversation_turns = max_conversation_turns
        self.max_working_items = max_working_items
        self.max_episodes = max_episodes
        self.max_facts = max_facts
        
        # In-memory caches for fast access
        self._conversation: List[ConversationTurn] = []
        self._working: Dict[str, WorkingMemoryItem] = {}
        self._episodes: List[Episode] = []
        self._facts: Dict[str, Fact] = {}
        
        # Load from persistent memory
        self._load_from_memory()
    
    def _key(self, mem_type: str) -> str:
        """Generate memory key for agent."""
        return f"agent:{self.agent_id}:{mem_type}"
    
    def _load_from_memory(self):
        """Load memories from persistent storage."""
        # Load conversation
        conv_data = self.memory.retrieve(self._key("conversation"), [])
        if conv_data:
            self._conversation = [ConversationTurn.from_dict(t) for t in conv_data]
        
        # Load working memory
        work_data = self.memory.retrieve(self._key("working"), {})
        if work_data:
            self._working = {k: WorkingMemoryItem.from_dict(v) for k, v in work_data.items()}
        
        # Load episodes
        ep_data = self.memory.retrieve(self._key("episodes"), [])
        if ep_data:
            self._episodes = [Episode.from_dict(e) for e in ep_data]
        
        # Load facts
        fact_data = self.memory.retrieve(self._key("facts"), {})
        if fact_data:
            self._facts = {k: Fact.from_dict(v) for k, v in fact_data.items()}
    
    def _save_conversation(self):
        """Persist conversation to memory."""
        self.memory.store_long_term(
            self._key("conversation"),
            [t.to_dict() for t in self._conversation],
            priority=8,
        )
    
    def _save_working(self):
        """Persist working memory."""
        self.memory.store_short_term(
            self._key("working"),
            {k: v.to_dict() for k, v in self._working.items()},
            ttl=3600,  # 1 hour
            priority=5,
        )
    
    def _save_episodes(self):
        """Persist episodes."""
        self.memory.store_long_term(
            self._key("episodes"),
            [e.to_dict() for e in self._episodes],
            priority=7,
        )
    
    def _save_facts(self):
        """Persist facts."""
        self.memory.store_long_term(
            self._key("facts"),
            {k: v.to_dict() for k, v in self._facts.items()},
            priority=9,
        )
    
    # =========================================================================
    # Conversation Memory
    # =========================================================================
    
    def add_turn(
        self,
        role: str,
        content: str,
        metadata: Dict = None,
        tokens: int = 0,
    ) -> ConversationTurn:
        """Add a conversation turn."""
        import uuid
        turn = ConversationTurn(
            turn_id=f"turn-{uuid.uuid4().hex[:8]}",
            role=role,
            content=content,
            metadata=metadata or {},
            tokens=tokens,
        )
        
        self._conversation.append(turn)
        
        # Evict old turns if over limit
        while len(self._conversation) > self.max_conversation_turns:
            self._conversation.pop(0)
        
        self._save_conversation()
        return turn
    
    def get_conversation(
        self,
        last_n: int = None,
        roles: List[str] = None,
    ) -> List[ConversationTurn]:
        """Get conversation history."""
        turns = self._conversation
        
        if roles:
            turns = [t for t in turns if t.role in roles]
        
        if last_n:
            turns = turns[-last_n:]
        
        return turns
    
    def get_conversation_text(
        self,
        last_n: int = None,
        format: str = "simple",  # simple, chat, markdown
    ) -> str:
        """Get conversation as formatted text."""
        turns = self.get_conversation(last_n=last_n)
        
        if format == "chat":
            return "\n".join([f"{t.role}: {t.content}" for t in turns])
        elif format == "markdown":
            lines = []
            for t in turns:
                if t.role == "user":
                    lines.append(f"**User:** {t.content}")
                elif t.role == "assistant":
                    lines.append(f"**Assistant:** {t.content}")
                else:
                    lines.append(f"*{t.role}:* {t.content}")
            return "\n\n".join(lines)
        else:
            return "\n".join([t.content for t in turns])
    
    def clear_conversation(self):
        """Clear conversation history."""
        self._conversation.clear()
        self._save_conversation()
    
    def summarize_conversation(
        self,
        summarizer: Callable[[str], str] = None,
    ) -> str:
        """Summarize and compress conversation history."""
        if not self._conversation:
            return ""
        
        text = self.get_conversation_text(format="chat")
        
        if summarizer:
            summary = summarizer(text)
        else:
            # Simple extractive summary - keep first and last few turns
            turns = self._conversation
            if len(turns) <= 6:
                return text
            
            first = turns[:2]
            last = turns[-4:]
            summary = "\n".join([f"{t.role}: {t.content}" for t in first])
            summary += f"\n... [{len(turns) - 6} turns omitted] ...\n"
            summary += "\n".join([f"{t.role}: {t.content}" for t in last])
        
        return summary
    
    # =========================================================================
    # Working Memory
    # =========================================================================
    
    def set_working(
        self,
        key: str,
        value: Any,
        relevance: float = 1.0,
        ttl_seconds: int = None,
    ):
        """Set working memory item."""
        expires_at = None
        if ttl_seconds:
            from datetime import timedelta
            expires_at = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()
        
        item = WorkingMemoryItem(
            key=key,
            value=value,
            relevance=relevance,
            expires_at=expires_at,
        )
        
        self._working[key] = item
        
        # Evict if over limit (remove lowest relevance)
        while len(self._working) > self.max_working_items:
            min_key = min(self._working.keys(), key=lambda k: self._working[k].relevance)
            del self._working[min_key]
        
        self._save_working()
    
    def get_working(self, key: str, default: Any = None) -> Any:
        """Get working memory item."""
        item = self._working.get(key)
        if not item:
            return default
        
        # Check expiration
        if item.expires_at:
            if datetime.fromisoformat(item.expires_at) < datetime.now():
                del self._working[key]
                self._save_working()
                return default
        
        return item.value
    
    def get_all_working(self) -> Dict[str, Any]:
        """Get all working memory as dict."""
        self._clean_expired_working()
        return {k: v.value for k, v in self._working.items()}
    
    def _clean_expired_working(self):
        """Remove expired working memory items."""
        now = datetime.now()
        expired = [
            k for k, v in self._working.items()
            if v.expires_at and datetime.fromisoformat(v.expires_at) < now
        ]
        for k in expired:
            del self._working[k]
        if expired:
            self._save_working()
    
    def decay_working_memory(self, decay_rate: float = 0.1):
        """Decay relevance of working memory items."""
        for item in self._working.values():
            item.relevance = max(0.0, item.relevance - decay_rate)
        
        # Remove items with zero relevance
        self._working = {k: v for k, v in self._working.items() if v.relevance > 0}
        self._save_working()
    
    def clear_working(self):
        """Clear working memory."""
        self._working.clear()
        self._save_working()
    
    # =========================================================================
    # Episodic Memory
    # =========================================================================
    
    def record_episode(
        self,
        task: str,
        outcome: str,
        summary: str = None,
        actions: List[str] = None,
        learnings: List[str] = None,
        importance: float = 0.5,
        metadata: Dict = None,
    ) -> Episode:
        """Record an episodic memory."""
        import uuid
        episode = Episode(
            episode_id=f"ep-{uuid.uuid4().hex[:8]}",
            task=task,
            outcome=outcome,
            summary=summary or f"Completed task: {task} with outcome: {outcome}",
            actions=actions or [],
            learnings=learnings or [],
            importance=importance,
            metadata=metadata or {},
        )
        
        self._episodes.append(episode)
        
        # Evict old episodes (keep most important)
        while len(self._episodes) > self.max_episodes:
            min_idx = min(range(len(self._episodes)), key=lambda i: self._episodes[i].importance)
            self._episodes.pop(min_idx)
        
        self._save_episodes()
        return episode
    
    def get_episodes(
        self,
        task_contains: str = None,
        outcome: str = None,
        min_importance: float = None,
        last_n: int = None,
    ) -> List[Episode]:
        """Get episodic memories with filters."""
        episodes = self._episodes
        
        if task_contains:
            episodes = [e for e in episodes if task_contains.lower() in e.task.lower()]
        
        if outcome:
            episodes = [e for e in episodes if e.outcome == outcome]
        
        if min_importance is not None:
            episodes = [e for e in episodes if e.importance >= min_importance]
        
        if last_n:
            episodes = episodes[-last_n:]
        
        return episodes
    
    def get_relevant_episodes(
        self,
        task: str,
        top_k: int = 5,
    ) -> List[Episode]:
        """Get episodes most relevant to a task (simple keyword matching)."""
        task_words = set(task.lower().split())
        
        scored = []
        for ep in self._episodes:
            ep_words = set(ep.task.lower().split())
            overlap = len(task_words & ep_words)
            score = overlap * ep.importance
            scored.append((score, ep))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:top_k]]
    
    # =========================================================================
    # Semantic Memory (Facts)
    # =========================================================================
    
    def learn_fact(
        self,
        category: str,
        content: str,
        source: str = None,
        confidence: float = 1.0,
    ) -> Fact:
        """Learn a new fact."""
        import uuid
        fact_id = f"fact-{uuid.uuid4().hex[:8]}"
        
        fact = Fact(
            fact_id=fact_id,
            category=category,
            content=content,
            source=source,
            confidence=confidence,
        )
        
        self._facts[fact_id] = fact
        
        # Evict if over limit (remove lowest confidence)
        while len(self._facts) > self.max_facts:
            min_id = min(self._facts.keys(), key=lambda k: self._facts[k].confidence)
            del self._facts[min_id]
        
        self._save_facts()
        return fact
    
    def get_facts(
        self,
        category: str = None,
        min_confidence: float = None,
    ) -> List[Fact]:
        """Get facts with filters."""
        facts = list(self._facts.values())
        
        if category:
            facts = [f for f in facts if f.category == category]
        
        if min_confidence is not None:
            facts = [f for f in facts if f.confidence >= min_confidence]
        
        return facts
    
    def use_fact(self, fact_id: str) -> Optional[Fact]:
        """Mark a fact as used (updates usage stats)."""
        fact = self._facts.get(fact_id)
        if fact:
            fact.last_used = datetime.now().isoformat()
            fact.use_count += 1
            self._save_facts()
        return fact
    
    def search_facts(self, query: str, top_k: int = 10) -> List[Fact]:
        """Search facts by content."""
        query_lower = query.lower()
        
        scored = []
        for fact in self._facts.values():
            if query_lower in fact.content.lower():
                score = fact.confidence * (1 + fact.use_count * 0.1)
                scored.append((score, fact))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored[:top_k]]
    
    def forget_fact(self, fact_id: str) -> bool:
        """Remove a fact."""
        if fact_id in self._facts:
            del self._facts[fact_id]
            self._save_facts()
            return True
        return False
    
    # =========================================================================
    # Memory Stats & Export
    # =========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "agent_id": self.agent_id,
            "conversation_turns": len(self._conversation),
            "working_items": len(self._working),
            "episodes": len(self._episodes),
            "facts": len(self._facts),
            "total_tokens": sum(t.tokens for t in self._conversation),
        }
    
    def export_all(self) -> Dict[str, Any]:
        """Export all memories."""
        return {
            "agent_id": self.agent_id,
            "conversation": [t.to_dict() for t in self._conversation],
            "working": {k: v.to_dict() for k, v in self._working.items()},
            "episodes": [e.to_dict() for e in self._episodes],
            "facts": {k: v.to_dict() for k, v in self._facts.items()},
            "exported_at": datetime.now().isoformat(),
        }
    
    def clear_all(self):
        """Clear all memories."""
        self._conversation.clear()
        self._working.clear()
        self._episodes.clear()
        self._facts.clear()
        self._save_conversation()
        self._save_working()
        self._save_episodes()
        self._save_facts()


__all__ = [
    "MemoryType",
    "ConversationTurn",
    "Episode",
    "Fact",
    "WorkingMemoryItem",
    "AgentMemoryManager",
]
