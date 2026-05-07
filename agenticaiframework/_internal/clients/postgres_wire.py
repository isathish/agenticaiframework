"""Pure-Python PostgreSQL wire-protocol client (stdlib-only, v3 protocol).

Implements the subset needed by ``agenticaiframework.tools.database.sql_tools``:

* Startup: SSL request (best-effort) + StartupMessage
* Authentication: cleartext, MD5, SASL SCRAM-SHA-256
* Simple query (`Query`) — used by ``execute(sql)`` / ``fetchall()``
* Extended query (`Parse`/`Bind`/`Execute`) — used by ``execute(sql, params)``
* Connection close

References:
* https://www.postgresql.org/docs/current/protocol.html
* https://www.postgresql.org/docs/current/protocol-message-formats.html

This is **not** a full driver — there's no async, no COPY, no notifications, and
type decoding is text-mode only (no binary). It is sufficient for typical CRUD
queries against a Postgres database when ``psycopg2`` is unavailable.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import socket
import ssl
import struct
from base64 import b64decode, b64encode
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


class PostgresError(Exception):
    """Server-reported error (ErrorResponse 'E')."""

    def __init__(self, fields: Dict[str, str]) -> None:
        msg = fields.get("M", "Unknown error")
        super().__init__(msg)
        self.fields = fields


class ProtocolError(Exception):
    """Client-side protocol violation."""


# ---------------------------------------------------------------------------
# Message framing helpers
# ---------------------------------------------------------------------------

def _pack_message(tag: bytes, body: bytes) -> bytes:
    if tag:
        return tag + struct.pack(">I", 4 + len(body)) + body
    return struct.pack(">I", 4 + len(body)) + body


def _cstring(s: str) -> bytes:
    return s.encode("utf-8") + b"\x00"


# ---------------------------------------------------------------------------
# SCRAM-SHA-256
# ---------------------------------------------------------------------------

def _scram_client_first(username: str, nonce: bytes) -> Tuple[bytes, bytes]:
    client_nonce = b64encode(nonce).decode("ascii")
    bare = f"n={username},r={client_nonce}"
    initial = "n,," + bare  # GS2 header + bare
    return initial.encode("utf-8"), bare.encode("utf-8")


def _scram_parse(payload: bytes) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for piece in payload.decode("utf-8").split(","):
        if "=" in piece:
            k, v = piece.split("=", 1)
            out[k] = v
    return out


def _scram_client_proof(
    password: str,
    server_first: bytes,
    client_first_bare: bytes,
) -> Tuple[bytes, bytes, bytes]:
    parsed = _scram_parse(server_first)
    server_nonce = parsed["r"]
    salt = b64decode(parsed["s"])
    iterations = int(parsed["i"])

    salted_password = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    client_key = hmac.new(salted_password, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()

    channel_binding = b64encode(b"n,,").decode("ascii")
    client_final_no_proof = f"c={channel_binding},r={server_nonce}".encode("utf-8")

    auth_message = client_first_bare + b"," + server_first + b"," + client_final_no_proof
    client_signature = hmac.new(stored_key, auth_message, hashlib.sha256).digest()
    client_proof = bytes(a ^ b for a, b in zip(client_key, client_signature))
    proof_b64 = b64encode(client_proof).decode("ascii")

    server_key = hmac.new(salted_password, b"Server Key", hashlib.sha256).digest()
    server_signature = hmac.new(server_key, auth_message, hashlib.sha256).digest()

    final_message = client_final_no_proof + b",p=" + proof_b64.encode("ascii")
    return final_message, server_signature, auth_message


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

@dataclass
class _Field:
    name: str
    type_oid: int
    format_code: int = 0  # 0 = text, 1 = binary


@dataclass
class Connection:
    host: str = "localhost"
    port: int = 5432
    database: str = "postgres"
    user: str = "postgres"
    password: str = ""
    sslmode: str = "prefer"  # 'disable' | 'prefer' | 'require'
    application_name: str = "agenticaiframework"
    timeout: float = 30.0

    _sock: Optional[socket.socket] = field(default=None, init=False, repr=False)
    _server_signature: Optional[bytes] = field(default=None, init=False, repr=False)

    # -- connection lifecycle ---------------------------------------

    def connect(self) -> None:
        if self._sock is not None:
            return
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(self.timeout)

        # Try SSL
        if self.sslmode in ("prefer", "require"):
            sock.sendall(struct.pack(">II", 8, 80877103))  # SSLRequest magic
            resp = sock.recv(1)
            if resp == b"S":
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                sock = ctx.wrap_socket(sock, server_hostname=self.host)
            elif self.sslmode == "require":
                raise ProtocolError("Server refused SSL but sslmode=require")

        self._sock = sock
        self._send_startup()
        self._authenticate()
        self._wait_for_ready()

    def close(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.sendall(_pack_message(b"X", b""))
        except OSError:
            pass
        try:
            self._sock.close()
        finally:
            self._sock = None

    # -- low-level send/recv ----------------------------------------

    def _send(self, data: bytes) -> None:
        assert self._sock is not None
        self._sock.sendall(data)

    def _recv(self, n: int) -> bytes:
        assert self._sock is not None
        out = bytearray()
        while len(out) < n:
            chunk = self._sock.recv(n - len(out))
            if not chunk:
                raise ConnectionError("PostgreSQL connection closed")
            out.extend(chunk)
        return bytes(out)

    def _read_message(self) -> Tuple[bytes, bytes]:
        tag = self._recv(1)
        length = struct.unpack(">I", self._recv(4))[0]
        body = self._recv(length - 4) if length > 4 else b""
        if tag == b"E":
            raise PostgresError(_parse_error_fields(body))
        return tag, body

    # -- startup + auth ---------------------------------------------

    def _send_startup(self) -> None:
        params = (
            _cstring("user") + _cstring(self.user)
            + _cstring("database") + _cstring(self.database)
            + _cstring("application_name") + _cstring(self.application_name)
            + _cstring("client_encoding") + _cstring("UTF8")
            + b"\x00"
        )
        body = struct.pack(">I", 196608) + params  # protocol version 3.0
        self._send(struct.pack(">I", 4 + len(body)) + body)

    def _authenticate(self) -> None:
        while True:
            tag, body = self._read_message()
            if tag != b"R":
                raise ProtocolError(f"Unexpected message during auth: {tag!r}")
            auth_type = struct.unpack(">I", body[:4])[0]
            if auth_type == 0:  # AuthenticationOk
                return
            if auth_type == 3:  # cleartext
                self._send(_pack_message(b"p", _cstring(self.password)))
                continue
            if auth_type == 5:  # MD5
                salt = body[4:8]
                token = (
                    "md5"
                    + hashlib.md5(
                        hashlib.md5((self.password + self.user).encode()).hexdigest().encode()
                        + salt
                    ).hexdigest()
                )
                self._send(_pack_message(b"p", _cstring(token)))
                continue
            if auth_type == 10:  # SASL
                # Body: list of mechanisms, NUL-terminated, ending with empty
                mechs = body[4:].split(b"\x00")
                if b"SCRAM-SHA-256" not in mechs:
                    raise ProtocolError("Server requires unsupported SASL mechanisms")
                client_initial, client_first_bare = _scram_client_first(self.user, secrets.token_bytes(18))
                msg = _cstring("SCRAM-SHA-256") + struct.pack(">I", len(client_initial)) + client_initial
                self._send(_pack_message(b"p", msg))
                # Expect SASLContinue (R, type=11)
                tag, body = self._read_message()
                if tag != b"R" or struct.unpack(">I", body[:4])[0] != 11:
                    raise ProtocolError("SASL: expected continuation")
                server_first = body[4:]
                final_msg, server_signature, _ = _scram_client_proof(
                    self.password, server_first, client_first_bare
                )
                self._server_signature = server_signature
                self._send(_pack_message(b"p", final_msg))
                # Expect SASLFinal (R, type=12)
                tag, body = self._read_message()
                if tag != b"R" or struct.unpack(">I", body[:4])[0] != 12:
                    raise ProtocolError("SASL: expected final")
                # Verify server signature
                parsed = _scram_parse(body[4:])
                if "v" in parsed:
                    expected = b64encode(server_signature).decode("ascii")
                    if not hmac.compare_digest(parsed["v"], expected):
                        raise ProtocolError("SASL: server signature mismatch")
                continue
            raise ProtocolError(f"Unsupported auth type: {auth_type}")

    def _wait_for_ready(self) -> None:
        while True:
            tag, _body = self._read_message()
            if tag == b"Z":  # ReadyForQuery
                return
            # Skip ParameterStatus (S), BackendKeyData (K), NoticeResponse (N)

    # -- query execution --------------------------------------------

    def execute(
        self,
        sql: str,
        params: Optional[Iterable[Any]] = None,
    ) -> Tuple[List[str], List[List[Any]]]:
        """Execute a query and return (column_names, rows)."""
        self.connect()
        if params is None:
            return self._simple_query(sql)
        return self._extended_query(sql, list(params))

    def _simple_query(self, sql: str) -> Tuple[List[str], List[List[Any]]]:
        self._send(_pack_message(b"Q", _cstring(sql)))
        return self._read_query_result()

    def _extended_query(self, sql: str, params: List[Any]) -> Tuple[List[str], List[List[Any]]]:
        # Parse + Bind + Describe + Execute + Sync
        statement_name = b""
        portal_name = b""

        parse_body = (
            statement_name + b"\x00"
            + _cstring(sql)
            + struct.pack(">H", 0)  # 0 parameter types (server infers)
        )
        bind_body = (
            portal_name + b"\x00"
            + statement_name + b"\x00"
            + struct.pack(">H", 0)  # 0 format codes => all text
            + struct.pack(">H", len(params))
        )
        for p in params:
            if p is None:
                bind_body += struct.pack(">i", -1)
            else:
                if isinstance(p, bool):
                    encoded = (b"t" if p else b"f")
                elif isinstance(p, (bytes, bytearray)):
                    encoded = b"\\x" + bytes(p).hex().encode("ascii")
                else:
                    encoded = str(p).encode("utf-8")
                bind_body += struct.pack(">i", len(encoded)) + encoded
        bind_body += struct.pack(">H", 0)  # all text result format

        describe_body = b"P" + portal_name + b"\x00"
        execute_body = portal_name + b"\x00" + struct.pack(">i", 0)
        sync_body = b""

        msgs = (
            _pack_message(b"P", parse_body)
            + _pack_message(b"B", bind_body)
            + _pack_message(b"D", describe_body)
            + _pack_message(b"E", execute_body)
            + _pack_message(b"S", sync_body)
        )
        self._send(msgs)
        return self._read_query_result()

    def _read_query_result(self) -> Tuple[List[str], List[List[Any]]]:
        columns: List[str] = []
        rows: List[List[Any]] = []
        while True:
            tag, body = self._read_message()
            if tag == b"T":  # RowDescription
                columns = _parse_row_description(body)
            elif tag == b"D":  # DataRow
                rows.append(_parse_data_row(body))
            elif tag == b"C":  # CommandComplete
                pass
            elif tag in (b"1", b"2", b"3", b"n", b"s", b"t"):
                # ParseComplete, BindComplete, CloseComplete, NoData,
                # PortalSuspended, ParameterDescription — ignore
                pass
            elif tag == b"Z":  # ReadyForQuery
                return columns, rows
            elif tag == b"N":  # NoticeResponse — ignore
                pass
            elif tag == b"I":  # EmptyQueryResponse
                pass
            else:
                # Unknown but non-fatal — skip
                pass


# ---------------------------------------------------------------------------
# Message body parsers
# ---------------------------------------------------------------------------

def _parse_error_fields(body: bytes) -> Dict[str, str]:
    out: Dict[str, str] = {}
    i = 0
    while i < len(body):
        code = body[i:i + 1]
        if code == b"\x00":
            break
        end = body.index(b"\x00", i + 1)
        out[code.decode("ascii", "replace")] = body[i + 1 : end].decode("utf-8", "replace")
        i = end + 1
    return out


def _parse_row_description(body: bytes) -> List[str]:
    n = struct.unpack(">H", body[:2])[0]
    columns: List[str] = []
    i = 2
    for _ in range(n):
        end = body.index(b"\x00", i)
        name = body[i:end].decode("utf-8", "replace")
        # Skip remaining 18 bytes per field: tableOID(4)+colAttrNum(2)+typeOID(4)+typeSize(2)+typeMod(4)+formatCode(2)
        i = end + 1 + 18
        columns.append(name)
    return columns


def _parse_data_row(body: bytes) -> List[Any]:
    n = struct.unpack(">H", body[:2])[0]
    out: List[Any] = []
    i = 2
    for _ in range(n):
        length = struct.unpack(">i", body[i : i + 4])[0]
        i += 4
        if length == -1:
            out.append(None)
        else:
            out.append(body[i : i + length].decode("utf-8", "replace"))
            i += length
    return out


def connect(**kwargs) -> Connection:
    """``psycopg2.connect``-like helper."""
    conn = Connection(**kwargs)
    conn.connect()
    return conn


# ---------------------------------------------------------------------------
# DB-API 2.0 thin wrapper
# ---------------------------------------------------------------------------

class _DBAPICursor:
    """Minimal DB-API 2.0 cursor over :class:`Connection`."""

    def __init__(self, connection: "DBAPIConnection") -> None:
        self._conn = connection
        self.description: Optional[List[Tuple[str, ...]]] = None
        self._rows: List[List[Any]] = []
        self._idx = 0
        self.rowcount = -1

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> None:
        # Translate %s placeholders → $1, $2, ... for extended protocol.
        if params is None:
            cols, rows = self._conn._wire.execute(sql)
        else:
            translated = _translate_placeholders(sql)
            cols, rows = self._conn._wire.execute(translated, list(params))
        self.description = [(c,) for c in cols]
        self._rows = rows
        self._idx = 0
        self.rowcount = len(rows)

    def executemany(self, sql: str, seq_of_params: Iterable[Iterable[Any]]) -> None:
        for params in seq_of_params:
            self.execute(sql, params)

    def fetchall(self) -> List[List[Any]]:
        result = self._rows[self._idx :]
        self._idx = len(self._rows)
        return result

    def fetchone(self) -> Optional[List[Any]]:
        if self._idx >= len(self._rows):
            return None
        row = self._rows[self._idx]
        self._idx += 1
        return row

    def fetchmany(self, size: int = 1) -> List[List[Any]]:
        end = min(self._idx + size, len(self._rows))
        result = self._rows[self._idx : end]
        self._idx = end
        return result

    def close(self) -> None:
        self._rows = []
        self.description = None

    def __iter__(self):
        return iter(self.fetchall())


class DBAPIConnection:
    """psycopg2-shaped connection wrapping :class:`Connection`."""

    def __init__(self, **kwargs) -> None:
        self._wire = Connection(**kwargs)
        self._wire.connect()
        self._closed = False

    def cursor(self) -> _DBAPICursor:
        if self._closed:
            raise ProtocolError("Connection is closed")
        return _DBAPICursor(self)

    def commit(self) -> None:
        # Server in autocommit mode by default for simple queries.
        pass

    def rollback(self) -> None:
        try:
            self._wire.execute("ROLLBACK")
        except PostgresError:
            pass

    def close(self) -> None:
        if not self._closed:
            self._wire.close()
            self._closed = True


def _translate_placeholders(sql: str) -> str:
    """Convert ``%s`` placeholders (psycopg2 style) to PG ``$1, $2, ...``."""
    out: List[str] = []
    i = 0
    n = 0
    in_single = False
    in_double = False
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
        elif ch == "%" and not in_single and not in_double and i + 1 < len(sql) and sql[i + 1] == "s":
            n += 1
            out.append(f"${n}")
            i += 1
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def dbapi_connect(**kwargs) -> DBAPIConnection:
    """Drop-in replacement for ``psycopg2.connect(**kwargs)``."""
    return DBAPIConnection(**kwargs)


__all__ = [
    "Connection",
    "DBAPIConnection",
    "PostgresError",
    "ProtocolError",
    "connect",
    "dbapi_connect",
]
