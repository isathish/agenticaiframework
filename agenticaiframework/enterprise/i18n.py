"""
Enterprise I18n Module.

Provides internationalization and localization support,
including message translation, pluralization, and formatting.

Example:
    # Create translator
    i18n = create_i18n(default_locale="en")
    
    # Load translations
    i18n.load_translations("en", {
        "greeting": "Hello, {name}!",
        "items": {
            "one": "{count} item",
            "other": "{count} items"
        }
    })
    
    i18n.load_translations("es", {
        "greeting": "¡Hola, {name}!",
        "items": {
            "one": "{count} artículo",
            "other": "{count} artículos"
        }
    })
    
    # Use translations
    print(i18n.t("greeting", name="World"))  # Hello, World!
    print(i18n.t("items", count=5))          # 5 items
    
    # With locale decorator
    @with_locale("es")
    def spanish_greeting():
        return i18n.t("greeting", name="Mundo")
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class I18nError(Exception):
    """I18n error."""
    pass


class TranslationNotFoundError(I18nError):
    """Translation not found."""
    pass


class LocaleNotFoundError(I18nError):
    """Locale not found."""
    pass


class PluralCategory(str, Enum):
    """CLDR plural categories."""
    ZERO = "zero"
    ONE = "one"
    TWO = "two"
    FEW = "few"
    MANY = "many"
    OTHER = "other"


@dataclass
class LocaleInfo:
    """Locale information."""
    code: str  # e.g., "en-US"
    language: str  # e.g., "en"
    region: Optional[str] = None  # e.g., "US"
    name: str = ""
    native_name: str = ""
    direction: str = "ltr"  # "ltr" or "rtl"
    
    @classmethod
    def parse(cls, code: str) -> 'LocaleInfo':
        """Parse locale code."""
        parts = code.replace("_", "-").split("-")
        language = parts[0].lower()
        region = parts[1].upper() if len(parts) > 1 else None
        
        return cls(
            code=code,
            language=language,
            region=region,
        )


@dataclass
class NumberFormat:
    """Number format specification."""
    decimal_separator: str = "."
    thousands_separator: str = ","
    currency_symbol: str = "$"
    currency_position: str = "before"  # "before" or "after"
    percent_symbol: str = "%"


@dataclass
class DateFormat:
    """Date format specification."""
    short_date: str = "%m/%d/%Y"
    long_date: str = "%B %d, %Y"
    short_time: str = "%I:%M %p"
    long_time: str = "%I:%M:%S %p"
    datetime: str = "%m/%d/%Y %I:%M %p"


# Context variable for current locale
_current_locale: ContextVar[str] = ContextVar('current_locale', default='en')


class PluralRules:
    """
    Plural rules for different languages.
    Based on CLDR plural rules.
    """
    
    # Common plural rules
    _rules: Dict[str, Callable[[int], PluralCategory]] = {}
    
    @classmethod
    def register(
        cls,
        language: str,
        rule: Callable[[int], PluralCategory],
    ) -> None:
        """Register plural rule for a language."""
        cls._rules[language] = rule
    
    @classmethod
    def get_category(cls, language: str, count: int) -> PluralCategory:
        """Get plural category for a count."""
        rule = cls._rules.get(language, cls._english_rule)
        return rule(count)
    
    @staticmethod
    def _english_rule(count: int) -> PluralCategory:
        """English plural rule."""
        if count == 1:
            return PluralCategory.ONE
        return PluralCategory.OTHER
    
    @staticmethod
    def _russian_rule(count: int) -> PluralCategory:
        """Russian plural rule."""
        n = abs(count)
        mod10 = n % 10
        mod100 = n % 100
        
        if mod10 == 1 and mod100 != 11:
            return PluralCategory.ONE
        if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
            return PluralCategory.FEW
        return PluralCategory.MANY
    
    @staticmethod
    def _arabic_rule(count: int) -> PluralCategory:
        """Arabic plural rule."""
        n = abs(count)
        
        if n == 0:
            return PluralCategory.ZERO
        if n == 1:
            return PluralCategory.ONE
        if n == 2:
            return PluralCategory.TWO
        if 3 <= n % 100 <= 10:
            return PluralCategory.FEW
        if 11 <= n % 100 <= 99:
            return PluralCategory.MANY
        return PluralCategory.OTHER


# Register common plural rules
PluralRules.register("en", PluralRules._english_rule)
PluralRules.register("ru", PluralRules._russian_rule)
PluralRules.register("ar", PluralRules._arabic_rule)


class TranslationLoader(ABC):
    """Abstract translation loader."""
    
    @abstractmethod
    def load(self, locale: str) -> Dict[str, Any]:
        """Load translations for a locale."""
        pass


class JsonTranslationLoader(TranslationLoader):
    """Load translations from JSON files."""
    
    def __init__(self, directory: Union[str, Path]):
        self._directory = Path(directory)
    
    def load(self, locale: str) -> Dict[str, Any]:
        """Load translations from JSON file."""
        file_path = self._directory / f"{locale}.json"
        
        if not file_path.exists():
            raise LocaleNotFoundError(f"Translation file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)


class DictTranslationLoader(TranslationLoader):
    """Load translations from dictionaries."""
    
    def __init__(self, translations: Dict[str, Dict[str, Any]]):
        self._translations = translations
    
    def load(self, locale: str) -> Dict[str, Any]:
        """Get translations for locale."""
        if locale not in self._translations:
            raise LocaleNotFoundError(f"Locale not found: {locale}")
        
        return self._translations[locale]


class Translator:
    """
    Main translator class for internationalization.
    """
    
    def __init__(
        self,
        default_locale: str = "en",
        fallback_locale: Optional[str] = None,
    ):
        self._default_locale = default_locale
        self._fallback_locale = fallback_locale or default_locale
        self._translations: Dict[str, Dict[str, Any]] = {}
        self._loaders: List[TranslationLoader] = []
        self._formatters: Dict[str, Callable] = {}
        self._number_formats: Dict[str, NumberFormat] = {}
        self._date_formats: Dict[str, DateFormat] = {}
        
        # Set default locale
        _current_locale.set(default_locale)
    
    @property
    def locale(self) -> str:
        """Get current locale."""
        return _current_locale.get()
    
    @locale.setter
    def locale(self, value: str) -> None:
        """Set current locale."""
        _current_locale.set(value)
    
    def add_loader(self, loader: TranslationLoader) -> None:
        """Add a translation loader."""
        self._loaders.append(loader)
    
    def load_translations(
        self,
        locale: str,
        translations: Dict[str, Any],
    ) -> None:
        """Load translations for a locale."""
        if locale not in self._translations:
            self._translations[locale] = {}
        
        self._merge_translations(self._translations[locale], translations)
    
    def _merge_translations(
        self,
        target: Dict[str, Any],
        source: Dict[str, Any],
    ) -> None:
        """Merge translations deeply."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_translations(target[key], value)
            else:
                target[key] = value
    
    def load_locale(self, locale: str) -> bool:
        """Load all translations for a locale."""
        if locale in self._translations:
            return True
        
        for loader in self._loaders:
            try:
                translations = loader.load(locale)
                self.load_translations(locale, translations)
                return True
            except LocaleNotFoundError:
                continue
        
        return False
    
    def t(
        self,
        key: str,
        locale: Optional[str] = None,
        default: Optional[str] = None,
        **params: Any,
    ) -> str:
        """
        Translate a key.
        
        Args:
            key: Translation key (dot-separated for nested)
            locale: Optional locale override
            default: Default value if not found
            **params: Parameters for interpolation
        """
        locale = locale or self.locale
        
        # Try to find translation
        translation = self._get_translation(key, locale)
        
        if translation is None and locale != self._fallback_locale:
            translation = self._get_translation(key, self._fallback_locale)
        
        if translation is None:
            if default is not None:
                return default
            logger.warning(f"Translation not found: {key} for locale {locale}")
            return key
        
        # Handle plural forms
        if isinstance(translation, dict) and 'count' in params:
            translation = self._pluralize(translation, params['count'], locale)
        
        # Interpolate parameters
        return self._interpolate(translation, params)
    
    def _get_translation(
        self,
        key: str,
        locale: str,
    ) -> Optional[Union[str, Dict[str, Any]]]:
        """Get translation for a key."""
        # Ensure locale is loaded
        if locale not in self._translations:
            self.load_locale(locale)
        
        if locale not in self._translations:
            return None
        
        # Navigate nested keys
        parts = key.split(".")
        current = self._translations[locale]
        
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        
        return current
    
    def _pluralize(
        self,
        translations: Dict[str, Any],
        count: int,
        locale: str,
    ) -> str:
        """Get plural form."""
        language = locale.split("-")[0].split("_")[0]
        category = PluralRules.get_category(language, count)
        
        # Try exact category
        if category.value in translations:
            return translations[category.value]
        
        # Fall back to "other"
        if "other" in translations:
            return translations["other"]
        
        # Return first available
        if translations:
            return next(iter(translations.values()))
        
        return ""
    
    def _interpolate(self, text: str, params: Dict[str, Any]) -> str:
        """Interpolate parameters into text."""
        if not params:
            return text
        
        # Support {name} and {name:format} syntax
        pattern = r'\{(\w+)(?::(\w+))?\}'
        
        def replace(match):
            name = match.group(1)
            format_name = match.group(2)
            
            if name not in params:
                return match.group(0)
            
            value = params[name]
            
            if format_name and format_name in self._formatters:
                return self._formatters[format_name](value)
            
            return str(value)
        
        return re.sub(pattern, replace, text)
    
    def register_formatter(
        self,
        name: str,
        formatter: Callable[[Any], str],
    ) -> None:
        """Register a custom formatter."""
        self._formatters[name] = formatter
    
    def set_number_format(
        self,
        locale: str,
        format_spec: NumberFormat,
    ) -> None:
        """Set number format for locale."""
        self._number_formats[locale] = format_spec
    
    def set_date_format(
        self,
        locale: str,
        format_spec: DateFormat,
    ) -> None:
        """Set date format for locale."""
        self._date_formats[locale] = format_spec
    
    def format_number(
        self,
        value: Union[int, float, Decimal],
        locale: Optional[str] = None,
        decimals: int = 2,
    ) -> str:
        """Format a number according to locale."""
        locale = locale or self.locale
        fmt = self._number_formats.get(locale, NumberFormat())
        
        if isinstance(value, float) or isinstance(value, Decimal):
            formatted = f"{value:,.{decimals}f}"
        else:
            formatted = f"{value:,}"
        
        # Replace separators
        formatted = formatted.replace(",", "__TEMP__")
        formatted = formatted.replace(".", fmt.decimal_separator)
        formatted = formatted.replace("__TEMP__", fmt.thousands_separator)
        
        return formatted
    
    def format_currency(
        self,
        value: Union[int, float, Decimal],
        currency: Optional[str] = None,
        locale: Optional[str] = None,
    ) -> str:
        """Format currency according to locale."""
        locale = locale or self.locale
        fmt = self._number_formats.get(locale, NumberFormat())
        symbol = currency or fmt.currency_symbol
        
        formatted = self.format_number(value, locale, decimals=2)
        
        if fmt.currency_position == "before":
            return f"{symbol}{formatted}"
        else:
            return f"{formatted}{symbol}"
    
    def format_date(
        self,
        value: Union[datetime, date],
        format_type: str = "short",
        locale: Optional[str] = None,
    ) -> str:
        """Format date according to locale."""
        locale = locale or self.locale
        fmt = self._date_formats.get(locale, DateFormat())
        
        format_map = {
            "short": fmt.short_date,
            "long": fmt.long_date,
            "time": fmt.short_time,
            "datetime": fmt.datetime,
        }
        
        format_str = format_map.get(format_type, fmt.short_date)
        return value.strftime(format_str)
    
    def format_relative_time(
        self,
        value: datetime,
        locale: Optional[str] = None,
    ) -> str:
        """Format relative time (e.g., '2 hours ago')."""
        locale = locale or self.locale
        now = datetime.now()
        diff = now - value
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return self.t("time.just_now", locale=locale, default="just now")
        
        if seconds < 3600:
            minutes = int(seconds / 60)
            return self.t("time.minutes_ago", locale=locale, count=minutes, default=f"{minutes} minutes ago")
        
        if seconds < 86400:
            hours = int(seconds / 3600)
            return self.t("time.hours_ago", locale=locale, count=hours, default=f"{hours} hours ago")
        
        if seconds < 604800:
            days = int(seconds / 86400)
            return self.t("time.days_ago", locale=locale, count=days, default=f"{days} days ago")
        
        return self.format_date(value, "short", locale)
    
    @contextmanager
    def use_locale(self, locale: str):
        """Context manager to temporarily use a different locale."""
        old_locale = self.locale
        try:
            self.locale = locale
            yield
        finally:
            self.locale = old_locale
    
    def get_available_locales(self) -> List[str]:
        """Get list of available locales."""
        return list(self._translations.keys())


# Global translator instance
_translator: Optional[Translator] = None


def get_translator() -> Translator:
    """Get the global translator."""
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


# Decorators
def with_locale(locale: str) -> Callable:
    """
    Decorator to run function with specific locale.
    
    Example:
        @with_locale("es")
        def spanish_greeting():
            return t("greeting")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            translator = get_translator()
            with translator.use_locale(locale):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def translatable(
    key: str,
    **default_params: Any,
) -> Callable:
    """
    Decorator to make a function return translated text.
    
    Example:
        @translatable("greeting.message")
        def get_greeting(name: str):
            return {"name": name}
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> str:
            params = func(*args, **kwargs) or {}
            params = {**default_params, **params}
            return t(key, **params)
        return wrapper
    return decorator


# Convenience functions
def t(
    key: str,
    locale: Optional[str] = None,
    **params: Any,
) -> str:
    """Translate a key using the global translator."""
    return get_translator().t(key, locale, **params)


def set_locale(locale: str) -> None:
    """Set the current locale."""
    get_translator().locale = locale


def get_locale() -> str:
    """Get the current locale."""
    return get_translator().locale


def load_translations(locale: str, translations: Dict[str, Any]) -> None:
    """Load translations for a locale."""
    get_translator().load_translations(locale, translations)


# Factory functions
def create_i18n(
    default_locale: str = "en",
    fallback_locale: Optional[str] = None,
) -> Translator:
    """Create a translator instance."""
    global _translator
    _translator = Translator(default_locale, fallback_locale)
    return _translator


def create_json_loader(directory: Union[str, Path]) -> JsonTranslationLoader:
    """Create a JSON translation loader."""
    return JsonTranslationLoader(directory)


def create_dict_loader(
    translations: Dict[str, Dict[str, Any]],
) -> DictTranslationLoader:
    """Create a dictionary translation loader."""
    return DictTranslationLoader(translations)


__all__ = [
    # Exceptions
    "I18nError",
    "TranslationNotFoundError",
    "LocaleNotFoundError",
    # Enums
    "PluralCategory",
    # Data classes
    "LocaleInfo",
    "NumberFormat",
    "DateFormat",
    # Core classes
    "PluralRules",
    "TranslationLoader",
    "JsonTranslationLoader",
    "DictTranslationLoader",
    "Translator",
    # Decorators
    "with_locale",
    "translatable",
    # Convenience functions
    "t",
    "set_locale",
    "get_locale",
    "load_translations",
    "get_translator",
    # Factory
    "create_i18n",
    "create_json_loader",
    "create_dict_loader",
]
