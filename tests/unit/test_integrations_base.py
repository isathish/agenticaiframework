"""
Tests for integrations module - Base and Types.
"""

import time
import pytest
from unittest.mock import Mock, patch

from agenticaiframework.integrations.base import BaseIntegration
from agenticaiframework.integrations.types import IntegrationConfig, IntegrationStatus


class TestIntegrationStatus:
    """Tests for IntegrationStatus enum."""
    
    def test_status_values(self):
        """Test all status values exist."""
        assert IntegrationStatus.ACTIVE.value == "active"
        assert IntegrationStatus.INACTIVE.value == "inactive"
        assert IntegrationStatus.ERROR.value == "error"
        assert IntegrationStatus.PENDING.value == "pending"


class TestIntegrationConfig:
    """Tests for IntegrationConfig dataclass."""
    
    def test_create_config(self):
        """Test creating an integration config."""
        config = IntegrationConfig(
            integration_id="int-123",
            name="Test Integration",
            integration_type="api",
            endpoint="https://api.example.com",
            auth_type="api_key",
            credentials={"api_key": "secret"},
            settings={"timeout": 30},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        assert config.integration_id == "int-123"
        assert config.name == "Test Integration"
        assert config.integration_type == "api"
        assert config.endpoint == "https://api.example.com"
        assert config.auth_type == "api_key"
        assert config.credentials["api_key"] == "secret"
        assert config.settings["timeout"] == 30
        assert config.status == IntegrationStatus.ACTIVE
    
    def test_config_default_metadata(self):
        """Test default metadata is empty dict."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="none",
            credentials={},
            settings={},
            status=IntegrationStatus.PENDING,
            created_at=time.time(),
        )
        
        assert config.metadata == {}
    
    def test_config_with_metadata(self):
        """Test config with custom metadata."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="none",
            credentials={},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
            metadata={"version": "1.0", "environment": "prod"}
        )
        
        assert config.metadata["version"] == "1.0"
        assert config.metadata["environment"] == "prod"


class ConcreteIntegration(BaseIntegration):
    """Concrete implementation for testing."""
    
    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self.connected = False
    
    def connect(self) -> bool:
        self.connected = True
        return True
    
    def disconnect(self):
        self.connected = False
    
    def health_check(self):
        return {"status": "healthy" if self.connected else "disconnected"}


class TestBaseIntegration:
    """Tests for BaseIntegration class."""
    
    def test_init(self):
        """Test initialization."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://api.example.com",
            auth_type="api_key",
            credentials={"api_key": "secret"},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        integration = ConcreteIntegration(config)
        
        assert integration.config == config
        assert integration._session is None
        assert integration._last_error is None
    
    def test_connect(self):
        """Test connect method."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="none",
            credentials={},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        integration = ConcreteIntegration(config)
        result = integration.connect()
        
        assert result is True
        assert integration.connected is True
    
    def test_disconnect(self):
        """Test disconnect method."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="none",
            credentials={},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        integration = ConcreteIntegration(config)
        integration.connect()
        integration.disconnect()
        
        assert integration.connected is False
    
    def test_health_check(self):
        """Test health check method."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="none",
            credentials={},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        integration = ConcreteIntegration(config)
        
        # Disconnected
        result = integration.health_check()
        assert result["status"] == "disconnected"
        
        # Connected
        integration.connect()
        result = integration.health_check()
        assert result["status"] == "healthy"
    
    def test_get_auth_headers_api_key(self):
        """Test API key authentication headers."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="api_key",
            credentials={"api_key": "my-secret-key"},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        integration = ConcreteIntegration(config)
        headers = integration._get_auth_headers()
        
        assert "Authorization" in headers
        assert "my-secret-key" in headers["Authorization"]
    
    def test_get_auth_headers_api_key_custom_header(self):
        """Test API key with custom header name."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="api_key",
            credentials={"api_key": "secret"},
            settings={"api_key_header": "X-API-Key", "api_key_prefix": ""},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        integration = ConcreteIntegration(config)
        headers = integration._get_auth_headers()
        
        assert "X-API-Key" in headers
        assert headers["X-API-Key"].strip() == "secret"
    
    def test_get_auth_headers_basic(self):
        """Test basic authentication headers."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="basic",
            credentials={"username": "user", "password": "pass"},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        integration = ConcreteIntegration(config)
        headers = integration._get_auth_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
    
    def test_get_auth_headers_oauth(self):
        """Test OAuth authentication headers."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="oauth",
            credentials={"access_token": "oauth-token-123"},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        integration = ConcreteIntegration(config)
        headers = integration._get_auth_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer oauth-token-123"
    
    def test_get_auth_headers_none(self):
        """Test no authentication."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="none",
            credentials={},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        integration = ConcreteIntegration(config)
        headers = integration._get_auth_headers()
        
        assert headers == {}


class TestIntegrationStatusTransitions:
    """Tests for status transitions."""
    
    def test_active_to_inactive(self):
        """Test transitioning from active to inactive."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="none",
            credentials={},
            settings={},
            status=IntegrationStatus.ACTIVE,
            created_at=time.time(),
        )
        
        assert config.status == IntegrationStatus.ACTIVE
        
        # Simulate status change
        config = IntegrationConfig(
            **{**config.__dict__, 'status': IntegrationStatus.INACTIVE}
        )
        
        assert config.status == IntegrationStatus.INACTIVE
    
    def test_pending_to_active(self):
        """Test transitioning from pending to active."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="none",
            credentials={},
            settings={},
            status=IntegrationStatus.PENDING,
            created_at=time.time(),
        )
        
        assert config.status == IntegrationStatus.PENDING
    
    def test_error_status(self):
        """Test error status."""
        config = IntegrationConfig(
            integration_id="int-1",
            name="Test",
            integration_type="api",
            endpoint="https://example.com",
            auth_type="none",
            credentials={},
            settings={},
            status=IntegrationStatus.ERROR,
            created_at=time.time(),
        )
        
        assert config.status == IntegrationStatus.ERROR
