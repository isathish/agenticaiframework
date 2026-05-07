"""Internal stdlib-only support modules for AgenticAI Framework.

Everything under ``agenticaiframework._internal`` is part of the private API
and should not be imported by user code directly. These modules replace
external PyPI dependencies (openai, anthropic, requests, httpx, pydantic,
yaml, numpy, etc.) with pure-stdlib equivalents so the framework can run on
Python 3.10+ with zero runtime dependencies.
"""

__all__: list[str] = []
