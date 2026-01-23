"""
Enterprise Order Processing Module.

Order workflow, fulfillment, status tracking,
returns, and order lifecycle management.

Example:
    # Create order processor
    orders = create_order_processor()
    
    # Create order
    order = await orders.create_order(
        customer_id="cust_123",
        items=[
            {"sku": "WIDGET-001", "quantity": 2, "price": 29.99},
            {"sku": "WIDGET-002", "quantity": 1, "price": 49.99},
        ],
        shipping_address={"city": "New York", "zip": "10001"},
    )
    
    # Process payment
    await orders.process_payment(order.id, payment_id="pay_xyz")
    
    # Fulfill order
    await orders.fulfill(order.id, tracking_number="TRACK123")
    
    # Track status
    history = await orders.get_history(order.id)
"""

from __future__ import annotations

import asyncio
import json
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


class OrderError(Exception):
    """Order error."""
    pass


class OrderNotFoundError(OrderError):
    """Order not found."""
    pass


class InvalidStateTransitionError(OrderError):
    """Invalid state transition."""
    pass


class OrderStatus(str, Enum):
    """Order status."""
    DRAFT = "draft"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    ON_HOLD = "on_hold"


class PaymentStatus(str, Enum):
    """Payment status."""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class FulfillmentStatus(str, Enum):
    """Fulfillment status."""
    UNFULFILLED = "unfulfilled"
    PARTIALLY_FULFILLED = "partially_fulfilled"
    FULFILLED = "fulfilled"
    SHIPPED = "shipped"
    DELIVERED = "delivered"


class ReturnStatus(str, Enum):
    """Return status."""
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    RECEIVED = "received"
    REFUNDED = "refunded"


@dataclass
class Address:
    """Shipping/billing address."""
    line1: str = ""
    line2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    phone: str = ""


@dataclass
class OrderItem:
    """Order line item."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sku: str = ""
    name: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    discount: float = 0.0
    tax: float = 0.0
    fulfilled_quantity: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def subtotal(self) -> float:
        """Item subtotal."""
        return self.quantity * self.unit_price
    
    @property
    def total(self) -> float:
        """Item total with discount and tax."""
        return self.subtotal - self.discount + self.tax


@dataclass
class Shipment:
    """Order shipment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    carrier: str = ""
    tracking_number: str = ""
    tracking_url: str = ""
    items: List[str] = field(default_factory=list)  # item IDs
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    status: str = "pending"


@dataclass
class Payment:
    """Order payment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    amount: float = 0.0
    currency: str = "USD"
    method: str = ""  # credit_card, paypal, etc.
    provider: str = ""
    transaction_id: str = ""
    status: PaymentStatus = PaymentStatus.PENDING
    captured_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Return:
    """Order return."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    items: List[Dict[str, Any]] = field(default_factory=list)
    reason: str = ""
    status: ReturnStatus = ReturnStatus.REQUESTED
    refund_amount: float = 0.0
    notes: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None


@dataclass
class Order:
    """Order."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_number: str = ""
    customer_id: str = ""
    email: str = ""
    phone: str = ""
    items: List[OrderItem] = field(default_factory=list)
    shipping_address: Address = field(default_factory=Address)
    billing_address: Address = field(default_factory=Address)
    status: OrderStatus = OrderStatus.DRAFT
    payment_status: PaymentStatus = PaymentStatus.PENDING
    fulfillment_status: FulfillmentStatus = FulfillmentStatus.UNFULFILLED
    subtotal: float = 0.0
    discount: float = 0.0
    shipping: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    currency: str = "USD"
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""  # web, mobile, pos, etc.
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_totals(self) -> None:
        """Calculate order totals."""
        self.subtotal = sum(item.subtotal for item in self.items)
        self.tax = sum(item.tax for item in self.items)
        item_discounts = sum(item.discount for item in self.items)
        self.total = self.subtotal - self.discount - item_discounts + self.tax + self.shipping


@dataclass
class OrderEvent:
    """Order history event."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    order_id: str = ""
    event_type: str = ""
    description: str = ""
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    performed_by: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OrderStats:
    """Order statistics."""
    total_orders: int = 0
    pending_orders: int = 0
    completed_orders: int = 0
    cancelled_orders: int = 0
    total_revenue: float = 0.0
    average_order_value: float = 0.0


# Order store
class OrderStore(ABC):
    """Order storage."""
    
    @abstractmethod
    async def save(self, order: Order) -> None:
        pass
    
    @abstractmethod
    async def get(self, order_id: str) -> Optional[Order]:
        pass
    
    @abstractmethod
    async def query(
        self,
        customer_id: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Order]:
        pass


class InMemoryOrderStore(OrderStore):
    """In-memory order store."""
    
    def __init__(self):
        self._orders: Dict[str, Order] = {}
        self._counter = 1000
    
    async def save(self, order: Order) -> None:
        if not order.order_number:
            self._counter += 1
            order.order_number = f"ORD-{self._counter}"
        order.updated_at = datetime.utcnow()
        self._orders[order.id] = order
    
    async def get(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)
    
    async def query(
        self,
        customer_id: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Order]:
        results = list(self._orders.values())
        
        if customer_id:
            results = [o for o in results if o.customer_id == customer_id]
        if status:
            results = [o for o in results if o.status == status]
        if start:
            results = [o for o in results if o.created_at >= start]
        if end:
            results = [o for o in results if o.created_at <= end]
        
        return sorted(results, key=lambda o: o.created_at, reverse=True)


# Order processor
class OrderProcessor:
    """Order processor."""
    
    # Valid state transitions
    TRANSITIONS = {
        OrderStatus.DRAFT: [OrderStatus.PENDING, OrderStatus.CANCELLED],
        OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED, OrderStatus.ON_HOLD],
        OrderStatus.CONFIRMED: [OrderStatus.PROCESSING, OrderStatus.CANCELLED, OrderStatus.ON_HOLD],
        OrderStatus.PROCESSING: [OrderStatus.SHIPPED, OrderStatus.CANCELLED, OrderStatus.ON_HOLD],
        OrderStatus.SHIPPED: [OrderStatus.DELIVERED],
        OrderStatus.DELIVERED: [OrderStatus.COMPLETED, OrderStatus.REFUNDED],
        OrderStatus.COMPLETED: [OrderStatus.REFUNDED],
        OrderStatus.ON_HOLD: [OrderStatus.PENDING, OrderStatus.CANCELLED],
        OrderStatus.CANCELLED: [],
        OrderStatus.REFUNDED: [],
    }
    
    def __init__(
        self,
        order_store: Optional[OrderStore] = None,
    ):
        self._orders = order_store or InMemoryOrderStore()
        self._events: Dict[str, List[OrderEvent]] = {}
        self._shipments: Dict[str, List[Shipment]] = {}
        self._payments: Dict[str, List[Payment]] = {}
        self._returns: Dict[str, List[Return]] = {}
        self._stats = OrderStats()
    
    async def create_order(
        self,
        customer_id: str,
        items: List[Dict[str, Any]],
        shipping_address: Optional[Dict[str, str]] = None,
        billing_address: Optional[Dict[str, str]] = None,
        shipping: float = 0.0,
        discount: float = 0.0,
        **kwargs,
    ) -> Order:
        """Create order."""
        order_items = [
            OrderItem(
                sku=item.get("sku", ""),
                name=item.get("name", ""),
                quantity=item.get("quantity", 1),
                unit_price=item.get("price", 0.0),
                discount=item.get("discount", 0.0),
                tax=item.get("tax", 0.0),
            )
            for item in items
        ]
        
        order = Order(
            customer_id=customer_id,
            items=order_items,
            shipping_address=Address(**shipping_address) if shipping_address else Address(),
            billing_address=Address(**billing_address) if billing_address else Address(),
            shipping=shipping,
            discount=discount,
            status=OrderStatus.DRAFT,
            **kwargs,
        )
        
        order.calculate_totals()
        
        await self._orders.save(order)
        await self._record_event(order.id, "order_created", "Order created")
        
        self._stats.total_orders += 1
        
        logger.info(f"Order created: {order.order_number}")
        
        return order
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order."""
        return await self._orders.get(order_id)
    
    async def update_order(
        self,
        order_id: str,
        **updates,
    ) -> Optional[Order]:
        """Update order."""
        order = await self._orders.get(order_id)
        if not order:
            return None
        
        for key, value in updates.items():
            if hasattr(order, key):
                setattr(order, key, value)
        
        order.calculate_totals()
        await self._orders.save(order)
        await self._record_event(order.id, "order_updated", f"Order updated: {list(updates.keys())}")
        
        return order
    
    async def submit_order(self, order_id: str) -> Order:
        """Submit draft order."""
        order = await self._orders.get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        await self._transition(order, OrderStatus.PENDING)
        self._stats.pending_orders += 1
        
        return order
    
    async def confirm_order(self, order_id: str) -> Order:
        """Confirm order."""
        order = await self._orders.get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        await self._transition(order, OrderStatus.CONFIRMED)
        self._stats.pending_orders -= 1
        
        return order
    
    async def cancel_order(
        self,
        order_id: str,
        reason: str = "",
    ) -> Order:
        """Cancel order."""
        order = await self._orders.get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        await self._transition(order, OrderStatus.CANCELLED)
        order.notes = f"{order.notes}\nCancellation: {reason}".strip()
        await self._orders.save(order)
        
        self._stats.cancelled_orders += 1
        
        return order
    
    async def hold_order(
        self,
        order_id: str,
        reason: str = "",
    ) -> Order:
        """Put order on hold."""
        order = await self._orders.get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        await self._transition(order, OrderStatus.ON_HOLD)
        order.notes = f"{order.notes}\nOn hold: {reason}".strip()
        await self._orders.save(order)
        
        return order
    
    async def process_payment(
        self,
        order_id: str,
        payment_id: str,
        amount: Optional[float] = None,
        method: str = "credit_card",
        provider: str = "",
    ) -> Payment:
        """Process payment."""
        order = await self._orders.get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        payment = Payment(
            order_id=order_id,
            amount=amount or order.total,
            currency=order.currency,
            method=method,
            provider=provider,
            transaction_id=payment_id,
            status=PaymentStatus.CAPTURED,
            captured_at=datetime.utcnow(),
        )
        
        if order_id not in self._payments:
            self._payments[order_id] = []
        self._payments[order_id].append(payment)
        
        # Update order payment status
        total_paid = sum(p.amount for p in self._payments[order_id] if p.status == PaymentStatus.CAPTURED)
        
        if total_paid >= order.total:
            order.payment_status = PaymentStatus.PAID
        elif total_paid > 0:
            order.payment_status = PaymentStatus.PARTIALLY_PAID
        
        await self._orders.save(order)
        await self._record_event(order_id, "payment_captured", f"Payment captured: {payment.amount}")
        
        self._stats.total_revenue += payment.amount
        
        return payment
    
    async def fulfill(
        self,
        order_id: str,
        item_ids: Optional[List[str]] = None,
        carrier: str = "",
        tracking_number: str = "",
    ) -> Shipment:
        """Fulfill order."""
        order = await self._orders.get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        # Fulfill items
        items_to_fulfill = item_ids or [item.id for item in order.items]
        
        for item in order.items:
            if item.id in items_to_fulfill:
                item.fulfilled_quantity = item.quantity
        
        # Create shipment
        shipment = Shipment(
            order_id=order_id,
            carrier=carrier,
            tracking_number=tracking_number,
            items=items_to_fulfill,
            shipped_at=datetime.utcnow(),
            status="shipped",
        )
        
        if order_id not in self._shipments:
            self._shipments[order_id] = []
        self._shipments[order_id].append(shipment)
        
        # Update fulfillment status
        total_items = sum(item.quantity for item in order.items)
        fulfilled_items = sum(item.fulfilled_quantity for item in order.items)
        
        if fulfilled_items >= total_items:
            order.fulfillment_status = FulfillmentStatus.FULFILLED
            await self._transition(order, OrderStatus.SHIPPED)
        else:
            order.fulfillment_status = FulfillmentStatus.PARTIALLY_FULFILLED
            await self._transition(order, OrderStatus.PROCESSING)
        
        await self._orders.save(order)
        await self._record_event(order_id, "shipment_created", f"Shipped via {carrier}: {tracking_number}")
        
        return shipment
    
    async def mark_delivered(self, order_id: str) -> Order:
        """Mark order as delivered."""
        order = await self._orders.get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        order.fulfillment_status = FulfillmentStatus.DELIVERED
        await self._transition(order, OrderStatus.DELIVERED)
        
        # Update shipments
        if order_id in self._shipments:
            for shipment in self._shipments[order_id]:
                shipment.delivered_at = datetime.utcnow()
                shipment.status = "delivered"
        
        return order
    
    async def complete_order(self, order_id: str) -> Order:
        """Complete order."""
        order = await self._orders.get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        await self._transition(order, OrderStatus.COMPLETED)
        self._stats.completed_orders += 1
        
        # Calculate average order value
        if self._stats.completed_orders > 0:
            self._stats.average_order_value = (
                self._stats.total_revenue / self._stats.completed_orders
            )
        
        return order
    
    async def request_return(
        self,
        order_id: str,
        items: List[Dict[str, Any]],
        reason: str = "",
    ) -> Return:
        """Request return."""
        order = await self._orders.get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order not found: {order_id}")
        
        return_request = Return(
            order_id=order_id,
            items=items,
            reason=reason,
            status=ReturnStatus.REQUESTED,
        )
        
        if order_id not in self._returns:
            self._returns[order_id] = []
        self._returns[order_id].append(return_request)
        
        await self._record_event(order_id, "return_requested", f"Return requested: {reason}")
        
        return return_request
    
    async def process_return(
        self,
        return_id: str,
        approved: bool = True,
        refund_amount: float = 0.0,
    ) -> Return:
        """Process return."""
        for order_id, returns in self._returns.items():
            for ret in returns:
                if ret.id == return_id:
                    if approved:
                        ret.status = ReturnStatus.APPROVED
                        ret.refund_amount = refund_amount
                    else:
                        ret.status = ReturnStatus.REJECTED
                    
                    ret.processed_at = datetime.utcnow()
                    
                    await self._record_event(
                        order_id,
                        "return_processed",
                        f"Return {'approved' if approved else 'rejected'}",
                    )
                    
                    return ret
        
        raise OrderError(f"Return not found: {return_id}")
    
    async def _transition(
        self,
        order: Order,
        new_status: OrderStatus,
    ) -> None:
        """Transition order status."""
        current = order.status
        allowed = self.TRANSITIONS.get(current, [])
        
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition from {current} to {new_status}"
            )
        
        old_status = order.status
        order.status = new_status
        
        await self._orders.save(order)
        await self._record_event(
            order.id,
            "status_changed",
            f"Status: {old_status.value} → {new_status.value}",
            old_value=old_status.value,
            new_value=new_status.value,
        )
        
        logger.info(f"Order {order.order_number}: {old_status} → {new_status}")
    
    async def _record_event(
        self,
        order_id: str,
        event_type: str,
        description: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        performed_by: str = "",
    ) -> None:
        """Record order event."""
        event = OrderEvent(
            order_id=order_id,
            event_type=event_type,
            description=description,
            old_value=old_value,
            new_value=new_value,
            performed_by=performed_by,
        )
        
        if order_id not in self._events:
            self._events[order_id] = []
        self._events[order_id].append(event)
    
    async def get_history(self, order_id: str) -> List[OrderEvent]:
        """Get order history."""
        return self._events.get(order_id, [])
    
    async def get_shipments(self, order_id: str) -> List[Shipment]:
        """Get order shipments."""
        return self._shipments.get(order_id, [])
    
    async def get_payments(self, order_id: str) -> List[Payment]:
        """Get order payments."""
        return self._payments.get(order_id, [])
    
    async def get_returns(self, order_id: str) -> List[Return]:
        """Get order returns."""
        return self._returns.get(order_id, [])
    
    async def search_orders(
        self,
        customer_id: Optional[str] = None,
        status: Optional[OrderStatus] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> List[Order]:
        """Search orders."""
        return await self._orders.query(
            customer_id=customer_id,
            status=status,
            start=start,
            end=end,
        )
    
    def get_stats(self) -> OrderStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_order_processor() -> OrderProcessor:
    """Create order processor."""
    return OrderProcessor()


def create_order(
    customer_id: str,
    **kwargs,
) -> Order:
    """Create order."""
    return Order(customer_id=customer_id, **kwargs)


def create_order_item(
    sku: str,
    quantity: int = 1,
    unit_price: float = 0.0,
    **kwargs,
) -> OrderItem:
    """Create order item."""
    return OrderItem(
        sku=sku,
        quantity=quantity,
        unit_price=unit_price,
        **kwargs,
    )


def create_address(**kwargs) -> Address:
    """Create address."""
    return Address(**kwargs)


__all__ = [
    # Exceptions
    "OrderError",
    "OrderNotFoundError",
    "InvalidStateTransitionError",
    # Enums
    "OrderStatus",
    "PaymentStatus",
    "FulfillmentStatus",
    "ReturnStatus",
    # Data classes
    "Address",
    "OrderItem",
    "Shipment",
    "Payment",
    "Return",
    "Order",
    "OrderEvent",
    "OrderStats",
    # Stores
    "OrderStore",
    "InMemoryOrderStore",
    # Processor
    "OrderProcessor",
    # Factory functions
    "create_order_processor",
    "create_order",
    "create_order_item",
    "create_address",
]
