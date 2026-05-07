"""Pure-Python Qdrant REST client (stdlib-only).

Exposes the small subset used by ``agenticaiframework.tools.database.vector_tools``:

* ``search(collection, vector, limit, filter, with_payload)``
* ``upsert(collection, points)``
* ``create_collection(collection, vector_size, distance)``
* ``delete_collection(collection)``

Anything richer should pull in the official ``qdrant-client``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from .. import http as _http


@dataclass
class QdrantHit:
    id: Any
    score: float
    payload: Optional[Dict[str, Any]] = None
    vector: Optional[List[float]] = None


class QdrantClient:
    """Minimal REST client for a Qdrant server."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.url = url.rstrip("/")
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["api-key"] = api_key
        self._client = _http.Client(base_url=self.url, headers=headers, timeout=timeout)

    # -- collections -------------------------------------------------

    def create_collection(
        self,
        collection: str,
        vector_size: int,
        distance: str = "Cosine",
    ) -> Dict[str, Any]:
        payload = {"vectors": {"size": vector_size, "distance": distance}}
        resp = self._client.put(f"/collections/{collection}", json=payload).raise_for_status()
        return resp.json()

    def delete_collection(self, collection: str) -> Dict[str, Any]:
        resp = self._client.delete(f"/collections/{collection}").raise_for_status()
        return resp.json()

    def collection_exists(self, collection: str) -> bool:
        resp = self._client.get(f"/collections/{collection}")
        return resp.status == 200

    # -- points ------------------------------------------------------

    def upsert(
        self,
        collection: str,
        points: List[Mapping[str, Any]],
        wait: bool = True,
    ) -> Dict[str, Any]:
        payload = {"points": [
            {
                "id": p["id"],
                "vector": p["vector"],
                "payload": p.get("payload", {}),
            }
            for p in points
        ]}
        path = f"/collections/{collection}/points"
        if wait:
            path += "?wait=true"
        resp = self._client.put(path, json=payload).raise_for_status()
        return resp.json()

    def search(
        self,
        collection: str,
        vector: List[float],
        limit: int = 10,
        filter: Optional[Mapping[str, Any]] = None,
        with_payload: bool = True,
        with_vector: bool = False,
    ) -> List[QdrantHit]:
        payload: Dict[str, Any] = {
            "vector": list(vector),
            "limit": limit,
            "with_payload": with_payload,
            "with_vector": with_vector,
        }
        if filter:
            payload["filter"] = dict(filter)
        resp = self._client.post(
            f"/collections/{collection}/points/search", json=payload
        ).raise_for_status()
        result = resp.json().get("result", [])
        return [
            QdrantHit(
                id=hit.get("id"),
                score=hit.get("score", 0.0),
                payload=hit.get("payload"),
                vector=hit.get("vector"),
            )
            for hit in result
        ]

    def delete_points(self, collection: str, ids: List[Any]) -> Dict[str, Any]:
        payload = {"points": list(ids)}
        resp = self._client.post(
            f"/collections/{collection}/points/delete", json=payload
        ).raise_for_status()
        return resp.json()


def build_filter_from_dict(conditions: Mapping[str, Any]) -> Dict[str, Any]:
    """Translate ``{field: value}`` into a Qdrant ``must`` filter."""
    return {
        "must": [
            {"key": key, "match": {"value": value}}
            for key, value in conditions.items()
        ]
    }


__all__ = ["QdrantClient", "QdrantHit", "build_filter_from_dict"]
