"""Final coverage push tests - targeting communication.py uncovered lines"""

import pytest
from agenticaiframework import CommunicationManager


class TestCommunicationFinal:
    """Cover all communication.py lines"""
    
    def test_register_protocol(self):
        """Test protocol registration"""
        comm = CommunicationManager()
        
        def my_handler(data):
            return f"Handled: {data}"
        
        comm.register_protocol("test_proto", my_handler)
        assert "test_proto" in comm.list_protocols()
    
    def test_register_handler(self):
        """Test handler registration (alias method)"""
        comm = CommunicationManager()
        
        def handler1(data):
            return data * 2
        
        def handler2(data):
            return data + 10
        
        comm.register_handler(handler1, name="doubler")
        comm.register_handler(handler2)  # Without name
        
        protocols = comm.list_protocols()
        assert "doubler" in protocols
        assert len(protocols) >= 2
    
    def test_send_with_protocol(self):
        """Test sending data with registered protocol"""
        comm = CommunicationManager()
        
        def echo_handler(data):
            return f"Echo: {data}"
        
        comm.register_protocol("echo", echo_handler)
        result = comm.send("echo", "test message")
        
        assert result == "Echo: test message"
    
    def test_send_with_missing_protocol(self):
        """Test sending with non-existent protocol"""
        comm = CommunicationManager()
        result = comm.send("nonexistent", "data")
        
        assert result is None
    
    def test_send_with_error(self):
        """Test sending when handler raises error"""
        comm = CommunicationManager()
        
        def failing_handler(data):
            raise ValueError("Handler failed")
        
        comm.register_protocol("failer", failing_handler)
        result = comm.send("failer", "data")
        
        assert result is None  # Should return None on error
    
    def test_send_message_with_protocol(self):
        """Test send_message with specified protocol"""
        comm = CommunicationManager()
        
        def processor(data):
            return data.upper()
        
        comm.register_protocol("upper", processor)
        result = comm.send_message("hello", protocol="upper")
        
        assert result == "HELLO"
    
    def test_send_message_without_protocol(self):
        """Test send_message using first available protocol"""
        comm = CommunicationManager()
        
        def handler1(data):
            return f"First: {data}"
        
        def handler2(data):
            return f"Second: {data}"
        
        comm.register_protocol("proto1", handler1)
        comm.register_protocol("proto2", handler2)
        
        result = comm.send_message("test")
        assert result is not None
        assert "test" in result
    
    def test_send_message_no_protocols(self):
        """Test send_message with no protocols registered"""
        comm = CommunicationManager()
        result = comm.send_message("message")
        
        assert result is None
    
    def test_list_protocols(self):
        """Test listing all protocols"""
        comm = CommunicationManager()
        
        comm.register_protocol("p1", lambda x: x)
        comm.register_protocol("p2", lambda x: x)
        comm.register_protocol("p3", lambda x: x)
        
        protocols = comm.list_protocols()
        assert len(protocols) == 3
        assert "p1" in protocols
        assert "p2" in protocols
        assert "p3" in protocols
