"""
Comprehensive tests for communication/protocols.py to boost coverage.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from queue import Queue, Empty
import json
import sys

# Check if optional dependencies are available
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import paho.mqtt.client
    HAS_PAHO = True
except ImportError:
    HAS_PAHO = False


class TestProtocolType:
    """Test ProtocolType enum."""
    
    def test_protocol_type_values(self):
        """Test all ProtocolType values exist."""
        from agenticaiframework.communication.protocols import ProtocolType
        
        assert ProtocolType.STDIO.value == "stdio"
        assert ProtocolType.HTTP.value == "http"
        assert ProtocolType.HTTPS.value == "https"
        assert ProtocolType.SSE.value == "sse"
        assert ProtocolType.MQTT.value == "mqtt"
        assert ProtocolType.WEBSOCKET.value == "websocket"
    
    def test_protocol_type_enum_membership(self):
        """Test enum membership."""
        from agenticaiframework.communication.protocols import ProtocolType
        
        assert ProtocolType.STDIO in ProtocolType
        assert ProtocolType.HTTP in ProtocolType


class TestProtocolConfig:
    """Test ProtocolConfig dataclass."""
    
    def test_config_defaults(self):
        """Test default values."""
        from agenticaiframework.communication.protocols import ProtocolConfig, ProtocolType
        
        config = ProtocolConfig(protocol_type=ProtocolType.HTTP)
        
        assert config.host == "localhost"
        assert config.port == 8080
        assert config.path == "/"
        assert config.timeout == 30.0
        assert config.retry_count == 3
        assert config.retry_delay == 1.0
        assert config.headers == {}
        assert config.auth_token is None
        assert config.ssl_verify == True
        assert config.metadata == {}
    
    def test_config_custom_values(self):
        """Test custom config values."""
        from agenticaiframework.communication.protocols import ProtocolConfig, ProtocolType
        
        config = ProtocolConfig(
            protocol_type=ProtocolType.HTTPS,
            host="example.com",
            port=443,
            path="/api",
            timeout=60.0,
            retry_count=5,
            headers={"X-Custom": "value"},
            auth_token="token123"
        )
        
        assert config.host == "example.com"
        assert config.port == 443
        assert config.timeout == 60.0
        assert config.auth_token == "token123"


class TestCommunicationProtocolBase:
    """Test CommunicationProtocol base class."""
    
    def test_base_init_default_config(self):
        """Test base protocol with default config."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        # HTTPProtocol is a concrete implementation
        protocol = HTTPProtocol()
        
        assert protocol.is_connected == False
        assert len(protocol._message_handlers) == 0
        assert protocol._connection_id is not None
    
    def test_on_message_handler(self):
        """Test registering message handlers."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        protocol = HTTPProtocol()
        
        handler = Mock()
        protocol.on_message(handler)
        
        assert handler in protocol._message_handlers
    
    def test_notify_handlers(self):
        """Test notifying message handlers."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        protocol = HTTPProtocol()
        
        handler1 = Mock()
        handler2 = Mock()
        protocol.on_message(handler1)
        protocol.on_message(handler2)
        
        message = {"type": "test", "data": "hello"}
        protocol._notify_handlers(message)
        
        handler1.assert_called_once_with(message)
        handler2.assert_called_once_with(message)
    
    def test_notify_handlers_error(self):
        """Test handler errors are caught."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        protocol = HTTPProtocol()
        
        bad_handler = Mock(side_effect=Exception("handler error"))
        protocol.on_message(bad_handler)
        
        # Should not raise
        protocol._notify_handlers({"type": "test"})


class TestSTDIOProtocol:
    """Test STDIOProtocol class."""
    
    def test_stdio_init(self):
        """Test STDIO protocol initialization."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        protocol = STDIOProtocol(command=["python", "test.py"])
        
        assert protocol.command == ["python", "test.py"]
        assert protocol.encoding == "utf-8"
        assert protocol._process is None
        assert protocol._running == False
    
    def test_stdio_init_no_command(self):
        """Test STDIO protocol with no command."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        protocol = STDIOProtocol()
        
        assert protocol.command == []
    
    def test_stdio_connect_no_command(self):
        """Test connect fails with no command."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        protocol = STDIOProtocol()
        result = protocol.connect()
        
        assert result == False
        assert protocol.is_connected == False
    
    @patch('subprocess.Popen')
    def test_stdio_connect_success(self, mock_popen):
        """Test successful connect."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        mock_process = Mock()
        mock_process.stdout.readline.return_value = ""
        mock_popen.return_value = mock_process
        
        protocol = STDIOProtocol(command=["python", "test.py"])
        result = protocol.connect()
        
        assert result == True
        assert protocol.is_connected == True
        assert protocol._running == True
    
    @patch('subprocess.Popen', side_effect=Exception("spawn error"))
    def test_stdio_connect_error(self, mock_popen):
        """Test connect handles errors."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        protocol = STDIOProtocol(command=["bad", "command"])
        result = protocol.connect()
        
        assert result == False
    
    def test_stdio_disconnect(self):
        """Test disconnect."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        protocol = STDIOProtocol()
        protocol._running = True
        
        result = protocol.disconnect()
        
        assert result == True
        assert protocol._running == False
        assert protocol.is_connected == False
    
    @patch('subprocess.Popen')
    def test_stdio_disconnect_terminates_process(self, mock_popen):
        """Test disconnect terminates process."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        mock_process = Mock()
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process
        
        protocol = STDIOProtocol(command=["python", "test.py"])
        protocol._process = mock_process
        protocol._running = True
        
        protocol.disconnect()
        
        mock_process.terminate.assert_called_once()
    
    def test_stdio_send_not_connected(self):
        """Test send when not connected."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        protocol = STDIOProtocol()
        
        result = protocol.send({"type": "test"})
        
        assert "error" in result
    
    @patch('subprocess.Popen')
    def test_stdio_send_writes_to_stdin(self, mock_popen):
        """Test send writes JSON to stdin."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        mock_stdin = Mock()
        mock_process = Mock()
        mock_process.stdin = mock_stdin
        mock_popen.return_value = mock_process
        
        protocol = STDIOProtocol(command=["python", "test.py"])
        protocol._process = mock_process
        protocol._message_queue = Queue()
        
        # Put a response in the queue
        protocol._message_queue.put({"response": "ok"})
        
        result = protocol.send({"type": "test"})
        
        mock_stdin.write.assert_called()
        mock_stdin.flush.assert_called()
    
    def test_stdio_receive_empty_queue(self):
        """Test receive with empty queue."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        protocol = STDIOProtocol()
        protocol.config.timeout = 0.1
        
        result = protocol.receive(timeout=0.1)
        
        assert result is None
    
    def test_stdio_receive_with_message(self):
        """Test receive with message in queue."""
        from agenticaiframework.communication.protocols import STDIOProtocol
        
        protocol = STDIOProtocol()
        protocol._message_queue.put({"type": "response", "data": "hello"})
        
        result = protocol.receive(timeout=1.0)
        
        assert result == {"type": "response", "data": "hello"}


class TestHTTPProtocol:
    """Test HTTPProtocol class."""
    
    def test_http_init_defaults(self):
        """Test HTTP protocol default initialization."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        protocol = HTTPProtocol()
        
        assert protocol.config.host == "localhost"
        assert protocol.config.port == 8080
        assert protocol.use_ssl == False
    
    def test_http_init_custom(self):
        """Test HTTP protocol custom initialization."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        protocol = HTTPProtocol(
            host="api.example.com",
            port=443,
            path="/v1/agent",
            use_ssl=True
        )
        
        assert protocol.config.host == "api.example.com"
        assert protocol.config.port == 443
        assert protocol.use_ssl == True
    
    def test_http_base_url_http(self):
        """Test base_url for HTTP."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        protocol = HTTPProtocol(host="example.com", port=8080)
        
        assert protocol.base_url == "http://example.com:8080"
    
    def test_http_base_url_https(self):
        """Test base_url for HTTPS."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        protocol = HTTPProtocol(host="example.com", port=443, use_ssl=True)
        
        assert protocol.base_url == "https://example.com:443"
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_connect_success(self):
        """Test successful HTTP connection."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        with patch('agenticaiframework.communication.protocols.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_session.get.return_value = mock_response
            mock_session_class.return_value = mock_session
            
            protocol = HTTPProtocol()
            result = protocol.connect()
            
            assert result == True
            assert protocol.is_connected == True
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_connect_with_auth_token(self):
        """Test HTTP connect with auth token."""
        from agenticaiframework.communication.protocols import HTTPProtocol, ProtocolConfig, ProtocolType
        
        with patch('agenticaiframework.communication.protocols.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session.headers = {}
            mock_response = Mock()
            mock_response.status_code = 200
            mock_session.get.return_value = mock_response
            mock_session_class.return_value = mock_session
            
            config = ProtocolConfig(
                protocol_type=ProtocolType.HTTP,
                auth_token="test-token"
            )
            protocol = HTTPProtocol(config=config)
            protocol.connect()
            
            assert "Authorization" in mock_session.headers
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_disconnect(self):
        """Test HTTP disconnect."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        mock_session = Mock()
        
        protocol = HTTPProtocol()
        protocol._session = mock_session
        protocol.is_connected = True
        
        result = protocol.disconnect()
        
        assert result == True
        assert protocol.is_connected == False
        mock_session.close.assert_called_once()
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_send_not_connected(self):
        """Test send when not connected."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        protocol = HTTPProtocol()
        
        result = protocol.send({"type": "test"})
        
        assert "error" in result
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_send_success(self):
        """Test successful send."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_session.post.return_value = mock_response
        
        protocol = HTTPProtocol()
        protocol._session = mock_session
        
        result = protocol.send({"type": "query"})
        
        assert result == {"result": "success"}
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_send_error_status(self):
        """Test send with error status code."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_session.post.return_value = mock_response
        
        protocol = HTTPProtocol()
        protocol._session = mock_session
        protocol.config.retry_count = 1
        
        result = protocol.send({"type": "query"})
        
        assert "error" in result
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_receive(self):
        """Test HTTP receive."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "hello"}
        mock_session.get.return_value = mock_response
        
        protocol = HTTPProtocol()
        protocol._session = mock_session
        
        result = protocol.receive(timeout=1.0)
        
        assert result == {"message": "hello"}
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_receive_not_connected(self):
        """Test receive when not connected."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        protocol = HTTPProtocol()
        
        result = protocol.receive()
        
        assert result is None
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_get_method(self):
        """Test HTTP GET method."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}
        mock_session.get.return_value = mock_response
        
        protocol = HTTPProtocol()
        protocol._session = mock_session
        
        result = protocol.get("/api/data", params={"key": "val"})
        
        assert result == {"data": "value"}
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_get_not_connected(self):
        """Test GET when not connected."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        protocol = HTTPProtocol()
        
        result = protocol.get("/api/data")
        
        assert "error" in result


class TestSSEProtocol:
    """Test SSEProtocol class."""
    
    def test_sse_init_defaults(self):
        """Test SSE protocol default initialization."""
        from agenticaiframework.communication.protocols import SSEProtocol
        
        protocol = SSEProtocol()
        
        assert protocol.config.host == "localhost"
        assert protocol.config.port == 8080
        assert protocol.use_ssl == False
    
    def test_sse_init_custom(self):
        """Test SSE protocol custom initialization."""
        from agenticaiframework.communication.protocols import SSEProtocol
        
        protocol = SSEProtocol(
            host="stream.example.com",
            port=443,
            path="/events",
            use_ssl=True
        )
        
        assert protocol.config.host == "stream.example.com"
        assert protocol.use_ssl == True
    
    def test_sse_base_url(self):
        """Test SSE base_url."""
        from agenticaiframework.communication.protocols import SSEProtocol
        
        protocol = SSEProtocol(host="example.com", port=8080)
        
        assert protocol.base_url == "http://example.com:8080"
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_sse_connect_success(self):
        """Test successful SSE connection."""
        from agenticaiframework.communication.protocols import SSEProtocol
        
        with patch('agenticaiframework.communication.protocols.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            protocol = SSEProtocol()
            result = protocol.connect()
            
            assert result == True
            assert protocol.is_connected == True
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_sse_disconnect(self):
        """Test SSE disconnect."""
        from agenticaiframework.communication.protocols import SSEProtocol
        
        mock_session = Mock()
        
        protocol = SSEProtocol()
        protocol._session = mock_session
        protocol._stream_response = Mock()
        
        result = protocol.disconnect()
        
        assert result == True
        assert protocol.is_connected == False
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_sse_send(self):
        """Test SSE send."""
        from agenticaiframework.communication.protocols import SSEProtocol
        
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ack": True}
        mock_session.post.return_value = mock_response
        
        protocol = SSEProtocol()
        protocol._session = mock_session
        
        result = protocol.send({"type": "test"})
        
        assert result == {"ack": True}
    
    def test_sse_send_not_connected(self):
        """Test send when not connected."""
        from agenticaiframework.communication.protocols import SSEProtocol
        
        protocol = SSEProtocol()
        
        result = protocol.send({"type": "test"})
        
        assert "error" in result
    
    def test_sse_receive_empty_queue(self):
        """Test receive with empty queue."""
        from agenticaiframework.communication.protocols import SSEProtocol
        
        protocol = SSEProtocol()
        
        result = protocol.receive(timeout=0.1)
        
        assert result is None
    
    def test_sse_receive_with_event(self):
        """Test receive with event in queue."""
        from agenticaiframework.communication.protocols import SSEProtocol
        
        protocol = SSEProtocol()
        protocol._event_queue.put({"type": "message", "data": "hello"})
        
        result = protocol.receive(timeout=1.0)
        
        assert result["data"] == "hello"


class TestMQTTProtocol:
    """Test MQTTProtocol class."""
    
    def test_mqtt_init_defaults(self):
        """Test MQTT protocol default initialization."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        
        assert protocol.broker == "localhost"
        assert protocol.port == 1883
        assert protocol.topic == "agents/default"
        assert protocol.client_id.startswith("agent-")
    
    def test_mqtt_init_custom(self):
        """Test MQTT protocol custom initialization."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol(
            broker="mqtt.example.com",
            port=8883,
            topic="agents/myagent",
            client_id="custom-client",
            username="user",
            password="pass",
            use_ssl=True
        )
        
        assert protocol.broker == "mqtt.example.com"
        assert protocol.port == 8883
        assert protocol.client_id == "custom-client"
        assert protocol.username == "user"
        assert protocol.use_ssl == True
    
    def test_mqtt_disconnect_no_client(self):
        """Test MQTT disconnect with no client."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        
        result = protocol.disconnect()
        
        assert result == True
        assert protocol.is_connected == False
    
    def test_mqtt_send_not_connected(self):
        """Test send when not connected."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        
        result = protocol.send({"type": "test"})
        
        assert "error" in result
    
    @pytest.mark.skipif(not HAS_PAHO, reason="paho-mqtt module not installed")
    def test_mqtt_send_success(self):
        """Test successful MQTT send."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        mock_client = Mock()
        mock_result = Mock()
        mock_result.mid = 123
        mock_client.publish.return_value = mock_result
        
        protocol = MQTTProtocol()
        protocol._client = mock_client
        
        result = protocol.send({"type": "test"})
        
        assert result["status"] == "published"
        assert result["message_id"] == 123
    
    def test_mqtt_receive_empty_queue(self):
        """Test receive with empty queue."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        protocol.config.timeout = 0.1
        
        result = protocol.receive(timeout=0.1)
        
        assert result is None
    
    def test_mqtt_receive_with_message(self):
        """Test receive with message in queue."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        protocol._message_queue.put({
            "topic": "agents/test",
            "payload": {"data": "hello"}
        })
        
        result = protocol.receive(timeout=1.0)
        
        assert result["topic"] == "agents/test"
    
    def test_mqtt_subscribe_not_connected(self):
        """Test subscribe when not connected."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        
        result = protocol.subscribe("topic/test")
        
        assert result == False
    
    @pytest.mark.skipif(not HAS_PAHO, reason="paho-mqtt module not installed")
    def test_mqtt_subscribe_success(self):
        """Test successful subscribe."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        mock_client = Mock()
        
        protocol = MQTTProtocol()
        protocol._client = mock_client
        
        result = protocol.subscribe("agents/responses", qos=1)
        
        assert result == True
        assert "agents/responses" in protocol._subscriptions
    
    def test_mqtt_unsubscribe_not_connected(self):
        """Test unsubscribe when not connected."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        
        result = protocol.unsubscribe("topic/test")
        
        assert result == False
    
    @pytest.mark.skipif(not HAS_PAHO, reason="paho-mqtt module not installed")
    def test_mqtt_unsubscribe_success(self):
        """Test successful unsubscribe."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        mock_client = Mock()
        
        protocol = MQTTProtocol()
        protocol._client = mock_client
        protocol._subscriptions = ["topic/test"]
        
        result = protocol.unsubscribe("topic/test")
        
        assert result == True
        assert "topic/test" not in protocol._subscriptions
    
    @pytest.mark.skipif(not HAS_PAHO, reason="paho-mqtt module not installed")
    def test_mqtt_on_connect_success(self):
        """Test _on_connect callback success."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        protocol._subscriptions = ["topic1", "topic2"]
        
        mock_client = Mock()
        protocol._on_connect(mock_client, None, None, 0)
        
        assert protocol.is_connected == True
    
    @pytest.mark.skipif(not HAS_PAHO, reason="paho-mqtt module not installed")
    def test_mqtt_on_connect_failure(self):
        """Test _on_connect callback failure."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        
        mock_client = Mock()
        protocol._on_connect(mock_client, None, None, 1)
        
        # Should not set is_connected = True on failure
    
    @pytest.mark.skipif(not HAS_PAHO, reason="paho-mqtt module not installed")
    def test_mqtt_on_message(self):
        """Test _on_message callback."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        
        mock_msg = Mock()
        mock_msg.topic = "test/topic"
        mock_msg.payload = b'{"data": "hello"}'
        
        protocol._on_message(None, None, mock_msg)
        
        # Message should be in queue
        msg = protocol._message_queue.get(timeout=1.0)
        assert msg["topic"] == "test/topic"
        assert msg["payload"]["data"] == "hello"
    
    @pytest.mark.skipif(not HAS_PAHO, reason="paho-mqtt module not installed")
    def test_mqtt_on_message_invalid_json(self):
        """Test _on_message with invalid JSON."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        
        mock_msg = Mock()
        mock_msg.topic = "test/topic"
        mock_msg.payload = b'not valid json'
        
        # Should not raise
        protocol._on_message(None, None, mock_msg)
    
    @pytest.mark.skipif(not HAS_PAHO, reason="paho-mqtt module not installed")
    def test_mqtt_on_disconnect(self):
        """Test _on_disconnect callback."""
        from agenticaiframework.communication.protocols import MQTTProtocol
        
        protocol = MQTTProtocol()
        protocol.is_connected = True
        
        protocol._on_disconnect(None, None, 0)
        
        assert protocol.is_connected == False


class TestProtocolConfigFromInit:
    """Test ProtocolConfig created from protocol init."""
    
    def test_http_creates_config(self):
        """Test HTTPProtocol creates ProtocolConfig."""
        from agenticaiframework.communication.protocols import HTTPProtocol, ProtocolType
        
        protocol = HTTPProtocol(host="test.com", port=9000)
        
        assert protocol.config.host == "test.com"
        assert protocol.config.port == 9000
    
    def test_sse_creates_config(self):
        """Test SSEProtocol creates ProtocolConfig."""
        from agenticaiframework.communication.protocols import SSEProtocol, ProtocolType
        
        protocol = SSEProtocol(host="stream.com", path="/events")
        
        assert protocol.config.host == "stream.com"
        assert protocol.config.path == "/events"
    
    def test_mqtt_creates_config(self):
        """Test MQTTProtocol creates ProtocolConfig."""
        from agenticaiframework.communication.protocols import MQTTProtocol, ProtocolType
        
        protocol = MQTTProtocol(broker="mqtt.io", port=1884)
        
        assert protocol.config.host == "mqtt.io"
        assert protocol.config.port == 1884


class TestProtocolRetry:
    """Test protocol retry logic."""
    
    @pytest.mark.skipif(not HAS_REQUESTS, reason="requests module not installed")
    def test_http_send_retries_on_exception(self):
        """Test HTTP send retries on exception."""
        from agenticaiframework.communication.protocols import HTTPProtocol
        
        mock_session = Mock()
        mock_session.post.side_effect = [Exception("error1"), Exception("error2")]
        
        protocol = HTTPProtocol()
        protocol._session = mock_session
        protocol.config.retry_count = 2
        protocol.config.retry_delay = 0.01
        
        result = protocol.send({"type": "test"})
        
        assert mock_session.post.call_count == 2
        assert "error" in result
