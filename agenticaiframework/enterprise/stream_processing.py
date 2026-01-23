"""
Enterprise Stream Processing Module.

Provides stream processing patterns, windowing, aggregation,
and real-time analytics capabilities.

Example:
    # Create stream
    stream = create_stream("orders")
    
    # Process with windowing
    result = await (
        stream
        .filter(lambda x: x.amount > 100)
        .window(tumbling(minutes=5))
        .aggregate(sum_by("amount"))
        .sink(print_result)
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

T = TypeVar('T')
R = TypeVar('R')
K = TypeVar('K')


logger = logging.getLogger(__name__)


class StreamError(Exception):
    """Stream processing error."""
    pass


class WindowError(StreamError):
    """Window error."""
    pass


class AggregationError(StreamError):
    """Aggregation error."""
    pass


class WatermarkPolicy(str, Enum):
    """Watermark policy for late data."""
    DROP = "drop"
    EMIT = "emit"
    BUFFER = "buffer"


class WindowType(str, Enum):
    """Window type."""
    TUMBLING = "tumbling"
    SLIDING = "sliding"
    SESSION = "session"
    GLOBAL = "global"


@dataclass
class StreamConfig:
    """Stream configuration."""
    name: str
    parallelism: int = 1
    buffer_size: int = 1000
    checkpoint_interval: float = 60.0
    watermark_delay: float = 0.0


@dataclass
class WindowConfig:
    """Window configuration."""
    window_type: WindowType
    size: timedelta
    slide: Optional[timedelta] = None  # For sliding windows
    gap: Optional[timedelta] = None  # For session windows
    allowed_lateness: timedelta = field(default_factory=lambda: timedelta(0))


@dataclass
class StreamEvent(Generic[T]):
    """Event in a stream."""
    key: Optional[str]
    value: T
    timestamp: datetime = field(default_factory=datetime.now)
    event_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def effective_time(self) -> datetime:
        return self.event_time or self.timestamp


@dataclass
class Window:
    """A time window."""
    start: datetime
    end: datetime
    
    def contains(self, timestamp: datetime) -> bool:
        return self.start <= timestamp < self.end
    
    def __hash__(self) -> int:
        return hash((self.start, self.end))


@dataclass
class WindowedValue(Generic[T]):
    """Value with window information."""
    value: T
    window: Window
    timestamp: datetime


@dataclass
class AggregateResult(Generic[T]):
    """Aggregation result."""
    key: Optional[str]
    value: T
    window: Optional[Window] = None
    count: int = 0


class Aggregator(ABC, Generic[T, R]):
    """
    Abstract aggregator.
    """
    
    @abstractmethod
    def create_accumulator(self) -> R:
        """Create initial accumulator."""
        pass
    
    @abstractmethod
    def add(self, accumulator: R, value: T) -> R:
        """Add value to accumulator."""
        pass
    
    @abstractmethod
    def merge(self, acc1: R, acc2: R) -> R:
        """Merge two accumulators."""
        pass
    
    @abstractmethod
    def extract(self, accumulator: R) -> R:
        """Extract final result."""
        pass


class SumAggregator(Aggregator[Any, float]):
    """Sum aggregator."""
    
    def __init__(self, field: Optional[str] = None):
        self._field = field
    
    def create_accumulator(self) -> float:
        return 0.0
    
    def add(self, accumulator: float, value: Any) -> float:
        if self._field and hasattr(value, self._field):
            return accumulator + getattr(value, self._field)
        elif self._field and isinstance(value, dict):
            return accumulator + value.get(self._field, 0)
        return accumulator + float(value)
    
    def merge(self, acc1: float, acc2: float) -> float:
        return acc1 + acc2
    
    def extract(self, accumulator: float) -> float:
        return accumulator


class CountAggregator(Aggregator[Any, int]):
    """Count aggregator."""
    
    def create_accumulator(self) -> int:
        return 0
    
    def add(self, accumulator: int, value: Any) -> int:
        return accumulator + 1
    
    def merge(self, acc1: int, acc2: int) -> int:
        return acc1 + acc2
    
    def extract(self, accumulator: int) -> int:
        return accumulator


class AverageAggregator(Aggregator[Any, Tuple[float, int]]):
    """Average aggregator."""
    
    def __init__(self, field: Optional[str] = None):
        self._field = field
    
    def create_accumulator(self) -> Tuple[float, int]:
        return (0.0, 0)
    
    def add(
        self,
        accumulator: Tuple[float, int],
        value: Any,
    ) -> Tuple[float, int]:
        total, count = accumulator
        if self._field and hasattr(value, self._field):
            return (total + getattr(value, self._field), count + 1)
        elif self._field and isinstance(value, dict):
            return (total + value.get(self._field, 0), count + 1)
        return (total + float(value), count + 1)
    
    def merge(
        self,
        acc1: Tuple[float, int],
        acc2: Tuple[float, int],
    ) -> Tuple[float, int]:
        return (acc1[0] + acc2[0], acc1[1] + acc2[1])
    
    def extract(self, accumulator: Tuple[float, int]) -> float:
        total, count = accumulator
        return total / count if count > 0 else 0.0


class MinAggregator(Aggregator[Any, Optional[float]]):
    """Minimum aggregator."""
    
    def __init__(self, field: Optional[str] = None):
        self._field = field
    
    def create_accumulator(self) -> Optional[float]:
        return None
    
    def add(
        self,
        accumulator: Optional[float],
        value: Any,
    ) -> Optional[float]:
        if self._field and hasattr(value, self._field):
            v = getattr(value, self._field)
        elif self._field and isinstance(value, dict):
            v = value.get(self._field)
        else:
            v = float(value)
        
        if accumulator is None:
            return v
        return min(accumulator, v)
    
    def merge(
        self,
        acc1: Optional[float],
        acc2: Optional[float],
    ) -> Optional[float]:
        if acc1 is None:
            return acc2
        if acc2 is None:
            return acc1
        return min(acc1, acc2)
    
    def extract(self, accumulator: Optional[float]) -> Optional[float]:
        return accumulator


class MaxAggregator(Aggregator[Any, Optional[float]]):
    """Maximum aggregator."""
    
    def __init__(self, field: Optional[str] = None):
        self._field = field
    
    def create_accumulator(self) -> Optional[float]:
        return None
    
    def add(
        self,
        accumulator: Optional[float],
        value: Any,
    ) -> Optional[float]:
        if self._field and hasattr(value, self._field):
            v = getattr(value, self._field)
        elif self._field and isinstance(value, dict):
            v = value.get(self._field)
        else:
            v = float(value)
        
        if accumulator is None:
            return v
        return max(accumulator, v)
    
    def merge(
        self,
        acc1: Optional[float],
        acc2: Optional[float],
    ) -> Optional[float]:
        if acc1 is None:
            return acc2
        if acc2 is None:
            return acc1
        return max(acc1, acc2)
    
    def extract(self, accumulator: Optional[float]) -> Optional[float]:
        return accumulator


class CollectAggregator(Aggregator[T, List[T]]):
    """Collect values aggregator."""
    
    def __init__(self, max_size: int = 1000):
        self._max_size = max_size
    
    def create_accumulator(self) -> List[T]:
        return []
    
    def add(self, accumulator: List[T], value: T) -> List[T]:
        if len(accumulator) < self._max_size:
            accumulator.append(value)
        return accumulator
    
    def merge(self, acc1: List[T], acc2: List[T]) -> List[T]:
        result = acc1 + acc2
        return result[:self._max_size]
    
    def extract(self, accumulator: List[T]) -> List[T]:
        return accumulator


class WindowAssigner:
    """
    Assigns events to windows.
    """
    
    def __init__(self, config: WindowConfig):
        self._config = config
    
    def assign(self, event: StreamEvent) -> List[Window]:
        """Assign event to windows."""
        timestamp = event.effective_time
        
        if self._config.window_type == WindowType.TUMBLING:
            return [self._tumbling_window(timestamp)]
        elif self._config.window_type == WindowType.SLIDING:
            return self._sliding_windows(timestamp)
        elif self._config.window_type == WindowType.GLOBAL:
            return [Window(
                start=datetime.min,
                end=datetime.max,
            )]
        else:
            return [self._tumbling_window(timestamp)]
    
    def _tumbling_window(self, timestamp: datetime) -> Window:
        """Get tumbling window for timestamp."""
        size_seconds = self._config.size.total_seconds()
        epoch = timestamp.timestamp()
        window_start = int(epoch / size_seconds) * size_seconds
        
        return Window(
            start=datetime.fromtimestamp(window_start),
            end=datetime.fromtimestamp(window_start + size_seconds),
        )
    
    def _sliding_windows(self, timestamp: datetime) -> List[Window]:
        """Get sliding windows for timestamp."""
        windows = []
        size_seconds = self._config.size.total_seconds()
        slide_seconds = (
            self._config.slide.total_seconds()
            if self._config.slide
            else size_seconds
        )
        
        epoch = timestamp.timestamp()
        
        # Find all windows that contain this timestamp
        first_window_start = (
            int(epoch / slide_seconds) * slide_seconds
            - size_seconds
            + slide_seconds
        )
        
        current = first_window_start
        while current <= epoch:
            window_end = current + size_seconds
            if current <= epoch < window_end:
                windows.append(Window(
                    start=datetime.fromtimestamp(current),
                    end=datetime.fromtimestamp(window_end),
                ))
            current += slide_seconds
        
        return windows


class WindowState(Generic[T]):
    """
    State for a window.
    """
    
    def __init__(
        self,
        window: Window,
        aggregator: Aggregator,
    ):
        self.window = window
        self.aggregator = aggregator
        self.accumulator = aggregator.create_accumulator()
        self.count = 0
    
    def add(self, value: T) -> None:
        """Add value to window state."""
        self.accumulator = self.aggregator.add(self.accumulator, value)
        self.count += 1
    
    def merge(self, other: WindowState[T]) -> None:
        """Merge another window state."""
        self.accumulator = self.aggregator.merge(
            self.accumulator,
            other.accumulator,
        )
        self.count += other.count
    
    def result(self) -> Any:
        """Get result."""
        return self.aggregator.extract(self.accumulator)


class Stream(ABC, Generic[T]):
    """
    Abstract stream interface.
    """
    
    @abstractmethod
    async def __aiter__(self) -> AsyncIterator[StreamEvent[T]]:
        pass
    
    def filter(
        self,
        predicate: Callable[[T], bool],
    ) -> Stream[T]:
        """Filter stream."""
        return FilteredStream(self, predicate)
    
    def map(
        self,
        mapper: Callable[[T], R],
    ) -> Stream[R]:
        """Map stream."""
        return MappedStream(self, mapper)
    
    def flat_map(
        self,
        mapper: Callable[[T], List[R]],
    ) -> Stream[R]:
        """Flat map stream."""
        return FlatMappedStream(self, mapper)
    
    def key_by(
        self,
        key_selector: Callable[[T], str],
    ) -> KeyedStream[T]:
        """Key stream by selector."""
        return KeyedStream(self, key_selector)
    
    def window(
        self,
        config: WindowConfig,
    ) -> WindowedStream[T]:
        """Apply windowing."""
        return WindowedStream(self, config)
    
    async def collect(self, limit: int = 1000) -> List[T]:
        """Collect stream values."""
        results = []
        async for event in self:
            results.append(event.value)
            if len(results) >= limit:
                break
        return results
    
    async def count(self) -> int:
        """Count stream events."""
        count = 0
        async for _ in self:
            count += 1
        return count


class FilteredStream(Stream[T]):
    """Filtered stream."""
    
    def __init__(
        self,
        source: Stream[T],
        predicate: Callable[[T], bool],
    ):
        self._source = source
        self._predicate = predicate
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[T]]:
        async for event in self._source:
            if self._predicate(event.value):
                yield event


class MappedStream(Stream[R]):
    """Mapped stream."""
    
    def __init__(
        self,
        source: Stream[T],
        mapper: Callable[[T], R],
    ):
        self._source = source
        self._mapper = mapper
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[R]]:
        async for event in self._source:
            yield StreamEvent(
                key=event.key,
                value=self._mapper(event.value),
                timestamp=event.timestamp,
                event_time=event.event_time,
                metadata=event.metadata,
            )


class FlatMappedStream(Stream[R]):
    """Flat mapped stream."""
    
    def __init__(
        self,
        source: Stream[T],
        mapper: Callable[[T], List[R]],
    ):
        self._source = source
        self._mapper = mapper
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[R]]:
        async for event in self._source:
            for value in self._mapper(event.value):
                yield StreamEvent(
                    key=event.key,
                    value=value,
                    timestamp=event.timestamp,
                    event_time=event.event_time,
                    metadata=event.metadata,
                )


class KeyedStream(Stream[T]):
    """Keyed stream."""
    
    def __init__(
        self,
        source: Stream[T],
        key_selector: Callable[[T], str],
    ):
        self._source = source
        self._key_selector = key_selector
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[T]]:
        async for event in self._source:
            yield StreamEvent(
                key=self._key_selector(event.value),
                value=event.value,
                timestamp=event.timestamp,
                event_time=event.event_time,
                metadata=event.metadata,
            )
    
    def aggregate(
        self,
        aggregator: Aggregator,
    ) -> Stream[AggregateResult]:
        """Aggregate keyed stream."""
        return AggregatedStream(self, aggregator)
    
    def reduce(
        self,
        reducer: Callable[[T, T], T],
    ) -> Stream[T]:
        """Reduce keyed stream."""
        return ReducedStream(self, reducer)


class WindowedStream(Stream[T]):
    """Windowed stream."""
    
    def __init__(
        self,
        source: Stream[T],
        config: WindowConfig,
    ):
        self._source = source
        self._config = config
        self._assigner = WindowAssigner(config)
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[T]]:
        async for event in self._source:
            yield event
    
    def aggregate(
        self,
        aggregator: Aggregator,
    ) -> Stream[AggregateResult]:
        """Aggregate windowed stream."""
        return WindowedAggregatedStream(
            self._source,
            self._config,
            aggregator,
        )


class AggregatedStream(Stream[AggregateResult]):
    """Aggregated keyed stream."""
    
    def __init__(
        self,
        source: Stream[T],
        aggregator: Aggregator,
    ):
        self._source = source
        self._aggregator = aggregator
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[AggregateResult]]:
        accumulators: Dict[str, Any] = {}
        counts: Dict[str, int] = defaultdict(int)
        
        async for event in self._source:
            key = event.key or "__default__"
            
            if key not in accumulators:
                accumulators[key] = self._aggregator.create_accumulator()
            
            accumulators[key] = self._aggregator.add(
                accumulators[key],
                event.value,
            )
            counts[key] += 1
            
            result = AggregateResult(
                key=key,
                value=self._aggregator.extract(accumulators[key]),
                count=counts[key],
            )
            
            yield StreamEvent(
                key=key,
                value=result,
                timestamp=event.timestamp,
            )


class WindowedAggregatedStream(Stream[AggregateResult]):
    """Windowed aggregated stream."""
    
    def __init__(
        self,
        source: Stream[T],
        config: WindowConfig,
        aggregator: Aggregator,
    ):
        self._source = source
        self._config = config
        self._aggregator = aggregator
        self._assigner = WindowAssigner(config)
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[AggregateResult]]:
        window_states: Dict[Tuple[str, Window], WindowState] = {}
        
        async for event in self._source:
            key = event.key or "__default__"
            windows = self._assigner.assign(event)
            
            for window in windows:
                state_key = (key, window)
                
                if state_key not in window_states:
                    window_states[state_key] = WindowState(
                        window,
                        self._aggregator,
                    )
                
                window_states[state_key].add(event.value)
                
                # Emit result
                result = AggregateResult(
                    key=key,
                    value=window_states[state_key].result(),
                    window=window,
                    count=window_states[state_key].count,
                )
                
                yield StreamEvent(
                    key=key,
                    value=result,
                    timestamp=event.timestamp,
                )


class ReducedStream(Stream[T]):
    """Reduced keyed stream."""
    
    def __init__(
        self,
        source: Stream[T],
        reducer: Callable[[T, T], T],
    ):
        self._source = source
        self._reducer = reducer
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[T]]:
        states: Dict[str, T] = {}
        
        async for event in self._source:
            key = event.key or "__default__"
            
            if key not in states:
                states[key] = event.value
            else:
                states[key] = self._reducer(states[key], event.value)
            
            yield StreamEvent(
                key=key,
                value=states[key],
                timestamp=event.timestamp,
            )


class ListStream(Stream[T]):
    """Stream from a list."""
    
    def __init__(self, items: List[T]):
        self._items = items
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[T]]:
        for item in self._items:
            yield StreamEvent(key=None, value=item)


class AsyncIteratorStream(Stream[T]):
    """Stream from async iterator."""
    
    def __init__(self, iterator: AsyncIterator[T]):
        self._iterator = iterator
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[T]]:
        async for item in self._iterator:
            yield StreamEvent(key=None, value=item)


class QueueStream(Stream[T]):
    """Stream from async queue."""
    
    def __init__(
        self,
        queue: asyncio.Queue,
        timeout: Optional[float] = None,
    ):
        self._queue = queue
        self._timeout = timeout
        self._running = True
    
    async def __aiter__(self) -> AsyncIterator[StreamEvent[T]]:
        while self._running:
            try:
                if self._timeout:
                    item = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._timeout,
                    )
                else:
                    item = await self._queue.get()
                
                if item is None:  # Poison pill
                    break
                
                yield StreamEvent(key=None, value=item)
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        self._running = False


class StreamSink(ABC, Generic[T]):
    """
    Abstract stream sink.
    """
    
    @abstractmethod
    async def write(self, event: StreamEvent[T]) -> None:
        """Write event to sink."""
        pass
    
    async def close(self) -> None:
        """Close sink."""
        pass


class PrintSink(StreamSink[T]):
    """Print sink."""
    
    def __init__(self, prefix: str = ""):
        self._prefix = prefix
    
    async def write(self, event: StreamEvent[T]) -> None:
        print(f"{self._prefix}{event.value}")


class ListSink(StreamSink[T]):
    """Collect to list sink."""
    
    def __init__(self):
        self.values: List[T] = []
    
    async def write(self, event: StreamEvent[T]) -> None:
        self.values.append(event.value)


class CallbackSink(StreamSink[T]):
    """Callback sink."""
    
    def __init__(self, callback: Callable[[StreamEvent[T]], Any]):
        self._callback = callback
    
    async def write(self, event: StreamEvent[T]) -> None:
        if asyncio.iscoroutinefunction(self._callback):
            await self._callback(event)
        else:
            self._callback(event)


class StreamProcessor:
    """
    Stream processor for executing stream pipelines.
    """
    
    def __init__(self, name: str = "processor"):
        self._name = name
        self._running = False
    
    async def run(
        self,
        stream: Stream[T],
        sink: StreamSink[T],
    ) -> None:
        """Run stream to sink."""
        self._running = True
        
        try:
            async for event in stream:
                if not self._running:
                    break
                await sink.write(event)
        finally:
            await sink.close()
    
    def stop(self) -> None:
        """Stop processor."""
        self._running = False


# Factory functions
def create_stream(items: List[T]) -> Stream[T]:
    """Create stream from list."""
    return ListStream(items)


def from_iterator(iterator: AsyncIterator[T]) -> Stream[T]:
    """Create stream from async iterator."""
    return AsyncIteratorStream(iterator)


def from_queue(
    queue: asyncio.Queue,
    timeout: Optional[float] = None,
) -> QueueStream[T]:
    """Create stream from queue."""
    return QueueStream(queue, timeout)


def tumbling(
    seconds: int = 0,
    minutes: int = 0,
    hours: int = 0,
) -> WindowConfig:
    """Create tumbling window config."""
    size = timedelta(seconds=seconds, minutes=minutes, hours=hours)
    return WindowConfig(
        window_type=WindowType.TUMBLING,
        size=size,
    )


def sliding(
    size_seconds: int = 0,
    size_minutes: int = 0,
    slide_seconds: int = 0,
    slide_minutes: int = 0,
) -> WindowConfig:
    """Create sliding window config."""
    size = timedelta(seconds=size_seconds, minutes=size_minutes)
    slide = timedelta(seconds=slide_seconds, minutes=slide_minutes)
    return WindowConfig(
        window_type=WindowType.SLIDING,
        size=size,
        slide=slide,
    )


def session(gap_seconds: int = 300) -> WindowConfig:
    """Create session window config."""
    return WindowConfig(
        window_type=WindowType.SESSION,
        size=timedelta(seconds=gap_seconds),
        gap=timedelta(seconds=gap_seconds),
    )


def sum_by(field: Optional[str] = None) -> SumAggregator:
    """Create sum aggregator."""
    return SumAggregator(field)


def count() -> CountAggregator:
    """Create count aggregator."""
    return CountAggregator()


def avg_by(field: Optional[str] = None) -> AverageAggregator:
    """Create average aggregator."""
    return AverageAggregator(field)


def min_by(field: Optional[str] = None) -> MinAggregator:
    """Create min aggregator."""
    return MinAggregator(field)


def max_by(field: Optional[str] = None) -> MaxAggregator:
    """Create max aggregator."""
    return MaxAggregator(field)


def collect(max_size: int = 1000) -> CollectAggregator:
    """Create collect aggregator."""
    return CollectAggregator(max_size)


def create_processor(name: str = "processor") -> StreamProcessor:
    """Create stream processor."""
    return StreamProcessor(name)


def print_sink(prefix: str = "") -> PrintSink:
    """Create print sink."""
    return PrintSink(prefix)


def list_sink() -> ListSink:
    """Create list sink."""
    return ListSink()


def callback_sink(
    callback: Callable[[StreamEvent[T]], Any],
) -> CallbackSink[T]:
    """Create callback sink."""
    return CallbackSink(callback)


__all__ = [
    # Exceptions
    "StreamError",
    "WindowError",
    "AggregationError",
    # Enums
    "WatermarkPolicy",
    "WindowType",
    # Data classes
    "StreamConfig",
    "WindowConfig",
    "StreamEvent",
    "Window",
    "WindowedValue",
    "AggregateResult",
    # Aggregators
    "Aggregator",
    "SumAggregator",
    "CountAggregator",
    "AverageAggregator",
    "MinAggregator",
    "MaxAggregator",
    "CollectAggregator",
    # Windowing
    "WindowAssigner",
    "WindowState",
    # Streams
    "Stream",
    "FilteredStream",
    "MappedStream",
    "FlatMappedStream",
    "KeyedStream",
    "WindowedStream",
    "AggregatedStream",
    "WindowedAggregatedStream",
    "ReducedStream",
    "ListStream",
    "AsyncIteratorStream",
    "QueueStream",
    # Sinks
    "StreamSink",
    "PrintSink",
    "ListSink",
    "CallbackSink",
    # Processor
    "StreamProcessor",
    # Factory functions
    "create_stream",
    "from_iterator",
    "from_queue",
    "tumbling",
    "sliding",
    "session",
    "sum_by",
    "count",
    "avg_by",
    "min_by",
    "max_by",
    "collect",
    "create_processor",
    "print_sink",
    "list_sink",
    "callback_sink",
]
