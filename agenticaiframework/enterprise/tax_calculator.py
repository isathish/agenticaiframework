"""
Enterprise Tax Calculator Module.

Tax rates, jurisdiction handling, compliance rules,
and tax computation for various scenarios.

Example:
    # Create tax calculator
    tax = create_tax_calculator()
    
    # Add tax rates
    await tax.add_rate(
        jurisdiction="US-CA",
        type="sales",
        rate=0.0725,  # 7.25%
    )
    
    # Calculate tax
    result = await tax.calculate(
        amount=100.00,
        jurisdiction="US-CA",
        type="sales",
    )
    # result.tax = 7.25
    
    # Validate tax ID
    valid = await tax.validate_tax_id("US", "12-3456789")
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')

logger = logging.getLogger(__name__)


class TaxError(Exception):
    """Tax error."""
    pass


class InvalidJurisdictionError(TaxError):
    """Invalid jurisdiction."""
    pass


class TaxType(str, Enum):
    """Tax type."""
    SALES = "sales"
    VAT = "vat"
    GST = "gst"
    INCOME = "income"
    PROPERTY = "property"
    EXCISE = "excise"
    CUSTOMS = "customs"
    SERVICE = "service"


class TaxCategory(str, Enum):
    """Product/service tax category."""
    STANDARD = "standard"
    REDUCED = "reduced"
    ZERO = "zero"
    EXEMPT = "exempt"
    FOOD = "food"
    MEDICINE = "medicine"
    DIGITAL = "digital"
    LUXURY = "luxury"


@dataclass
class TaxRate:
    """Tax rate definition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    jurisdiction: str = ""  # Country-State or Country
    type: TaxType = TaxType.SALES
    category: TaxCategory = TaxCategory.STANDARD
    rate: float = 0.0
    name: str = ""
    description: str = ""
    min_amount: float = 0.0
    max_amount: Optional[float] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_compound: bool = False
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self, on_date: Optional[date] = None) -> bool:
        """Check if rate is active."""
        check_date = on_date or date.today()
        
        if self.effective_from and check_date < self.effective_from:
            return False
        if self.effective_to and check_date > self.effective_to:
            return False
        
        return True


@dataclass
class TaxComponent:
    """Tax component in calculation."""
    name: str = ""
    type: TaxType = TaxType.SALES
    rate: float = 0.0
    amount: float = 0.0
    jurisdiction: str = ""


@dataclass
class TaxResult:
    """Tax calculation result."""
    subtotal: float = 0.0
    tax: float = 0.0
    total: float = 0.0
    components: List[TaxComponent] = field(default_factory=list)
    effective_rate: float = 0.0
    jurisdiction: str = ""
    currency: str = "USD"


@dataclass
class TaxExemption:
    """Tax exemption."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    entity_id: str = ""  # customer_id, org_id
    entity_type: str = "customer"
    jurisdiction: str = ""
    type: TaxType = TaxType.SALES
    certificate_number: str = ""
    reason: str = ""
    valid_from: date = field(default_factory=date.today)
    valid_to: Optional[date] = None
    is_verified: bool = False


@dataclass
class TaxIdValidation:
    """Tax ID validation result."""
    valid: bool = False
    country: str = ""
    tax_id: str = ""
    entity_name: str = ""
    entity_address: str = ""
    format_valid: bool = False
    checksum_valid: bool = False
    message: str = ""


@dataclass
class Jurisdiction:
    """Tax jurisdiction."""
    code: str = ""
    name: str = ""
    country: str = ""
    state: str = ""
    city: str = ""
    type: str = ""  # country, state, city, district
    parent: Optional[str] = None
    tax_id_format: str = ""
    tax_id_pattern: str = ""


@dataclass
class TaxStats:
    """Tax statistics."""
    total_jurisdictions: int = 0
    total_rates: int = 0
    total_exemptions: int = 0
    tax_collected: float = 0.0


# Tax rate store
class TaxRateStore(ABC):
    """Tax rate storage."""
    
    @abstractmethod
    async def save(self, rate: TaxRate) -> None:
        pass
    
    @abstractmethod
    async def get(self, rate_id: str) -> Optional[TaxRate]:
        pass
    
    @abstractmethod
    async def find(
        self,
        jurisdiction: str,
        type: Optional[TaxType] = None,
        category: Optional[TaxCategory] = None,
    ) -> List[TaxRate]:
        pass


class InMemoryTaxRateStore(TaxRateStore):
    """In-memory tax rate store."""
    
    def __init__(self):
        self._rates: Dict[str, TaxRate] = {}
        self._init_default_rates()
    
    def _init_default_rates(self) -> None:
        """Initialize default tax rates."""
        defaults = [
            # US Sales Tax
            TaxRate(jurisdiction="US-CA", type=TaxType.SALES, rate=0.0725, name="California Sales Tax"),
            TaxRate(jurisdiction="US-NY", type=TaxType.SALES, rate=0.08, name="New York Sales Tax"),
            TaxRate(jurisdiction="US-TX", type=TaxType.SALES, rate=0.0625, name="Texas Sales Tax"),
            TaxRate(jurisdiction="US-FL", type=TaxType.SALES, rate=0.06, name="Florida Sales Tax"),
            TaxRate(jurisdiction="US-WA", type=TaxType.SALES, rate=0.065, name="Washington Sales Tax"),
            # VAT
            TaxRate(jurisdiction="GB", type=TaxType.VAT, rate=0.20, name="UK VAT"),
            TaxRate(jurisdiction="DE", type=TaxType.VAT, rate=0.19, name="German VAT"),
            TaxRate(jurisdiction="FR", type=TaxType.VAT, rate=0.20, name="French VAT"),
            TaxRate(jurisdiction="IT", type=TaxType.VAT, rate=0.22, name="Italian VAT"),
            TaxRate(jurisdiction="ES", type=TaxType.VAT, rate=0.21, name="Spanish VAT"),
            # GST
            TaxRate(jurisdiction="AU", type=TaxType.GST, rate=0.10, name="Australia GST"),
            TaxRate(jurisdiction="CA", type=TaxType.GST, rate=0.05, name="Canada GST"),
            TaxRate(jurisdiction="IN", type=TaxType.GST, rate=0.18, name="India GST"),
            TaxRate(jurisdiction="SG", type=TaxType.GST, rate=0.08, name="Singapore GST"),
        ]
        
        for rate in defaults:
            self._rates[rate.id] = rate
    
    async def save(self, rate: TaxRate) -> None:
        self._rates[rate.id] = rate
    
    async def get(self, rate_id: str) -> Optional[TaxRate]:
        return self._rates.get(rate_id)
    
    async def find(
        self,
        jurisdiction: str,
        type: Optional[TaxType] = None,
        category: Optional[TaxCategory] = None,
    ) -> List[TaxRate]:
        results = []
        
        for rate in self._rates.values():
            # Match jurisdiction (exact or parent)
            if rate.jurisdiction != jurisdiction:
                # Check if jurisdiction is child
                if not jurisdiction.startswith(rate.jurisdiction + "-"):
                    continue
            
            if type and rate.type != type:
                continue
            if category and rate.category != category:
                continue
            
            if rate.is_active():
                results.append(rate)
        
        return sorted(results, key=lambda r: r.priority)


# Tax calculator
class TaxCalculator:
    """Tax calculator."""
    
    # Tax ID patterns by country
    TAX_ID_PATTERNS = {
        "US": r"^\d{2}-\d{7}$",  # EIN
        "GB": r"^GB\d{9}$|^GB\d{12}$|^GBGD\d{3}$|^GBHA\d{3}$",  # VAT
        "DE": r"^DE\d{9}$",  # VAT
        "FR": r"^FR[A-Z0-9]{2}\d{9}$",  # VAT
        "AU": r"^\d{11}$",  # ABN
        "CA": r"^\d{9}RT\d{4}$",  # GST/HST
        "IN": r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}$",  # GSTIN
    }
    
    def __init__(
        self,
        rate_store: Optional[TaxRateStore] = None,
        default_currency: str = "USD",
        rounding: int = 2,
    ):
        self._rates = rate_store or InMemoryTaxRateStore()
        self._exemptions: Dict[str, List[TaxExemption]] = {}
        self._jurisdictions: Dict[str, Jurisdiction] = {}
        self._default_currency = default_currency
        self._rounding = rounding
        self._stats = TaxStats()
    
    async def add_rate(
        self,
        jurisdiction: str,
        type: TaxType = TaxType.SALES,
        rate: float = 0.0,
        category: TaxCategory = TaxCategory.STANDARD,
        **kwargs,
    ) -> TaxRate:
        """Add tax rate."""
        tax_rate = TaxRate(
            jurisdiction=jurisdiction,
            type=type,
            rate=rate,
            category=category,
            **kwargs,
        )
        await self._rates.save(tax_rate)
        self._stats.total_rates += 1
        
        logger.info(f"Tax rate added: {jurisdiction} {type.value} {rate*100}%")
        
        return tax_rate
    
    async def get_rate(
        self,
        jurisdiction: str,
        type: TaxType = TaxType.SALES,
        category: TaxCategory = TaxCategory.STANDARD,
    ) -> Optional[TaxRate]:
        """Get tax rate."""
        rates = await self._rates.find(
            jurisdiction=jurisdiction,
            type=type,
            category=category,
        )
        return rates[0] if rates else None
    
    async def calculate(
        self,
        amount: float,
        jurisdiction: str,
        type: TaxType = TaxType.SALES,
        category: TaxCategory = TaxCategory.STANDARD,
        entity_id: Optional[str] = None,
        inclusive: bool = False,
        currency: Optional[str] = None,
    ) -> TaxResult:
        """Calculate tax."""
        # Check exemption
        if entity_id and await self._is_exempt(entity_id, jurisdiction, type):
            return TaxResult(
                subtotal=amount,
                tax=0.0,
                total=amount,
                components=[],
                effective_rate=0.0,
                jurisdiction=jurisdiction,
                currency=currency or self._default_currency,
            )
        
        # Get applicable rates
        rates = await self._rates.find(
            jurisdiction=jurisdiction,
            type=type,
            category=category,
        )
        
        if not rates:
            return TaxResult(
                subtotal=amount,
                tax=0.0,
                total=amount,
                components=[],
                effective_rate=0.0,
                jurisdiction=jurisdiction,
                currency=currency or self._default_currency,
            )
        
        # Calculate tax
        components: List[TaxComponent] = []
        total_tax = 0.0
        base_amount = amount
        
        for rate in rates:
            if inclusive:
                # Tax included in amount
                tax_amount = base_amount - (base_amount / (1 + rate.rate))
            else:
                tax_amount = base_amount * rate.rate
            
            tax_amount = self._round(tax_amount)
            
            components.append(TaxComponent(
                name=rate.name or f"{rate.type.value} Tax",
                type=rate.type,
                rate=rate.rate,
                amount=tax_amount,
                jurisdiction=rate.jurisdiction,
            ))
            
            total_tax += tax_amount
            
            # For compound taxes, base increases
            if rate.is_compound:
                base_amount += tax_amount
        
        total_tax = self._round(total_tax)
        
        if inclusive:
            subtotal = amount - total_tax
            total = amount
        else:
            subtotal = amount
            total = amount + total_tax
        
        effective_rate = total_tax / subtotal if subtotal > 0 else 0.0
        
        self._stats.tax_collected += total_tax
        
        return TaxResult(
            subtotal=self._round(subtotal),
            tax=total_tax,
            total=self._round(total),
            components=components,
            effective_rate=effective_rate,
            jurisdiction=jurisdiction,
            currency=currency or self._default_currency,
        )
    
    async def calculate_items(
        self,
        items: List[Dict[str, Any]],
        jurisdiction: str,
        type: TaxType = TaxType.SALES,
        entity_id: Optional[str] = None,
    ) -> TaxResult:
        """Calculate tax for multiple items."""
        total_subtotal = 0.0
        total_tax = 0.0
        all_components: List[TaxComponent] = []
        
        for item in items:
            amount = item.get("amount", 0.0)
            category = TaxCategory(item.get("category", "standard"))
            
            result = await self.calculate(
                amount=amount,
                jurisdiction=jurisdiction,
                type=type,
                category=category,
                entity_id=entity_id,
            )
            
            total_subtotal += result.subtotal
            total_tax += result.tax
            all_components.extend(result.components)
        
        return TaxResult(
            subtotal=self._round(total_subtotal),
            tax=self._round(total_tax),
            total=self._round(total_subtotal + total_tax),
            components=all_components,
            effective_rate=total_tax / total_subtotal if total_subtotal > 0 else 0.0,
            jurisdiction=jurisdiction,
            currency=self._default_currency,
        )
    
    async def add_exemption(
        self,
        entity_id: str,
        jurisdiction: str,
        type: TaxType = TaxType.SALES,
        certificate_number: str = "",
        reason: str = "",
        valid_to: Optional[date] = None,
    ) -> TaxExemption:
        """Add tax exemption."""
        exemption = TaxExemption(
            entity_id=entity_id,
            jurisdiction=jurisdiction,
            type=type,
            certificate_number=certificate_number,
            reason=reason,
            valid_to=valid_to,
        )
        
        if entity_id not in self._exemptions:
            self._exemptions[entity_id] = []
        self._exemptions[entity_id].append(exemption)
        self._stats.total_exemptions += 1
        
        return exemption
    
    async def _is_exempt(
        self,
        entity_id: str,
        jurisdiction: str,
        type: TaxType,
    ) -> bool:
        """Check if entity is exempt."""
        exemptions = self._exemptions.get(entity_id, [])
        today = date.today()
        
        for exemption in exemptions:
            if exemption.jurisdiction != jurisdiction:
                continue
            if exemption.type != type:
                continue
            if exemption.valid_to and exemption.valid_to < today:
                continue
            return True
        
        return False
    
    async def validate_tax_id(
        self,
        country: str,
        tax_id: str,
    ) -> TaxIdValidation:
        """Validate tax ID format."""
        result = TaxIdValidation(
            country=country,
            tax_id=tax_id,
        )
        
        # Clean ID
        clean_id = tax_id.replace(" ", "").replace("-", "").upper()
        
        # Get pattern
        pattern = self.TAX_ID_PATTERNS.get(country)
        
        if not pattern:
            result.message = f"No validation pattern for country: {country}"
            return result
        
        # Validate format
        if re.match(pattern, tax_id) or re.match(pattern, clean_id):
            result.format_valid = True
            result.valid = True
            result.message = "Tax ID format is valid"
        else:
            result.message = f"Invalid tax ID format for {country}"
        
        return result
    
    async def add_jurisdiction(
        self,
        code: str,
        name: str,
        country: str,
        **kwargs,
    ) -> Jurisdiction:
        """Add jurisdiction."""
        jurisdiction = Jurisdiction(
            code=code,
            name=name,
            country=country,
            **kwargs,
        )
        self._jurisdictions[code] = jurisdiction
        self._stats.total_jurisdictions += 1
        
        return jurisdiction
    
    async def get_jurisdiction(self, code: str) -> Optional[Jurisdiction]:
        """Get jurisdiction."""
        return self._jurisdictions.get(code)
    
    def _round(self, amount: float) -> float:
        """Round amount."""
        d = Decimal(str(amount))
        return float(d.quantize(
            Decimal(10) ** -self._rounding,
            rounding=ROUND_HALF_UP,
        ))
    
    def get_stats(self) -> TaxStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_tax_calculator(
    default_currency: str = "USD",
) -> TaxCalculator:
    """Create tax calculator."""
    return TaxCalculator(default_currency=default_currency)


def create_tax_rate(
    jurisdiction: str,
    rate: float,
    type: TaxType = TaxType.SALES,
    **kwargs,
) -> TaxRate:
    """Create tax rate."""
    return TaxRate(
        jurisdiction=jurisdiction,
        rate=rate,
        type=type,
        **kwargs,
    )


def create_exemption(
    entity_id: str,
    jurisdiction: str,
    **kwargs,
) -> TaxExemption:
    """Create exemption."""
    return TaxExemption(
        entity_id=entity_id,
        jurisdiction=jurisdiction,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "TaxError",
    "InvalidJurisdictionError",
    # Enums
    "TaxType",
    "TaxCategory",
    # Data classes
    "TaxRate",
    "TaxComponent",
    "TaxResult",
    "TaxExemption",
    "TaxIdValidation",
    "Jurisdiction",
    "TaxStats",
    # Stores
    "TaxRateStore",
    "InMemoryTaxRateStore",
    # Calculator
    "TaxCalculator",
    # Factory functions
    "create_tax_calculator",
    "create_tax_rate",
    "create_exemption",
]
