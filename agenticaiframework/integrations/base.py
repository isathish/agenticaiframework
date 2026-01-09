"""
Base Integration Module.

Abstract base class for all integrations.
"""

import logging
import base64
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from .types import IntegrationConfig

logger = logging.getLogger(__name__)


class BaseIntegration(ABC):
    """Base class for integrations."""
    
    def __init__(self, config: IntegrationConfig):
        self.config = config
        self._session = None
        self._last_error: Optional[str] = None
    
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection."""
    
    @abstractmethod
    def disconnect(self):
        """Close connection."""
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check integration health."""
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        headers = {}
        
        if self.config.auth_type == "api_key":
            key_header = self.config.settings.get('api_key_header', 'Authorization')
            key_prefix = self.config.settings.get('api_key_prefix', 'Bearer')
            headers[key_header] = f"{key_prefix} {self.config.credentials.get('api_key', '')}"
        
        elif self.config.auth_type == "basic":
            credentials = base64.b64encode(
                f"{self.config.credentials.get('username', '')}:{self.config.credentials.get('password', '')}".encode()
            ).decode()
            headers['Authorization'] = f"Basic {credentials}"
        
        elif self.config.auth_type == "oauth":
            headers['Authorization'] = f"Bearer {self.config.credentials.get('access_token', '')}"
        
        return headers


__all__ = ['BaseIntegration']
