"""Stdlib-only HTTP server with router, middleware, JSON, and SSE.

Built on top of ``http.server.ThreadingHTTPServer``. Provides a minimal
FastAPI-shaped surface — ``App`` with route decorators (``@app.get``,
``@app.post``, ...) and ``Request`` / ``Response`` helpers.

This is intentionally a small subset: no async, no dependency-injection, no
Pydantic-style body coercion (callers can use ``_internal.schema``).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, Iterable, List, Optional, Pattern, Tuple, Union
from urllib.parse import parse_qs, urlsplit

logger = logging.getLogger(__name__)


JSONLike = Union[Dict[str, Any], List[Any], str, int, float, bool, None]
Handler = Callable[["Request"], "Response"]
Middleware = Callable[["Request", Callable[["Request"], "Response"]], "Response"]


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------

@dataclass
class Request:
    method: str
    path: str
    query: Dict[str, List[str]]
    headers: Dict[str, str]
    body: bytes
    path_params: Dict[str, str] = field(default_factory=dict)
    client: Optional[str] = None

    def json(self) -> Any:
        if not self.body:
            return None
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        return self.headers.get(name.lower(), default)


@dataclass
class Response:
    status: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    @classmethod
    def json(cls, data: JSONLike, status: int = 200, headers: Optional[Dict[str, str]] = None) -> "Response":
        payload = json.dumps(data).encode("utf-8")
        merged = {"Content-Type": "application/json; charset=utf-8"}
        if headers:
            merged.update(headers)
        return cls(status=status, headers=merged, body=payload)

    @classmethod
    def text(cls, body: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> "Response":
        return cls(status=status, headers={"Content-Type": content_type}, body=body.encode("utf-8"))

    @classmethod
    def empty(cls, status: int = 204) -> "Response":
        return cls(status=status, headers={}, body=b"")


class StreamingResponse(Response):
    """SSE / chunked streaming response.

    ``body_iter`` yields ``bytes`` (or ``str``) chunks; the server flushes each.
    """

    def __init__(self, body_iter: Iterable[Union[bytes, str]], *, status: int = 200,
                 content_type: str = "text/event-stream", headers: Optional[Dict[str, str]] = None) -> None:
        merged = {
            "Content-Type": content_type,
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
        if headers:
            merged.update(headers)
        super().__init__(status=status, headers=merged, body=b"")
        self.body_iter = body_iter

    @staticmethod
    def sse(events: Iterable[Tuple[Optional[str], Any]]) -> "StreamingResponse":
        """Helper: build an SSE stream from ``(event_name, data)`` tuples."""
        def _gen():
            for name, data in events:
                if not isinstance(data, (str, bytes)):
                    data = json.dumps(data)
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")
                if name:
                    yield f"event: {name}\n".encode("utf-8")
                yield f"data: {data}\n\n".encode("utf-8")

        return StreamingResponse(_gen())


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

@dataclass
class _Route:
    method: str
    pattern: Pattern[str]
    handler: Handler
    param_names: List[str]


class App:
    """Minimal FastAPI-shaped HTTP application.

    Usage::

        app = App()

        @app.get("/health")
        def health(req):
            return Response.json({"status": "ok"})

        @app.post("/items/{item_id}")
        def update(req):
            return Response.json({"id": req.path_params["item_id"]})

        app.run(host="0.0.0.0", port=8080)
    """

    def __init__(self) -> None:
        self._routes: List[_Route] = []
        self._middlewares: List[Middleware] = []
        self._server: Optional[ThreadingHTTPServer] = None

    # -- routing ------------------------------------------------------

    def route(self, path: str, *, methods: Iterable[str] = ("GET",)) -> Callable[[Handler], Handler]:
        def decorator(handler: Handler) -> Handler:
            pattern, names = _compile_path(path)
            for m in methods:
                self._routes.append(_Route(m.upper(), pattern, handler, names))
            return handler
        return decorator

    def get(self, path: str) -> Callable[[Handler], Handler]:
        return self.route(path, methods=("GET",))

    def post(self, path: str) -> Callable[[Handler], Handler]:
        return self.route(path, methods=("POST",))

    def put(self, path: str) -> Callable[[Handler], Handler]:
        return self.route(path, methods=("PUT",))

    def delete(self, path: str) -> Callable[[Handler], Handler]:
        return self.route(path, methods=("DELETE",))

    def patch(self, path: str) -> Callable[[Handler], Handler]:
        return self.route(path, methods=("PATCH",))

    def middleware(self, fn: Middleware) -> Middleware:
        self._middlewares.append(fn)
        return fn

    # -- dispatch -----------------------------------------------------

    def dispatch(self, request: Request) -> Response:
        def _terminal(req: Request) -> Response:
            for route in self._routes:
                if route.method != req.method:
                    continue
                m = route.pattern.match(req.path)
                if not m:
                    continue
                req.path_params = dict(zip(route.param_names, m.groups()))
                try:
                    result = route.handler(req)
                except HTTPException as exc:
                    return Response.json({"detail": exc.detail}, status=exc.status)
                except Exception:  # noqa: BLE001
                    logger.exception("Unhandled error in %s %s", req.method, req.path)
                    return Response.json({"detail": "Internal Server Error"}, status=500)
                if isinstance(result, Response):
                    return result
                if result is None:
                    return Response.empty()
                return Response.json(result)
            return Response.json({"detail": "Not Found"}, status=404)

        handler: Callable[[Request], Response] = _terminal
        for mw in reversed(self._middlewares):
            next_handler = handler

            def _wrap(req: Request, _mw=mw, _next=next_handler) -> Response:
                return _mw(req, _next)

            handler = _wrap
        return handler(request)

    # -- server -------------------------------------------------------

    def run(self, host: str = "127.0.0.1", port: int = 8000, *, block: bool = True) -> ThreadingHTTPServer:
        app_ref = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                logger.debug("%s - " + format, self.client_address[0], *args)

            def _serve(self, method: str) -> None:
                parts = urlsplit(self.path)
                length = int(self.headers.get("Content-Length", "0") or "0")
                body = self.rfile.read(length) if length > 0 else b""
                request = Request(
                    method=method,
                    path=parts.path,
                    query=parse_qs(parts.query),
                    headers={k.lower(): v for k, v in self.headers.items()},
                    body=body,
                    client=self.client_address[0],
                )
                response = app_ref.dispatch(request)
                self._write(response)

            def _write(self, response: Response) -> None:
                self.send_response(response.status)
                if isinstance(response, StreamingResponse):
                    for k, v in response.headers.items():
                        self.send_header(k, v)
                    self.end_headers()
                    try:
                        for chunk in response.body_iter:
                            if isinstance(chunk, str):
                                chunk = chunk.encode("utf-8")
                            self.wfile.write(chunk)
                            self.wfile.flush()
                    except Exception:  # noqa: BLE001
                        logger.exception("Streaming response failed")
                    return
                body = response.body or b""
                response.headers.setdefault("Content-Length", str(len(body)))
                for k, v in response.headers.items():
                    self.send_header(k, v)
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def do_GET(self) -> None: self._serve("GET")
            def do_POST(self) -> None: self._serve("POST")
            def do_PUT(self) -> None: self._serve("PUT")
            def do_DELETE(self) -> None: self._serve("DELETE")
            def do_PATCH(self) -> None: self._serve("PATCH")
            def do_HEAD(self) -> None: self._serve("HEAD")
            def do_OPTIONS(self) -> None: self._serve("OPTIONS")

        server = ThreadingHTTPServer((host, port), _Handler)
        self._server = server
        if block:
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                server.shutdown()
        else:
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
        return server

    def shutdown(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None


# ---------------------------------------------------------------------------
# Errors & helpers
# ---------------------------------------------------------------------------

class HTTPException(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _compile_path(path: str) -> Tuple[Pattern[str], List[str]]:
    names: List[str] = []
    regex_parts: List[str] = []
    for chunk in re.split(r"(\{[^}]+\})", path):
        if chunk.startswith("{") and chunk.endswith("}"):
            name = chunk[1:-1]
            names.append(name)
            regex_parts.append(r"([^/]+)")
        else:
            regex_parts.append(re.escape(chunk))
    return re.compile("^" + "".join(regex_parts) + "$"), names


# ---------------------------------------------------------------------------
# Built-in middlewares
# ---------------------------------------------------------------------------

def cors_middleware(*, origins: str = "*", methods: str = "GET,POST,PUT,DELETE,OPTIONS,PATCH",
                    headers: str = "*") -> Middleware:
    def _mw(req: Request, nxt: Callable[[Request], Response]) -> Response:
        if req.method == "OPTIONS":
            return Response(status=204, headers={
                "Access-Control-Allow-Origin": origins,
                "Access-Control-Allow-Methods": methods,
                "Access-Control-Allow-Headers": headers,
                "Access-Control-Max-Age": "86400",
            })
        resp = nxt(req)
        resp.headers.setdefault("Access-Control-Allow-Origin", origins)
        return resp

    return _mw


def access_log_middleware() -> Middleware:
    def _mw(req: Request, nxt: Callable[[Request], Response]) -> Response:
        start = time.perf_counter()
        resp = nxt(req)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info("%s %s -> %d (%.1f ms)", req.method, req.path, resp.status, elapsed_ms)
        return resp

    return _mw


__all__ = [
    "App",
    "Request",
    "Response",
    "StreamingResponse",
    "HTTPException",
    "cors_middleware",
    "access_log_middleware",
]
