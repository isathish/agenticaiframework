"""
Infrastructure Package.

Enterprise infrastructure functionality for AI agents:
- Multi-Region Support
- Tenant Isolation
- Serverless Execution
- Distributed Coordination
"""

from .types import (
    Region,
    RegionConfig,
    Tenant,
    ServerlessFunction,
    FunctionInvocation,
)
from .multi_region import MultiRegionManager
from .tenant import TenantManager
from .serverless import ServerlessExecutor
from .coordinator import DistributedCoordinator

# Global instances
multi_region_manager = MultiRegionManager()
tenant_manager = TenantManager()
serverless_executor = ServerlessExecutor()
distributed_coordinator = DistributedCoordinator()

__all__ = [
    # Types
    'Region',
    'RegionConfig',
    'Tenant',
    'ServerlessFunction',
    'FunctionInvocation',
    # Classes
    'MultiRegionManager',
    'TenantManager',
    'ServerlessExecutor',
    'DistributedCoordinator',
    # Global instances
    'multi_region_manager',
    'tenant_manager',
    'serverless_executor',
    'distributed_coordinator',
]
