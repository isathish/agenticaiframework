"""
Enterprise Profiler Module.

Provides performance profiling, bottleneck detection, and
optimization insights for agent operations.

Example:
    # Profile execution
    profiler = Profiler()
    
    with profiler.trace("process_request"):
        result = await process()
    
    report = profiler.get_report()
    print(report.slowest_operations)
    
    # Decorators
    @profile(name="api_call")
    async def call_api():
        ...
"""

from __future__ import annotations

import asyncio
import cProfile
import pstats
import io
import time
import tracemalloc
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Generic,
    Tuple,
)
from datetime import datetime
from functools import wraps
from contextlib import contextmanager
from enum import Enum
import logging
import statistics

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ProfilerError(Exception):
    """Profiler error."""
    pass


class MetricType(str, Enum):
    """Types of metrics."""
    TIME = "time"
    MEMORY = "memory"
    CPU = "cpu"
    CALLS = "calls"


@dataclass
class TimingRecord:
    """A single timing record."""
    name: str
    start_time: float
    end_time: float
    parent: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        return (self.end_time - self.start_time) * 1000
    
    @property
    def duration_s(self) -> float:
        """Get duration in seconds."""
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": self.duration_ms,
            "parent": self.parent,
            "metadata": self.metadata,
        }


@dataclass
class MemoryRecord:
    """A single memory record."""
    name: str
    timestamp: float
    current_bytes: int
    peak_bytes: int
    allocated_bytes: int
    
    @property
    def current_mb(self) -> float:
        """Get current memory in MB."""
        return self.current_bytes / (1024 * 1024)
    
    @property
    def peak_mb(self) -> float:
        """Get peak memory in MB."""
        return self.peak_bytes / (1024 * 1024)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "current_mb": round(self.current_mb, 2),
            "peak_mb": round(self.peak_mb, 2),
            "allocated_bytes": self.allocated_bytes,
        }


@dataclass
class OperationStats:
    """Statistics for an operation."""
    name: str
    call_count: int
    total_time_ms: float
    min_time_ms: float
    max_time_ms: float
    mean_time_ms: float
    median_time_ms: float
    std_dev_ms: float
    p95_time_ms: float
    p99_time_ms: float
    
    @classmethod
    def from_timings(cls, name: str, timings: List[float]) -> 'OperationStats':
        """Create from list of timing values."""
        if not timings:
            return cls(
                name=name,
                call_count=0,
                total_time_ms=0,
                min_time_ms=0,
                max_time_ms=0,
                mean_time_ms=0,
                median_time_ms=0,
                std_dev_ms=0,
                p95_time_ms=0,
                p99_time_ms=0,
            )
        
        sorted_timings = sorted(timings)
        
        return cls(
            name=name,
            call_count=len(timings),
            total_time_ms=sum(timings),
            min_time_ms=min(timings),
            max_time_ms=max(timings),
            mean_time_ms=statistics.mean(timings),
            median_time_ms=statistics.median(timings),
            std_dev_ms=statistics.stdev(timings) if len(timings) > 1 else 0,
            p95_time_ms=sorted_timings[int(len(timings) * 0.95)] if timings else 0,
            p99_time_ms=sorted_timings[int(len(timings) * 0.99)] if timings else 0,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "call_count": self.call_count,
            "total_time_ms": round(self.total_time_ms, 2),
            "min_time_ms": round(self.min_time_ms, 2),
            "max_time_ms": round(self.max_time_ms, 2),
            "mean_time_ms": round(self.mean_time_ms, 2),
            "median_time_ms": round(self.median_time_ms, 2),
            "std_dev_ms": round(self.std_dev_ms, 2),
            "p95_time_ms": round(self.p95_time_ms, 2),
            "p99_time_ms": round(self.p99_time_ms, 2),
        }


@dataclass
class ProfileReport:
    """Complete profiling report."""
    start_time: float
    end_time: float
    total_duration_ms: float
    operation_stats: Dict[str, OperationStats]
    memory_stats: Optional[Dict[str, Any]] = None
    hotspots: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    @property
    def slowest_operations(self) -> List[Tuple[str, float]]:
        """Get operations sorted by mean time."""
        return sorted(
            [(s.name, s.mean_time_ms) for s in self.operation_stats.values()],
            key=lambda x: x[1],
            reverse=True,
        )
    
    @property
    def most_called(self) -> List[Tuple[str, int]]:
        """Get operations sorted by call count."""
        return sorted(
            [(s.name, s.call_count) for s in self.operation_stats.values()],
            key=lambda x: x[1],
            reverse=True,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_duration_ms": round(self.total_duration_ms, 2),
            "operation_stats": {
                name: stats.to_dict()
                for name, stats in self.operation_stats.items()
            },
            "memory_stats": self.memory_stats,
            "hotspots": self.hotspots,
            "recommendations": self.recommendations,
        }
    
    def to_text(self) -> str:
        """Generate text report."""
        lines = [
            "=" * 60,
            "PERFORMANCE PROFILE REPORT",
            "=" * 60,
            f"Total Duration: {round(self.total_duration_ms, 2)} ms",
            "",
            "Top Operations by Time:",
            "-" * 40,
        ]
        
        for name, time_ms in self.slowest_operations[:10]:
            lines.append(f"  {name}: {round(time_ms, 2)} ms (mean)")
        
        lines.extend([
            "",
            "Most Called Operations:",
            "-" * 40,
        ])
        
        for name, count in self.most_called[:10]:
            lines.append(f"  {name}: {count} calls")
        
        if self.hotspots:
            lines.extend([
                "",
                "Detected Hotspots:",
                "-" * 40,
            ])
            for hotspot in self.hotspots:
                lines.append(f"  • {hotspot}")
        
        if self.recommendations:
            lines.extend([
                "",
                "Recommendations:",
                "-" * 40,
            ])
            for rec in self.recommendations:
                lines.append(f"  • {rec}")
        
        lines.append("=" * 60)
        return "\n".join(lines)


class Profiler:
    """
    Performance profiler for agent operations.
    """
    
    def __init__(
        self,
        track_memory: bool = False,
        max_records: int = 10000,
    ):
        """
        Initialize profiler.
        
        Args:
            track_memory: Enable memory tracking
            max_records: Maximum records to keep
        """
        self._timing_records: List[TimingRecord] = []
        self._memory_records: List[MemoryRecord] = []
        self._operation_timings: Dict[str, List[float]] = {}
        self._track_memory = track_memory
        self._max_records = max_records
        self._start_time: Optional[float] = None
        self._current_parent: Optional[str] = None
        self._lock = asyncio.Lock()
    
    def start(self) -> None:
        """Start profiling session."""
        self._start_time = time.time()
        self._timing_records.clear()
        self._memory_records.clear()
        self._operation_timings.clear()
        
        if self._track_memory:
            tracemalloc.start()
    
    def stop(self) -> ProfileReport:
        """Stop profiling and generate report."""
        end_time = time.time()
        
        if self._track_memory:
            tracemalloc.stop()
        
        start = self._start_time or end_time
        
        return self._generate_report(start, end_time)
    
    @contextmanager
    def trace(self, name: str, **metadata: Any):
        """
        Context manager to trace an operation.
        
        Example:
            with profiler.trace("process_request"):
                process()
        """
        start = time.time()
        parent = self._current_parent
        self._current_parent = name
        
        memory_start = None
        if self._track_memory:
            memory_start = tracemalloc.get_traced_memory()
        
        try:
            yield
        finally:
            end = time.time()
            self._current_parent = parent
            
            record = TimingRecord(
                name=name,
                start_time=start,
                end_time=end,
                parent=parent,
                metadata=metadata,
            )
            
            self._add_timing(record)
            
            if self._track_memory and memory_start:
                current, peak = tracemalloc.get_traced_memory()
                memory_record = MemoryRecord(
                    name=name,
                    timestamp=end,
                    current_bytes=current,
                    peak_bytes=peak,
                    allocated_bytes=current - memory_start[0],
                )
                self._memory_records.append(memory_record)
    
    def _add_timing(self, record: TimingRecord) -> None:
        """Add a timing record."""
        self._timing_records.append(record)
        
        if record.name not in self._operation_timings:
            self._operation_timings[record.name] = []
        self._operation_timings[record.name].append(record.duration_ms)
        
        # Trim old records
        if len(self._timing_records) > self._max_records:
            self._timing_records = self._timing_records[-self._max_records:]
    
    def record(self, name: str, duration_ms: float, **metadata: Any) -> None:
        """Manually record a timing."""
        end = time.time()
        record = TimingRecord(
            name=name,
            start_time=end - (duration_ms / 1000),
            end_time=end,
            parent=self._current_parent,
            metadata=metadata,
        )
        self._add_timing(record)
    
    def _generate_report(self, start_time: float, end_time: float) -> ProfileReport:
        """Generate profiling report."""
        # Calculate operation stats
        operation_stats = {
            name: OperationStats.from_timings(name, timings)
            for name, timings in self._operation_timings.items()
        }
        
        # Memory stats
        memory_stats = None
        if self._memory_records:
            peak_memory = max(r.peak_bytes for r in self._memory_records)
            memory_stats = {
                "peak_mb": round(peak_memory / (1024 * 1024), 2),
                "allocations": len(self._memory_records),
            }
        
        # Detect hotspots
        hotspots = self._detect_hotspots(operation_stats)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(operation_stats, memory_stats)
        
        return ProfileReport(
            start_time=start_time,
            end_time=end_time,
            total_duration_ms=(end_time - start_time) * 1000,
            operation_stats=operation_stats,
            memory_stats=memory_stats,
            hotspots=hotspots,
            recommendations=recommendations,
        )
    
    def _detect_hotspots(self, stats: Dict[str, OperationStats]) -> List[str]:
        """Detect performance hotspots."""
        hotspots = []
        
        for name, op_stats in stats.items():
            # High variance indicates inconsistent performance
            if op_stats.std_dev_ms > op_stats.mean_time_ms * 0.5:
                hotspots.append(
                    f"{name}: High variance (std_dev={round(op_stats.std_dev_ms, 2)}ms)"
                )
            
            # P99 significantly higher than mean
            if op_stats.p99_time_ms > op_stats.mean_time_ms * 3:
                hotspots.append(
                    f"{name}: Tail latency issue (P99={round(op_stats.p99_time_ms, 2)}ms)"
                )
            
            # High call count with high mean time
            if op_stats.call_count > 100 and op_stats.mean_time_ms > 10:
                hotspots.append(
                    f"{name}: Frequently called slow operation"
                )
        
        return hotspots
    
    def _generate_recommendations(
        self,
        stats: Dict[str, OperationStats],
        memory_stats: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Find operations that contribute most to total time
        total_time = sum(s.total_time_ms for s in stats.values())
        
        for name, op_stats in stats.items():
            if total_time > 0:
                contribution = (op_stats.total_time_ms / total_time) * 100
                
                if contribution > 50:
                    recommendations.append(
                        f"Consider optimizing '{name}' - contributes {round(contribution, 1)}% of total time"
                    )
                
                if op_stats.call_count > 100 and op_stats.mean_time_ms > 5:
                    recommendations.append(
                        f"Consider caching results from '{name}' - called {op_stats.call_count} times"
                    )
        
        if memory_stats and memory_stats.get("peak_mb", 0) > 100:
            recommendations.append(
                f"High memory usage detected ({memory_stats['peak_mb']} MB) - consider streaming or batching"
            )
        
        return recommendations
    
    def get_stats(self, name: str) -> Optional[OperationStats]:
        """Get stats for a specific operation."""
        if name not in self._operation_timings:
            return None
        
        return OperationStats.from_timings(name, self._operation_timings[name])
    
    def get_report(self) -> ProfileReport:
        """Get current report without stopping."""
        end_time = time.time()
        start = self._start_time or end_time
        return self._generate_report(start, end_time)


class CPUProfiler:
    """
    CPU profiler using cProfile.
    """
    
    def __init__(self):
        self._profiler: Optional[cProfile.Profile] = None
        self._stats: Optional[pstats.Stats] = None
    
    def start(self) -> None:
        """Start CPU profiling."""
        self._profiler = cProfile.Profile()
        self._profiler.enable()
    
    def stop(self) -> pstats.Stats:
        """Stop profiling and get stats."""
        if self._profiler:
            self._profiler.disable()
            
            stream = io.StringIO()
            self._stats = pstats.Stats(self._profiler, stream=stream)
            
        return self._stats
    
    @contextmanager
    def profile(self):
        """Context manager for CPU profiling."""
        self.start()
        try:
            yield
        finally:
            self.stop()
    
    def get_top_functions(self, limit: int = 20) -> str:
        """Get top functions by cumulative time."""
        if not self._stats:
            return ""
        
        stream = io.StringIO()
        self._stats.stream = stream
        self._stats.sort_stats('cumulative')
        self._stats.print_stats(limit)
        
        return stream.getvalue()
    
    def get_callers(self, function_name: str) -> str:
        """Get callers of a function."""
        if not self._stats:
            return ""
        
        stream = io.StringIO()
        self._stats.stream = stream
        self._stats.print_callers(function_name)
        
        return stream.getvalue()


class MemoryProfiler:
    """
    Memory profiler using tracemalloc.
    """
    
    def __init__(self, top_n: int = 10):
        self._top_n = top_n
        self._snapshots: List[Tuple[str, Any]] = []
    
    def start(self) -> None:
        """Start memory profiling."""
        tracemalloc.start()
    
    def stop(self) -> None:
        """Stop memory profiling."""
        tracemalloc.stop()
    
    def take_snapshot(self, name: str = "snapshot") -> Any:
        """Take a memory snapshot."""
        snapshot = tracemalloc.take_snapshot()
        self._snapshots.append((name, snapshot))
        return snapshot
    
    def get_top_allocations(self) -> List[Dict[str, Any]]:
        """Get top memory allocations."""
        if not self._snapshots:
            snapshot = tracemalloc.take_snapshot()
        else:
            _, snapshot = self._snapshots[-1]
        
        top_stats = snapshot.statistics('lineno')[:self._top_n]
        
        return [
            {
                "file": str(stat.traceback),
                "size_kb": round(stat.size / 1024, 2),
                "count": stat.count,
            }
            for stat in top_stats
        ]
    
    def compare_snapshots(
        self,
        name1: str,
        name2: str,
    ) -> List[Dict[str, Any]]:
        """Compare two snapshots."""
        snap1 = None
        snap2 = None
        
        for name, snap in self._snapshots:
            if name == name1:
                snap1 = snap
            if name == name2:
                snap2 = snap
        
        if not snap1 or not snap2:
            return []
        
        diff = snap2.compare_to(snap1, 'lineno')[:self._top_n]
        
        return [
            {
                "file": str(stat.traceback),
                "size_diff_kb": round(stat.size_diff / 1024, 2),
                "count_diff": stat.count_diff,
            }
            for stat in diff
        ]
    
    @contextmanager
    def track(self):
        """Context manager for memory tracking."""
        self.start()
        self.take_snapshot("before")
        try:
            yield
        finally:
            self.take_snapshot("after")


# Global profiler instance
_profiler: Optional[Profiler] = None


def get_profiler(track_memory: bool = False) -> Profiler:
    """Get or create global profiler."""
    global _profiler
    if _profiler is None:
        _profiler = Profiler(track_memory=track_memory)
    return _profiler


def profile(
    name: Optional[str] = None,
    profiler: Optional[Profiler] = None,
) -> Callable:
    """
    Decorator to profile a function.
    
    Example:
        @profile(name="api_call")
        async def call_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        operation_name = name or func.__name__
        prof = profiler or get_profiler()
        
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            with prof.trace(operation_name):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with prof.trace(operation_name):
                return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def profile_memory(
    name: Optional[str] = None,
) -> Callable:
    """
    Decorator to profile memory usage.
    
    Example:
        @profile_memory()
        def memory_intensive_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        operation_name = name or func.__name__
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracemalloc.start()
            start_memory = tracemalloc.get_traced_memory()
            
            try:
                result = func(*args, **kwargs)
                
                current, peak = tracemalloc.get_traced_memory()
                allocated = current - start_memory[0]
                
                logger.debug(
                    f"{operation_name}: allocated={allocated/1024:.2f}KB, "
                    f"peak={peak/1024:.2f}KB"
                )
                
                return result
            finally:
                tracemalloc.stop()
        
        return wrapper
    
    return decorator


def timed(func: Callable) -> Callable:
    """
    Simple timing decorator.
    
    Example:
        @timed
        async def operation():
            ...
    """
    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.time()
        try:
            return await func(*args, **kwargs)
        finally:
            duration = (time.time() - start) * 1000
            logger.debug(f"{func.__name__} took {duration:.2f}ms")
    
    @wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            duration = (time.time() - start) * 1000
            logger.debug(f"{func.__name__} took {duration:.2f}ms")
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper


__all__ = [
    # Exceptions
    "ProfilerError",
    # Enums
    "MetricType",
    # Data classes
    "TimingRecord",
    "MemoryRecord",
    "OperationStats",
    "ProfileReport",
    # Profilers
    "Profiler",
    "CPUProfiler",
    "MemoryProfiler",
    # Decorators
    "profile",
    "profile_memory",
    "timed",
    # Utilities
    "get_profiler",
]
