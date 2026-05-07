"""Stdlib-only HTTP client.

Replaces ``requests`` / ``httpx`` / ``aiohttp`` for the framework's needs.

Features
--------
- Synchronous :class:`Client` and asynchronous :class:`AsyncClient`.
- ``get/post/put/patch/delete/head/options/request`` helpers.
- JSON / form / multipart / raw-bytes bodies.
- Streaming line iteration and Server-Sent-Events (SSE) iterator.
- Retries with exponential backoff, configurable timeouts, keep-alive via
  ``http.client``.
- Transparent gzip / deflate response decoding.
- Bearer / Basic / custom headers.

Built only on the Python standard library (``urllib``, ``http.client``,
``ssl``, ``socket``, ``gzip``, ``zlib``, ``json``, ``base64``, ``asyncio``).
"""

from __future__ import annotations

import asyncio
import base64
import gzip
import io
import json as _json
import logging
import socket
import ssl
import time
import urllib.parse
import uuid
import zlib
from dataclasses import dataclass, field
from http.client import HTTPConnection, HTTPResponse, HTTPSConnection
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Tuple,
    Union,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

JSONLike = Union[Dict[str, Any], list, str, int, float, bool, None]
Headers = Dict[str, str]


class HTTPError(Exception):
    """Raised when the HTTP response indicates a non-2xx status."""

    def __init__(self, status: int, message: str, response: "Response | None" = None):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status
        self.response = response


class TimeoutError(Exception):  # noqa: A001 - intentional public name
    """Raised on connection or read timeout."""


@dataclass
class Response:
    """HTTP response object with a small, requests-like API."""

    status: int
    reason: str
    headers: Headers
    content: bytes
    url: str
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 400

    @property
    def text(self) -> str:
        encoding = "utf-8"
        ctype = self.headers.get("content-type", "")
        if "charset=" in ctype.lower():
            encoding = ctype.lower().split("charset=", 1)[1].split(";", 1)[0].strip()
        try:
            return self.content.decode(encoding, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")

    def json(self) -> JSONLike:
        return _json.loads(self.text)

    def raise_for_status(self) -> "Response":
        if not self.ok:
            raise HTTPError(self.status, self.reason or "", self)
        return self

    def iter_lines(self, chunk_size: int = 8192) -> Iterator[bytes]:
        """Yield response body line by line (CR/LF terminated)."""
        buf = io.BytesIO(self.content)
        while True:
            line = buf.readline()
            if not line:
                return
            yield line.rstrip(b"\r\n")

    def iter_sse(self) -> Iterator["SSEEvent"]:
        return iter_sse(self.iter_lines())


@dataclass
class SSEEvent:
    """A single Server-Sent-Events frame."""

    event: str = "message"
    data: str = ""
    id: str = ""
    retry: Optional[int] = None


def iter_sse(lines: Iterable[bytes]) -> Iterator[SSEEvent]:
    """Parse an iterable of bytes lines into SSE events (RFC 6elements: event/data/id/retry)."""
    event_type = "message"
    data_lines: list[str] = []
    last_id = ""
    retry: Optional[int] = None
    for raw in lines:
        line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
        if line == "":
            if data_lines:
                yield SSEEvent(
                    event=event_type,
                    data="\n".join(data_lines),
                    id=last_id,
                    retry=retry,
                )
            event_type = "message"
            data_lines = []
            retry = None
            continue
        if line.startswith(":"):
            continue  # comment / keep-alive
        if ":" in line:
            field_name, _, value = line.partition(":")
            if value.startswith(" "):
                value = value[1:]
        else:
            field_name, value = line, ""
        if field_name == "event":
            event_type = value
        elif field_name == "data":
            data_lines.append(value)
        elif field_name == "id":
            last_id = value
        elif field_name == "retry":
            try:
                retry = int(value)
            except ValueError:
                pass
    # Tail event without trailing blank line
    if data_lines:
        yield SSEEvent(
            event=event_type, data="\n".join(data_lines), id=last_id, retry=retry
        )


# ---------------------------------------------------------------------------
# Body encoding helpers
# ---------------------------------------------------------------------------

def _encode_body(
    *,
    json: Any = None,
    data: Any = None,
    files: Optional[Mapping[str, Any]] = None,
    headers: Headers,
) -> Tuple[bytes, Headers]:
    """Return (body, headers) for the supplied body kind."""
    headers = dict(headers)
    if json is not None:
        body = _json.dumps(json, default=str).encode("utf-8")
        headers.setdefault("content-type", "application/json")
        return body, headers
    if files:
        boundary = f"----aaf{uuid.uuid4().hex}"
        body_io = io.BytesIO()
        # form fields
        if isinstance(data, Mapping):
            for k, v in data.items():
                body_io.write(f"--{boundary}\r\n".encode())
                body_io.write(
                    f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
                )
                body_io.write(str(v).encode("utf-8"))
                body_io.write(b"\r\n")
        for name, payload in files.items():
            if isinstance(payload, tuple):
                filename, content = payload[0], payload[1]
                ctype = payload[2] if len(payload) > 2 else "application/octet-stream"
            else:
                filename, content = name, payload
                ctype = "application/octet-stream"
            if isinstance(content, str):
                content = content.encode("utf-8")
            body_io.write(f"--{boundary}\r\n".encode())
            body_io.write(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n".encode()
            )
            body_io.write(content)
            body_io.write(b"\r\n")
        body_io.write(f"--{boundary}--\r\n".encode())
        body = body_io.getvalue()
        headers["content-type"] = f"multipart/form-data; boundary={boundary}"
        return body, headers
    if data is None:
        return b"", headers
    if isinstance(data, (bytes, bytearray)):
        return bytes(data), headers
    if isinstance(data, str):
        headers.setdefault("content-type", "text/plain; charset=utf-8")
        return data.encode("utf-8"), headers
    if isinstance(data, Mapping):
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers.setdefault("content-type", "application/x-www-form-urlencoded")
        return body, headers
    raise TypeError(f"Unsupported body type: {type(data).__name__}")


def _decode_response_body(raw: bytes, headers: Mapping[str, str]) -> bytes:
    enc = headers.get("content-encoding", "").lower()
    if not enc:
        return raw
    try:
        if "gzip" in enc:
            return gzip.decompress(raw)
        if "deflate" in enc:
            try:
                return zlib.decompress(raw)
            except zlib.error:
                return zlib.decompress(raw, -zlib.MAX_WBITS)
    except OSError:
        return raw
    return raw


# ---------------------------------------------------------------------------
# Sync client
# ---------------------------------------------------------------------------

@dataclass
class _ClientConfig:
    base_url: str = ""
    headers: Headers = field(default_factory=dict)
    timeout: float = 60.0
    max_retries: int = 0
    retry_backoff: float = 0.5
    retry_status: Tuple[int, ...] = (429, 500, 502, 503, 504)
    verify: bool = True
    follow_redirects: bool = True


class Client:
    """Synchronous HTTP client.

    Example
    -------
    >>> client = Client(base_url="https://api.example.com",
    ...                 headers={"Authorization": "Bearer x"})
    >>> r = client.post("/v1/items", json={"a": 1}).raise_for_status()
    >>> r.json()
    """

    def __init__(
        self,
        base_url: str = "",
        *,
        headers: Optional[Headers] = None,
        timeout: float = 60.0,
        max_retries: int = 0,
        retry_backoff: float = 0.5,
        retry_status: Tuple[int, ...] = (429, 500, 502, 503, 504),
        verify: bool = True,
        follow_redirects: bool = True,
    ) -> None:
        self.config = _ClientConfig(
            base_url=base_url.rstrip("/"),
            headers={k.lower(): v for k, v in (headers or {}).items()},
            timeout=timeout,
            max_retries=max_retries,
            retry_backoff=retry_backoff,
            retry_status=retry_status,
            verify=verify,
            follow_redirects=follow_redirects,
        )
        self._ssl_ctx: Optional[ssl.SSLContext] = None

    # -- public verbs -------------------------------------------------------

    def get(self, url: str, **kw: Any) -> Response:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw: Any) -> Response:
        return self.request("POST", url, **kw)

    def put(self, url: str, **kw: Any) -> Response:
        return self.request("PUT", url, **kw)

    def patch(self, url: str, **kw: Any) -> Response:
        return self.request("PATCH", url, **kw)

    def delete(self, url: str, **kw: Any) -> Response:
        return self.request("DELETE", url, **kw)

    def head(self, url: str, **kw: Any) -> Response:
        return self.request("HEAD", url, **kw)

    def options(self, url: str, **kw: Any) -> Response:
        return self.request("OPTIONS", url, **kw)

    # -- core ---------------------------------------------------------------

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Headers] = None,
        json: Any = None,
        data: Any = None,
        files: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        auth: Optional[Tuple[str, str]] = None,
    ) -> Response:
        full_url = self._build_url(url, params)
        merged_headers = dict(self.config.headers)
        if headers:
            for k, v in headers.items():
                merged_headers[k.lower()] = v
        if auth:
            user, password = auth
            token = base64.b64encode(f"{user}:{password}".encode()).decode()
            merged_headers["authorization"] = f"Basic {token}"
        body, merged_headers = _encode_body(
            json=json, data=data, files=files, headers=merged_headers
        )
        merged_headers.setdefault("accept-encoding", "gzip, deflate")
        merged_headers.setdefault("user-agent", "agenticaiframework/3.0 (stdlib)")
        merged_headers.setdefault("connection", "close")
        if body:
            merged_headers.setdefault("content-length", str(len(body)))

        last_exc: Optional[Exception] = None
        attempts = max(1, self.config.max_retries + 1)
        for attempt in range(attempts):
            start = time.monotonic()
            try:
                resp = self._raw_request(
                    method, full_url, merged_headers, body, timeout or self.config.timeout
                )
                resp.elapsed = time.monotonic() - start
                if resp.status in self.config.retry_status and attempt < attempts - 1:
                    time.sleep(self.config.retry_backoff * (2**attempt))
                    continue
                return resp
            except (TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < attempts - 1:
                    time.sleep(self.config.retry_backoff * (2**attempt))
                    continue
                raise
        if last_exc is not None:  # pragma: no cover - defensive
            raise last_exc
        raise RuntimeError("HTTP request failed without exception")  # pragma: no cover

    # -- helpers ------------------------------------------------------------

    def _build_url(self, url: str, params: Optional[Mapping[str, Any]]) -> str:
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"{self.config.base_url}/{url.lstrip('/')}" if self.config.base_url else url
        if params:
            sep = "&" if "?" in url else "?"
            url = (
                url
                + sep
                + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            )
        return url

    def _ssl_context(self) -> ssl.SSLContext:
        if self._ssl_ctx is None:
            ctx = ssl.create_default_context()
            if not self.config.verify:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            self._ssl_ctx = ctx
        return self._ssl_ctx

    def _raw_request(
        self,
        method: str,
        url: str,
        headers: Headers,
        body: bytes,
        timeout: float,
    ) -> Response:
        parsed = urllib.parse.urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        try:
            if parsed.scheme == "https":
                conn: HTTPConnection = HTTPSConnection(
                    host, port, timeout=timeout, context=self._ssl_context()
                )
            else:
                conn = HTTPConnection(host, port, timeout=timeout)
            try:
                conn.request(method, path, body=body if body else None, headers=headers)
                raw_resp: HTTPResponse = conn.getresponse()
                raw_body = raw_resp.read()
                resp_headers = {k.lower(): v for k, v in raw_resp.getheaders()}
                content = _decode_response_body(raw_body, resp_headers)
                resp = Response(
                    status=raw_resp.status,
                    reason=raw_resp.reason or "",
                    headers=resp_headers,
                    content=content,
                    url=url,
                )
                # Manual redirect handling (HTTPConnection doesn't follow)
                if (
                    self.config.follow_redirects
                    and resp.status in (301, 302, 303, 307, 308)
                    and "location" in resp_headers
                ):
                    new_url = urllib.parse.urljoin(url, resp_headers["location"])
                    new_method = method
                    new_body = body
                    if resp.status in (301, 302, 303) and method != "HEAD":
                        new_method = "GET"
                        new_body = b""
                        headers.pop("content-length", None)
                        headers.pop("content-type", None)
                    return self._raw_request(new_method, new_url, headers, new_body, timeout)
                return resp
            finally:
                conn.close()
        except socket.timeout as exc:
            raise TimeoutError(f"Request to {url} timed out after {timeout}s") from exc


# ---------------------------------------------------------------------------
# Streaming response (line / SSE)
# ---------------------------------------------------------------------------

class StreamingResponse:
    """Streaming response that yields raw bytes lines as they arrive.

    Acquire via :meth:`Client.stream` (context manager) for true incremental I/O.
    """

    def __init__(self, conn: HTTPConnection, raw: HTTPResponse, url: str) -> None:
        self._conn = conn
        self._raw = raw
        self.url = url
        self.status = raw.status
        self.reason = raw.reason or ""
        self.headers = {k.lower(): v for k, v in raw.getheaders()}
        self._closed = False

    def __enter__(self) -> "StreamingResponse":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        try:
            self._conn.close()
        finally:
            self._closed = True

    def iter_lines(self) -> Iterator[bytes]:
        # http.client's HTTPResponse exposes a file-like interface
        while True:
            line = self._raw.readline()
            if not line:
                return
            yield line.rstrip(b"\r\n")

    def iter_bytes(self, chunk_size: int = 8192) -> Iterator[bytes]:
        """Yield raw response bytes as they arrive."""
        while True:
            chunk = self._raw.read(chunk_size)
            if not chunk:
                return
            yield chunk

    def iter_sse(self) -> Iterator[SSEEvent]:
        return iter_sse(self.iter_lines())

    def raise_for_status(self) -> "StreamingResponse":
        if not (200 <= self.status < 400):
            raise HTTPError(self.status, self.reason)
        return self


def stream_request(
    client: Client,
    method: str,
    url: str,
    *,
    headers: Optional[Headers] = None,
    json: Any = None,
    data: Any = None,
    timeout: Optional[float] = None,
    params: Optional[Mapping[str, Any]] = None,
) -> StreamingResponse:
    """Open a streaming HTTP request. Caller is responsible for ``close()``."""
    full_url = client._build_url(url, params)  # noqa: SLF001 - intentional
    merged_headers = dict(client.config.headers)
    if headers:
        for k, v in headers.items():
            merged_headers[k.lower()] = v
    body, merged_headers = _encode_body(
        json=json, data=data, files=None, headers=merged_headers
    )
    merged_headers.setdefault("user-agent", "agenticaiframework/3.0 (stdlib)")
    if body:
        merged_headers.setdefault("content-length", str(len(body)))
    parsed = urllib.parse.urlsplit(full_url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    if parsed.scheme == "https":
        conn: HTTPConnection = HTTPSConnection(
            host, port, timeout=timeout or client.config.timeout, context=client._ssl_context()
        )
    else:
        conn = HTTPConnection(host, port, timeout=timeout or client.config.timeout)
    conn.request(method, path, body=body if body else None, headers=merged_headers)
    raw_resp = conn.getresponse()
    return StreamingResponse(conn, raw_resp, full_url)


# Add convenience method to Client (defined here to keep file structure clean).
def _client_stream(  # noqa: D401 - method shim
    self: Client, method: str, url: str, **kw: Any
) -> StreamingResponse:
    """Open a streaming HTTP connection (use as a context manager)."""
    return stream_request(self, method, url, **kw)


Client.stream = _client_stream  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Async client (asyncio.open_connection based)
# ---------------------------------------------------------------------------

class AsyncClient:
    """Asynchronous HTTP/1.1 client built on :func:`asyncio.open_connection`.

    Supports the same verbs as :class:`Client`. Stream support is provided via
    :meth:`stream_lines` which yields raw bytes lines.
    """

    def __init__(
        self,
        base_url: str = "",
        *,
        headers: Optional[Headers] = None,
        timeout: float = 60.0,
        verify: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.timeout = timeout
        self.verify = verify

    async def get(self, url: str, **kw: Any) -> Response:
        return await self.request("GET", url, **kw)

    async def post(self, url: str, **kw: Any) -> Response:
        return await self.request("POST", url, **kw)

    async def put(self, url: str, **kw: Any) -> Response:
        return await self.request("PUT", url, **kw)

    async def patch(self, url: str, **kw: Any) -> Response:
        return await self.request("PATCH", url, **kw)

    async def delete(self, url: str, **kw: Any) -> Response:
        return await self.request("DELETE", url, **kw)

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Headers] = None,
        json: Any = None,
        data: Any = None,
        timeout: Optional[float] = None,
    ) -> Response:
        full = self._build_url(url, params)
        merged = dict(self.headers)
        if headers:
            for k, v in headers.items():
                merged[k.lower()] = v
        body, merged = _encode_body(json=json, data=data, files=None, headers=merged)
        merged.setdefault("accept-encoding", "gzip, deflate")
        merged.setdefault("user-agent", "agenticaiframework/3.0 (stdlib-async)")
        merged.setdefault("connection", "close")
        if body:
            merged.setdefault("content-length", str(len(body)))

        parsed = urllib.parse.urlsplit(full)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        merged.setdefault("host", host)

        ssl_ctx = None
        if parsed.scheme == "https":
            ssl_ctx = ssl.create_default_context()
            if not self.verify:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=ssl_ctx),
                timeout=timeout or self.timeout,
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"Async connect to {host}:{port} timed out") from exc

        try:
            req_lines = [f"{method} {path} HTTP/1.1"]
            for k, v in merged.items():
                req_lines.append(f"{k}: {v}")
            req_lines.append("")
            req_lines.append("")
            writer.write("\r\n".join(req_lines).encode("ascii", errors="replace"))
            if body:
                writer.write(body)
            await writer.drain()

            status_line = await asyncio.wait_for(
                reader.readline(), timeout=timeout or self.timeout
            )
            status_text = status_line.decode("iso-8859-1").rstrip()
            parts = status_text.split(" ", 2)
            status = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0
            reason = parts[2] if len(parts) >= 3 else ""

            resp_headers: Headers = {}
            while True:
                hl = await reader.readline()
                if not hl or hl in (b"\r\n", b"\n", b""):
                    break
                line = hl.decode("iso-8859-1").rstrip()
                if ":" in line:
                    k, _, v = line.partition(":")
                    resp_headers[k.strip().lower()] = v.strip()

            raw_body = await self._read_body(reader, resp_headers)
            content = _decode_response_body(raw_body, resp_headers)
            return Response(
                status=status,
                reason=reason,
                headers=resp_headers,
                content=content,
                url=full,
            )
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    async def stream_lines(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        headers: Optional[Headers] = None,
        json: Any = None,
        data: Any = None,
    ) -> AsyncIterator[bytes]:
        """Yield response body lines as they arrive (suitable for SSE)."""
        full = self._build_url(url, params)
        merged = dict(self.headers)
        if headers:
            for k, v in headers.items():
                merged[k.lower()] = v
        body, merged = _encode_body(json=json, data=data, files=None, headers=merged)
        merged.setdefault("user-agent", "agenticaiframework/3.0 (stdlib-async)")
        merged.setdefault("accept", "text/event-stream")
        if body:
            merged.setdefault("content-length", str(len(body)))

        parsed = urllib.parse.urlsplit(full)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        merged.setdefault("host", host)

        ssl_ctx = None
        if parsed.scheme == "https":
            ssl_ctx = ssl.create_default_context()
            if not self.verify:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

        reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
        try:
            req = [f"{method} {path} HTTP/1.1"]
            for k, v in merged.items():
                req.append(f"{k}: {v}")
            req.append("")
            req.append("")
            writer.write("\r\n".join(req).encode("ascii", errors="replace"))
            if body:
                writer.write(body)
            await writer.drain()

            await reader.readline()  # status
            while True:
                hl = await reader.readline()
                if not hl or hl in (b"\r\n", b"\n"):
                    break
            # body lines
            while True:
                line = await reader.readline()
                if not line:
                    return
                yield line.rstrip(b"\r\n")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    # -- helpers ------------------------------------------------------------

    def _build_url(self, url: str, params: Optional[Mapping[str, Any]]) -> str:
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"{self.base_url}/{url.lstrip('/')}" if self.base_url else url
        if params:
            sep = "&" if "?" in url else "?"
            url = (
                url
                + sep
                + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            )
        return url

    @staticmethod
    async def _read_body(reader: asyncio.StreamReader, headers: Headers) -> bytes:
        if headers.get("transfer-encoding", "").lower() == "chunked":
            chunks = bytearray()
            while True:
                size_line = (await reader.readline()).decode("ascii", errors="replace").strip()
                if not size_line:
                    break
                size_hex = size_line.split(";", 1)[0]
                try:
                    size = int(size_hex, 16)
                except ValueError:
                    break
                if size == 0:
                    # Read trailing CRLF (and optional trailers)
                    while True:
                        t = await reader.readline()
                        if not t or t in (b"\r\n", b"\n"):
                            break
                    break
                data = await reader.readexactly(size)
                chunks.extend(data)
                await reader.readline()  # consume trailing CRLF after chunk
            return bytes(chunks)
        if "content-length" in headers:
            try:
                n = int(headers["content-length"])
            except ValueError:
                n = 0
            if n == 0:
                return b""
            return await reader.readexactly(n)
        # Read until EOF
        return await reader.read()


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------

_default_client: Optional[Client] = None


def _client() -> Client:
    global _default_client
    if _default_client is None:
        _default_client = Client()
    return _default_client


def get(url: str, **kw: Any) -> Response:
    return _client().get(url, **kw)


def post(url: str, **kw: Any) -> Response:
    return _client().post(url, **kw)


def request(method: str, url: str, **kw: Any) -> Response:
    return _client().request(method, url, **kw)


__all__ = [
    "AsyncClient",
    "Client",
    "HTTPError",
    "Response",
    "SSEEvent",
    "StreamingResponse",
    "TimeoutError",
    "get",
    "iter_sse",
    "post",
    "request",
    "stream_request",
]
