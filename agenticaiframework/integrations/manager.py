"""
Integration Manager.

Manages all integrations with:
- Integration lifecycle
- Credential management
- Health monitoring
- Event routing
"""

import uuid
import time
import logging
import threading
from typing import Dict, Any, List, Optional

from .types import IntegrationConfig, IntegrationStatus
from .base import BaseIntegration
from .servicenow import ServiceNowIntegration
from .github import GitHubIntegration
from .azure_devops import AzureDevOpsIntegration
from .webhooks import WebhookManager

logger = logging.getLogger(__name__)


class IntegrationManager:
    """
    Manages all integrations.
    
    Features:
    - Integration lifecycle
    - Credential management
    - Health monitoring
    - Event routing
    """
    
    def __init__(self):
        self.integrations: Dict[str, BaseIntegration] = {}
        self.configs: Dict[str, IntegrationConfig] = {}
        self.webhook_manager = WebhookManager()
        self._lock = threading.Lock()
        
        # Integration type registry
        self._integration_types = {
            'servicenow': ServiceNowIntegration,
            'github': GitHubIntegration,
            'azure_devops': AzureDevOpsIntegration
        }
    
    def register_integration_type(self, name: str, cls: type):
        """Register a custom integration type."""
        self._integration_types[name] = cls
    
    def add_integration(self,
                       name: str,
                       integration_type: str,
                       endpoint: str,
                       auth_type: str = "api_key",
                       credentials: Dict[str, str] = None,
                       settings: Dict[str, Any] = None) -> IntegrationConfig:
        """Add a new integration."""
        integration_id = str(uuid.uuid4())
        
        config = IntegrationConfig(
            integration_id=integration_id,
            name=name,
            integration_type=integration_type,
            endpoint=endpoint,
            auth_type=auth_type,
            credentials=credentials or {},
            settings=settings or {},
            status=IntegrationStatus.PENDING,
            created_at=time.time()
        )
        
        # Create integration instance
        integration_cls = self._integration_types.get(integration_type)
        if integration_cls:
            integration = integration_cls(config)
        else:
            raise ValueError(f"Unknown integration type: {integration_type}")
        
        with self._lock:
            self.configs[integration_id] = config
            self.integrations[integration_id] = integration
        
        logger.info("Added integration: %s (%s)", name, integration_type)
        return config
    
    def connect(self, integration_id: str) -> bool:
        """Connect an integration."""
        integration = self.integrations.get(integration_id)
        if not integration:
            raise ValueError(f"Integration not found: {integration_id}")
        
        return integration.connect()
    
    def disconnect(self, integration_id: str):
        """Disconnect an integration."""
        integration = self.integrations.get(integration_id)
        if integration:
            integration.disconnect()
    
    def get_integration(self, integration_id: str) -> Optional[BaseIntegration]:
        """Get integration by ID."""
        return self.integrations.get(integration_id)
    
    def get_integration_by_name(self, name: str) -> Optional[BaseIntegration]:
        """Get integration by name."""
        for config in self.configs.values():
            if config.name == name:
                return self.integrations.get(config.integration_id)
        return None
    
    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all integrations."""
        results = {}
        
        for integration_id, integration in self.integrations.items():
            config = self.configs[integration_id]
            results[config.name] = {
                'integration_id': integration_id,
                'type': config.integration_type,
                **integration.health_check()
            }
        
        return results
    
    def list_integrations(self) -> List[Dict[str, Any]]:
        """List all integrations."""
        return [
            {
                'integration_id': c.integration_id,
                'name': c.name,
                'type': c.integration_type,
                'endpoint': c.endpoint,
                'status': c.status.value,
                'created_at': c.created_at
            }
            for c in self.configs.values()
        ]
    
    def remove_integration(self, integration_id: str):
        """Remove an integration."""
        with self._lock:
            if integration_id in self.integrations:
                self.integrations[integration_id].disconnect()
                del self.integrations[integration_id]
                del self.configs[integration_id]
        
        logger.info("Removed integration: %s", integration_id)


__all__ = ['IntegrationManager']
