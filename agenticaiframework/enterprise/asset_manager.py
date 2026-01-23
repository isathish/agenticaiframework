"""
Enterprise Asset Manager Module.

IT asset lifecycle management, inventory tracking,
depreciation, and maintenance scheduling.

Example:
    # Create asset manager
    assets = create_asset_manager()
    
    # Add asset
    asset = await assets.add(
        name="Server-001",
        asset_type=AssetType.SERVER,
        category=AssetCategory.HARDWARE,
        cost=10000.00,
    )
    
    # Assign to user
    await assets.assign(asset.id, assignee="user@example.com")
    
    # Schedule maintenance
    await assets.schedule_maintenance(
        asset.id,
        maintenance_type="Annual checkup",
        scheduled_for=datetime.utcnow() + timedelta(days=30),
    )
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)

logger = logging.getLogger(__name__)


class AssetError(Exception):
    """Asset error."""
    pass


class AssetType(str, Enum):
    """Asset type."""
    SERVER = "server"
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    MONITOR = "monitor"
    PRINTER = "printer"
    NETWORK = "network"
    STORAGE = "storage"
    SOFTWARE = "software"
    LICENSE = "license"
    MOBILE = "mobile"
    PERIPHERAL = "peripheral"
    OTHER = "other"


class AssetCategory(str, Enum):
    """Asset category."""
    HARDWARE = "hardware"
    SOFTWARE = "software"
    INFRASTRUCTURE = "infrastructure"
    CLOUD = "cloud"
    SERVICE = "service"


class AssetStatus(str, Enum):
    """Asset status."""
    AVAILABLE = "available"
    ASSIGNED = "assigned"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    RESERVED = "reserved"
    RETIRED = "retired"
    DISPOSED = "disposed"
    LOST = "lost"


class MaintenanceStatus(str, Enum):
    """Maintenance status."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class DepreciationMethod(str, Enum):
    """Depreciation method."""
    STRAIGHT_LINE = "straight_line"
    DECLINING_BALANCE = "declining_balance"
    SUM_OF_YEARS = "sum_of_years"


@dataclass
class Asset:
    """Asset."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    asset_tag: str = ""
    serial_number: str = ""
    
    # Classification
    asset_type: AssetType = AssetType.OTHER
    category: AssetCategory = AssetCategory.HARDWARE
    status: AssetStatus = AssetStatus.AVAILABLE
    
    # Assignment
    assignee: str = ""
    department: str = ""
    location: str = ""
    
    # Financial
    cost: float = 0.0
    current_value: float = 0.0
    salvage_value: float = 0.0
    depreciation_method: DepreciationMethod = DepreciationMethod.STRAIGHT_LINE
    useful_life_years: int = 5
    
    # Dates
    purchase_date: Optional[datetime] = None
    warranty_expires: Optional[datetime] = None
    last_maintenance: Optional[datetime] = None
    next_maintenance: Optional[datetime] = None
    retired_date: Optional[datetime] = None
    
    # Vendor
    vendor: str = ""
    vendor_contact: str = ""
    
    # Metadata
    description: str = ""
    notes: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    
    # Audit
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""


@dataclass
class MaintenanceRecord:
    """Maintenance record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset_id: str = ""
    maintenance_type: str = ""
    description: str = ""
    status: MaintenanceStatus = MaintenanceStatus.SCHEDULED
    
    # Schedule
    scheduled_for: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Cost
    cost: float = 0.0
    
    # Personnel
    technician: str = ""
    notes: str = ""
    
    # Result
    issues_found: List[str] = field(default_factory=list)
    actions_taken: List[str] = field(default_factory=list)


@dataclass
class AssetTransfer:
    """Asset transfer record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    asset_id: str = ""
    from_assignee: str = ""
    to_assignee: str = ""
    from_location: str = ""
    to_location: str = ""
    transferred_at: datetime = field(default_factory=datetime.utcnow)
    transferred_by: str = ""
    reason: str = ""


@dataclass
class Depreciation:
    """Depreciation calculation."""
    asset_id: str = ""
    original_cost: float = 0.0
    current_value: float = 0.0
    accumulated: float = 0.0
    annual_amount: float = 0.0
    remaining_life_years: float = 0.0


@dataclass
class AssetStats:
    """Asset statistics."""
    total_assets: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)
    by_category: Dict[str, int] = field(default_factory=dict)
    by_type: Dict[str, int] = field(default_factory=dict)
    total_value: float = 0.0
    total_cost: float = 0.0
    maintenance_due: int = 0
    warranty_expiring: int = 0


# Asset store
class AssetStore(ABC):
    """Asset storage."""
    
    @abstractmethod
    async def save(self, asset: Asset) -> None:
        pass
    
    @abstractmethod
    async def get(self, asset_id: str) -> Optional[Asset]:
        pass
    
    @abstractmethod
    async def get_by_tag(self, asset_tag: str) -> Optional[Asset]:
        pass
    
    @abstractmethod
    async def list_all(self) -> List[Asset]:
        pass
    
    @abstractmethod
    async def delete(self, asset_id: str) -> bool:
        pass


class InMemoryAssetStore(AssetStore):
    """In-memory asset store."""
    
    def __init__(self):
        self._assets: Dict[str, Asset] = {}
        self._by_tag: Dict[str, str] = {}
        self._counter = 0
    
    async def save(self, asset: Asset) -> None:
        # Generate asset tag if not set
        if not asset.asset_tag:
            self._counter += 1
            asset.asset_tag = f"ASSET-{self._counter:06d}"
        
        self._assets[asset.id] = asset
        self._by_tag[asset.asset_tag] = asset.id
    
    async def get(self, asset_id: str) -> Optional[Asset]:
        return self._assets.get(asset_id)
    
    async def get_by_tag(self, asset_tag: str) -> Optional[Asset]:
        asset_id = self._by_tag.get(asset_tag)
        if asset_id:
            return self._assets.get(asset_id)
        return None
    
    async def list_all(self) -> List[Asset]:
        return list(self._assets.values())
    
    async def delete(self, asset_id: str) -> bool:
        asset = self._assets.get(asset_id)
        if asset:
            del self._assets[asset_id]
            self._by_tag.pop(asset.asset_tag, None)
            return True
        return False


# Maintenance store
class MaintenanceStore(ABC):
    """Maintenance storage."""
    
    @abstractmethod
    async def save(self, record: MaintenanceRecord) -> None:
        pass
    
    @abstractmethod
    async def get(self, record_id: str) -> Optional[MaintenanceRecord]:
        pass
    
    @abstractmethod
    async def list_by_asset(self, asset_id: str) -> List[MaintenanceRecord]:
        pass
    
    @abstractmethod
    async def list_pending(self) -> List[MaintenanceRecord]:
        pass


class InMemoryMaintenanceStore(MaintenanceStore):
    """In-memory maintenance store."""
    
    def __init__(self):
        self._records: Dict[str, MaintenanceRecord] = {}
        self._by_asset: Dict[str, List[str]] = {}
    
    async def save(self, record: MaintenanceRecord) -> None:
        self._records[record.id] = record
        
        if record.asset_id not in self._by_asset:
            self._by_asset[record.asset_id] = []
        
        if record.id not in self._by_asset[record.asset_id]:
            self._by_asset[record.asset_id].append(record.id)
    
    async def get(self, record_id: str) -> Optional[MaintenanceRecord]:
        return self._records.get(record_id)
    
    async def list_by_asset(self, asset_id: str) -> List[MaintenanceRecord]:
        record_ids = self._by_asset.get(asset_id, [])
        return [self._records[rid] for rid in record_ids if rid in self._records]
    
    async def list_pending(self) -> List[MaintenanceRecord]:
        pending = []
        for record in self._records.values():
            if record.status in (MaintenanceStatus.SCHEDULED, MaintenanceStatus.OVERDUE):
                pending.append(record)
        return sorted(pending, key=lambda r: r.scheduled_for)


# Transfer store
class TransferStore(ABC):
    """Transfer storage."""
    
    @abstractmethod
    async def save(self, transfer: AssetTransfer) -> None:
        pass
    
    @abstractmethod
    async def list_by_asset(self, asset_id: str) -> List[AssetTransfer]:
        pass


class InMemoryTransferStore(TransferStore):
    """In-memory transfer store."""
    
    def __init__(self):
        self._transfers: Dict[str, AssetTransfer] = {}
        self._by_asset: Dict[str, List[str]] = {}
    
    async def save(self, transfer: AssetTransfer) -> None:
        self._transfers[transfer.id] = transfer
        
        if transfer.asset_id not in self._by_asset:
            self._by_asset[transfer.asset_id] = []
        
        self._by_asset[transfer.asset_id].append(transfer.id)
    
    async def list_by_asset(self, asset_id: str) -> List[AssetTransfer]:
        transfer_ids = self._by_asset.get(asset_id, [])
        return [self._transfers[tid] for tid in transfer_ids if tid in self._transfers]


# Depreciation calculator
class DepreciationCalculator:
    """Depreciation calculator."""
    
    @staticmethod
    def calculate(asset: Asset) -> Depreciation:
        """Calculate depreciation."""
        if not asset.purchase_date:
            return Depreciation(asset_id=asset.id)
        
        years_owned = (datetime.utcnow() - asset.purchase_date).days / 365.0
        remaining_life = max(0, asset.useful_life_years - years_owned)
        
        depreciable_amount = asset.cost - asset.salvage_value
        
        if asset.depreciation_method == DepreciationMethod.STRAIGHT_LINE:
            annual = depreciable_amount / asset.useful_life_years if asset.useful_life_years > 0 else 0
            accumulated = min(depreciable_amount, annual * years_owned)
        
        elif asset.depreciation_method == DepreciationMethod.DECLINING_BALANCE:
            rate = 2 / asset.useful_life_years if asset.useful_life_years > 0 else 0
            current = asset.cost
            accumulated = 0
            
            for _ in range(int(years_owned)):
                depreciation = current * rate
                accumulated += depreciation
                current -= depreciation
                if current < asset.salvage_value:
                    break
            
            annual = current * rate
        
        elif asset.depreciation_method == DepreciationMethod.SUM_OF_YEARS:
            n = asset.useful_life_years
            sum_years = n * (n + 1) / 2
            accumulated = 0
            annual = 0
            
            for year in range(1, int(years_owned) + 2):
                if year <= n:
                    year_rate = (n - year + 1) / sum_years
                    if year <= int(years_owned):
                        accumulated += depreciable_amount * year_rate
                    else:
                        annual = depreciable_amount * year_rate
        
        else:
            annual = 0
            accumulated = 0
        
        current_value = max(asset.salvage_value, asset.cost - accumulated)
        
        return Depreciation(
            asset_id=asset.id,
            original_cost=asset.cost,
            current_value=current_value,
            accumulated=accumulated,
            annual_amount=annual,
            remaining_life_years=remaining_life,
        )


# Asset manager
class AssetManager:
    """Asset manager."""
    
    def __init__(
        self,
        asset_store: Optional[AssetStore] = None,
        maintenance_store: Optional[MaintenanceStore] = None,
        transfer_store: Optional[TransferStore] = None,
    ):
        self._asset_store = asset_store or InMemoryAssetStore()
        self._maintenance_store = maintenance_store or InMemoryMaintenanceStore()
        self._transfer_store = transfer_store or InMemoryTransferStore()
        self._listeners: List[Callable] = []
    
    async def add(
        self,
        name: str,
        asset_type: Union[str, AssetType] = AssetType.OTHER,
        category: Union[str, AssetCategory] = AssetCategory.HARDWARE,
        cost: float = 0.0,
        **kwargs,
    ) -> Asset:
        """Add asset."""
        if isinstance(asset_type, str):
            asset_type = AssetType(asset_type)
        if isinstance(category, str):
            category = AssetCategory(category)
        
        asset = Asset(
            name=name,
            asset_type=asset_type,
            category=category,
            cost=cost,
            current_value=cost,
            purchase_date=kwargs.get("purchase_date") or datetime.utcnow(),
            **kwargs,
        )
        
        await self._asset_store.save(asset)
        
        logger.info(f"Asset added: {name} ({asset.asset_tag})")
        
        await self._notify("add", asset)
        
        return asset
    
    async def get(self, asset_id: str) -> Optional[Asset]:
        """Get asset by ID."""
        return await self._asset_store.get(asset_id)
    
    async def get_by_tag(self, asset_tag: str) -> Optional[Asset]:
        """Get asset by tag."""
        return await self._asset_store.get_by_tag(asset_tag)
    
    async def list_assets(
        self,
        status: Optional[AssetStatus] = None,
        category: Optional[AssetCategory] = None,
        asset_type: Optional[AssetType] = None,
        assignee: Optional[str] = None,
    ) -> List[Asset]:
        """List assets with filters."""
        assets = await self._asset_store.list_all()
        
        if status:
            assets = [a for a in assets if a.status == status]
        if category:
            assets = [a for a in assets if a.category == category]
        if asset_type:
            assets = [a for a in assets if a.asset_type == asset_type]
        if assignee:
            assets = [a for a in assets if a.assignee == assignee]
        
        return assets
    
    async def update(
        self,
        asset_id: str,
        **updates,
    ) -> Optional[Asset]:
        """Update asset."""
        asset = await self._asset_store.get(asset_id)
        
        if not asset:
            return None
        
        for key, value in updates.items():
            if hasattr(asset, key):
                setattr(asset, key, value)
        
        asset.updated_at = datetime.utcnow()
        
        await self._asset_store.save(asset)
        
        logger.info(f"Asset updated: {asset.asset_tag}")
        
        await self._notify("update", asset)
        
        return asset
    
    async def assign(
        self,
        asset_id: str,
        assignee: str,
        department: str = "",
        location: str = "",
        transferred_by: str = "",
        reason: str = "",
    ) -> Optional[Asset]:
        """Assign asset."""
        asset = await self._asset_store.get(asset_id)
        
        if not asset:
            return None
        
        # Record transfer
        if asset.assignee:
            transfer = AssetTransfer(
                asset_id=asset.id,
                from_assignee=asset.assignee,
                to_assignee=assignee,
                from_location=asset.location,
                to_location=location or asset.location,
                transferred_by=transferred_by,
                reason=reason,
            )
            await self._transfer_store.save(transfer)
        
        asset.assignee = assignee
        asset.department = department or asset.department
        asset.location = location or asset.location
        asset.status = AssetStatus.ASSIGNED
        asset.updated_at = datetime.utcnow()
        
        await self._asset_store.save(asset)
        
        logger.info(f"Asset assigned: {asset.asset_tag} -> {assignee}")
        
        await self._notify("assign", asset)
        
        return asset
    
    async def unassign(
        self,
        asset_id: str,
        transferred_by: str = "",
        reason: str = "",
    ) -> Optional[Asset]:
        """Unassign asset."""
        asset = await self._asset_store.get(asset_id)
        
        if not asset:
            return None
        
        if asset.assignee:
            transfer = AssetTransfer(
                asset_id=asset.id,
                from_assignee=asset.assignee,
                to_assignee="",
                from_location=asset.location,
                to_location="storage",
                transferred_by=transferred_by,
                reason=reason or "Unassigned",
            )
            await self._transfer_store.save(transfer)
        
        asset.assignee = ""
        asset.status = AssetStatus.AVAILABLE
        asset.updated_at = datetime.utcnow()
        
        await self._asset_store.save(asset)
        
        logger.info(f"Asset unassigned: {asset.asset_tag}")
        
        return asset
    
    async def retire(
        self,
        asset_id: str,
        reason: str = "",
    ) -> Optional[Asset]:
        """Retire asset."""
        asset = await self._asset_store.get(asset_id)
        
        if not asset:
            return None
        
        asset.status = AssetStatus.RETIRED
        asset.retired_date = datetime.utcnow()
        asset.notes = f"{asset.notes}\nRetired: {reason}".strip()
        asset.updated_at = datetime.utcnow()
        
        await self._asset_store.save(asset)
        
        logger.info(f"Asset retired: {asset.asset_tag}")
        
        await self._notify("retire", asset)
        
        return asset
    
    async def schedule_maintenance(
        self,
        asset_id: str,
        maintenance_type: str,
        scheduled_for: datetime,
        description: str = "",
        technician: str = "",
    ) -> Optional[MaintenanceRecord]:
        """Schedule maintenance."""
        asset = await self._asset_store.get(asset_id)
        
        if not asset:
            return None
        
        record = MaintenanceRecord(
            asset_id=asset_id,
            maintenance_type=maintenance_type,
            description=description,
            scheduled_for=scheduled_for,
            technician=technician,
        )
        
        await self._maintenance_store.save(record)
        
        asset.next_maintenance = scheduled_for
        asset.updated_at = datetime.utcnow()
        await self._asset_store.save(asset)
        
        logger.info(f"Maintenance scheduled: {asset.asset_tag} on {scheduled_for}")
        
        return record
    
    async def complete_maintenance(
        self,
        record_id: str,
        cost: float = 0.0,
        issues_found: Optional[List[str]] = None,
        actions_taken: Optional[List[str]] = None,
        notes: str = "",
    ) -> Optional[MaintenanceRecord]:
        """Complete maintenance."""
        record = await self._maintenance_store.get(record_id)
        
        if not record:
            return None
        
        record.status = MaintenanceStatus.COMPLETED
        record.completed_at = datetime.utcnow()
        record.cost = cost
        record.issues_found = issues_found or []
        record.actions_taken = actions_taken or []
        record.notes = notes
        
        await self._maintenance_store.save(record)
        
        # Update asset
        asset = await self._asset_store.get(record.asset_id)
        if asset:
            asset.last_maintenance = datetime.utcnow()
            asset.updated_at = datetime.utcnow()
            
            if asset.status == AssetStatus.MAINTENANCE:
                asset.status = AssetStatus.AVAILABLE
            
            await self._asset_store.save(asset)
        
        logger.info(f"Maintenance completed: {record_id}")
        
        return record
    
    async def get_maintenance_history(
        self,
        asset_id: str,
    ) -> List[MaintenanceRecord]:
        """Get maintenance history."""
        return await self._maintenance_store.list_by_asset(asset_id)
    
    async def get_pending_maintenance(self) -> List[MaintenanceRecord]:
        """Get pending maintenance."""
        records = await self._maintenance_store.list_pending()
        
        # Update overdue status
        now = datetime.utcnow()
        for record in records:
            if record.scheduled_for < now and record.status == MaintenanceStatus.SCHEDULED:
                record.status = MaintenanceStatus.OVERDUE
                await self._maintenance_store.save(record)
        
        return records
    
    async def get_transfer_history(
        self,
        asset_id: str,
    ) -> List[AssetTransfer]:
        """Get transfer history."""
        return await self._transfer_store.list_by_asset(asset_id)
    
    async def calculate_depreciation(
        self,
        asset_id: str,
    ) -> Optional[Depreciation]:
        """Calculate depreciation."""
        asset = await self._asset_store.get(asset_id)
        
        if not asset:
            return None
        
        depreciation = DepreciationCalculator.calculate(asset)
        
        # Update asset current value
        asset.current_value = depreciation.current_value
        asset.updated_at = datetime.utcnow()
        await self._asset_store.save(asset)
        
        return depreciation
    
    async def get_expiring_warranties(
        self,
        days: int = 30,
    ) -> List[Asset]:
        """Get assets with expiring warranties."""
        assets = await self._asset_store.list_all()
        expiring = []
        
        threshold = datetime.utcnow() + timedelta(days=days)
        
        for asset in assets:
            if asset.warranty_expires:
                if datetime.utcnow() < asset.warranty_expires <= threshold:
                    expiring.append(asset)
        
        return sorted(expiring, key=lambda a: a.warranty_expires)
    
    async def get_stats(self) -> AssetStats:
        """Get asset statistics."""
        assets = await self._asset_store.list_all()
        pending = await self._maintenance_store.list_pending()
        expiring = await self.get_expiring_warranties(days=30)
        
        stats = AssetStats(
            total_assets=len(assets),
            maintenance_due=len(pending),
            warranty_expiring=len(expiring),
        )
        
        for asset in assets:
            # By status
            status = asset.status.value
            stats.by_status[status] = stats.by_status.get(status, 0) + 1
            
            # By category
            category = asset.category.value
            stats.by_category[category] = stats.by_category.get(category, 0) + 1
            
            # By type
            asset_type = asset.asset_type.value
            stats.by_type[asset_type] = stats.by_type.get(asset_type, 0) + 1
            
            # Totals
            stats.total_cost += asset.cost
            stats.total_value += asset.current_value
        
        return stats
    
    def add_listener(self, listener: Callable) -> None:
        """Add event listener."""
        self._listeners.append(listener)
    
    async def _notify(self, event: str, asset: Asset) -> None:
        """Notify listeners."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, asset)
                else:
                    listener(event, asset)
            except Exception as e:
                logger.error(f"Listener error: {e}")


# Factory functions
def create_asset_manager() -> AssetManager:
    """Create asset manager."""
    return AssetManager()


def create_asset(
    name: str,
    asset_type: AssetType = AssetType.OTHER,
    **kwargs,
) -> Asset:
    """Create asset."""
    return Asset(name=name, asset_type=asset_type, **kwargs)


__all__ = [
    # Exceptions
    "AssetError",
    # Enums
    "AssetType",
    "AssetCategory",
    "AssetStatus",
    "MaintenanceStatus",
    "DepreciationMethod",
    # Data classes
    "Asset",
    "MaintenanceRecord",
    "AssetTransfer",
    "Depreciation",
    "AssetStats",
    # Stores
    "AssetStore",
    "InMemoryAssetStore",
    "MaintenanceStore",
    "InMemoryMaintenanceStore",
    "TransferStore",
    "InMemoryTransferStore",
    # Utilities
    "DepreciationCalculator",
    # Manager
    "AssetManager",
    # Factory functions
    "create_asset_manager",
    "create_asset",
]
