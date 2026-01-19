"""
Knowledge Base State Management.

Provides state tracking for knowledge base creation, indexing, and sync.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .manager import StateManager, StateType

logger = logging.getLogger(__name__)


class IndexingStatus(Enum):
    """Status of knowledge base indexing."""
    IDLE = "idle"
    PREPARING = "preparing"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class SyncStatus(Enum):
    """Sync status for knowledge sources."""
    SYNCED = "synced"
    PENDING = "pending"
    SYNCING = "syncing"
    FAILED = "failed"
    STALE = "stale"


@dataclass
class SourceState:
    """State of a knowledge source."""
    source_id: str
    source_type: str  # file, url, api, database
    path: str
    status: SyncStatus
    chunk_count: int = 0
    last_synced: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "path": self.path,
            "status": self.status.value,
            "chunk_count": self.chunk_count,
            "last_synced": self.last_synced,
            "error": self.error,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceState":
        return cls(
            source_id=data["source_id"],
            source_type=data["source_type"],
            path=data["path"],
            status=SyncStatus(data["status"]),
            chunk_count=data.get("chunk_count", 0),
            last_synced=data.get("last_synced"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class IndexingProgress:
    """Progress of knowledge base indexing."""
    total_sources: int = 0
    processed_sources: int = 0
    total_chunks: int = 0
    indexed_chunks: int = 0
    failed_chunks: int = 0
    current_source: Optional[str] = None
    started_at: Optional[str] = None
    estimated_completion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_sources": self.total_sources,
            "processed_sources": self.processed_sources,
            "total_chunks": self.total_chunks,
            "indexed_chunks": self.indexed_chunks,
            "failed_chunks": self.failed_chunks,
            "current_source": self.current_source,
            "started_at": self.started_at,
            "estimated_completion": self.estimated_completion,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IndexingProgress":
        return cls(
            total_sources=data.get("total_sources", 0),
            processed_sources=data.get("processed_sources", 0),
            total_chunks=data.get("total_chunks", 0),
            indexed_chunks=data.get("indexed_chunks", 0),
            failed_chunks=data.get("failed_chunks", 0),
            current_source=data.get("current_source"),
            started_at=data.get("started_at"),
            estimated_completion=data.get("estimated_completion"),
        )
    
    @property
    def progress_percent(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return (self.indexed_chunks / self.total_chunks) * 100
    
    @property
    def is_complete(self) -> bool:
        return self.indexed_chunks + self.failed_chunks >= self.total_chunks


@dataclass
class KnowledgeBaseState:
    """Complete state of a knowledge base."""
    kb_id: str
    name: str
    status: IndexingStatus
    sources: Dict[str, SourceState]
    progress: IndexingProgress
    embedding_model: str
    vector_db: str
    dimension: int
    total_chunks: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "kb_id": self.kb_id,
            "name": self.name,
            "status": self.status.value,
            "sources": {k: v.to_dict() for k, v in self.sources.items()},
            "progress": self.progress.to_dict(),
            "embedding_model": self.embedding_model,
            "vector_db": self.vector_db,
            "dimension": self.dimension,
            "total_chunks": self.total_chunks,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeBaseState":
        return cls(
            kb_id=data["kb_id"],
            name=data["name"],
            status=IndexingStatus(data["status"]),
            sources={k: SourceState.from_dict(v) for k, v in data.get("sources", {}).items()},
            progress=IndexingProgress.from_dict(data.get("progress", {})),
            embedding_model=data.get("embedding_model", ""),
            vector_db=data.get("vector_db", ""),
            dimension=data.get("dimension", 0),
            total_chunks=data.get("total_chunks", 0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )


class KnowledgeStateManager:
    """
    Manages state for knowledge base creation and indexing.
    
    Example:
        >>> kb_state = KnowledgeStateManager()
        >>> 
        >>> # Create knowledge base
        >>> kb = kb_state.create_kb("my-kb", embedding_model="openai")
        >>> 
        >>> # Add sources
        >>> kb_state.add_source(kb.kb_id, source_type="file", path="/docs")
        >>> 
        >>> # Track indexing progress
        >>> kb_state.start_indexing(kb.kb_id)
        >>> kb_state.update_progress(kb.kb_id, indexed_chunks=100)
        >>> 
        >>> # Check sync status
        >>> status = kb_state.get_sync_status(kb.kb_id)
    """
    
    def __init__(self, state_manager: StateManager = None):
        self.state_manager = state_manager or StateManager()
    
    def _save_kb(self, kb: KnowledgeBaseState) -> bool:
        """Save knowledge base state."""
        kb.updated_at = datetime.now().isoformat()
        return self.state_manager.save(
            f"knowledge:{kb.kb_id}",
            kb.to_dict(),
            StateType.KNOWLEDGE,
        )
    
    def create_kb(
        self,
        name: str,
        embedding_model: str = "openai",
        vector_db: str = "chroma",
        dimension: int = 1536,
        metadata: Dict = None,
    ) -> KnowledgeBaseState:
        """Create a new knowledge base."""
        import uuid
        kb_id = f"kb-{uuid.uuid4().hex[:8]}"
        
        kb = KnowledgeBaseState(
            kb_id=kb_id,
            name=name,
            status=IndexingStatus.IDLE,
            sources={},
            progress=IndexingProgress(),
            embedding_model=embedding_model,
            vector_db=vector_db,
            dimension=dimension,
            metadata=metadata or {},
        )
        
        self._save_kb(kb)
        return kb
    
    def get_kb(self, kb_id: str) -> Optional[KnowledgeBaseState]:
        """Get knowledge base state."""
        data = self.state_manager.get(f"knowledge:{kb_id}")
        if data:
            return KnowledgeBaseState.from_dict(data)
        return None
    
    def delete_kb(self, kb_id: str) -> bool:
        """Delete knowledge base state."""
        return self.state_manager.delete(f"knowledge:{kb_id}")
    
    def list_kbs(self) -> List[KnowledgeBaseState]:
        """List all knowledge bases."""
        keys = self.state_manager.list("knowledge:")
        kbs = []
        for key in keys:
            data = self.state_manager.get(key)
            if data:
                kbs.append(KnowledgeBaseState.from_dict(data))
        return kbs
    
    # Source Management
    def add_source(
        self,
        kb_id: str,
        source_type: str,
        path: str,
        metadata: Dict = None,
    ) -> Optional[SourceState]:
        """Add source to knowledge base."""
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        
        import uuid
        source_id = f"src-{uuid.uuid4().hex[:8]}"
        
        source = SourceState(
            source_id=source_id,
            source_type=source_type,
            path=path,
            status=SyncStatus.PENDING,
            metadata=metadata or {},
        )
        
        kb.sources[source_id] = source
        kb.progress.total_sources = len(kb.sources)
        self._save_kb(kb)
        return source
    
    def remove_source(self, kb_id: str, source_id: str) -> bool:
        """Remove source from knowledge base."""
        kb = self.get_kb(kb_id)
        if not kb or source_id not in kb.sources:
            return False
        
        del kb.sources[source_id]
        kb.progress.total_sources = len(kb.sources)
        self._save_kb(kb)
        return True
    
    def update_source_status(
        self,
        kb_id: str,
        source_id: str,
        status: str,
        chunk_count: int = None,
        error: str = None,
    ) -> bool:
        """Update source sync status."""
        kb = self.get_kb(kb_id)
        if not kb or source_id not in kb.sources:
            return False
        
        source = kb.sources[source_id]
        source.status = SyncStatus(status)
        if chunk_count is not None:
            source.chunk_count = chunk_count
        if status == "synced":
            source.last_synced = datetime.now().isoformat()
        if error:
            source.error = error
        
        self._save_kb(kb)
        return True
    
    # Indexing Management
    def start_indexing(
        self,
        kb_id: str,
        total_chunks: int = None,
    ) -> bool:
        """Start indexing process."""
        kb = self.get_kb(kb_id)
        if not kb:
            return False
        
        kb.status = IndexingStatus.INDEXING
        kb.progress.started_at = datetime.now().isoformat()
        kb.progress.indexed_chunks = 0
        kb.progress.failed_chunks = 0
        if total_chunks:
            kb.progress.total_chunks = total_chunks
        
        self._save_kb(kb)
        return True
    
    def update_progress(
        self,
        kb_id: str,
        indexed_chunks: int = None,
        failed_chunks: int = None,
        current_source: str = None,
        total_chunks: int = None,
    ) -> bool:
        """Update indexing progress."""
        kb = self.get_kb(kb_id)
        if not kb:
            return False
        
        if indexed_chunks is not None:
            kb.progress.indexed_chunks = indexed_chunks
        if failed_chunks is not None:
            kb.progress.failed_chunks = failed_chunks
        if current_source is not None:
            kb.progress.current_source = current_source
        if total_chunks is not None:
            kb.progress.total_chunks = total_chunks
        
        # Check if complete
        if kb.progress.is_complete:
            kb.status = IndexingStatus.COMPLETED
            kb.total_chunks = kb.progress.indexed_chunks
        
        self._save_kb(kb)
        return True
    
    def pause_indexing(self, kb_id: str) -> bool:
        """Pause indexing process."""
        kb = self.get_kb(kb_id)
        if not kb:
            return False
        
        kb.status = IndexingStatus.PAUSED
        self._save_kb(kb)
        return True
    
    def resume_indexing(self, kb_id: str) -> bool:
        """Resume indexing process."""
        kb = self.get_kb(kb_id)
        if not kb or kb.status != IndexingStatus.PAUSED:
            return False
        
        kb.status = IndexingStatus.INDEXING
        self._save_kb(kb)
        return True
    
    def fail_indexing(self, kb_id: str, error: str) -> bool:
        """Mark indexing as failed."""
        kb = self.get_kb(kb_id)
        if not kb:
            return False
        
        kb.status = IndexingStatus.FAILED
        kb.metadata["last_error"] = error
        kb.metadata["failed_at"] = datetime.now().isoformat()
        self._save_kb(kb)
        return True
    
    def complete_indexing(self, kb_id: str) -> bool:
        """Mark indexing as completed."""
        kb = self.get_kb(kb_id)
        if not kb:
            return False
        
        kb.status = IndexingStatus.COMPLETED
        kb.total_chunks = kb.progress.indexed_chunks
        kb.metadata["completed_at"] = datetime.now().isoformat()
        
        # Update all sources to synced
        for source in kb.sources.values():
            if source.status == SyncStatus.SYNCING:
                source.status = SyncStatus.SYNCED
                source.last_synced = datetime.now().isoformat()
        
        self._save_kb(kb)
        return True
    
    # Status and Stats
    def get_indexing_status(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """Get current indexing status."""
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        
        return {
            "kb_id": kb_id,
            "name": kb.name,
            "status": kb.status.value,
            "progress_percent": kb.progress.progress_percent,
            "total_chunks": kb.progress.total_chunks,
            "indexed_chunks": kb.progress.indexed_chunks,
            "failed_chunks": kb.progress.failed_chunks,
            "current_source": kb.progress.current_source,
            "started_at": kb.progress.started_at,
            "is_complete": kb.progress.is_complete,
        }
    
    def get_sync_status(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """Get sync status for all sources."""
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        
        sources = []
        for source in kb.sources.values():
            sources.append({
                "source_id": source.source_id,
                "type": source.source_type,
                "path": source.path,
                "status": source.status.value,
                "chunk_count": source.chunk_count,
                "last_synced": source.last_synced,
                "error": source.error,
            })
        
        synced = sum(1 for s in kb.sources.values() if s.status == SyncStatus.SYNCED)
        
        return {
            "kb_id": kb_id,
            "total_sources": len(kb.sources),
            "synced_sources": synced,
            "sync_percent": (synced / len(kb.sources) * 100) if kb.sources else 0,
            "sources": sources,
        }
    
    def needs_resync(self, kb_id: str, max_age_hours: int = 24) -> bool:
        """Check if knowledge base needs resync."""
        kb = self.get_kb(kb_id)
        if not kb:
            return False
        
        from datetime import timedelta
        max_age = timedelta(hours=max_age_hours)
        now = datetime.now()
        
        for source in kb.sources.values():
            if source.status == SyncStatus.STALE:
                return True
            if source.last_synced:
                synced_at = datetime.fromisoformat(source.last_synced)
                if (now - synced_at) > max_age:
                    return True
        
        return False


__all__ = [
    "IndexingStatus",
    "SyncStatus",
    "SourceState",
    "IndexingProgress",
    "KnowledgeBaseState",
    "KnowledgeStateManager",
]
