"""Shared async health-probe primitives (HTTP + TCP) used by the discovery,
service-registry, deployment and blue/green modules.

Stdlib-only: HTTP probes go through :class:`agenticaiframework._internal.http.AsyncClient`,
TCP probes through :func:`asyncio.open_connection`.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .http import AsyncClient


@dataclass
class ProbeResult:
    ok: bool
    latency_ms: float
    status_code: Optional[int] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


async def http_probe(
    url: str,
    *,
    timeout: float = 5.0,
    method: str = "GET",
    expected_status: range = range(200, 400),
    headers: Optional[Dict[str, str]] = None,
    verify: bool = True,
) -> ProbeResult:
    """Issue one HTTP request and report whether it looks healthy."""
    start = time.perf_counter()
    client = AsyncClient(timeout=timeout, verify=verify)
    try:
        resp = await asyncio.wait_for(
            client.request(method, url, headers=headers, timeout=timeout),
            timeout=timeout,
        )
        latency = (time.perf_counter() - start) * 1000
        ok = resp.status in expected_status
        body_preview = resp.text[:200] if resp.content else ""
        return ProbeResult(
            ok=ok,
            latency_ms=latency,
            status_code=resp.status,
            message="OK" if ok else f"HTTP {resp.status} {resp.reason}".strip(),
            details={"url": url, "status": resp.status, "body": body_preview},
        )
    except asyncio.TimeoutError:
        return ProbeResult(ok=False, latency_ms=timeout * 1000,
                           message=f"Timed out after {timeout}s", details={"url": url})
    except Exception as exc:  # noqa: BLE001 - any network failure = unhealthy
        return ProbeResult(ok=False, latency_ms=(time.perf_counter() - start) * 1000,
                           message=f"{type(exc).__name__}: {exc}", details={"url": url})


async def tcp_probe(host: str, port: int, *, timeout: float = 5.0) -> ProbeResult:
    """Attempt a TCP connect and report success/latency."""
    start = time.perf_counter()
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        return ProbeResult(ok=True, latency_ms=(time.perf_counter() - start) * 1000,
                           message="OK", details={"host": host, "port": port})
    except asyncio.TimeoutError:
        return ProbeResult(ok=False, latency_ms=timeout * 1000,
                           message=f"Timed out after {timeout}s", details={"host": host, "port": port})
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(ok=False, latency_ms=(time.perf_counter() - start) * 1000,
                           message=f"{type(exc).__name__}: {exc}", details={"host": host, "port": port})


__all__ = ["ProbeResult", "http_probe", "tcp_probe"]
