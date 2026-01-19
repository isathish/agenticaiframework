"""
Global Configuration for AgenticAI Framework.

Provides centralized configuration and initialization for the framework.
Reduces boilerplate code for common setups.
"""

import os
import logging
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class FrameworkConfig:
    """Global configuration for the AgenticAI framework."""
    
    # LLM Settings
    default_provider: str = "auto"  # 'openai', 'anthropic', 'google', 'auto'
    default_model: Optional[str] = None
    temperature: float = 0.7
    max_retries: int = 3
    
    # Guardrails
    guardrails_enabled: bool = True
    guardrails_preset: str = "minimal"  # 'minimal', 'safety', 'enterprise'
    
    # Tracing
    tracing_enabled: bool = True
    trace_sampling_rate: float = 1.0
    
    # Tools
    auto_discover_tools: bool = True
    tool_packages: List[str] = field(default_factory=lambda: ["agenticaiframework.tools"])
    
    # Memory
    max_context_tokens: int = 4096
    auto_compress_context: bool = True
    
    # Logging
    log_level: str = "INFO"
    verbose: bool = False
    
    @classmethod
    def from_env(cls) -> 'FrameworkConfig':
        """Create configuration from environment variables."""
        return cls(
            default_provider=os.getenv("AGENTIC_DEFAULT_PROVIDER", "auto"),
            default_model=os.getenv("AGENTIC_DEFAULT_MODEL"),
            temperature=float(os.getenv("AGENTIC_TEMPERATURE", "0.7")),
            max_retries=int(os.getenv("AGENTIC_MAX_RETRIES", "3")),
            guardrails_enabled=os.getenv("AGENTIC_GUARDRAILS", "true").lower() == "true",
            guardrails_preset=os.getenv("AGENTIC_GUARDRAILS_PRESET", "minimal"),
            tracing_enabled=os.getenv("AGENTIC_TRACING", "true").lower() == "true",
            trace_sampling_rate=float(os.getenv("AGENTIC_TRACE_SAMPLING", "1.0")),
            auto_discover_tools=os.getenv("AGENTIC_AUTO_DISCOVER_TOOLS", "true").lower() == "true",
            max_context_tokens=int(os.getenv("AGENTIC_MAX_CONTEXT_TOKENS", "4096")),
            log_level=os.getenv("AGENTIC_LOG_LEVEL", "INFO"),
            verbose=os.getenv("AGENTIC_VERBOSE", "false").lower() == "true",
        )


# Global configuration instance
_config: Optional[FrameworkConfig] = None
_initialized: bool = False


def configure(
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    guardrails: Optional[Union[bool, str]] = None,
    tracing: Optional[bool] = None,
    auto_discover_tools: Optional[bool] = None,
    log_level: Optional[str] = None,
    verbose: Optional[bool] = None,
    from_environment: bool = True,
    **kwargs,
) -> FrameworkConfig:
    """
    Configure the AgenticAI framework with sensible defaults.
    
    Call this once at startup to configure global settings.
    All parameters are optional - omitted values use defaults or environment variables.
    
    Args:
        provider: Default LLM provider ('openai', 'anthropic', 'google', 'auto')
        model: Default model name (e.g., 'gpt-4o', 'claude-sonnet-4-20250514')
        temperature: Default temperature for LLM calls
        guardrails: Enable guardrails (True/False) or preset name ('minimal', 'safety', 'enterprise')
        tracing: Enable execution tracing
        auto_discover_tools: Auto-discover and register tools
        log_level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        verbose: Enable verbose output
        from_environment: Load settings from environment variables first
        **kwargs: Additional configuration options
        
    Returns:
        The global FrameworkConfig instance
        
    Example:
        >>> import agenticaiframework as aaf
        >>> 
        >>> # Quick setup with defaults from environment
        >>> aaf.configure()
        >>> 
        >>> # Or with specific options
        >>> aaf.configure(
        ...     provider="openai",
        ...     model="gpt-4o",
        ...     guardrails="enterprise",
        ...     tracing=True,
        ... )
        >>> 
        >>> # Then create agents without boilerplate
        >>> agent = Agent.quick("MyAssistant")
    """
    global _config, _initialized
    
    # Start with environment config or defaults
    if from_environment:
        _config = FrameworkConfig.from_env()
    else:
        _config = FrameworkConfig()
    
    # Apply overrides
    if provider is not None:
        _config.default_provider = provider
    if model is not None:
        _config.default_model = model
    if temperature is not None:
        _config.temperature = temperature
    if guardrails is not None:
        if isinstance(guardrails, bool):
            _config.guardrails_enabled = guardrails
        else:
            _config.guardrails_enabled = True
            _config.guardrails_preset = guardrails
    if tracing is not None:
        _config.tracing_enabled = tracing
    if auto_discover_tools is not None:
        _config.auto_discover_tools = auto_discover_tools
    if log_level is not None:
        _config.log_level = log_level
    if verbose is not None:
        _config.verbose = verbose
    
    # Apply additional kwargs
    for key, value in kwargs.items():
        if hasattr(_config, key):
            setattr(_config, key, value)
    
    # Initialize framework
    _initialize_framework(_config)
    _initialized = True
    
    logger.info("AgenticAI Framework configured: provider=%s, guardrails=%s", 
                _config.default_provider, _config.guardrails_preset)
    
    return _config


def _initialize_framework(config: FrameworkConfig) -> None:
    """Initialize framework components based on configuration."""
    
    # Configure logging
    logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO))
    
    if config.verbose:
        logging.getLogger("agenticaiframework").setLevel(logging.DEBUG)
    
    # Auto-discover tools
    if config.auto_discover_tools:
        from .tools import tool_registry
        for package in config.tool_packages:
            try:
                tool_registry.discover(package)
            except Exception as e:
                logger.debug("Could not discover tools from %s: %s", package, e)
    
    # Configure tracer
    if config.tracing_enabled:
        from .tracing import tracer
        tracer.set_sampling_rate(config.trace_sampling_rate)


def get_config() -> FrameworkConfig:
    """Get the current global configuration."""
    global _config
    if _config is None:
        # Auto-configure from environment
        return configure()
    return _config


def is_configured() -> bool:
    """Check if the framework has been configured."""
    return _initialized


def reset_config() -> None:
    """Reset configuration to defaults."""
    global _config, _initialized
    _config = None
    _initialized = False


__all__ = [
    'FrameworkConfig',
    'configure',
    'get_config',
    'is_configured',
    'reset_config',
]
