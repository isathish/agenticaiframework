"""
Enterprise Shipping Service Module.

Carrier integration, rate calculation, tracking,
label generation, and shipping management.

Example:
    # Create shipping service
    shipping = create_shipping_service()
    
    # Get rates
    rates = await shipping.get_rates(
        origin={"zip": "10001", "country": "US"},
        destination={"zip": "90210", "country": "US"},
        package={"weight": 2.5, "dimensions": [10, 8, 6]},
    )
    
    # Create shipment
    shipment = await shipping.create_shipment(
        carrier="fedex",
        service="ground",
        from_address={...},
        to_address={...},
        parcels=[{"weight": 2.5}],
    )
    
    # Track shipment
    tracking = await shipping.track("TRACK123456")
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class ShippingError(Exception):
    """Shipping error."""
    pass


class CarrierNotFoundError(ShippingError):
    """Carrier not found."""
    pass


class TrackingNotFoundError(ShippingError):
    """Tracking not found."""
    pass


class ShipmentStatus(str, Enum):
    """Shipment status."""
    PENDING = "pending"
    LABEL_CREATED = "label_created"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    RETURNED = "returned"
    EXCEPTION = "exception"
    CANCELLED = "cancelled"


class ServiceType(str, Enum):
    """Shipping service type."""
    GROUND = "ground"
    EXPRESS = "express"
    OVERNIGHT = "overnight"
    TWO_DAY = "two_day"
    ECONOMY = "economy"
    FREIGHT = "freight"
    INTERNATIONAL = "international"


class PackageType(str, Enum):
    """Package type."""
    ENVELOPE = "envelope"
    PARCEL = "parcel"
    FLAT_RATE_BOX = "flat_rate_box"
    FLAT_RATE_ENVELOPE = "flat_rate_envelope"
    TUBE = "tube"
    PALLET = "pallet"
    CUSTOM = "custom"


@dataclass
class Address:
    """Shipping address."""
    name: str = ""
    company: str = ""
    street1: str = ""
    street2: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    country: str = "US"
    phone: str = ""
    email: str = ""
    is_residential: bool = True


@dataclass
class Parcel:
    """Package/parcel."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    weight: float = 0.0  # lbs or kg
    weight_unit: str = "lb"
    length: float = 0.0
    width: float = 0.0
    height: float = 0.0
    dimension_unit: str = "in"
    package_type: PackageType = PackageType.PARCEL
    value: float = 0.0
    currency: str = "USD"
    description: str = ""


@dataclass
class Rate:
    """Shipping rate."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    carrier: str = ""
    carrier_name: str = ""
    service: str = ""
    service_name: str = ""
    price: float = 0.0
    retail_price: float = 0.0
    currency: str = "USD"
    delivery_days: int = 0
    estimated_delivery: Optional[datetime] = None
    guaranteed: bool = False
    package_type: str = ""
    zone: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Label:
    """Shipping label."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    carrier: str = ""
    tracking_number: str = ""
    label_url: str = ""
    label_format: str = "pdf"
    label_size: str = "4x6"
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TrackingEvent:
    """Tracking event."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: ShipmentStatus = ShipmentStatus.IN_TRANSIT
    description: str = ""
    location: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    zip: str = ""


@dataclass
class TrackingInfo:
    """Tracking information."""
    tracking_number: str = ""
    carrier: str = ""
    status: ShipmentStatus = ShipmentStatus.PENDING
    estimated_delivery: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None
    signed_by: str = ""
    events: List[TrackingEvent] = field(default_factory=list)
    origin: Optional[Address] = None
    destination: Optional[Address] = None


@dataclass
class Shipment:
    """Shipment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    carrier: str = ""
    service: str = ""
    from_address: Address = field(default_factory=Address)
    to_address: Address = field(default_factory=Address)
    return_address: Optional[Address] = None
    parcels: List[Parcel] = field(default_factory=list)
    tracking_number: str = ""
    status: ShipmentStatus = ShipmentStatus.PENDING
    rate: Optional[Rate] = None
    label: Optional[Label] = None
    customs: Optional[Dict[str, Any]] = None
    insurance_amount: float = 0.0
    signature_required: bool = False
    reference: str = ""
    order_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


@dataclass
class Carrier:
    """Shipping carrier."""
    id: str = ""
    name: str = ""
    code: str = ""
    services: List[str] = field(default_factory=list)
    is_active: bool = True
    supports_tracking: bool = True
    supports_labels: bool = True
    supports_returns: bool = True


@dataclass
class ShippingStats:
    """Shipping statistics."""
    total_shipments: int = 0
    delivered: int = 0
    in_transit: int = 0
    total_cost: float = 0.0


# Carrier interface
class CarrierInterface(ABC):
    """Carrier interface."""
    
    @abstractmethod
    async def get_rates(
        self,
        origin: Address,
        destination: Address,
        parcels: List[Parcel],
    ) -> List[Rate]:
        pass
    
    @abstractmethod
    async def create_label(
        self,
        shipment: Shipment,
    ) -> Label:
        pass
    
    @abstractmethod
    async def track(
        self,
        tracking_number: str,
    ) -> TrackingInfo:
        pass
    
    @abstractmethod
    async def cancel_shipment(
        self,
        shipment_id: str,
    ) -> bool:
        pass


class MockCarrier(CarrierInterface):
    """Mock carrier for testing."""
    
    def __init__(self, carrier_code: str = "mock"):
        self.carrier_code = carrier_code
        self._tracking: Dict[str, TrackingInfo] = {}
    
    async def get_rates(
        self,
        origin: Address,
        destination: Address,
        parcels: List[Parcel],
    ) -> List[Rate]:
        total_weight = sum(p.weight for p in parcels)
        base_price = 5.99 + (total_weight * 0.50)
        
        return [
            Rate(
                carrier=self.carrier_code,
                carrier_name=self.carrier_code.upper(),
                service="ground",
                service_name="Ground Shipping",
                price=base_price,
                delivery_days=5,
                estimated_delivery=datetime.utcnow() + timedelta(days=5),
            ),
            Rate(
                carrier=self.carrier_code,
                carrier_name=self.carrier_code.upper(),
                service="express",
                service_name="Express Shipping",
                price=base_price * 2,
                delivery_days=2,
                estimated_delivery=datetime.utcnow() + timedelta(days=2),
            ),
            Rate(
                carrier=self.carrier_code,
                carrier_name=self.carrier_code.upper(),
                service="overnight",
                service_name="Overnight Shipping",
                price=base_price * 4,
                delivery_days=1,
                estimated_delivery=datetime.utcnow() + timedelta(days=1),
                guaranteed=True,
            ),
        ]
    
    async def create_label(
        self,
        shipment: Shipment,
    ) -> Label:
        tracking = f"{self.carrier_code.upper()}{uuid.uuid4().hex[:12].upper()}"
        
        label = Label(
            carrier=self.carrier_code,
            tracking_number=tracking,
            label_url=f"https://mock-carrier.example.com/labels/{tracking}.pdf",
            label_format="pdf",
        )
        
        # Create tracking info
        self._tracking[tracking] = TrackingInfo(
            tracking_number=tracking,
            carrier=self.carrier_code,
            status=ShipmentStatus.LABEL_CREATED,
            events=[
                TrackingEvent(
                    status=ShipmentStatus.LABEL_CREATED,
                    description="Shipping label created",
                )
            ],
        )
        
        return label
    
    async def track(
        self,
        tracking_number: str,
    ) -> TrackingInfo:
        if tracking_number in self._tracking:
            return self._tracking[tracking_number]
        
        raise TrackingNotFoundError(f"Tracking not found: {tracking_number}")
    
    async def cancel_shipment(
        self,
        shipment_id: str,
    ) -> bool:
        return True


# Shipment store
class ShipmentStore(ABC):
    """Shipment storage."""
    
    @abstractmethod
    async def save(self, shipment: Shipment) -> None:
        pass
    
    @abstractmethod
    async def get(self, shipment_id: str) -> Optional[Shipment]:
        pass
    
    @abstractmethod
    async def find_by_tracking(self, tracking_number: str) -> Optional[Shipment]:
        pass
    
    @abstractmethod
    async def list(
        self,
        status: Optional[ShipmentStatus] = None,
    ) -> List[Shipment]:
        pass


class InMemoryShipmentStore(ShipmentStore):
    """In-memory shipment store."""
    
    def __init__(self):
        self._shipments: Dict[str, Shipment] = {}
    
    async def save(self, shipment: Shipment) -> None:
        self._shipments[shipment.id] = shipment
    
    async def get(self, shipment_id: str) -> Optional[Shipment]:
        return self._shipments.get(shipment_id)
    
    async def find_by_tracking(self, tracking_number: str) -> Optional[Shipment]:
        for shipment in self._shipments.values():
            if shipment.tracking_number == tracking_number:
                return shipment
        return None
    
    async def list(
        self,
        status: Optional[ShipmentStatus] = None,
    ) -> List[Shipment]:
        shipments = list(self._shipments.values())
        
        if status:
            shipments = [s for s in shipments if s.status == status]
        
        return sorted(shipments, key=lambda s: s.created_at, reverse=True)


# Shipping service
class ShippingService:
    """Shipping service."""
    
    def __init__(
        self,
        shipment_store: Optional[ShipmentStore] = None,
    ):
        self._shipments = shipment_store or InMemoryShipmentStore()
        self._carriers: Dict[str, CarrierInterface] = {}
        self._carrier_info: Dict[str, Carrier] = {}
        self._stats = ShippingStats()
        
        # Register mock carriers
        self._register_mock_carriers()
    
    def _register_mock_carriers(self) -> None:
        """Register mock carriers."""
        mock_carriers = [
            Carrier(id="fedex", name="FedEx", code="fedex", services=["ground", "express", "overnight"]),
            Carrier(id="ups", name="UPS", code="ups", services=["ground", "express", "overnight"]),
            Carrier(id="usps", name="USPS", code="usps", services=["priority", "express", "first_class"]),
            Carrier(id="dhl", name="DHL", code="dhl", services=["express", "economy", "freight"]),
        ]
        
        for carrier in mock_carriers:
            self._carrier_info[carrier.code] = carrier
            self._carriers[carrier.code] = MockCarrier(carrier.code)
    
    async def register_carrier(
        self,
        carrier_code: str,
        carrier_interface: CarrierInterface,
        carrier_info: Optional[Carrier] = None,
    ) -> None:
        """Register carrier."""
        self._carriers[carrier_code] = carrier_interface
        if carrier_info:
            self._carrier_info[carrier_code] = carrier_info
    
    async def get_carriers(self) -> List[Carrier]:
        """Get available carriers."""
        return [c for c in self._carrier_info.values() if c.is_active]
    
    async def get_rates(
        self,
        origin: Dict[str, str],
        destination: Dict[str, str],
        package: Dict[str, Any],
        carriers: Optional[List[str]] = None,
    ) -> List[Rate]:
        """Get shipping rates."""
        origin_addr = Address(**origin)
        dest_addr = Address(**destination)
        
        parcel = Parcel(
            weight=package.get("weight", 1.0),
            length=package.get("dimensions", [0, 0, 0])[0] if "dimensions" in package else 0,
            width=package.get("dimensions", [0, 0, 0])[1] if "dimensions" in package else 0,
            height=package.get("dimensions", [0, 0, 0])[2] if "dimensions" in package else 0,
        )
        
        all_rates: List[Rate] = []
        carrier_list = carriers or list(self._carriers.keys())
        
        for carrier_code in carrier_list:
            if carrier_code not in self._carriers:
                continue
            
            try:
                rates = await self._carriers[carrier_code].get_rates(
                    origin_addr,
                    dest_addr,
                    [parcel],
                )
                all_rates.extend(rates)
            except Exception as e:
                logger.warning(f"Failed to get rates from {carrier_code}: {e}")
        
        return sorted(all_rates, key=lambda r: r.price)
    
    async def create_shipment(
        self,
        carrier: str,
        service: str,
        from_address: Dict[str, str],
        to_address: Dict[str, str],
        parcels: List[Dict[str, Any]],
        order_id: str = "",
        **kwargs,
    ) -> Shipment:
        """Create shipment."""
        if carrier not in self._carriers:
            raise CarrierNotFoundError(f"Carrier not found: {carrier}")
        
        shipment = Shipment(
            carrier=carrier,
            service=service,
            from_address=Address(**from_address),
            to_address=Address(**to_address),
            parcels=[
                Parcel(
                    weight=p.get("weight", 1.0),
                    length=p.get("length", 0),
                    width=p.get("width", 0),
                    height=p.get("height", 0),
                    value=p.get("value", 0),
                    description=p.get("description", ""),
                )
                for p in parcels
            ],
            order_id=order_id,
            **kwargs,
        )
        
        # Create label
        carrier_interface = self._carriers[carrier]
        label = await carrier_interface.create_label(shipment)
        
        shipment.label = label
        shipment.tracking_number = label.tracking_number
        shipment.status = ShipmentStatus.LABEL_CREATED
        
        await self._shipments.save(shipment)
        self._stats.total_shipments += 1
        
        logger.info(f"Shipment created: {shipment.tracking_number}")
        
        return shipment
    
    async def get_shipment(self, shipment_id: str) -> Optional[Shipment]:
        """Get shipment."""
        return await self._shipments.get(shipment_id)
    
    async def track(
        self,
        tracking_number: str,
    ) -> TrackingInfo:
        """Track shipment."""
        # Find shipment
        shipment = await self._shipments.find_by_tracking(tracking_number)
        
        if shipment and shipment.carrier in self._carriers:
            return await self._carriers[shipment.carrier].track(tracking_number)
        
        # Try all carriers
        for carrier in self._carriers.values():
            try:
                return await carrier.track(tracking_number)
            except TrackingNotFoundError:
                continue
        
        raise TrackingNotFoundError(f"Tracking not found: {tracking_number}")
    
    async def cancel_shipment(
        self,
        shipment_id: str,
    ) -> bool:
        """Cancel shipment."""
        shipment = await self._shipments.get(shipment_id)
        if not shipment:
            return False
        
        if shipment.carrier in self._carriers:
            result = await self._carriers[shipment.carrier].cancel_shipment(shipment_id)
            if result:
                shipment.status = ShipmentStatus.CANCELLED
                await self._shipments.save(shipment)
            return result
        
        return False
    
    async def update_status(
        self,
        shipment_id: str,
        status: ShipmentStatus,
    ) -> Optional[Shipment]:
        """Update shipment status."""
        shipment = await self._shipments.get(shipment_id)
        if not shipment:
            return None
        
        old_status = shipment.status
        shipment.status = status
        
        if status == ShipmentStatus.PICKED_UP:
            shipment.shipped_at = datetime.utcnow()
        elif status == ShipmentStatus.DELIVERED:
            shipment.delivered_at = datetime.utcnow()
            self._stats.delivered += 1
        
        await self._shipments.save(shipment)
        
        logger.info(f"Shipment {shipment.tracking_number}: {old_status} → {status}")
        
        return shipment
    
    async def list_shipments(
        self,
        status: Optional[ShipmentStatus] = None,
    ) -> List[Shipment]:
        """List shipments."""
        return await self._shipments.list(status=status)
    
    def get_stats(self) -> ShippingStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_shipping_service() -> ShippingService:
    """Create shipping service."""
    return ShippingService()


def create_address(**kwargs) -> Address:
    """Create address."""
    return Address(**kwargs)


def create_parcel(**kwargs) -> Parcel:
    """Create parcel."""
    return Parcel(**kwargs)


def create_shipment(**kwargs) -> Shipment:
    """Create shipment."""
    return Shipment(**kwargs)


__all__ = [
    # Exceptions
    "ShippingError",
    "CarrierNotFoundError",
    "TrackingNotFoundError",
    # Enums
    "ShipmentStatus",
    "ServiceType",
    "PackageType",
    # Data classes
    "Address",
    "Parcel",
    "Rate",
    "Label",
    "TrackingEvent",
    "TrackingInfo",
    "Shipment",
    "Carrier",
    "ShippingStats",
    # Interfaces
    "CarrierInterface",
    "MockCarrier",
    # Stores
    "ShipmentStore",
    "InMemoryShipmentStore",
    # Service
    "ShippingService",
    # Factory functions
    "create_shipping_service",
    "create_address",
    "create_parcel",
    "create_shipment",
]
