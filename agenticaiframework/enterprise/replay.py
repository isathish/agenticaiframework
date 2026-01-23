"""
Enterprise Replay Module.

Provides request/response replay, debugging sessions,
and time-travel debugging for agent operations.

Example:
    # Record and replay
    recorder = Recorder()
    
    with recorder.record("session-1"):
        result = await agent.run(prompt)
    
    # Replay later
    player = Player(recorder)
    async for event in player.replay("session-1"):
        print(event)
    
    # Decorators
    @record_calls()
    async def api_call():
        ...
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)
from datetime import datetime
from functools import wraps
from contextlib import asynccontextmanager
from enum import Enum
import logging
import pickle
import hashlib

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ReplayError(Exception):
    """Replay error."""
    pass


class RecordingNotFoundError(ReplayError):
    """Recording not found."""
    pass


class EventType(str, Enum):
    """Types of recorded events."""
    CALL = "call"
    RETURN = "return"
    EXCEPTION = "exception"
    MESSAGE = "message"
    STATE = "state"
    CUSTOM = "custom"


@dataclass
class RecordedEvent:
    """A recorded event."""
    event_id: str
    event_type: EventType
    timestamp: float
    name: str
    data: Dict[str, Any]
    duration_ms: Optional[float] = None
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "name": self.name,
            "data": self.data,
            "duration_ms": self.duration_ms,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecordedEvent':
        return cls(
            event_id=data["event_id"],
            event_type=EventType(data["event_type"]),
            timestamp=data["timestamp"],
            name=data["name"],
            data=data["data"],
            duration_ms=data.get("duration_ms"),
            parent_id=data.get("parent_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Recording:
    """A complete recording session."""
    session_id: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    events: List[RecordedEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> float:
        """Get recording duration."""
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000
    
    @property
    def event_count(self) -> int:
        """Get event count."""
        return len(self.events)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "event_count": self.event_count,
            "events": [e.to_dict() for e in self.events],
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Recording':
        return cls(
            session_id=data["session_id"],
            name=data["name"],
            start_time=data["start_time"],
            end_time=data.get("end_time"),
            events=[RecordedEvent.from_dict(e) for e in data.get("events", [])],
            metadata=data.get("metadata", {}),
        )
    
    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Recording':
        """Deserialize from JSON."""
        return cls.from_dict(json.loads(json_str))


class RecordingStore(ABC):
    """Abstract recording storage."""
    
    @abstractmethod
    async def save(self, recording: Recording) -> None:
        """Save a recording."""
        pass
    
    @abstractmethod
    async def load(self, session_id: str) -> Recording:
        """Load a recording."""
        pass
    
    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete a recording."""
        pass
    
    @abstractmethod
    async def list_recordings(self) -> List[Dict[str, Any]]:
        """List all recordings."""
        pass


class InMemoryRecordingStore(RecordingStore):
    """In-memory recording store."""
    
    def __init__(self, max_recordings: int = 100):
        self._recordings: Dict[str, Recording] = {}
        self._max_recordings = max_recordings
    
    async def save(self, recording: Recording) -> None:
        """Save a recording."""
        self._recordings[recording.session_id] = recording
        
        # Trim old recordings
        if len(self._recordings) > self._max_recordings:
            oldest = sorted(
                self._recordings.items(),
                key=lambda x: x[1].start_time,
            )[0][0]
            del self._recordings[oldest]
    
    async def load(self, session_id: str) -> Recording:
        """Load a recording."""
        if session_id not in self._recordings:
            raise RecordingNotFoundError(f"Recording {session_id} not found")
        return self._recordings[session_id]
    
    async def delete(self, session_id: str) -> bool:
        """Delete a recording."""
        if session_id in self._recordings:
            del self._recordings[session_id]
            return True
        return False
    
    async def list_recordings(self) -> List[Dict[str, Any]]:
        """List all recordings."""
        return [
            {
                "session_id": r.session_id,
                "name": r.name,
                "start_time": r.start_time,
                "duration_ms": r.duration_ms,
                "event_count": r.event_count,
            }
            for r in self._recordings.values()
        ]


class FileRecordingStore(RecordingStore):
    """File-based recording store."""
    
    def __init__(self, directory: str):
        self._directory = directory
        import os
        os.makedirs(directory, exist_ok=True)
    
    def _get_path(self, session_id: str) -> str:
        """Get file path for a session."""
        import os
        return os.path.join(self._directory, f"{session_id}.json")
    
    async def save(self, recording: Recording) -> None:
        """Save a recording to file."""
        path = self._get_path(recording.session_id)
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: open(path, 'w').write(recording.to_json()),
        )
    
    async def load(self, session_id: str) -> Recording:
        """Load a recording from file."""
        import os
        path = self._get_path(session_id)
        
        if not os.path.exists(path):
            raise RecordingNotFoundError(f"Recording {session_id} not found")
        
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(
            None,
            lambda: open(path, 'r').read(),
        )
        
        return Recording.from_json(content)
    
    async def delete(self, session_id: str) -> bool:
        """Delete a recording file."""
        import os
        path = self._get_path(session_id)
        
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
    
    async def list_recordings(self) -> List[Dict[str, Any]]:
        """List all recordings."""
        import os
        
        recordings = []
        for filename in os.listdir(self._directory):
            if filename.endswith('.json'):
                session_id = filename[:-5]
                try:
                    recording = await self.load(session_id)
                    recordings.append({
                        "session_id": recording.session_id,
                        "name": recording.name,
                        "start_time": recording.start_time,
                        "duration_ms": recording.duration_ms,
                        "event_count": recording.event_count,
                    })
                except Exception:
                    pass
        
        return recordings


class Recorder:
    """
    Records events for later replay.
    """
    
    def __init__(
        self,
        store: Optional[RecordingStore] = None,
        auto_save: bool = True,
    ):
        """
        Initialize recorder.
        
        Args:
            store: Recording store
            auto_save: Auto-save on session end
        """
        self._store = store or InMemoryRecordingStore()
        self._auto_save = auto_save
        self._current: Optional[Recording] = None
        self._event_stack: List[str] = []
    
    @asynccontextmanager
    async def record(
        self,
        name: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Context manager to record a session.
        
        Example:
            async with recorder.record("test-session"):
                await agent.run(prompt)
        """
        session_id = session_id or str(uuid.uuid4())
        
        self._current = Recording(
            session_id=session_id,
            name=name,
            start_time=time.time(),
            metadata=metadata or {},
        )
        
        try:
            yield self._current
        finally:
            self._current.end_time = time.time()
            
            if self._auto_save:
                await self._store.save(self._current)
            
            self._current = None
    
    def add_event(
        self,
        event_type: EventType,
        name: str,
        data: Dict[str, Any],
        duration_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add an event to the current recording."""
        if not self._current:
            raise ReplayError("No active recording session")
        
        event_id = str(uuid.uuid4())
        parent_id = self._event_stack[-1] if self._event_stack else None
        
        event = RecordedEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=time.time(),
            name=name,
            data=data,
            duration_ms=duration_ms,
            parent_id=parent_id,
            metadata=metadata or {},
        )
        
        self._current.events.append(event)
        return event_id
    
    def record_call(
        self,
        name: str,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a function call."""
        event_id = self.add_event(
            EventType.CALL,
            name,
            {
                "args": [str(a)[:100] for a in args],
                "kwargs": {k: str(v)[:100] for k, v in (kwargs or {}).items()},
            },
        )
        self._event_stack.append(event_id)
        return event_id
    
    def record_return(
        self,
        name: str,
        result: Any,
        duration_ms: float,
    ) -> str:
        """Record a function return."""
        if self._event_stack:
            self._event_stack.pop()
        
        return self.add_event(
            EventType.RETURN,
            name,
            {"result": str(result)[:500]},
            duration_ms=duration_ms,
        )
    
    def record_exception(
        self,
        name: str,
        exception: Exception,
        duration_ms: float,
    ) -> str:
        """Record an exception."""
        if self._event_stack:
            self._event_stack.pop()
        
        return self.add_event(
            EventType.EXCEPTION,
            name,
            {
                "exception_type": type(exception).__name__,
                "message": str(exception),
            },
            duration_ms=duration_ms,
        )
    
    def record_message(
        self,
        name: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a message."""
        return self.add_event(
            EventType.MESSAGE,
            name,
            {"message": message},
            metadata=metadata,
        )
    
    def record_state(
        self,
        name: str,
        state: Dict[str, Any],
    ) -> str:
        """Record a state snapshot."""
        return self.add_event(
            EventType.STATE,
            name,
            {"state": {k: str(v)[:100] for k, v in state.items()}},
        )
    
    async def save(self) -> None:
        """Save current recording."""
        if self._current:
            await self._store.save(self._current)
    
    @property
    def is_recording(self) -> bool:
        """Check if recording is active."""
        return self._current is not None
    
    @property
    def current_session(self) -> Optional[str]:
        """Get current session ID."""
        return self._current.session_id if self._current else None


class Player:
    """
    Replays recorded sessions.
    """
    
    def __init__(
        self,
        store: Optional[RecordingStore] = None,
        speed: float = 1.0,
    ):
        """
        Initialize player.
        
        Args:
            store: Recording store
            speed: Playback speed multiplier
        """
        self._store = store or InMemoryRecordingStore()
        self._speed = speed
        self._paused = False
        self._current_index = 0
    
    async def load(self, session_id: str) -> Recording:
        """Load a recording."""
        return await self._store.load(session_id)
    
    async def replay(
        self,
        session_id: str,
        realtime: bool = False,
        filter_types: Optional[List[EventType]] = None,
    ) -> AsyncIterator[RecordedEvent]:
        """
        Replay a recording.
        
        Args:
            session_id: Session to replay
            realtime: Replay in real-time with original delays
            filter_types: Only replay these event types
            
        Yields:
            Recorded events
        """
        recording = await self.load(session_id)
        
        last_timestamp = recording.start_time
        
        for i, event in enumerate(recording.events):
            self._current_index = i
            
            # Wait while paused
            while self._paused:
                await asyncio.sleep(0.1)
            
            # Filter by type
            if filter_types and event.event_type not in filter_types:
                continue
            
            # Real-time delay
            if realtime and i > 0:
                delay = (event.timestamp - last_timestamp) / self._speed
                if delay > 0:
                    await asyncio.sleep(delay)
            
            last_timestamp = event.timestamp
            yield event
    
    async def replay_to(
        self,
        session_id: str,
        event_index: int,
    ) -> List[RecordedEvent]:
        """Replay up to a specific event index."""
        recording = await self.load(session_id)
        return recording.events[:event_index + 1]
    
    def pause(self) -> None:
        """Pause playback."""
        self._paused = True
    
    def resume(self) -> None:
        """Resume playback."""
        self._paused = False
    
    def set_speed(self, speed: float) -> None:
        """Set playback speed."""
        self._speed = max(0.1, speed)
    
    @property
    def current_index(self) -> int:
        """Get current playback index."""
        return self._current_index


class MockPlayer:
    """
    Replays recordings with mocked responses.
    """
    
    def __init__(self, store: Optional[RecordingStore] = None):
        self._store = store or InMemoryRecordingStore()
        self._mocks: Dict[str, Any] = {}
    
    async def mock_function(
        self,
        session_id: str,
        function_name: str,
    ) -> Callable:
        """
        Create a mock function from recording.
        
        Returns a function that returns recorded values.
        """
        recording = await self._store.load(session_id)
        
        # Find all return events for this function
        returns = [
            e for e in recording.events
            if e.event_type == EventType.RETURN and e.name == function_name
        ]
        
        return_index = 0
        
        def mock_func(*args, **kwargs) -> Any:
            nonlocal return_index
            
            if return_index < len(returns):
                result = returns[return_index].data.get("result")
                return_index += 1
                return result
            
            return None
        
        return mock_func
    
    def get_calls(
        self,
        recording: Recording,
        function_name: str,
    ) -> List[RecordedEvent]:
        """Get all calls to a function."""
        return [
            e for e in recording.events
            if e.event_type == EventType.CALL and e.name == function_name
        ]


# Global recorder
_recorder: Optional[Recorder] = None


def get_recorder() -> Recorder:
    """Get global recorder."""
    global _recorder
    if _recorder is None:
        _recorder = Recorder()
    return _recorder


def record_calls(
    recorder: Optional[Recorder] = None,
) -> Callable:
    """
    Decorator to record function calls.
    
    Example:
        @record_calls()
        async def api_call():
            ...
    """
    def decorator(func: Callable) -> Callable:
        rec = recorder or get_recorder()
        func_name = func.__name__
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not rec.is_recording:
                return await func(*args, **kwargs)
            
            rec.record_call(func_name, args, kwargs)
            start = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                rec.record_return(func_name, result, duration)
                return result
                
            except Exception as e:
                duration = (time.time() - start) * 1000
                rec.record_exception(func_name, e, duration)
                raise
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            if not rec.is_recording:
                return func(*args, **kwargs)
            
            rec.record_call(func_name, args, kwargs)
            start = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                rec.record_return(func_name, result, duration)
                return result
                
            except Exception as e:
                duration = (time.time() - start) * 1000
                rec.record_exception(func_name, e, duration)
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


__all__ = [
    # Exceptions
    "ReplayError",
    "RecordingNotFoundError",
    # Enums
    "EventType",
    # Data classes
    "RecordedEvent",
    "Recording",
    # Stores
    "RecordingStore",
    "InMemoryRecordingStore",
    "FileRecordingStore",
    # Classes
    "Recorder",
    "Player",
    "MockPlayer",
    # Decorators
    "record_calls",
    # Utilities
    "get_recorder",
]
