"""Pure-Python Azure Cosmos DB SQL API REST client (stdlib-only).

Implements the small subset used by ``agenticaiframework.enterprise.adapters``:

* ``create_database_if_not_exists(id)``
* ``create_container_if_not_exists(database, id, partition_key="/id")``
* ``upsert_item(database, container, item)``
* ``query_items(database, container, query, enable_cross_partition_query)``
* ``delete_item(database, container, item_id, partition_key)``

Auth: Master Key signed via HMAC-SHA256 over a canonicalized request string.

Reference: https://learn.microsoft.com/en-us/rest/api/cosmos-db/
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import hmac
import json
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .. import http as _http


_API_VERSION = "2018-12-31"


def parse_connection_string(conn_str: str) -> Dict[str, str]:
    parts: Dict[str, str] = {}
    for piece in conn_str.split(";"):
        if "=" in piece:
            k, v = piece.split("=", 1)
            parts[k.strip()] = v.strip()
    return parts


def _utcnow_rfc1123() -> str:
    return datetime.datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")


def _generate_auth_token(
    *,
    verb: str,
    resource_type: str,
    resource_link: str,
    date: str,
    master_key: str,
) -> str:
    """Build the Cosmos master-key authorization header."""
    key_bytes = base64.b64decode(master_key)
    string_to_sign = (
        f"{verb.lower()}\n{resource_type.lower()}\n{resource_link}\n{date.lower()}\n\n"
    )
    sig = hmac.new(key_bytes, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = base64.b64encode(sig).decode("ascii")
    token = f"type=master&ver=1.0&sig={sig_b64}"
    return urllib.parse.quote(token, safe="-_.~")


@dataclass
class CosmosClient:
    endpoint: str  # e.g. "https://acct.documents.azure.com"
    master_key: str
    timeout: float = 30.0

    @classmethod
    def from_connection_string(cls, conn_str: str) -> "CosmosClient":
        parts = parse_connection_string(conn_str)
        return cls(
            endpoint=parts.get("AccountEndpoint", "").rstrip("/"),
            master_key=parts.get("AccountKey", ""),
        )

    def _request(
        self,
        method: str,
        resource_type: str,
        resource_link: str,
        path: str,
        *,
        body: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        date = _utcnow_rfc1123()
        token = _generate_auth_token(
            verb=method,
            resource_type=resource_type,
            resource_link=resource_link,
            date=date,
            master_key=self.master_key,
        )
        headers: Dict[str, str] = {
            "Authorization": token,
            "x-ms-date": date,
            "x-ms-version": _API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)
        url = f"{self.endpoint}{path}"
        client = _http.Client(timeout=self.timeout)
        if method.upper() == "GET":
            return client.get(url, headers=headers)
        if method.upper() == "DELETE":
            return client.delete(url, headers=headers)
        data = json.dumps(body).encode("utf-8") if body is not None else b""
        return client.request(method.upper(), url, data=data, headers=headers)

    # -- databases ---------------------------------------------------

    def create_database_if_not_exists(self, database_id: str) -> Dict[str, Any]:
        # Try GET first
        get_resp = self._request("GET", "dbs", f"dbs/{database_id}", f"/dbs/{database_id}")
        if get_resp.status == 200:
            return get_resp.json()
        # Create
        resp = self._request(
            "POST", "dbs", "", "/dbs",
            body={"id": database_id},
        )
        if resp.status not in (200, 201, 409):
            resp.raise_for_status()
        return resp.json() if resp.content else {"id": database_id}

    # -- containers --------------------------------------------------

    def create_container_if_not_exists(
        self,
        database_id: str,
        container_id: str,
        partition_key_path: str = "/id",
    ) -> Dict[str, Any]:
        link = f"dbs/{database_id}/colls/{container_id}"
        get_resp = self._request("GET", "colls", link, f"/{link}")
        if get_resp.status == 200:
            return get_resp.json()
        resp = self._request(
            "POST", "colls",
            f"dbs/{database_id}",
            f"/dbs/{database_id}/colls",
            body={
                "id": container_id,
                "partitionKey": {"paths": [partition_key_path], "kind": "Hash"},
            },
        )
        if resp.status not in (200, 201, 409):
            resp.raise_for_status()
        return resp.json() if resp.content else {"id": container_id}

    # -- items -------------------------------------------------------

    def upsert_item(
        self,
        database_id: str,
        container_id: str,
        item: Dict[str, Any],
        *,
        partition_key: Optional[Any] = None,
    ) -> Dict[str, Any]:
        link = f"dbs/{database_id}/colls/{container_id}"
        pk = partition_key if partition_key is not None else item.get("id")
        extra = {
            "x-ms-documentdb-is-upsert": "true",
            "x-ms-documentdb-partitionkey": json.dumps([pk]),
        }
        resp = self._request(
            "POST", "docs", link, f"/{link}/docs",
            body=item, extra_headers=extra,
        )
        resp.raise_for_status()
        return resp.json()

    def query_items(
        self,
        database_id: str,
        container_id: str,
        query: str,
        *,
        parameters: Optional[List[Dict[str, Any]]] = None,
        enable_cross_partition_query: bool = False,
    ) -> Iterable[Dict[str, Any]]:
        link = f"dbs/{database_id}/colls/{container_id}"
        body = {"query": query, "parameters": parameters or []}
        extra = {
            "Content-Type": "application/query+json",
            "x-ms-documentdb-isquery": "true",
        }
        if enable_cross_partition_query:
            extra["x-ms-documentdb-query-enablecrosspartition"] = "true"
        all_items: List[Dict[str, Any]] = []
        continuation: Optional[str] = None
        while True:
            headers = dict(extra)
            if continuation:
                headers["x-ms-continuation"] = continuation
            resp = self._request(
                "POST", "docs", link, f"/{link}/docs",
                body=body, extra_headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            all_items.extend(data.get("Documents", []))
            continuation = resp.headers.get("x-ms-continuation")
            if not continuation:
                break
        return all_items

    def delete_item(
        self,
        database_id: str,
        container_id: str,
        item_id: str,
        partition_key: Any,
    ) -> None:
        link = f"dbs/{database_id}/colls/{container_id}/docs/{item_id}"
        extra = {"x-ms-documentdb-partitionkey": json.dumps([partition_key])}
        resp = self._request(
            "DELETE", "docs", link, f"/{link}",
            extra_headers=extra,
        )
        if resp.status not in (200, 204, 404):
            resp.raise_for_status()


__all__ = ["CosmosClient", "parse_connection_string"]
