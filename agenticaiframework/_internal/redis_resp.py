"""Minimal Redis client speaking RESP2 over plain TCP — stdlib-only.

Implements a tiny subset of the Redis command set sufficient for the framework's
usage: ``GET``, ``SET`` (with EX/PX/NX/XX), ``DEL``, ``EXPIRE``, ``EXISTS``,
``MGET``, ``INCR``, ``INCRBY``, ``DECR``, ``HSET``, ``HGET``, ``HGETALL``,
``KEYS``, ``FLUSHDB``, ``PING``, plus pipeline-style execution.

Both a synchronous client (:class:`RedisClient`) and an async client
(:class:`AsyncRedisClient`) are provided.

This is intentionally pragmatic — not a drop-in replacement for ``redis-py``.
"""

from __future__ import annotations

import asyncio
import socket
import threading
from typing import Any, Iterable, List, Optional, Sequence, Union

CRLF = b"\r\n"

# ---------------------------------------------------------------------------
# Shared encoding/decoding
# ---------------------------------------------------------------------------


def _encode_command(args: Sequence[Union[str, bytes, int, float]]) -> bytes:
    parts: List[bytes] = [f"*{len(args)}".encode("ascii"), CRLF]
    for arg in args:
        if isinstance(arg, (int, float)):
            arg = str(arg)
        if isinstance(arg, str):
            arg = arg.encode("utf-8")
        parts.append(f"${len(arg)}".encode("ascii"))
        parts.append(CRLF)
        parts.append(arg)
        parts.append(CRLF)
    return b"".join(parts)


class RedisError(Exception):
    """Server-side error reply."""


# ---------------------------------------------------------------------------
# Sync client
# ---------------------------------------------------------------------------

class _RESPReader:
    """Buffered RESP2 parser working off a callable returning raw bytes."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> None:
        self._buf.extend(data)

    def parse(self) -> Any:
        return self._parse_one()

    def _read_line(self) -> Optional[bytes]:
        idx = self._buf.find(CRLF)
        if idx < 0:
            return None
        line = bytes(self._buf[:idx])
        del self._buf[: idx + 2]
        return line

    def _parse_one(self) -> Any:
        line = self._read_line()
        if line is None:
            raise _NeedMoreData()
        prefix = chr(line[0])
        payload = line[1:]
        if prefix == "+":
            return payload.decode("utf-8")
        if prefix == "-":
            raise RedisError(payload.decode("utf-8"))
        if prefix == ":":
            return int(payload)
        if prefix == "$":
            length = int(payload)
            if length == -1:
                return None
            if len(self._buf) < length + 2:
                raise _NeedMoreData()
            data = bytes(self._buf[:length])
            del self._buf[: length + 2]
            return data
        if prefix == "*":
            count = int(payload)
            if count == -1:
                return None
            return [self._parse_one() for _ in range(count)]
        raise RedisError(f"Unknown RESP prefix: {prefix}")


class _NeedMoreData(Exception):
    pass


class RedisClient:
    """Synchronous RESP2 client over a TCP socket."""

    def __init__(self, host: str = "127.0.0.1", port: int = 6379, *, password: Optional[str] = None,
                 db: int = 0, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._reader = _RESPReader()
        self._lock = threading.Lock()

    # -- connection ----------------------------------------------------

    def connect(self) -> None:
        if self._sock is not None:
            return
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._sock = sock
        if self.password:
            self.execute("AUTH", self.password)
        if self.db:
            self.execute("SELECT", self.db)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    # -- core ----------------------------------------------------------

    def execute(self, *args: Union[str, bytes, int, float]) -> Any:
        with self._lock:
            self.connect()
            assert self._sock is not None
            self._sock.sendall(_encode_command(args))
            return self._read_reply()

    def _read_reply(self) -> Any:
        assert self._sock is not None
        while True:
            try:
                return self._reader.parse()
            except _NeedMoreData:
                chunk = self._sock.recv(65536)
                if not chunk:
                    raise RedisError("Connection closed by server")
                self._reader.feed(chunk)

    # -- convenience commands -----------------------------------------

    def ping(self) -> str:
        return self.execute("PING")

    def get(self, key: str) -> Optional[bytes]:
        return self.execute("GET", key)

    def set(self, key: str, value: Union[str, bytes, int, float], *,
            ex: Optional[int] = None, px: Optional[int] = None,
            nx: bool = False, xx: bool = False) -> Optional[str]:
        args: List[Union[str, bytes, int, float]] = ["SET", key, value]
        if ex is not None:
            args += ["EX", ex]
        if px is not None:
            args += ["PX", px]
        if nx:
            args.append("NX")
        if xx:
            args.append("XX")
        return self.execute(*args)

    def delete(self, *keys: str) -> int:
        return int(self.execute("DEL", *keys))

    def exists(self, *keys: str) -> int:
        return int(self.execute("EXISTS", *keys))

    def expire(self, key: str, seconds: int) -> int:
        return int(self.execute("EXPIRE", key, seconds))

    def keys(self, pattern: str = "*") -> List[bytes]:
        result = self.execute("KEYS", pattern)
        return result or []

    def mget(self, *keys: str) -> List[Optional[bytes]]:
        return self.execute("MGET", *keys) or []

    def incr(self, key: str, amount: int = 1) -> int:
        return int(self.execute("INCRBY", key, amount))

    def decr(self, key: str, amount: int = 1) -> int:
        return int(self.execute("DECRBY", key, amount))

    def hset(self, key: str, field: str, value: Union[str, bytes, int, float]) -> int:
        return int(self.execute("HSET", key, field, value))

    def hget(self, key: str, field: str) -> Optional[bytes]:
        return self.execute("HGET", key, field)

    def hgetall(self, key: str) -> dict:
        flat = self.execute("HGETALL", key) or []
        return {flat[i]: flat[i + 1] for i in range(0, len(flat), 2)}

    def flushdb(self) -> str:
        return self.execute("FLUSHDB")


# ---------------------------------------------------------------------------
# Async client
# ---------------------------------------------------------------------------

class AsyncRedisClient:
    """Asyncio RESP2 client. Usable as ``await client.get('foo')``."""

    def __init__(self, host: str = "127.0.0.1", port: int = 6379, *, password: Optional[str] = None,
                 db: int = 0, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.timeout = timeout
        self._reader_stream: Optional[asyncio.StreamReader] = None
        self._writer_stream: Optional[asyncio.StreamWriter] = None
        self._lock = asyncio.Lock()
        self._reader = _RESPReader()

    async def connect(self) -> None:
        if self._writer_stream is not None:
            return
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=self.timeout
        )
        self._reader_stream = reader
        self._writer_stream = writer
        if self.password:
            await self.execute("AUTH", self.password)
        if self.db:
            await self.execute("SELECT", self.db)

    async def close(self) -> None:
        if self._writer_stream is not None:
            self._writer_stream.close()
            try:
                await self._writer_stream.wait_closed()
            except Exception:  # noqa: BLE001
                pass
            self._writer_stream = None
            self._reader_stream = None

    async def execute(self, *args: Union[str, bytes, int, float]) -> Any:
        async with self._lock:
            await self.connect()
            assert self._writer_stream is not None and self._reader_stream is not None
            self._writer_stream.write(_encode_command(args))
            await self._writer_stream.drain()
            return await self._read_reply()

    async def _read_reply(self) -> Any:
        assert self._reader_stream is not None
        while True:
            try:
                return self._reader.parse()
            except _NeedMoreData:
                chunk = await self._reader_stream.read(65536)
                if not chunk:
                    raise RedisError("Connection closed by server")
                self._reader.feed(chunk)

    # Convenience ------------------------------------------------------

    async def ping(self) -> str:
        return await self.execute("PING")

    async def get(self, key: str) -> Optional[bytes]:
        return await self.execute("GET", key)

    async def set(self, key: str, value: Union[str, bytes, int, float], *,
                  ex: Optional[int] = None, px: Optional[int] = None,
                  nx: bool = False, xx: bool = False) -> Optional[str]:
        args: List[Union[str, bytes, int, float]] = ["SET", key, value]
        if ex is not None:
            args += ["EX", ex]
        if px is not None:
            args += ["PX", px]
        if nx:
            args.append("NX")
        if xx:
            args.append("XX")
        return await self.execute(*args)

    async def delete(self, *keys: str) -> int:
        return int(await self.execute("DEL", *keys))

    async def exists(self, *keys: str) -> int:
        return int(await self.execute("EXISTS", *keys))

    async def expire(self, key: str, seconds: int) -> int:
        return int(await self.execute("EXPIRE", key, seconds))

    async def keys(self, pattern: str = "*") -> List[bytes]:
        result = await self.execute("KEYS", pattern)
        return result or []

    async def incr(self, key: str, amount: int = 1) -> int:
        return int(await self.execute("INCRBY", key, amount))

    async def hset(self, key: str, field: str, value: Union[str, bytes, int, float]) -> int:
        return int(await self.execute("HSET", key, field, value))

    async def hget(self, key: str, field: str) -> Optional[bytes]:
        return await self.execute("HGET", key, field)

    async def hgetall(self, key: str) -> dict:
        flat = await self.execute("HGETALL", key) or []
        return {flat[i]: flat[i + 1] for i in range(0, len(flat), 2)}

    async def flushdb(self) -> str:
        return await self.execute("FLUSHDB")


__all__ = ["RedisClient", "AsyncRedisClient", "RedisError"]
