"""
Weaviate REST client - stdlib HTTP fallback for ``weaviate-client``.

Implements the v1 REST API surface needed by ``WeaviateVectorSearchTool``:
schema management, object CRUD, GraphQL queries.

Auth supports anonymous (default), API-key, and OIDC bearer tokens.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .. import http as _http  # stdlib HTTP wrapper from agenticaiframework._internal


class WeaviateError(Exception):
    """Raised when the Weaviate REST API returns an error."""


class WeaviateClient:
    """Minimal Weaviate v1 REST client."""

    def __init__(
        self,
        url: str = "http://localhost:8080",
        api_key: Optional[str] = None,
        bearer_token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = url.rstrip("/")
        self.api_key = api_key
        self.bearer_token = bearer_token
        self.timeout = timeout

    # --------------------------------------------------------------- helpers
    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        token = self.bearer_token or self.api_key
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
            if qs:
                url = f"{url}?{qs}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        resp = _http.request(
            method,
            url,
            data=data,
            headers=self._headers(),
            timeout=self.timeout,
        )
        if resp.status_code >= 400:
            raise WeaviateError(f"{method} {path} -> {resp.status_code}: {resp.text}")
        if not resp.text:
            return None
        try:
            return resp.json()
        except Exception:
            return resp.text

    # --------------------------------------------------------------- schema
    def get_schema(self) -> Dict[str, Any]:
        return self._request("GET", "/v1/schema")

    def class_exists(self, class_name: str) -> bool:
        try:
            self._request("GET", f"/v1/schema/{class_name}")
            return True
        except WeaviateError:
            return False

    def create_class(
        self,
        class_name: str,
        properties: Optional[List[Dict[str, Any]]] = None,
        vectorizer: str = "none",
    ) -> Dict[str, Any]:
        body = {
            "class": class_name,
            "vectorizer": vectorizer,
            "properties": properties or [
                {"name": "content", "dataType": ["text"]},
                {"name": "title", "dataType": ["text"]},
            ],
        }
        return self._request("POST", "/v1/schema", body=body)

    def delete_class(self, class_name: str) -> None:
        self._request("DELETE", f"/v1/schema/{class_name}")

    # --------------------------------------------------------------- objects
    def upsert_object(
        self,
        class_name: str,
        properties: Dict[str, Any],
        vector: Optional[List[float]] = None,
        object_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {"class": class_name, "properties": properties}
        if vector is not None:
            body["vector"] = vector
        if object_id is not None:
            body["id"] = object_id
        return self._request("POST", "/v1/objects", body=body)

    def delete_object(self, class_name: str, object_id: str) -> None:
        self._request("DELETE", f"/v1/objects/{class_name}/{object_id}")

    # --------------------------------------------------------------- graphql
    def graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body: Dict[str, Any] = {"query": query}
        if variables:
            body["variables"] = variables
        result = self._request("POST", "/v1/graphql", body=body)
        if isinstance(result, dict) and result.get("errors"):
            raise WeaviateError(f"GraphQL errors: {result['errors']}")
        return result or {}

    # --------------------------------------------------------------- search
    def near_vector(
        self,
        class_name: str,
        vector: List[float],
        properties: List[str],
        limit: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        prop_block = " ".join(properties) + " _additional { id distance }"
        where_block = f", where: {_to_graphql(where)}" if where else ""
        query = (
            f'{{ Get {{ {class_name}('
            f'nearVector: {{ vector: {json.dumps(vector)} }}, '
            f"limit: {limit}{where_block}"
            f") {{ {prop_block} }} }} }}"
        )
        result = self.graphql(query)
        return _extract_hits(result, class_name)

    def bm25(
        self,
        class_name: str,
        query: str,
        properties: List[str],
        limit: int = 10,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        prop_block = " ".join(properties) + " _additional { id score }"
        where_block = f", where: {_to_graphql(where)}" if where else ""
        gql = (
            f'{{ Get {{ {class_name}('
            f'bm25: {{ query: {json.dumps(query)} }}, '
            f"limit: {limit}{where_block}"
            f") {{ {prop_block} }} }} }}"
        )
        result = self.graphql(gql)
        return _extract_hits(result, class_name)

    def hybrid(
        self,
        class_name: str,
        query: str,
        properties: List[str],
        limit: int = 10,
        alpha: float = 0.5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        prop_block = " ".join(properties) + " _additional { id score }"
        where_block = f", where: {_to_graphql(where)}" if where else ""
        gql = (
            f'{{ Get {{ {class_name}('
            f'hybrid: {{ query: {json.dumps(query)}, alpha: {alpha} }}, '
            f"limit: {limit}{where_block}"
            f") {{ {prop_block} }} }} }}"
        )
        result = self.graphql(gql)
        return _extract_hits(result, class_name)


def _extract_hits(result: Dict[str, Any], class_name: str) -> List[Dict[str, Any]]:
    return (
        result.get("data", {})
        .get("Get", {})
        .get(class_name, [])
        or []
    )


def _to_graphql(value: Any) -> str:
    """Convert a Python value into GraphQL inline-literal syntax."""
    if isinstance(value, dict):
        body = ", ".join(f"{k}: {_to_graphql(v)}" for k, v in value.items())
        return "{" + body + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_to_graphql(v) for v in value) + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


__all__ = ["WeaviateClient", "WeaviateError"]
