"""Model Context Protocol (MCP) runtime — stdlib-only.

Implements the MCP 2025-06-18 wire protocol (JSON-RPC 2.0 over stdio).
References: https://modelcontextprotocol.io/specification/2025-06-18

Subset of methods supported:

- ``initialize``
- ``tools/list`` and ``tools/call``
- ``resources/list`` and ``resources/read``
- ``prompts/list`` and ``prompts/get``
- ``ping``
- ``notifications/initialized``

The server pulls tools from the framework's :class:`ToolRegistry`, so any
``BaseTool`` registered with the framework is automatically exposed via MCP.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TextIO

from .registry import ToolRegistry, tool_registry

logger = logging.getLogger(__name__)


PROTOCOL_VERSION = "2025-06-18"


# ---------------------------------------------------------------------------
# JSON-RPC primitives
# ---------------------------------------------------------------------------

@dataclass
class JsonRpcError:
    code: int
    message: str
    data: Any = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            out["data"] = self.data
        return out


PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _make_response(id_: Any, result: Any = None, error: Optional[JsonRpcError] = None) -> Dict[str, Any]:
    msg: Dict[str, Any] = {"jsonrpc": "2.0", "id": id_}
    if error is not None:
        msg["error"] = error.to_dict()
    else:
        msg["result"] = result
    return msg


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

@dataclass
class MCPServerInfo:
    name: str = "agenticaiframework"
    version: str = "3.0.0"


@dataclass
class MCPServer:
    """Stdio JSON-RPC server exposing the framework's tools/resources/prompts.

    Usage::

        server = MCPServer()
        server.add_resource("memory://hello", lambda: "Hello, world!")
        server.serve_forever()
    """

    registry: ToolRegistry = field(default_factory=lambda: tool_registry)
    server_info: MCPServerInfo = field(default_factory=MCPServerInfo)
    input_stream: TextIO = field(default_factory=lambda: sys.stdin)
    output_stream: TextIO = field(default_factory=lambda: sys.stdout)

    _resources: Dict[str, Callable[[], str]] = field(default_factory=dict)
    _prompts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    _initialized: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # -- registration --------------------------------------------------

    def add_resource(self, uri: str, getter: Callable[[], str], *, mime: str = "text/plain") -> None:
        self._resources[uri] = getter
        # Store mime by prefixing key (kept simple)
        self._resources.setdefault(uri + "::mime", lambda m=mime: m)  # type: ignore[arg-type]

    def add_prompt(
        self,
        name: str,
        template: str,
        *,
        description: str = "",
        arguments: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._prompts[name] = {
            "name": name,
            "description": description,
            "template": template,
            "arguments": arguments or [],
        }

    # -- lifecycle -----------------------------------------------------

    def serve_forever(self) -> None:
        """Read JSON-RPC messages from stdin and write responses to stdout."""
        for line in self.input_stream:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                self._write(_make_response(None, error=JsonRpcError(PARSE_ERROR, "Parse error")))
                continue
            self._dispatch(msg)

    def handle_message(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Synchronously handle a single message; useful for tests."""
        return self._dispatch(msg, write=False)

    # -- dispatch ------------------------------------------------------

    def _dispatch(self, msg: Dict[str, Any], *, write: bool = True) -> Optional[Dict[str, Any]]:
        if msg.get("jsonrpc") != "2.0":
            response = _make_response(
                msg.get("id"), error=JsonRpcError(INVALID_REQUEST, "Invalid JSON-RPC version")
            )
            if write:
                self._write(response)
            return response

        method = msg.get("method")
        params = msg.get("params") or {}
        msg_id = msg.get("id")

        # Notifications (no id) — no response expected
        if msg_id is None:
            try:
                self._handle_notification(method, params)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to handle notification %s", method)
            return None

        try:
            result = self._handle_method(method, params)
            response = _make_response(msg_id, result=result)
        except _RpcError as exc:
            response = _make_response(msg_id, error=exc.error)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Internal error in MCP handler %s", method)
            response = _make_response(
                msg_id, error=JsonRpcError(INTERNAL_ERROR, str(exc))
            )
        if write:
            self._write(response)
        return response

    def _write(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            self.output_stream.write(json.dumps(payload) + "\n")
            self.output_stream.flush()

    # -- method handlers ----------------------------------------------

    def _handle_method(self, method: Optional[str], params: Dict[str, Any]) -> Any:
        if method == "initialize":
            self._initialized = True
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "serverInfo": {"name": self.server_info.name, "version": self.server_info.version},
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"listChanged": False},
                    "prompts": {"listChanged": False},
                    "logging": {},
                },
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": self._list_tools()}
        if method == "tools/call":
            return self._call_tool(params)
        if method == "resources/list":
            return {"resources": self._list_resources()}
        if method == "resources/read":
            return self._read_resource(params)
        if method == "prompts/list":
            return {"prompts": [
                {k: v for k, v in p.items() if k != "template"}
                for p in self._prompts.values()
            ]}
        if method == "prompts/get":
            return self._get_prompt(params)
        raise _RpcError(JsonRpcError(METHOD_NOT_FOUND, f"Method not found: {method}"))

    def _handle_notification(self, method: Optional[str], params: Dict[str, Any]) -> None:
        if method == "notifications/initialized":
            self._initialized = True

    # -- tool helpers --------------------------------------------------

    def _list_tools(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for name in self.registry.list_tools():
            tool = self.registry.get_tool(name)
            if tool is None:
                continue
            schema = getattr(tool, "input_schema", None) or {
                "type": "object",
                "properties": {},
            }
            out.append(
                {
                    "name": name,
                    "description": getattr(tool, "description", "") or getattr(tool.config, "description", ""),
                    "inputSchema": schema,
                }
            )
        return out

    def _call_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not name:
            raise _RpcError(JsonRpcError(INVALID_PARAMS, "tools/call requires 'name'"))
        tool = self.registry.get_tool(name)
        if tool is None:
            return {
                "content": [{"type": "text", "text": f"Tool not found: {name}"}],
                "isError": True,
            }
        try:
            result = tool.execute(**arguments) if hasattr(tool, "execute") else tool(**arguments)
            text = ""
            is_error = False
            if hasattr(result, "is_success"):
                is_error = not result.is_success
                text = str(result.data) if not is_error else (result.error or "")
            else:
                text = str(result)
            return {
                "content": [{"type": "text", "text": text}],
                "isError": is_error,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            }

    # -- resource helpers ---------------------------------------------

    def _list_resources(self) -> List[Dict[str, Any]]:
        return [
            {"uri": uri, "name": uri, "mimeType": (self._resources.get(uri + "::mime") or (lambda: "text/plain"))()}
            for uri in self._resources
            if not uri.endswith("::mime")
        ]

    def _read_resource(self, params: Dict[str, Any]) -> Dict[str, Any]:
        uri = params.get("uri")
        if not uri:
            raise _RpcError(JsonRpcError(INVALID_PARAMS, "resources/read requires 'uri'"))
        getter = self._resources.get(uri)
        if getter is None:
            raise _RpcError(JsonRpcError(INVALID_PARAMS, f"Resource not found: {uri}"))
        try:
            text = getter()
        except Exception as exc:  # noqa: BLE001
            raise _RpcError(JsonRpcError(INTERNAL_ERROR, str(exc))) from exc
        mime_getter = self._resources.get(uri + "::mime")
        mime = mime_getter() if mime_getter else "text/plain"
        return {"contents": [{"uri": uri, "mimeType": mime, "text": text}]}

    # -- prompt helpers -----------------------------------------------

    def _get_prompt(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        if not name or name not in self._prompts:
            raise _RpcError(JsonRpcError(INVALID_PARAMS, f"Prompt not found: {name}"))
        prompt = self._prompts[name]
        args = params.get("arguments") or {}
        text = prompt["template"]
        for k, v in args.items():
            text = text.replace("{" + k + "}", str(v))
        return {
            "description": prompt.get("description", ""),
            "messages": [
                {"role": "user", "content": {"type": "text", "text": text}}
            ],
        }


# ---------------------------------------------------------------------------
# Client (stdio)
# ---------------------------------------------------------------------------

class _RpcError(Exception):
    def __init__(self, error: JsonRpcError):
        super().__init__(error.message)
        self.error = error


@dataclass
class MCPClient:
    """Synchronous stdio client.

    Spawns a child process and exchanges JSON-RPC messages over its stdio.
    """

    command: List[str]
    _proc: Any = None
    _next_id: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        import subprocess  # local import — security-gated

        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def initialize(self) -> Dict[str, Any]:
        return self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "clientInfo": {"name": "agenticaiframework", "version": "3.0.0"},
                "capabilities": {},
            },
        )

    def list_tools(self) -> List[Dict[str, Any]]:
        return self.request("tools/list", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return self.request("tools/call", {"name": name, "arguments": arguments or {}})

    def request(self, method: str, params: Dict[str, Any]) -> Any:
        if self._proc is None:
            raise RuntimeError("MCP client process is not running")
        with self._lock:
            self._next_id += 1
            msg_id = self._next_id
        msg = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
        assert self._proc.stdin is not None
        assert self._proc.stdout is not None
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()
        # Read responses until we see one matching our id
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed stdout")
            try:
                resp = json.loads(line)
            except json.JSONDecodeError:
                continue
            if resp.get("id") != msg_id:
                continue
            if "error" in resp:
                err = resp["error"]
                raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")
            return resp.get("result")

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.terminate()
            except Exception:  # noqa: BLE001
                pass
            self._proc = None


__all__ = [
    "MCPClient",
    "MCPServer",
    "MCPServerInfo",
    "PROTOCOL_VERSION",
]
