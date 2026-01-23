"""
Enterprise OAuth Provider Module.

OAuth2/OIDC provider with social auth integration,
token management, and consent flows.

Example:
    # Create OAuth provider
    oauth = create_oauth_provider()
    
    # Register client
    client = await oauth.register_client(
        name="My App",
        redirect_uris=["https://app.com/callback"],
    )
    
    # Start authorization
    auth_url = await oauth.authorize(
        client_id=client.client_id,
        redirect_uri="https://app.com/callback",
        scope=["openid", "profile", "email"],
    )
    
    # Exchange code for tokens
    tokens = await oauth.exchange_code(code, client_id, client_secret)
"""

from __future__ import annotations

import base64
import functools
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
    Union,
)
from urllib.parse import urlencode

T = TypeVar('T')


logger = logging.getLogger(__name__)


class OAuthError(Exception):
    """OAuth error."""
    pass


class InvalidClientError(OAuthError):
    """Invalid client."""
    pass


class InvalidGrantError(OAuthError):
    """Invalid grant."""
    pass


class InvalidScopeError(OAuthError):
    """Invalid scope."""
    pass


class UnauthorizedClientError(OAuthError):
    """Unauthorized client."""
    pass


class AccessDeniedError(OAuthError):
    """Access denied."""
    pass


class GrantType(str, Enum):
    """OAuth grant types."""
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    REFRESH_TOKEN = "refresh_token"
    PASSWORD = "password"
    IMPLICIT = "implicit"
    DEVICE_CODE = "urn:ietf:params:oauth:grant-type:device_code"


class ResponseType(str, Enum):
    """Response types."""
    CODE = "code"
    TOKEN = "token"
    ID_TOKEN = "id_token"


class TokenType(str, Enum):
    """Token types."""
    BEARER = "Bearer"
    MAC = "MAC"


class ClientType(str, Enum):
    """Client types."""
    CONFIDENTIAL = "confidential"
    PUBLIC = "public"


@dataclass
class OAuthClient:
    """OAuth client."""
    client_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_secret: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    name: str = ""
    description: str = ""
    client_type: ClientType = ClientType.CONFIDENTIAL
    redirect_uris: List[str] = field(default_factory=list)
    allowed_scopes: Set[str] = field(default_factory=set)
    allowed_grants: Set[GrantType] = field(default_factory=lambda: {
        GrantType.AUTHORIZATION_CODE,
        GrantType.REFRESH_TOKEN,
    })
    logo_uri: Optional[str] = None
    tos_uri: Optional[str] = None
    policy_uri: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorizationCode:
    """Authorization code."""
    code: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    client_id: str = ""
    user_id: str = ""
    redirect_uri: str = ""
    scope: Set[str] = field(default_factory=set)
    code_challenge: Optional[str] = None
    code_challenge_method: str = "S256"
    nonce: Optional[str] = None
    state: Optional[str] = None
    expires_at: datetime = field(
        default_factory=lambda: datetime.utcnow() + timedelta(minutes=10)
    )
    used: bool = False


@dataclass
class AccessToken:
    """Access token."""
    access_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    token_type: TokenType = TokenType.BEARER
    client_id: str = ""
    user_id: Optional[str] = None
    scope: Set[str] = field(default_factory=set)
    expires_at: datetime = field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=1)
    )
    created_at: datetime = field(default_factory=datetime.utcnow)
    revoked: bool = False


@dataclass
class RefreshToken:
    """Refresh token."""
    refresh_token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    access_token: str = ""
    client_id: str = ""
    user_id: Optional[str] = None
    scope: Set[str] = field(default_factory=set)
    expires_at: datetime = field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=30)
    )
    created_at: datetime = field(default_factory=datetime.utcnow)
    revoked: bool = False


@dataclass
class TokenResponse:
    """Token response."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    scope: str = ""
    id_token: Optional[str] = None


@dataclass
class UserInfo:
    """OIDC user info."""
    sub: str
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    email: Optional[str] = None
    email_verified: bool = False
    picture: Optional[str] = None
    locale: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceCode:
    """Device authorization code."""
    device_code: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    user_code: str = field(default_factory=lambda: secrets.token_urlsafe(8).upper()[:8])
    client_id: str = ""
    scope: Set[str] = field(default_factory=set)
    verification_uri: str = ""
    expires_at: datetime = field(
        default_factory=lambda: datetime.utcnow() + timedelta(minutes=15)
    )
    interval: int = 5
    user_id: Optional[str] = None
    authorized: bool = False


# Token storage
class TokenStore(ABC):
    """Abstract token store."""
    
    @abstractmethod
    async def save_client(self, client: OAuthClient) -> None:
        pass
    
    @abstractmethod
    async def get_client(self, client_id: str) -> Optional[OAuthClient]:
        pass
    
    @abstractmethod
    async def save_code(self, code: AuthorizationCode) -> None:
        pass
    
    @abstractmethod
    async def get_code(self, code: str) -> Optional[AuthorizationCode]:
        pass
    
    @abstractmethod
    async def invalidate_code(self, code: str) -> None:
        pass
    
    @abstractmethod
    async def save_access_token(self, token: AccessToken) -> None:
        pass
    
    @abstractmethod
    async def get_access_token(self, token: str) -> Optional[AccessToken]:
        pass
    
    @abstractmethod
    async def revoke_access_token(self, token: str) -> None:
        pass
    
    @abstractmethod
    async def save_refresh_token(self, token: RefreshToken) -> None:
        pass
    
    @abstractmethod
    async def get_refresh_token(self, token: str) -> Optional[RefreshToken]:
        pass
    
    @abstractmethod
    async def revoke_refresh_token(self, token: str) -> None:
        pass


class InMemoryTokenStore(TokenStore):
    """In-memory token store."""
    
    def __init__(self):
        self._clients: Dict[str, OAuthClient] = {}
        self._codes: Dict[str, AuthorizationCode] = {}
        self._access_tokens: Dict[str, AccessToken] = {}
        self._refresh_tokens: Dict[str, RefreshToken] = {}
    
    async def save_client(self, client: OAuthClient) -> None:
        self._clients[client.client_id] = client
    
    async def get_client(self, client_id: str) -> Optional[OAuthClient]:
        return self._clients.get(client_id)
    
    async def save_code(self, code: AuthorizationCode) -> None:
        self._codes[code.code] = code
    
    async def get_code(self, code: str) -> Optional[AuthorizationCode]:
        return self._codes.get(code)
    
    async def invalidate_code(self, code: str) -> None:
        if code in self._codes:
            self._codes[code].used = True
    
    async def save_access_token(self, token: AccessToken) -> None:
        self._access_tokens[token.access_token] = token
    
    async def get_access_token(self, token: str) -> Optional[AccessToken]:
        return self._access_tokens.get(token)
    
    async def revoke_access_token(self, token: str) -> None:
        if token in self._access_tokens:
            self._access_tokens[token].revoked = True
    
    async def save_refresh_token(self, token: RefreshToken) -> None:
        self._refresh_tokens[token.refresh_token] = token
    
    async def get_refresh_token(self, token: str) -> Optional[RefreshToken]:
        return self._refresh_tokens.get(token)
    
    async def revoke_refresh_token(self, token: str) -> None:
        if token in self._refresh_tokens:
            self._refresh_tokens[token].revoked = True


class OAuthProvider:
    """
    OAuth2/OIDC provider.
    """
    
    def __init__(
        self,
        issuer: str = "http://localhost",
        store: Optional[TokenStore] = None,
        access_token_ttl: int = 3600,
        refresh_token_ttl: int = 86400 * 30,
        code_ttl: int = 600,
    ):
        self._issuer = issuer
        self._store = store or InMemoryTokenStore()
        self._access_token_ttl = access_token_ttl
        self._refresh_token_ttl = refresh_token_ttl
        self._code_ttl = code_ttl
        self._user_validator: Optional[Callable] = None
    
    def set_user_validator(
        self,
        validator: Callable[[str, str], Optional[UserInfo]],
    ) -> None:
        """Set user validator for password grant."""
        self._user_validator = validator
    
    async def register_client(
        self,
        name: str,
        redirect_uris: List[str],
        client_type: ClientType = ClientType.CONFIDENTIAL,
        allowed_scopes: Optional[Set[str]] = None,
        allowed_grants: Optional[Set[GrantType]] = None,
        **kwargs,
    ) -> OAuthClient:
        """
        Register OAuth client.
        
        Args:
            name: Client name
            redirect_uris: Redirect URIs
            client_type: Client type
            allowed_scopes: Allowed scopes
            allowed_grants: Allowed grants
            
        Returns:
            Registered client
        """
        client = OAuthClient(
            name=name,
            client_type=client_type,
            redirect_uris=redirect_uris,
            allowed_scopes=allowed_scopes or {"openid", "profile", "email"},
            allowed_grants=allowed_grants or {
                GrantType.AUTHORIZATION_CODE,
                GrantType.REFRESH_TOKEN,
            },
            **kwargs,
        )
        
        await self._store.save_client(client)
        return client
    
    async def get_client(self, client_id: str) -> Optional[OAuthClient]:
        """Get client by ID."""
        return await self._store.get_client(client_id)
    
    async def authorize(
        self,
        client_id: str,
        redirect_uri: str,
        response_type: str = "code",
        scope: Optional[List[str]] = None,
        state: Optional[str] = None,
        nonce: Optional[str] = None,
        code_challenge: Optional[str] = None,
        code_challenge_method: str = "S256",
    ) -> str:
        """
        Build authorization URL.
        
        Args:
            client_id: Client ID
            redirect_uri: Redirect URI
            response_type: Response type
            scope: Requested scopes
            state: State parameter
            nonce: Nonce for OIDC
            code_challenge: PKCE code challenge
            code_challenge_method: PKCE method
            
        Returns:
            Authorization URL
        """
        client = await self.get_client(client_id)
        if not client:
            raise InvalidClientError("Client not found")
        
        if redirect_uri not in client.redirect_uris:
            raise InvalidClientError("Invalid redirect URI")
        
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": response_type,
            "scope": " ".join(scope or ["openid"]),
        }
        
        if state:
            params["state"] = state
        if nonce:
            params["nonce"] = nonce
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = code_challenge_method
        
        return f"{self._issuer}/authorize?{urlencode(params)}"
    
    async def create_authorization_code(
        self,
        client_id: str,
        user_id: str,
        redirect_uri: str,
        scope: Set[str],
        code_challenge: Optional[str] = None,
        code_challenge_method: str = "S256",
        nonce: Optional[str] = None,
        state: Optional[str] = None,
    ) -> AuthorizationCode:
        """
        Create authorization code.
        
        Args:
            client_id: Client ID
            user_id: User ID
            redirect_uri: Redirect URI
            scope: Granted scopes
            code_challenge: PKCE challenge
            code_challenge_method: PKCE method
            nonce: OIDC nonce
            state: State parameter
            
        Returns:
            Authorization code
        """
        client = await self.get_client(client_id)
        if not client:
            raise InvalidClientError("Client not found")
        
        if redirect_uri not in client.redirect_uris:
            raise InvalidClientError("Invalid redirect URI")
        
        # Validate scopes
        invalid_scopes = scope - client.allowed_scopes
        if invalid_scopes:
            raise InvalidScopeError(f"Invalid scopes: {invalid_scopes}")
        
        code = AuthorizationCode(
            client_id=client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            nonce=nonce,
            state=state,
            expires_at=datetime.utcnow() + timedelta(seconds=self._code_ttl),
        )
        
        await self._store.save_code(code)
        return code
    
    async def exchange_code(
        self,
        code: str,
        client_id: str,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        code_verifier: Optional[str] = None,
    ) -> TokenResponse:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code
            client_id: Client ID
            client_secret: Client secret
            redirect_uri: Redirect URI
            code_verifier: PKCE verifier
            
        Returns:
            Token response
        """
        auth_code = await self._store.get_code(code)
        if not auth_code:
            raise InvalidGrantError("Invalid authorization code")
        
        if auth_code.used:
            raise InvalidGrantError("Authorization code already used")
        
        if datetime.utcnow() > auth_code.expires_at:
            raise InvalidGrantError("Authorization code expired")
        
        if auth_code.client_id != client_id:
            raise InvalidClientError("Client mismatch")
        
        if redirect_uri and auth_code.redirect_uri != redirect_uri:
            raise InvalidGrantError("Redirect URI mismatch")
        
        # Validate client
        client = await self.get_client(client_id)
        if not client:
            raise InvalidClientError("Client not found")
        
        # Validate secret for confidential clients
        if client.client_type == ClientType.CONFIDENTIAL:
            if not client_secret or not secrets.compare_digest(
                client_secret, client.client_secret
            ):
                raise InvalidClientError("Invalid client credentials")
        
        # Validate PKCE
        if auth_code.code_challenge:
            if not code_verifier:
                raise InvalidGrantError("Code verifier required")
            
            if not self._verify_code_challenge(
                code_verifier,
                auth_code.code_challenge,
                auth_code.code_challenge_method,
            ):
                raise InvalidGrantError("Invalid code verifier")
        
        # Mark code as used
        await self._store.invalidate_code(code)
        
        # Create tokens
        return await self._create_tokens(
            client_id=client_id,
            user_id=auth_code.user_id,
            scope=auth_code.scope,
            nonce=auth_code.nonce,
        )
    
    async def refresh_tokens(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: Optional[str] = None,
        scope: Optional[Set[str]] = None,
    ) -> TokenResponse:
        """
        Refresh access token.
        
        Args:
            refresh_token: Refresh token
            client_id: Client ID
            client_secret: Client secret
            scope: Requested scopes (subset)
            
        Returns:
            Token response
        """
        token = await self._store.get_refresh_token(refresh_token)
        if not token:
            raise InvalidGrantError("Invalid refresh token")
        
        if token.revoked:
            raise InvalidGrantError("Refresh token revoked")
        
        if datetime.utcnow() > token.expires_at:
            raise InvalidGrantError("Refresh token expired")
        
        if token.client_id != client_id:
            raise InvalidClientError("Client mismatch")
        
        # Validate client
        client = await self.get_client(client_id)
        if not client:
            raise InvalidClientError("Client not found")
        
        if client.client_type == ClientType.CONFIDENTIAL:
            if not client_secret or not secrets.compare_digest(
                client_secret, client.client_secret
            ):
                raise InvalidClientError("Invalid client credentials")
        
        # Validate scope
        requested_scope = scope or token.scope
        if not requested_scope.issubset(token.scope):
            raise InvalidScopeError("Cannot expand scope")
        
        # Revoke old tokens
        await self._store.revoke_access_token(token.access_token)
        await self._store.revoke_refresh_token(refresh_token)
        
        # Create new tokens
        return await self._create_tokens(
            client_id=client_id,
            user_id=token.user_id,
            scope=requested_scope,
        )
    
    async def client_credentials(
        self,
        client_id: str,
        client_secret: str,
        scope: Optional[Set[str]] = None,
    ) -> TokenResponse:
        """
        Client credentials grant.
        
        Args:
            client_id: Client ID
            client_secret: Client secret
            scope: Requested scopes
            
        Returns:
            Token response
        """
        client = await self.get_client(client_id)
        if not client:
            raise InvalidClientError("Client not found")
        
        if GrantType.CLIENT_CREDENTIALS not in client.allowed_grants:
            raise UnauthorizedClientError("Grant type not allowed")
        
        if not secrets.compare_digest(client_secret, client.client_secret):
            raise InvalidClientError("Invalid client credentials")
        
        # Validate scopes
        requested_scope = scope or set()
        if not requested_scope.issubset(client.allowed_scopes):
            raise InvalidScopeError("Invalid scope")
        
        # Create access token only
        access_token = AccessToken(
            client_id=client_id,
            scope=requested_scope,
            expires_at=datetime.utcnow() + timedelta(seconds=self._access_token_ttl),
        )
        
        await self._store.save_access_token(access_token)
        
        return TokenResponse(
            access_token=access_token.access_token,
            token_type="Bearer",
            expires_in=self._access_token_ttl,
            scope=" ".join(requested_scope),
        )
    
    async def validate_token(
        self,
        token: str,
    ) -> Optional[AccessToken]:
        """
        Validate access token.
        
        Args:
            token: Access token
            
        Returns:
            Token info if valid
        """
        access_token = await self._store.get_access_token(token)
        if not access_token:
            return None
        
        if access_token.revoked:
            return None
        
        if datetime.utcnow() > access_token.expires_at:
            return None
        
        return access_token
    
    async def revoke_token(
        self,
        token: str,
        token_type_hint: str = "access_token",
    ) -> bool:
        """
        Revoke token.
        
        Args:
            token: Token to revoke
            token_type_hint: Token type hint
            
        Returns:
            Success status
        """
        if token_type_hint == "refresh_token":
            await self._store.revoke_refresh_token(token)
        else:
            await self._store.revoke_access_token(token)
        
        return True
    
    async def _create_tokens(
        self,
        client_id: str,
        user_id: Optional[str],
        scope: Set[str],
        nonce: Optional[str] = None,
    ) -> TokenResponse:
        """Create access and refresh tokens."""
        access_token = AccessToken(
            client_id=client_id,
            user_id=user_id,
            scope=scope,
            expires_at=datetime.utcnow() + timedelta(seconds=self._access_token_ttl),
        )
        
        refresh_token = RefreshToken(
            access_token=access_token.access_token,
            client_id=client_id,
            user_id=user_id,
            scope=scope,
            expires_at=datetime.utcnow() + timedelta(seconds=self._refresh_token_ttl),
        )
        
        await self._store.save_access_token(access_token)
        await self._store.save_refresh_token(refresh_token)
        
        response = TokenResponse(
            access_token=access_token.access_token,
            token_type="Bearer",
            expires_in=self._access_token_ttl,
            refresh_token=refresh_token.refresh_token,
            scope=" ".join(scope),
        )
        
        # Add ID token for OpenID Connect
        if "openid" in scope:
            response.id_token = self._create_id_token(
                client_id=client_id,
                user_id=user_id,
                nonce=nonce,
            )
        
        return response
    
    def _create_id_token(
        self,
        client_id: str,
        user_id: Optional[str],
        nonce: Optional[str] = None,
    ) -> str:
        """Create ID token (simplified)."""
        now = int(time.time())
        
        payload = {
            "iss": self._issuer,
            "sub": user_id,
            "aud": client_id,
            "exp": now + self._access_token_ttl,
            "iat": now,
        }
        
        if nonce:
            payload["nonce"] = nonce
        
        # Simplified - in production use proper JWT library
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        ).rstrip(b"=")
        
        body = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).rstrip(b"=")
        
        signature = base64.urlsafe_b64encode(
            b"mock_signature"
        ).rstrip(b"=")
        
        return f"{header.decode()}.{body.decode()}.{signature.decode()}"
    
    def _verify_code_challenge(
        self,
        verifier: str,
        challenge: str,
        method: str,
    ) -> bool:
        """Verify PKCE code challenge."""
        if method == "plain":
            return verifier == challenge
        
        # S256
        digest = hashlib.sha256(verifier.encode()).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return secrets.compare_digest(computed, challenge)
    
    def get_discovery_document(self) -> Dict[str, Any]:
        """Get OIDC discovery document."""
        return {
            "issuer": self._issuer,
            "authorization_endpoint": f"{self._issuer}/authorize",
            "token_endpoint": f"{self._issuer}/token",
            "userinfo_endpoint": f"{self._issuer}/userinfo",
            "jwks_uri": f"{self._issuer}/.well-known/jwks.json",
            "revocation_endpoint": f"{self._issuer}/revoke",
            "introspection_endpoint": f"{self._issuer}/introspect",
            "response_types_supported": ["code", "token", "id_token"],
            "grant_types_supported": [gt.value for gt in GrantType],
            "token_endpoint_auth_methods_supported": [
                "client_secret_basic",
                "client_secret_post",
            ],
            "code_challenge_methods_supported": ["plain", "S256"],
            "scopes_supported": ["openid", "profile", "email", "offline_access"],
        }


# Factory functions
def create_oauth_provider(
    issuer: str = "http://localhost",
    store: Optional[TokenStore] = None,
    **kwargs,
) -> OAuthProvider:
    """Create OAuth provider."""
    return OAuthProvider(issuer=issuer, store=store, **kwargs)


def create_token_store() -> TokenStore:
    """Create token store."""
    return InMemoryTokenStore()


def create_oauth_client(
    name: str,
    redirect_uris: List[str],
    **kwargs,
) -> OAuthClient:
    """Create OAuth client."""
    return OAuthClient(name=name, redirect_uris=redirect_uris, **kwargs)


__all__ = [
    # Exceptions
    "OAuthError",
    "InvalidClientError",
    "InvalidGrantError",
    "InvalidScopeError",
    "UnauthorizedClientError",
    "AccessDeniedError",
    # Enums
    "GrantType",
    "ResponseType",
    "TokenType",
    "ClientType",
    # Data classes
    "OAuthClient",
    "AuthorizationCode",
    "AccessToken",
    "RefreshToken",
    "TokenResponse",
    "UserInfo",
    "DeviceCode",
    # Store
    "TokenStore",
    "InMemoryTokenStore",
    # Provider
    "OAuthProvider",
    # Factory functions
    "create_oauth_provider",
    "create_token_store",
    "create_oauth_client",
]
