"""
Infrastructure Types.

Common types, enums, and dataclasses for infrastructure.
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


class Region(Enum):
    """Supported regions."""
    US_EAST = "us-east"
    US_WEST = "us-west"
    EU_WEST = "eu-west"
    EU_CENTRAL = "eu-central"
    ASIA_PACIFIC = "asia-pacific"
    ASIA_SOUTH = "asia-south"
    AUSTRALIA = "australia"


@dataclass
class RegionConfig:
    """Configuration for a region."""
    region: Region
    endpoint: str
    is_primary: bool = False
    weight: float = 1.0
    latency_ms: float = 0
    health_status: str = "healthy"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Tenant:
    """Represents a tenant in multi-tenant system."""
    tenant_id: str
    name: str
    tier: str  # free, standard, premium, enterprise
    quota: Dict[str, int]
    metadata: Dict[str, Any]
    created_at: float
    status: str = "active"
    region: Optional[Region] = None
    isolation_level: str = "shared"  # shared, dedicated, isolated


@dataclass
class ServerlessFunction:
    """Represents a serverless function."""
    function_id: str
    name: str
    handler: Any  # Callable
    runtime: str
    memory_mb: int
    timeout_seconds: int
    environment: Dict[str, str]
    metadata: Dict[str, Any]
    created_at: float


@dataclass
class FunctionInvocation:
    """Records a function invocation."""
    invocation_id: str
    function_id: str
    input_data: Any
    output_data: Any
    status: str
    start_time: float
    end_time: float
    memory_used_mb: float
    billed_duration_ms: float


__all__ = [
    'Region',
    'RegionConfig',
    'Tenant',
    'ServerlessFunction',
    'FunctionInvocation',
]
