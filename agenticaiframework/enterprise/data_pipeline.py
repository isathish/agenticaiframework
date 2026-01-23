"""
Enterprise Data Pipeline Module.

ETL (Extract, Transform, Load), streaming, and batch
data processing with stages and transformations.

Example:
    # Create data pipeline
    pipeline = create_data_pipeline("user_etl")
    
    # Define stages
    pipeline.extract(sql_source("SELECT * FROM users"))
    pipeline.transform(filter_nulls("email"))
    pipeline.transform(normalize_email)
    pipeline.load(parquet_sink("/data/users/"))
    
    # Run pipeline
    result = await pipeline.run()
    
    # With decorator
    @pipeline.stage("transform")
    def clean_data(record):
        return {**record, "name": record["name"].strip()}
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import time
import uuid
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
    Generator,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')
S = TypeVar('S')


logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Pipeline error."""
    pass


class StageError(PipelineError):
    """Stage error."""
    pass


class TransformError(PipelineError):
    """Transform error."""
    pass


class ValidationError(PipelineError):
    """Validation error."""
    pass


class StageType(str, Enum):
    """Stage types."""
    EXTRACT = "extract"
    TRANSFORM = "transform"
    LOAD = "load"
    FILTER = "filter"
    VALIDATE = "validate"
    AGGREGATE = "aggregate"
    JOIN = "join"
    SPLIT = "split"


class PipelineStatus(str, Enum):
    """Pipeline status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ErrorHandling(str, Enum):
    """Error handling strategies."""
    STOP = "stop"
    SKIP = "skip"
    RETRY = "retry"
    DEAD_LETTER = "dead_letter"


@dataclass
class StageConfig:
    """Stage configuration."""
    name: str
    stage_type: StageType
    parallelism: int = 1
    batch_size: int = 1000
    timeout: float = 300.0
    retries: int = 3
    error_handling: ErrorHandling = ErrorHandling.SKIP


@dataclass
class StageMetrics:
    """Stage metrics."""
    records_in: int = 0
    records_out: int = 0
    records_failed: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class PipelineMetrics:
    """Pipeline metrics."""
    total_records: int = 0
    successful_records: int = 0
    failed_records: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    stage_metrics: Dict[str, StageMetrics] = field(default_factory=dict)


@dataclass
class PipelineRun:
    """Pipeline run info."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_name: str = ""
    status: PipelineStatus = PipelineStatus.PENDING
    metrics: PipelineMetrics = field(default_factory=PipelineMetrics)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class Record:
    """Data record wrapper."""
    data: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


# Stage interface
class Stage(ABC, Generic[T, S]):
    """Abstract pipeline stage."""
    
    def __init__(
        self,
        name: str,
        config: Optional[StageConfig] = None,
    ):
        self.name = name
        self.config = config or StageConfig(
            name=name,
            stage_type=StageType.TRANSFORM,
        )
        self.metrics = StageMetrics()
    
    @abstractmethod
    async def process(self, record: T) -> Optional[S]:
        """Process single record."""
        pass
    
    async def process_batch(self, records: List[T]) -> List[S]:
        """Process batch of records."""
        results = []
        for record in records:
            try:
                result = await self.process(record)
                if result is not None:
                    results.append(result)
                    self.metrics.records_out += 1
                self.metrics.records_in += 1
            except Exception as e:
                self.metrics.records_failed += 1
                self.metrics.errors.append(str(e))
                
                if self.config.error_handling == ErrorHandling.STOP:
                    raise
        
        return results


# Source stages
class Source(ABC):
    """Abstract data source."""
    
    @abstractmethod
    async def read(self) -> AsyncIterator[Record]:
        """Read records from source."""
        pass
    
    async def count(self) -> Optional[int]:
        """Get total record count if available."""
        return None


class ListSource(Source):
    """List data source."""
    
    def __init__(self, data: List[Any]):
        self._data = data
    
    async def read(self) -> AsyncIterator[Record]:
        for item in self._data:
            yield Record(data=item)
    
    async def count(self) -> Optional[int]:
        return len(self._data)


class GeneratorSource(Source):
    """Generator data source."""
    
    def __init__(self, generator: Callable[[], Iterator[Any]]):
        self._generator = generator
    
    async def read(self) -> AsyncIterator[Record]:
        for item in self._generator():
            yield Record(data=item)


class FileSource(Source):
    """File data source."""
    
    def __init__(
        self,
        path: str,
        format: str = "json",
        batch_size: int = 1000,
    ):
        self._path = path
        self._format = format
        self._batch_size = batch_size
    
    async def read(self) -> AsyncIterator[Record]:
        # Mock file reading
        yield Record(data={"file": self._path, "format": self._format})


# Sink stages
class Sink(ABC):
    """Abstract data sink."""
    
    @abstractmethod
    async def write(self, record: Record) -> None:
        """Write single record."""
        pass
    
    async def write_batch(self, records: List[Record]) -> int:
        """Write batch of records."""
        count = 0
        for record in records:
            await self.write(record)
            count += 1
        return count
    
    async def flush(self) -> None:
        """Flush pending writes."""
        pass
    
    async def close(self) -> None:
        """Close sink."""
        pass


class ListSink(Sink):
    """List data sink."""
    
    def __init__(self):
        self.records: List[Any] = []
    
    async def write(self, record: Record) -> None:
        self.records.append(record.data)


class FileSink(Sink):
    """File data sink."""
    
    def __init__(
        self,
        path: str,
        format: str = "json",
        batch_size: int = 1000,
    ):
        self._path = path
        self._format = format
        self._batch_size = batch_size
        self._buffer: List[Any] = []
    
    async def write(self, record: Record) -> None:
        self._buffer.append(record.data)
        
        if len(self._buffer) >= self._batch_size:
            await self.flush()
    
    async def flush(self) -> None:
        if self._buffer:
            # Mock file writing
            logger.info(f"Writing {len(self._buffer)} records to {self._path}")
            self._buffer.clear()


class ConsoleSink(Sink):
    """Console data sink."""
    
    async def write(self, record: Record) -> None:
        print(json.dumps(record.data, default=str))


# Transform stages
class Transform(Stage[Record, Record]):
    """Transform stage."""
    
    def __init__(
        self,
        name: str,
        func: Callable[[Any], Any],
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self._func = func
        self.config.stage_type = StageType.TRANSFORM
    
    async def process(self, record: Record) -> Optional[Record]:
        if asyncio.iscoroutinefunction(self._func):
            result = await self._func(record.data)
        else:
            result = self._func(record.data)
        
        if result is None:
            return None
        
        return Record(
            data=result,
            metadata=record.metadata,
            source=record.source,
        )


class Filter(Stage[Record, Record]):
    """Filter stage."""
    
    def __init__(
        self,
        name: str,
        predicate: Callable[[Any], bool],
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self._predicate = predicate
        self.config.stage_type = StageType.FILTER
    
    async def process(self, record: Record) -> Optional[Record]:
        if asyncio.iscoroutinefunction(self._predicate):
            keep = await self._predicate(record.data)
        else:
            keep = self._predicate(record.data)
        
        return record if keep else None


class Validator(Stage[Record, Record]):
    """Validation stage."""
    
    def __init__(
        self,
        name: str,
        schema: Dict[str, Any],
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self._schema = schema
        self.config.stage_type = StageType.VALIDATE
    
    async def process(self, record: Record) -> Optional[Record]:
        # Simple schema validation
        data = record.data
        
        if not isinstance(data, dict):
            raise ValidationError("Record must be a dictionary")
        
        for field, field_type in self._schema.items():
            if field not in data:
                if field_type.get("required", False):
                    raise ValidationError(f"Missing required field: {field}")
            else:
                # Type checking could be added here
                pass
        
        return record


class Aggregator(Stage[List[Record], Record]):
    """Aggregation stage."""
    
    def __init__(
        self,
        name: str,
        key_func: Callable[[Any], str],
        agg_func: Callable[[List[Any]], Any],
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self._key_func = key_func
        self._agg_func = agg_func
        self._groups: Dict[str, List[Any]] = defaultdict(list)
        self.config.stage_type = StageType.AGGREGATE
    
    async def process(self, record: Record) -> Optional[Record]:
        # Collect records for aggregation
        key = self._key_func(record.data)
        self._groups[key].append(record.data)
        return None  # Will emit during flush
    
    async def flush(self) -> List[Record]:
        """Flush aggregated records."""
        results = []
        
        for key, values in self._groups.items():
            agg_result = self._agg_func(values)
            results.append(Record(
                data={"key": key, "value": agg_result},
            ))
        
        self._groups.clear()
        return results


# Pipeline
class DataPipeline:
    """
    Data pipeline.
    """
    
    def __init__(
        self,
        name: str,
        batch_size: int = 1000,
        parallelism: int = 1,
        error_handling: ErrorHandling = ErrorHandling.SKIP,
    ):
        self.name = name
        self._batch_size = batch_size
        self._parallelism = parallelism
        self._error_handling = error_handling
        self._source: Optional[Source] = None
        self._stages: List[Stage] = []
        self._sink: Optional[Sink] = None
        self._dead_letter: Optional[Sink] = None
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
        self._runs: Dict[str, PipelineRun] = {}
    
    def extract(self, source: Source) -> "DataPipeline":
        """Set source."""
        self._source = source
        return self
    
    def transform(
        self,
        func: Callable[[Any], Any],
        name: Optional[str] = None,
    ) -> "DataPipeline":
        """Add transform stage."""
        stage_name = name or f"transform_{len(self._stages)}"
        self._stages.append(Transform(stage_name, func))
        return self
    
    def filter(
        self,
        predicate: Callable[[Any], bool],
        name: Optional[str] = None,
    ) -> "DataPipeline":
        """Add filter stage."""
        stage_name = name or f"filter_{len(self._stages)}"
        self._stages.append(Filter(stage_name, predicate))
        return self
    
    def validate(
        self,
        schema: Dict[str, Any],
        name: Optional[str] = None,
    ) -> "DataPipeline":
        """Add validation stage."""
        stage_name = name or f"validate_{len(self._stages)}"
        self._stages.append(Validator(stage_name, schema))
        return self
    
    def add_stage(self, stage: Stage) -> "DataPipeline":
        """Add custom stage."""
        self._stages.append(stage)
        return self
    
    def load(self, sink: Sink) -> "DataPipeline":
        """Set sink."""
        self._sink = sink
        return self
    
    def dead_letter(self, sink: Sink) -> "DataPipeline":
        """Set dead letter sink."""
        self._dead_letter = sink
        return self
    
    def on(self, event: str, handler: Callable) -> "DataPipeline":
        """Add event handler."""
        self._hooks[event].append(handler)
        return self
    
    async def _trigger(self, event: str, *args, **kwargs) -> None:
        """Trigger event handlers."""
        for handler in self._hooks[event]:
            if asyncio.iscoroutinefunction(handler):
                await handler(*args, **kwargs)
            else:
                handler(*args, **kwargs)
    
    async def run(self) -> PipelineRun:
        """
        Run pipeline.
        
        Returns:
            Pipeline run info
        """
        if not self._source:
            raise PipelineError("No source configured")
        
        if not self._sink:
            raise PipelineError("No sink configured")
        
        run = PipelineRun(
            pipeline_name=self.name,
            status=PipelineStatus.RUNNING,
            started_at=datetime.utcnow(),
        )
        run.metrics.start_time = run.started_at
        
        self._runs[run.id] = run
        
        await self._trigger("start", run)
        
        try:
            batch: List[Record] = []
            
            async for record in self._source.read():
                batch.append(record)
                run.metrics.total_records += 1
                
                if len(batch) >= self._batch_size:
                    await self._process_batch(batch, run)
                    batch.clear()
            
            # Process remaining
            if batch:
                await self._process_batch(batch, run)
            
            # Flush sink
            await self._sink.flush()
            
            run.status = PipelineStatus.COMPLETED
            
        except Exception as e:
            run.status = PipelineStatus.FAILED
            run.error = str(e)
            logger.error(f"Pipeline failed: {e}")
            
        finally:
            run.completed_at = datetime.utcnow()
            run.metrics.end_time = run.completed_at
            
            if run.metrics.start_time and run.metrics.end_time:
                run.metrics.duration_seconds = (
                    run.metrics.end_time - run.metrics.start_time
                ).total_seconds()
            
            await self._sink.close()
            await self._trigger("complete", run)
        
        return run
    
    async def _process_batch(
        self,
        batch: List[Record],
        run: PipelineRun,
    ) -> None:
        """Process batch through stages."""
        records = batch
        
        for stage in self._stages:
            stage.metrics.start_time = datetime.utcnow()
            
            try:
                records = await stage.process_batch(records)
            except Exception as e:
                logger.error(f"Stage {stage.name} failed: {e}")
                
                if self._error_handling == ErrorHandling.STOP:
                    raise
                elif self._error_handling == ErrorHandling.DEAD_LETTER:
                    if self._dead_letter:
                        for record in records:
                            await self._dead_letter.write(record)
                    records = []
            
            stage.metrics.end_time = datetime.utcnow()
            
            if stage.metrics.start_time and stage.metrics.end_time:
                stage.metrics.duration_seconds = (
                    stage.metrics.end_time - stage.metrics.start_time
                ).total_seconds()
            
            run.metrics.stage_metrics[stage.name] = stage.metrics
        
        # Write to sink
        for record in records:
            try:
                await self._sink.write(record)
                run.metrics.successful_records += 1
            except Exception as e:
                run.metrics.failed_records += 1
                
                if self._dead_letter:
                    record.metadata["error"] = str(e)
                    await self._dead_letter.write(record)
    
    async def validate_pipeline(self) -> List[str]:
        """Validate pipeline configuration."""
        errors = []
        
        if not self._source:
            errors.append("No source configured")
        
        if not self._sink:
            errors.append("No sink configured")
        
        if not self._stages:
            errors.append("No transform stages configured")
        
        return errors
    
    def get_run(self, run_id: str) -> Optional[PipelineRun]:
        """Get pipeline run by ID."""
        return self._runs.get(run_id)
    
    def get_runs(self) -> List[PipelineRun]:
        """Get all pipeline runs."""
        return list(self._runs.values())
    
    def stage(
        self,
        stage_type: str = "transform",
        name: Optional[str] = None,
    ) -> Callable:
        """
        Decorator to add function as stage.
        
        Args:
            stage_type: Stage type
            name: Stage name
            
        Returns:
            Decorator
        """
        def decorator(func: Callable) -> Callable:
            stage_name = name or func.__name__
            
            if stage_type == "transform":
                self.transform(func, stage_name)
            elif stage_type == "filter":
                self.filter(func, stage_name)
            
            return func
        
        return decorator


# Built-in transforms
def map_fields(mapping: Dict[str, str]) -> Callable:
    """Create field mapping transform."""
    def transform(data: Dict) -> Dict:
        return {
            new_key: data.get(old_key)
            for old_key, new_key in mapping.items()
        }
    return transform


def filter_nulls(*fields: str) -> Callable:
    """Create null filter."""
    def predicate(data: Dict) -> bool:
        for field in fields:
            if data.get(field) is None:
                return False
        return True
    return predicate


def add_timestamp(field: str = "timestamp") -> Callable:
    """Add timestamp to records."""
    def transform(data: Dict) -> Dict:
        return {**data, field: datetime.utcnow().isoformat()}
    return transform


def flatten(prefix: str = "", separator: str = "_") -> Callable:
    """Flatten nested dictionaries."""
    def transform(data: Dict, _prefix: str = "") -> Dict:
        result = {}
        for key, value in data.items():
            new_key = f"{_prefix}{separator}{key}" if _prefix else key
            
            if isinstance(value, dict):
                result.update(transform(value, new_key))
            else:
                result[new_key] = value
        
        return result
    
    return lambda d: transform(d, prefix)


# Factory functions
def create_data_pipeline(
    name: str,
    batch_size: int = 1000,
    **kwargs,
) -> DataPipeline:
    """Create data pipeline."""
    return DataPipeline(name=name, batch_size=batch_size, **kwargs)


def create_list_source(data: List[Any]) -> ListSource:
    """Create list source."""
    return ListSource(data)


def create_file_source(
    path: str,
    format: str = "json",
    **kwargs,
) -> FileSource:
    """Create file source."""
    return FileSource(path=path, format=format, **kwargs)


def create_list_sink() -> ListSink:
    """Create list sink."""
    return ListSink()


def create_file_sink(
    path: str,
    format: str = "json",
    **kwargs,
) -> FileSink:
    """Create file sink."""
    return FileSink(path=path, format=format, **kwargs)


__all__ = [
    # Exceptions
    "PipelineError",
    "StageError",
    "TransformError",
    "ValidationError",
    # Enums
    "StageType",
    "PipelineStatus",
    "ErrorHandling",
    # Data classes
    "StageConfig",
    "StageMetrics",
    "PipelineMetrics",
    "PipelineRun",
    "Record",
    # Stage base
    "Stage",
    # Sources
    "Source",
    "ListSource",
    "GeneratorSource",
    "FileSource",
    # Sinks
    "Sink",
    "ListSink",
    "FileSink",
    "ConsoleSink",
    # Stages
    "Transform",
    "Filter",
    "Validator",
    "Aggregator",
    # Pipeline
    "DataPipeline",
    # Built-in transforms
    "map_fields",
    "filter_nulls",
    "add_timestamp",
    "flatten",
    # Factory functions
    "create_data_pipeline",
    "create_list_source",
    "create_file_source",
    "create_list_sink",
    "create_file_sink",
]
