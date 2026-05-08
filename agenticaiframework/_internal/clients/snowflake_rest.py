"""
Snowflake SQL REST API client - stdlib HTTP fallback for
``snowflake-connector-python``.

Targets the v2 SQL Statements REST API
(https://docs.snowflake.com/en/developer-guide/sql-api/intro), which executes
arbitrary SQL via HTTPS using a JWT access token. JWT generation requires an
RSA private key registered as a Snowflake user public key.

Limitations vs the binary client:
    * Authentication is JWT-only (no SSO browser flow). Use a key-pair user.
    * Async statement polling is implemented; binary streaming is not.
    * Result chunks are downloaded over HTTPS (no Arrow IPC).

This is sufficient for ``SnowflakeSearchTool`` which executes SELECT / DESCRIBE
/ SHOW statements.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .. import http as _http


class SnowflakeError(Exception):
    """Raised on Snowflake REST API failures."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class SnowflakeRESTClient:
    """Snowflake SQL REST API v2 client."""

    def __init__(
        self,
        account: str,
        user: str,
        private_key_pem: Optional[str] = None,
        password: Optional[str] = None,
        warehouse: Optional[str] = None,
        database: Optional[str] = None,
        schema: Optional[str] = "PUBLIC",
        role: Optional[str] = None,
        timeout: float = 60.0,
    ):
        if not (private_key_pem or password):
            raise SnowflakeError(
                "Snowflake REST client requires either ``private_key_pem`` (JWT)"
                " or ``password`` (legacy login-request auth)"
            )
        self.account = account.split(".")[0].upper()
        self.host = f"{account}.snowflakecomputing.com" if "." not in account else account
        self.user = user.upper()
        self.private_key_pem = private_key_pem
        self.password = password
        self.warehouse = warehouse
        self.database = database
        self.schema = schema
        self.role = role
        self.timeout = timeout
        self._session_token: Optional[str] = None
        self._session_token_exp: float = 0.0

    # --------------------------------------------------------------- auth
    def _jwt(self) -> str:
        """Build a Snowflake key-pair JWT (RS256)."""
        if not self.private_key_pem:
            raise SnowflakeError("private_key_pem required for JWT auth")
        try:
            from .. import pem as _pem  # type: ignore

            private_key = _pem.load_rsa_private_key(self.private_key_pem)
        except Exception as exc:
            raise SnowflakeError(
                f"Failed to load RSA private key: {exc}. "
                "Stdlib RSA loader is required."
            ) from exc

        # Compute SHA-256 fingerprint of the matching public key (DER-encoded
        # SubjectPublicKeyInfo) - Snowflake expects ``SHA256:<base64>``
        try:
            pubkey_der = private_key.public_key_der()
        except AttributeError:
            raise SnowflakeError(
                "Private key implementation does not expose ``public_key_der()``"
            )
        fingerprint = "SHA256:" + base64.b64encode(
            hashlib.sha256(pubkey_der).digest()
        ).decode("ascii")
        sub = f"{self.account}.{self.user}"
        iss = f"{sub}.{fingerprint}"

        now = int(time.time())
        header = {"alg": "RS256", "typ": "JWT"}
        payload = {
            "iss": iss,
            "sub": sub,
            "iat": now,
            "exp": now + 3600,
        }
        signing_input = (
            _b64url(json.dumps(header, separators=(",", ":")).encode())
            + "."
            + _b64url(json.dumps(payload, separators=(",", ":")).encode())
        )
        try:
            signature = private_key.sign(signing_input.encode("ascii"), "SHA-256")
        except AttributeError:
            raise SnowflakeError(
                "Private key implementation does not expose ``sign(data, hash)``"
            )
        return signing_input + "." + _b64url(signature)

    def _ensure_token(self) -> str:
        if self._session_token and time.time() < self._session_token_exp - 60:
            return self._session_token
        if self.private_key_pem:
            self._session_token = self._jwt()
            self._session_token_exp = time.time() + 3600
            return self._session_token
        # Password fallback via login-request endpoint
        url = f"https://{self.host}/session/v1/login-request"
        body = {
            "data": {
                "ACCOUNT_NAME": self.account,
                "LOGIN_NAME": self.user,
                "PASSWORD": self.password,
                "CLIENT_APP_ID": "PythonStdlib",
                "CLIENT_APP_VERSION": "1.0",
            }
        }
        resp = _http.request(
            "POST",
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise SnowflakeError(f"login failed: {resp.status_code} {resp.text}")
        token = (resp.json() or {}).get("data", {}).get("token")
        if not token:
            raise SnowflakeError("login-request did not return a token")
        self._session_token = token
        self._session_token_exp = time.time() + 3600
        return self._session_token

    # --------------------------------------------------------------- exec
    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        token = self._ensure_token()
        if self.private_key_pem:
            auth = f"Bearer {token}"
            extra = {"X-Snowflake-Authorization-Token-Type": "KEYPAIR_JWT"}
        else:
            auth = f"Snowflake Token=\"{token}\""
            extra = {}
        headers = {
            "Authorization": auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
            **extra,
        }
        url = f"https://{self.host}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        resp = _http.request(method, url, data=data, headers=headers, timeout=self.timeout)
        if resp.status_code >= 400:
            raise SnowflakeError(f"{method} {path} -> {resp.status_code}: {resp.text}")
        try:
            return resp.json() or {}
        except Exception:
            return {}

    def execute(self, sql: str, bindings: Optional[List[Any]] = None) -> Tuple[List[str], List[Tuple[Any, ...]]]:
        """Execute SQL and return ``(column_names, rows)``."""
        request_id = str(uuid.uuid4())
        body: Dict[str, Any] = {
            "statement": sql,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema,
            "role": self.role,
            "timeout": int(self.timeout),
        }
        if bindings:
            body["bindings"] = {
                str(i + 1): {"type": "TEXT", "value": str(v)}
                for i, v in enumerate(bindings)
            }
        result = self._request(
            "POST",
            f"/api/v2/statements?requestId={request_id}",
            body=body,
        )
        # Async (long-running) statements respond with statementHandle - poll.
        if "statementHandle" in result and "data" not in result:
            handle = result["statementHandle"]
            for _ in range(120):
                time.sleep(1)
                result = self._request("GET", f"/api/v2/statements/{handle}")
                if result.get("code") not in (None, "333334"):  # not "still running"
                    break

        meta = result.get("resultSetMetaData", {}) or {}
        columns = [c.get("name", "") for c in meta.get("rowType", [])]
        raw_rows = result.get("data", []) or []
        rows = [tuple(_decode(v) for v in row) for row in raw_rows]
        return columns, rows


def _decode(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        # SQL REST returns numbers as strings; let callers re-cast as needed
        return value
    return value


# ----------------------------------------------------------------------------
# DB-API 2.0 thin shim - only the ``cursor().execute()`` surface used by the
# Snowflake search tool.
# ----------------------------------------------------------------------------
class _Cursor:
    def __init__(self, client: SnowflakeRESTClient):
        self._client = client
        self.description: Optional[List[Tuple[str, None, None, None, None, None, None]]] = None
        self._rows: List[Tuple[Any, ...]] = []

    def execute(self, sql: str, params: Optional[List[Any]] = None) -> None:
        cols, rows = self._client.execute(sql, list(params or []))
        self.description = [(c, None, None, None, None, None, None) for c in cols]
        self._rows = rows

    def fetchall(self) -> List[Tuple[Any, ...]]:
        out, self._rows = self._rows, []
        return out

    def fetchone(self) -> Optional[Tuple[Any, ...]]:
        return self._rows.pop(0) if self._rows else None

    def close(self) -> None:
        self._rows = []


class DBAPIConnection:
    def __init__(self, **kwargs: Any):
        self._client = SnowflakeRESTClient(**kwargs)

    def cursor(self) -> _Cursor:
        return _Cursor(self._client)

    def close(self) -> None:
        pass


def connect(**kwargs: Any) -> DBAPIConnection:
    """DB-API entry point - signature mirrors ``snowflake.connector.connect``."""
    return DBAPIConnection(**kwargs)


__all__ = ["SnowflakeRESTClient", "SnowflakeError", "DBAPIConnection", "connect"]
