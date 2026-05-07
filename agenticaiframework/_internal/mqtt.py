"""Tiny MQTT 3.1.1 client — stdlib-only.

Implements a minimal subset of MQTT 3.1.1 sufficient for publish/subscribe at
QoS 0. Not a replacement for ``paho-mqtt`` — anything beyond CONNECT, PUBLISH,
SUBSCRIBE, PING, DISCONNECT at QoS 0 is intentionally out of scope.
"""

from __future__ import annotations

import socket
import struct
import threading
import time
from typing import Callable, Dict, Optional

CONNECT = 1
CONNACK = 2
PUBLISH = 3
SUBSCRIBE = 8
SUBACK = 9
PINGREQ = 12
PINGRESP = 13
DISCONNECT = 14


def _encode_remaining_length(length: int) -> bytes:
    out = bytearray()
    while True:
        digit = length % 128
        length //= 128
        if length > 0:
            digit |= 0x80
        out.append(digit)
        if length == 0:
            break
    return bytes(out)


def _encode_string(s: str) -> bytes:
    data = s.encode("utf-8")
    return struct.pack(">H", len(data)) + data


class MQTTError(Exception):
    pass


class MQTTClient:
    """Minimal blocking MQTT 3.1.1 publisher/subscriber."""

    def __init__(self, host: str = "127.0.0.1", port: int = 1883, *, client_id: str = "aaf",
                 username: Optional[str] = None, password: Optional[str] = None,
                 keepalive: int = 60, timeout: float = 10.0) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self.username = username
        self.password = password
        self.keepalive = keepalive
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._packet_id = 0
        self._handlers: Dict[str, Callable[[str, bytes], None]] = {}
        self._loop_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # -- core ----------------------------------------------------------

    def connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock = sock
        flags = 0x02  # clean session
        payload = _encode_string(self.client_id)
        if self.username is not None:
            flags |= 0x80
            payload += _encode_string(self.username)
        if self.password is not None:
            flags |= 0x40
            payload += _encode_string(self.password)
        variable = _encode_string("MQTT") + bytes([4]) + bytes([flags]) + struct.pack(">H", self.keepalive)
        packet = bytes([CONNECT << 4]) + _encode_remaining_length(len(variable) + len(payload)) + variable + payload
        sock.sendall(packet)
        self._read_packet(expect_type=CONNACK)

    def disconnect(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.sendall(bytes([DISCONNECT << 4, 0]))
            except OSError:
                pass
            try:
                self._sock.close()
            finally:
                self._sock = None

    def publish(self, topic: str, payload: bytes | str) -> None:
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        if self._sock is None:
            raise MQTTError("not connected")
        variable = _encode_string(topic)
        body = variable + payload
        header = bytes([PUBLISH << 4]) + _encode_remaining_length(len(body))
        with self._lock:
            self._sock.sendall(header + body)

    def subscribe(self, topic: str, callback: Callable[[str, bytes], None]) -> None:
        if self._sock is None:
            raise MQTTError("not connected")
        self._handlers[topic] = callback
        self._packet_id += 1
        body = struct.pack(">H", self._packet_id) + _encode_string(topic) + bytes([0])
        header = bytes([(SUBSCRIBE << 4) | 0x02]) + _encode_remaining_length(len(body))
        with self._lock:
            self._sock.sendall(header + body)
        self._read_packet(expect_type=SUBACK)

    def loop_start(self) -> None:
        self._stop.clear()
        self._loop_thread = threading.Thread(target=self._loop, daemon=True)
        self._loop_thread.start()

    def loop_stop(self) -> None:
        self._stop.set()
        if self._loop_thread is not None:
            self._loop_thread.join(timeout=1.0)
            self._loop_thread = None

    # -- internals -----------------------------------------------------

    def _loop(self) -> None:
        last_ping = time.time()
        assert self._sock is not None
        self._sock.settimeout(1.0)
        while not self._stop.is_set():
            try:
                self._read_packet()
            except socket.timeout:
                pass
            except OSError:
                break
            if time.time() - last_ping > self.keepalive / 2:
                try:
                    with self._lock:
                        self._sock.sendall(bytes([PINGREQ << 4, 0]))
                    last_ping = time.time()
                except OSError:
                    break

    def _read_exact(self, n: int) -> bytes:
        assert self._sock is not None
        data = bytearray()
        while len(data) < n:
            chunk = self._sock.recv(n - len(data))
            if not chunk:
                raise MQTTError("Connection closed")
            data.extend(chunk)
        return bytes(data)

    def _read_remaining_length(self) -> int:
        multiplier = 1
        value = 0
        while True:
            digit = self._read_exact(1)[0]
            value += (digit & 0x7F) * multiplier
            if (digit & 0x80) == 0:
                return value
            multiplier *= 128
            if multiplier > 128 * 128 * 128:
                raise MQTTError("Malformed remaining length")

    def _read_packet(self, expect_type: Optional[int] = None) -> None:
        header = self._read_exact(1)[0]
        ptype = header >> 4
        remaining = self._read_remaining_length()
        body = self._read_exact(remaining) if remaining else b""
        if expect_type is not None and ptype != expect_type:
            raise MQTTError(f"Expected packet type {expect_type}, got {ptype}")
        if ptype == PUBLISH:
            topic_len = struct.unpack(">H", body[:2])[0]
            topic = body[2 : 2 + topic_len].decode("utf-8", errors="replace")
            payload = body[2 + topic_len :]
            cb = self._handlers.get(topic) or self._handlers.get("#")
            if cb is not None:
                try:
                    cb(topic, payload)
                except Exception:  # noqa: BLE001
                    pass


__all__ = ["MQTTClient", "MQTTError"]
