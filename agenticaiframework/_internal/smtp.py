"""Thin stdlib SMTP sender shared by the email / notification modules.

Wraps :mod:`smtplib` so async callers can ``await send_message(...)`` without
blocking the event loop (delivery runs in a worker thread).
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.message import Message
from typing import Iterable, Optional


def send_message_sync(
    msg: Message,
    *,
    host: str,
    port: int = 587,
    username: str = "",
    password: str = "",
    use_tls: bool = True,
    use_ssl: Optional[bool] = None,
    timeout: float = 30.0,
    from_addr: Optional[str] = None,
    to_addrs: Optional[Iterable[str]] = None,
) -> dict:
    """Deliver ``msg`` over SMTP. Returns ``smtplib`` refused-recipient dict.

    ``use_ssl`` defaults to ``True`` for port 465 (implicit TLS); otherwise
    STARTTLS is negotiated when ``use_tls`` is set.
    """
    if use_ssl is None:
        use_ssl = port == 465
    context = ssl.create_default_context()
    if use_ssl:
        server: smtplib.SMTP = smtplib.SMTP_SSL(host, port, timeout=timeout, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=timeout)
    try:
        server.ehlo()
        if use_tls and not use_ssl and server.has_extn("starttls"):
            server.starttls(context=context)
            server.ehlo()
        if username:
            server.login(username, password)
        return server.send_message(msg, from_addr=from_addr, to_addrs=list(to_addrs) if to_addrs else None)
    finally:
        try:
            server.quit()
        except Exception:  # noqa: BLE001 - connection already gone
            pass


async def send_message(msg: Message, **kw) -> dict:
    """Async wrapper around :func:`send_message_sync`."""
    return await asyncio.to_thread(send_message_sync, msg, **kw)


__all__ = ["send_message", "send_message_sync"]
