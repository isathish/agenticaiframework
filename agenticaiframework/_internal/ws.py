"""RFC 6455 WebSocket — minimal client + server frame codec.

Provides a low-level frame encoder/decoder plus a tiny client (:class:`WSClient`)
that performs the upgrade handshake over a plain TCP socket. For server-side
use, :func:`accept_websocket` upgrades a raw socket from an incoming HTTP
request and returns a :class:`WSConnection`.

Supports text + binary data frames, close, ping/pong; QoS / extensions /
compression are intentionally out of scope.
"""

from __future__ import annotations

import base64
import hashlib
import os
import socket
import ssl
import struct
import threading
from dataclasses import dataclass
from typing import Optional, Tuple, Union
from urllib.parse import urlsplit

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OP_CONTINUATION = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA


class WebSocketError(Exception):
    pass


@dataclass
class Frame:
    fin: bool
    opcode: int
    payload: bytes


# ---------------------------------------------------------------------------
# Frame codec
# ---------------------------------------------------------------------------

def encode_frame(opcode: int, payload: bytes, *, mask: bool) -> bytes:
    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))  # FIN=1
    length = len(payload)
    mask_bit = 0x80 if mask else 0x00
    if length < 126:
        header.append(mask_bit | length)
    elif length < (1 << 16):
        header.append(mask_bit | 126)
        header.extend(struct.pack(">H", length))
    else:
        header.append(mask_bit | 127)
        header.extend(struct.pack(">Q", length))
    if mask:
        mask_key = os.urandom(4)
        header.extend(mask_key)
        masked = bytearray(length)
        for i, b in enumerate(payload):
            masked[i] = b ^ mask_key[i % 4]
        return bytes(header) + bytes(masked)
    return bytes(header) + payload


def _read_exact(sock: socket.socket, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        chunk = sock.recv(n - len(out))
        if not chunk:
            raise WebSocketError("connection closed")
        out.extend(chunk)
    return bytes(out)


def read_frame(sock: socket.socket) -> Frame:
    header = _read_exact(sock, 2)
    fin = bool(header[0] & 0x80)
    opcode = header[0] & 0x0F
    masked = bool(header[1] & 0x80)
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", _read_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _read_exact(sock, 8))[0]
    mask_key = _read_exact(sock, 4) if masked else None
    payload = _read_exact(sock, length) if length else b""
    if mask_key is not None:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    return Frame(fin=fin, opcode=opcode, payload=payload)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

class WSConnection:
    def __init__(self, sock: socket.socket, *, mask_outgoing: bool) -> None:
        self._sock = sock
        self._mask = mask_outgoing
        self._lock = threading.Lock()
        self._closed = False

    def send_text(self, data: str) -> None:
        self._send(OP_TEXT, data.encode("utf-8"))

    def send_bytes(self, data: bytes) -> None:
        self._send(OP_BINARY, data)

    def ping(self, data: bytes = b"") -> None:
        self._send(OP_PING, data)

    def close(self, code: int = 1000, reason: str = "") -> None:
        if self._closed:
            return
        payload = struct.pack(">H", code) + reason.encode("utf-8")
        try:
            self._send(OP_CLOSE, payload)
        finally:
            self._closed = True
            try:
                self._sock.close()
            except OSError:
                pass

    def recv(self) -> Tuple[int, bytes]:
        """Receive a complete (possibly fragmented) message. Returns (opcode, payload)."""
        first = read_frame(self._sock)
        if first.opcode == OP_CLOSE:
            self._closed = True
            return OP_CLOSE, first.payload
        if first.opcode == OP_PING:
            self._send(OP_PONG, first.payload)
            return self.recv()
        opcode = first.opcode
        payload = bytearray(first.payload)
        while not first.fin:
            first = read_frame(self._sock)
            if first.opcode != OP_CONTINUATION:
                raise WebSocketError("expected continuation frame")
            payload.extend(first.payload)
        return opcode, bytes(payload)

    def _send(self, opcode: int, payload: bytes) -> None:
        with self._lock:
            self._sock.sendall(encode_frame(opcode, payload, mask=self._mask))


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def connect(url: str, *, timeout: float = 10.0,
            extra_headers: Optional[dict] = None) -> WSConnection:
    parts = urlsplit(url)
    if parts.scheme not in ("ws", "wss"):
        raise WebSocketError(f"Unsupported scheme: {parts.scheme}")
    host = parts.hostname or "127.0.0.1"
    port = parts.port or (443 if parts.scheme == "wss" else 80)
    sock = socket.create_connection((host, port), timeout=timeout)
    if parts.scheme == "wss":
        sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    headers = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}:{port}" if parts.port else f"Host: {host}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    ]
    for k, v in (extra_headers or {}).items():
        headers.append(f"{k}: {v}")
    sock.sendall(("\r\n".join(headers) + "\r\n\r\n").encode("ascii"))
    response = _read_until(sock, b"\r\n\r\n")
    status_line = response.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
    if "101" not in status_line:
        raise WebSocketError(f"Handshake failed: {status_line}")
    expected = base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest()).decode("ascii")
    if expected.encode("ascii").lower() not in response.lower():
        raise WebSocketError("Sec-WebSocket-Accept mismatch")
    sock.settimeout(None)
    return WSConnection(sock, mask_outgoing=True)


def _read_until(sock: socket.socket, sentinel: bytes) -> bytes:
    buf = bytearray()
    while sentinel not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise WebSocketError("connection closed during handshake")
        buf.extend(chunk)
    return bytes(buf)


# ---------------------------------------------------------------------------
# Server-side upgrade
# ---------------------------------------------------------------------------

def accept_websocket(sock: socket.socket, headers: dict) -> WSConnection:
    """Complete the server-side upgrade. ``headers`` are the parsed request headers."""
    key = headers.get("sec-websocket-key") or headers.get("Sec-WebSocket-Key")
    if not key:
        raise WebSocketError("Missing Sec-WebSocket-Key")
    accept = base64.b64encode(hashlib.sha1((key + GUID).encode("ascii")).digest()).decode("ascii")
    response = (
        "HTTP/1.1 101 Switching Protocols\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
    )
    sock.sendall(response.encode("ascii"))
    return WSConnection(sock, mask_outgoing=False)


__all__ = [
    "Frame",
    "WSConnection",
    "WebSocketError",
    "encode_frame",
    "read_frame",
    "connect",
    "accept_websocket",
]
