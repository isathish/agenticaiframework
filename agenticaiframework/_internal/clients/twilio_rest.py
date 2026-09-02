"""Twilio Programmable Messaging REST client (stdlib-only).

Docs: https://www.twilio.com/docs/sms/api/message-resource
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from ..http import Client, HTTPError

_BASE = "https://api.twilio.com/2010-04-01"


class TwilioError(Exception):
    def __init__(self, message: str, *, status: int = 0, code: Optional[int] = None):
        super().__init__(message)
        self.status = status
        self.code = code


class TwilioClient:
    def __init__(self, account_sid: str, auth_token: str, *, timeout: float = 30.0,
                 base_url: str = _BASE) -> None:
        self._sid = account_sid
        self._auth = (account_sid, auth_token)
        self._client = Client(base_url=base_url, timeout=timeout)

    # -- sync -----------------------------------------------------------------

    def send_message(self, *, to: str, from_: Optional[str] = None, body: str = "",
                     media_urls: Optional[List[str]] = None,
                     messaging_service_sid: Optional[str] = None,
                     status_callback: Optional[str] = None) -> Dict[str, Any]:
        form: List[tuple] = [("To", to), ("Body", body)]
        if from_:
            form.append(("From", from_))
        if messaging_service_sid:
            form.append(("MessagingServiceSid", messaging_service_sid))
        if status_callback:
            form.append(("StatusCallback", status_callback))
        for url in media_urls or []:
            form.append(("MediaUrl", url))
        return self._post(f"/Accounts/{self._sid}/Messages.json", form)

    def get_message(self, sid: str) -> Dict[str, Any]:
        resp = self._client.get(f"/Accounts/{self._sid}/Messages/{sid}.json", auth=self._auth)
        return self._handle(resp)

    # -- async ----------------------------------------------------------------

    async def send_message_async(self, **kw) -> Dict[str, Any]:
        return await asyncio.to_thread(self.send_message, **kw)

    async def get_message_async(self, sid: str) -> Dict[str, Any]:
        return await asyncio.to_thread(self.get_message, sid)

    # -- internals ------------------------------------------------------------

    def _post(self, path: str, form: List[tuple]) -> Dict[str, Any]:
        import urllib.parse
        body = urllib.parse.urlencode(form).encode()
        resp = self._client.post(
            path, data=body, auth=self._auth,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return self._handle(resp)

    @staticmethod
    def _handle(resp) -> Dict[str, Any]:
        try:
            payload = resp.json()
        except Exception:  # noqa: BLE001
            payload = {"message": resp.text}
        if not resp.ok:
            raise TwilioError(
                payload.get("message") or f"HTTP {resp.status}",
                status=resp.status, code=payload.get("code"),
            )
        return payload


__all__ = ["TwilioClient", "TwilioError"]
