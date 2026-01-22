"""
Enterprise Streaming - Token-by-token streaming support.

Provides streaming capabilities for real-time LLM output,
progressive display, and efficient memory usage.

Features:
- Token-by-token streaming
- Async generators
- Progress callbacks
- Stream transformation
- Multi-consumer support
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Stream Events
# =============================================================================

class StreamEventType(Enum):
    """Types of stream events."""
    START = "start"
    TOKEN = "token"
    CHUNK = "chunk"
    PROGRESS = "progress"
    COMPLETE = "complete"
    ERROR = "error"
    METADATA = "metadata"


@dataclass
class StreamEvent:
    """An event in a stream."""
    type: StreamEventType
    data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Token-specific
    token: Optional[str] = None
    token_id: Optional[int] = None
    
    # Progress
    tokens_generated: int = 0
    total_tokens: Optional[int] = None
    
    # Timing
    latency_ms: Optional[float] = None


# =============================================================================
# Stream Source
# =============================================================================

class StreamSource(ABC, Generic[T]):
    """Abstract base for stream sources."""
    
    @abstractmethod
    async def stream(self) -> AsyncGenerator[T, None]:
        """Generate stream items."""
        pass


class LLMStreamSource(StreamSource[StreamEvent]):
    """
    Stream source for LLM responses.
    
    Usage:
        >>> source = LLMStreamSource(llm, prompt="Write a story")
        >>> async for event in source.stream():
        ...     if event.type == StreamEventType.TOKEN:
        ...         print(event.token, end="", flush=True)
    """
    
    def __init__(
        self,
        llm: Any,
        prompt: str,
        model: Optional[str] = None,
        **kwargs,
    ):
        self.llm = llm
        self.prompt = prompt
        self.model = model
        self.kwargs = kwargs
        
        self._start_time: Optional[float] = None
        self._token_count = 0
    
    async def stream(self) -> AsyncGenerator[StreamEvent, None]:
        """Stream LLM response tokens."""
        self._start_time = time.time()
        self._token_count = 0
        
        # Emit start event
        yield StreamEvent(
            type=StreamEventType.START,
            metadata={"model": self.model, "prompt_length": len(self.prompt)},
        )
        
        try:
            # Stream from LLM
            async for token in self._stream_llm():
                self._token_count += 1
                latency = (time.time() - self._start_time) * 1000
                
                yield StreamEvent(
                    type=StreamEventType.TOKEN,
                    token=token,
                    tokens_generated=self._token_count,
                    latency_ms=latency,
                )
            
            # Emit complete event
            total_time = (time.time() - self._start_time) * 1000
            yield StreamEvent(
                type=StreamEventType.COMPLETE,
                tokens_generated=self._token_count,
                latency_ms=total_time,
                metadata={"tokens_per_second": self._token_count / (total_time / 1000)},
            )
            
        except Exception as e:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                data=str(e),
                metadata={"error_type": type(e).__name__},
            )
    
    async def _stream_llm(self) -> AsyncGenerator[str, None]:
        """Stream from the LLM (implementation depends on LLM type)."""
        # Try different LLM interfaces
        if hasattr(self.llm, "astream"):
            async for chunk in self.llm.astream(self.prompt, **self.kwargs):
                if hasattr(chunk, "content"):
                    yield chunk.content
                elif isinstance(chunk, str):
                    yield chunk
        elif hasattr(self.llm, "stream"):
            for chunk in self.llm.stream(self.prompt, **self.kwargs):
                if hasattr(chunk, "content"):
                    yield chunk.content
                elif isinstance(chunk, str):
                    yield chunk
        else:
            # Fallback: simulate streaming from full response
            response = await self.llm.ainvoke(self.prompt, **self.kwargs)
            content = response.content if hasattr(response, "content") else str(response)
            
            for char in content:
                yield char


# =============================================================================
# Stream Processor
# =============================================================================

class StreamProcessor(Generic[T]):
    """
    Process and transform streams.
    
    Usage:
        >>> processor = StreamProcessor(source)
        >>> processor.add_transform(TokenToWordTransform())
        >>> processor.add_callback(print_token)
        >>> 
        >>> async for event in processor.process():
        ...     handle(event)
    """
    
    def __init__(self, source: StreamSource[T]):
        self.source = source
        self._transforms: List[Callable[[T], T]] = []
        self._callbacks: List[Callable[[T], Awaitable[None]]] = []
        self._filters: List[Callable[[T], bool]] = []
    
    def add_transform(self, transform: Callable[[T], T]) -> "StreamProcessor[T]":
        """Add a transformation function."""
        self._transforms.append(transform)
        return self
    
    def add_callback(self, callback: Callable[[T], Awaitable[None]]) -> "StreamProcessor[T]":
        """Add a callback for each item."""
        self._callbacks.append(callback)
        return self
    
    def add_filter(self, filter_fn: Callable[[T], bool]) -> "StreamProcessor[T]":
        """Add a filter function."""
        self._filters.append(filter_fn)
        return self
    
    async def process(self) -> AsyncGenerator[T, None]:
        """Process the stream with transforms and callbacks."""
        async for item in self.source.stream():
            # Apply filters
            if any(not f(item) for f in self._filters):
                continue
            
            # Apply transforms
            for transform in self._transforms:
                item = transform(item)
            
            # Call callbacks
            for callback in self._callbacks:
                await callback(item)
            
            yield item


# =============================================================================
# Stream Accumulator
# =============================================================================

class StreamAccumulator:
    """
    Accumulates stream tokens into complete content.
    
    Usage:
        >>> accumulator = StreamAccumulator()
        >>> async for event in stream:
        ...     accumulator.add(event)
        ...     print(f"\\rProgress: {accumulator.token_count}", end="")
        >>> print(accumulator.content)
    """
    
    def __init__(self):
        self._tokens: List[str] = []
        self._events: List[StreamEvent] = []
        self._start_time: Optional[float] = None
        self._end_time: Optional[float] = None
        self._error: Optional[str] = None
    
    def add(self, event: StreamEvent):
        """Add an event to the accumulator."""
        self._events.append(event)
        
        if event.type == StreamEventType.START:
            self._start_time = time.time()
        elif event.type == StreamEventType.TOKEN:
            if event.token:
                self._tokens.append(event.token)
        elif event.type == StreamEventType.COMPLETE:
            self._end_time = time.time()
        elif event.type == StreamEventType.ERROR:
            self._error = event.data
    
    @property
    def content(self) -> str:
        """Get accumulated content."""
        return "".join(self._tokens)
    
    @property
    def token_count(self) -> int:
        """Get token count."""
        return len(self._tokens)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Get stream duration in milliseconds."""
        if self._start_time and self._end_time:
            return (self._end_time - self._start_time) * 1000
        return None
    
    @property
    def tokens_per_second(self) -> Optional[float]:
        """Get tokens per second."""
        duration = self.duration_ms
        if duration and duration > 0:
            return self.token_count / (duration / 1000)
        return None
    
    @property
    def is_complete(self) -> bool:
        """Check if stream is complete."""
        return any(e.type == StreamEventType.COMPLETE for e in self._events)
    
    @property
    def has_error(self) -> bool:
        """Check if stream had an error."""
        return self._error is not None
    
    @property
    def error(self) -> Optional[str]:
        """Get error message if any."""
        return self._error


# =============================================================================
# Stream Multiplexer
# =============================================================================

class StreamMultiplexer:
    """
    Allows multiple consumers for a single stream.
    
    Usage:
        >>> mux = StreamMultiplexer(stream_source)
        >>> 
        >>> # Consumer 1
        >>> async def consumer1():
        ...     async for event in mux.subscribe():
        ...         process1(event)
        >>> 
        >>> # Consumer 2
        >>> async def consumer2():
        ...     async for event in mux.subscribe():
        ...         process2(event)
        >>> 
        >>> await asyncio.gather(mux.start(), consumer1(), consumer2())
    """
    
    def __init__(self, source: StreamSource[StreamEvent]):
        self.source = source
        self._queues: List[asyncio.Queue] = []
        self._started = False
        self._completed = False
    
    def subscribe(self) -> AsyncGenerator[StreamEvent, None]:
        """Subscribe to the stream."""
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.append(queue)
        
        async def generator():
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        
        return generator()
    
    async def start(self):
        """Start streaming to all subscribers."""
        if self._started:
            return
        
        self._started = True
        
        async for event in self.source.stream():
            for queue in self._queues:
                await queue.put(event)
        
        # Signal completion
        for queue in self._queues:
            await queue.put(None)
        
        self._completed = True


# =============================================================================
# Stream Formatters
# =============================================================================

class StreamFormatter(ABC):
    """Base class for stream formatters."""
    
    @abstractmethod
    def format(self, event: StreamEvent) -> str:
        """Format a stream event."""
        pass


class SSEFormatter(StreamFormatter):
    """Format events as Server-Sent Events."""
    
    def format(self, event: StreamEvent) -> str:
        """Format as SSE."""
        data = {
            "type": event.type.value,
            "token": event.token,
            "tokens_generated": event.tokens_generated,
        }
        
        if event.type == StreamEventType.ERROR:
            data["error"] = event.data
        
        return f"data: {json.dumps(data)}\n\n"


class JSONLFormatter(StreamFormatter):
    """Format events as JSON Lines."""
    
    def format(self, event: StreamEvent) -> str:
        """Format as JSONL."""
        data = {
            "type": event.type.value,
            "timestamp": event.timestamp.isoformat(),
        }
        
        if event.token:
            data["token"] = event.token
        if event.data:
            data["data"] = event.data
        
        return json.dumps(data) + "\n"


class MarkdownFormatter(StreamFormatter):
    """Format tokens for markdown display."""
    
    def __init__(self):
        self._in_code_block = False
    
    def format(self, event: StreamEvent) -> str:
        """Format for markdown."""
        if event.type != StreamEventType.TOKEN:
            return ""
        
        token = event.token or ""
        
        # Track code blocks
        if "```" in token:
            self._in_code_block = not self._in_code_block
        
        return token


# =============================================================================
# Streaming Helpers
# =============================================================================

async def stream_to_string(
    stream: AsyncGenerator[StreamEvent, None],
) -> str:
    """Collect stream into a string."""
    accumulator = StreamAccumulator()
    
    async for event in stream:
        accumulator.add(event)
    
    return accumulator.content


async def stream_with_progress(
    stream: AsyncGenerator[StreamEvent, None],
    on_progress: Callable[[int, Optional[int]], None],
) -> str:
    """Stream with progress callback."""
    accumulator = StreamAccumulator()
    
    async for event in stream:
        accumulator.add(event)
        
        if event.type == StreamEventType.TOKEN:
            on_progress(event.tokens_generated, event.total_tokens)
    
    return accumulator.content


async def stream_with_display(
    stream: AsyncGenerator[StreamEvent, None],
    print_fn: Callable[[str], None] = None,
) -> str:
    """Stream with real-time display."""
    if print_fn is None:
        print_fn = lambda s: print(s, end="", flush=True)
    
    accumulator = StreamAccumulator()
    
    async for event in stream:
        accumulator.add(event)
        
        if event.type == StreamEventType.TOKEN and event.token:
            print_fn(event.token)
    
    return accumulator.content


# =============================================================================
# Stream Decorators
# =============================================================================

def stream_response(fn: Callable) -> Callable:
    """
    Decorator to automatically stream function output.
    
    Usage:
        >>> @stream_response
        >>> async def generate(prompt: str) -> str:
        ...     return await llm.invoke(prompt)
    """
    import functools
    
    @functools.wraps(fn)
    async def wrapper(*args, **kwargs) -> AsyncGenerator[StreamEvent, None]:
        start_time = time.time()
        
        yield StreamEvent(type=StreamEventType.START)
        
        try:
            result = await fn(*args, **kwargs)
            
            # Simulate streaming for non-streaming functions
            if isinstance(result, str):
                for i, char in enumerate(result):
                    yield StreamEvent(
                        type=StreamEventType.TOKEN,
                        token=char,
                        tokens_generated=i + 1,
                    )
            
            total_time = (time.time() - start_time) * 1000
            yield StreamEvent(
                type=StreamEventType.COMPLETE,
                tokens_generated=len(result) if isinstance(result, str) else 0,
                latency_ms=total_time,
            )
            
        except Exception as e:
            yield StreamEvent(
                type=StreamEventType.ERROR,
                data=str(e),
            )
    
    return wrapper


# =============================================================================
# Async Stream Builder
# =============================================================================

class StreamBuilder:
    """
    Fluent builder for streams.
    
    Usage:
        >>> result = await (
        ...     StreamBuilder(source)
        ...     .filter(lambda e: e.type == StreamEventType.TOKEN)
        ...     .transform(uppercase_transform)
        ...     .on_token(print)
        ...     .collect()
        ... )
    """
    
    def __init__(self, source: Union[StreamSource, AsyncGenerator]):
        self._source = source
        self._filters: List[Callable] = []
        self._transforms: List[Callable] = []
        self._callbacks: List[Callable] = []
    
    def filter(self, fn: Callable[[StreamEvent], bool]) -> "StreamBuilder":
        """Add a filter."""
        self._filters.append(fn)
        return self
    
    def transform(self, fn: Callable[[StreamEvent], StreamEvent]) -> "StreamBuilder":
        """Add a transform."""
        self._transforms.append(fn)
        return self
    
    def on_token(self, fn: Callable[[str], None]) -> "StreamBuilder":
        """Add token callback."""
        async def callback(event: StreamEvent):
            if event.type == StreamEventType.TOKEN and event.token:
                fn(event.token)
        self._callbacks.append(callback)
        return self
    
    def on_complete(self, fn: Callable[[], None]) -> "StreamBuilder":
        """Add completion callback."""
        async def callback(event: StreamEvent):
            if event.type == StreamEventType.COMPLETE:
                fn()
        self._callbacks.append(callback)
        return self
    
    async def collect(self) -> str:
        """Collect stream into string."""
        return await stream_to_string(self._process())
    
    async def _process(self) -> AsyncGenerator[StreamEvent, None]:
        """Process the stream."""
        source = self._source
        
        if hasattr(source, "stream"):
            source = source.stream()
        
        async for event in source:
            # Apply filters
            if any(not f(event) for f in self._filters):
                continue
            
            # Apply transforms
            for transform in self._transforms:
                event = transform(event)
            
            # Call callbacks
            for callback in self._callbacks:
                await callback(event)
            
            yield event
