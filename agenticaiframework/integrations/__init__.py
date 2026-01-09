"""
Integration Package for External Services.

Features:
- ITSM Integration (ServiceNow, etc.)
- Developer Tools (GitHub, Azure DevOps)
- Data Platforms (Snowflake, Databricks)
- Generic webhook support
"""

# Types and configuration
from .types import IntegrationStatus, IntegrationConfig

# Base class
from .base import BaseIntegration

# ITSM Integrations
from .servicenow import ServiceNowIntegration

# Developer Tools
from .github import GitHubIntegration
from .azure_devops import AzureDevOpsIntegration

# Data Platforms
from .data_platforms import (
    DataPlatformConnector,
    SnowflakeConnector,
    DatabricksConnector
)

# Webhooks
from .webhooks import WebhookManager

# Manager
from .manager import IntegrationManager

# Global instances
integration_manager = IntegrationManager()
webhook_manager = WebhookManager()


__all__ = [
    # Types
    'IntegrationStatus',
    'IntegrationConfig',
    # Base
    'BaseIntegration',
    # ITSM
    'ServiceNowIntegration',
    # Developer Tools
    'GitHubIntegration',
    'AzureDevOpsIntegration',
    # Data Platforms
    'DataPlatformConnector',
    'SnowflakeConnector',
    'DatabricksConnector',
    # Webhooks
    'WebhookManager',
    # Manager
    'IntegrationManager',
    # Global instances
    'integration_manager',
    'webhook_manager'
]
