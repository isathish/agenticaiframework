"""
Integration Types Module.

Contains all enums and dataclasses for the integrations package.
"""

import time
from typing import Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class IntegrationStatus(Enum):
    """Status of an integration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"


@dataclass
class IntegrationConfig:
    """Configuration for an integration."""
    integration_id: str
    name: str
    integration_type: str
    endpoint: str
    auth_type: str  # api_key, oauth, basic, none
    credentials: Dict[str, str]
    settings: Dict[str, Any]
    status: IntegrationStatus
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = ['IntegrationStatus', 'IntegrationConfig']
