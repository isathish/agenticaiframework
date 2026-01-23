"""
Enterprise Invoice Generator Module.

Invoice creation, PDF generation,
line items, taxes, and payment tracking.

Example:
    # Create invoice service
    invoices = create_invoice_service()
    
    # Create invoice
    invoice = await invoices.create(
        customer_id="cust_123",
        items=[
            InvoiceItem(description="Widget Pro", quantity=2, unit_price=9999),
            InvoiceItem(description="Support", quantity=1, unit_price=4999),
        ],
    )
    
    # Add tax
    invoice.add_tax("Sales Tax", rate=0.08)
    
    # Generate PDF
    pdf = await invoices.generate_pdf(invoice.id)
    
    # Send invoice
    await invoices.send(invoice.id, email="customer@example.com")
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
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


class InvoiceError(Exception):
    """Invoice error."""
    pass


class InvoiceStatus(str, Enum):
    """Invoice status."""
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    PAID = "paid"
    PARTIAL = "partial"
    OVERDUE = "overdue"
    CANCELED = "canceled"
    REFUNDED = "refunded"


class PaymentTerms(str, Enum):
    """Payment terms."""
    DUE_ON_RECEIPT = "due_on_receipt"
    NET_7 = "net_7"
    NET_15 = "net_15"
    NET_30 = "net_30"
    NET_60 = "net_60"
    NET_90 = "net_90"
    CUSTOM = "custom"


class DiscountType(str, Enum):
    """Discount type."""
    PERCENTAGE = "percentage"
    FIXED = "fixed"


@dataclass
class Address:
    """Address."""
    line1: str = ""
    line2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    
    def format(self) -> str:
        """Format address."""
        lines = [self.line1]
        if self.line2:
            lines.append(self.line2)
        lines.append(f"{self.city}, {self.state} {self.postal_code}")
        if self.country:
            lines.append(self.country)
        return "\n".join(lines)


@dataclass
class Customer:
    """Invoice customer."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    billing_address: Address = field(default_factory=Address)
    shipping_address: Optional[Address] = None
    tax_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InvoiceItem:
    """Invoice line item."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    quantity: Decimal = Decimal("1")
    unit_price: int = 0  # in cents
    discount: int = 0  # in cents
    discount_type: DiscountType = DiscountType.FIXED
    tax_rate: Decimal = Decimal("0")
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def subtotal(self) -> int:
        """Calculate subtotal."""
        return int(self.quantity * self.unit_price)
    
    @property
    def discount_amount(self) -> int:
        """Calculate discount."""
        if self.discount_type == DiscountType.PERCENTAGE:
            return int(self.subtotal * self.discount / 100)
        return self.discount
    
    @property
    def tax_amount(self) -> int:
        """Calculate tax."""
        taxable = self.subtotal - self.discount_amount
        return int(taxable * self.tax_rate)
    
    @property
    def total(self) -> int:
        """Calculate total."""
        return self.subtotal - self.discount_amount + self.tax_amount


@dataclass
class Tax:
    """Tax line."""
    name: str = ""
    rate: Decimal = Decimal("0")
    amount: int = 0
    
    def calculate(self, subtotal: int) -> int:
        """Calculate tax amount."""
        self.amount = int(Decimal(subtotal) * self.rate)
        return self.amount


@dataclass
class Discount:
    """Invoice discount."""
    description: str = ""
    amount: int = 0
    type: DiscountType = DiscountType.FIXED
    
    def apply(self, subtotal: int) -> int:
        """Apply discount."""
        if self.type == DiscountType.PERCENTAGE:
            return int(subtotal * self.amount / 100)
        return min(self.amount, subtotal)


@dataclass
class Payment:
    """Invoice payment."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    amount: int = 0
    method: str = "card"
    reference: str = ""
    paid_at: datetime = field(default_factory=datetime.utcnow)
    notes: str = ""


@dataclass
class Invoice:
    """Invoice."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    number: str = ""
    customer_id: str = ""
    customer: Optional[Customer] = None
    status: InvoiceStatus = InvoiceStatus.DRAFT
    items: List[InvoiceItem] = field(default_factory=list)
    taxes: List[Tax] = field(default_factory=list)
    discounts: List[Discount] = field(default_factory=list)
    payments: List[Payment] = field(default_factory=list)
    currency: str = "USD"
    payment_terms: PaymentTerms = PaymentTerms.NET_30
    issue_date: datetime = field(default_factory=datetime.utcnow)
    due_date: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    notes: str = ""
    footer: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if not self.due_date:
            self._calculate_due_date()
    
    def _calculate_due_date(self) -> None:
        """Calculate due date from terms."""
        days = {
            PaymentTerms.DUE_ON_RECEIPT: 0,
            PaymentTerms.NET_7: 7,
            PaymentTerms.NET_15: 15,
            PaymentTerms.NET_30: 30,
            PaymentTerms.NET_60: 60,
            PaymentTerms.NET_90: 90,
        }
        self.due_date = self.issue_date + timedelta(
            days=days.get(self.payment_terms, 30)
        )
    
    def add_item(self, item: InvoiceItem) -> None:
        """Add line item."""
        self.items.append(item)
        self.updated_at = datetime.utcnow()
    
    def remove_item(self, item_id: str) -> bool:
        """Remove line item."""
        for i, item in enumerate(self.items):
            if item.id == item_id:
                self.items.pop(i)
                self.updated_at = datetime.utcnow()
                return True
        return False
    
    def add_tax(self, name: str, rate: float) -> Tax:
        """Add tax."""
        tax = Tax(name=name, rate=Decimal(str(rate)))
        self.taxes.append(tax)
        self.updated_at = datetime.utcnow()
        return tax
    
    def add_discount(
        self,
        description: str,
        amount: int,
        discount_type: DiscountType = DiscountType.FIXED,
    ) -> Discount:
        """Add discount."""
        discount = Discount(
            description=description,
            amount=amount,
            type=discount_type,
        )
        self.discounts.append(discount)
        self.updated_at = datetime.utcnow()
        return discount
    
    def add_payment(
        self,
        amount: int,
        method: str = "card",
        reference: str = "",
    ) -> Payment:
        """Record payment."""
        payment = Payment(
            amount=amount,
            method=method,
            reference=reference,
        )
        self.payments.append(payment)
        self._update_status()
        self.updated_at = datetime.utcnow()
        return payment
    
    def _update_status(self) -> None:
        """Update status based on payments."""
        if self.status in [InvoiceStatus.CANCELED, InvoiceStatus.REFUNDED]:
            return
        
        paid = self.amount_paid
        total = self.total
        
        if paid >= total:
            self.status = InvoiceStatus.PAID
            self.paid_at = datetime.utcnow()
        elif paid > 0:
            self.status = InvoiceStatus.PARTIAL
        elif self.due_date and datetime.utcnow() > self.due_date:
            self.status = InvoiceStatus.OVERDUE
    
    @property
    def subtotal(self) -> int:
        """Calculate subtotal."""
        return sum(item.subtotal for item in self.items)
    
    @property
    def total_discounts(self) -> int:
        """Calculate total discounts."""
        item_discounts = sum(item.discount_amount for item in self.items)
        invoice_discounts = sum(d.apply(self.subtotal) for d in self.discounts)
        return item_discounts + invoice_discounts
    
    @property
    def taxable_amount(self) -> int:
        """Calculate taxable amount."""
        return self.subtotal - self.total_discounts
    
    @property
    def total_taxes(self) -> int:
        """Calculate total taxes."""
        item_taxes = sum(item.tax_amount for item in self.items)
        invoice_taxes = sum(t.calculate(self.taxable_amount) for t in self.taxes)
        return item_taxes + invoice_taxes
    
    @property
    def total(self) -> int:
        """Calculate total."""
        return self.taxable_amount + self.total_taxes
    
    @property
    def amount_paid(self) -> int:
        """Calculate amount paid."""
        return sum(p.amount for p in self.payments)
    
    @property
    def amount_due(self) -> int:
        """Calculate amount due."""
        return max(0, self.total - self.amount_paid)
    
    @property
    def is_paid(self) -> bool:
        """Check if fully paid."""
        return self.amount_paid >= self.total
    
    @property
    def is_overdue(self) -> bool:
        """Check if overdue."""
        if self.is_paid or not self.due_date:
            return False
        return datetime.utcnow() > self.due_date


@dataclass
class InvoiceTemplate:
    """Invoice template."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    company_name: str = ""
    company_address: Address = field(default_factory=Address)
    logo_url: str = ""
    primary_color: str = "#2196F3"
    footer_text: str = ""
    terms_and_conditions: str = ""


@dataclass
class InvoiceStats:
    """Invoice statistics."""
    total_invoices: int = 0
    total_amount: int = 0
    paid_amount: int = 0
    outstanding_amount: int = 0
    overdue_amount: int = 0
    by_status: Dict[str, int] = field(default_factory=dict)


# Invoice store
class InvoiceStore(ABC):
    """Invoice storage."""
    
    @abstractmethod
    async def save(self, invoice: Invoice) -> None:
        """Save invoice."""
        pass
    
    @abstractmethod
    async def get(self, invoice_id: str) -> Optional[Invoice]:
        """Get invoice."""
        pass
    
    @abstractmethod
    async def get_by_number(self, number: str) -> Optional[Invoice]:
        """Get by number."""
        pass
    
    @abstractmethod
    async def list(
        self,
        customer_id: Optional[str] = None,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
    ) -> List[Invoice]:
        """List invoices."""
        pass
    
    @abstractmethod
    async def delete(self, invoice_id: str) -> bool:
        """Delete invoice."""
        pass
    
    @abstractmethod
    async def get_next_number(self) -> str:
        """Get next invoice number."""
        pass


class InMemoryInvoiceStore(InvoiceStore):
    """In-memory invoice store."""
    
    def __init__(self, number_prefix: str = "INV-"):
        self._invoices: Dict[str, Invoice] = {}
        self._counter: int = 0
        self._prefix = number_prefix
    
    async def save(self, invoice: Invoice) -> None:
        invoice.updated_at = datetime.utcnow()
        self._invoices[invoice.id] = invoice
    
    async def get(self, invoice_id: str) -> Optional[Invoice]:
        return self._invoices.get(invoice_id)
    
    async def get_by_number(self, number: str) -> Optional[Invoice]:
        for invoice in self._invoices.values():
            if invoice.number == number:
                return invoice
        return None
    
    async def list(
        self,
        customer_id: Optional[str] = None,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
    ) -> List[Invoice]:
        results = []
        for invoice in sorted(
            self._invoices.values(),
            key=lambda i: i.created_at,
            reverse=True,
        ):
            if customer_id and invoice.customer_id != customer_id:
                continue
            if status and invoice.status != status:
                continue
            results.append(invoice)
            if len(results) >= limit:
                break
        return results
    
    async def delete(self, invoice_id: str) -> bool:
        if invoice_id in self._invoices:
            del self._invoices[invoice_id]
            return True
        return False
    
    async def get_next_number(self) -> str:
        self._counter += 1
        return f"{self._prefix}{self._counter:06d}"


# PDF generator
class PDFGenerator(ABC):
    """PDF generator."""
    
    @abstractmethod
    async def generate(
        self,
        invoice: Invoice,
        template: Optional[InvoiceTemplate] = None,
    ) -> bytes:
        """Generate PDF."""
        pass


class SimplePDFGenerator(PDFGenerator):
    """Simple PDF generator (HTML-based)."""
    
    async def generate(
        self,
        invoice: Invoice,
        template: Optional[InvoiceTemplate] = None,
    ) -> bytes:
        """Generate PDF as HTML."""
        template = template or InvoiceTemplate()
        
        # Generate HTML
        items_html = ""
        for item in invoice.items:
            items_html += f"""
                <tr>
                    <td>{item.description}</td>
                    <td style="text-align: right">{item.quantity}</td>
                    <td style="text-align: right">${item.unit_price/100:.2f}</td>
                    <td style="text-align: right">${item.total/100:.2f}</td>
                </tr>
            """
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Invoice {invoice.number}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            color: #333;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 40px;
        }}
        .invoice-title {{
            font-size: 32px;
            color: {template.primary_color};
        }}
        .invoice-meta {{
            text-align: right;
        }}
        .invoice-meta p {{
            margin: 5px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background: {template.primary_color};
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        .totals {{
            width: 300px;
            margin-left: auto;
        }}
        .totals td {{
            padding: 8px;
        }}
        .totals .total {{
            font-weight: bold;
            font-size: 18px;
            border-top: 2px solid #333;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 12px;
        }}
        .status {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            background: {'#4caf50' if invoice.status == InvoiceStatus.PAID else '#ff9800'};
            color: white;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <div class="invoice-title">INVOICE</div>
            <div>{template.company_name}</div>
            <div style="white-space: pre-line">{template.company_address.format() if template.company_address else ''}</div>
        </div>
        <div class="invoice-meta">
            <p><strong>Invoice #:</strong> {invoice.number}</p>
            <p><strong>Date:</strong> {invoice.issue_date.strftime('%Y-%m-%d')}</p>
            <p><strong>Due Date:</strong> {invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else 'N/A'}</p>
            <p><span class="status">{invoice.status.value.upper()}</span></p>
        </div>
    </div>
    
    <div style="margin-bottom: 30px;">
        <strong>Bill To:</strong><br>
        {invoice.customer.name if invoice.customer else ''}<br>
        {invoice.customer.company if invoice.customer and invoice.customer.company else ''}<br>
        {invoice.customer.billing_address.format() if invoice.customer else ''}
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Description</th>
                <th style="text-align: right">Qty</th>
                <th style="text-align: right">Unit Price</th>
                <th style="text-align: right">Amount</th>
            </tr>
        </thead>
        <tbody>
            {items_html}
        </tbody>
    </table>
    
    <table class="totals">
        <tr>
            <td>Subtotal</td>
            <td style="text-align: right">${invoice.subtotal/100:.2f}</td>
        </tr>
        {''.join(f'<tr><td>Discount</td><td style="text-align: right">-${d.apply(invoice.subtotal)/100:.2f}</td></tr>' for d in invoice.discounts)}
        {''.join(f'<tr><td>{t.name} ({float(t.rate)*100:.1f}%)</td><td style="text-align: right">${t.amount/100:.2f}</td></tr>' for t in invoice.taxes)}
        <tr class="total">
            <td>Total</td>
            <td style="text-align: right">${invoice.total/100:.2f}</td>
        </tr>
        <tr>
            <td>Amount Paid</td>
            <td style="text-align: right">${invoice.amount_paid/100:.2f}</td>
        </tr>
        <tr class="total">
            <td>Amount Due</td>
            <td style="text-align: right">${invoice.amount_due/100:.2f}</td>
        </tr>
    </table>
    
    {f'<div style="margin-top: 30px;"><strong>Notes:</strong><br>{invoice.notes}</div>' if invoice.notes else ''}
    
    <div class="footer">
        {template.footer_text}<br>
        {template.terms_and_conditions}
    </div>
</body>
</html>
        """
        
        return html.encode('utf-8')


# Invoice service
class InvoiceService:
    """Invoice service."""
    
    def __init__(
        self,
        store: Optional[InvoiceStore] = None,
        pdf_generator: Optional[PDFGenerator] = None,
        template: Optional[InvoiceTemplate] = None,
    ):
        self.store = store or InMemoryInvoiceStore()
        self.pdf_generator = pdf_generator or SimplePDFGenerator()
        self.template = template or InvoiceTemplate()
        self._stats = InvoiceStats()
    
    async def create(
        self,
        customer_id: str,
        items: Optional[List[InvoiceItem]] = None,
        customer: Optional[Customer] = None,
        payment_terms: PaymentTerms = PaymentTerms.NET_30,
        currency: str = "USD",
        notes: str = "",
        **kwargs,
    ) -> Invoice:
        """Create invoice."""
        number = await self.store.get_next_number()
        
        invoice = Invoice(
            number=number,
            customer_id=customer_id,
            customer=customer,
            items=items or [],
            payment_terms=payment_terms,
            currency=currency,
            notes=notes,
            **kwargs,
        )
        
        await self.store.save(invoice)
        
        self._stats.total_invoices += 1
        self._stats.total_amount += invoice.total
        
        logger.info(f"Invoice created: {invoice.number}")
        
        return invoice
    
    async def get(self, invoice_id: str) -> Optional[Invoice]:
        """Get invoice."""
        return await self.store.get(invoice_id)
    
    async def get_by_number(self, number: str) -> Optional[Invoice]:
        """Get by number."""
        return await self.store.get_by_number(number)
    
    async def update(self, invoice: Invoice) -> Invoice:
        """Update invoice."""
        await self.store.save(invoice)
        return invoice
    
    async def delete(self, invoice_id: str) -> bool:
        """Delete invoice."""
        return await self.store.delete(invoice_id)
    
    async def list(
        self,
        customer_id: Optional[str] = None,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
    ) -> List[Invoice]:
        """List invoices."""
        return await self.store.list(
            customer_id=customer_id,
            status=status,
            limit=limit,
        )
    
    async def add_item(
        self,
        invoice_id: str,
        description: str,
        quantity: int = 1,
        unit_price: int = 0,
        **kwargs,
    ) -> Optional[InvoiceItem]:
        """Add item to invoice."""
        invoice = await self.get(invoice_id)
        if not invoice:
            return None
        
        item = InvoiceItem(
            description=description,
            quantity=Decimal(str(quantity)),
            unit_price=unit_price,
            **kwargs,
        )
        invoice.add_item(item)
        await self.store.save(invoice)
        
        return item
    
    async def record_payment(
        self,
        invoice_id: str,
        amount: int,
        method: str = "card",
        reference: str = "",
    ) -> Optional[Payment]:
        """Record payment."""
        invoice = await self.get(invoice_id)
        if not invoice:
            return None
        
        payment = invoice.add_payment(
            amount=amount,
            method=method,
            reference=reference,
        )
        await self.store.save(invoice)
        
        if invoice.is_paid:
            self._stats.paid_amount += invoice.total
        
        logger.info(
            f"Payment recorded: ${amount/100:.2f} for {invoice.number}"
        )
        
        return payment
    
    async def send(
        self,
        invoice_id: str,
        email: str,
        message: str = "",
    ) -> bool:
        """Send invoice (stub - integrate with email service)."""
        invoice = await self.get(invoice_id)
        if not invoice:
            return False
        
        if invoice.status == InvoiceStatus.DRAFT:
            invoice.status = InvoiceStatus.SENT
            await self.store.save(invoice)
        
        logger.info(f"Invoice {invoice.number} sent to {email}")
        return True
    
    async def cancel(self, invoice_id: str) -> Optional[Invoice]:
        """Cancel invoice."""
        invoice = await self.get(invoice_id)
        if not invoice:
            return None
        
        if invoice.status in [InvoiceStatus.PAID, InvoiceStatus.REFUNDED]:
            raise InvoiceError("Cannot cancel paid invoice")
        
        invoice.status = InvoiceStatus.CANCELED
        await self.store.save(invoice)
        
        return invoice
    
    async def generate_pdf(
        self,
        invoice_id: str,
        template: Optional[InvoiceTemplate] = None,
    ) -> bytes:
        """Generate PDF."""
        invoice = await self.get(invoice_id)
        if not invoice:
            raise InvoiceError(f"Invoice not found: {invoice_id}")
        
        return await self.pdf_generator.generate(
            invoice,
            template or self.template,
        )
    
    async def get_overdue(self) -> List[Invoice]:
        """Get overdue invoices."""
        all_invoices = await self.store.list(limit=1000)
        return [i for i in all_invoices if i.is_overdue]
    
    def get_stats(self) -> InvoiceStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_invoice_service(
    store: Optional[InvoiceStore] = None,
    template: Optional[InvoiceTemplate] = None,
) -> InvoiceService:
    """Create invoice service."""
    return InvoiceService(store=store, template=template)


def create_invoice_item(
    description: str,
    quantity: int = 1,
    unit_price: int = 0,
    **kwargs,
) -> InvoiceItem:
    """Create invoice item."""
    return InvoiceItem(
        description=description,
        quantity=Decimal(str(quantity)),
        unit_price=unit_price,
        **kwargs,
    )


def create_invoice_template(
    company_name: str,
    company_address: Optional[Address] = None,
    **kwargs,
) -> InvoiceTemplate:
    """Create invoice template."""
    return InvoiceTemplate(
        company_name=company_name,
        company_address=company_address or Address(),
        **kwargs,
    )


def create_customer(
    name: str,
    email: str = "",
    **kwargs,
) -> Customer:
    """Create customer."""
    return Customer(name=name, email=email, **kwargs)


__all__ = [
    # Exceptions
    "InvoiceError",
    # Enums
    "InvoiceStatus",
    "PaymentTerms",
    "DiscountType",
    # Data classes
    "Address",
    "Customer",
    "InvoiceItem",
    "Tax",
    "Discount",
    "Payment",
    "Invoice",
    "InvoiceTemplate",
    "InvoiceStats",
    # Store
    "InvoiceStore",
    "InMemoryInvoiceStore",
    # PDF Generator
    "PDFGenerator",
    "SimplePDFGenerator",
    # Service
    "InvoiceService",
    # Factory functions
    "create_invoice_service",
    "create_invoice_item",
    "create_invoice_template",
    "create_customer",
]
