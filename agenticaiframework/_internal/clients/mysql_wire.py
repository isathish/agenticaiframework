"""
Pure-Python MySQL/SingleStore wire-protocol client.

Implements just enough of the MySQL Client/Server Protocol to support
``execute_query``-style usage from ``mysql.connector`` without depending
on the official driver.

Supported:
    * Protocol version 10 handshake parsing
    * ``mysql_native_password`` auth (SHA1 challenge-response, RFC-style)
    * ``caching_sha2_password`` auth (fast-path - SHA256(SHA256(password)) XOR
      SHA256(salt + SHA256(SHA256(password)))). Falls back to plaintext
      auth-switch when the server requires public-key exchange (only safe
      over SSL or unix socket).
    * COM_QUERY (text protocol) with full result-set parsing for
      OK/ERR/EOF/ResultSet packets.
    * DB-API 2.0 compatible ``connect(...)`` returning a connection with
      ``cursor()`` exposing ``execute``/``fetchall``/``description``/
      ``rowcount``.
    * SSL upgrade via stdlib ``ssl`` (used when ``ssl=True`` is passed).

Standard-library only - uses ``socket``, ``ssl``, ``hashlib``, ``struct``.
"""

from __future__ import annotations

import hashlib
import socket
import ssl
import struct
from typing import Any, Iterable, List, Optional, Sequence, Tuple

# ----------------------------------------------------------------------------
# Capability flags (subset)
# ----------------------------------------------------------------------------
CLIENT_LONG_PASSWORD = 0x00000001
CLIENT_FOUND_ROWS = 0x00000002
CLIENT_LONG_FLAG = 0x00000004
CLIENT_CONNECT_WITH_DB = 0x00000008
CLIENT_PROTOCOL_41 = 0x00000200
CLIENT_SSL = 0x00000800
CLIENT_TRANSACTIONS = 0x00002000
CLIENT_SECURE_CONNECTION = 0x00008000
CLIENT_MULTI_STATEMENTS = 0x00010000
CLIENT_PLUGIN_AUTH = 0x00080000
CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA = 0x00200000
CLIENT_DEPRECATE_EOF = 0x01000000

# ----------------------------------------------------------------------------
# Helpers: length-encoded values
# ----------------------------------------------------------------------------
def _read_lenenc_int(buf: bytes, pos: int) -> Tuple[int, int]:
    first = buf[pos]
    pos += 1
    if first < 0xFB:
        return first, pos
    if first == 0xFC:
        return struct.unpack_from("<H", buf, pos)[0], pos + 2
    if first == 0xFD:
        b0, b1, b2 = buf[pos], buf[pos + 1], buf[pos + 2]
        return b0 | (b1 << 8) | (b2 << 16), pos + 3
    if first == 0xFE:
        return struct.unpack_from("<Q", buf, pos)[0], pos + 8
    if first == 0xFB:  # NULL
        return -1, pos
    raise ValueError(f"Invalid length-encoded prefix: {first:#x}")


def _read_lenenc_str(buf: bytes, pos: int) -> Tuple[Optional[bytes], int]:
    length, pos = _read_lenenc_int(buf, pos)
    if length < 0:
        return None, pos
    return bytes(buf[pos:pos + length]), pos + length


def _write_lenenc_int(value: int) -> bytes:
    if value < 0xFB:
        return bytes([value])
    if value < (1 << 16):
        return b"\xfc" + struct.pack("<H", value)
    if value < (1 << 24):
        return b"\xfd" + struct.pack("<I", value)[:3]
    return b"\xfe" + struct.pack("<Q", value)


def _write_lenenc_str(value: bytes) -> bytes:
    return _write_lenenc_int(len(value)) + value


def _read_null_str(buf: bytes, pos: int) -> Tuple[bytes, int]:
    end = buf.find(b"\x00", pos)
    if end < 0:
        return bytes(buf[pos:]), len(buf)
    return bytes(buf[pos:end]), end + 1


# ----------------------------------------------------------------------------
# Native password auth scrambles
# ----------------------------------------------------------------------------
def _scramble_native_password(password: str, scramble: bytes) -> bytes:
    """mysql_native_password: SHA1(password) XOR SHA1(scramble + SHA1(SHA1(password)))."""
    if not password:
        return b""
    pw = password.encode("utf-8")
    stage1 = hashlib.sha1(pw).digest()
    stage2 = hashlib.sha1(stage1).digest()
    token = hashlib.sha1(scramble + stage2).digest()
    return bytes(a ^ b for a, b in zip(stage1, token))


def _scramble_caching_sha2(password: str, scramble: bytes) -> bytes:
    """caching_sha2_password: SHA256(password) XOR SHA256(SHA256(SHA256(password)) + scramble)."""
    if not password:
        return b""
    pw = password.encode("utf-8")
    stage1 = hashlib.sha256(pw).digest()
    stage2 = hashlib.sha256(stage1).digest()
    token = hashlib.sha256(stage2 + scramble).digest()
    return bytes(a ^ b for a, b in zip(stage1, token))


# ----------------------------------------------------------------------------
# Connection
# ----------------------------------------------------------------------------
class MySQLError(Exception):
    """Raised on any wire-protocol or server error."""

    def __init__(self, errno: int, sqlstate: str, message: str):
        self.errno = errno
        self.sqlstate = sqlstate
        super().__init__(f"[{errno}] ({sqlstate}) {message}")


class _Packet:
    __slots__ = ("payload", "seq")

    def __init__(self, payload: bytes, seq: int):
        self.payload = payload
        self.seq = seq


class Connection:
    """Low-level MySQL connection."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3306,
        user: str = "",
        password: str = "",
        database: str = "",
        charset: str = "utf8mb4",
        ssl: bool = False,
        timeout: Optional[float] = 30.0,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.charset = charset
        self.use_ssl = ssl
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._seq = 0
        self._capabilities = 0
        self._server_version = ""

    # ----- packet i/o ------------------------------------------------
    def _read_exact(self, n: int) -> bytes:
        assert self._sock is not None
        buf = bytearray()
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("MySQL connection closed unexpectedly")
            buf.extend(chunk)
        return bytes(buf)

    def _read_packet(self) -> _Packet:
        header = self._read_exact(4)
        plen = header[0] | (header[1] << 8) | (header[2] << 16)
        seq = header[3]
        self._seq = (seq + 1) & 0xFF
        return _Packet(self._read_exact(plen), seq)

    def _write_packet(self, payload: bytes) -> None:
        assert self._sock is not None
        plen = len(payload)
        header = bytes([plen & 0xFF, (plen >> 8) & 0xFF, (plen >> 16) & 0xFF, self._seq])
        self._sock.sendall(header + payload)
        self._seq = (self._seq + 1) & 0xFF

    # ----- packet decoders ------------------------------------------
    @staticmethod
    def _decode_err(payload: bytes) -> MySQLError:
        # 0xFF | error_code(2) | '#' sql_state(5) | message
        errno = struct.unpack_from("<H", payload, 1)[0]
        sqlstate = ""
        msg_pos = 3
        if len(payload) > 3 and payload[3:4] == b"#":
            sqlstate = payload[4:9].decode("ascii", errors="replace")
            msg_pos = 9
        message = payload[msg_pos:].decode("utf-8", errors="replace")
        return MySQLError(errno, sqlstate, message)

    @staticmethod
    def _is_ok(payload: bytes) -> bool:
        return bool(payload) and payload[0] == 0x00 and len(payload) >= 7

    @staticmethod
    def _is_eof(payload: bytes, deprecate_eof: bool) -> bool:
        if deprecate_eof:
            return bool(payload) and payload[0] == 0xFE and len(payload) < 0xFFFFFF
        return bool(payload) and payload[0] == 0xFE and len(payload) < 9

    @staticmethod
    def _is_err(payload: bytes) -> bool:
        return bool(payload) and payload[0] == 0xFF

    # ----- handshake ------------------------------------------------
    def connect(self) -> None:
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._seq = 0

        handshake = self._read_packet()
        salt, auth_plugin, server_caps = self._parse_handshake(handshake.payload)
        self._capabilities = server_caps & (
            CLIENT_LONG_PASSWORD
            | CLIENT_LONG_FLAG
            | CLIENT_PROTOCOL_41
            | CLIENT_TRANSACTIONS
            | CLIENT_SECURE_CONNECTION
            | CLIENT_PLUGIN_AUTH
            | CLIENT_DEPRECATE_EOF
        )
        if self.database:
            self._capabilities |= CLIENT_CONNECT_WITH_DB

        # Optional TLS upgrade
        if self.use_ssl:
            ssl_request = struct.pack(
                "<IIB23s",
                self._capabilities | CLIENT_SSL,
                16777215,  # max packet
                self._charset_id(),
                b"\x00" * 23,
            )
            self._write_packet(ssl_request)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            self._sock = ctx.wrap_socket(self._sock, server_hostname=self.host)
            self._capabilities |= CLIENT_SSL

        # Auth response
        auth_response = self._compute_auth(auth_plugin, salt)
        login = self._build_login_packet(auth_plugin, auth_response)
        self._write_packet(login)

        # Auth result loop (handles auth-switch / caching_sha2 fast-auth flow)
        while True:
            pkt = self._read_packet()
            payload = pkt.payload
            if self._is_err(payload):
                raise self._decode_err(payload)
            if self._is_ok(payload):
                return
            # 0xFE = auth-switch request
            if payload and payload[0] == 0xFE:
                new_plugin, new_salt = self._parse_auth_switch(payload)
                resp = self._compute_auth(new_plugin, new_salt)
                self._write_packet(resp)
                continue
            # 0x01 = caching_sha2 progress signal (0x03 = fast auth ok, 0x04 = full auth)
            if payload and payload[0] == 0x01:
                if len(payload) >= 2 and payload[1] == 0x03:
                    continue  # fast auth ok, expect OK next
                if len(payload) >= 2 and payload[1] == 0x04:
                    if not self.use_ssl:
                        raise MySQLError(
                            2061,
                            "HY000",
                            "caching_sha2_password full auth requires SSL or local socket",
                        )
                    self._write_packet(self.password.encode("utf-8") + b"\x00")
                    continue
                continue
            raise MySQLError(0, "HY000", f"Unexpected auth response: {payload[:1].hex()}")

    def _parse_handshake(self, payload: bytes) -> Tuple[bytes, str, int]:
        # protocol_version(1) | server_version(NULL) | thread_id(4) | salt1(8) | filler(1)
        # | cap_lower(2) | charset(1) | status(2) | cap_upper(2) | salt_len(1)
        # | reserved(10) | salt2(>=12, NULL term) | auth_plugin(NULL)
        if not payload or payload[0] != 0x0A:
            raise MySQLError(0, "HY000", f"Unsupported handshake protocol: {payload[:1].hex()}")
        pos = 1
        server_version, pos = _read_null_str(payload, pos)
        self._server_version = server_version.decode("ascii", errors="replace")
        pos += 4  # thread_id
        salt1 = bytes(payload[pos:pos + 8])
        pos += 8 + 1  # salt1 + filler
        cap_lower = struct.unpack_from("<H", payload, pos)[0]
        pos += 2
        salt2 = b""
        auth_plugin = "mysql_native_password"
        if pos < len(payload):
            pos += 1  # charset
            pos += 2  # status
            cap_upper = struct.unpack_from("<H", payload, pos)[0]
            pos += 2
            server_caps = cap_lower | (cap_upper << 16)
            salt_len = payload[pos]
            pos += 1
            pos += 10  # reserved
            extra = max(13, salt_len - 8)
            salt2 = bytes(payload[pos:pos + extra]).rstrip(b"\x00")
            pos += extra
            if server_caps & CLIENT_PLUGIN_AUTH:
                plugin_bytes, _ = _read_null_str(payload, pos)
                auth_plugin = plugin_bytes.decode("ascii", errors="replace") or auth_plugin
        else:
            server_caps = cap_lower
        return salt1 + salt2, auth_plugin, server_caps

    def _parse_auth_switch(self, payload: bytes) -> Tuple[str, bytes]:
        # 0xFE | plugin_name(NULL) | auth_data
        pos = 1
        plugin, pos = _read_null_str(payload, pos)
        salt = bytes(payload[pos:]).rstrip(b"\x00")
        return plugin.decode("ascii", errors="replace"), salt

    def _compute_auth(self, plugin: str, salt: bytes) -> bytes:
        if plugin == "mysql_native_password":
            return _scramble_native_password(self.password, salt[:20])
        if plugin == "caching_sha2_password":
            return _scramble_caching_sha2(self.password, salt[:20])
        if plugin == "mysql_clear_password":
            return self.password.encode("utf-8") + b"\x00"
        # Unknown plugin - send empty (server will likely fail)
        return b""

    def _charset_id(self) -> int:
        return {
            "utf8": 33,
            "utf8mb3": 33,
            "utf8mb4": 45,
            "latin1": 8,
            "ascii": 11,
        }.get(self.charset.lower(), 45)

    def _build_login_packet(self, auth_plugin: str, auth_response: bytes) -> bytes:
        body = bytearray()
        body += struct.pack(
            "<IIB23s",
            self._capabilities,
            16777215,
            self._charset_id(),
            b"\x00" * 23,
        )
        body += self.user.encode("utf-8") + b"\x00"
        if self._capabilities & CLIENT_PLUGIN_AUTH_LENENC_CLIENT_DATA:
            body += _write_lenenc_str(auth_response)
        else:
            body += bytes([len(auth_response)]) + auth_response
        if self._capabilities & CLIENT_CONNECT_WITH_DB:
            body += self.database.encode("utf-8") + b"\x00"
        if self._capabilities & CLIENT_PLUGIN_AUTH:
            body += auth_plugin.encode("ascii") + b"\x00"
        return bytes(body)

    # ----- queries ---------------------------------------------------
    def query(
        self,
        sql: str,
    ) -> Tuple[List[Tuple[str, int]], List[Tuple[Any, ...]], int, int]:
        """Run a single SQL statement.

        Returns ``(columns, rows, affected_rows, last_insert_id)`` where
        ``columns`` is a list of ``(name, type_code)`` tuples (empty for
        non-SELECT statements).
        """
        if self._sock is None:
            self.connect()
        self._seq = 0
        sql_bytes = sql.encode("utf-8")
        self._write_packet(b"\x03" + sql_bytes)  # COM_QUERY
        return self._read_resultset()

    def _read_resultset(
        self,
    ) -> Tuple[List[Tuple[str, int]], List[Tuple[Any, ...]], int, int]:
        first = self._read_packet().payload
        if self._is_err(first):
            raise self._decode_err(first)
        if self._is_ok(first):
            affected, last_id = self._parse_ok(first)
            return [], [], affected, last_id

        # ResultSet header: column count (length-encoded int)
        col_count, _ = _read_lenenc_int(first, 0)
        deprecate_eof = bool(self._capabilities & CLIENT_DEPRECATE_EOF)

        columns: List[Tuple[str, int]] = []
        for _ in range(col_count):
            cdef = self._read_packet().payload
            columns.append(self._parse_column_def(cdef))

        if not deprecate_eof:
            eof = self._read_packet().payload
            if not self._is_eof(eof, deprecate_eof):
                raise MySQLError(0, "HY000", "Expected EOF after column definitions")

        rows: List[Tuple[Any, ...]] = []
        while True:
            pkt = self._read_packet().payload
            if self._is_err(pkt):
                raise self._decode_err(pkt)
            if self._is_eof(pkt, deprecate_eof):
                break
            row = self._parse_text_row(pkt, columns)
            rows.append(row)

        return columns, rows, len(rows), 0

    @staticmethod
    def _parse_ok(payload: bytes) -> Tuple[int, int]:
        pos = 1
        affected, pos = _read_lenenc_int(payload, pos)
        last_id, pos = _read_lenenc_int(payload, pos)
        return affected, last_id

    @staticmethod
    def _parse_column_def(payload: bytes) -> Tuple[str, int]:
        pos = 0
        for _ in range(4):  # catalog, schema, table, org_table
            _, pos = _read_lenenc_str(payload, pos)
        name, pos = _read_lenenc_str(payload, pos)
        _, pos = _read_lenenc_str(payload, pos)  # org_name
        # next len-enc (0x0c) followed by fixed 12-byte col-meta block
        _, pos = _read_lenenc_int(payload, pos)
        # charset(2) col_len(4) col_type(1) flags(2) decimals(1) filler(2)
        col_type = payload[pos + 2 + 4]
        return ((name or b"").decode("utf-8", errors="replace"), int(col_type))

    @staticmethod
    def _parse_text_row(payload: bytes, columns: Sequence[Tuple[str, int]]) -> Tuple[Any, ...]:
        pos = 0
        out: List[Any] = []
        for _, type_code in columns:
            raw, pos = _read_lenenc_str(payload, pos)
            out.append(_decode_value(raw, type_code))
        return tuple(out)

    # ----- shutdown --------------------------------------------------
    def close(self) -> None:
        if self._sock is not None:
            try:
                self._seq = 0
                self._write_packet(b"\x01")  # COM_QUIT
            except Exception:
                pass
            try:
                self._sock.close()
            finally:
                self._sock = None


# ----------------------------------------------------------------------------
# Type decoding (text protocol returns everything as bytes)
# ----------------------------------------------------------------------------
_INT_TYPES = {0x01, 0x02, 0x03, 0x08, 0x09, 0x0D}  # TINY/SHORT/LONG/LONGLONG/INT24/YEAR
_FLOAT_TYPES = {0x04, 0x05, 0x00, 0xF6}            # FLOAT/DOUBLE/DECIMAL/NEWDECIMAL


def _decode_value(raw: Optional[bytes], type_code: int) -> Any:
    if raw is None:
        return None
    text = raw.decode("utf-8", errors="replace")
    if type_code in _INT_TYPES:
        try:
            return int(text)
        except ValueError:
            return text
    if type_code in _FLOAT_TYPES:
        try:
            return float(text)
        except ValueError:
            return text
    return text


# ----------------------------------------------------------------------------
# DB-API 2.0 layer (drop-in for ``mysql.connector.connect``)
# ----------------------------------------------------------------------------
class _DBAPICursor:
    def __init__(self, conn: "DBAPIConnection", dictionary: bool = False):
        self._conn = conn
        self._dictionary = dictionary
        self.description: Optional[List[Tuple[str, int, None, None, None, None, None]]] = None
        self.rowcount: int = -1
        self._rows: List[Any] = []
        self.lastrowid: int = 0
        self._closed = False

    def execute(self, query: str, params: Optional[Sequence[Any]] = None) -> None:
        if self._closed:
            raise MySQLError(0, "HY000", "Cursor is closed")
        sql = _interpolate(query, params or ())
        cols, rows, affected, last_id = self._conn._raw.query(sql)
        if cols:
            self.description = [(name, tcode, None, None, None, None, None) for name, tcode in cols]
            if self._dictionary:
                names = [c[0] for c in cols]
                self._rows = [dict(zip(names, r)) for r in rows]
            else:
                self._rows = list(rows)
            self.rowcount = len(rows)
        else:
            self.description = None
            self._rows = []
            self.rowcount = affected
        self.lastrowid = last_id

    def executemany(self, query: str, seq_params: Iterable[Sequence[Any]]) -> None:
        for params in seq_params:
            self.execute(query, params)

    def fetchone(self) -> Any:
        return self._rows.pop(0) if self._rows else None

    def fetchmany(self, size: int = 1) -> List[Any]:
        out, self._rows = self._rows[:size], self._rows[size:]
        return out

    def fetchall(self) -> List[Any]:
        out, self._rows = self._rows, []
        return out

    def close(self) -> None:
        self._closed = True

    def __iter__(self):
        while self._rows:
            yield self._rows.pop(0)


class DBAPIConnection:
    def __init__(self, **kwargs: Any):
        self._raw = Connection(**kwargs)
        self._raw.connect()

    def cursor(self, dictionary: bool = False) -> _DBAPICursor:
        return _DBAPICursor(self, dictionary=dictionary)

    def commit(self) -> None:
        self._raw.query("COMMIT")

    def rollback(self) -> None:
        self._raw.query("ROLLBACK")

    def close(self) -> None:
        self._raw.close()


def connect(**kwargs: Any) -> DBAPIConnection:
    """DB-API entry point - signature mirrors ``mysql.connector.connect``."""
    return DBAPIConnection(**kwargs)


# ----------------------------------------------------------------------------
# Parameter interpolation (text-protocol; safe for str/int/float/None/bytes)
# ----------------------------------------------------------------------------
def _quote(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return "0x" + bytes(value).hex()
    s = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


def _interpolate(query: str, params: Sequence[Any]) -> str:
    if not params:
        return query
    # Support both %s and ? styles
    if "%s" in query:
        out = []
        i = 0
        idx = 0
        while i < len(query):
            if query[i:i + 2] == "%s":
                if idx >= len(params):
                    raise MySQLError(0, "HY000", "Not enough parameters supplied")
                out.append(_quote(params[idx]))
                idx += 1
                i += 2
            else:
                out.append(query[i])
                i += 1
        return "".join(out)
    if "?" in query:
        out = []
        idx = 0
        for ch in query:
            if ch == "?":
                if idx >= len(params):
                    raise MySQLError(0, "HY000", "Not enough parameters supplied")
                out.append(_quote(params[idx]))
                idx += 1
            else:
                out.append(ch)
        return "".join(out)
    return query


__all__ = [
    "Connection",
    "DBAPIConnection",
    "MySQLError",
    "connect",
]
