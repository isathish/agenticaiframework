"""
Enterprise Export/Import Service Module.

Data migration, bulk operations, transformations,
and data management.

Example:
    # Create export/import service
    service = create_data_service()
    
    # Export data
    export_job = await service.export(
        format=ExportFormat.JSON,
        data_source="users",
        query={"active": True},
    )
    
    # Import data
    import_job = await service.import_data(
        format=ImportFormat.CSV,
        data=csv_content,
        target="users",
        mappings={"email_address": "email"},
    )
    
    # Track job status
    status = await service.get_job_status(import_job.id)
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class DataServiceError(Exception):
    """Data service error."""
    pass


class ValidationError(DataServiceError):
    """Validation error."""
    pass


class TransformError(DataServiceError):
    """Transform error."""
    pass


class ExportFormat(str, Enum):
    """Export format."""
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    YAML = "yaml"
    NDJSON = "ndjson"


class ImportFormat(str, Enum):
    """Import format."""
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    YAML = "yaml"
    NDJSON = "ndjson"


class JobStatus(str, Enum):
    """Job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class JobType(str, Enum):
    """Job type."""
    EXPORT = "export"
    IMPORT = "import"
    TRANSFORM = "transform"
    MIGRATE = "migrate"
    SYNC = "sync"


@dataclass
class FieldMapping:
    """Field mapping."""
    source: str = ""
    target: str = ""
    transform: Optional[str] = None
    default: Any = None
    required: bool = False


@dataclass
class ValidationRule:
    """Validation rule."""
    field: str = ""
    rule: str = ""  # required, email, min_length, max_length, regex, type
    params: Dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass
class TransformRule:
    """Transform rule."""
    field: str = ""
    operation: str = ""  # uppercase, lowercase, trim, date_format, etc.
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataJob:
    """Data job."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: JobType = JobType.EXPORT
    status: JobStatus = JobStatus.PENDING
    source: str = ""
    target: str = ""
    format: str = ""
    total_records: int = 0
    processed_records: int = 0
    success_count: int = 0
    failure_count: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    result_data: Optional[bytes] = None
    result_url: str = ""
    mappings: List[FieldMapping] = field(default_factory=list)
    validations: List[ValidationRule] = field(default_factory=list)
    transforms: List[TransformRule] = field(default_factory=list)
    options: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataStats:
    """Data service statistics."""
    total_jobs: int = 0
    export_jobs: int = 0
    import_jobs: int = 0
    total_records_processed: int = 0


# Data source interface
class DataSource(ABC):
    """Data source."""
    
    @abstractmethod
    async def fetch(self, query: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    async def insert(self, records: List[Dict[str, Any]]) -> int:
        pass
    
    @abstractmethod
    async def count(self, query: Dict[str, Any] = None) -> int:
        pass


class InMemoryDataSource(DataSource):
    """In-memory data source."""
    
    def __init__(self, data: List[Dict[str, Any]] = None):
        self._data = data or []
    
    async def fetch(self, query: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        if not query:
            return list(self._data)
        
        results = []
        for record in self._data:
            match = all(record.get(k) == v for k, v in query.items())
            if match:
                results.append(record)
        
        return results
    
    async def insert(self, records: List[Dict[str, Any]]) -> int:
        self._data.extend(records)
        return len(records)
    
    async def count(self, query: Dict[str, Any] = None) -> int:
        return len(await self.fetch(query))


# Job store
class JobStore(ABC):
    """Job storage."""
    
    @abstractmethod
    async def save(self, job: DataJob) -> None:
        pass
    
    @abstractmethod
    async def get(self, job_id: str) -> Optional[DataJob]:
        pass
    
    @abstractmethod
    async def list(self, type: Optional[JobType] = None) -> List[DataJob]:
        pass


class InMemoryJobStore(JobStore):
    """In-memory job store."""
    
    def __init__(self):
        self._jobs: Dict[str, DataJob] = {}
    
    async def save(self, job: DataJob) -> None:
        self._jobs[job.id] = job
    
    async def get(self, job_id: str) -> Optional[DataJob]:
        return self._jobs.get(job_id)
    
    async def list(self, type: Optional[JobType] = None) -> List[DataJob]:
        jobs = list(self._jobs.values())
        if type:
            jobs = [j for j in jobs if j.type == type]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)


# Transformers
class DataTransformer:
    """Data transformer."""
    
    OPERATIONS = {
        "uppercase": lambda v, p: str(v).upper() if v else v,
        "lowercase": lambda v, p: str(v).lower() if v else v,
        "trim": lambda v, p: str(v).strip() if v else v,
        "prefix": lambda v, p: f"{p.get('value', '')}{v}" if v else v,
        "suffix": lambda v, p: f"{v}{p.get('value', '')}" if v else v,
        "replace": lambda v, p: str(v).replace(p.get("old", ""), p.get("new", "")) if v else v,
        "default": lambda v, p: v if v is not None else p.get("value"),
        "int": lambda v, p: int(v) if v else None,
        "float": lambda v, p: float(v) if v else None,
        "bool": lambda v, p: str(v).lower() in ("true", "1", "yes") if v else False,
        "split": lambda v, p: str(v).split(p.get("delimiter", ",")) if v else [],
        "join": lambda v, p: p.get("delimiter", ",").join(v) if isinstance(v, list) else v,
    }
    
    def transform(
        self,
        record: Dict[str, Any],
        rules: List[TransformRule],
    ) -> Dict[str, Any]:
        """Transform record."""
        result = dict(record)
        
        for rule in rules:
            if rule.field in result:
                operation = self.OPERATIONS.get(rule.operation)
                if operation:
                    try:
                        result[rule.field] = operation(result[rule.field], rule.params)
                    except Exception as e:
                        logger.warning(f"Transform error: {e}")
        
        return result
    
    def map_fields(
        self,
        record: Dict[str, Any],
        mappings: List[FieldMapping],
    ) -> Dict[str, Any]:
        """Map fields."""
        result = {}
        
        for mapping in mappings:
            value = record.get(mapping.source, mapping.default)
            
            if mapping.transform and value is not None:
                operation = self.OPERATIONS.get(mapping.transform)
                if operation:
                    value = operation(value, {})
            
            result[mapping.target] = value
        
        return result


# Validator
class DataValidator:
    """Data validator."""
    
    def validate(
        self,
        record: Dict[str, Any],
        rules: List[ValidationRule],
    ) -> List[str]:
        """Validate record."""
        errors = []
        
        for rule in rules:
            value = record.get(rule.field)
            
            if rule.rule == "required":
                if value is None or value == "":
                    errors.append(rule.message or f"{rule.field} is required")
            
            elif rule.rule == "email" and value:
                if "@" not in str(value):
                    errors.append(rule.message or f"{rule.field} is not a valid email")
            
            elif rule.rule == "min_length" and value:
                min_len = rule.params.get("length", 0)
                if len(str(value)) < min_len:
                    errors.append(rule.message or f"{rule.field} must be at least {min_len} characters")
            
            elif rule.rule == "max_length" and value:
                max_len = rule.params.get("length", 0)
                if len(str(value)) > max_len:
                    errors.append(rule.message or f"{rule.field} must be at most {max_len} characters")
            
            elif rule.rule == "type" and value is not None:
                expected_type = rule.params.get("type", "str")
                if expected_type == "int" and not isinstance(value, int):
                    try:
                        int(value)
                    except:
                        errors.append(rule.message or f"{rule.field} must be an integer")
                elif expected_type == "float" and not isinstance(value, (int, float)):
                    try:
                        float(value)
                    except:
                        errors.append(rule.message or f"{rule.field} must be a number")
        
        return errors


# Export/Import service
class DataService:
    """Data service."""
    
    def __init__(
        self,
        job_store: Optional[JobStore] = None,
        transformer: Optional[DataTransformer] = None,
        validator: Optional[DataValidator] = None,
    ):
        self._jobs = job_store or InMemoryJobStore()
        self._transformer = transformer or DataTransformer()
        self._validator = validator or DataValidator()
        self._sources: Dict[str, DataSource] = {}
        self._stats = DataStats()
    
    def register_source(self, name: str, source: DataSource) -> None:
        """Register data source."""
        self._sources[name] = source
    
    async def export(
        self,
        data_source: str,
        format: ExportFormat = ExportFormat.JSON,
        query: Dict[str, Any] = None,
        fields: List[str] = None,
        transforms: List[TransformRule] = None,
        created_by: str = "",
    ) -> DataJob:
        """Export data."""
        source = self._sources.get(data_source)
        if not source:
            raise DataServiceError(f"Unknown data source: {data_source}")
        
        job = DataJob(
            type=JobType.EXPORT,
            source=data_source,
            format=format.value,
            transforms=transforms or [],
            created_by=created_by,
            options={"query": query, "fields": fields},
        )
        
        await self._jobs.save(job)
        
        # Execute export
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        await self._jobs.save(job)
        
        try:
            records = await source.fetch(query)
            job.total_records = len(records)
            
            # Apply transforms
            if transforms:
                records = [self._transformer.transform(r, transforms) for r in records]
            
            # Filter fields
            if fields:
                records = [{k: r.get(k) for k in fields} for r in records]
            
            # Convert to output format
            job.result_data = self._serialize(records, format)
            job.processed_records = len(records)
            job.success_count = len(records)
            job.status = JobStatus.COMPLETED
        
        except Exception as e:
            job.status = JobStatus.FAILED
            job.errors.append(str(e))
        
        job.completed_at = datetime.utcnow()
        await self._jobs.save(job)
        
        self._stats.total_jobs += 1
        self._stats.export_jobs += 1
        self._stats.total_records_processed += job.processed_records
        
        logger.info(f"Export completed: {job.processed_records} records")
        
        return job
    
    def _serialize(
        self,
        records: List[Dict[str, Any]],
        format: ExportFormat,
    ) -> bytes:
        """Serialize records."""
        if format == ExportFormat.JSON:
            return json.dumps(records, indent=2, default=str).encode('utf-8')
        
        elif format == ExportFormat.NDJSON:
            lines = [json.dumps(r, default=str) for r in records]
            return '\n'.join(lines).encode('utf-8')
        
        elif format == ExportFormat.CSV:
            if not records:
                return b""
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
            return output.getvalue().encode('utf-8')
        
        else:
            return json.dumps(records, default=str).encode('utf-8')
    
    async def import_data(
        self,
        data: Union[str, bytes],
        target: str,
        format: ImportFormat = ImportFormat.JSON,
        mappings: List[FieldMapping] = None,
        validations: List[ValidationRule] = None,
        transforms: List[TransformRule] = None,
        skip_errors: bool = True,
        created_by: str = "",
    ) -> DataJob:
        """Import data."""
        source = self._sources.get(target)
        if not source:
            raise DataServiceError(f"Unknown target: {target}")
        
        job = DataJob(
            type=JobType.IMPORT,
            target=target,
            format=format.value,
            mappings=mappings or [],
            validations=validations or [],
            transforms=transforms or [],
            created_by=created_by,
            options={"skip_errors": skip_errors},
        )
        
        await self._jobs.save(job)
        
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        await self._jobs.save(job)
        
        try:
            # Parse input
            records = self._deserialize(data, format)
            job.total_records = len(records)
            
            valid_records = []
            
            for i, record in enumerate(records):
                # Apply mappings
                if mappings:
                    record = self._transformer.map_fields(record, mappings)
                
                # Apply transforms
                if transforms:
                    record = self._transformer.transform(record, transforms)
                
                # Validate
                if validations:
                    errors = self._validator.validate(record, validations)
                    if errors:
                        job.failure_count += 1
                        job.errors.append(f"Row {i + 1}: {', '.join(errors)}")
                        if not skip_errors:
                            raise ValidationError(f"Validation failed: {errors}")
                        continue
                
                valid_records.append(record)
                job.success_count += 1
            
            # Insert valid records
            if valid_records:
                await source.insert(valid_records)
            
            job.processed_records = len(records)
            job.status = JobStatus.COMPLETED
        
        except Exception as e:
            job.status = JobStatus.FAILED
            job.errors.append(str(e))
        
        job.completed_at = datetime.utcnow()
        await self._jobs.save(job)
        
        self._stats.total_jobs += 1
        self._stats.import_jobs += 1
        self._stats.total_records_processed += job.processed_records
        
        logger.info(f"Import completed: {job.success_count}/{job.total_records} records")
        
        return job
    
    def _deserialize(
        self,
        data: Union[str, bytes],
        format: ImportFormat,
    ) -> List[Dict[str, Any]]:
        """Deserialize data."""
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        
        if format == ImportFormat.JSON:
            parsed = json.loads(data)
            return parsed if isinstance(parsed, list) else [parsed]
        
        elif format == ImportFormat.NDJSON:
            return [json.loads(line) for line in data.strip().split('\n') if line]
        
        elif format == ImportFormat.CSV:
            reader = csv.DictReader(io.StringIO(data))
            return list(reader)
        
        else:
            return json.loads(data)
    
    async def get_job_status(self, job_id: str) -> Optional[DataJob]:
        """Get job status."""
        return await self._jobs.get(job_id)
    
    async def list_jobs(
        self,
        type: Optional[JobType] = None,
    ) -> List[DataJob]:
        """List jobs."""
        return await self._jobs.list(type)
    
    async def cancel_job(self, job_id: str) -> Optional[DataJob]:
        """Cancel job."""
        job = await self._jobs.get(job_id)
        if not job:
            return None
        
        if job.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.PAUSED):
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            await self._jobs.save(job)
        
        return job
    
    def get_stats(self) -> DataStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_data_service() -> DataService:
    """Create data service."""
    return DataService()


def create_field_mapping(
    source: str,
    target: str,
    **kwargs,
) -> FieldMapping:
    """Create field mapping."""
    return FieldMapping(source=source, target=target, **kwargs)


def create_validation_rule(
    field: str,
    rule: str,
    **kwargs,
) -> ValidationRule:
    """Create validation rule."""
    return ValidationRule(field=field, rule=rule, **kwargs)


def create_transform_rule(
    field: str,
    operation: str,
    **kwargs,
) -> TransformRule:
    """Create transform rule."""
    return TransformRule(field=field, operation=operation, **kwargs)


__all__ = [
    # Exceptions
    "DataServiceError",
    "ValidationError",
    "TransformError",
    # Enums
    "ExportFormat",
    "ImportFormat",
    "JobStatus",
    "JobType",
    # Data classes
    "FieldMapping",
    "ValidationRule",
    "TransformRule",
    "DataJob",
    "DataStats",
    # Data source
    "DataSource",
    "InMemoryDataSource",
    # Job store
    "JobStore",
    "InMemoryJobStore",
    # Transformers
    "DataTransformer",
    "DataValidator",
    # Service
    "DataService",
    # Factory functions
    "create_data_service",
    "create_field_mapping",
    "create_validation_rule",
    "create_transform_rule",
]
