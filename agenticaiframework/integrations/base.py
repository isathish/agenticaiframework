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
    
    # -- HTTP helpers -------------------------------------------------------
    
    @property
    def _timeout(self) -> float:
        return float(self.config.settings.get('timeout', 30.0))
    
    def _http(self):
        """Lazily built stdlib HTTP client carrying the auth headers."""
        if self._session is None:
            from agenticaiframework._internal.http import Client
            self._session = Client(
                timeout=self._timeout,
                headers={'Accept': 'application/json', **self._get_auth_headers()},
                max_retries=int(self.config.settings.get('max_retries', 2)),
            )
        return self._session
    
    def _request(self, method: str, url: str, **kwargs) -> Any:
        """Issue a request; raise ``IntegrationError`` on non-2xx, return parsed JSON (or text)."""
        response = self._http().request(method, url, **kwargs)
        if not (200 <= response.status < 300):
            self._last_error = f"HTTP {response.status}: {response.text[:300]}"
            raise IntegrationError(self._last_error, status=response.status, body=response.text)
        if not response.content:
            return {}
        ctype = response.headers.get('content-type', '')
        if 'json' in ctype:
            return response.json()
        try:
            return response.json()
        except ValueError:
            return response.text


class IntegrationError(Exception):
    """Raised when a remote system returns an error."""
    
    def __init__(self, message: str, status: Optional[int] = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


__all__ = ['BaseIntegration', 'IntegrationError']
