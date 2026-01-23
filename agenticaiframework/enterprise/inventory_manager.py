"""
Enterprise Inventory Manager Module.

Stock tracking, SKU management, warehouses,
reorder alerts, and inventory operations.

Example:
    # Create inventory manager
    inventory = create_inventory_manager()
    
    # Add product
    product = await inventory.add_product(
        sku="WIDGET-001",
        name="Blue Widget",
        category="widgets",
    )
    
    # Stock product
    await inventory.stock(
        sku="WIDGET-001",
        warehouse_id="wh_main",
        quantity=100,
        unit_cost=5.00,
    )
    
    # Reserve for order
    reservation = await inventory.reserve(
        sku="WIDGET-001",
        quantity=5,
        order_id="order_123",
    )
    
    # Check stock
    stock = await inventory.get_stock("WIDGET-001")
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


class InventoryError(Exception):
    """Inventory error."""
    pass


class ProductNotFoundError(InventoryError):
    """Product not found."""
    pass


class InsufficientStockError(InventoryError):
    """Insufficient stock."""
    pass


class StockStatus(str, Enum):
    """Stock status."""
    IN_STOCK = "in_stock"
    LOW_STOCK = "low_stock"
    OUT_OF_STOCK = "out_of_stock"
    DISCONTINUED = "discontinued"


class MovementType(str, Enum):
    """Stock movement type."""
    PURCHASE = "purchase"
    SALE = "sale"
    RETURN = "return"
    ADJUSTMENT = "adjustment"
    TRANSFER = "transfer"
    DAMAGE = "damage"
    EXPIRED = "expired"


class ReorderStrategy(str, Enum):
    """Reorder strategy."""
    FIXED_QUANTITY = "fixed_quantity"
    ECONOMIC_ORDER = "economic_order"
    MIN_MAX = "min_max"


@dataclass
class Product:
    """Product definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sku: str = ""
    name: str = ""
    description: str = ""
    category: str = ""
    brand: str = ""
    unit: str = "each"  # each, kg, liter, etc.
    weight: float = 0.0  # kg
    dimensions: Dict[str, float] = field(default_factory=dict)  # length, width, height
    barcode: str = ""
    reorder_point: int = 10
    reorder_quantity: int = 50
    max_stock: int = 1000
    lead_time_days: int = 7
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Warehouse:
    """Warehouse location."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    code: str = ""
    address: str = ""
    city: str = ""
    country: str = ""
    is_primary: bool = False
    is_active: bool = True
    capacity: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StockLevel:
    """Stock level at warehouse."""
    product_id: str = ""
    sku: str = ""
    warehouse_id: str = ""
    quantity: int = 0
    reserved: int = 0
    unit_cost: float = 0.0
    bin_location: str = ""
    lot_number: str = ""
    expiry_date: Optional[datetime] = None
    last_counted: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def available(self) -> int:
        """Available quantity."""
        return max(0, self.quantity - self.reserved)
    
    @property
    def total_value(self) -> float:
        """Total value."""
        return self.quantity * self.unit_cost


@dataclass
class StockMovement:
    """Stock movement record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    sku: str = ""
    warehouse_id: str = ""
    type: MovementType = MovementType.ADJUSTMENT
    quantity: int = 0
    unit_cost: float = 0.0
    reference_id: str = ""  # order_id, transfer_id, etc.
    reason: str = ""
    performed_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Reservation:
    """Stock reservation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    sku: str = ""
    warehouse_id: str = ""
    quantity: int = 0
    order_id: str = ""
    expires_at: Optional[datetime] = None
    fulfilled: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ReorderAlert:
    """Reorder alert."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str = ""
    sku: str = ""
    warehouse_id: str = ""
    current_quantity: int = 0
    reorder_point: int = 0
    suggested_quantity: int = 0
    priority: str = "normal"  # low, normal, high, critical
    acknowledged: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class InventoryStats:
    """Inventory statistics."""
    total_products: int = 0
    total_warehouses: int = 0
    total_stock_value: float = 0.0
    low_stock_items: int = 0
    out_of_stock_items: int = 0


# Product store
class ProductStore(ABC):
    """Product storage."""
    
    @abstractmethod
    async def save(self, product: Product) -> None:
        pass
    
    @abstractmethod
    async def get(self, product_id: str) -> Optional[Product]:
        pass
    
    @abstractmethod
    async def get_by_sku(self, sku: str) -> Optional[Product]:
        pass
    
    @abstractmethod
    async def list(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Product]:
        pass


class InMemoryProductStore(ProductStore):
    """In-memory product store."""
    
    def __init__(self):
        self._products: Dict[str, Product] = {}
        self._sku_index: Dict[str, str] = {}
    
    async def save(self, product: Product) -> None:
        self._products[product.id] = product
        self._sku_index[product.sku] = product.id
    
    async def get(self, product_id: str) -> Optional[Product]:
        return self._products.get(product_id)
    
    async def get_by_sku(self, sku: str) -> Optional[Product]:
        product_id = self._sku_index.get(sku)
        return self._products.get(product_id) if product_id else None
    
    async def list(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> List[Product]:
        products = list(self._products.values())
        
        if category:
            products = [p for p in products if p.category == category]
        if active_only:
            products = [p for p in products if p.is_active]
        
        return products


# Stock store
class StockStore(ABC):
    """Stock storage."""
    
    @abstractmethod
    async def save(self, stock: StockLevel) -> None:
        pass
    
    @abstractmethod
    async def get(
        self,
        product_id: str,
        warehouse_id: str,
    ) -> Optional[StockLevel]:
        pass
    
    @abstractmethod
    async def list(
        self,
        product_id: Optional[str] = None,
        warehouse_id: Optional[str] = None,
    ) -> List[StockLevel]:
        pass


class InMemoryStockStore(StockStore):
    """In-memory stock store."""
    
    def __init__(self):
        self._stock: Dict[str, StockLevel] = {}  # key: product_id:warehouse_id
    
    def _key(self, product_id: str, warehouse_id: str) -> str:
        return f"{product_id}:{warehouse_id}"
    
    async def save(self, stock: StockLevel) -> None:
        key = self._key(stock.product_id, stock.warehouse_id)
        stock.updated_at = datetime.utcnow()
        self._stock[key] = stock
    
    async def get(
        self,
        product_id: str,
        warehouse_id: str,
    ) -> Optional[StockLevel]:
        key = self._key(product_id, warehouse_id)
        return self._stock.get(key)
    
    async def list(
        self,
        product_id: Optional[str] = None,
        warehouse_id: Optional[str] = None,
    ) -> List[StockLevel]:
        results = list(self._stock.values())
        
        if product_id:
            results = [s for s in results if s.product_id == product_id]
        if warehouse_id:
            results = [s for s in results if s.warehouse_id == warehouse_id]
        
        return results


# Inventory manager
class InventoryManager:
    """Inventory manager."""
    
    def __init__(
        self,
        product_store: Optional[ProductStore] = None,
        stock_store: Optional[StockStore] = None,
    ):
        self._products = product_store or InMemoryProductStore()
        self._stock = stock_store or InMemoryStockStore()
        self._warehouses: Dict[str, Warehouse] = {}
        self._movements: List[StockMovement] = []
        self._reservations: Dict[str, Reservation] = {}
        self._alerts: List[ReorderAlert] = []
        self._stats = InventoryStats()
    
    # Product management
    async def add_product(
        self,
        sku: str,
        name: str,
        category: str = "",
        reorder_point: int = 10,
        reorder_quantity: int = 50,
        **kwargs,
    ) -> Product:
        """Add product."""
        product = Product(
            sku=sku,
            name=name,
            category=category,
            reorder_point=reorder_point,
            reorder_quantity=reorder_quantity,
            **kwargs,
        )
        await self._products.save(product)
        self._stats.total_products += 1
        
        logger.info(f"Product added: {sku}")
        
        return product
    
    async def get_product(self, sku: str) -> Optional[Product]:
        """Get product by SKU."""
        return await self._products.get_by_sku(sku)
    
    async def list_products(
        self,
        category: Optional[str] = None,
    ) -> List[Product]:
        """List products."""
        return await self._products.list(category=category)
    
    # Warehouse management
    async def add_warehouse(
        self,
        name: str,
        code: str,
        **kwargs,
    ) -> Warehouse:
        """Add warehouse."""
        warehouse = Warehouse(
            name=name,
            code=code,
            **kwargs,
        )
        self._warehouses[warehouse.id] = warehouse
        self._stats.total_warehouses += 1
        
        logger.info(f"Warehouse added: {name}")
        
        return warehouse
    
    async def get_warehouse(self, warehouse_id: str) -> Optional[Warehouse]:
        """Get warehouse."""
        return self._warehouses.get(warehouse_id)
    
    async def list_warehouses(self) -> List[Warehouse]:
        """List warehouses."""
        return [w for w in self._warehouses.values() if w.is_active]
    
    # Stock operations
    async def stock(
        self,
        sku: str,
        warehouse_id: str,
        quantity: int,
        unit_cost: float = 0.0,
        lot_number: str = "",
        expiry_date: Optional[datetime] = None,
        performed_by: str = "",
    ) -> StockLevel:
        """Add stock."""
        product = await self._products.get_by_sku(sku)
        if not product:
            raise ProductNotFoundError(f"Product not found: {sku}")
        
        # Get or create stock level
        stock = await self._stock.get(product.id, warehouse_id)
        if not stock:
            stock = StockLevel(
                product_id=product.id,
                sku=sku,
                warehouse_id=warehouse_id,
            )
        
        stock.quantity += quantity
        stock.unit_cost = unit_cost or stock.unit_cost
        stock.lot_number = lot_number or stock.lot_number
        stock.expiry_date = expiry_date or stock.expiry_date
        
        await self._stock.save(stock)
        
        # Record movement
        movement = StockMovement(
            product_id=product.id,
            sku=sku,
            warehouse_id=warehouse_id,
            type=MovementType.PURCHASE,
            quantity=quantity,
            unit_cost=unit_cost,
            performed_by=performed_by,
        )
        self._movements.append(movement)
        
        # Update stats
        self._stats.total_stock_value += quantity * unit_cost
        
        logger.info(f"Stock added: {sku} x {quantity}")
        
        return stock
    
    async def get_stock(
        self,
        sku: str,
        warehouse_id: Optional[str] = None,
    ) -> List[StockLevel]:
        """Get stock levels."""
        product = await self._products.get_by_sku(sku)
        if not product:
            return []
        
        stocks = await self._stock.list(
            product_id=product.id,
            warehouse_id=warehouse_id,
        )
        
        return stocks
    
    async def get_total_stock(self, sku: str) -> int:
        """Get total stock across all warehouses."""
        stocks = await self.get_stock(sku)
        return sum(s.available for s in stocks)
    
    async def get_stock_status(self, sku: str) -> StockStatus:
        """Get stock status."""
        product = await self._products.get_by_sku(sku)
        if not product:
            return StockStatus.OUT_OF_STOCK
        
        if not product.is_active:
            return StockStatus.DISCONTINUED
        
        total = await self.get_total_stock(sku)
        
        if total == 0:
            return StockStatus.OUT_OF_STOCK
        elif total <= product.reorder_point:
            return StockStatus.LOW_STOCK
        else:
            return StockStatus.IN_STOCK
    
    # Reservation
    async def reserve(
        self,
        sku: str,
        quantity: int,
        order_id: str,
        warehouse_id: Optional[str] = None,
        expires_in: int = 1800,  # seconds
    ) -> Reservation:
        """Reserve stock."""
        product = await self._products.get_by_sku(sku)
        if not product:
            raise ProductNotFoundError(f"Product not found: {sku}")
        
        # Find stock to reserve
        stocks = await self.get_stock(sku, warehouse_id)
        
        remaining = quantity
        reservations: List[Reservation] = []
        
        for stock in stocks:
            if remaining <= 0:
                break
            
            available = stock.available
            if available <= 0:
                continue
            
            reserve_qty = min(remaining, available)
            stock.reserved += reserve_qty
            await self._stock.save(stock)
            
            reservation = Reservation(
                product_id=product.id,
                sku=sku,
                warehouse_id=stock.warehouse_id,
                quantity=reserve_qty,
                order_id=order_id,
                expires_at=datetime.utcnow() + timedelta(seconds=expires_in),
            )
            self._reservations[reservation.id] = reservation
            reservations.append(reservation)
            
            remaining -= reserve_qty
        
        if remaining > 0:
            # Rollback reservations
            for r in reservations:
                await self.release_reservation(r.id)
            raise InsufficientStockError(
                f"Insufficient stock for {sku}. Available: {quantity - remaining}"
            )
        
        # Return first reservation (main one)
        return reservations[0] if reservations else Reservation()
    
    async def release_reservation(self, reservation_id: str) -> bool:
        """Release reservation."""
        reservation = self._reservations.get(reservation_id)
        if not reservation:
            return False
        
        stock = await self._stock.get(
            reservation.product_id,
            reservation.warehouse_id,
        )
        if stock:
            stock.reserved -= reservation.quantity
            await self._stock.save(stock)
        
        del self._reservations[reservation_id]
        
        return True
    
    async def fulfill_reservation(self, reservation_id: str) -> bool:
        """Fulfill reservation (convert to sale)."""
        reservation = self._reservations.get(reservation_id)
        if not reservation:
            return False
        
        stock = await self._stock.get(
            reservation.product_id,
            reservation.warehouse_id,
        )
        if stock:
            stock.quantity -= reservation.quantity
            stock.reserved -= reservation.quantity
            await self._stock.save(stock)
            
            # Record movement
            movement = StockMovement(
                product_id=reservation.product_id,
                sku=reservation.sku,
                warehouse_id=reservation.warehouse_id,
                type=MovementType.SALE,
                quantity=-reservation.quantity,
                reference_id=reservation.order_id,
            )
            self._movements.append(movement)
        
        reservation.fulfilled = True
        del self._reservations[reservation_id]
        
        # Check reorder
        await self._check_reorder(reservation.sku, reservation.warehouse_id)
        
        return True
    
    # Transfer
    async def transfer(
        self,
        sku: str,
        from_warehouse: str,
        to_warehouse: str,
        quantity: int,
        performed_by: str = "",
    ) -> Tuple[StockLevel, StockLevel]:
        """Transfer stock between warehouses."""
        product = await self._products.get_by_sku(sku)
        if not product:
            raise ProductNotFoundError(f"Product not found: {sku}")
        
        # Get source stock
        source = await self._stock.get(product.id, from_warehouse)
        if not source or source.available < quantity:
            raise InsufficientStockError(
                f"Insufficient stock in source warehouse"
            )
        
        # Get or create destination stock
        dest = await self._stock.get(product.id, to_warehouse)
        if not dest:
            dest = StockLevel(
                product_id=product.id,
                sku=sku,
                warehouse_id=to_warehouse,
                unit_cost=source.unit_cost,
            )
        
        # Transfer
        source.quantity -= quantity
        dest.quantity += quantity
        
        await self._stock.save(source)
        await self._stock.save(dest)
        
        # Record movements
        self._movements.append(StockMovement(
            product_id=product.id,
            sku=sku,
            warehouse_id=from_warehouse,
            type=MovementType.TRANSFER,
            quantity=-quantity,
            reference_id=to_warehouse,
            performed_by=performed_by,
        ))
        self._movements.append(StockMovement(
            product_id=product.id,
            sku=sku,
            warehouse_id=to_warehouse,
            type=MovementType.TRANSFER,
            quantity=quantity,
            reference_id=from_warehouse,
            performed_by=performed_by,
        ))
        
        logger.info(f"Transferred {quantity} x {sku} from {from_warehouse} to {to_warehouse}")
        
        return source, dest
    
    # Adjustment
    async def adjust(
        self,
        sku: str,
        warehouse_id: str,
        quantity: int,  # Can be negative
        reason: str = "",
        performed_by: str = "",
    ) -> StockLevel:
        """Adjust stock."""
        product = await self._products.get_by_sku(sku)
        if not product:
            raise ProductNotFoundError(f"Product not found: {sku}")
        
        stock = await self._stock.get(product.id, warehouse_id)
        if not stock:
            stock = StockLevel(
                product_id=product.id,
                sku=sku,
                warehouse_id=warehouse_id,
            )
        
        stock.quantity += quantity
        if stock.quantity < 0:
            stock.quantity = 0
        
        await self._stock.save(stock)
        
        # Record movement
        self._movements.append(StockMovement(
            product_id=product.id,
            sku=sku,
            warehouse_id=warehouse_id,
            type=MovementType.ADJUSTMENT,
            quantity=quantity,
            reason=reason,
            performed_by=performed_by,
        ))
        
        logger.info(f"Stock adjusted: {sku} by {quantity}")
        
        return stock
    
    # Reorder
    async def _check_reorder(
        self,
        sku: str,
        warehouse_id: str,
    ) -> Optional[ReorderAlert]:
        """Check if reorder is needed."""
        product = await self._products.get_by_sku(sku)
        if not product:
            return None
        
        stock = await self._stock.get(product.id, warehouse_id)
        if not stock:
            return None
        
        if stock.quantity <= product.reorder_point:
            alert = ReorderAlert(
                product_id=product.id,
                sku=sku,
                warehouse_id=warehouse_id,
                current_quantity=stock.quantity,
                reorder_point=product.reorder_point,
                suggested_quantity=product.reorder_quantity,
                priority="high" if stock.quantity == 0 else "normal",
            )
            self._alerts.append(alert)
            self._stats.low_stock_items += 1
            
            if stock.quantity == 0:
                self._stats.out_of_stock_items += 1
            
            logger.warning(f"Reorder alert: {sku} at {stock.quantity}")
            
            return alert
        
        return None
    
    async def get_reorder_alerts(
        self,
        acknowledged: bool = False,
    ) -> List[ReorderAlert]:
        """Get reorder alerts."""
        return [
            a for a in self._alerts
            if a.acknowledged == acknowledged
        ]
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge alert."""
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    # Movements
    async def get_movements(
        self,
        sku: Optional[str] = None,
        warehouse_id: Optional[str] = None,
        type: Optional[MovementType] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[StockMovement]:
        """Get stock movements."""
        movements = self._movements
        
        if sku:
            movements = [m for m in movements if m.sku == sku]
        if warehouse_id:
            movements = [m for m in movements if m.warehouse_id == warehouse_id]
        if type:
            movements = [m for m in movements if m.type == type]
        if start:
            movements = [m for m in movements if m.created_at >= start]
        if end:
            movements = [m for m in movements if m.created_at <= end]
        
        return sorted(movements, key=lambda m: m.created_at, reverse=True)
    
    # Stats
    def get_stats(self) -> InventoryStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_inventory_manager() -> InventoryManager:
    """Create inventory manager."""
    return InventoryManager()


def create_product(
    sku: str,
    name: str,
    **kwargs,
) -> Product:
    """Create product."""
    return Product(sku=sku, name=name, **kwargs)


def create_warehouse(
    name: str,
    code: str,
    **kwargs,
) -> Warehouse:
    """Create warehouse."""
    return Warehouse(name=name, code=code, **kwargs)


__all__ = [
    # Exceptions
    "InventoryError",
    "ProductNotFoundError",
    "InsufficientStockError",
    # Enums
    "StockStatus",
    "MovementType",
    "ReorderStrategy",
    # Data classes
    "Product",
    "Warehouse",
    "StockLevel",
    "StockMovement",
    "Reservation",
    "ReorderAlert",
    "InventoryStats",
    # Stores
    "ProductStore",
    "InMemoryProductStore",
    "StockStore",
    "InMemoryStockStore",
    # Manager
    "InventoryManager",
    # Factory functions
    "create_inventory_manager",
    "create_product",
    "create_warehouse",
]
