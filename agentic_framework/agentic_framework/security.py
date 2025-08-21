"""
Agentic Framework Security Module

This module provides comprehensive security mechanisms for the Agentic Framework,
including authentication, authorization, encryption, access control, sandboxing,
and audit logging. It ensures safe and compliant operations across agents, tools,
communication protocols, memory systems, and other components.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime
import hashlib
import hmac
import secrets
import base64
import threading
from abc import ABC, abstractmethod
import logging
import time
import os
from enum import Enum
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityLevel(Enum):
    """Enum for different security levels within the framework."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

class SecurityError(Exception):
    """Custom exception for security-related errors."""
    pass

class AuthenticationProvider(ABC):
    """Abstract base class for authentication mechanisms."""
    
    @abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate a user or component with the provided credentials."""
        pass
    
    @abstractmethod
    def generate_token(self, identity: str, duration: int = 3600) -> str:
        """Generate an authentication token for the given identity."""
        pass
    
    @abstractmethod
    def validate_token(self, token: str) -> bool:
        """Validate an authentication token."""
        pass

class SimpleAuthProvider(AuthenticationProvider):
    """Simple authentication provider using HMAC-SHA256 for token generation."""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode('utf-8')
        self.active_tokens: Dict[str, Tuple[str, float]] = {}
        self.lock = threading.Lock()
    
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Simulate authentication with username/password or API key."""
        username = credentials.get('username')
        password = credentials.get('password')
        api_key = credentials.get('api_key')
        
        if api_key:
            return self._validate_api_key(api_key)
        elif username and password:
            return self._validate_credentials(username, password)
        return False
    
    def _validate_api_key(self, api_key: str) -> bool:
        """Validate an API key (simulated)."""
        # In a real implementation, this would check against a database
        return len(api_key) > 16
    
    def _validate_credentials(self, username: str, password: str) -> bool:
        """Validate username and password (simulated)."""
        # In a real implementation, this would check hashed passwords in a database
        return len(username) > 3 and len(password) > 6
    
    def generate_token(self, identity: str, duration: int = 3600) -> str:
        """Generate a secure token using HMAC-SHA256."""
        timestamp = str(time.time())
        payload = f"{identity}:{timestamp}".encode('utf-8')
        token = hmac.new(self.secret_key, payload, hashlib.sha256).digest()
        token_b64 = base64.b64encode(token).decode('utf-8')
        
        with self.lock:
            self.active_tokens[token_b64] = (identity, time.time() + duration)
        return token_b64
    
    def validate_token(self, token: str) -> bool:
        """Validate a token and check if it has expired."""
        with self.lock:
            if token not in self.active_tokens:
                return False
            identity, expiry = self.active_tokens[token]
            if time.time() > expiry:
                del self.active_tokens[token]
                return False
            return True

class AuthorizationPolicy(ABC):
    """Abstract base class for authorization policies."""
    
    @abstractmethod
    def can_access(self, identity: str, resource: str, action: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if the identity can perform the action on the resource."""
        pass

class RoleBasedPolicy(AuthorizationPolicy):
    """Role-based access control policy."""
    
    def __init__(self):
        self.role_permissions: Dict[str, Dict[str, Set[str]]] = {
            'admin': {'*': {'read', 'write', 'delete', 'execute'}},
            'agent': {'agent/*': {'read', 'write', 'execute'}, 'task/*': {'read', 'write'}},
            'user': {'task/*': {'read'}, 'data/*': {'read'}},
            'guest': {'public/*': {'read'}}
        }
        self.user_roles: Dict[str, Set[str]] = {}
        self.lock = threading.Lock()
    
    def assign_role(self, identity: str, role: str):
        """Assign a role to an identity."""
        with self.lock:
            if identity not in self.user_roles:
                self.user_roles[identity] = set()
            self.user_roles[identity].add(role)
    
    def can_access(self, identity: str, resource: str, action: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if the identity can perform the action on the resource based on roles."""
        if identity not in self.user_roles:
            return False
            
        roles = self.user_roles[identity]
        for role in roles:
            if role not in self.role_permissions:
                continue
            permissions = self.role_permissions[role]
            for resource_pattern, allowed_actions in permissions.items():
                if resource_pattern == '*' or resource.startswith(resource_pattern.split('*')[0]):
                    if action in allowed_actions:
                        return True
        return False

class EncryptionProvider(ABC):
    """Abstract base class for encryption mechanisms."""
    
    @abstractmethod
    def encrypt(self, data: bytes) -> bytes:
        """Encrypt the provided data."""
        pass
    
    @abstractmethod
    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt the provided data."""
        pass

class SimpleEncryptionProvider(EncryptionProvider):
    """Simple encryption provider using XOR with a key (for demonstration)."""
    
    def __init__(self, key: bytes):
        self.key = key
    
    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data using XOR with the key."""
        return bytes(a ^ b for a, b in zip(data, self.key * (len(data) // len(self.key) + 1)))
    
    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt data using XOR with the key (symmetric operation)."""
        return self.encrypt(encrypted_data)  # XOR is symmetric

class SandboxEnvironment:
    """Provides a sandboxed environment for executing untrusted code or components."""
    
    def __init__(self, isolation_level: SecurityLevel = SecurityLevel.MEDIUM):
        self.isolation_level = isolation_level
        self.resource_limits = {
            'cpu': 0.5 if isolation_level.value >= SecurityLevel.MEDIUM.value else 1.0,
            'memory': 512 if isolation_level.value >= SecurityLevel.MEDIUM.value else 1024,  # MB
            'network': isolation_level.value < SecurityLevel.CRITICAL.value
        }
        self.allowed_operations: Set[str] = set()
        self._configure_allowed_operations()
        logger.info(f"Sandbox initialized with isolation level {isolation_level}")
    
    def _configure_allowed_operations(self):
        """Configure allowed operations based on isolation level."""
        if self.isolation_level == SecurityLevel.LOW:
            self.allowed_operations = {'read', 'write', 'execute'}
        elif self.isolation_level == SecurityLevel.MEDIUM:
            self.allowed_operations = {'read', 'write'}
        elif self.isolation_level == SecurityLevel.HIGH:
            self.allowed_operations = {'read'}
        else:  # CRITICAL
            self.allowed_operations = set()
    
    def execute(self, operation: str, payload: Any) -> Any:
        """Execute an operation within the sandbox if allowed."""
        if operation not in self.allowed_operations:
            raise SecurityError(f"Operation {operation} not allowed in sandbox with isolation level {self.isolation_level}")
        
        # Simulate resource limitation checks (in a real implementation, this would use cgroups or similar)
        logger.info(f"Executing {operation} in sandbox with payload {str(payload)[:50]}...")
        
        # Simulated execution with resource constraints
        if operation == 'read':
            return f"Read result for {payload}"
        elif operation == 'write':
            return f"Write completed for {payload}"
        elif operation == 'execute':
            return f"Execution result for {payload}"
        return None

class AuditLogger:
    """Handles logging of security-related events for compliance and debugging."""
    
    def __init__(self, log_file: str = "security_audit.log", retention_days: int = 30):
        self.log_file = log_file
        self.retention_days = retention_days
        self.lock = threading.Lock()
        self._rotate_logs_if_needed()
        logger.info(f"Audit logger initialized with log file {log_file}")
    
    def _rotate_logs_if_needed(self):
        """Rotate logs if they exceed retention period (simulated)."""
        try:
            if os.path.exists(self.log_file):
                mod_time = os.path.getmtime(self.log_file)
                if time.time() - mod_time > self.retention_days * 24 * 60 * 60:
                    with open(self.log_file, 'w'):
                        pass  # Clear the file for simulation
        except Exception as e:
            logger.error(f"Error during log rotation check: {str(e)}")
    
    def log_event(self, event_type: str, identity: str, resource: str, action: str, 
                  status: str, details: Optional[Dict[str, Any]] = None):
        """Log a security event with detailed information."""
        timestamp = datetime.now().isoformat()
        event = {
            'timestamp': timestamp,
            'event_type': event_type,
            'identity': identity,
            'resource': resource,
            'action': action,
            'status': status,
            'details': details or {}
        }
        log_entry = json.dumps(event)
        
        with self.lock:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(log_entry + '\n')
                logger.info(f"Audit event logged: {event_type} by {identity} on {resource}")
            except Exception as e:
                logger.error(f"Failed to log audit event: {str(e)}")

class SecurityManager:
    """Central manager for all security operations within the Agentic Framework."""
    
    def __init__(self, secret_key: str = secrets.token_hex(32), 
                 security_level: SecurityLevel = SecurityLevel.MEDIUM):
        self.security_level = security_level
        self.auth_provider = SimpleAuthProvider(secret_key)
        self.authz_policy = RoleBasedPolicy()
        self.encryption_provider = SimpleEncryptionProvider(secret_key.encode('utf-8'))
        self.sandbox = SandboxEnvironment(security_level)
        self.audit_logger = AuditLogger()
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self._initialize_default_roles()
        logger.info(f"Security Manager initialized with security level {security_level}")
    
    def _initialize_default_roles(self):
        """Initialize default roles for common identities."""
        self.authz_policy.assign_role('system:admin', 'admin')
        self.authz_policy.assign_role('agent:default', 'agent')
        self.authz_policy.assign_role('user:default', 'user')
        self.authz_policy.assign_role('guest:anonymous', 'guest')
    
    def authenticate_component(self, credentials: Dict[str, Any]) -> Optional[str]:
        """Authenticate a component and return a token if successful."""
        if self.auth_provider.authenticate(credentials):
            identity = credentials.get('username', credentials.get('api_key', 'anonymous'))
            token = self.auth_provider.generate_token(identity)
            with self.lock:
                self.active_sessions[token] = {
                    'identity': identity,
                    'login_time': time.time(),
                    'last_activity': time.time()
                }
            self.audit_logger.log_event('authentication', identity, 'system', 'login', 'success')
            return token
        self.audit_logger.log_event('authentication', 'unknown', 'system', 'login', 'failure', 
                                   {'reason': 'invalid credentials'})
        return None
    
    def validate_session(self, token: str) -> bool:
        """Validate an active session token."""
        if token not in self.active_sessions:
            return False
        if not self.auth_provider.validate_token(token):
            with self.lock:
                if token in self.active_sessions:
                    identity = self.active_sessions[token]['identity']
                    del self.active_sessions[token]
                    self.audit_logger.log_event('session', identity, 'system', 'logout', 'expired')
            return False
        with self.lock:
            self.active_sessions[token]['last_activity'] = time.time()
        return True
    
    def check_access(self, token: str, resource: str, action: str, 
                    context: Optional[Dict[str, Any]] = None) -> bool:
        """Check if the token holder has access to perform the action on the resource."""
        if not self.validate_session(token):
            self.audit_logger.log_event('authorization', 'unknown', resource, action, 'failure', 
                                      {'reason': 'invalid session'})
            return False
        
        identity = self.active_sessions[token]['identity']
        if self.authz_policy.can_access(identity, resource, action, context):
            self.audit_logger.log_event('authorization', identity, resource, action, 'success', context)
            return True
        self.audit_logger.log_event('authorization', identity, resource, action, 'failure', 
                                  {'reason': 'policy denied'})
        return False
    
    def secure_data(self, data: bytes) -> bytes:
        """Encrypt sensitive data."""
        try:
            encrypted = self.encryption_provider.encrypt(data)
            self.audit_logger.log_event('encryption', 'system', 'data', 'encrypt', 'success')
            return encrypted
        except Exception as e:
            self.audit_logger.log_event('encryption', 'system', 'data', 'encrypt', 'failure', 
                                      {'error': str(e)})
            raise SecurityError(f"Encryption failed: {str(e)}")
    
    def access_secure_data(self, encrypted_data: bytes) -> bytes:
        """Decrypt sensitive data."""
        try:
            decrypted = self.encryption_provider.decrypt(encrypted_data)
            self.audit_logger.log_event('encryption', 'system', 'data', 'decrypt', 'success')
            return decrypted
        except Exception as e:
            self.audit_logger.log_event('encryption', 'system', 'data', 'decrypt', 'failure', 
                                      {'error': str(e)})
            raise SecurityError(f"Decryption failed: {str(e)}")
    
    def execute_in_sandbox(self, token: str, operation: str, payload: Any, 
                          resource: str = "sandbox") -> Any:
        """Execute an operation in a sandboxed environment if authorized."""
        if not self.check_access(token, resource, 'execute'):
            raise SecurityError(f"Access denied for sandbox execution of {operation}")
        try:
            result = self.sandbox.execute(operation, payload)
            identity = self.active_sessions.get(token, {}).get('identity', 'unknown')
            self.audit_logger.log_event('sandbox', identity, resource, operation, 'success')
            return result
        except SecurityError as e:
            identity = self.active_sessions.get(token, {}).get('identity', 'unknown')
            self.audit_logger.log_event('sandbox', identity, resource, operation, 'failure', 
                                      {'error': str(e)})
            raise
    
    def logout(self, token: str):
        """Log out a session and invalidate the token."""
        if token in self.active_sessions:
            identity = self.active_sessions[token]['identity']
            with self.lock:
                del self.active_sessions[token]
            self.audit_logger.log_event('session', identity, 'system', 'logout', 'success')
    
    def set_security_level(self, level: SecurityLevel):
        """Update the security level of the framework."""
        self.security_level = level
        self.sandbox = SandboxEnvironment(level)
        self.audit_logger.log_event('configuration', 'system', 'security', 'update_level', 'success', 
                                  {'new_level': level.name})
        logger.info(f"Security level updated to {level}")

# Example usage and initialization
if __name__ == "__main__":
    # Initialize security manager with a random secret key
    security_manager = SecurityManager(secret_key=secrets.token_hex(32), 
                                     security_level=SecurityLevel.MEDIUM)
    
    # Simulate agent authentication
    agent_credentials = {'username': 'agent:default', 'password': 'secure_password_123'}
    token = security_manager.authenticate_component(agent_credentials)
    if token:
        print(f"Agent authenticated with token: {token}")
        
        # Check access for a task operation
        if security_manager.check_access(token, "task/123", "write"):
            print("Agent has access to write to task/123")
        
        # Execute a safe operation in sandbox
        try:
            result = security_manager.execute_in_sandbox(token, "read", "test_data")
            print(f"Sandbox execution result: {result}")
        except SecurityError as e:
            print(f"Sandbox execution failed: {e}")
        
        # Encrypt and decrypt data
        sensitive_data = b"Top secret agent data"
        encrypted = security_manager.secure_data(sensitive_data)
        print(f"Encrypted data: {encrypted}")
        decrypted = security_manager.access_secure_data(encrypted)
        print(f"Decrypted data: {decrypted}")
        
        # Logout
        security_manager.logout(token)
        print("Agent logged out")
    else:
        print("Agent authentication failed")
