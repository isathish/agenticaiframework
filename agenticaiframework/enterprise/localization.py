"""
Enterprise Localization Service Module.

Internationalization and localization with pluralization,
date/number formatting, and language detection.

Example:
    # Create localization service
    l10n = create_localization_service()
    
    # Add translations
    await l10n.add_translations("en", {
        "greeting": "Hello, {name}!",
        "items": "{count} item|{count} items",
    })
    
    # Translate
    text = await l10n.t("greeting", name="World", locale="en")
    
    # Pluralization
    text = await l10n.t("items", count=5, locale="en")
    
    # Format date
    formatted = await l10n.format_date(date, locale="fr")
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)

T = TypeVar('T')
F = TypeVar('F', bound=Callable)


logger = logging.getLogger(__name__)


class LocalizationError(Exception):
    """Localization error."""
    pass


class TranslationNotFoundError(LocalizationError):
    """Translation not found."""
    pass


class LocaleNotFoundError(LocalizationError):
    """Locale not found."""
    pass


class PluralCategory(str, Enum):
    """Plural categories (CLDR)."""
    ZERO = "zero"
    ONE = "one"
    TWO = "two"
    FEW = "few"
    MANY = "many"
    OTHER = "other"


class DateStyle(str, Enum):
    """Date formatting styles."""
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    FULL = "full"


class NumberStyle(str, Enum):
    """Number formatting styles."""
    DECIMAL = "decimal"
    CURRENCY = "currency"
    PERCENT = "percent"
    SCIENTIFIC = "scientific"


@dataclass
class LocaleConfig:
    """Locale configuration."""
    code: str  # e.g., "en-US"
    name: str = ""
    language: str = ""  # e.g., "en"
    region: str = ""  # e.g., "US"
    date_format: str = "%Y-%m-%d"
    time_format: str = "%H:%M:%S"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"
    decimal_separator: str = "."
    thousands_separator: str = ","
    currency_symbol: str = "$"
    currency_code: str = "USD"
    first_day_of_week: int = 0  # 0=Sunday
    rtl: bool = False


@dataclass
class TranslationEntry:
    """Translation entry."""
    key: str
    value: str
    plural_forms: Dict[PluralCategory, str] = field(default_factory=dict)
    context: str = ""
    description: str = ""


@dataclass
class TranslationBundle:
    """Translation bundle."""
    locale: str
    entries: Dict[str, TranslationEntry] = field(default_factory=dict)
    fallback: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)


# Locale data
LOCALE_CONFIGS: Dict[str, LocaleConfig] = {
    "en": LocaleConfig(
        code="en",
        name="English",
        language="en",
        date_format="%m/%d/%Y",
        currency_symbol="$",
        currency_code="USD",
    ),
    "en-US": LocaleConfig(
        code="en-US",
        name="English (US)",
        language="en",
        region="US",
        date_format="%m/%d/%Y",
        currency_symbol="$",
        currency_code="USD",
    ),
    "en-GB": LocaleConfig(
        code="en-GB",
        name="English (UK)",
        language="en",
        region="GB",
        date_format="%d/%m/%Y",
        currency_symbol="£",
        currency_code="GBP",
        first_day_of_week=1,
    ),
    "fr": LocaleConfig(
        code="fr",
        name="Français",
        language="fr",
        date_format="%d/%m/%Y",
        decimal_separator=",",
        thousands_separator=" ",
        currency_symbol="€",
        currency_code="EUR",
        first_day_of_week=1,
    ),
    "de": LocaleConfig(
        code="de",
        name="Deutsch",
        language="de",
        date_format="%d.%m.%Y",
        decimal_separator=",",
        thousands_separator=".",
        currency_symbol="€",
        currency_code="EUR",
        first_day_of_week=1,
    ),
    "es": LocaleConfig(
        code="es",
        name="Español",
        language="es",
        date_format="%d/%m/%Y",
        decimal_separator=",",
        thousands_separator=".",
        currency_symbol="€",
        currency_code="EUR",
        first_day_of_week=1,
    ),
    "ja": LocaleConfig(
        code="ja",
        name="日本語",
        language="ja",
        date_format="%Y/%m/%d",
        currency_symbol="¥",
        currency_code="JPY",
    ),
    "zh": LocaleConfig(
        code="zh",
        name="中文",
        language="zh",
        date_format="%Y/%m/%d",
        currency_symbol="¥",
        currency_code="CNY",
    ),
    "ar": LocaleConfig(
        code="ar",
        name="العربية",
        language="ar",
        date_format="%d/%m/%Y",
        decimal_separator="٫",
        thousands_separator="٬",
        rtl=True,
    ),
}


# Pluralization rules
class PluralRules:
    """Plural rules engine."""
    
    @staticmethod
    def get_category(count: int, locale: str) -> PluralCategory:
        """Get plural category for count and locale."""
        language = locale.split("-")[0].lower()
        
        # English-like languages (one/other)
        if language in ("en", "de", "es", "it", "nl", "pt"):
            if count == 1:
                return PluralCategory.ONE
            return PluralCategory.OTHER
        
        # French (0-1 one, 2+ other)
        if language == "fr":
            if count in (0, 1):
                return PluralCategory.ONE
            return PluralCategory.OTHER
        
        # Russian/Ukrainian (complex)
        if language in ("ru", "uk"):
            if count % 10 == 1 and count % 100 != 11:
                return PluralCategory.ONE
            if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
                return PluralCategory.FEW
            return PluralCategory.MANY
        
        # Arabic
        if language == "ar":
            if count == 0:
                return PluralCategory.ZERO
            if count == 1:
                return PluralCategory.ONE
            if count == 2:
                return PluralCategory.TWO
            if count % 100 >= 3 and count % 100 <= 10:
                return PluralCategory.FEW
            if count % 100 >= 11:
                return PluralCategory.MANY
            return PluralCategory.OTHER
        
        # Japanese/Chinese (no plural)
        if language in ("ja", "zh", "ko"):
            return PluralCategory.OTHER
        
        # Default
        return PluralCategory.OTHER if count != 1 else PluralCategory.ONE


# Translation store
class TranslationStore(ABC):
    """Abstract translation store."""
    
    @abstractmethod
    async def get_bundle(self, locale: str) -> Optional[TranslationBundle]:
        pass
    
    @abstractmethod
    async def save_bundle(self, bundle: TranslationBundle) -> None:
        pass
    
    @abstractmethod
    async def get_entry(
        self,
        locale: str,
        key: str,
    ) -> Optional[TranslationEntry]:
        pass


class InMemoryTranslationStore(TranslationStore):
    """In-memory translation store."""
    
    def __init__(self):
        self._bundles: Dict[str, TranslationBundle] = {}
    
    async def get_bundle(self, locale: str) -> Optional[TranslationBundle]:
        return self._bundles.get(locale)
    
    async def save_bundle(self, bundle: TranslationBundle) -> None:
        self._bundles[bundle.locale] = bundle
    
    async def get_entry(
        self,
        locale: str,
        key: str,
    ) -> Optional[TranslationEntry]:
        bundle = self._bundles.get(locale)
        if bundle:
            return bundle.entries.get(key)
        return None


class LocalizationService:
    """
    Localization service.
    """
    
    def __init__(
        self,
        default_locale: str = "en",
        store: Optional[TranslationStore] = None,
        fallback_locale: Optional[str] = None,
    ):
        self._default_locale = default_locale
        self._store = store or InMemoryTranslationStore()
        self._fallback_locale = fallback_locale or "en"
        self._locale_configs = LOCALE_CONFIGS.copy()
        self._missing_key_handler: Optional[Callable] = None
    
    def set_missing_key_handler(
        self,
        handler: Callable[[str, str], str],
    ) -> None:
        """Set handler for missing translation keys."""
        self._missing_key_handler = handler
    
    async def add_locale(self, config: LocaleConfig) -> None:
        """Add locale configuration."""
        self._locale_configs[config.code] = config
    
    def get_locale_config(self, locale: str) -> LocaleConfig:
        """Get locale configuration."""
        if locale in self._locale_configs:
            return self._locale_configs[locale]
        
        # Try base language
        language = locale.split("-")[0]
        if language in self._locale_configs:
            return self._locale_configs[language]
        
        return self._locale_configs.get("en", LocaleConfig(code="en"))
    
    async def add_translations(
        self,
        locale: str,
        translations: Dict[str, str],
        fallback: Optional[str] = None,
    ) -> None:
        """
        Add translations for locale.
        
        Args:
            locale: Locale code
            translations: Translation dictionary
            fallback: Fallback locale
        """
        bundle = await self._store.get_bundle(locale)
        if not bundle:
            bundle = TranslationBundle(locale=locale, fallback=fallback)
        
        for key, value in translations.items():
            # Check for plural forms (separated by |)
            if "|" in value:
                parts = value.split("|")
                plural_forms = {}
                
                if len(parts) == 2:
                    # one|other
                    plural_forms[PluralCategory.ONE] = parts[0]
                    plural_forms[PluralCategory.OTHER] = parts[1]
                elif len(parts) >= 3:
                    # zero|one|other or one|few|many|other
                    plural_forms[PluralCategory.ZERO] = parts[0]
                    plural_forms[PluralCategory.ONE] = parts[1]
                    plural_forms[PluralCategory.OTHER] = parts[-1]
                    if len(parts) >= 4:
                        plural_forms[PluralCategory.FEW] = parts[2]
                    if len(parts) >= 5:
                        plural_forms[PluralCategory.MANY] = parts[3]
                
                entry = TranslationEntry(
                    key=key,
                    value=parts[0],
                    plural_forms=plural_forms,
                )
            else:
                entry = TranslationEntry(key=key, value=value)
            
            bundle.entries[key] = entry
        
        await self._store.save_bundle(bundle)
    
    async def t(
        self,
        key: str,
        locale: Optional[str] = None,
        count: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        Translate key.
        
        Args:
            key: Translation key
            locale: Locale code
            count: Count for pluralization
            **kwargs: Interpolation values
            
        Returns:
            Translated string
        """
        locale = locale or self._default_locale
        
        # Get entry
        entry = await self._store.get_entry(locale, key)
        
        # Try fallback
        if not entry:
            bundle = await self._store.get_bundle(locale)
            if bundle and bundle.fallback:
                entry = await self._store.get_entry(bundle.fallback, key)
        
        if not entry:
            entry = await self._store.get_entry(self._fallback_locale, key)
        
        if not entry:
            if self._missing_key_handler:
                return self._missing_key_handler(key, locale)
            return key
        
        # Get value
        if count is not None and entry.plural_forms:
            category = PluralRules.get_category(count, locale)
            value = entry.plural_forms.get(category, entry.value)
        else:
            value = entry.value
        
        # Interpolate
        if kwargs:
            try:
                value = value.format(**kwargs, count=count)
            except KeyError:
                pass
        
        return value
    
    async def format_number(
        self,
        value: Union[int, float, Decimal],
        locale: Optional[str] = None,
        style: NumberStyle = NumberStyle.DECIMAL,
        min_decimals: int = 0,
        max_decimals: int = 2,
        currency: Optional[str] = None,
    ) -> str:
        """
        Format number.
        
        Args:
            value: Number to format
            locale: Locale code
            style: Number style
            min_decimals: Minimum decimal places
            max_decimals: Maximum decimal places
            currency: Currency code override
            
        Returns:
            Formatted number
        """
        locale = locale or self._default_locale
        config = self.get_locale_config(locale)
        
        # Format decimals
        if isinstance(value, int) and style == NumberStyle.DECIMAL:
            formatted = str(value)
        else:
            formatted = f"{value:.{max_decimals}f}"
            
            # Remove trailing zeros if min_decimals is lower
            if min_decimals < max_decimals:
                parts = formatted.split(".")
                if len(parts) == 2:
                    decimal_part = parts[1].rstrip("0")
                    if len(decimal_part) < min_decimals:
                        decimal_part = decimal_part.ljust(min_decimals, "0")
                    if decimal_part:
                        formatted = f"{parts[0]}.{decimal_part}"
                    else:
                        formatted = parts[0]
        
        # Add thousands separator
        parts = formatted.split(".")
        integer_part = parts[0]
        
        if len(integer_part) > 3:
            groups = []
            while integer_part:
                groups.append(integer_part[-3:])
                integer_part = integer_part[:-3]
            integer_part = config.thousands_separator.join(reversed(groups))
        
        if len(parts) > 1:
            formatted = f"{integer_part}{config.decimal_separator}{parts[1]}"
        else:
            formatted = integer_part
        
        # Apply style
        if style == NumberStyle.PERCENT:
            formatted = f"{formatted}%"
        elif style == NumberStyle.CURRENCY:
            symbol = currency or config.currency_symbol
            formatted = f"{symbol}{formatted}"
        elif style == NumberStyle.SCIENTIFIC:
            formatted = f"{value:.{max_decimals}e}"
        
        return formatted
    
    async def format_currency(
        self,
        value: Union[int, float, Decimal],
        locale: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> str:
        """Format currency."""
        return await self.format_number(
            value,
            locale=locale,
            style=NumberStyle.CURRENCY,
            min_decimals=2,
            max_decimals=2,
            currency=currency,
        )
    
    async def format_percent(
        self,
        value: Union[int, float, Decimal],
        locale: Optional[str] = None,
        decimals: int = 0,
    ) -> str:
        """Format percentage."""
        return await self.format_number(
            value * 100,
            locale=locale,
            style=NumberStyle.PERCENT,
            max_decimals=decimals,
        )
    
    async def format_date(
        self,
        value: Union[datetime, date],
        locale: Optional[str] = None,
        style: DateStyle = DateStyle.MEDIUM,
        custom_format: Optional[str] = None,
    ) -> str:
        """
        Format date.
        
        Args:
            value: Date to format
            locale: Locale code
            style: Date style
            custom_format: Custom format string
            
        Returns:
            Formatted date
        """
        locale = locale or self._default_locale
        config = self.get_locale_config(locale)
        
        if custom_format:
            return value.strftime(custom_format)
        
        if style == DateStyle.SHORT:
            return value.strftime(config.date_format)
        elif style == DateStyle.LONG:
            return value.strftime("%B %d, %Y")
        elif style == DateStyle.FULL:
            return value.strftime("%A, %B %d, %Y")
        else:  # MEDIUM
            return value.strftime(config.date_format)
    
    async def format_time(
        self,
        value: Union[datetime, time],
        locale: Optional[str] = None,
        include_seconds: bool = False,
    ) -> str:
        """Format time."""
        locale = locale or self._default_locale
        config = self.get_locale_config(locale)
        
        if include_seconds:
            return value.strftime(config.time_format)
        return value.strftime("%H:%M")
    
    async def format_datetime(
        self,
        value: datetime,
        locale: Optional[str] = None,
        date_style: DateStyle = DateStyle.MEDIUM,
        include_time: bool = True,
    ) -> str:
        """Format datetime."""
        date_str = await self.format_date(value, locale, date_style)
        
        if include_time:
            time_str = await self.format_time(value, locale)
            return f"{date_str} {time_str}"
        
        return date_str
    
    async def format_relative_time(
        self,
        value: datetime,
        locale: Optional[str] = None,
        reference: Optional[datetime] = None,
    ) -> str:
        """
        Format relative time (e.g., "2 hours ago").
        
        Args:
            value: Target datetime
            locale: Locale code
            reference: Reference datetime (default: now)
            
        Returns:
            Relative time string
        """
        locale = locale or self._default_locale
        reference = reference or datetime.utcnow()
        
        delta = reference - value
        seconds = delta.total_seconds()
        
        if seconds < 0:
            seconds = abs(seconds)
            future = True
        else:
            future = False
        
        # Determine unit
        if seconds < 60:
            count = int(seconds)
            unit = "second"
        elif seconds < 3600:
            count = int(seconds / 60)
            unit = "minute"
        elif seconds < 86400:
            count = int(seconds / 3600)
            unit = "hour"
        elif seconds < 604800:
            count = int(seconds / 86400)
            unit = "day"
        elif seconds < 2592000:
            count = int(seconds / 604800)
            unit = "week"
        elif seconds < 31536000:
            count = int(seconds / 2592000)
            unit = "month"
        else:
            count = int(seconds / 31536000)
            unit = "year"
        
        # Get translation
        if count == 1:
            unit_text = await self.t(f"relative.{unit}", locale=locale) or unit
        else:
            unit_text = await self.t(f"relative.{unit}s", locale=locale) or f"{unit}s"
        
        if future:
            template = await self.t("relative.in", locale=locale) or "in {count} {unit}"
        else:
            template = await self.t("relative.ago", locale=locale) or "{count} {unit} ago"
        
        return template.format(count=count, unit=unit_text)
    
    def detect_locale(
        self,
        accept_language: Optional[str] = None,
        cookie: Optional[str] = None,
        default: Optional[str] = None,
    ) -> str:
        """
        Detect locale from various sources.
        
        Args:
            accept_language: Accept-Language header
            cookie: Locale cookie value
            default: Default locale
            
        Returns:
            Detected locale
        """
        # Cookie takes precedence
        if cookie and cookie in self._locale_configs:
            return cookie
        
        # Parse Accept-Language
        if accept_language:
            for part in accept_language.split(","):
                locale = part.split(";")[0].strip()
                if locale in self._locale_configs:
                    return locale
                
                # Try base language
                language = locale.split("-")[0]
                if language in self._locale_configs:
                    return language
        
        return default or self._default_locale


# Decorator
def translated(
    key: str,
    locale_arg: str = "locale",
):
    """
    Decorator to translate function return value.
    
    Args:
        key: Translation key prefix
        locale_arg: Argument name for locale
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            # Implement translation logic here
            return result
        
        return wrapper  # type: ignore
    
    return decorator


# Factory functions
def create_localization_service(
    default_locale: str = "en",
    store: Optional[TranslationStore] = None,
    **kwargs,
) -> LocalizationService:
    """Create localization service."""
    return LocalizationService(
        default_locale=default_locale,
        store=store,
        **kwargs,
    )


def create_translation_store() -> TranslationStore:
    """Create in-memory translation store."""
    return InMemoryTranslationStore()


def create_locale_config(
    code: str,
    name: str = "",
    **kwargs,
) -> LocaleConfig:
    """Create locale configuration."""
    return LocaleConfig(code=code, name=name, **kwargs)


__all__ = [
    # Exceptions
    "LocalizationError",
    "TranslationNotFoundError",
    "LocaleNotFoundError",
    # Enums
    "PluralCategory",
    "DateStyle",
    "NumberStyle",
    # Data classes
    "LocaleConfig",
    "TranslationEntry",
    "TranslationBundle",
    # Rules
    "PluralRules",
    # Store
    "TranslationStore",
    "InMemoryTranslationStore",
    # Service
    "LocalizationService",
    # Constants
    "LOCALE_CONFIGS",
    # Decorator
    "translated",
    # Factory functions
    "create_localization_service",
    "create_translation_store",
    "create_locale_config",
]
