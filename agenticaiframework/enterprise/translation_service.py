"""
Enterprise Translation Service Module.

Internationalization (i18n), locale management,
pluralization, and translation management.

Example:
    # Create translation service
    i18n = create_translation_service()
    
    # Add translations
    await i18n.add_translations("en", {
        "greeting": "Hello, {name}!",
        "items": "{count} item|{count} items",
    })
    
    # Translate
    text = await i18n.translate("greeting", locale="en", name="John")
    # "Hello, John!"
    
    # Pluralization
    text = await i18n.translate("items", locale="en", count=5)
    # "5 items"
    
    # Change locale
    await i18n.set_locale("es")
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
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


class TranslationError(Exception):
    """Translation error."""
    pass


class LocaleNotFoundError(TranslationError):
    """Locale not found."""
    pass


class TranslationNotFoundError(TranslationError):
    """Translation not found."""
    pass


class PluralRule(str, Enum):
    """Plural rule."""
    ZERO = "zero"
    ONE = "one"
    TWO = "two"
    FEW = "few"
    MANY = "many"
    OTHER = "other"


@dataclass
class Locale:
    """Locale definition."""
    code: str = ""  # e.g., "en", "en-US"
    name: str = ""
    native_name: str = ""
    language: str = ""
    region: str = ""
    direction: str = "ltr"  # ltr or rtl
    date_format: str = "%Y-%m-%d"
    time_format: str = "%H:%M:%S"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"
    number_format: Dict[str, str] = field(default_factory=lambda: {
        "decimal": ".",
        "thousands": ",",
    })
    currency: str = "USD"
    currency_format: str = "${amount}"
    plural_rule: str = "n != 1"  # Expression for other form


@dataclass
class Translation:
    """Translation entry."""
    key: str = ""
    value: str = ""
    locale: str = ""
    context: str = ""
    plurals: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TranslationBundle:
    """Translation bundle."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    locale: str = ""
    namespace: str = "default"
    translations: Dict[str, Translation] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TranslationStats:
    """Translation statistics."""
    total_translations: int = 0
    total_locales: int = 0
    missing_translations: int = 0
    by_locale: Dict[str, int] = field(default_factory=dict)


# Translation store
class TranslationStore(ABC):
    """Translation storage."""
    
    @abstractmethod
    async def save_translation(
        self,
        locale: str,
        key: str,
        translation: Translation,
    ) -> None:
        """Save translation."""
        pass
    
    @abstractmethod
    async def get_translation(
        self,
        locale: str,
        key: str,
    ) -> Optional[Translation]:
        """Get translation."""
        pass
    
    @abstractmethod
    async def get_all(
        self,
        locale: str,
    ) -> Dict[str, Translation]:
        """Get all translations for locale."""
        pass
    
    @abstractmethod
    async def list_locales(self) -> List[str]:
        """List available locales."""
        pass


class InMemoryTranslationStore(TranslationStore):
    """In-memory translation store."""
    
    def __init__(self):
        self._translations: Dict[str, Dict[str, Translation]] = {}
    
    async def save_translation(
        self,
        locale: str,
        key: str,
        translation: Translation,
    ) -> None:
        if locale not in self._translations:
            self._translations[locale] = {}
        self._translations[locale][key] = translation
    
    async def get_translation(
        self,
        locale: str,
        key: str,
    ) -> Optional[Translation]:
        return self._translations.get(locale, {}).get(key)
    
    async def get_all(
        self,
        locale: str,
    ) -> Dict[str, Translation]:
        return self._translations.get(locale, {})
    
    async def list_locales(self) -> List[str]:
        return list(self._translations.keys())


# Locale store
class LocaleStore(ABC):
    """Locale storage."""
    
    @abstractmethod
    async def save(self, locale: Locale) -> None:
        """Save locale."""
        pass
    
    @abstractmethod
    async def get(self, code: str) -> Optional[Locale]:
        """Get locale."""
        pass
    
    @abstractmethod
    async def list(self) -> List[Locale]:
        """List locales."""
        pass


class InMemoryLocaleStore(LocaleStore):
    """In-memory locale store."""
    
    def __init__(self):
        self._locales: Dict[str, Locale] = {}
        self._init_defaults()
    
    def _init_defaults(self) -> None:
        """Initialize default locales."""
        defaults = [
            Locale(
                code="en",
                name="English",
                native_name="English",
                language="en",
                direction="ltr",
            ),
            Locale(
                code="es",
                name="Spanish",
                native_name="Español",
                language="es",
                direction="ltr",
            ),
            Locale(
                code="fr",
                name="French",
                native_name="Français",
                language="fr",
                direction="ltr",
            ),
            Locale(
                code="de",
                name="German",
                native_name="Deutsch",
                language="de",
                direction="ltr",
            ),
            Locale(
                code="zh",
                name="Chinese",
                native_name="中文",
                language="zh",
                direction="ltr",
            ),
            Locale(
                code="ja",
                name="Japanese",
                native_name="日本語",
                language="ja",
                direction="ltr",
            ),
            Locale(
                code="ar",
                name="Arabic",
                native_name="العربية",
                language="ar",
                direction="rtl",
            ),
        ]
        for locale in defaults:
            self._locales[locale.code] = locale
    
    async def save(self, locale: Locale) -> None:
        self._locales[locale.code] = locale
    
    async def get(self, code: str) -> Optional[Locale]:
        return self._locales.get(code)
    
    async def list(self) -> List[Locale]:
        return list(self._locales.values())


# Plural rules
class PluralRules:
    """Plural rules for different languages."""
    
    RULES = {
        "en": lambda n: "one" if n == 1 else "other",
        "es": lambda n: "one" if n == 1 else "other",
        "fr": lambda n: "one" if n in (0, 1) else "other",
        "de": lambda n: "one" if n == 1 else "other",
        "zh": lambda n: "other",  # No plural forms
        "ja": lambda n: "other",  # No plural forms
        "ar": lambda n: (
            "zero" if n == 0 else
            "one" if n == 1 else
            "two" if n == 2 else
            "few" if 3 <= n % 100 <= 10 else
            "many" if 11 <= n % 100 <= 99 else
            "other"
        ),
        "ru": lambda n: (
            "one" if n % 10 == 1 and n % 100 != 11 else
            "few" if 2 <= n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20) else
            "many"
        ),
    }
    
    @classmethod
    def get_plural_form(cls, locale: str, count: int) -> str:
        """Get plural form for count."""
        lang = locale.split("-")[0] if "-" in locale else locale
        rule = cls.RULES.get(lang, lambda n: "one" if n == 1 else "other")
        return rule(count)


# Translation service
class TranslationService:
    """Translation service."""
    
    def __init__(
        self,
        translation_store: Optional[TranslationStore] = None,
        locale_store: Optional[LocaleStore] = None,
        default_locale: str = "en",
        fallback_locale: str = "en",
    ):
        self._translations = translation_store or InMemoryTranslationStore()
        self._locales = locale_store or InMemoryLocaleStore()
        self._default_locale = default_locale
        self._fallback_locale = fallback_locale
        self._current_locale = default_locale
        self._stats = TranslationStats()
        self._cache: Dict[str, Dict[str, str]] = {}
    
    # Locale management
    @property
    def locale(self) -> str:
        """Get current locale."""
        return self._current_locale
    
    async def set_locale(self, locale: str) -> None:
        """Set current locale."""
        locale_obj = await self._locales.get(locale)
        if not locale_obj:
            # Try fallback to language code
            lang = locale.split("-")[0]
            locale_obj = await self._locales.get(lang)
        
        if locale_obj:
            self._current_locale = locale_obj.code
        else:
            logger.warning(f"Locale not found: {locale}")
            self._current_locale = self._fallback_locale
    
    async def get_locale(self, code: Optional[str] = None) -> Optional[Locale]:
        """Get locale."""
        return await self._locales.get(code or self._current_locale)
    
    async def list_locales(self) -> List[Locale]:
        """List available locales."""
        return await self._locales.list()
    
    async def add_locale(
        self,
        code: str,
        name: str,
        native_name: str = "",
        **kwargs,
    ) -> Locale:
        """Add locale."""
        locale = Locale(
            code=code,
            name=name,
            native_name=native_name or name,
            language=code.split("-")[0],
            **kwargs,
        )
        await self._locales.save(locale)
        self._stats.total_locales += 1
        return locale
    
    # Translation management
    async def add_translation(
        self,
        key: str,
        value: str,
        locale: Optional[str] = None,
        plurals: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> Translation:
        """Add translation."""
        loc = locale or self._current_locale
        
        translation = Translation(
            key=key,
            value=value,
            locale=loc,
            plurals=plurals or {},
            **kwargs,
        )
        
        await self._translations.save_translation(loc, key, translation)
        
        # Clear cache
        self._cache.pop(loc, None)
        
        self._stats.total_translations += 1
        self._stats.by_locale[loc] = self._stats.by_locale.get(loc, 0) + 1
        
        return translation
    
    async def add_translations(
        self,
        locale: str,
        translations: Dict[str, str],
    ) -> int:
        """Add multiple translations."""
        count = 0
        for key, value in translations.items():
            # Check for plural forms (pipe-separated)
            if "|" in value:
                parts = value.split("|")
                plurals = {}
                
                if len(parts) == 2:
                    plurals["one"] = parts[0]
                    plurals["other"] = parts[1]
                elif len(parts) >= 3:
                    plurals["zero"] = parts[0]
                    plurals["one"] = parts[1]
                    plurals["other"] = parts[2] if len(parts) > 2 else parts[1]
                
                await self.add_translation(
                    key=key,
                    value=parts[0],
                    locale=locale,
                    plurals=plurals,
                )
            else:
                await self.add_translation(
                    key=key,
                    value=value,
                    locale=locale,
                )
            count += 1
        
        return count
    
    async def get_translation(
        self,
        key: str,
        locale: Optional[str] = None,
    ) -> Optional[Translation]:
        """Get translation."""
        loc = locale or self._current_locale
        return await self._translations.get_translation(loc, key)
    
    async def get_all_translations(
        self,
        locale: Optional[str] = None,
    ) -> Dict[str, Translation]:
        """Get all translations for locale."""
        loc = locale or self._current_locale
        return await self._translations.get_all(loc)
    
    # Translation
    async def translate(
        self,
        key: str,
        locale: Optional[str] = None,
        count: Optional[int] = None,
        **kwargs,
    ) -> str:
        """Translate key."""
        loc = locale or self._current_locale
        
        # Get translation
        translation = await self._translations.get_translation(loc, key)
        
        # Fallback
        if not translation and loc != self._fallback_locale:
            translation = await self._translations.get_translation(
                self._fallback_locale, key
            )
        
        if not translation:
            self._stats.missing_translations += 1
            return key  # Return key if no translation found
        
        # Get appropriate form
        value = translation.value
        
        if count is not None and translation.plurals:
            plural_form = PluralRules.get_plural_form(loc, count)
            value = translation.plurals.get(plural_form, translation.value)
        
        # Interpolate
        value = self._interpolate(value, count=count, **kwargs)
        
        return value
    
    async def t(
        self,
        key: str,
        **kwargs,
    ) -> str:
        """Shorthand for translate."""
        return await self.translate(key, **kwargs)
    
    def _interpolate(self, text: str, **kwargs) -> str:
        """Interpolate variables."""
        for key, value in kwargs.items():
            if value is not None:
                text = text.replace(f"{{{key}}}", str(value))
        return text
    
    # Formatting
    async def format_number(
        self,
        number: float,
        locale: Optional[str] = None,
    ) -> str:
        """Format number."""
        loc = await self.get_locale(locale)
        if not loc:
            return str(number)
        
        fmt = loc.number_format
        decimal = fmt.get("decimal", ".")
        thousands = fmt.get("thousands", ",")
        
        # Split into parts
        if isinstance(number, float):
            int_part, dec_part = str(number).split(".")
        else:
            int_part = str(number)
            dec_part = None
        
        # Add thousands separator
        int_part = "{:,}".format(int(int_part)).replace(",", thousands)
        
        if dec_part:
            return f"{int_part}{decimal}{dec_part}"
        return int_part
    
    async def format_currency(
        self,
        amount: float,
        currency: Optional[str] = None,
        locale: Optional[str] = None,
    ) -> str:
        """Format currency."""
        loc = await self.get_locale(locale)
        if not loc:
            return f"${amount:.2f}"
        
        curr = currency or loc.currency
        formatted = await self.format_number(amount, locale)
        
        # Apply currency format
        result = loc.currency_format.replace("{amount}", formatted)
        result = result.replace("$", curr)
        
        return result
    
    async def format_date(
        self,
        date: datetime,
        format: Optional[str] = None,
        locale: Optional[str] = None,
    ) -> str:
        """Format date."""
        loc = await self.get_locale(locale)
        if not loc:
            return date.strftime("%Y-%m-%d")
        
        fmt = format or loc.date_format
        return date.strftime(fmt)
    
    async def format_time(
        self,
        time: datetime,
        format: Optional[str] = None,
        locale: Optional[str] = None,
    ) -> str:
        """Format time."""
        loc = await self.get_locale(locale)
        if not loc:
            return time.strftime("%H:%M:%S")
        
        fmt = format or loc.time_format
        return time.strftime(fmt)
    
    async def format_datetime(
        self,
        dt: datetime,
        format: Optional[str] = None,
        locale: Optional[str] = None,
    ) -> str:
        """Format datetime."""
        loc = await self.get_locale(locale)
        if not loc:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        
        fmt = format or loc.datetime_format
        return dt.strftime(fmt)
    
    # Import/export
    async def import_json(
        self,
        locale: str,
        data: Dict[str, str],
    ) -> int:
        """Import translations from JSON."""
        return await self.add_translations(locale, data)
    
    async def export_json(
        self,
        locale: Optional[str] = None,
    ) -> Dict[str, str]:
        """Export translations to JSON."""
        translations = await self.get_all_translations(locale)
        return {
            key: t.value
            for key, t in translations.items()
        }
    
    # Stats
    def get_stats(self) -> TranslationStats:
        """Get statistics."""
        return self._stats


# Factory functions
def create_translation_service(
    default_locale: str = "en",
    fallback_locale: str = "en",
) -> TranslationService:
    """Create translation service."""
    return TranslationService(
        default_locale=default_locale,
        fallback_locale=fallback_locale,
    )


def create_locale(
    code: str,
    name: str,
    native_name: str = "",
    **kwargs,
) -> Locale:
    """Create locale."""
    return Locale(
        code=code,
        name=name,
        native_name=native_name or name,
        language=code.split("-")[0],
        **kwargs,
    )


def create_translation(
    key: str,
    value: str,
    locale: str = "en",
    **kwargs,
) -> Translation:
    """Create translation."""
    return Translation(
        key=key,
        value=value,
        locale=locale,
        **kwargs,
    )


__all__ = [
    # Exceptions
    "TranslationError",
    "LocaleNotFoundError",
    "TranslationNotFoundError",
    # Enums
    "PluralRule",
    # Data classes
    "Locale",
    "Translation",
    "TranslationBundle",
    "TranslationStats",
    # Stores
    "TranslationStore",
    "InMemoryTranslationStore",
    "LocaleStore",
    "InMemoryLocaleStore",
    # Rules
    "PluralRules",
    # Service
    "TranslationService",
    # Factory functions
    "create_translation_service",
    "create_locale",
    "create_translation",
]
