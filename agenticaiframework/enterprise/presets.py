"""
Enterprise Presets - Pre-configured settings for common use cases.

Presets provide opinionated configurations for different environments
and use cases, enabling instant production-ready setups.

Usage:
    >>> from agenticaiframework.enterprise import load_preset
    >>> 
    >>> # Load enterprise preset
    >>> config = load_preset("enterprise")
    >>> 
    >>> # Apply to pipeline
    >>> pipeline = create_sdlc_pipeline("project", **config.to_dict())
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Preset Types
# =============================================================================

class PresetType(Enum):
    """Available preset types."""
    ENTERPRISE = "enterprise"
    STARTUP = "startup"
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"
    MINIMAL = "minimal"


@dataclass
class PresetConfig:
    """Configuration preset."""
    name: str
    description: str
    
    # LLM settings
    model: str = "gpt-4o"
    provider: str = "azure"
    temperature: float = 0.7
    max_tokens: int = 4096
    
    # Feature flags
    enable_tracing: bool = True
    enable_memory: bool = True
    enable_guardrails: bool = True
    enable_storage: bool = True
    enable_cache: bool = False
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Concurrency
    max_concurrency: int = 5
    parallel_execution: bool = False
    
    # Storage
    output_dir: str = "artifacts"
    log_level: str = "INFO"
    
    # Security
    enable_auth: bool = False
    enable_rate_limiting: bool = False
    
    # Additional settings
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for passing to constructors."""
        return {
            "model": self.model,
            "provider": self.provider,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "enable_tracing": self.enable_tracing,
            "enable_memory": self.enable_memory,
            "enable_guardrails": self.enable_guardrails,
            "enable_storage": self.enable_storage,
            "enable_cache": self.enable_cache,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "max_concurrency": self.max_concurrency,
            "parallel_execution": self.parallel_execution,
            "output_dir": self.output_dir,
            "log_level": self.log_level,
            **self.extra,
        }
    
    def merge(self, overrides: Dict[str, Any]) -> "PresetConfig":
        """Create new config with overrides applied."""
        config_dict = self.to_dict()
        config_dict.update(overrides)
        return PresetConfig(
            name=self.name,
            description=self.description,
            **{k: v for k, v in config_dict.items() if k not in ["extra"]},
        )


# =============================================================================
# Preset Definitions
# =============================================================================

class EnterprisePreset(PresetConfig):
    """
    Enterprise-grade preset for production deployments.
    
    Features:
    - Full tracing and monitoring
    - Comprehensive guardrails
    - High reliability with retries
    - Storage for audit trails
    - Rate limiting and auth ready
    """
    
    def __init__(self, **overrides):
        super().__init__(
            name="enterprise",
            description="Production-grade enterprise configuration",
            model="gpt-4o",
            provider="azure",
            temperature=0.5,
            max_tokens=8192,
            enable_tracing=True,
            enable_memory=True,
            enable_guardrails=True,
            enable_storage=True,
            enable_cache=True,
            max_retries=5,
            retry_delay=2.0,
            max_concurrency=10,
            parallel_execution=True,
            output_dir="enterprise_artifacts",
            log_level="INFO",
            enable_auth=True,
            enable_rate_limiting=True,
            extra=overrides,
        )


class StartupPreset(PresetConfig):
    """
    Startup preset for fast iteration.
    
    Features:
    - Faster models for quick feedback
    - Basic tracing
    - Minimal guardrails
    - Local storage
    """
    
    def __init__(self, **overrides):
        super().__init__(
            name="startup",
            description="Fast iteration for startups",
            model="gpt-4o-mini",
            provider="azure",
            temperature=0.7,
            max_tokens=4096,
            enable_tracing=True,
            enable_memory=True,
            enable_guardrails=False,
            enable_storage=True,
            enable_cache=False,
            max_retries=2,
            retry_delay=0.5,
            max_concurrency=5,
            parallel_execution=False,
            output_dir="startup_artifacts",
            log_level="INFO",
            enable_auth=False,
            enable_rate_limiting=False,
            extra=overrides,
        )


class DevelopmentPreset(PresetConfig):
    """
    Development preset for local testing.
    
    Features:
    - Detailed logging
    - No rate limiting
    - Local storage only
    - Quick iterations
    """
    
    def __init__(self, **overrides):
        super().__init__(
            name="development",
            description="Local development and testing",
            model="gpt-4o-mini",
            provider="azure",
            temperature=0.8,
            max_tokens=2048,
            enable_tracing=True,
            enable_memory=True,
            enable_guardrails=False,
            enable_storage=True,
            enable_cache=False,
            max_retries=1,
            retry_delay=0.1,
            max_concurrency=3,
            parallel_execution=False,
            output_dir="dev_artifacts",
            log_level="DEBUG",
            enable_auth=False,
            enable_rate_limiting=False,
            extra=overrides,
        )


class ProductionPreset(PresetConfig):
    """
    Production preset for live deployments.
    
    Features:
    - Reliable models
    - Full monitoring
    - Guardrails enabled
    - Cloud storage
    """
    
    def __init__(self, **overrides):
        super().__init__(
            name="production",
            description="Production deployment configuration",
            model="gpt-4o",
            provider="azure",
            temperature=0.5,
            max_tokens=8192,
            enable_tracing=True,
            enable_memory=True,
            enable_guardrails=True,
            enable_storage=True,
            enable_cache=True,
            max_retries=3,
            retry_delay=1.0,
            max_concurrency=8,
            parallel_execution=True,
            output_dir="production_artifacts",
            log_level="WARNING",
            enable_auth=True,
            enable_rate_limiting=True,
            extra=overrides,
        )


class TestingPreset(PresetConfig):
    """
    Testing preset for CI/CD pipelines.
    
    Features:
    - Predictable outputs (low temperature)
    - Minimal tokens
    - Fast execution
    - No external dependencies
    """
    
    def __init__(self, **overrides):
        super().__init__(
            name="testing",
            description="CI/CD and automated testing",
            model="gpt-4o-mini",
            provider="azure",
            temperature=0.0,
            max_tokens=1024,
            enable_tracing=False,
            enable_memory=False,
            enable_guardrails=True,
            enable_storage=False,
            enable_cache=False,
            max_retries=1,
            retry_delay=0.0,
            max_concurrency=1,
            parallel_execution=False,
            output_dir="test_artifacts",
            log_level="ERROR",
            enable_auth=False,
            enable_rate_limiting=False,
            extra=overrides,
        )


class MinimalPreset(PresetConfig):
    """
    Minimal preset for simple use cases.
    
    Features:
    - Bare minimum configuration
    - No optional features
    - Quick setup
    """
    
    def __init__(self, **overrides):
        super().__init__(
            name="minimal",
            description="Minimal configuration for simple tasks",
            model="gpt-4o-mini",
            provider="azure",
            temperature=0.7,
            max_tokens=2048,
            enable_tracing=False,
            enable_memory=False,
            enable_guardrails=False,
            enable_storage=False,
            enable_cache=False,
            max_retries=1,
            retry_delay=0.0,
            max_concurrency=1,
            parallel_execution=False,
            output_dir="artifacts",
            log_level="INFO",
            enable_auth=False,
            enable_rate_limiting=False,
            extra=overrides,
        )


# =============================================================================
# Preset Registry
# =============================================================================

PRESET_REGISTRY: Dict[str, type] = {
    "enterprise": EnterprisePreset,
    "startup": StartupPreset,
    "development": DevelopmentPreset,
    "production": ProductionPreset,
    "testing": TestingPreset,
    "minimal": MinimalPreset,
}


def load_preset(
    name: str,
    **overrides,
) -> PresetConfig:
    """
    Load a preset by name.
    
    Args:
        name: Preset name (enterprise, startup, development, production, testing, minimal)
        **overrides: Configuration overrides
        
    Returns:
        PresetConfig instance
        
    Example:
        >>> config = load_preset("enterprise")
        >>> config = load_preset("startup", model="gpt-4o")
    """
    preset_class = PRESET_REGISTRY.get(name.lower())
    
    if preset_class is None:
        available = ", ".join(PRESET_REGISTRY.keys())
        raise ValueError(f"Unknown preset: {name}. Available: {available}")
    
    return preset_class(**overrides)


def list_presets() -> List[str]:
    """List available presets."""
    return list(PRESET_REGISTRY.keys())


def get_preset_info(name: str) -> Dict[str, Any]:
    """Get information about a preset."""
    preset = load_preset(name)
    return {
        "name": preset.name,
        "description": preset.description,
        "model": preset.model,
        "provider": preset.provider,
        "features": {
            "tracing": preset.enable_tracing,
            "memory": preset.enable_memory,
            "guardrails": preset.enable_guardrails,
            "storage": preset.enable_storage,
            "cache": preset.enable_cache,
            "auth": preset.enable_auth,
            "rate_limiting": preset.enable_rate_limiting,
        },
    }


# =============================================================================
# Environment-based Preset Loading
# =============================================================================

def auto_preset() -> PresetConfig:
    """
    Automatically select preset based on environment.
    
    Checks ENVIRONMENT or ENV variable:
    - production/prod -> ProductionPreset
    - development/dev -> DevelopmentPreset
    - testing/test/ci -> TestingPreset
    - startup -> StartupPreset
    - enterprise -> EnterprisePreset
    - Default -> DevelopmentPreset
    
    Returns:
        PresetConfig for detected environment
    """
    env = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
    
    env_mapping = {
        "production": "production",
        "prod": "production",
        "development": "development",
        "dev": "development",
        "testing": "testing",
        "test": "testing",
        "ci": "testing",
        "startup": "startup",
        "enterprise": "enterprise",
    }
    
    preset_name = env_mapping.get(env, "development")
    logger.info(f"Auto-detected environment: {env} -> preset: {preset_name}")
    
    return load_preset(preset_name)
