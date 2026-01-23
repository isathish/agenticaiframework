"""
Enterprise Payment Gateway Module.

Payment processing, multiple providers,
refunds, and transaction management.

Example:
    # Create payment gateway
    payment = create_payment_gateway(stripe_config)
    
    # Charge customer
    result = await payment.charge(
        amount=9999,  # in cents
        currency="usd",
        source="tok_visa",
        description="Order #123",
    )
    
    # Refund
    refund = await payment.refund(
        transaction_id=result.transaction_id,
        amount=5000,  # partial refund
    )
    
    # Create subscription
    sub = await payment.create_subscription(
        customer_id="cus_123",
        plan_id="plan_premium",
    )
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
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


class PaymentError(Exception):
    """Payment error."""
    pass


class PaymentDeclinedError(PaymentError):
    """Payment declined."""
    pass


class InvalidCardError(PaymentError):
    """Invalid card."""
    pass


class InsufficientFundsError(PaymentError):
    """Insufficient funds."""
    pass


class PaymentStatus(str, Enum):
    """Payment status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    DISPUTED = "disputed"


class PaymentMethod(str, Enum):
    """Payment methods."""
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"
    CRYPTO = "crypto"
    PAYPAL = "paypal"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"


class SubscriptionStatus(str, Enum):
    """Subscription status."""
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    TRIALING = "trialing"
    PAUSED = "paused"


class Currency(str, Enum):
    """Currencies."""
    USD = "usd"
    EUR = "eur"
    GBP = "gbp"
    JPY = "jpy"
    AUD = "aud"
    CAD = "cad"
    CHF = "chf"
    INR = "inr"


@dataclass
class PaymentConfig:
    """Payment provider configuration."""
    provider: str = "mock"
    api_key: str = ""
    secret_key: str = ""
    webhook_secret: str = ""
    sandbox: bool = True
    default_currency: Currency = Currency.USD
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Card:
    """Payment card."""
    number: str = ""
    exp_month: int = 0
    exp_year: int = 0
    cvc: str = ""
    name: str = ""
    last_four: str = ""
    brand: str = ""
    country: str = ""


@dataclass
class Customer:
    """Customer."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    email: str = ""
    name: str = ""
    phone: str = ""
    default_source: Optional[str] = None
    sources: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Transaction:
    """Payment transaction."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    amount: int = 0  # in smallest currency unit (cents)
    currency: Currency = Currency.USD
    status: PaymentStatus = PaymentStatus.PENDING
    method: PaymentMethod = PaymentMethod.CARD
    customer_id: Optional[str] = None
    source: str = ""
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None
    refund_amount: int = 0
    fee: int = 0
    net_amount: int = 0


@dataclass
class Refund:
    """Refund."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    transaction_id: str = ""
    amount: int = 0
    reason: str = ""
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Plan:
    """Subscription plan."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    amount: int = 0
    currency: Currency = Currency.USD
    interval: str = "month"  # day, week, month, year
    interval_count: int = 1
    trial_days: int = 0
    features: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True


@dataclass
class Subscription:
    """Subscription."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = ""
    plan_id: str = ""
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    current_period_start: datetime = field(default_factory=datetime.utcnow)
    current_period_end: Optional[datetime] = None
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ChargeResult:
    """Charge result."""
    success: bool
    transaction_id: str
    status: PaymentStatus
    amount: int
    currency: Currency
    error: Optional[str] = None
    error_code: Optional[str] = None


@dataclass
class PaymentStats:
    """Payment statistics."""
    total_transactions: int = 0
    total_amount: int = 0
    successful: int = 0
    failed: int = 0
    refunded: int = 0
    by_method: Dict[str, int] = field(default_factory=dict)
    by_currency: Dict[str, int] = field(default_factory=dict)


# Payment provider base
class PaymentProvider(ABC):
    """Base payment provider."""
    
    @abstractmethod
    async def charge(
        self,
        amount: int,
        currency: Currency,
        source: str,
        **kwargs,
    ) -> ChargeResult:
        """Charge payment."""
        pass
    
    @abstractmethod
    async def refund(
        self,
        transaction_id: str,
        amount: Optional[int] = None,
        reason: str = "",
    ) -> Refund:
        """Refund payment."""
        pass
    
    @abstractmethod
    async def get_transaction(
        self,
        transaction_id: str,
    ) -> Optional[Transaction]:
        """Get transaction."""
        pass
    
    @abstractmethod
    async def create_customer(
        self,
        email: str,
        name: str = "",
        **kwargs,
    ) -> Customer:
        """Create customer."""
        pass
    
    @abstractmethod
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        **kwargs,
    ) -> Subscription:
        """Create subscription."""
        pass


# Mock provider
class MockPaymentProvider(PaymentProvider):
    """Mock payment provider for testing."""
    
    def __init__(self):
        self._transactions: Dict[str, Transaction] = {}
        self._customers: Dict[str, Customer] = {}
        self._subscriptions: Dict[str, Subscription] = {}
        self._plans: Dict[str, Plan] = {}
        self.should_fail: bool = False
        self.failure_rate: float = 0.0
    
    async def charge(
        self,
        amount: int,
        currency: Currency,
        source: str,
        customer_id: Optional[str] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> ChargeResult:
        """Charge (mock)."""
        import random
        
        # Simulate failure
        if self.should_fail or random.random() < self.failure_rate:
            return ChargeResult(
                success=False,
                transaction_id="",
                status=PaymentStatus.FAILED,
                amount=amount,
                currency=currency,
                error="Payment declined",
                error_code="card_declined",
            )
        
        # Create transaction
        transaction = Transaction(
            amount=amount,
            currency=currency,
            status=PaymentStatus.SUCCEEDED,
            customer_id=customer_id,
            source=source,
            description=description,
            metadata=metadata or {},
            fee=int(amount * 0.029 + 30),  # 2.9% + $0.30
        )
        transaction.net_amount = amount - transaction.fee
        
        self._transactions[transaction.id] = transaction
        
        return ChargeResult(
            success=True,
            transaction_id=transaction.id,
            status=PaymentStatus.SUCCEEDED,
            amount=amount,
            currency=currency,
        )
    
    async def refund(
        self,
        transaction_id: str,
        amount: Optional[int] = None,
        reason: str = "",
    ) -> Refund:
        """Refund (mock)."""
        transaction = self._transactions.get(transaction_id)
        if not transaction:
            raise PaymentError(f"Transaction not found: {transaction_id}")
        
        refund_amount = amount or transaction.amount
        if refund_amount > (transaction.amount - transaction.refund_amount):
            raise PaymentError("Refund amount exceeds available")
        
        refund = Refund(
            transaction_id=transaction_id,
            amount=refund_amount,
            reason=reason,
            status=PaymentStatus.SUCCEEDED,
        )
        
        # Update transaction
        transaction.refund_amount += refund_amount
        if transaction.refund_amount >= transaction.amount:
            transaction.status = PaymentStatus.REFUNDED
        else:
            transaction.status = PaymentStatus.PARTIALLY_REFUNDED
        transaction.updated_at = datetime.utcnow()
        
        return refund
    
    async def get_transaction(
        self,
        transaction_id: str,
    ) -> Optional[Transaction]:
        """Get transaction (mock)."""
        return self._transactions.get(transaction_id)
    
    async def create_customer(
        self,
        email: str,
        name: str = "",
        **kwargs,
    ) -> Customer:
        """Create customer (mock)."""
        customer = Customer(
            email=email,
            name=name,
            metadata=kwargs.get("metadata", {}),
        )
        self._customers[customer.id] = customer
        return customer
    
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        trial_days: int = 0,
        **kwargs,
    ) -> Subscription:
        """Create subscription (mock)."""
        now = datetime.utcnow()
        
        subscription = Subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            status=SubscriptionStatus.TRIALING if trial_days > 0 else SubscriptionStatus.ACTIVE,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            trial_start=now if trial_days > 0 else None,
            trial_end=now + timedelta(days=trial_days) if trial_days > 0 else None,
            metadata=kwargs.get("metadata", {}),
        )
        
        self._subscriptions[subscription.id] = subscription
        return subscription
    
    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True,
    ) -> Subscription:
        """Cancel subscription (mock)."""
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            raise PaymentError(f"Subscription not found: {subscription_id}")
        
        subscription.canceled_at = datetime.utcnow()
        if not at_period_end:
            subscription.status = SubscriptionStatus.CANCELED
            subscription.ended_at = datetime.utcnow()
        
        return subscription
    
    async def add_plan(self, plan: Plan) -> Plan:
        """Add plan (mock)."""
        self._plans[plan.id] = plan
        return plan


# Transaction store
class TransactionStore(ABC):
    """Transaction storage."""
    
    @abstractmethod
    async def save(self, transaction: Transaction) -> None:
        """Save transaction."""
        pass
    
    @abstractmethod
    async def get(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction."""
        pass
    
    @abstractmethod
    async def list(
        self,
        customer_id: Optional[str] = None,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
    ) -> List[Transaction]:
        """List transactions."""
        pass


class InMemoryTransactionStore(TransactionStore):
    """In-memory transaction store."""
    
    def __init__(self):
        self._transactions: Dict[str, Transaction] = {}
    
    async def save(self, transaction: Transaction) -> None:
        transaction.updated_at = datetime.utcnow()
        self._transactions[transaction.id] = transaction
    
    async def get(self, transaction_id: str) -> Optional[Transaction]:
        return self._transactions.get(transaction_id)
    
    async def list(
        self,
        customer_id: Optional[str] = None,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
    ) -> List[Transaction]:
        results = []
        for tx in self._transactions.values():
            if customer_id and tx.customer_id != customer_id:
                continue
            if status and tx.status != status:
                continue
            results.append(tx)
            if len(results) >= limit:
                break
        return results


# Payment gateway
class PaymentGateway:
    """Payment gateway service."""
    
    def __init__(
        self,
        provider: PaymentProvider,
        store: Optional[TransactionStore] = None,
        config: Optional[PaymentConfig] = None,
    ):
        self.provider = provider
        self.store = store or InMemoryTransactionStore()
        self.config = config or PaymentConfig()
        self._stats = PaymentStats()
        self._webhooks: List[Callable] = []
    
    async def charge(
        self,
        amount: int,
        currency: Optional[Currency] = None,
        source: str = "",
        customer_id: Optional[str] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> ChargeResult:
        """Charge payment."""
        currency = currency or self.config.default_currency
        
        result = await self.provider.charge(
            amount=amount,
            currency=currency,
            source=source,
            customer_id=customer_id,
            description=description,
            metadata=metadata,
        )
        
        # Update stats
        self._stats.total_transactions += 1
        if result.success:
            self._stats.successful += 1
            self._stats.total_amount += amount
        else:
            self._stats.failed += 1
        
        # Store transaction
        if result.success and result.transaction_id:
            transaction = await self.provider.get_transaction(result.transaction_id)
            if transaction:
                await self.store.save(transaction)
        
        logger.info(
            f"Payment {'succeeded' if result.success else 'failed'}: "
            f"{amount/100:.2f} {currency.value}"
        )
        
        return result
    
    async def refund(
        self,
        transaction_id: str,
        amount: Optional[int] = None,
        reason: str = "",
    ) -> Refund:
        """Refund payment."""
        refund = await self.provider.refund(
            transaction_id=transaction_id,
            amount=amount,
            reason=reason,
        )
        
        self._stats.refunded += 1
        
        logger.info(f"Refund processed: {refund.amount/100:.2f} for {transaction_id}")
        
        return refund
    
    async def get_transaction(
        self,
        transaction_id: str,
    ) -> Optional[Transaction]:
        """Get transaction."""
        # Check store first
        transaction = await self.store.get(transaction_id)
        if transaction:
            return transaction
        
        # Fallback to provider
        return await self.provider.get_transaction(transaction_id)
    
    async def list_transactions(
        self,
        customer_id: Optional[str] = None,
        status: Optional[PaymentStatus] = None,
        limit: int = 50,
    ) -> List[Transaction]:
        """List transactions."""
        return await self.store.list(
            customer_id=customer_id,
            status=status,
            limit=limit,
        )
    
    async def create_customer(
        self,
        email: str,
        name: str = "",
        **kwargs,
    ) -> Customer:
        """Create customer."""
        return await self.provider.create_customer(
            email=email,
            name=name,
            **kwargs,
        )
    
    async def create_subscription(
        self,
        customer_id: str,
        plan_id: str,
        **kwargs,
    ) -> Subscription:
        """Create subscription."""
        return await self.provider.create_subscription(
            customer_id=customer_id,
            plan_id=plan_id,
            **kwargs,
        )
    
    def on_webhook(self, callback: Callable) -> None:
        """Register webhook handler."""
        self._webhooks.append(callback)
    
    async def handle_webhook(
        self,
        payload: Dict[str, Any],
        signature: str = "",
    ) -> bool:
        """Handle webhook."""
        # Verify signature if webhook secret configured
        if self.config.webhook_secret and signature:
            expected = hmac.new(
                self.config.webhook_secret.encode(),
                json.dumps(payload, sort_keys=True).encode(),
                hashlib.sha256,
            ).hexdigest()
            
            if not hmac.compare_digest(signature, expected):
                logger.warning("Invalid webhook signature")
                return False
        
        # Call handlers
        for handler in self._webhooks:
            try:
                await handler(payload) if asyncio.iscoroutinefunction(handler) else handler(payload)
            except Exception as e:
                logger.error(f"Webhook handler error: {e}")
        
        return True
    
    def get_stats(self) -> PaymentStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_payment_gateway(
    config: Optional[PaymentConfig] = None,
    provider: Optional[PaymentProvider] = None,
) -> PaymentGateway:
    """Create payment gateway."""
    if provider is None:
        provider = MockPaymentProvider()
    
    return PaymentGateway(
        provider=provider,
        config=config,
    )


def create_plan(
    name: str,
    amount: int,
    currency: Currency = Currency.USD,
    interval: str = "month",
    **kwargs,
) -> Plan:
    """Create subscription plan."""
    return Plan(
        name=name,
        amount=amount,
        currency=currency,
        interval=interval,
        **kwargs,
    )


def create_payment_config(
    provider: str = "mock",
    api_key: str = "",
    secret_key: str = "",
    **kwargs,
) -> PaymentConfig:
    """Create payment config."""
    return PaymentConfig(
        provider=provider,
        api_key=api_key,
        secret_key=secret_key,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "PaymentError",
    "PaymentDeclinedError",
    "InvalidCardError",
    "InsufficientFundsError",
    # Enums
    "PaymentStatus",
    "PaymentMethod",
    "SubscriptionStatus",
    "Currency",
    # Data classes
    "PaymentConfig",
    "Card",
    "Customer",
    "Transaction",
    "Refund",
    "Plan",
    "Subscription",
    "ChargeResult",
    "PaymentStats",
    # Providers
    "PaymentProvider",
    "MockPaymentProvider",
    # Store
    "TransactionStore",
    "InMemoryTransactionStore",
    # Service
    "PaymentGateway",
    # Factory functions
    "create_payment_gateway",
    "create_plan",
    "create_payment_config",
]
