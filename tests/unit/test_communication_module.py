"""
Tests for communication module.
"""

import pytest
from unittest.mock import Mock, patch

from agenticaiframework.communication import CommunicationManager


class TestCommunicationManager:
    """Tests for CommunicationManager class."""
    
    def test_init(self):
        """Test initialization."""
        manager = CommunicationManager()
        assert len(manager.protocols) == 0
    
    def test_register_protocol(self):
        """Test registering a protocol."""
        manager = CommunicationManager()
        handler = Mock()
        
        manager.register_protocol("http", handler)
        
        assert "http" in manager.protocols
        assert manager.protocols["http"] == handler
    
    def test_register_handler(self):
        """Test registering a handler (alias)."""
        manager = CommunicationManager()
        handler = Mock()
        
        manager.register_handler(handler, name="custom")
        
        assert "custom" in manager.protocols
    
    def test_register_handler_auto_name(self):
        """Test registering handler with auto-generated name."""
        manager = CommunicationManager()
        handler = Mock()
        
        manager.register_handler(handler)
        
        assert "handler_0" in manager.protocols
    
    def test_send_success(self):
        """Test sending data successfully."""
        manager = CommunicationManager()
        handler = Mock(return_value="response")
        manager.register_protocol("http", handler)
        
        result = manager.send("http", {"data": "value"})
        
        assert result == "response"
        handler.assert_called_once_with({"data": "value"})
    
    def test_send_protocol_not_found(self):
        """Test sending with unknown protocol."""
        manager = CommunicationManager()
        
        result = manager.send("unknown", {"data": "value"})
        
        assert result is None
    
    def test_send_type_error(self):
        """Test sending with TypeError in handler."""
        manager = CommunicationManager()
        handler = Mock(side_effect=TypeError("type error"))
        manager.register_protocol("http", handler)
        
        result = manager.send("http", {"data": "value"})
        
        assert result is None
    
    def test_send_value_error(self):
        """Test sending with ValueError in handler."""
        manager = CommunicationManager()
        handler = Mock(side_effect=ValueError("value error"))
        manager.register_protocol("http", handler)
        
        result = manager.send("http", {"data": "value"})
        
        assert result is None
    
    def test_send_connection_error(self):
        """Test sending with ConnectionError in handler."""
        manager = CommunicationManager()
        handler = Mock(side_effect=ConnectionError("connection error"))
        manager.register_protocol("http", handler)
        
        result = manager.send("http", {"data": "value"})
        
        assert result is None
    
    def test_send_timeout_error(self):
        """Test sending with TimeoutError in handler."""
        manager = CommunicationManager()
        handler = Mock(side_effect=TimeoutError("timeout"))
        manager.register_protocol("http", handler)
        
        result = manager.send("http", {"data": "value"})
        
        assert result is None
    
    def test_send_unexpected_error(self):
        """Test sending with unexpected error in handler."""
        manager = CommunicationManager()
        handler = Mock(side_effect=RuntimeError("unexpected"))
        manager.register_protocol("http", handler)
        
        result = manager.send("http", {"data": "value"})
        
        assert result is None
    
    def test_list_protocols(self):
        """Test listing protocols."""
        manager = CommunicationManager()
        manager.register_protocol("http", Mock())
        manager.register_protocol("grpc", Mock())
        
        protocols = manager.list_protocols()
        
        assert len(protocols) == 2
        assert "http" in protocols
        assert "grpc" in protocols
    
    def test_send_message_with_protocol(self):
        """Test send_message with specific protocol."""
        manager = CommunicationManager()
        handler = Mock(return_value="response")
        manager.register_protocol("http", handler)
        
        result = manager.send_message("hello", protocol="http")
        
        assert result == "response"
    
    def test_send_message_first_protocol(self):
        """Test send_message using first available protocol."""
        manager = CommunicationManager()
        handler = Mock(return_value="response")
        manager.register_protocol("http", handler)
        
        result = manager.send_message("hello")
        
        assert result == "response"
    
    def test_send_message_no_protocols(self):
        """Test send_message with no protocols available."""
        manager = CommunicationManager()
        
        result = manager.send_message("hello")
        
        assert result is None


class TestCommunicationManagerMultipleProtocols:
    """Tests for multiple protocols."""
    
    def test_multiple_protocols(self):
        """Test using multiple protocols."""
        manager = CommunicationManager()
        
        http_handler = Mock(return_value="http_response")
        grpc_handler = Mock(return_value="grpc_response")
        
        manager.register_protocol("http", http_handler)
        manager.register_protocol("grpc", grpc_handler)
        
        assert manager.send("http", "data1") == "http_response"
        assert manager.send("grpc", "data2") == "grpc_response"
    
    def test_override_protocol(self):
        """Test overriding a protocol."""
        manager = CommunicationManager()
        
        handler1 = Mock(return_value="response1")
        handler2 = Mock(return_value="response2")
        
        manager.register_protocol("http", handler1)
        manager.register_protocol("http", handler2)  # Override
        
        result = manager.send("http", "data")
        
        assert result == "response2"
        handler1.assert_not_called()
